"""Check that the numbers printed in the written deliverables match the artifacts.

A paper can claim traceability; this measures it. Each check takes a value
*computed from an experiment artifact*, formats it the way the paper prints it,
and requires that string to appear in `docs/research_paper.md`. A figure that was
mistyped, copied from an earlier run, or quietly rounded the wrong way fails here.

The checks are deliberately written to read the artifact first and the paper
second, so a wrong number in the paper cannot make its own check pass.

Usage
-----
    python scripts/verify_paper_claims.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from edupro import config

PAPER = config.DOCS_DIR / "research_paper.md"
SUMMARY = config.DOCS_DIR / "executive_summary.md"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if not PAPER.exists():
        raise SystemExit(f"{PAPER} not found")
    # The paper uses typographic minus signs and thin spaces; the artifacts use
    # ASCII. Normalise presentation so the comparison is about values.
    text = (
        PAPER.read_text(encoding="utf-8")
        .replace("−", "-")
        .replace("–", "-")
        .replace(" ", "")
        .replace(" ", " ")
    )

    audit = load(config.ARTIFACTS_DIR / "phase2_audit.json")
    seg = load(config.ARTIFACTS_DIR / "segmentation" / "segmentation_results.json")
    rec = load(config.ARTIFACTS_DIR / "recommendation" / "recommendation_results.json")
    arch = load(config.ARTIFACTS_DIR / "architecture" / "architecture_validation.json")
    profiles = pd.read_csv(config.ARTIFACTS_DIR / "segmentation" / "cluster_profiles.csv")

    sparsity = audit["EXP-003_sparsity"]
    popularity = audit["EXP-006_distributions"]["course_popularity"]
    signal = audit["signal_detection"]
    split = audit["EXP-004_temporal_split"]
    k4 = next(r for r in seg["EXP-010_k_sweep"] if r["k"] == 4)
    test = rec["test"]
    sig = rec["significance_vs_random"]["per_method"]

    checks: list[tuple[str, str]] = []

    def check(label: str, value: str) -> None:
        checks.append((label, value))

    # --- dataset ---------------------------------------------------------
    check("learners", f"{sparsity['n_learners']:,}")
    check("interactions", f"{split['n_train'] + split['n_validation'] + split['n_test']:,}")
    check("single-interaction share", f"{sparsity['pct_with_1']:.1f}%")
    check("learners with 1 enrollment", f"{sparsity['n_with_1']:,}")
    check("max enrollments", str(sparsity["max"]))
    check("learner activity Gini", f"{sparsity['gini_user_activity']:.3f}")
    check("mean enrollments", f"{sparsity['mean']:.3f}")

    # --- popularity ------------------------------------------------------
    check("popularity min", str(popularity["min"]))
    check("popularity max", str(popularity["max"]))
    check("popularity Gini", f"{popularity['gini']:.3f}")
    check("popularity chi2 p", f"{popularity['chi_square_uniform']['p_value']:.3f}")

    # --- signal detection ------------------------------------------------
    levels = signal["preference_vs_popularity_null"]["mean_distinct_levels"]
    check("distinct levels observed", f"{levels['observed']:.3f}")
    check("distinct levels z", f"{levels['z']:.2f}")
    check("gender x category p", f"{signal['demographics_vs_choice']['gender_x_category']['p_value']:.3f}")
    check("teacher concentration observed", f"{signal['teacher_concentration']['observed_distinct_teachers_per_interaction']:.3f}")

    teacher = audit["behavioural_structure"]["teacher_predicts_next_course"]
    check("teacher next-course hit", f"{teacher['hit_rate']:.4f}")
    check("teacher next-course lift", f"{teacher['lift']:.3f}")
    progression = audit["behavioural_structure"]["level_progression"]
    check("level progression p", f"{progression['p_value']:.3f}")

    # --- split -----------------------------------------------------------
    check("train rows", f"{split['n_train']:,}")
    check("test rows", f"{split['n_test']:,}")
    check("evaluable learners", str(split["n_evaluable_learners"]))
    check("validation cut", split["validation_date"])
    check("test cut", split["test_date"])

    # --- segmentation ----------------------------------------------------
    check("k=4 silhouette", f"{k4['silhouette']:.4f}")
    check("k=4 intra-cluster similarity", f"{k4['intra_cluster_similarity']:.3f}")
    check("k=4 seed ARI", f"{k4['seed_stability_ari']:.5f}")
    check("mean bootstrap Jaccard", f"{seg['EXP-013_stability']['mean_jaccard']:.4f}")
    check("variant ARI", f"{seg['EXP-011_variants']['ari_between_variants']:.3f}")
    teacher_arm = next(a for a in seg["EXP-014_teacher"]["arms"] if a["representation"] == "B_teacher")
    check("teacher arm silhouette", f"{teacher_arm['silhouette']:.6f}")
    check("teacher ARI", f"{seg['EXP-014_teacher']['ari_core_vs_teacher']:.3f}")
    check("hierarchical ARI ward", f"{seg['EXP-012_hierarchical']['ari_kmeans_vs_ward']:.3f}")
    check("hierarchical ARI average", f"{seg['EXP-012_hierarchical']['ari_kmeans_vs_average']:.3f}")
    blocks = seg["EXP-011g_level_ablation"]["arms"][0]["block_explained_share"]
    check("level block share", f"{blocks['level'] * 100:.1f}%")
    check("category block share", f"{blocks['category'] * 100:.1f}%")

    for _, row in profiles.iterrows():
        check(f"segment {int(row['cluster'])} size", f"{int(row['n_learners'])}")
        check(f"segment {int(row['cluster'])} courses", f"{row['total_courses_mean']:.2f}")

    # --- recommendation --------------------------------------------------
    for method in ("random", "cluster_popularity", "content_based", "hybrid",
                   "global_popularity", "user_user_history"):
        metrics = test[method]["overall"]["10"]
        check(f"{method} NDCG@10", f"{metrics['ndcg']:.4f}")
        check(f"{method} hit rate", f"{metrics['hit_rate']:.4f}")
    check("precision ceiling", f"{test['random']['overall']['10']['precision_ceiling']:.4f}")
    check("n significantly better than random",
          str(rec["significance_vs_random"]["n_methods_significantly_better_than_random"]))
    cp = sig["cluster_popularity"]["vs_random"]
    check("cluster_popularity delta vs random", f"{cp['mean_difference']:.4f}")
    check("engagement proxy deployed", f"{test['cluster_popularity']['engagement_lift_proxy']:.3f}")
    check("engagement proxy random", f"{test['random']['engagement_lift_proxy']:.3f}")

    weights = rec["EXP-024_weight_search"]["best_weights"]
    check("hybrid cluster weight", f"{weights['cluster_popularity']:.3f}")
    check("hybrid rating weight", f"{weights['rating']:.3f}")
    ablation = {a["removed"]: a for a in rec["EXP-024b_ablation"]}
    check("rating ablation delta", f"{ablation['rating']['delta_vs_full']:.4f}".lstrip("-"))

    error = rec["EXP-error_analysis"]
    check("level overlap hit rate", f"{error['level_match']['when_history_level_overlaps_target']:.3f}")
    check("level non-overlap hit rate", f"{error['level_match']['when_it_does_not']:.3f}")
    check("recommended popularity rank", f"{error['popularity_bias']['mean_recommended_popularity_rank']:.1f}")
    check("target popularity rank", f"{error['popularity_bias']['mean_target_popularity_rank']:.1f}")
    check("min candidate pool", str(error["candidate_pool"]["min"]))

    strata = rec["EXP-027_demographic_strata"]
    check("female NDCG", f"{strata['strata']['female']['ndcg']:.4f}")
    check("male NDCG", f"{strata['strata']['male']['ndcg']:.4f}")
    check("gender gap", f"{strata['gender_gap_test']['difference']:.4f}".lstrip("-"))

    # --- architecture ----------------------------------------------------
    for name, label in (("A_cluster_popularity_flat", "A"),
                        ("C_tiered_with_selected_core", "C")):
        metrics = arch["architectures"][name]["overall"]["10"]
        check(f"architecture {label} NDCG", f"{metrics['ndcg']:.4f}")
    check("architecture evaluable learners", str(arch["provenance"]["n_evaluable_learners"]))

    # --- coverage --------------------------------------------------------
    coverage = rec["EXP-009_coverage_accounting"]
    for tier, n in coverage["learners_by_tier"].items():
        check(f"tier {tier} count", f"{n:,}")

    # --- executive summary ------------------------------------------------
    # The summary quotes fewer figures, in rounded plain-language form, so its
    # checks are separate and formatted the way a stakeholder reads them.
    summary_checks: list[tuple[str, str]] = []

    def summary_check(label: str, value: str) -> None:
        summary_checks.append((label, value))

    features = pd.read_parquet(
        config.ARTIFACTS_DIR / "production" / "learner_features.parquet"
    )
    sizes = features["cluster"].value_counts().sort_index()

    summary_check("learners", f"{len(features):,}")
    summary_check("single-course learners", f"{sparsity['n_with_1']:,}")
    summary_check("single-course share", f"{sparsity['pct_with_1']:.0f}%")
    summary_check("popularity range low", str(popularity["min"]))
    summary_check("popularity range high", str(popularity["max"]))
    for cluster, n in sizes.items():
        summary_check(f"deployed segment {cluster} size", f"{n:,}")
    heavy = sparsity["cohort_heavy_9_plus"]
    summary_check("heavy cohort share of enrollments",
                  f"{heavy['n_interactions'] / 10_000 * 100:.0f}%")
    summary_check("evaluable learners", str(split["n_evaluable_learners"]))
    for label, method in (("deployed", "cluster_popularity"), ("random", "random"),
                          ("popularity", "global_popularity")):
        rate = test[method]["overall"]["10"]["hit_rate"]
        summary_check(f"{label} hit rate in plain form", f"{rate * 100:.0f} in 100")
    summary_check("engagement proxy deployed",
                  f"{test['cluster_popularity']['engagement_lift_proxy']:.3f}")
    summary_check("engagement proxy random", f"{test['random']['engagement_lift_proxy']:.3f}")
    reach = round(test["global_popularity"]["overall"]["10"]["coverage"] * 60)
    summary_check("popularity catalogue reach", f"{reach} of the 60")
    summary_check("female ranking quality", f"{strata['strata']['female']['ndcg']:.3f}")
    summary_check("male ranking quality", f"{strata['strata']['male']['ndcg']:.3f}")

    # --- report ----------------------------------------------------------
    print(f"Checking {len(checks)} numeric claims in {PAPER.name} against the artifacts\n")
    missing = [(label, value) for label, value in checks if value not in text]
    for label, value in checks:
        if value in text:
            continue
        print(f"  [MISSING] {label}: artifact says {value!r}, not found in the paper")
    print()
    normalise = str.maketrans({"−": "-", "–": "-", " ": "", " ": " "})
    summary_text = (
        SUMMARY.read_text(encoding="utf-8").translate(normalise) if SUMMARY.exists() else ""
    )
    summary_missing = [(l, v) for l, v in summary_checks if v not in summary_text]

    print(f"Checking {len(summary_checks)} numeric claims in {SUMMARY.name}")
    for label, value in summary_missing:
        print(f"  [MISSING] {label}: artifact says {value!r}, not found in the summary")
    print()

    if missing or summary_missing:
        if missing:
            print(f"FAILED: {len(missing)} of {len(checks)} values missing from the paper")
        if summary_missing:
            print(f"FAILED: {len(summary_missing)} of {len(summary_checks)} values "
                  "missing from the executive summary")
        return 1
    print(f"All {len(checks)} paper values and {len(summary_checks)} summary values "
          "appear verbatim in their documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
