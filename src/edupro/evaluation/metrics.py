"""Top-K recommendation metrics.

Mandated by the official brief: **Recommendation Precision**. Added where
scientifically appropriate (CLAUDE.md §3) and pre-registered in
``research/recommendation_evaluation_plan.md`` §3: Recall@K, Hit Rate@K, NDCG@K,
MRR, catalogue coverage and a popularity-concentration (Gini) diagnostic.

Two reporting constraints are baked in rather than left to discipline:

**Precision@K is ceiling-limited here.** With a 60-course catalogue and a small
number of held-out courses per learner, Precision@10 cannot exceed
``n_relevant / 10``. :func:`precision_ceiling` computes that bound so every
reported precision can be shown against what was achievable. Reporting the bare
number would make a strong model look like a failure.

**NDCG@K is the primary accuracy metric** [R23]: it is rank-sensitive and not
ceiling-limited in the same way, which matters when Precision@10 tops out at 0.10
for a single-holdout learner.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class RankingMetrics:
    """Metrics for one method at one K, aggregated over an evaluation set."""

    k: int
    n_users: int
    precision: float
    precision_ceiling: float
    recall: float
    hit_rate: float
    ndcg: float
    mrr: float
    coverage: float
    gini: float
    n_items_recommended: int

    def to_dict(self) -> dict[str, float | int]:
        return {
            "k": self.k,
            "n_users": self.n_users,
            "precision": round(self.precision, 6),
            "precision_ceiling": round(self.precision_ceiling, 6),
            "precision_vs_ceiling": (
                round(self.precision / self.precision_ceiling, 6)
                if self.precision_ceiling > 0 else float("nan")
            ),
            "recall": round(self.recall, 6),
            "hit_rate": round(self.hit_rate, 6),
            "ndcg": round(self.ndcg, 6),
            "mrr": round(self.mrr, 6),
            "coverage": round(self.coverage, 6),
            "gini": round(self.gini, 6),
            "n_items_recommended": self.n_items_recommended,
        }


def precision_at_k(ranked: np.ndarray, relevant: set[int], k: int) -> float:
    top = ranked[:k]
    return sum(1 for item in top if item in relevant) / k


def precision_ceiling(n_relevant: int, k: int) -> float:
    """The largest Precision@K achievable given how many items are relevant.

    With one held-out course, Precision@10 cannot exceed 0.10 no matter how good
    the ranker is. Reporting precision without this bound is misleading on a
    catalogue this small.
    """
    return min(n_relevant, k) / k


def recall_at_k(ranked: np.ndarray, relevant: set[int], k: int) -> float:
    if not relevant:
        return float("nan")
    top = ranked[:k]
    return sum(1 for item in top if item in relevant) / len(relevant)


def hit_rate_at_k(ranked: np.ndarray, relevant: set[int], k: int) -> float:
    return float(any(item in relevant for item in ranked[:k]))


def ndcg_at_k(ranked: np.ndarray, relevant: set[int], k: int) -> float:
    """Binary-relevance NDCG with logarithmic position discounting [R23]."""
    if not relevant:
        return float("nan")
    gains = np.array([1.0 if item in relevant else 0.0 for item in ranked[:k]])
    discounts = 1.0 / np.log2(np.arange(2, len(gains) + 2))
    dcg = float((gains * discounts).sum())
    ideal_hits = min(len(relevant), k)
    idcg = float((np.ones(ideal_hits) / np.log2(np.arange(2, ideal_hits + 2))).sum())
    return dcg / idcg if idcg > 0 else 0.0


def reciprocal_rank(ranked: np.ndarray, relevant: set[int]) -> float:
    for position, item in enumerate(ranked, start=1):
        if item in relevant:
            return 1.0 / position
    return 0.0


def gini(values: np.ndarray) -> float:
    """Concentration of recommendation exposure across the catalogue.

    0 = every course recommended equally often; 1 = all exposure on one course.
    Reported alongside coverage as the popularity-bias diagnostic [R29].
    """
    values = np.sort(np.asarray(values, dtype=float))
    n = len(values)
    if n == 0 or values.sum() == 0:
        return 0.0
    index = np.arange(1, n + 1)
    return float((2 * index - n - 1).dot(values) / (n * values.sum()))


@dataclass
class MetricAccumulator:
    """Accumulates per-user results for one method at one K."""

    k: int
    n_catalogue: int
    precision: list[float] = field(default_factory=list)
    ceiling: list[float] = field(default_factory=list)
    recall: list[float] = field(default_factory=list)
    hit: list[float] = field(default_factory=list)
    ndcg: list[float] = field(default_factory=list)
    mrr: list[float] = field(default_factory=list)
    exposure: np.ndarray | None = None

    def add(self, ranked: np.ndarray, relevant: set[int]) -> None:
        if self.exposure is None:
            self.exposure = np.zeros(self.n_catalogue, dtype=float)
        top = ranked[: self.k]
        self.exposure[top] += 1
        self.precision.append(precision_at_k(ranked, relevant, self.k))
        self.ceiling.append(precision_ceiling(len(relevant), self.k))
        self.recall.append(recall_at_k(ranked, relevant, self.k))
        self.hit.append(hit_rate_at_k(ranked, relevant, self.k))
        self.ndcg.append(ndcg_at_k(ranked, relevant, self.k))
        self.mrr.append(reciprocal_rank(ranked, relevant))

    def finalise(self) -> RankingMetrics:
        exposure = self.exposure if self.exposure is not None else np.zeros(self.n_catalogue)
        recommended = int((exposure > 0).sum())
        return RankingMetrics(
            k=self.k,
            n_users=len(self.precision),
            precision=float(np.mean(self.precision)) if self.precision else float("nan"),
            precision_ceiling=float(np.mean(self.ceiling)) if self.ceiling else float("nan"),
            recall=float(np.nanmean(self.recall)) if self.recall else float("nan"),
            hit_rate=float(np.mean(self.hit)) if self.hit else float("nan"),
            ndcg=float(np.nanmean(self.ndcg)) if self.ndcg else float("nan"),
            mrr=float(np.mean(self.mrr)) if self.mrr else float("nan"),
            coverage=recommended / self.n_catalogue,
            gini=gini(exposure),
            n_items_recommended=recommended,
        )


def engagement_lift_proxy(method_hit_rate: float, baseline_hit_rate: float) -> float:
    """**Engagement Lift (Proxy)** — the brief's mandated impact metric.

    Defined in Phase 1 (decision log D-014) *before any result was seen*: the ratio
    of this method's Hit Rate@10 to the global-popularity baseline's, on the same
    evaluable population and split.

    **This is not a causal estimate and must never be reported as one.** The data
    is observational: there are no impressions, no control group and no
    counterfactual. The value measures how much better this system agrees with
    learners' actual next enrollments than a non-personalised popularity list does
    — an offline agreement ratio, nothing more (CLAUDE.md §6).
    """
    if baseline_hit_rate <= 0:
        return float("nan")
    return method_hit_rate / baseline_hit_rate
