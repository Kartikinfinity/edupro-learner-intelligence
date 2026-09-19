"""Recommender interface and the fitting context every method shares.

Design constraint decided in Phase 1 (decision log D-015), before any recommender
was written: **scoring returns per-component contributions, not just a scalar.**

CLAUDE.md §16 requires explanations that correspond to the signals the recommender
actually used. [R31] distinguishes model-intrinsic explanation, where the model's
own mechanism is interpretable, from post-hoc explanation, which can assert
reasons the model never used. Only the former can be faithful. If a scorer returns
a bare total, faithful explanation becomes impossible after the fact — so the
interface carries the decomposition from the start rather than being retrofitted.

Every recommender is fitted from a :class:`FitContext` built **only** from the
training window, so no method can see the future (leakage controls L1, L4, L5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import pandas as pd

from edupro import config


@dataclass(frozen=True)
class FitContext:
    """Everything a recommender may learn from, scoped to the training window.

    Constructed once per evaluation run by
    :func:`edupro.recommendation.build_fit_context`. A recommender that reads
    anything outside this object is reading the future.
    """

    #: Interactions available for training. Never contains held-out rows.
    interactions: pd.DataFrame
    #: Course catalogue (static attributes; not time-dependent).
    courses: pd.DataFrame
    #: Learner features built from ``interactions`` alone.
    features: pd.DataFrame
    #: Cluster assignment per learner, from the Phase 3A segmentation.
    clusters: pd.Series
    #: Ordered course IDs; every recommender works in these index positions.
    course_ids: list[str]
    #: Course ID -> index position.
    course_index: dict[str, int] = field(default_factory=dict)
    #: Learner -> set of course positions already enrolled in the training window.
    seen: dict[str, set[int]] = field(default_factory=dict)

    @property
    def n_items(self) -> int:
        return len(self.course_ids)

    def candidates_for(self, user: str) -> np.ndarray:
        """Unseen course positions, in catalogue order.

        Excluding already-enrolled courses is required by CLAUDE.md §23. The
        exclusion uses **training-window** history only (leakage control L2): using
        full history would leak the existence of the held-out interaction.
        """
        seen = self.seen.get(user, set())
        return np.array([i for i in range(self.n_items) if i not in seen], dtype=int)


@dataclass
class Scores:
    """A scored candidate set, with the decomposition that makes it explainable."""

    candidates: np.ndarray
    total: np.ndarray
    #: Per-component contributions, already weighted. Keys are component names.
    #: Single-signal recommenders report one component; the hybrid reports all.
    components: dict[str, np.ndarray] = field(default_factory=dict)

    def ranked(self, k: int | None = None) -> np.ndarray:
        """Candidate positions sorted by descending score.

        Ties are broken by candidate index so the ranking is deterministic — an
        arbitrary tie order would make results irreproducible, and on a catalogue
        this flat ties are common.
        """
        order = np.lexsort((self.candidates, -self.total))
        ranked = self.candidates[order]
        return ranked if k is None else ranked[:k]

    def contribution_at(self, position: int) -> dict[str, float]:
        """Per-component contribution for one candidate — the explanation's input."""
        index = int(np.flatnonzero(self.candidates == position)[0])
        return {name: float(values[index]) for name, values in self.components.items()}


class Recommender(Protocol):
    """A scoring function over unseen courses."""

    name: str

    def fit(self, context: FitContext) -> "Recommender": ...

    def score(self, user: str, candidates: np.ndarray) -> Scores: ...


class BaseRecommender:
    """Shared plumbing: holds the context and exposes a uniform recommend()."""

    name: str = "base"
    #: Human-readable component name used in explanations.
    component: str = "score"

    def __init__(self) -> None:
        self.context: FitContext | None = None

    def fit(self, context: FitContext) -> "BaseRecommender":
        self.context = context
        self._fit(context)
        return self

    def _fit(self, context: FitContext) -> None:  # pragma: no cover - overridden
        return None

    def _raw_scores(self, user: str, candidates: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def score(self, user: str, candidates: np.ndarray) -> Scores:
        values = np.asarray(self._raw_scores(user, candidates), dtype=float)
        return Scores(candidates=candidates, total=values, components={self.component: values})

    def recommend(self, user: str, k: int = 10) -> np.ndarray:
        if self.context is None:
            raise RuntimeError(f"{self.name} has not been fitted.")
        candidates = self.context.candidates_for(user)
        if len(candidates) == 0:
            return np.array([], dtype=int)
        return self.score(user, candidates).ranked(k)


def minmax(values: np.ndarray) -> np.ndarray:
    """Scale to [0, 1]; a constant vector becomes all zeros.

    Components are min-max scaled before weighting so that a weight means the same
    thing across signals whose natural ranges differ (counts, cosines, ratings).
    Mapping a constant vector to zeros rather than to 0.5 is deliberate: a signal
    that cannot discriminate should contribute nothing, not a constant offset.
    """
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return values
    low, high = float(values.min()), float(values.max())
    if high - low < 1e-12:
        return np.zeros_like(values)
    return (values - low) / (high - low)


def build_fit_context(
    interactions: pd.DataFrame,
    courses: pd.DataFrame,
    features: pd.DataFrame,
    clusters: pd.Series,
) -> FitContext:
    """Assemble a :class:`FitContext` from a training-window interaction frame."""
    course_ids = courses[config.KEY_COURSE].tolist()
    course_index = {course: i for i, course in enumerate(course_ids)}
    seen: dict[str, set[int]] = {}
    for user, group in interactions.groupby(config.KEY_USER)[config.KEY_COURSE]:
        seen[user] = {course_index[c] for c in group if c in course_index}
    return FitContext(
        interactions=interactions,
        courses=courses,
        features=features,
        clusters=clusters,
        course_ids=course_ids,
        course_index=course_index,
        seen=seen,
    )
