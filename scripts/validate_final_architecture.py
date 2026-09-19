"""Phase 4 — validate the assembled final architecture.

Phase 3B evaluated eleven *methods*. The architecture this project will freeze is
an assembly of several of them — a tiered router whose personalised route is the
method the pre-registered rule selected — and that exact assembly was never
measured. Freezing an unmeasured configuration would be a gap, so it is measured
here.

**Test budget.** The test window was spent in Phase 3B, once, as pre-registered.
This script therefore evaluates on the **validation** window only, which is what
validation is for. The component test metrics from Phase 3B remain the best
available out-of-sample evidence and are quoted as such — they are not re-run.

Usage
-----
    python scripts/validate_final_architecture.py
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from edupro import config
from edupro.data.joins import build_interactions
from edupro.data.loader import load_all, verify_raw_workbook
from edupro.evaluation.protocol import (
    build_evaluation_set,
    evaluate,
    paired_bootstrap,
    per_user_ndcg,
)
from edupro.evaluation.splits import apply_global_split, global_temporal_split
from edupro.features.learner import build_learner_features
from edupro.recommendation.base import build_fit_context
from edupro.recommendation.baselines import (
    ClusterPopularity,
    ContentBased,
    DiversifiedFallback,
    GlobalPopularity,
    ItemItemCF,
    PreferenceMatch,
    RandomRecommender,
    RatingRecommender,
)
from edupro.recommendation.hybrid import TieredRecommender, WeightedHybrid
from edupro.segmentation.clustering import fit_kmeans
from edupro.segmentation.representations import REPRESENTATION_GRID, build_representation

OUT = config.ARTIFACTS_DIR / "architecture"

#: The hybrid weights found by the Phase 3B search. Reused, not re-searched.
HYBRID_WEIGHTS = {
    "cluster_popularity": 0.557,
    "rating": 0.249,
    "item_item_cf": 0.173,
    "preference_match": 0.021,
    "content_based": 0.0,
    "user_user_profile": 0.0,
}


def build_components(context) -> dict[str, Any]:
    components = {
        "random": RandomRecommender(),
        "global_popularity": GlobalPopularity(),
        "rating": RatingRecommender(),
        "content_based": ContentBased(),
        "preference_match": PreferenceMatch(),
        "item_item_cf": ItemItemCF(),
        "cluster_popularity": ClusterPopularity(),
    }
    for recommender in components.values():
        recommender.fit(context)
    return components


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    checksum = verify_raw_workbook()
    data = load_all()
    interactions = build_interactions(data, with_user_demographics=True, with_teacher=True)
    split = global_temporal_split(interactions)
    frames = apply_global_split(interactions, split)

    features = build_learner_features(frames["train"], users=data.users)
    spec = next(s for s in REPRESENTATION_GRID if s.name == "B_proportion")
    representation = build_representation(features, spec)
    clusters = pd.Series(
        fit_kmeans(representation.matrix, 4).labels_, index=features.index, name="cluster"
    )
    catalogue = (
        interactions.drop_duplicates(subset=[config.KEY_COURSE])
        .set_index(config.KEY_COURSE)
        .loc[sorted(interactions[config.KEY_COURSE].unique())]
        .reset_index()
    )
    context = build_fit_context(frames["train"], catalogue, features, clusters)
    evaluation_set = build_evaluation_set(
        frames["train"], frames["validation"], context, "A_validation"
    )
    components = build_components(context)

    # The Phase 3B hybrid, rebuilt with its searched weights (not re-searched).
    hybrid = WeightedHybrid(
        {name: components[name] for name in
         ("content_based", "preference_match", "item_item_cf", "cluster_popularity", "rating")
         },
        {k: v for k, v in HYBRID_WEIGHTS.items() if k != "user_user_profile"},
    ).fit(context)
    hybrid.name = "hybrid"

    # §15's prescribed fallback for learners with no history: popularity, rating
    # AND diversity. A plain popularity+rating blend was measured first and reached
    # only 17% of the catalogue - worse than popularity alone - because the two
    # signals concentrate on the same courses. DiversifiedFallback keeps the blend
    # and re-ranks it round-robin across categories.
    naive_fallback = WeightedHybrid(
        {"global_popularity": components["global_popularity"], "rating": components["rating"]},
        {"global_popularity": 0.5, "rating": 0.5},
    ).fit(context)
    naive_fallback.name = "popularity_rating_blend"
    fallback = DiversifiedFallback().fit(context)

    # ---- the three architectures under consideration ----------------------
    candidates: dict[str, Any] = {
        "A_cluster_popularity_flat": components["cluster_popularity"],
        "B_tiered_with_hybrid_core": TieredRecommender(routes={
            "insufficient": fallback,
            "minimal": components["content_based"],
            "moderate": hybrid,
            "rich": hybrid,
        }).fit(context),
        "C_tiered_with_selected_core": TieredRecommender(routes={
            "insufficient": fallback,
            "minimal": components["content_based"],
            "moderate": components["cluster_popularity"],
            "rich": components["cluster_popularity"],
        }).fit(context),
    }
    for name, recommender in candidates.items():
        recommender.name = name

    results: dict[str, Any] = {
        "provenance": {
            "workbook_sha256": checksum,
            "seed": config.RANDOM_SEED,
            "window": "VALIDATION ONLY - the test budget was spent once in Phase 3B",
            "validation_cut": str(split.validation_date.date()),
            "test_cut": str(split.test_date.date()),
            "n_evaluable_learners": len(evaluation_set.relevant),
            "note": (
                "Phase 3B evaluated individual methods. This script measures the "
                "assembled architecture, which no single Phase 3B row represents. "
                "Component test metrics from Phase 3B remain the out-of-sample "
                "evidence and are not re-run here."
            ),
        },
        "evaluation_set": evaluation_set.summary(),
    }

    random_scores = per_user_ndcg(components["random"], context, evaluation_set)
    print(f"validation learners: {len(evaluation_set.relevant)}")
    print(f"\n{'architecture':<32}{'NDCG@10':>9}{'HR@10':>8}{'cov':>7}{'gini':>7}"
          f"{'dNDCG vs random':>18}{'signif':>8}")

    comparison = {}
    for name, recommender in candidates.items():
        result = evaluate(recommender, context, evaluation_set)
        scores = per_user_ndcg(recommender, context, evaluation_set)
        significance = paired_bootstrap(scores, random_scores)
        metrics = result.overall[10]
        comparison[name] = {
            **result.to_dict(),
            "vs_random": significance,
        }
        flag = "YES" if significance["significant"] else "no"
        print(f"{name:<32}{metrics.ndcg:>9.4f}{metrics.hit_rate:>8.4f}"
              f"{metrics.coverage:>7.2f}{metrics.gini:>7.3f}"
              f"{significance['mean_difference']:>+18.4f}{flag:>8}")

    results["architectures"] = comparison

    # Per-tier behaviour of the chosen assembly.
    print("\nper-tier, architecture C:")
    for tier, per_k in comparison["C_tiered_with_selected_core"]["by_tier"].items():
        m = per_k["10"]
        print(f"  {tier:<12} n={m['n_users']:<5} NDCG={m['ndcg']:.4f} "
              f"HR={m['hit_rate']:.4f} cov={m['coverage']:.2f}")

    # Catalogue reach of the zero-history fallback, which cannot be accuracy-scored
    # because those learners have no history by definition.
    cold_start_users = [
        user for user in data.users[config.KEY_USER]
        if user not in context.seen
    ]
    # A learner with no history has nothing to differentiate them, so every
    # deterministic ranker gives all of them the *same* list. Cross-user catalogue
    # coverage is therefore fixed at K/60 = 0.17 for any fallback and measures
    # nothing. The meaningful diversity property is the spread *within* that one
    # list: how many of the twelve categories a cold-start learner is shown.
    indexed = catalogue.set_index(config.KEY_COURSE).reindex(context.course_ids)
    course_category = indexed["CourseCategory"].tolist()
    course_level = indexed["CourseLevel"].tolist()
    probe = cold_start_users[0]

    cold_start = {}
    for label, recommender in (
        ("global_popularity", components["global_popularity"]),
        ("rating", components["rating"]),
        ("popularity_rating_blend", naive_fallback),
        ("diversified_fallback", fallback),
    ):
        top = recommender.recommend(probe, k=10)
        categories = [course_category[int(i)] for i in top]
        cold_start[label] = {
            "distinct_categories_in_top_10": len(set(categories)),
            "distinct_levels_in_top_10": len({course_level[int(i)] for i in top}),
            "largest_category_share": round(
                max(categories.count(c) for c in set(categories)) / len(top), 4
            ),
        }

    results["cold_start_fallback"] = {
        "n_learners_with_no_history": len(cold_start_users),
        "within_list_diversity": cold_start,
        "selected": "diversified_fallback",
        "note": (
            "Accuracy cannot be measured for these learners: they have no training "
            "history, so there is nothing to personalise from and nothing to hold "
            "out. Cross-user catalogue coverage is also uninformative here - every "
            "deterministic ranker gives all of them the same list, fixing coverage "
            "at K/60. The meaningful property is how much of the catalogue that "
            "single list spans."
        ),
    }
    print(f"\ncold-start fallback ({len(cold_start_users)} learners with no history)")
    print(f"  {'fallback':<26}{'categories':>12}{'levels':>8}{'top-cat share':>15}")
    for label, payload in cold_start.items():
        print(f"  {label:<26}{payload['distinct_categories_in_top_10']:>12}"
              f"{payload['distinct_levels_in_top_10']:>8}"
              f"{payload['largest_category_share']:>15.2f}")

    destination = OUT / "architecture_validation.json"
    destination.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nWritten to {destination.relative_to(config.PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
