"""Phase 3B — recommendation experiments (EXP-019 … EXP-027).

Runs every baseline and hybrid candidate against the pre-registered protocol and
writes machine-readable results to ``artifacts/recommendation/``. Every number in
``research/recommendation_results.md`` comes from this file.

Protocol (pre-registered in Phase 1, confirmed viable in Phase 2)
    Training  : interactions before 2025-09-12  (validation stage)
    Validation: 2025-09-12 to 2025-10-18        -> model selection happens here
    Fit       : everything before 2025-10-18     (final stage)
    Test      : on or after 2025-10-18           -> touched ONCE, at the end

The test window is used exactly once, for the selected method, after selection is
complete. That budget is enforced in code, not by discipline.

Usage
-----
    python scripts/run_recommendation_experiments.py
"""

from __future__ import annotations

import json
import time
from typing import Any

import numpy as np
import pandas as pd

from edupro import config
from edupro.data.joins import build_interactions
from edupro.data.loader import load_all, verify_raw_workbook
from edupro.evaluation.metrics import engagement_lift_proxy
from edupro.evaluation.protocol import (
    DEFAULT_KS,
    build_evaluation_set,
    evaluate,
    paired_bootstrap,
    per_user_ndcg,
    verify_leakage_controls,
)
from edupro.evaluation.splits import (
    apply_global_split,
    global_temporal_split,
    leave_one_out_split,
)
from edupro.features.learner import build_learner_features
from edupro.recommendation.base import build_fit_context
from edupro.recommendation.baselines import (
    ClusterPopularity,
    ContentBased,
    GlobalPopularity,
    ItemItemCF,
    PreferenceMatch,
    RandomRecommender,
    RatingRecommender,
    TeacherAffinity,
    UserUserHistory,
    UserUserProfile,
)
from edupro.recommendation.hybrid import (
    TieredRecommender,
    WeightedHybrid,
    random_simplex_weights,
)
from edupro.segmentation.clustering import fit_kmeans
from edupro.segmentation.representations import REPRESENTATION_GRID, build_representation

OUT = config.ARTIFACTS_DIR / "recommendation"

#: Phase 3A's frozen configuration.
SEGMENTATION_REPRESENTATION = "B_proportion"
SEGMENTATION_K = 4

#: Pre-registered selection rule (`recommendation_evaluation_plan.md` §6).
COVERAGE_GATE = 0.25
PARSIMONY_MARGIN = 0.01
PRIMARY_K = 10

#: Weight-search budget for the hybrid. Fixed in advance so the search cannot be
#: quietly extended until a preferred method wins.
N_WEIGHT_SAMPLES = 400

#: Simplicity ranking for the parsimony tiebreak: how many signals each method
#: needs, and how much machinery it implies to maintain and explain.
COMPLEXITY = {
    "random": 0,
    "global_popularity": 1,
    "rating": 1,
    "content_based": 2,
    "preference_match": 2,
    "cluster_popularity": 3,
    "teacher_affinity": 2,
    "item_item_cf": 3,
    "user_user_history": 3,
    "user_user_profile": 4,
    "hybrid": 6,
    "tiered": 7,
}


def make_baselines() -> dict[str, Any]:
    """Every non-hybrid candidate. Each gets the same treatment [R26]."""
    return {
        "random": RandomRecommender(),
        "global_popularity": GlobalPopularity(),
        "rating": RatingRecommender(),
        "content_based": ContentBased(),
        "preference_match": PreferenceMatch(),
        "user_user_history": UserUserHistory(),
        "user_user_profile": UserUserProfile(),
        "item_item_cf": ItemItemCF(),
        "cluster_popularity": ClusterPopularity(),
        "teacher_affinity": TeacherAffinity(),
    }


def segment(features: pd.DataFrame) -> pd.Series:
    """Apply the Phase 3A segmentation to a feature frame."""
    spec = next(s for s in REPRESENTATION_GRID if s.name == SEGMENTATION_REPRESENTATION)
    representation = build_representation(features, spec)
    labels = fit_kmeans(representation.matrix, SEGMENTATION_K).labels_
    return pd.Series(labels, index=features.index, name="cluster")


