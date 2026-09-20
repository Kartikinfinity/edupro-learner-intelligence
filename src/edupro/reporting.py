"""Read measured results out of the experiment artifacts, as tidy frames.

Every metric the dashboard displays comes through this module, and every value it
returns was written by an experiment script that actually ran. Nothing here
computes a metric and nothing here contains a typed-in number — if a figure is not
in an artifact, this module cannot produce it, which is the point (CLAUDE.md §6).

The dashboard is therefore incapable of showing a fabricated metric: the only
alternative to a real artifact value is a missing-artifact empty state.

Provenance is carried alongside the numbers rather than dropped, so a page can
state which window a figure came from and how many learners it was measured on.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from edupro import config

logger = logging.getLogger(__name__)

SEGMENTATION_RESULTS: Path = config.ARTIFACTS_DIR / "segmentation" / "segmentation_results.json"
RECOMMENDATION_RESULTS: Path = (
    config.ARTIFACTS_DIR / "recommendation" / "recommendation_results.json"
)
ARCHITECTURE_RESULTS: Path = config.ARTIFACTS_DIR / "architecture" / "architecture_validation.json"
AUDIT_RESULTS: Path = config.ARTIFACTS_DIR / "phase2_audit.json"

#: The frozen selections, so a table can mark which row is deployed without the
#: page hard-coding an opinion about it.
DEPLOYED_METHOD: str = "cluster_popularity"
DEPLOYED_ARCHITECTURE: str = "C_tiered_with_selected_core"
REFERENCE_METHOD: str = "random"

#: Primary evaluation cut-off. Pre-registered in Phase 1; the artifacts report at
#: 5, 10 and 20, and every headline figure in `research/` uses 10.
PRIMARY_K: int = 10


class MissingArtifactError(FileNotFoundError):
    """Raised when a results artifact the dashboard needs has not been generated."""


def _describe(path: Path) -> str:
    """Project-relative path where possible, absolute otherwise.

    ``relative_to`` raises for a path outside the project, which would turn a
    helpful "artifact is missing" message into an unrelated ValueError — the error
    path failing is worse than the error it was reporting.
    """
    try:
        return str(path.relative_to(config.PROJECT_ROOT))
    except ValueError:
        return str(path)


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise MissingArtifactError(
            f"{_describe(path)} is missing. "
            "Run the experiment scripts in scripts/ to regenerate it."
        )
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def segmentation_results() -> dict[str, Any]:
    return _load(SEGMENTATION_RESULTS)


@lru_cache(maxsize=1)
def recommendation_results() -> dict[str, Any]:
    return _load(RECOMMENDATION_RESULTS)


@lru_cache(maxsize=1)
def architecture_results() -> dict[str, Any]:
    return _load(ARCHITECTURE_RESULTS)


@lru_cache(maxsize=1)
def audit_results() -> dict[str, Any]:
    return _load(AUDIT_RESULTS)


def artifacts_available() -> dict[str, bool]:
    """Which results artifacts are present — for a page's empty state."""
    return {
        "segmentation": SEGMENTATION_RESULTS.exists(),
        "recommendation": RECOMMENDATION_RESULTS.exists(),
        "architecture": ARCHITECTURE_RESULTS.exists(),
        "audit": AUDIT_RESULTS.exists(),
    }


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EvaluationProvenance:
    """Where a set of recommendation metrics came from."""

    protocol: str
    n_users: int
    n_held_out: int
    validation_cut: str
    test_cut: str
    seed: int

    def caption(self) -> str:
        return (
            f"Protocol A (global temporal split) · test window from {self.test_cut} · "
            f"{self.n_users:,} evaluable learners · {self.n_held_out:,} held-out "
            f"interactions · seed {self.seed}"
        )


def evaluation_provenance() -> EvaluationProvenance:
    results = recommendation_results()
    test_set = results["test_set"]
    provenance = results["provenance"]
    return EvaluationProvenance(
        protocol=test_set["protocol"],
        n_users=int(test_set["n_users"]),
        n_held_out=int(test_set["n_held_out_interactions"]),
        validation_cut=str(provenance["validation_cut"]),
        test_cut=str(provenance["test_cut"]),
        seed=int(provenance["seed"]),
    )


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------
def recommendation_comparison(k: int = PRIMARY_K) -> pd.DataFrame:
    """Every evaluated method on the test window, with significance against random.

    The random baseline is a row like any other, deliberately: on a 60-course
    catalogue a ranker that beats nothing still posts a Hit Rate near 0.35, so a
    table without the reference row would read as success.
    """
    results = recommendation_results()
    significance = results["significance_vs_random"]["per_method"]

    rows = []
    for method, payload in results["test"].items():
        metrics = payload["overall"][str(k)]
        comparison = significance.get(method, {}).get("vs_random", {})
        rows.append(
            {
                "method": method,
                "ndcg": metrics["ndcg"],
                "hit_rate": metrics["hit_rate"],
                "precision": metrics["precision"],
                "precision_ceiling": metrics["precision_ceiling"],
                "recall": metrics["recall"],
                "mrr": metrics["mrr"],
                "coverage": metrics["coverage"],
                "gini": metrics.get("gini"),
                "vs_random": comparison.get("mean_difference"),
                "ci_low": comparison.get("ci_95_low"),
                "ci_high": comparison.get("ci_95_high"),
                "significant": bool(comparison.get("significant", False)),
                "is_reference": method == REFERENCE_METHOD,
                "is_deployed": method == DEPLOYED_METHOD,
            }
        )
    return pd.DataFrame(rows).sort_values("ndcg", ascending=False).reset_index(drop=True)


