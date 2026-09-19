"""Clustering algorithms and the cluster-count sweep.

K-Means is the primary method, as the official brief mandates. Hierarchical
clustering provides validation — with the caveat, stated wherever the comparison
is reported, that **Ward minimises within-cluster variance, the same objective
family K-Means optimises**, so Ward-K-Means agreement is partly a shared inductive
bias rather than independent confirmation. Average linkage is run alongside
precisely because it optimises something different (`segmentation_research.md` §9).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.metrics import adjusted_rand_score
from sklearn.mixture import GaussianMixture

from edupro import config
from edupro.segmentation.metrics import (
    cluster_sizes,
    intra_cluster_similarity,
    internal_metrics,
    per_cluster_silhouette,
)

#: Search range for k. The upper bound is set by the deliverable, not by
#: statistics: the dashboard must present segment comparisons a stakeholder can
#: hold in mind, and past roughly eight segments interpretability collapses
#: regardless of what any index says (`segmentation_research.md` §6.2).
DEFAULT_K_RANGE: tuple[int, ...] = tuple(range(2, 11))


@dataclass
class KMeansSweepRow:
    k: int
    inertia: float
    silhouette: float
    calinski_harabasz: float
    davies_bouldin: float
    sizes: dict[int, int]
    min_cluster_share: float
    per_cluster_silhouette: dict[int, float]
    intra_cluster_similarity: float
    seed_stability_ari: float

    def to_dict(self) -> dict[str, object]:
        return {
            "k": self.k,
            "inertia": round(self.inertia, 4),
            "silhouette": round(self.silhouette, 6),
            "calinski_harabasz": round(self.calinski_harabasz, 4),
            "davies_bouldin": round(self.davies_bouldin, 6),
            "sizes": self.sizes,
            "min_cluster_share": round(self.min_cluster_share, 6),
            "per_cluster_silhouette": {k: round(v, 6) for k, v in self.per_cluster_silhouette.items()},
            "intra_cluster_similarity": round(self.intra_cluster_similarity, 6),
            "seed_stability_ari": round(self.seed_stability_ari, 6),
        }


@dataclass
class SweepResult:
    representation: str
    rows: list[KMeansSweepRow] = field(default_factory=list)

    def to_records(self) -> list[dict[str, object]]:
        return [row.to_dict() for row in self.rows]

    def best_by_silhouette(self) -> KMeansSweepRow:
        return max(self.rows, key=lambda r: r.silhouette)


def fit_kmeans(matrix: np.ndarray, k: int, seed: int = config.RANDOM_SEED) -> KMeans:
    """K-Means with k-means++ seeding and multiple restarts [R09]."""
    return KMeans(n_clusters=k, n_init=10, random_state=seed).fit(matrix)


def seed_stability(matrix: np.ndarray, k: int, seeds: list[int]) -> float:
    """Mean pairwise Adjusted Rand Index across restarts with different seeds.

    A baseline hygiene check: it detects initialisation artefacts only. A stable
    but meaningless partition passes, which is why bootstrap Jaccard stability
    (`edupro.segmentation.stability`) is also run.
    """
    labellings = [fit_kmeans(matrix, k, seed=s).labels_ for s in seeds]
    scores = [
        adjusted_rand_score(labellings[i], labellings[j])
        for i in range(len(labellings))
        for j in range(i + 1, len(labellings))
    ]
    return float(np.mean(scores)) if scores else 1.0


def kmeans_sweep(
    matrix: np.ndarray,
    behavioural_positions: list[int],
    k_range: tuple[int, ...] = DEFAULT_K_RANGE,
    representation: str = "",
    seeds: tuple[int, ...] = (42, 7, 123, 2024, 31337),
) -> SweepResult:
    """Fit K-Means across the range and score every k on every criterion.

    Deliberately reports *all* k, including the ones that lose, so the selection
    can be read against the alternatives rather than asserted (CLAUDE.md §6).
    """
    result = SweepResult(representation=representation)
    n = len(matrix)
    for k in k_range:
        model = fit_kmeans(matrix, k)
        labels = model.labels_
        sizes = cluster_sizes(labels)
        internal = internal_metrics(matrix, labels)
        similarity = intra_cluster_similarity(matrix, labels, behavioural_positions)
        result.rows.append(
            KMeansSweepRow(
                k=k,
                inertia=float(model.inertia_),
                silhouette=internal["silhouette"],
                calinski_harabasz=internal["calinski_harabasz"],
                davies_bouldin=internal["davies_bouldin"],
                sizes=sizes,
                min_cluster_share=min(sizes.values()) / n,
                per_cluster_silhouette=per_cluster_silhouette(matrix, labels),
                intra_cluster_similarity=float(similarity["weighted_mean"]),
                seed_stability_ari=seed_stability(matrix, k, list(seeds)),
            )
        )
    return result


def fit_hierarchical(
    matrix: np.ndarray, k: int, method: str = "ward"
) -> np.ndarray:
    """Agglomerative clustering, returning 0-based labels.

    ``method`` is a scipy linkage method: ``ward`` (the brief's validation method)
    or ``average`` (the genuinely independent check).
    """
    if method == "ward":
        model = AgglomerativeClustering(n_clusters=k, linkage="ward").fit(matrix)
        return model.labels_
    tree = linkage(matrix, method=method)
    return fcluster(tree, t=k, criterion="maxclust") - 1


def fit_gmm(matrix: np.ndarray, k: int, seed: int = config.RANDOM_SEED) -> GaussianMixture:
    return GaussianMixture(n_components=k, random_state=seed, n_init=3).fit(matrix)


def gmm_selection(
    matrix: np.ndarray, k_range: tuple[int, ...] = DEFAULT_K_RANGE, seed: int = config.RANDOM_SEED
) -> list[dict[str, float]]:
    """BIC/AIC over k, as an independent k-criterion from a different model family."""
    out = []
    for k in k_range:
        model = fit_gmm(matrix, k, seed=seed)
        out.append({
            "k": k,
            "bic": round(float(model.bic(matrix)), 4),
            "aic": round(float(model.aic(matrix)), 4),
        })
    return out


def compare_partitions(a: np.ndarray, b: np.ndarray) -> float:
    """Adjusted Rand Index between two labellings."""
    return float(adjusted_rand_score(a, b))
