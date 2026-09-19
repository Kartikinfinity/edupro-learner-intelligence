"""Leakage-controlled train/validation/test splits.

Two protocols, both pre-registered in ``research/recommendation_evaluation_plan.md``
§2 before any result was seen:

Protocol A — global temporal split (**primary**)
    One calendar cut for every learner. Leakage-free by construction: the model
    never sees an interaction that had not happened at the moment being predicted.

Protocol B — per-user leave-one-out (**secondary, leakage-bearing**)
    Each learner's most recent interaction is held out. Every learner's cut is a
    *different* calendar date, so training contains interactions that occur after
    some learners' test points. Reported for comparability with published work and
    always labelled as leaking.

The split is computed **once** and persisted; no experiment re-derives it. A
subtle difference in tie-breaking would otherwise make results non-comparable,
and the cross-method comparison is the entire basis for model selection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

import pandas as pd

from edupro import config

#: Quantiles of ``TransactionDate`` used for the two cuts. Fixed in Phase 1.
VALIDATION_QUANTILE: float = 0.70
TEST_QUANTILE: float = 0.80

#: Pre-registered viability threshold for Protocol A. If fewer learners than this
#: are evaluable, the primary protocol switches to B and every reported figure is
#: labelled leakage-bearing.
PROTOCOL_A_MIN_EVALUABLE: int = 300


@dataclass(frozen=True)
class TemporalSplit:
    """A global temporal split with its evaluability statistics."""

    validation_date: pd.Timestamp
    test_date: pd.Timestamp
    n_train: int
    n_validation: int
    n_test: int
    n_evaluable_learners: int
    protocol_a_viable: bool

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["validation_date"] = str(self.validation_date.date())
        payload["test_date"] = str(self.test_date.date())
        return payload


def global_temporal_split(interactions: pd.DataFrame) -> TemporalSplit:
    """Compute Protocol A's cut dates and report how many learners it can evaluate.

    A learner is *evaluable* under Protocol A only if they have at least one
    interaction before the test cut (to build features from) and at least one on
    or after it (to predict).
    """
    dates = interactions[config.COL_TRANSACTION_DATE]
    validation_date = dates.quantile(VALIDATION_QUANTILE)
    test_date = dates.quantile(TEST_QUANTILE)

    train = interactions[dates < validation_date]
    validation = interactions[(dates >= validation_date) & (dates < test_date)]
    test = interactions[dates >= test_date]

    before_test = set(interactions.loc[dates < test_date, config.KEY_USER])
    in_test = set(test[config.KEY_USER])
    evaluable = before_test & in_test

    return TemporalSplit(
        validation_date=validation_date,
        test_date=test_date,
        n_train=len(train),
        n_validation=len(validation),
        n_test=len(test),
        n_evaluable_learners=len(evaluable),
        protocol_a_viable=len(evaluable) >= PROTOCOL_A_MIN_EVALUABLE,
    )


def apply_global_split(
    interactions: pd.DataFrame, split: TemporalSplit
) -> dict[str, pd.DataFrame]:
    """Partition interactions into train / validation / test by the split dates.

    ``train`` is everything before the validation cut; ``fit`` is everything
    before the *test* cut — the frame to build final features and popularity from
    once hyperparameters are settled.
    """
    dates = interactions[config.COL_TRANSACTION_DATE]
    return {
        "train": interactions[dates < split.validation_date].copy(),
        "validation": interactions[
            (dates >= split.validation_date) & (dates < split.test_date)
        ].copy(),
        "fit": interactions[dates < split.test_date].copy(),
        "test": interactions[dates >= split.test_date].copy(),
    }


def leave_one_out_split(interactions: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Protocol B: hold out each learner's most recent interaction.

    **This split leaks** by the global-timeline definition. It is provided because
    it is the field's most common protocol and omitting it would make these
    results incomparable — never because it is defensible on its own.

    Learners with a single interaction are excluded from the held-out frame: they
    cannot be evaluated as personalised-recommendation users (CLAUDE.md §12).
    """
    ordered = interactions.sort_values(
        [config.KEY_USER, config.COL_TRANSACTION_DATE, config.KEY_TRANSACTION]
    )
    counts = ordered.groupby(config.KEY_USER)[config.KEY_TRANSACTION].transform("size")
    is_last = ordered.groupby(config.KEY_USER).cumcount() == (counts - 1)
    evaluable = counts >= 2

    return {
        "train": ordered[~(is_last & evaluable)].copy(),
        "test": ordered[is_last & evaluable].copy(),
        "excluded_single_interaction": ordered[counts == 1].copy(),
    }


def persist_split(
    split: TemporalSplit,
    frames: dict[str, pd.DataFrame],
    destination: Path | None = None,
) -> Path:
    """Write the split metadata and its transaction-ID sets to disk.

    Only the transaction IDs are stored, not copies of the data: the split is a
    partition of the raw interactions, and storing IDs keeps it unambiguous that
    no rows were altered.
    """
    destination = destination or (config.PROCESSED_DIR / "splits")
    destination.mkdir(parents=True, exist_ok=True)

    metadata = split.to_dict()
    metadata["partitions"] = {}
    for name, frame in frames.items():
        ids = frame[config.KEY_TRANSACTION].tolist()
        (destination / f"{name}_transaction_ids.json").write_text(
            json.dumps(ids), encoding="utf-8"
        )
        metadata["partitions"][name] = len(ids)

    path = destination / "split_metadata.json"
    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return path
