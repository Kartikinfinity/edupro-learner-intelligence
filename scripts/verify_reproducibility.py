"""Recompute headline experiment results and compare them to the stored artifacts.

Phase 5A refactored code the Phase 3A and 3B experiments ran through — the
segmentation representation gained a transform path for inference, and the course
content matrix moved into the feature layer. Neither change was supposed to alter
a single number. Asserting that would be worthless; this script measures it.

It recomputes a small set of headline results from scratch and compares each one
against the value stored in the experiment artifacts. A mismatch means the
refactor changed the science, and the refactor is wrong.

Usage
-----
    python scripts/verify_reproducibility.py
"""

from __future__ import annotations

import json
import sys
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import silhouette_score

from edupro import config
from edupro.data.joins import build_interactions
from edupro.data.loader import load_all, verify_raw_workbook
from edupro.evaluation.protocol import build_evaluation_set, evaluate
from edupro.evaluation.splits import apply_global_split, global_temporal_split
from edupro.features.learner import build_learner_features
from edupro.recommendation.base import build_fit_context
from edupro.recommendation.baselines import ClusterPopularity, ContentBased, RandomRecommender
from edupro.segmentation.clustering import fit_kmeans
from edupro.segmentation.representations import REPRESENTATION_GRID, build_representation
from edupro.segmentation.stability import assess_stability

#: Absolute tolerance. These are deterministic computations under a fixed seed, so
#: the only expected difference is floating-point noise.
TOLERANCE = 1e-6


class Check:
    """One recomputed value against one stored value."""

    def __init__(self, name: str, stored: float, recomputed: float) -> None:
        self.name = name
        self.stored = float(stored)
        self.recomputed = float(recomputed)

    @property
    def ok(self) -> bool:
        return abs(self.stored - self.recomputed) <= TOLERANCE

    def __str__(self) -> str:
        status = "OK  " if self.ok else "FAIL"
        return (
            f"  [{status}] {self.name:<46} stored {self.stored:.6f} "
            f"recomputed {self.recomputed:.6f}"
        )


def main() -> int:
    checks: list[Check] = []

    checksum = verify_raw_workbook()
    print(f"Workbook sha256 verified: {checksum[:16]}...")

    segmentation = json.loads(
        (config.ARTIFACTS_DIR / "segmentation" / "segmentation_results.json").read_text(
            encoding="utf-8"
        )
    )
    recommendation = json.loads(
        (config.ARTIFACTS_DIR / "recommendation" / "recommendation_results.json").read_text(
            encoding="utf-8"
        )
    )
    architecture = json.loads(
        (config.ARTIFACTS_DIR / "architecture" / "architecture_validation.json").read_text(
            encoding="utf-8"
        )
    )

    data = load_all()
    interactions = build_interactions(data, with_user_demographics=True, with_teacher=True)
    split = global_temporal_split(interactions)
    frames = apply_global_split(interactions, split)

    # --- segmentation, on the fit window ------------------------------------
    print("\nSegmentation (fit window, B_proportion, k=4)")
    features = build_learner_features(frames["fit"], users=data.users)
    spec = next(s for s in REPRESENTATION_GRID if s.name == "B_proportion")
    representation = build_representation(features, spec)
    labels = fit_kmeans(representation.matrix, 4).labels_

    stored_k4 = next(
        row for row in segmentation["EXP-010_k_sweep"] if int(row["k"]) == 4
    )
    checks.append(
        Check(
            "silhouette, B_proportion k=4",
            stored_k4["silhouette"],
            silhouette_score(representation.matrix, labels),
        )
    )

    stability = assess_stability(representation.matrix, 4)
    checks.append(
        Check(
            "mean bootstrap Jaccard, k=4",
            segmentation["EXP-013_stability"]["mean_jaccard"],
            round(stability.mean_jaccard, 4),
        )
    )
    for check in checks[-2:]:
        print(check)

    # --- recommendation, on the test window ---------------------------------
    print("\nRecommendation (test window, Protocol A)")
    fit_features = build_learner_features(frames["fit"], users=data.users)
    fit_representation = build_representation(fit_features, spec)
    fit_labels = fit_kmeans(fit_representation.matrix, 4).labels_
    clusters = pd.Series(fit_labels, index=fit_features.index, name="cluster")
    catalogue = (
        interactions.drop_duplicates(subset=[config.KEY_COURSE])
        .set_index(config.KEY_COURSE)
        .loc[sorted(interactions[config.KEY_COURSE].unique())]
        .reset_index()
    )
    context = build_fit_context(frames["fit"], catalogue, fit_features, clusters)
    evaluation_set = build_evaluation_set(frames["fit"], frames["test"], context, "A_test")

    for name, recommender in (
        ("random", RandomRecommender()),
        ("content_based", ContentBased()),
        ("cluster_popularity", ClusterPopularity()),
    ):
        result = evaluate(recommender.fit(context), context, evaluation_set)
        check = Check(
            f"NDCG@10, {name}",
            recommendation["test"][name]["overall"]["10"]["ndcg"],
            round(result.overall[10].ndcg, 6),
        )
        checks.append(check)
        print(check)

    # --- the assembled architecture, on the validation window ---------------
    print("\nArchitecture C (validation window)")
    stored = architecture["architectures"]["C_tiered_with_selected_core"]["overall"]["10"]
    train_features = build_learner_features(frames["train"], users=data.users)
    train_representation = build_representation(train_features, spec)
    train_labels = fit_kmeans(train_representation.matrix, 4).labels_
    train_clusters = pd.Series(train_labels, index=train_features.index, name="cluster")
    train_context = build_fit_context(
        frames["train"], catalogue, train_features, train_clusters
    )
    validation_set = build_evaluation_set(
        frames["train"], frames["validation"], train_context, "A_validation"
    )
    from edupro.recommendation.baselines import DiversifiedFallback
    from edupro.recommendation.hybrid import TieredRecommender

    router = TieredRecommender(
        routes={
            "insufficient": DiversifiedFallback(),
            "minimal": ContentBased(),
            "moderate": ClusterPopularity(),
            "rich": ClusterPopularity(),
        }
    ).fit(train_context)
    result = evaluate(router, train_context, validation_set)
    for metric in ("ndcg", "hit_rate", "coverage"):
        check = Check(
            f"{metric}@10, architecture C",
            stored[metric],
            round(getattr(result.overall[10], metric), 6),
        )
        checks.append(check)
        print(check)

    failures = [c for c in checks if not c.ok]
    print()
    if failures:
        print(f"REPRODUCIBILITY FAILED: {len(failures)} of {len(checks)} checks differ")
        for check in failures:
            print(str(check))
        return 1
    print(f"All {len(checks)} checks reproduce the stored results exactly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
