"""Cluster-quality metrics, including the two the official brief mandates.

Mandated
    **Silhouette Score** — cluster quality [R01]. Reported globally and per cluster:
    the per-cluster values are where the actionable information sits, since one
    loose segment among four tight ones is a finding an average conceals.

    **Intra-cluster similarity** — behavioural consistency. The brief names the
    metric but gives no formula, so one is defined here and justified in
    `research/segmentation_research.md` §5: **mean pairwise cosine similarity on
    the behavioural and engagement blocks only**, demographics excluded. Cosine
    compares profile *shape* independently of magnitude, so it does not simply
    re-measure the activity-volume axis that dominates this dataset.

Added beyond the brief
    **Gap statistic** [R02] — the only criterion here that can return *k = 1*, i.e.
    "there is no cluster structure". Elbow, silhouette, Calinski-Harabasz and
    Davies-Bouldin all assume structure exists and merely locate the best k. Given
    the Phase 2 finding that course choice is indistinguishable from chance, a
    project unable to report "no real structure" would be unable to report the
    truth (decision log D-017).

    **Eta-squared feature dominance** — the measurement CLAUDE.md §10 requires to
    show that demographics (or any other block) do not dominate the segmentation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_samples,
    silhouette_score,
)
from sklearn.metrics.pairwise import cosine_similarity

from edupro import config


def cluster_sizes(labels: np.ndarray) -> dict[int, int]:
    values, counts = np.unique(labels, return_counts=True)
    return {int(v): int(c) for v, c in zip(values, counts)}


def internal_metrics(matrix: np.ndarray, labels: np.ndarray) -> dict[str, float]:
    """Silhouette, Calinski-Harabasz and Davies-Bouldin.

    CH and DB share silhouette's bias toward convex, well-separated clusters, so
    they are corroboration rather than independent confirmation [R06]; they are
    reported with that caveat rather than presented as three separate votes.
    """
    if len(np.unique(labels)) < 2:
        return {"silhouette": float("nan"), "calinski_harabasz": float("nan"),
                "davies_bouldin": float("nan")}
    return {
        "silhouette": float(silhouette_score(matrix, labels)),
        "calinski_harabasz": float(calinski_harabasz_score(matrix, labels)),
        "davies_bouldin": float(davies_bouldin_score(matrix, labels)),
    }


def per_cluster_silhouette(matrix: np.ndarray, labels: np.ndarray) -> dict[int, float]:
    if len(np.unique(labels)) < 2:
        return {}
    samples = silhouette_samples(matrix, labels)
    return {int(c): float(samples[labels == c].mean()) for c in np.unique(labels)}


def intra_cluster_similarity(
    matrix: np.ndarray,
    labels: np.ndarray,
    behavioural_positions: list[int],
    max_sample: int = 400,
    seed: int = config.RANDOM_SEED,
) -> dict[str, float | dict[int, float]]:
    """Mean pairwise cosine similarity within each cluster, behavioural columns only.

    Large clusters are subsampled to ``max_sample`` members for the pairwise
    computation; the subsample is seeded, so the value is reproducible.
    """
    if not behavioural_positions:
        return {"weighted_mean": float("nan"), "per_cluster": {}}

    rng = np.random.default_rng(seed)
    behavioural = matrix[:, behavioural_positions]
    per_cluster: dict[int, float] = {}
    weights: dict[int, int] = {}

    for cluster in np.unique(labels):
        members = np.flatnonzero(labels == cluster)
        weights[int(cluster)] = len(members)
        if len(members) < 2:
            per_cluster[int(cluster)] = float("nan")
            continue
        if len(members) > max_sample:
            members = rng.choice(members, size=max_sample, replace=False)
        similarity = cosine_similarity(behavioural[members])
        upper = similarity[np.triu_indices_from(similarity, k=1)]
        per_cluster[int(cluster)] = float(upper.mean())

    valid = {c: v for c, v in per_cluster.items() if not np.isnan(v)}
    total = sum(weights[c] for c in valid) or 1
    weighted = sum(v * weights[c] for c, v in valid.items()) / total
    return {"weighted_mean": float(weighted), "per_cluster": per_cluster}


def eta_squared(matrix: np.ndarray, labels: np.ndarray, columns: list[str]) -> dict[str, float]:
    """Proportion of each feature's variance explained by cluster membership.

    One-way ANOVA eta-squared: between-cluster sum of squares over total sum of
    squares. Directly interpretable as "how much of this feature's variation the
    segmentation accounts for".
    """
    out: dict[str, float] = {}
    for position, column in enumerate(columns):
        values = matrix[:, position]
        grand_mean = values.mean()
        total_ss = float(((values - grand_mean) ** 2).sum())
        if total_ss == 0:
            out[column] = 0.0
            continue
        between_ss = 0.0
        for cluster in np.unique(labels):
            members = values[labels == cluster]
            between_ss += len(members) * (members.mean() - grand_mean) ** 2
        out[column] = float(between_ss / total_ss)
    return out


def block_dominance(
    matrix: np.ndarray,
    labels: np.ndarray,
    columns: list[str],
    blocks: dict[str, list[str]],
) -> dict[str, object]:
    """Aggregate eta-squared to feature blocks and report each block's share.

    The ``demographic_share`` this returns is the number CLAUDE.md §10 asks for.
    Its pre-registered interpretation (`research/segmentation_research.md` §4):
    below 20% secondary · 20-40% material, needs justification · **above 40%
    dominant, Variant A rejected**.
    """
    per_feature = eta_squared(matrix, labels, columns)
    per_block: dict[str, float] = {}
    block_totals: dict[str, float] = {}
    for block, members in blocks.items():
        present = [m for m in members if m in per_feature]
        if not present:
            continue
        per_block[block] = float(np.mean([per_feature[m] for m in present]))
        block_totals[block] = float(np.sum([per_feature[m] for m in present]))

    total = sum(block_totals.values()) or 1.0
    shares = {block: value / total for block, value in block_totals.items()}
    return {
        "per_feature": dict(sorted(per_feature.items(), key=lambda kv: -kv[1])),
        "mean_per_block": per_block,
        "explained_share_per_block": shares,
        "demographic_share": float(shares.get("demographic", 0.0)),
        "top_feature": max(per_feature, key=per_feature.get) if per_feature else None,
    }


@dataclass(frozen=True)
class GapResult:
    k_values: list[int]
    gap: list[float]
    std_error: list[float]
    optimal_k: int
    indicates_no_structure: bool


def gap_statistic(
    matrix: np.ndarray,
    k_values: range | list[int],
    n_references: int = 50,
    seed: int = config.RANDOM_SEED,
) -> GapResult:
    """Tibshirani-Walther-Hastie gap statistic [R02].

    Compares observed within-cluster dispersion against the dispersion expected
    under a uniform reference distribution over the data's bounding box. The
    standard selection rule takes the smallest k with
    ``gap(k) >= gap(k+1) - s(k+1)``.

    **k = 1 is included in the search range on purpose.** If it wins, the data does
    not support segmentation — the one verdict no mandated criterion can deliver.
    """
    rng = np.random.default_rng(seed)
    k_values = list(k_values)
    minimum = matrix.min(axis=0)
    maximum = matrix.max(axis=0)

    def dispersion(data: np.ndarray, k: int) -> float:
        if k == 1:
            centre = data.mean(axis=0)
            return float(((data - centre) ** 2).sum())
        model = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(data)
        return float(model.inertia_)

    observed = np.array([np.log(dispersion(matrix, k) + 1e-12) for k in k_values])
    reference = np.zeros((n_references, len(k_values)))
    for b in range(n_references):
        sample = rng.uniform(minimum, maximum, size=matrix.shape)
        for i, k in enumerate(k_values):
            reference[b, i] = np.log(dispersion(sample, k) + 1e-12)

    gap = reference.mean(axis=0) - observed
    std_error = reference.std(axis=0) * np.sqrt(1.0 + 1.0 / n_references)

    optimal = k_values[-1]
    for i in range(len(k_values) - 1):
        if gap[i] >= gap[i + 1] - std_error[i + 1]:
            optimal = k_values[i]
            break

    return GapResult(
        k_values=k_values,
        gap=[float(g) for g in gap],
        std_error=[float(s) for s in std_error],
        optimal_k=int(optimal),
        indicates_no_structure=bool(optimal == 1),
    )