def recommendation_headline(k: int = PRIMARY_K) -> dict[str, Any]:
    """The finding that governs how every quality figure must be presented."""
    results = recommendation_results()
    comparison = recommendation_comparison(k)
    reference = comparison[comparison["is_reference"]].iloc[0]
    deployed = comparison[comparison["is_deployed"]].iloc[0]
    return {
        "n_methods": int(len(comparison) - 1),
        "n_significant": int(
            results["significance_vs_random"]["n_methods_significantly_better_than_random"]
        ),
        "random_ndcg": float(reference["ndcg"]),
        "random_hit_rate": float(reference["hit_rate"]),
        "deployed_ndcg": float(deployed["ndcg"]),
        "deployed_hit_rate": float(deployed["hit_rate"]),
        "deployed_rank": int(comparison.index[comparison["is_deployed"]][0]) + 1,
        "random_rank": int(comparison.index[comparison["is_reference"]][0]) + 1,
        "interpretation": results["significance_vs_random"]["interpretation"],
    }


def per_tier_metrics(method: str = DEPLOYED_METHOD, k: int = PRIMARY_K) -> pd.DataFrame:
    """Test-window metrics split by history tier — where the design is justified."""
    payload = recommendation_results()["test"].get(method)
    if payload is None or "by_tier" not in payload:
        return pd.DataFrame()
    rows = []
    for tier, per_k in payload["by_tier"].items():
        metrics = per_k[str(k)]
        rows.append(
            {
                "tier": tier,
                "n_users": metrics["n_users"],
                "ndcg": metrics["ndcg"],
                "hit_rate": metrics["hit_rate"],
                "coverage": metrics["coverage"],
            }
        )
    order = {"insufficient": 0, "minimal": 1, "moderate": 2, "rich": 3}
    return (
        pd.DataFrame(rows)
        .assign(_order=lambda f: f["tier"].map(order))
        .sort_values("_order")
        .drop(columns="_order")
        .reset_index(drop=True)
    )


def coverage_accounting() -> dict[str, Any]:
    """How many learners are served, and by which route."""
    return recommendation_results()["EXP-009_coverage_accounting"]


def architecture_comparison(k: int = PRIMARY_K) -> pd.DataFrame:
    """The three assembled architectures measured in Phase 4, on validation."""
    results = architecture_results()
    rows = []
    for name, payload in results["architectures"].items():
        metrics = payload["overall"][str(k)]
        rows.append(
            {
                "architecture": name,
                "ndcg": metrics["ndcg"],
                "hit_rate": metrics["hit_rate"],
                "coverage": metrics["coverage"],
                "gini": metrics["gini"],
                "vs_random": payload["vs_random"]["mean_difference"],
                "significant": bool(payload["vs_random"]["significant"]),
                "is_deployed": name == DEPLOYED_ARCHITECTURE,
            }
        )
    return pd.DataFrame(rows)


def engagement_lift_proxy() -> dict[str, float]:
    """The official impact metric, returned **with random's own value beside it**.

    Returning them together is deliberate. The proxy is not a causal measurement
    (CLAUDE.md §6), and a lift of 1.08 only means something next to the 1.05 that
    random ranking scores on the same measure — so the two cannot be separated by
    a caller that only wanted the flattering one.
    """
    comparison = recommendation_results()["test"]
    return {
        "deployed": float(comparison[DEPLOYED_METHOD]["engagement_lift_proxy"]),
        "random": float(comparison[REFERENCE_METHOD]["engagement_lift_proxy"]),
    }


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------
def k_sweep() -> pd.DataFrame:
    """Cluster-count sweep: elbow, silhouette, CH, DB and the selection constraints."""
    rows = segmentation_results()["EXP-010_k_sweep"]
    frame = pd.DataFrame(
        [
            {
                "k": row["k"],
                "inertia": row["inertia"],
                "silhouette": row["silhouette"],
                "calinski_harabasz": row["calinski_harabasz"],
                "davies_bouldin": row["davies_bouldin"],
                "min_cluster_share": row["min_cluster_share"],
                "intra_cluster_similarity": row["intra_cluster_similarity"],
            }
            for row in rows
        ]
    )
    stability = segmentation_results().get("EXP-013_stability_by_k", {})
    frame["mean_bootstrap_jaccard"] = frame["k"].map(
        lambda k: stability.get(str(int(k)), {}).get("mean_jaccard")
    )
    frame["min_bootstrap_jaccard"] = frame["k"].map(
        lambda k: min(stability[str(int(k))]["per_cluster_jaccard"].values())
        if str(int(k)) in stability
        else None
    )
    frame["n_unstable_clusters"] = frame["k"].map(
        lambda k: stability.get(str(int(k)), {}).get("n_unstable_below_0.60")
    )
    return frame


