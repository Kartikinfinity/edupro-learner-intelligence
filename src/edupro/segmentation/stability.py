"""Cluster stability assessment.

Three complementary checks, because each catches a different failure:

**Seed stability** (in ``clustering.py``) — detects initialisation artefacts only.
A stable but meaningless partition passes.

**Bootstrap per-cluster Jaccard** [R03] — the most valuable of the three for this
project. It scores *each cluster separately* via the bootstrap distribution of the
Jaccard coefficient, so a partition containing three solid clusters and two
artefacts is diagnosed as such rather than receiving one averaged verdict. Since
the deliverable is segments a stakeholder will act on, a per-segment reliability
figure is what prevents recommending a strategy for a segment that dissolves under
resampling.

**Subsample consensus** [R04] — assesses whether structure is present at all, by a
different route from the gap statistic. Stability-based selection is a heuristic
with documented failure modes [R05], so it is reported as corroboration, never as
the decisive criterion.

Interpretation threshold: Hennig's conventional reading treats clusters with a
bootstrap Jaccard **below 0.6 as unstable** and **above 0.75 as reliable**. These
are conventions, not theory, and are labelled as such wherever reported.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import adjusted_rand_score

from edupro import config
from edupro.segmentation.clustering import fit_kmeans

JACCARD_UNSTABLE = 0.60
JACCARD_RELIABLE = 0.75


@dataclass(frozen=True)
class StabilityResult:
    k: int
    n_bootstrap: int
    per_cluster_jaccard: dict[int, float]
    mean_jaccard: float
    n_unstable: int
    n_reliable: int
    subsample_ari_mean: float
    subsample_ari_std: float

    def to_dict(self) -> dict[str, object]:
        return {
            "k": self.k,
            "n_bootstrap": self.n_bootstrap,
            "per_cluster_jaccard": {k: round(v, 4) for k, v in self.per_cluster_jaccard.items()},
            "mean_jaccard": round(self.mean_jaccard, 4),
            "n_unstable_below_0.60": self.n_unstable,
            "n_reliable_above_0.75": self.n_reliable,
            "subsample_ari_mean": round(self.subsample_ari_mean, 4),
            "subsample_ari_std": round(self.subsample_ari_std, 4),
            "all_clusters_reliable": self.n_unstable == 0,
        }


def _jaccard(a: set[int], b: set[int]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def bootstrap_jaccard(
    matrix: np.ndarray,
    k: int,
    n_bootstrap: int = 100,
    seed: int = config.RANDOM_SEED,
) -> dict[int, float]:
    """Per-cluster bootstrap Jaccard stability [R03].

    For each resample, the clustering is refitted and every original cluster is
    matched to its **most similar** cluster in the resample; the Jaccard value of
    that best match is recorded. A cluster that reliably reappears scores high.

    Matching is by maximum Jaccard rather than by label, because cluster labels
    are arbitrary and change between fits.
    """
    rng = np.random.default_rng(seed)
    n = len(matrix)
    reference = fit_kmeans(matrix, k).labels_
    reference_sets = {
        int(c): set(np.flatnonzero(reference == c).tolist()) for c in np.unique(reference)
    }
    scores: dict[int, list[float]] = {c: [] for c in reference_sets}

    for _ in range(n_bootstrap):
        sample = rng.choice(n, size=n, replace=True)
        unique_sample = np.unique(sample)
        if len(unique_sample) <= k:
            continue
        resampled = fit_kmeans(matrix[unique_sample], k, seed=int(rng.integers(0, 2**31 - 1)))
        # Map resampled cluster membership back to original row indices.
        resampled_sets = [
            set(unique_sample[np.flatnonzero(resampled.labels_ == c)].tolist())
            for c in np.unique(resampled.labels_)
        ]
        available = set(unique_sample.tolist())
        for cluster, members in reference_sets.items():
            visible = members & available
            if not visible:
                continue
            scores[cluster].append(max(_jaccard(visible, other) for other in resampled_sets))

    return {c: float(np.mean(v)) if v else float("nan") for c, v in scores.items()}


def subsample_consensus(
    matrix: np.ndarray,
    k: int,
    n_pairs: int = 30,
    fraction: float = 0.8,
    seed: int = config.RANDOM_SEED,
) -> tuple[float, float]:
    """Ben-Hur-style consensus [R04]: ARI between clusterings of overlapping subsamples.

    Two subsamples are drawn per replicate and each is clustered; agreement is
    measured on the points they share. High agreement indicates the structure does
    not depend on which 80% of the data is seen.
    """
    rng = np.random.default_rng(seed)
    n = len(matrix)
    size = int(n * fraction)
    scores = []
    for _ in range(n_pairs):
        first = rng.choice(n, size=size, replace=False)
        second = rng.choice(n, size=size, replace=False)
        shared = np.intersect1d(first, second)
        if len(shared) < k * 2:
            continue
        labels_first = fit_kmeans(matrix[first], k).labels_
        labels_second = fit_kmeans(matrix[second], k).labels_
        first_map = {row: label for row, label in zip(first, labels_first)}
        second_map = {row: label for row, label in zip(second, labels_second)}
        scores.append(
            adjusted_rand_score(
                [first_map[r] for r in shared], [second_map[r] for r in shared]
            )
        )
    return (float(np.mean(scores)), float(np.std(scores))) if scores else (float("nan"), float("nan"))


def assess_stability(
    matrix: np.ndarray,
    k: int,
    n_bootstrap: int = 100,
    n_subsample_pairs: int = 30,
    seed: int = config.RANDOM_SEED,
) -> StabilityResult:
    """Run both stability assessments and summarise."""
    jaccard = bootstrap_jaccard(matrix, k, n_bootstrap=n_bootstrap, seed=seed)
    values = [v for v in jaccard.values() if not np.isnan(v)]
    ari_mean, ari_std = subsample_consensus(matrix, k, n_pairs=n_subsample_pairs, seed=seed)
    return StabilityResult(
        k=k,
        n_bootstrap=n_bootstrap,
        per_cluster_jaccard=jaccard,
        mean_jaccard=float(np.mean(values)) if values else float("nan"),
        n_unstable=sum(1 for v in values if v < JACCARD_UNSTABLE),
        n_reliable=sum(1 for v in values if v >= JACCARD_RELIABLE),
        subsample_ari_mean=ari_mean,
        subsample_ari_std=ari_std,
    )