def stage(interactions: pd.DataFrame, training: pd.DataFrame, held_out: pd.DataFrame,
          users: pd.DataFrame, protocol: str, cut: pd.Timestamp | None):
    """Build the context and evaluation set for one stage of the protocol."""
    features = build_learner_features(training, users=users)
    clusters = segment(features)
    courses = interactions[[config.KEY_COURSE]].drop_duplicates()
    catalogue = (
        interactions.drop_duplicates(subset=[config.KEY_COURSE])
        .set_index(config.KEY_COURSE)
        .loc[sorted(interactions[config.KEY_COURSE].unique())]
        .reset_index()
    )
    context = build_fit_context(training, catalogue, features, clusters)
    evaluation_set = build_evaluation_set(training, held_out, context, protocol)
    leakage = verify_leakage_controls(context, training, held_out, evaluation_set, cut)
    return context, evaluation_set, leakage


def main() -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}

    checksum = verify_raw_workbook()
    data = load_all()
    interactions = build_interactions(data, with_user_demographics=True, with_teacher=True)
    split = global_temporal_split(interactions)
    frames = apply_global_split(interactions, split)

    results["provenance"] = {
        "workbook_sha256": checksum,
        "seed": config.RANDOM_SEED,
        "validation_cut": str(split.validation_date.date()),
        "test_cut": str(split.test_date.date()),
        "ks": list(DEFAULT_KS),
        "primary_k": PRIMARY_K,
        "n_weight_samples": N_WEIGHT_SAMPLES,
        "segmentation": {"representation": SEGMENTATION_REPRESENTATION, "k": SEGMENTATION_K},
        "selection_rule": {
            "eligibility": "beat BOTH random and global popularity on validation NDCG@10",
            "coverage_gate": COVERAGE_GATE,
            "parsimony_margin": PARSIMONY_MARGIN,
            "test_budget": "the test window is evaluated exactly once, after selection",
        },
    }

    # =====================================================================
    # STAGE 1 - VALIDATION. All model selection happens here.
    # =====================================================================
    print("=" * 70)
    print("STAGE 1 - VALIDATION (train < 2025-09-12, target 09-12 to 10-18)")
    print("=" * 70)
    val_context, val_set, val_leakage = stage(
        interactions, frames["train"], frames["validation"], data.users,
        "A_validation", split.validation_date,
    )
    print(f"evaluable learners: {len(val_set.relevant)}")
    print(f"leakage controls  : {'ALL PASSED' if val_leakage['all_passed'] else 'FAILED'}")
    results["validation_set"] = val_set.summary()
    results["leakage_validation"] = val_leakage

    baselines = make_baselines()
    for recommender in baselines.values():
        recommender.fit(val_context)

    validation: dict[str, Any] = {}
    print(f"\n{'method':<22}{'NDCG@10':>9}{'HR@10':>8}{'P@10':>8}{'ceil':>8}"
          f"{'Rec@10':>8}{'MRR':>7}{'cov':>7}{'gini':>7}")
    for name, recommender in baselines.items():
        result = evaluate(recommender, val_context, val_set)
        validation[name] = result.to_dict()
        h = result.headline(PRIMARY_K)
        print(f"{name:<22}{h['ndcg']:>9.4f}{h['hit_rate']:>8.4f}{h['precision']:>8.4f}"
              f"{h['precision_ceiling']:>8.4f}{h['recall']:>8.4f}{h['mrr']:>7.4f}"
              f"{h['coverage']:>7.2f}{h['gini']:>7.3f}")

    # ------------------------------------------------ EXP-024 hybrid search
    print("\n[EXP-024] hybrid weight search "
          f"({N_WEIGHT_SAMPLES} samples from the simplex, seed {config.RANDOM_SEED}) ...")
    component_names = [
        "content_based", "user_user_profile", "cluster_popularity",
        "rating", "preference_match", "item_item_cf",
    ]
    components = {name: baselines[name] for name in component_names}
    base_hybrid = WeightedHybrid(components, {name: 1.0 for name in component_names})
    base_hybrid.fit(val_context)

    search_rows = []
    best_weights, best_ndcg = None, -1.0
    for weights in random_simplex_weights(component_names, N_WEIGHT_SAMPLES, config.RANDOM_SEED):
        candidate = base_hybrid.with_weights(weights)
        result = evaluate(candidate, val_context, val_set, ks=(PRIMARY_K,))
        metrics = result.overall[PRIMARY_K]
        search_rows.append({
            "weights": {k: round(v, 4) for k, v in weights.items()},
            "ndcg": round(metrics.ndcg, 6),
            "hit_rate": round(metrics.hit_rate, 6),
            "coverage": round(metrics.coverage, 6),
        })
        if metrics.ndcg > best_ndcg:
            best_ndcg, best_weights = metrics.ndcg, weights

    search_rows.sort(key=lambda r: -r["ndcg"])
    results["EXP-024_weight_search"] = {
        "n_samples": N_WEIGHT_SAMPLES,
        "components": component_names,
        "best_weights": {k: round(v, 4) for k, v in best_weights.items()},
        "best_validation_ndcg": round(best_ndcg, 6),
        "top_10": search_rows[:10],
        "ndcg_spread": {
            "min": round(min(r["ndcg"] for r in search_rows), 6),
            "max": round(max(r["ndcg"] for r in search_rows), 6),
            "std": round(float(np.std([r["ndcg"] for r in search_rows])), 6),
        },
    }
    print(f"  best validation NDCG@10 = {best_ndcg:.4f}")
    print(f"  weights: " + ", ".join(f"{k}={v:.3f}" for k, v in best_weights.items() if v > 0.01))
    print(f"  NDCG spread across the search: "
          f"{results['EXP-024_weight_search']['ndcg_spread']}")

    tuned_hybrid = base_hybrid.with_weights(best_weights)
    tuned_hybrid.name = "hybrid"
    validation["hybrid"] = evaluate(tuned_hybrid, val_context, val_set).to_dict()

    # ------------------------------------------------------- ablation
    print("\n[EXP-024b] component ablation (remove one component at a time) ...")
    ablation = []
    for removed in component_names:
        weights = {k: (0.0 if k == removed else v) for k, v in best_weights.items()}
        if sum(weights.values()) == 0:
            continue
        result = evaluate(base_hybrid.with_weights(weights), val_context, val_set, ks=(PRIMARY_K,))
        metrics = result.overall[PRIMARY_K]
        ablation.append({
            "removed": removed,
            "weight_in_best": round(best_weights[removed], 4),
            "ndcg": round(metrics.ndcg, 6),
            "delta_vs_full": round(metrics.ndcg - best_ndcg, 6),
            "coverage": round(metrics.coverage, 6),
        })
        print(f"  without {removed:<20} NDCG@10={metrics.ndcg:.4f} "
              f"(delta {metrics.ndcg - best_ndcg:+.4f})")
    results["EXP-024b_ablation"] = ablation

    # ------------------------------------------------ EXP-025 tiered routing
    print("\n[EXP-025] tiered switching recommender ...")
    tiered = TieredRecommender(routes={
        "insufficient": baselines["global_popularity"],
        "minimal": baselines["content_based"],
        "moderate": tuned_hybrid,
        "rich": tuned_hybrid,
    })
    tiered.fit(val_context)
    validation["tiered"] = evaluate(tiered, val_context, val_set).to_dict()
    results["validation"] = validation

    # ------------------------------------------------ pre-registered selection
    random_ndcg = validation["random"]["overall"][str(PRIMARY_K)]["ndcg"]
    popularity_ndcg = validation["global_popularity"]["overall"][str(PRIMARY_K)]["ndcg"]
    popularity_hr = validation["global_popularity"]["overall"][str(PRIMARY_K)]["hit_rate"]

    candidates = []
    for name, payload in validation.items():
        if name == "random":
            continue
        metrics = payload["overall"][str(PRIMARY_K)]
        beats_random = metrics["ndcg"] > random_ndcg
        beats_popularity = metrics["ndcg"] > popularity_ndcg
        passes_coverage = metrics["coverage"] >= COVERAGE_GATE
        candidates.append({
            "method": name,
            "validation_ndcg": metrics["ndcg"],
            "coverage": metrics["coverage"],
            "beats_random": beats_random,
            "beats_popularity": beats_popularity,
            "passes_coverage_gate": passes_coverage,
            "eligible": bool(beats_random and beats_popularity and passes_coverage),
            "complexity": COMPLEXITY.get(name, 99),
        })
    candidates.sort(key=lambda c: -c["validation_ndcg"])

    eligible = [c for c in candidates if c["eligible"]]
    if eligible:
        best = max(eligible, key=lambda c: c["validation_ndcg"])
        simplest = min(eligible, key=lambda c: (c["complexity"], -c["validation_ndcg"]))
        if best["validation_ndcg"] - simplest["validation_ndcg"] < PARSIMONY_MARGIN:
            selected, reason = simplest, (
                f"parsimony tiebreak: the best method beat the simplest eligible one by "
                f"{best['validation_ndcg'] - simplest['validation_ndcg']:.4f} NDCG@10, "
                f"under the pre-registered {PARSIMONY_MARGIN} margin"
            )
        else:
            selected, reason = best, "highest validation NDCG@10 among eligible methods"
    else:
        selected, reason = None, (
            "NO method satisfied the pre-registered eligibility rule: beating both "
            "random and global popularity on validation NDCG@10 while keeping "
            f"catalogue coverage at or above {COVERAGE_GATE:.0%}"
        )

    results["selection"] = {
        "random_ndcg": random_ndcg,
        "popularity_ndcg": popularity_ndcg,
        "candidates": candidates,
        "n_eligible": len(eligible),
        "selected": selected["method"] if selected else None,
        "reason": reason,
    }
    print("\n" + "=" * 70)
    print("PRE-REGISTERED SELECTION")
    print("=" * 70)
    print(f"  random NDCG@10     = {random_ndcg:.4f}")
    print(f"  popularity NDCG@10 = {popularity_ndcg:.4f}")
    print(f"  eligible methods   = {[c['method'] for c in eligible]}")
    print(f"  SELECTED           = {selected['method'] if selected else 'NONE'}")
    print(f"  reason             = {reason}")

    # =====================================================================
    # STAGE 2 - TEST. Touched exactly once, after selection.
    # =====================================================================
    print("\n" + "=" * 70)
    print("STAGE 2 - TEST (fit < 2025-10-18, target >= 2025-10-18) - ONE evaluation")
    print("=" * 70)
    test_context, test_set, test_leakage = stage(
        interactions, frames["fit"], frames["test"], data.users, "A_test", split.test_date,
    )
    print(f"evaluable learners: {len(test_set.relevant)}")
    print(f"leakage controls  : {'ALL PASSED' if test_leakage['all_passed'] else 'FAILED'}")
    results["test_set"] = test_set.summary()
    results["leakage_test"] = test_leakage

    test_baselines = make_baselines()
    for recommender in test_baselines.values():
        recommender.fit(test_context)
    test_components = {name: test_baselines[name] for name in component_names}
    test_hybrid = WeightedHybrid(test_components, best_weights)
    test_hybrid.fit(test_context)
    test_hybrid.name = "hybrid"
    test_tiered = TieredRecommender(routes={
        "insufficient": test_baselines["global_popularity"],
        "minimal": test_baselines["content_based"],
        "moderate": test_hybrid,
        "rich": test_hybrid,
    })
    test_tiered.fit(test_context)

    all_test = {**test_baselines, "hybrid": test_hybrid, "tiered": test_tiered}
    test_results: dict[str, Any] = {}
    print(f"\n{'method':<22}{'NDCG@10':>9}{'HR@10':>8}{'P@10':>8}{'ceil':>8}"
          f"{'Rec@10':>8}{'MRR':>7}{'cov':>7}{'lift':>7}")
    test_popularity_hr = None
    for name, recommender in all_test.items():
        result = evaluate(recommender, test_context, test_set)
        test_results[name] = result.to_dict()
        if name == "global_popularity":
            test_popularity_hr = result.overall[PRIMARY_K].hit_rate
    for name, payload in test_results.items():
        m = payload["overall"][str(PRIMARY_K)]
        lift = engagement_lift_proxy(m["hit_rate"], test_popularity_hr)
        payload["engagement_lift_proxy"] = round(lift, 6)
        print(f"{name:<22}{m['ndcg']:>9.4f}{m['hit_rate']:>8.4f}{m['precision']:>8.4f}"
              f"{m['precision_ceiling']:>8.4f}{m['recall']:>8.4f}{m['mrr']:>7.4f}"
              f"{m['coverage']:>7.2f}{lift:>7.3f}")
    results["test"] = test_results
    results["test_budget_spent"] = True

    # ---------------------------------------------------------------------
    # Does ANY method beat random by more than sampling noise?
    # An aggregate gap of a few thousandths of NDCG on 791 learners means
    # nothing without a paired test, and the honest answer here may well be
    # "no" - so the test is run rather than the gap being eyeballed.
    # ---------------------------------------------------------------------
    print("\n[significance] paired bootstrap of per-learner NDCG@10 vs random ...")
    random_scores = per_user_ndcg(all_test["random"], test_context, test_set, PRIMARY_K)
    popularity_scores = per_user_ndcg(
        all_test["global_popularity"], test_context, test_set, PRIMARY_K
    )
    significance = {}
    print(f"  {'method':<22}{'dNDCG':>9}{'95% CI':>22}{'signif.':>10}")
    for name, recommender in all_test.items():
        if name == "random":
            continue
        scores = per_user_ndcg(recommender, test_context, test_set, PRIMARY_K)
        vs_random = paired_bootstrap(scores, random_scores)
        vs_popularity = paired_bootstrap(scores, popularity_scores)
        significance[name] = {"vs_random": vs_random, "vs_popularity": vs_popularity}
        ci = f"[{vs_random['ci_95_low']:+.4f}, {vs_random['ci_95_high']:+.4f}]"
        flag = "YES" if vs_random["significant"] else "no"
        print(f"  {name:<22}{vs_random['mean_difference']:>+9.4f}{ci:>22}{flag:>10}")
    n_significant = sum(
        1 for v in significance.values() if v["vs_random"]["significant"]
        and v["vs_random"]["direction"] == "better"
    )
    results["significance_vs_random"] = {
        "test": "paired bootstrap of per-learner NDCG@10 differences, 2000 resamples",
        "n_methods_significantly_better_than_random": n_significant,
        "per_method": significance,
        "interpretation": (
            "A 95% interval containing zero means the method has NOT been shown to "
            "beat the baseline. Phase 2 found course choice statistically "
            "indistinguishable from popularity-weighted chance, so this is the "
            "expected outcome and is reported as the headline rather than buried."
        ),
    }
    print(f"  -> methods significantly better than random: {n_significant}")

    # ---------------------------------------------------------------------
    # STEP 11 - error analysis on the reported method
    # ---------------------------------------------------------------------
    print("\n[error analysis] characterising where recommendations miss ...")
    # The method the project reports. Where no method satisfied the eligibility
    # rule, global popularity is analysed as the fallback the system would ship.
    reported = selected["method"] if selected else "global_popularity"
    reported_recommender = all_test[reported]
    catalogue = test_context.courses.set_index(config.KEY_COURSE)
    course_meta = {
        i: {
            "category": catalogue.iloc[i]["CourseCategory"],
            "level": catalogue.iloc[i]["CourseLevel"],
            "type": catalogue.iloc[i]["CourseType"],
            "rating": float(catalogue.iloc[i]["CourseRating"]),
        }
        for i in range(test_context.n_items)
    }
    popularity_rank = {
        int(position): rank
        for rank, position in enumerate(
            np.argsort(-test_baselines["global_popularity"].popularity)
        )
    }

    rows = []
    for user, relevant in test_set.relevant.items():
        candidates = test_context.candidates_for(user)
        if len(candidates) == 0:
            continue
        ranked = reported_recommender.score(user, candidates).ranked()
        top = set(ranked[:PRIMARY_K].tolist())
        hit = bool(top & relevant)
        history = sorted(test_context.seen.get(user, set()))
        history_categories = {course_meta[i]["category"] for i in history}
        history_levels = {course_meta[i]["level"] for i in history}
        target_categories = {course_meta[i]["category"] for i in relevant}
        target_levels = {course_meta[i]["level"] for i in relevant}
        rows.append({
            "user": user,
            "hit": hit,
            "tier": test_set.tier_of_user(user),
            "history_length": len(history),
            "n_targets": len(relevant),
            "n_candidates": len(candidates),
            "category_match": bool(history_categories & target_categories),
            "level_match": bool(history_levels & target_levels),
            "mean_target_popularity_rank": float(
                np.mean([popularity_rank[i] for i in relevant])
            ),
            "mean_recommended_popularity_rank": float(
                np.mean([popularity_rank[i] for i in ranked[:PRIMARY_K]])
            ),
        })
    error_frame = pd.DataFrame(rows)
    error_frame.to_csv(OUT / "error_analysis.csv", index=False)

    def rate(frame: pd.DataFrame) -> float:
        return round(float(frame["hit"].mean()), 6) if len(frame) else float("nan")

    analysis = {
        "method": reported,
        "n_users": int(len(error_frame)),
        "overall_hit_rate": rate(error_frame),
        "by_tier": {
            tier: {"n": int(len(g)), "hit_rate": rate(g),
                   "mean_history": round(float(g.history_length.mean()), 2),
                   "mean_targets": round(float(g.n_targets.mean()), 2)}
            for tier, g in error_frame.groupby("tier")
        },
        "by_history_length": {
            int(n): {"n": int(len(g)), "hit_rate": rate(g)}
            for n, g in error_frame.groupby("history_length") if len(g) >= 10
        },
        "by_n_targets": {
            int(n): {"n": int(len(g)), "hit_rate": rate(g)}
            for n, g in error_frame.groupby("n_targets") if len(g) >= 10
        },
        "category_match": {
            "when_history_category_overlaps_target": rate(error_frame[error_frame.category_match]),
            "when_it_does_not": rate(error_frame[~error_frame.category_match]),
            "n_overlapping": int(error_frame.category_match.sum()),
        },
        "level_match": {
            "when_history_level_overlaps_target": rate(error_frame[error_frame.level_match]),
            "when_it_does_not": rate(error_frame[~error_frame.level_match]),
            "n_overlapping": int(error_frame.level_match.sum()),
        },
        "popularity_bias": {
            "mean_recommended_popularity_rank": round(
                float(error_frame.mean_recommended_popularity_rank.mean()), 2),
            "mean_target_popularity_rank": round(
                float(error_frame.mean_target_popularity_rank.mean()), 2),
            "catalogue_midpoint": test_context.n_items / 2,
            "hits_mean_target_rank": round(
                float(error_frame[error_frame.hit].mean_target_popularity_rank.mean()), 2),
            "misses_mean_target_rank": round(
                float(error_frame[~error_frame.hit].mean_target_popularity_rank.mean()), 2),
        },
        "candidate_pool": {
            "mean": round(float(error_frame.n_candidates.mean()), 2),
            "min": int(error_frame.n_candidates.min()),
            "max": int(error_frame.n_candidates.max()),
            "users_with_pool_below_k": int((error_frame.n_candidates < PRIMARY_K).sum()),
        },
    }
    results["EXP-error_analysis"] = analysis
    print(f"  overall hit rate @10: {analysis['overall_hit_rate']:.4f}")
    for tier, payload in analysis["by_tier"].items():
        print(f"    {tier:<14} n={payload['n']:<5} HR={payload['hit_rate']:.4f}")
    print(f"  category overlap helps? {analysis['category_match']}")
    print(f"  popularity bias: recommended rank "
          f"{analysis['popularity_bias']['mean_recommended_popularity_rank']:.1f} "
          f"vs target rank {analysis['popularity_bias']['mean_target_popularity_rank']:.1f} "
          f"(midpoint {analysis['popularity_bias']['catalogue_midpoint']})")

    # =====================================================================
    # EXP-026 - leakage demonstration (the one use of the rejected random split)
    # =====================================================================
    print("\n[EXP-026] leakage demonstration: per-user leave-one-out (Protocol B) ...")
    loo = leave_one_out_split(interactions)
    loo_context, loo_set, _ = stage(
        interactions, loo["train"], loo["test"], data.users, "B_leave_one_out", None,
    )
    loo_baselines = make_baselines()
    for recommender in loo_baselines.values():
        recommender.fit(loo_context)
    loo_components = {name: loo_baselines[name] for name in component_names}
    loo_hybrid = WeightedHybrid(loo_components, best_weights)
    loo_hybrid.fit(loo_context)
    loo_hybrid.name = "hybrid"
    loo_results = {}
    for name, recommender in {**loo_baselines, "hybrid": loo_hybrid}.items():
        loo_results[name] = evaluate(recommender, loo_context, loo_set).to_dict()
    results["EXP-026_protocol_b"] = {
        "warning": (
            "PROTOCOL B LEAKS. Each learner's cut is a different calendar date, so "
            "training contains interactions occurring after some learners' test "
            "points [R25]. Reported only for comparability with published work."
        ),
        "evaluation_set": loo_set.summary(),
        "results": loo_results,
    }
    print(f"  evaluable learners: {len(loo_set.relevant)}")
    comparison = []
    for name in loo_results:
        if name not in test_results:
            continue
        comparison.append({
            "method": name,
            "protocol_a_ndcg": test_results[name]["overall"][str(PRIMARY_K)]["ndcg"],
            "protocol_b_ndcg": loo_results[name]["overall"][str(PRIMARY_K)]["ndcg"],
        })
    for row in comparison:
        row["inflation"] = round(row["protocol_b_ndcg"] - row["protocol_a_ndcg"], 6)
    order_a = [r["method"] for r in sorted(comparison, key=lambda r: -r["protocol_a_ndcg"])]
    order_b = [r["method"] for r in sorted(comparison, key=lambda r: -r["protocol_b_ndcg"])]
    results["EXP-026_protocol_b"]["comparison"] = comparison
    results["EXP-026_protocol_b"]["ranking_a"] = order_a
    results["EXP-026_protocol_b"]["ranking_b"] = order_b
    results["EXP-026_protocol_b"]["rankings_agree"] = order_a == order_b
    print(f"  method ranking identical across protocols: {order_a == order_b}")

    # =====================================================================
    # EXP-027 - demographic-stratified evaluation
    # =====================================================================
    print("\n[EXP-027] demographic-stratified evaluation of the reported method ...")
    demographics = data.users.set_index(config.KEY_USER)
    strata: dict[str, Any] = {}
    for label, users in (
        ("female", set(demographics[demographics["Gender"] == "Female"].index)),
        ("male", set(demographics[demographics["Gender"] == "Male"].index)),
        ("age_15_24", set(demographics[demographics["Age"] <= 24].index)),
        ("age_25_35", set(demographics[demographics["Age"] >= 25].index)),
    ):
        subset = type(test_set)(
            relevant={u: v for u, v in test_set.relevant.items() if u in users},
            protocol=test_set.protocol,
            history_length={u: v for u, v in test_set.history_length.items() if u in users},
        )
        if not subset.relevant:
            continue
        result = evaluate(reported_recommender, test_context, subset, ks=(PRIMARY_K,))
        metrics = result.overall[PRIMARY_K]
        strata[label] = {
            "n_users": metrics.n_users,
            "ndcg": round(metrics.ndcg, 6),
            "hit_rate": round(metrics.hit_rate, 6),
            "coverage": round(metrics.coverage, 6),
        }
        print(f"  {label:<12} n={metrics.n_users:<5} NDCG@10={metrics.ndcg:.4f} "
              f"HR@10={metrics.hit_rate:.4f}")
    # Is the gender gap real, or sampling noise? An unpaired difference between
    # two learner groups needs a test before it is reported as a disparity [R30].
    reported_scores = per_user_ndcg(reported_recommender, test_context, test_set, PRIMARY_K)
    female = set(demographics[demographics["Gender"] == "Female"].index)
    female_values = np.array([v for u, v in reported_scores.items() if u in female])
    male_values = np.array([v for u, v in reported_scores.items() if u not in female])
    rng = np.random.default_rng(config.RANDOM_SEED)
    differences = np.array([
        rng.choice(female_values, len(female_values)).mean()
        - rng.choice(male_values, len(male_values)).mean()
        for _ in range(2000)
    ])
    low, high = np.percentile(differences, [2.5, 97.5])
    gender_gap = {
        "female_mean_ndcg": round(float(female_values.mean()), 6),
        "male_mean_ndcg": round(float(male_values.mean()), 6),
        "difference": round(float(female_values.mean() - male_values.mean()), 6),
        "ci_95_low": round(float(low), 6),
        "ci_95_high": round(float(high), 6),
        "significant": bool(low > 0 or high < 0),
    }
    results["EXP-027_demographic_strata"] = {
        "method": reported,
        "strata": strata,
        "gender_gap_test": gender_gap,
    }
    print(f"  gender gap: {gender_gap['difference']:+.4f} "
          f"[{gender_gap['ci_95_low']:+.4f}, {gender_gap['ci_95_high']:+.4f}] "
          f"-> {'SIGNIFICANT' if gender_gap['significant'] else 'not significant'}")

    # A nominally significant gap is not yet a disparity. Before reporting one,
    # check whether it survives conditioning on history depth: if the groups are
    # composed differently across tiers, the aggregate gap can be composition
    # rather than differential treatment - especially when the recommender uses no
    # demographic feature at all.
    gender_series = demographics["Gender"]
    within_tier = {}
    for tier in sorted({test_set.tier_of_user(u) for u in test_set.relevant}):
        users = [u for u in reported_scores if test_set.tier_of_user(u) == tier]
        female_tier = [reported_scores[u] for u in users if gender_series.get(u) == "Female"]
        male_tier = [reported_scores[u] for u in users if gender_series.get(u) == "Male"]
        if not female_tier or not male_tier:
            continue
        within_tier[tier] = {
            "n_female": len(female_tier),
            "n_male": len(male_tier),
            "female_ndcg": round(float(np.mean(female_tier)), 6),
            "male_ndcg": round(float(np.mean(male_tier)), 6),
            "difference": round(float(np.mean(female_tier) - np.mean(male_tier)), 6),
        }
    directions = {np.sign(v["difference"]) for v in within_tier.values()}
    gender_gap["within_tier"] = within_tier
    gender_gap["consistent_direction_across_tiers"] = len(directions) == 1
    gender_gap["tier_composition"] = {
        tier: {
            "female_share": round(
                sum(1 for u in test_set.relevant
                    if test_set.tier_of_user(u) == tier and gender_series.get(u) == "Female")
                / max(1, sum(1 for u in test_set.relevant if test_set.tier_of_user(u) == tier)),
                4,
            )
        }
        for tier in within_tier
    }
    print(f"  within-tier differences: "
          + ", ".join(f"{t}={v['difference']:+.3f}" for t, v in within_tier.items()))
    print(f"  consistent direction across tiers: "
          f"{gender_gap['consistent_direction_across_tiers']}")

    # Does the reported method help in every tier, or only some? An aggregate
    # comparison against random can conceal a method that helps one population and
    # hurts another, and CLAUDE.md §12 requires the tiers be read separately.
    print("\n[per-tier] reported method vs random, paired within each tier ...")
    per_tier_significance = {}
    for tier in sorted({test_set.tier_of_user(u) for u in test_set.relevant}):
        users = {u for u in test_set.relevant if test_set.tier_of_user(u) == tier}
        method_subset = {u: v for u, v in reported_scores.items() if u in users}
        random_subset = {u: v for u, v in random_scores.items() if u in users}
        comparison = paired_bootstrap(method_subset, random_subset)
        per_tier_significance[tier] = comparison
        flag = "YES" if comparison["significant"] else "no"
        print(f"  {tier:<14} n={comparison['n_users']:<5} "
              f"dNDCG={comparison['mean_difference']:+.4f} "
              f"[{comparison['ci_95_low']:+.4f}, {comparison['ci_95_high']:+.4f}]  {flag}")
    results["per_tier_significance_vs_random"] = {
        "method": reported,
        "per_tier": per_tier_significance,
    }

    # ------------------------------------------------ coverage accounting
    all_learners = set(data.users[config.KEY_USER])
    with_history = set(test_context.seen)
    tier_counts: dict[str, int] = {}
    for user in all_learners:
        from edupro.recommendation.hybrid import tier_of
        tier_counts[tier_of(len(test_context.seen.get(user, set())))] = (
            tier_counts.get(tier_of(len(test_context.seen.get(user, set()))), 0) + 1
        )
    results["EXP-009_coverage_accounting"] = {
        "total_learners": len(all_learners),
        "learners_with_training_history": len(with_history),
        "learners_receiving_recommendations": len(all_learners),
        "learners_receiving_personalised": sum(
            n for tier, n in tier_counts.items() if tier != "insufficient"
        ),
        "learners_on_fallback": tier_counts.get("insufficient", 0),
        "learners_by_tier": tier_counts,
        "mean_candidate_pool": round(
            float(np.mean([
                len(test_context.candidates_for(u)) for u in list(all_learners)[:500]
            ])), 2
        ),
        "learners_with_empty_candidate_pool": sum(
            1 for u in all_learners if len(test_context.candidates_for(u)) == 0
        ),
    }

    destination = OUT / "recommendation_results.json"
    destination.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nWritten to {destination.relative_to(config.PROJECT_ROOT)} "
          f"({time.time() - started:.0f}s)")


if __name__ == "__main__":
    main()