def k_selection() -> dict[str, Any]:
    """The pre-registered selection rule and the candidates it accepted or rejected."""
    return segmentation_results()["k_selection"]


def segmentation_quality() -> dict[str, Any]:
    """Headline cluster-quality metrics for the frozen configuration."""
    selected = next(
        row for row in segmentation_results()["EXP-010_k_sweep"] if int(row["k"]) == 4
    )
    stability = segmentation_results()["EXP-013_stability"]
    return {
        "k": 4,
        "silhouette": selected["silhouette"],
        "calinski_harabasz": selected["calinski_harabasz"],
        "davies_bouldin": selected["davies_bouldin"],
        "intra_cluster_similarity": selected["intra_cluster_similarity"],
        "min_cluster_share": selected["min_cluster_share"],
        "mean_bootstrap_jaccard": stability["mean_jaccard"],
        "seed_stability_ari": selected["seed_stability_ari"],
        "per_cluster_silhouette": selected["per_cluster_silhouette"],
        # Surfaced so the dashboard can state how many clusters clear the
        # reliability threshold instead of asserting it in static text.
        "n_clusters_reliable": stability["n_reliable_above_0.75"],
        "n_bootstrap": stability["n_bootstrap"],
    }


#: Pre-registered constraint: a segment smaller than this cannot be acted on.
MIN_CLUSTER_SHARE: float = 0.05
#: Pre-registered constraint: a cluster below this Jaccard does not reappear
#: reliably under resampling.
MIN_BOOTSTRAP_JACCARD: float = 0.60


def representation_comparison() -> pd.DataFrame:
    """The ten representations compared in Phase 3A, each at its own best k.

    "Best k" applies the **pre-registered selection rule**, not the raw silhouette
    maximum: the highest-silhouette k for which every cluster holds at least 5% of
    learners, and — where per-k stability was measured, which is the deployed arm —
    every cluster also reaches bootstrap Jaccard 0.60.

    Reporting the unconstrained maximum instead would be misleading in a specific
    way. Every arm's silhouette rises as k rises, so an unconstrained table ranks
    arms by how far they were allowed to fragment rather than by how good their
    structure is; `B_proportion` would appear at k = 10, where half its clusters
    fail to reappear under resampling. This function reproduces the table in
    `research/ARCHITECTURE_FREEZE.md`.
    """
    results = segmentation_results()
    sweeps = results["sweeps"]
    stability = results.get("EXP-013_stability_by_k", {})

    def eligible(name: str, row: dict[str, Any]) -> bool:
        if row["min_cluster_share"] < MIN_CLUSTER_SHARE:
            return False
        if name != "B_proportion":
            # Per-k stability was only measured for the deployed arm, so the
            # constraint cannot be applied to the others without inventing data.
            return True
        entry = stability.get(str(int(row["k"])))
        if entry is None:
            return True
        return min(entry["per_cluster_jaccard"].values()) >= MIN_BOOTSTRAP_JACCARD

    rows = []
    for payload in results["EXP-011a_representations"]:
        name = payload["name"]
        sweep = sweeps.get(name, [])
        candidates = [row for row in sweep if eligible(name, row)]
        if not candidates:
            continue
        best = max(candidates, key=lambda row: row["silhouette"])
        rows.append(
            {
                "representation": name,
                "variant": payload.get("variant"),
                "best_k": best["k"],
                "silhouette": best["silhouette"],
                "intra_cluster_similarity": best["intra_cluster_similarity"],
                "min_cluster_share": best["min_cluster_share"],
                "n_features": payload.get("n_features"),
                "is_deployed": name == "B_proportion",
            }
        )
    return pd.DataFrame(rows).sort_values("silhouette", ascending=False).reset_index(drop=True)


def hierarchical_validation() -> dict[str, Any]:
    """The independent-algorithm check — reported including its negative result."""
    return segmentation_results()["EXP-012_hierarchical"]


def demographic_variant_comparison() -> dict[str, Any]:
    """Variant A (with demographics) against Variant B (behaviour only).

    Flattened so a page can quote the two numbers that settled the decision without
    reaching into the artifact's structure itself.
    """
    payload = segmentation_results()["EXP-011_variants"]
    arms = {arm["variant"]: arm for arm in payload["arms"]}
    return {
        "k": payload["k"],
        "ari_between_variants": payload["ari_between_variants"],
        "decision_rule": payload["decision_rule"],
        "demographic_share": arms.get("A", {}).get("demographic_share"),
        "silhouette_A": arms.get("A", {}).get("silhouette"),
        "silhouette_B": arms.get("B", {}).get("silhouette"),
    }


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
def dataset_facts() -> dict[str, Any]:
    """Observed properties of the source data, from the Phase 2 audit."""
    return audit_results()
