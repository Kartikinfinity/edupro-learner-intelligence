"""Phase 3A — controlled learner segmentation experiments.

Runs the segmentation programme registered in ``research/experiment_plan.md`` and
writes machine-readable results to ``artifacts/segmentation/``. Every number in
``research/segmentation_results.md`` comes from here.

Leakage discipline
    Experiments are run on the **fit window** — every interaction before the
    pre-registered test cut (2025-10-18). The clustering therefore never sees a
    test-window interaction, so the segment assignments can feed the Phase 3B
    recommendation evaluation without leaking (control L4). A full-data
    sensitivity check is run separately to confirm the conclusions do not depend
    on that choice.

Usage
-----
    python scripts/run_segmentation_experiments.py
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
from edupro.evaluation.splits import apply_global_split, global_temporal_split
from edupro.features.learner import build_learner_features
from edupro.segmentation.clustering import (
    DEFAULT_K_RANGE,
    compare_partitions,
    fit_hierarchical,
    fit_kmeans,
    gmm_selection,
    kmeans_sweep,
)
from edupro.segmentation.metrics import block_dominance, gap_statistic
from edupro.segmentation.profiling import (
    category_preference_matrix,
    centroid_deviations,
    compose_segment_names,
    label_clusters,
    profile_clusters,
)
from edupro.segmentation.representations import (
    REPRESENTATION_GRID,
    Representation,
    RepresentationSpec,
    build_representation,
)
from edupro.segmentation.stability import assess_stability

OUT = config.ARTIFACTS_DIR / "segmentation"

#: Minimum share of learners a cluster must hold to count as an actionable
#: segment. Pre-registered in `research/segmentation_research.md` §6.2.
MIN_CLUSTER_SHARE = 0.05

#: The arm every other representation is read against. Not assumed to win.
REFERENCE = "B_proportion"


def behavioural_positions(representation: Representation) -> list[int]:
    """Column positions of the behavioural + engagement blocks.

    Intra-cluster similarity is defined on these blocks only: the metric measures
    *behavioural* consistency, so including demographics would let a
    demographically homogeneous but behaviourally scattered cluster score well.
    """
    wanted = set(representation.blocks.get("behavioural", [])) | set(
        representation.blocks.get("engagement", [])
    )
    return [i for i, column in enumerate(representation.columns) if column in wanted]


def main() -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}

    checksum = verify_raw_workbook()
    data = load_all()
    interactions = build_interactions(data, with_user_demographics=True, with_teacher=True)
    split = global_temporal_split(interactions)
    frames = apply_global_split(interactions, split)
    fit_frame = frames["fit"]

    features = build_learner_features(fit_frame, users=data.users)
    full_features = build_learner_features(interactions, users=data.users)

    results["provenance"] = {
        "workbook_sha256": checksum,
        "seed": config.RANDOM_SEED,
        "window": "fit (all interactions before the pre-registered test cut)",
        "test_cut": str(split.test_date.date()),
        "n_learners_fit_window": int(len(features)),
        "n_learners_full": int(len(full_features)),
        "n_interactions_fit_window": int(len(fit_frame)),
        "k_range": list(DEFAULT_K_RANGE),
    }
    print(f"fit window: {len(features):,} learners, {len(fit_frame):,} interactions")

    # ================================================================ EXP-011a
    # Representation comparison. Each arm is swept over the full k range so the
    # comparison is not contingent on a k chosen for one of them.
    print("\n[EXP-011a] representation comparison ...")
    representations: dict[str, Representation] = {}
    sweeps: dict[str, Any] = {}
    representation_summary = []

    for spec in REPRESENTATION_GRID:
        representation = build_representation(features, spec)
        representations[spec.name] = representation
        positions = behavioural_positions(representation)
        sweep = kmeans_sweep(
            representation.matrix,
            behavioural_positions=positions,
            representation=spec.name,
        )
        sweeps[spec.name] = sweep

        eligible = [r for r in sweep.rows if r.min_cluster_share >= MIN_CLUSTER_SHARE]
        best = max(eligible or sweep.rows, key=lambda r: r.silhouette)
        labels = fit_kmeans(representation.matrix, best.k).labels_
        dominance = block_dominance(
            representation.matrix, labels, representation.columns, representation.blocks
        )
        representation_summary.append({
            **representation.summary(),
            "best_k": best.k,
            "best_silhouette": round(best.silhouette, 6),
            "min_cluster_share_at_best_k": round(best.min_cluster_share, 4),
            "intra_cluster_similarity": round(best.intra_cluster_similarity, 6),
            "seed_stability_ari": round(best.seed_stability_ari, 6),
            "block_explained_share": {
                b: round(v, 4) for b, v in dominance["explained_share_per_block"].items()
            },
            "demographic_share": round(dominance["demographic_share"], 4),
            "top_feature_eta_squared": dominance["top_feature"],
            "top_five_eta_squared": dict(list(dominance["per_feature"].items())[:5]),
        })
        print(f"  {spec.name:<24} d={representation.n_features:<3} best_k={best.k} "
              f"sil={best.silhouette:.4f} demo_share={dominance['demographic_share']:.3f}")

    results["EXP-011a_representations"] = representation_summary

    # Why RobustScaler is unusable here - measured rather than asserted.
    from edupro.segmentation.representations import EXTRA_NUMERIC, MANDATED_NUMERIC

    iqr_diagnostic = {}
    for column in list(MANDATED_NUMERIC) + list(EXTRA_NUMERIC):
        values = features[column].astype(float)
        q25, q75 = values.quantile([0.25, 0.75])
        iqr_diagnostic[column] = {
            "q25": round(float(q25), 4),
            "q75": round(float(q75), 4),
            "iqr": round(float(q75 - q25), 6),
            "degenerate": bool(q75 - q25 < 1e-9),
        }
    results["scaler_diagnostic"] = {
        "features_with_zero_iqr": [c for c, v in iqr_diagnostic.items() if v["degenerate"]],
        "per_feature": iqr_diagnostic,
        "conclusion": (
            "Two mandated features have IQR exactly 0, because 54% of learners have "
            "a single course so their 25th, 50th and 75th percentiles coincide. "
            "RobustScaler leaves those columns unscaled while compressing the "
            "others, producing an artificially separable axis and an inflated "
            "silhouette. StandardScaler is therefore the correct choice here - "
            "settling the deferred D5 decision on evidence."
        ),
    }
    results["sweeps"] = {name: sweep.to_records() for name, sweep in sweeps.items()}

    reference = representations[REFERENCE]
    reference_sweep = sweeps[REFERENCE]
    positions = behavioural_positions(reference)

    # ================================================================= EXP-010
    print("\n[EXP-010] k-selection criteria on the reference representation ...")
    results["EXP-010_k_sweep"] = reference_sweep.to_records()

    # ================================================================ EXP-010b
    print("[EXP-010b] gap statistic (k=1..20, 50 uniform references) ...")
    # The range deliberately extends past the interpretability ceiling: if the gap
    # curve never turns over, that is itself the finding, and a range stopping at
    # 10 would hide it behind an apparent "optimum at the boundary".
    gap = gap_statistic(reference.matrix, k_values=range(1, 21), n_references=50)
    monotone = all(b >= a for a, b in zip(gap.gap, gap.gap[1:]))
    results["EXP-010b_gap_statistic"] = {
        "k_values": gap.k_values,
        "gap": [round(g, 6) for g in gap.gap],
        "std_error": [round(s, 6) for s in gap.std_error],
        "optimal_k": gap.optimal_k,
        "indicates_no_structure": gap.indicates_no_structure,
        "monotonically_increasing": bool(monotone),
        "informative": bool(not monotone),
        "note": (
            "k=1 was in the search range on purpose: the gap statistic is the only "
            "criterion here that can report the ABSENCE of cluster structure. If "
            "the curve rises monotonically to the range ceiling it has found no "
            "interior optimum, and the statistic is uninformative on this data "
            "rather than endorsing the largest k."
        ),
    }
    print(f"  gap-optimal k = {gap.optimal_k}  monotone = {monotone}  "
          f"(informative: {not monotone})")

    # ================================================================ EXP-010c
    print("[EXP-010c] GMM/BIC cross-check ...")
    gmm = gmm_selection(reference.matrix)
    best_bic = min(gmm, key=lambda r: r["bic"])
    results["EXP-010c_gmm"] = {"sweep": gmm, "bic_optimal_k": best_bic["k"]}
    print(f"  BIC-optimal k = {best_bic['k']}")

    # --------------------------------------------------------------- choose k
    # The pre-registered rule has TWO constraints and stability is one of them.
    # It is evaluated for every candidate k here rather than measured afterwards,
    # because a constraint applied after the choice is not a constraint.
    print("\n[EXP-013] stability for every candidate k (60 bootstrap resamples each) ...")
    stability_by_k: dict[int, Any] = {}
    for row in reference_sweep.rows:
        assessment = assess_stability(
            reference.matrix, row.k, n_bootstrap=60, n_subsample_pairs=15
        )
        stability_by_k[row.k] = assessment
        print(f"  k={row.k:>2} sil={row.silhouette:.4f} minshare={row.min_cluster_share:.3f} "
              f"meanJ={assessment.mean_jaccard:.3f} unstable={assessment.n_unstable} "
              f"J={[round(v, 2) for v in assessment.per_cluster_jaccard.values()]}")

    def passes(row) -> tuple[bool, list[str]]:
        reasons = []
        if row.min_cluster_share < MIN_CLUSTER_SHARE:
            reasons.append(f"smallest cluster {row.min_cluster_share:.1%} < 5%")
        if stability_by_k[row.k].n_unstable > 0:
            reasons.append(f"{stability_by_k[row.k].n_unstable} cluster(s) below Jaccard 0.60")
        return (not reasons), reasons

    candidate_table = []
    for row in reference_sweep.rows:
        ok, reasons = passes(row)
        candidate_table.append({
            "k": row.k,
            "silhouette": round(row.silhouette, 6),
            "min_cluster_share": round(row.min_cluster_share, 4),
            "mean_bootstrap_jaccard": round(stability_by_k[row.k].mean_jaccard, 4),
            "n_unstable_clusters": stability_by_k[row.k].n_unstable,
            "passes_constraints": ok,
            "failure_reasons": reasons,
        })

    eligible = [row for row in reference_sweep.rows if passes(row)[0]]
    if eligible:
        chosen = max(eligible, key=lambda r: r.silhouette)
        fallback_used = False
    else:
        chosen = min(reference_sweep.rows, key=lambda r: stability_by_k[r.k].n_unstable)
        fallback_used = True
    chosen_k = chosen.k

    results["k_selection"] = {
        "rule": (
            "Gap statistic first (if k=1, report no structure). Otherwise the k "
            "maximising mean silhouette subject to BOTH constraints: every cluster "
            "holds >=5% of learners AND every cluster reaches bootstrap Jaccard "
            ">=0.60. Pre-registered in research/segmentation_research.md section 6.2."
        ),
        "gap_optimal_k": gap.optimal_k,
        "gap_informative": bool(not monotone),
        "silhouette_optimal_k_unconstrained": reference_sweep.best_by_silhouette().k,
        "candidates": candidate_table,
        "eligible_k": [row.k for row in eligible],
        "chosen_k": chosen_k,
        "fallback_used": fallback_used,
    }
    print(f"\n  eligible k (both constraints): {[r.k for r in eligible]}")
    print(f"  chosen k = {chosen_k}" + ("  (fallback)" if fallback_used else ""))

    # ================================================================= EXP-012
    print("\n[EXP-012] hierarchical validation ...")
    kmeans_labels = fit_kmeans(reference.matrix, chosen_k).labels_
    ward_labels = fit_hierarchical(reference.matrix, chosen_k, method="ward")
    average_labels = fit_hierarchical(reference.matrix, chosen_k, method="average")
    results["EXP-012_hierarchical"] = {
        "k": chosen_k,
        "ari_kmeans_vs_ward": round(compare_partitions(kmeans_labels, ward_labels), 6),
        "ari_kmeans_vs_average": round(compare_partitions(kmeans_labels, average_labels), 6),
        "ari_ward_vs_average": round(compare_partitions(ward_labels, average_labels), 6),
        "ward_sizes": {int(k): int(v) for k, v in zip(*np.unique(ward_labels, return_counts=True))},
        "average_sizes": {
            int(k): int(v) for k, v in zip(*np.unique(average_labels, return_counts=True))
        },
        "caveat": (
            "Ward minimises within-cluster variance, the same objective family "
            "K-Means optimises, so Ward-K-Means agreement is partly a shared "
            "inductive bias. Average linkage optimises something different, so "
            "agreement across all three is materially stronger evidence."
        ),
    }
    print(f"  ARI K-Means vs Ward    = {results['EXP-012_hierarchical']['ari_kmeans_vs_ward']:.4f}")
    print(f"  ARI K-Means vs Average = {results['EXP-012_hierarchical']['ari_kmeans_vs_average']:.4f}")

    # ================================================================= EXP-013
    print("\n[EXP-013] confirming stability at the chosen k (100 resamples) ...")
    stability = assess_stability(reference.matrix, chosen_k, n_bootstrap=100, n_subsample_pairs=30)
    results["EXP-013_stability"] = stability.to_dict()
    results["EXP-013_stability_by_k"] = {
        k: assessment.to_dict() for k, assessment in stability_by_k.items()
    }
    print(f"  per-cluster Jaccard: {stability.to_dict()['per_cluster_jaccard']}")
    print(f"  subsample ARI = {stability.subsample_ari_mean:.4f}")

    # ================================================================ EXP-011c
    print("\n[EXP-011c] feature dominance (eta-squared) ...")
    dominance = block_dominance(
        reference.matrix, kmeans_labels, reference.columns, reference.blocks
    )
    results["EXP-011c_dominance"] = {
        "representation": REFERENCE,
        "k": chosen_k,
        "mean_eta_squared_per_block": {b: round(v, 4) for b, v in dominance["mean_per_block"].items()},
        "explained_share_per_block": {
            b: round(v, 4) for b, v in dominance["explained_share_per_block"].items()
        },
        "top_15_features": dict(list(dominance["per_feature"].items())[:15]),
    }

    # Block dominance at a COMMON k. The per-arm table above reports each arm at
    # its own best k, which is the right basis for judging an arm but the wrong
    # basis for comparing encodings: a difference there could be a difference in k.
    print("[EXP-011c] block dominance at the common selected k ...")
    common = {}
    for name, representation in representations.items():
        labels = fit_kmeans(representation.matrix, chosen_k).labels_
        dom = block_dominance(
            representation.matrix, labels, representation.columns, representation.blocks
        )
        row = next(r for r in sweeps[name].rows if r.k == chosen_k)
        common[name] = {
            "k": chosen_k,
            "silhouette": round(row.silhouette, 6),
            "min_cluster_share": round(row.min_cluster_share, 4),
            "block_explained_share": {
                b: round(v, 4) for b, v in dom["explained_share_per_block"].items()
            },
            "top_feature": dom["top_feature"],
        }
    results["EXP-011c_dominance_at_common_k"] = common
    for name, row in common.items():
        cat = row["block_explained_share"].get("category", 0.0)
        lvl = row["block_explained_share"].get("level", 0.0)
        print(f"  {name:<24} category={cat:.4f} level={lvl:.4f} top={row['top_feature']}")

    # ================================================================= EXP-011
    print("\n[EXP-011] Variant A vs Variant B ...")
    variant_rows = []
    for name in ("B_proportion", "A_proportion"):
        representation = representations[name]
        sweep = sweeps[name]
        row = next(r for r in sweep.rows if r.k == chosen_k)
        labels = fit_kmeans(representation.matrix, chosen_k).labels_
        dom = block_dominance(
            representation.matrix, labels, representation.columns, representation.blocks
        )
        stab = assess_stability(representation.matrix, chosen_k, n_bootstrap=40, n_subsample_pairs=15)
        variant_rows.append({
            "representation": name,
            "variant": representation.spec.variant(),
            "n_features": representation.n_features,
            "silhouette": round(row.silhouette, 6),
            "intra_cluster_similarity": round(row.intra_cluster_similarity, 6),
            "min_cluster_share": round(row.min_cluster_share, 4),
            "seed_stability_ari": round(row.seed_stability_ari, 6),
            "mean_bootstrap_jaccard": round(stab.mean_jaccard, 4),
            "n_unstable_clusters": stab.n_unstable,
            "demographic_share": round(dom["demographic_share"], 4),
            "top_feature": dom["top_feature"],
        })
    ari_variants = compare_partitions(
        fit_kmeans(representations["B_proportion"].matrix, chosen_k).labels_,
        fit_kmeans(representations["A_proportion"].matrix, chosen_k).labels_,
    )
    results["EXP-011_variants"] = {
        "k": chosen_k,
        "arms": variant_rows,
        "ari_between_variants": round(ari_variants, 6),
        "decision_rule": (
            "Reject Variant A if the demographic block explains more than 40% of "
            "between-cluster variance. Otherwise prefer Variant B on ties, since "
            "it is simpler, more privacy-respecting and more actionable. The "
            "downstream recommendation check (EXP-023) can still overturn this in "
            "Phase 3B."
        ),
    }

    # ================================================================= EXP-014
    print("[EXP-014] teacher-signal arm ...")
    teacher_rows = []
    for name in ("B_proportion", "B_teacher"):
        representation = representations[name]
        row = next(r for r in sweeps[name].rows if r.k == chosen_k)
        labels = fit_kmeans(representation.matrix, chosen_k).labels_
        dom = block_dominance(
            representation.matrix, labels, representation.columns, representation.blocks
        )
        stab = assess_stability(representation.matrix, chosen_k, n_bootstrap=40, n_subsample_pairs=15)
        teacher_rows.append({
            "representation": name,
            "n_features": representation.n_features,
            "silhouette": round(row.silhouette, 6),
            "intra_cluster_similarity": round(row.intra_cluster_similarity, 6),
            "min_cluster_share": round(row.min_cluster_share, 4),
            "mean_bootstrap_jaccard": round(stab.mean_jaccard, 4),
            "teacher_block_share": round(dom["explained_share_per_block"].get("teacher", 0.0), 4),
            "top_feature": dom["top_feature"],
        })
    ari_teacher = compare_partitions(
        fit_kmeans(representations["B_proportion"].matrix, chosen_k).labels_,
        fit_kmeans(representations["B_teacher"].matrix, chosen_k).labels_,
    )
    results["EXP-014_teacher"] = {
        "k": chosen_k,
        "arms": teacher_rows,
        "ari_core_vs_teacher": round(ari_teacher, 6),
        "decision_rule": (
            "Retain teacher features only on defensible evidence of improvement "
            "(CLAUDE.md §11). Teacher Age and Gender are excluded before "
            "experimentation (D-016)."
        ),
    }

    # =========================================================== EXP-011g
    # Added after the first run: the k=4 partition turned out to be almost purely
    # a split by course level, so this arm removes preferred_level entirely and
    # asks what, if anything, survives. Recorded as a post-hoc addition rather
    # than presented as though it had been planned.
    print("[EXP-011g] level-ablation: what survives without preferred_level? ...")
    level_rows = []
    for name in ("B_proportion", "B_no_level"):
        representation = representations[name]
        sweep = sweeps[name]
        row = next(r for r in sweep.rows if r.k == chosen_k)
        labels = fit_kmeans(representation.matrix, chosen_k).labels_
        stab = assess_stability(representation.matrix, chosen_k, n_bootstrap=40, n_subsample_pairs=15)
        dom = block_dominance(
            representation.matrix, labels, representation.columns, representation.blocks
        )
        level_rows.append({
            "representation": name,
            "n_features": representation.n_features,
            "silhouette": round(row.silhouette, 6),
            "intra_cluster_similarity": round(row.intra_cluster_similarity, 6),
            "min_cluster_share": round(row.min_cluster_share, 4),
            "mean_bootstrap_jaccard": round(stab.mean_jaccard, 4),
            "n_unstable_clusters": stab.n_unstable,
            "block_explained_share": {
                b: round(v, 4) for b, v in dom["explained_share_per_block"].items()
            },
            "top_feature": dom["top_feature"],
        })
    ari_level = compare_partitions(
        fit_kmeans(representations["B_proportion"].matrix, chosen_k).labels_,
        fit_kmeans(representations["B_no_level"].matrix, chosen_k).labels_,
    )
    no_level_labels = fit_kmeans(representations["B_no_level"].matrix, chosen_k).labels_
    no_level_profiles = profile_clusters(features, no_level_labels)
    results["EXP-011g_level_ablation"] = {
        "k": chosen_k,
        "arms": level_rows,
        "ari_with_vs_without_level": round(ari_level, 6),
        "no_level_profiles": json.loads(no_level_profiles.to_json(orient="index")),
        "question": (
            "The reference partition splits learners almost perfectly by course "
            "level. Does any structure remain once preferred_level is removed?"
        ),
    }
    no_level_profiles.to_csv(OUT / "cluster_profiles_no_level.csv")
    print(f"  ARI with vs without level = {ari_level:.4f}")
    for row in level_rows:
        print(f"  {row['representation']:<16} sil={row['silhouette']:.4f} "
              f"meanJ={row['mean_bootstrap_jaccard']:.3f} unstable={row['n_unstable_clusters']} "
              f"top={row['top_feature']}")

    # ============================================================ EXP-011f/d/e
    print("\n[EXP-011f] does history length dominate? ...")
    volume = features["total_courses"].to_numpy(dtype=float)
    volume_eta = block_dominance(
        volume.reshape(-1, 1), kmeans_labels, ["total_courses"], {"volume": ["total_courses"]}
    )["per_feature"]["total_courses"]
    cohort = (features["total_courses"] >= 9).astype(int).to_numpy()
    results["EXP-011f_volume_dominance"] = {
        "eta_squared_total_courses": round(float(volume_eta), 6),
        "ari_clusters_vs_light_heavy_cohort": round(compare_partitions(kmeans_labels, cohort), 6),
        "note": (
            "ARI against the light/heavy cohort split measures how much of the "
            "segmentation is simply the Phase 2 activity-volume bimodality."
        ),
    }
    print(f"  eta^2(total_courses) = {volume_eta:.4f}  "
          f"ARI vs cohort split = {results['EXP-011f_volume_dominance']['ari_clusters_vs_light_heavy_cohort']:.4f}")

    # ============================================================== profiling
    print("\n[EXP-005 profiling] cluster profiles and evidence-derived labels ...")
    profiles = profile_clusters(features, kmeans_labels)
    deviations = centroid_deviations(features, kmeans_labels)
    naming_features = {
        c for c in reference.columns
        if not c.startswith(("cat_share_", "prefcat_", "preflevel_"))
    }
    labels_derived = label_clusters(features, kmeans_labels, allowed_features=naming_features)
    category_matrix = category_preference_matrix(features, kmeans_labels)

    results["cluster_profiles"] = json.loads(profiles.to_json(orient="index"))
    results["centroid_deviations"] = json.loads(deviations.to_json(orient="index"))
    results["derived_labels"] = labels_derived
    results["category_preference_matrix"] = json.loads(category_matrix.to_json(orient="index"))

    profiles.to_csv(OUT / "cluster_profiles.csv")
    deviations.to_csv(OUT / "centroid_deviations.csv")
    category_matrix.to_csv(OUT / "category_preference_matrix.csv")
    pd.DataFrame(
        {"UserID": features.index, "cluster": kmeans_labels}
    ).to_csv(OUT / "cluster_assignments_fit_window.csv", index=False)

    level_composition = (
        pd.crosstab(kmeans_labels, features["preferred_level"], normalize="index")
        .round(4)
    )
    level_composition.index.name = "cluster"
    results["cluster_level_composition"] = json.loads(level_composition.to_json(orient="index"))
    level_composition.to_csv(OUT / "cluster_level_composition.csv")
    results["level_purity"] = {
        int(c): round(float(level_composition.loc[c].max()), 4) for c in level_composition.index
    }

    # Deviation-based naming is blind to a cluster sitting at the middle of an
    # ordinal scale, so level purity is folded in before the labels are finalised.
    labels_derived = compose_segment_names(labels_derived, level_composition)
    results["derived_labels"] = labels_derived

    for cluster, info in labels_derived.items():
        purity = results["level_purity"].get(int(cluster), float("nan"))
        print(f"  cluster {cluster}: {info['label']}  (level purity {purity:.0%})")

    # ================================================== full-data sensitivity
    print("\n[sensitivity] repeating the selection on the full interaction history ...")
    full_rep = build_representation(
        full_features, next(s for s in REPRESENTATION_GRID if s.name == REFERENCE)
    )
    full_sweep = kmeans_sweep(
        full_rep.matrix,
        behavioural_positions=behavioural_positions(full_rep),
        representation=f"{REFERENCE}_full",
    )
    full_eligible = [r for r in full_sweep.rows if r.min_cluster_share >= MIN_CLUSTER_SHARE]
    full_best = max(full_eligible or full_sweep.rows, key=lambda r: r.silhouette)
    full_labels = fit_kmeans(full_rep.matrix, chosen_k).labels_
    shared = features.index.intersection(full_features.index)
    fit_series = pd.Series(kmeans_labels, index=features.index).loc[shared]
    full_series = pd.Series(full_labels, index=full_features.index).loc[shared]
    results["sensitivity_full_history"] = {
        "n_learners": int(len(full_features)),
        "best_k": full_best.k,
        "best_silhouette": round(full_best.silhouette, 6),
        "silhouette_at_chosen_k": round(
            next(r for r in full_sweep.rows if r.k == chosen_k).silhouette, 6
        ),
        "ari_fit_window_vs_full": round(compare_partitions(fit_series.to_numpy(), full_series.to_numpy()), 6),
        "sweep": full_sweep.to_records(),
    }
    print(f"  full-history best k = {full_best.k}, ARI vs fit-window labels = "
          f"{results['sensitivity_full_history']['ari_fit_window_vs_full']:.4f}")

    destination = OUT / "segmentation_results.json"
    destination.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nWritten to {destination.relative_to(config.PROJECT_ROOT)} "
          f"({time.time() - started:.0f}s)")


if __name__ == "__main__":
    main()
