"""The evaluation harness: one protocol, applied identically to every method.

Pre-registered in ``research/recommendation_evaluation_plan.md`` §2 **before any
recommender existed**, and confirmed viable in Phase 2 (EXP-004: 791 evaluable
learners against a threshold of 300).

**Protocol A — global temporal split (primary).** One calendar cut for every
learner. Leakage-free by construction: the model never sees an interaction that
had not happened at the moment being predicted [R25].

**Protocol B — per-user leave-one-out (secondary, leakage-bearing).** Each
learner's cut is a different calendar date, so training contains interactions
occurring after some learners' test points. Reported for comparability with
published work and labelled as leaking wherever it appears.

Every metric is reported **per tier** as well as in aggregate: CLAUDE.md §12
forbids evaluating one-interaction learners as though they were
personalised-recommendation users, and an aggregate-only report would hide whether
personalisation works where it is supposed to.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from edupro import config
from edupro.evaluation.metrics import MetricAccumulator, RankingMetrics
from edupro.recommendation.base import FitContext
from edupro.recommendation.hybrid import tier_of

#: K values reported. 10 is primary — a plausible dashboard page size; 5 and 20
#: test rank sensitivity. 20 is a third of this catalogue, so it mainly shows
#: where the measure saturates.
DEFAULT_KS: tuple[int, ...] = (5, 10, 20)


@dataclass
class EvaluationSet:
    """Held-out ground truth: learner -> the course positions they went on to take."""

    relevant: dict[str, set[int]]
    protocol: str
    #: Training-window history length per learner, used for tier routing.
    history_length: dict[str, int] = field(default_factory=dict)

    @property
    def users(self) -> list[str]:
        return list(self.relevant)

    def tier_of_user(self, user: str) -> str:
        return tier_of(self.history_length.get(user, 0))

    def summary(self) -> dict[str, object]:
        tiers: dict[str, int] = {}
        for user in self.relevant:
            tiers[self.tier_of_user(user)] = tiers.get(self.tier_of_user(user), 0) + 1
        return {
            "protocol": self.protocol,
            "n_users": len(self.relevant),
            "n_held_out_interactions": sum(len(v) for v in self.relevant.values()),
            "mean_held_out_per_user": round(
                np.mean([len(v) for v in self.relevant.values()]), 4
            ) if self.relevant else 0.0,
            "users_by_tier": tiers,
        }


def build_evaluation_set(
    training: pd.DataFrame,
    held_out: pd.DataFrame,
    context: FitContext,
    protocol: str,
) -> EvaluationSet:
    """Assemble ground truth from a training frame and a held-out frame.

    A learner is evaluable only if they have at least one interaction in **both**
    frames: training history to build features from, and a held-out interaction to
    predict. Learners with no training history are excluded from personalised
    evaluation and counted separately (§12) rather than being scored as if
    personalisation had applied to them.
    """
    training_by_user = training.groupby(config.KEY_USER)[config.KEY_COURSE].apply(set)
    relevant: dict[str, set[int]] = {}
    history_length: dict[str, int] = {}

    for user, group in held_out.groupby(config.KEY_USER)[config.KEY_COURSE]:
        if user not in training_by_user.index:
            continue
        seen = context.seen.get(user, set())
        positions = {
            context.course_index[c]
            for c in group
            if c in context.course_index and context.course_index[c] not in seen
        }
        if not positions:
            continue
        relevant[user] = positions
        history_length[user] = len(seen)

    return EvaluationSet(relevant=relevant, protocol=protocol, history_length=history_length)


@dataclass
class EvaluationResult:
    """Metrics for one method: overall, per K, and per tier."""

    method: str
    protocol: str
    overall: dict[int, RankingMetrics]
    by_tier: dict[str, dict[int, RankingMetrics]]
    n_users_scored: int
    n_users_no_candidates: int

    def to_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "protocol": self.protocol,
            "n_users_scored": self.n_users_scored,
            "n_users_no_candidates": self.n_users_no_candidates,
            "overall": {str(k): m.to_dict() for k, m in self.overall.items()},
            "by_tier": {
                tier: {str(k): m.to_dict() for k, m in per_k.items()}
                for tier, per_k in self.by_tier.items()
            },
        }

    def headline(self, k: int = 10) -> dict[str, float]:
        m = self.overall[k]
        return {
            "ndcg": m.ndcg,
            "hit_rate": m.hit_rate,
            "precision": m.precision,
            "precision_ceiling": m.precision_ceiling,
            "recall": m.recall,
            "mrr": m.mrr,
            "coverage": m.coverage,
            "gini": m.gini,
        }


def per_user_ndcg(
    recommender, context: FitContext, evaluation_set: EvaluationSet, k: int = 10
) -> dict[str, float]:
    """NDCG@k for each evaluable learner individually.

    Needed for the **paired** comparison against the random baseline. Comparing
    two aggregate means says nothing about whether a gap is larger than sampling
    noise; pairing by learner removes the between-learner variance that dominates
    here, where one learner may have five held-out courses and another one.
    """
    from edupro.evaluation.metrics import ndcg_at_k

    scores: dict[str, float] = {}
    for user, relevant in evaluation_set.relevant.items():
        candidates = context.candidates_for(user)
        if len(candidates) == 0:
            continue
        ranked = recommender.score(user, candidates).ranked()
        scores[user] = ndcg_at_k(ranked, relevant, k)
    return scores


def paired_bootstrap(
    method_scores: dict[str, float],
    baseline_scores: dict[str, float],
    n_resamples: int = 2000,
    seed: int = config.RANDOM_SEED,
) -> dict[str, float | bool]:
    """Paired bootstrap of the per-learner NDCG difference against a baseline.

    Returns the mean difference and a 95% percentile interval. **If the interval
    contains zero, the method has not been shown to beat the baseline** — which,
    on a dataset where course choice is indistinguishable from chance (Phase 2), is
    the outcome to expect and the one that must be reportable.
    """
    shared = sorted(set(method_scores) & set(baseline_scores))
    if not shared:
        return {"n_users": 0, "mean_difference": float("nan"), "significant": False}

    differences = np.array([method_scores[u] - baseline_scores[u] for u in shared])
    rng = np.random.default_rng(seed)
    means = np.array([
        differences[rng.integers(0, len(differences), len(differences))].mean()
        for _ in range(n_resamples)
    ])
    low, high = np.percentile(means, [2.5, 97.5])
    return {
        "n_users": len(shared),
        "mean_difference": round(float(differences.mean()), 6),
        "ci_95_low": round(float(low), 6),
        "ci_95_high": round(float(high), 6),
        "significant": bool(low > 0 or high < 0),
        "direction": "better" if differences.mean() > 0 else "worse",
    }


def evaluate(
    recommender,
    context: FitContext,
    evaluation_set: EvaluationSet,
    ks: tuple[int, ...] = DEFAULT_KS,
) -> EvaluationResult:
    """Score every evaluable learner and aggregate, overall and by tier."""
    overall = {k: MetricAccumulator(k=k, n_catalogue=context.n_items) for k in ks}
    by_tier: dict[str, dict[int, MetricAccumulator]] = {}
    n_scored = 0
    n_no_candidates = 0

    for user, relevant in evaluation_set.relevant.items():
        candidates = context.candidates_for(user)
        if len(candidates) == 0:
            n_no_candidates += 1
            continue
        ranked = recommender.score(user, candidates).ranked()
        tier = evaluation_set.tier_of_user(user)
        if tier not in by_tier:
            by_tier[tier] = {k: MetricAccumulator(k=k, n_catalogue=context.n_items) for k in ks}
        for k in ks:
            overall[k].add(ranked, relevant)
            by_tier[tier][k].add(ranked, relevant)
        n_scored += 1

    return EvaluationResult(
        method=getattr(recommender, "name", type(recommender).__name__),
        protocol=evaluation_set.protocol,
        overall={k: acc.finalise() for k, acc in overall.items()},
        by_tier={
            tier: {k: acc.finalise() for k, acc in per_k.items()}
            for tier, per_k in by_tier.items()
        },
        n_users_scored=n_scored,
        n_users_no_candidates=n_no_candidates,
    )


# ---------------------------------------------------------------------------
# Leakage verification
# ---------------------------------------------------------------------------
def verify_leakage_controls(
    context: FitContext,
    training: pd.DataFrame,
    held_out: pd.DataFrame,
    evaluation_set: EvaluationSet,
    split_date: pd.Timestamp | None = None,
) -> dict[str, object]:
    """Check the six pre-registered leakage controls and return the evidence.

    Run as part of the experiment, not as a separate review step: leakage produces
    plausible-looking numbers, so it cannot be caught by inspection.
    """
    checks: dict[str, object] = {}

    # L1 - training frame contains no held-out interaction.
    held_out_ids = set(held_out[config.KEY_TRANSACTION])
    training_ids = set(training[config.KEY_TRANSACTION])
    checks["L1_no_heldout_rows_in_training"] = {
        "overlap": len(held_out_ids & training_ids),
        "passed": not (held_out_ids & training_ids),
    }

    # L1b - under Protocol A, nothing in training happens at or after the cut.
    if split_date is not None:
        latest = training[config.COL_TRANSACTION_DATE].max()
        checks["L1b_training_strictly_before_cut"] = {
            "latest_training_date": str(latest.date()),
            "cut": str(split_date.date()),
            "passed": bool(latest < split_date),
        }

    # L2 - the already-enrolled exclusion uses training-window history only.
    training_seen = (
        training.groupby(config.KEY_USER)[config.KEY_COURSE]
        .apply(lambda s: {context.course_index[c] for c in s if c in context.course_index})
    )
    mismatches = sum(
        1 for user, positions in training_seen.items()
        if context.seen.get(user, set()) != positions
    )
    checks["L2_exclusion_from_training_history_only"] = {
        "mismatched_users": mismatches,
        "passed": mismatches == 0,
    }

    # L3 - tier assignment uses training-window history only.
    tier_mismatches = sum(
        1
        for user, length in evaluation_set.history_length.items()
        if length != len(context.seen.get(user, set()))
    )
    checks["L3_tier_from_training_history_only"] = {
        "mismatched_users": tier_mismatches,
        "passed": tier_mismatches == 0,
    }

    # L5 - popularity counts sum to the training interaction count.
    checks["L5_popularity_from_training_only"] = {
        "training_interactions": int(len(context.interactions)),
        "equals_training_frame": bool(len(context.interactions) == len(training)),
        "passed": bool(len(context.interactions) == len(training)),
    }

    # L6 - every held-out item is present in the candidate pool it must be found in.
    missing = 0
    for user, relevant in evaluation_set.relevant.items():
        candidates = set(context.candidates_for(user).tolist())
        if not relevant.issubset(candidates):
            missing += 1
    checks["L6_heldout_items_in_candidate_pool"] = {
        "users_with_missing_targets": missing,
        "passed": missing == 0,
    }

    checks["all_passed"] = all(
        value["passed"] for value in checks.values() if isinstance(value, dict)
    )
    return checks
