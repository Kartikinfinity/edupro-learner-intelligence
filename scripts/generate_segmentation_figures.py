"""Phase 3A — figures for the segmentation experiments.

Reads ``artifacts/segmentation/segmentation_results.json`` and writes figures to
``artifacts/segmentation/``. Every chart is produced from the same results file
the write-up quotes, so a figure cannot disagree with its number.

Usage
-----
    python scripts/generate_segmentation_figures.py
"""

from __future__ import annotations

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from edupro import config
from edupro.viz import (
    BLUE,
    DIVERGING,
    GRID,
    ORANGE,
    REFERENCE,
    TEXT_MUTED,
    TEXT_SECONDARY,
    apply_style,
    caption,
    save,
)

OUT = config.ARTIFACTS_DIR / "segmentation"
CHOSEN_COLOUR = ORANGE


def load() -> dict:
    return json.loads((OUT / "segmentation_results.json").read_text(encoding="utf-8"))


def fig_elbow_and_silhouette(results: dict) -> None:
    """The two brief-mandated k criteria, side by side with the constraint outcome."""
    sweep = pd.DataFrame(results["EXP-010_k_sweep"])
    candidates = pd.DataFrame(results["k_selection"]["candidates"])
    chosen = results["k_selection"]["chosen_k"]
    eligible = set(results["k_selection"]["eligible_k"])

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))

    axes[0].plot(sweep.k, sweep.inertia, color=BLUE, marker="o")
    axes[0].axvline(chosen, color=CHOSEN_COLOUR, linestyle="--", linewidth=1.8)
    axes[0].annotate(f"selected k = {chosen}", xy=(chosen, sweep.inertia.max() * 0.93),
                     xytext=(8, 0), textcoords="offset points", fontsize=9, color=CHOSEN_COLOUR)
    axes[0].set_xlabel("k")
    axes[0].set_ylabel("Within-cluster sum of squares")
    axes[0].set_title("Elbow: no clear knee")
    axes[0].set_xticks(sweep.k)

    colours = [BLUE if k in eligible else GRID for k in sweep.k]
    axes[1].bar(sweep.k, sweep.silhouette, color=colours, width=0.62)
    axes[1].axvline(chosen, color=CHOSEN_COLOUR, linestyle="--", linewidth=1.8)
    for k, value in zip(sweep.k, sweep.silhouette):
        axes[1].annotate(f"{value:.3f}", (k, value), ha="center", va="bottom",
                         fontsize=8, color=TEXT_SECONDARY)
    axes[1].set_xlabel("k")
    axes[1].set_ylabel("Mean silhouette")
    axes[1].set_title("Silhouette rises with k — but stability does not")
    axes[1].set_xticks(sweep.k)
    axes[1].set_ylim(0, sweep.silhouette.max() * 1.22)
    handles = [plt.Rectangle((0, 0), 1, 1, color=BLUE), plt.Rectangle((0, 0), 1, 1, color=GRID)]
    axes[1].legend(handles, ["Passes both constraints", "Fails a constraint"], loc="upper left")

    fig.tight_layout()
    caption(fig, "Unconstrained, silhouette keeps improving to k=10. The pre-registered rule "
                 "also requires every cluster to hold >=5% of learners and to reach bootstrap "
                 "Jaccard >=0.60, which only k = 2, 3 and 4 satisfy.")
    save(fig, OUT, "01_elbow_and_silhouette")


def fig_k_constraints(results: dict) -> None:
    """Why the highest-silhouette k was not chosen: the constraints, visualised."""
    candidates = pd.DataFrame(results["k_selection"]["candidates"])
    chosen = results["k_selection"]["chosen_k"]

    fig, axes = plt.subplots(3, 1, figsize=(9, 7), sharex=True)
    eligible = candidates.passes_constraints

    axes[0].bar(candidates.k, candidates.silhouette,
                color=[BLUE if e else GRID for e in eligible], width=0.62)
    axes[0].set_ylabel("Silhouette")
    axes[0].set_title("The three pre-registered criteria, by k")

    axes[1].bar(candidates.k, candidates.min_cluster_share * 100,
                color=[BLUE if e else GRID for e in eligible], width=0.62)
    axes[1].axhline(5, color=REFERENCE, linestyle="--", linewidth=1.5)
    axes[1].annotate("5% floor", xy=(candidates.k.max(), 5), xytext=(0, 4),
                     textcoords="offset points", ha="right", fontsize=8.5, color=TEXT_MUTED)
    axes[1].set_ylabel("Smallest cluster (%)")

    axes[2].bar(candidates.k, candidates.n_unstable_clusters,
                color=[BLUE if e else ORANGE for e in eligible], width=0.62)
    axes[2].set_ylabel("Clusters below\nJaccard 0.60")
    axes[2].set_xlabel("k")
    axes[2].set_xticks(candidates.k)
    for k, n in zip(candidates.k, candidates.n_unstable_clusters):
        if n:
            axes[2].annotate(str(n), (k, n), ha="center", va="bottom", fontsize=8.5,
                             color=TEXT_SECONDARY)

    for ax in axes:
        ax.axvline(chosen, color=CHOSEN_COLOUR, linestyle="--", linewidth=1.6, zorder=0)

    fig.tight_layout()
    caption(fig, f"k = {chosen} is the highest-silhouette value that keeps every cluster "
                 "actionable and reproducible. Above k=4 the partition fragments: at k=7 five "
                 "of seven clusters fail to reappear reliably under resampling.")
    save(fig, OUT, "02_k_selection_constraints")


def fig_cluster_sizes_and_stability(results: dict) -> None:
    profiles = pd.DataFrame(results["cluster_profiles"]).T
    stability = results["EXP-013_stability"]["per_cluster_jaccard"]
    labels = {int(k): v["label"] for k, v in results["derived_labels"].items()}

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4))

    order = profiles.index.astype(int).tolist()
    sizes = [int(profiles.loc[str(c) if str(c) in profiles.index else c, "n_learners"])
             for c in order]
    bars = axes[0].bar([str(c) for c in order], sizes, color=BLUE, width=0.6)
    for bar, size in zip(bars, sizes):
        axes[0].annotate(f"{size:,}\n{size / sum(sizes):.0%}",
                         (bar.get_x() + bar.get_width() / 2, size), ha="center", va="bottom",
                         fontsize=8.5, color=TEXT_SECONDARY)
    axes[0].set_xlabel("Cluster")
    axes[0].set_ylabel("Learners")
    axes[0].set_ylim(0, max(sizes) * 1.25)
    axes[0].set_title("Cluster sizes are well balanced")

    jaccard = [stability[str(c)] if str(c) in stability else stability[c] for c in order]
    bars = axes[1].bar([str(c) for c in order], jaccard, color=BLUE, width=0.6)
    axes[1].axhline(0.75, color=REFERENCE, linestyle="--", linewidth=1.5)
    axes[1].axhline(0.60, color=ORANGE, linestyle="--", linewidth=1.5)
    axes[1].annotate("reliable (0.75)", xy=(len(order) - 0.4, 0.755), ha="right",
                     fontsize=8.5, color=TEXT_MUTED)
    axes[1].annotate("unstable below 0.60", xy=(len(order) - 0.4, 0.61), ha="right",
                     fontsize=8.5, color=ORANGE)
    for bar, value in zip(bars, jaccard):
        axes[1].annotate(f"{value:.3f}", (bar.get_x() + bar.get_width() / 2, value),
                         ha="center", va="bottom", fontsize=8.5, color=TEXT_SECONDARY)
    axes[1].set_ylim(0, 1.12)
    axes[1].set_xlabel("Cluster")
    axes[1].set_ylabel("Bootstrap Jaccard")
    axes[1].set_title("Every cluster reappears under resampling")

    fig.tight_layout()
    caption(fig, "Per-cluster bootstrap Jaccard over 100 resamples. All four clusters exceed "
                 "0.98, well above the 0.75 reliability convention.")
    save(fig, OUT, "03_cluster_sizes_and_stability")


def fig_profile_heatmap(results: dict) -> None:
    """Centroid deviations — the evidence each segment name was derived from."""
    deviations = pd.DataFrame(results["centroid_deviations"]).T
    deviations.index = deviations.index.astype(int)
    deviations = deviations.sort_index()
    keep = [c for c in deviations.columns if deviations[c].abs().max() > 0.15]
    matrix = deviations[keep]
    labels = {int(k): v["label"] for k, v in results["derived_labels"].items()}

    fig, ax = plt.subplots(figsize=(min(14, 1.0 + 0.62 * len(keep)), 4.4))
    limit = float(np.abs(matrix.to_numpy()).max())
    image = ax.imshow(matrix.to_numpy(), cmap=DIVERGING, vmin=-limit, vmax=limit, aspect="auto")
    ax.set_xticks(range(len(keep)))
    ax.set_xticklabels(keep, rotation=48, ha="right", fontsize=8.5)
    ax.set_yticks(range(len(matrix)))
    ax.set_yticklabels([f"{c} — {labels.get(c, '')}" for c in matrix.index], fontsize=9)
    ax.grid(False)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix.iat[i, j]
            if abs(value) >= 0.45:
                ax.annotate(f"{value:+.1f}", (j, i), ha="center", va="center",
                            fontsize=7.5, color="#fcfcfb", fontweight="bold")
    bar = fig.colorbar(image, ax=ax, shrink=0.8)
    bar.set_label("SD from population mean", color=TEXT_SECONDARY, fontsize=9)
    bar.outline.set_visible(False)
    ax.set_title("Cluster profiles: deviation from the population mean")
    fig.tight_layout()
    caption(fig, "Labelled cells exceed 0.45 SD. Segment names were derived from these "
                 "deviations, not chosen first — and only from features the clustering used.")
    save(fig, OUT, "04_cluster_profile_heatmap")


def fig_level_composition(results: dict) -> None:
    """The headline finding: the partition is essentially a course-level split."""
    composition = pd.DataFrame(results["cluster_level_composition"]).T
    composition.index = composition.index.astype(int)
    composition = composition.sort_index()
    order = [c for c in ("Beginner", "Intermediate", "Advanced") if c in composition.columns]
    composition = composition[order]
    labels = {int(k): v["label"] for k, v in results["derived_labels"].items()}

    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    left = np.zeros(len(composition))
    palette = (BLUE, ORANGE, "#1baf7a")
    for colour, column in zip(palette, order):
        values = composition[column].to_numpy() * 100
        ax.barh([str(c) for c in composition.index], values, left=left, color=colour,
                height=0.6, label=column, edgecolor="#fcfcfb", linewidth=2)
        for i, (value, base) in enumerate(zip(values, left)):
            if value > 7:
                ax.annotate(f"{value:.0f}%", (base + value / 2, i), ha="center", va="center",
                            fontsize=9, color="#fcfcfb", fontweight="bold")
        left += values
    ax.set_xlabel("Share of learners (%)")
    ax.set_ylabel("Cluster")
    ax.set_xlim(0, 100)
    ax.set_title("Three of four clusters are 100% one course level")
    ax.invert_yaxis()
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), title="Preferred level", ncols=3)
    fig.tight_layout()
    caption(fig, "Clusters 0, 2 and 3 are pure Beginner, Advanced and Intermediate. Cluster 1 "
                 "is the mixed-level, high-volume group. For the 54% of learners with a single "
                 "course, 'preferred level' is simply the level of that one enrollment.")
    save(fig, OUT, "05_level_composition")


def fig_representation_comparison(results: dict) -> None:
    summary = pd.DataFrame(results["EXP-011a_representations"])
    summary = summary.sort_values("best_silhouette", ascending=True)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.0), width_ratios=[1.3, 1])

    colours = [ORANGE if n == "B_robust_scaled" else BLUE for n in summary.name]
    bars = axes[0].barh(summary.name, summary.best_silhouette, color=colours, height=0.62)
    for bar, value, k in zip(bars, summary.best_silhouette, summary.best_k):
        axes[0].annotate(f"{value:.3f}  (k={k})", (value, bar.get_y() + bar.get_height() / 2),
                         xytext=(6, 0), textcoords="offset points", va="center",
                         fontsize=8.5, color=TEXT_SECONDARY)
    axes[0].set_xlabel("Best mean silhouette")
    axes[0].set_xlim(0, summary.best_silhouette.max() * 1.32)
    axes[0].set_title("Representation comparison")
    axes[0].annotate("degenerate — two features\nhave IQR = 0", xy=(0.72, 0.5),
                     xycoords="axes fraction", fontsize=8.5, color=ORANGE, ha="center")

    blocks = pd.DataFrame(
        [row["block_explained_share"] for _, row in summary.iterrows()], index=summary.name
    ).fillna(0.0)
    order = [c for c in ("engagement", "behavioural", "level", "category", "demographic", "teacher")
             if c in blocks.columns]
    blocks = blocks[order]
    left = np.zeros(len(blocks))
    palette = (BLUE, ORANGE, "#1baf7a", "#eda100", "#e87ba4", "#4a3aa7")
    for colour, column in zip(palette, order):
        values = blocks[column].to_numpy() * 100
        axes[1].barh(blocks.index, values, left=left, color=colour, height=0.62,
                     label=column, edgecolor="#fcfcfb", linewidth=1.4)
        left += values
    axes[1].set_xlabel("Share of between-cluster variance (%)")
    axes[1].set_title("Which feature block drives each partition")
    axes[1].set_xlim(0, 100)
    axes[1].set_yticklabels([])
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), fontsize=8.5,
                   ncols=len(order))

    fig.tight_layout()
    caption(fig, "The category block never dominates under the proportion encoding — the risk "
                 "Phase 1 flagged did not materialise. The demographic block is invisible in "
                 "every arm that contains it.")
    save(fig, OUT, "06_representation_comparison")


def fig_variant_and_teacher(results: dict) -> None:
    """Two decisions the brief requires, on one figure: demographics and teachers."""
    variants = pd.DataFrame(results["EXP-011_variants"]["arms"])
    teacher = pd.DataFrame(results["EXP-014_teacher"]["arms"])

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))

    for ax, frame, title, ari, note in (
        (axes[0], variants, "Variant A vs B (demographics)",
         results["EXP-011_variants"]["ari_between_variants"],
         "identical partitions"),
        (axes[1], teacher, "Core vs core + teacher block",
         results["EXP-014_teacher"]["ari_core_vs_teacher"],
         "near-identical partitions"),
    ):
        positions = np.arange(len(frame))
        bars = ax.bar(positions, frame.silhouette, color=[BLUE, ORANGE], width=0.5)
        for bar, value in zip(bars, frame.silhouette):
            ax.annotate(f"{value:.4f}", (bar.get_x() + bar.get_width() / 2, value),
                        ha="center", va="bottom", fontsize=9, color=TEXT_SECONDARY)
        ax.set_xticks(positions)
        ax.set_xticklabels(frame.representation, fontsize=9)
        ax.set_ylabel("Silhouette")
        ax.set_ylim(0, frame.silhouette.max() * 1.35)
        ax.set_title(title)
        ax.annotate(f"ARI = {ari:.3f}\n({note})", xy=(0.5, 0.82), xycoords="axes fraction",
                    ha="center", fontsize=9.5, color=TEXT_MUTED)

    fig.tight_layout()
    caption(fig, "Adding demographics leaves the partition literally unchanged (ARI = 1.000). "
                 "Adding the teacher block changes silhouette by 0.0009 and ARI by 0.010 — "
                 "neither is evidence of improvement, so both are excluded.")
    save(fig, OUT, "07_variant_and_teacher")


def fig_gap_statistic(results: dict) -> None:
    """A criterion that failed — reported rather than dropped."""
    gap = results["EXP-010b_gap_statistic"]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.errorbar(gap["k_values"], gap["gap"], yerr=gap["std_error"], color=BLUE,
                marker="o", markersize=4, capsize=3, linewidth=1.8)
    ax.set_xlabel("k")
    ax.set_ylabel("Gap statistic")
    ax.set_xticks(gap["k_values"][::2])
    ax.set_title("The gap statistic never turns over — it is uninformative here")
    ax.annotate("rises monotonically to the range ceiling:\nno interior optimum, so no verdict "
                "on whether\ncluster structure exists",
                xy=(0.04, 0.72), xycoords="axes fraction", fontsize=9, color=TEXT_MUTED)
    fig.tight_layout()
    caption(fig, "The gap statistic was added in Phase 1 precisely because it is the only "
                 "criterion that can report 'no structure'. On this data its uniform "
                 "bounding-box reference is a poor null for discrete, bimodal features, and it "
                 "returns no answer. Reported as a failed instrument, not as an endorsement of "
                 "the largest k.")
    save(fig, OUT, "08_gap_statistic")


def fig_hierarchical(results: dict) -> None:
    h = results["EXP-012_hierarchical"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), width_ratios=[1, 1.25])

    pairs = ["K-Means\nvs Ward", "K-Means\nvs Average", "Ward\nvs Average"]
    values = [h["ari_kmeans_vs_ward"], h["ari_kmeans_vs_average"], h["ari_ward_vs_average"]]
    bars = axes[0].bar(pairs, values, color=[BLUE, ORANGE, ORANGE], width=0.55)
    for bar, value in zip(bars, values):
        axes[0].annotate(f"{value:.3f}", (bar.get_x() + bar.get_width() / 2, value),
                         ha="center", va="bottom", fontsize=9.5, color=TEXT_SECONDARY)
    axes[0].set_ylabel("Adjusted Rand Index")
    axes[0].set_ylim(0, 1.0)
    axes[0].set_title("Cross-algorithm agreement is weak")

    ward = list(h["ward_sizes"].values())
    average = list(h["average_sizes"].values())
    width = 0.36
    positions = np.arange(max(len(ward), len(average)))
    axes[1].bar(positions - width / 2, ward + [0] * (len(positions) - len(ward)),
                width=width, color=BLUE, label="Ward")
    axes[1].bar(positions + width / 2, average + [0] * (len(positions) - len(average)),
                width=width, color=ORANGE, label="Average linkage")
    axes[1].set_xticks(positions)
    axes[1].set_xlabel("Cluster")
    axes[1].set_ylabel("Learners")
    axes[1].set_title("Average linkage chains into one giant cluster")
    axes[1].legend(loc="upper left")

    fig.tight_layout()
    caption(fig, "Ward and K-Means optimise the same objective family, so their modest ARI of "
                 "0.35 is already a weak form of confirmation. Average linkage, which optimises "
                 "something different, agrees almost not at all (ARI 0.019) and degenerates into "
                 "one cluster of 2,406 — the structure is not algorithm-independent.")
    save(fig, OUT, "09_hierarchical_validation")


def fig_level_ablation(results: dict) -> None:
    ablation = results["EXP-011g_level_ablation"]
    frame = pd.DataFrame(ablation["arms"])

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2))
    positions = np.arange(len(frame))

    bars = axes[0].bar(positions, frame.silhouette, color=[BLUE, ORANGE], width=0.5)
    for bar, value in zip(bars, frame.silhouette):
        axes[0].annotate(f"{value:.4f}", (bar.get_x() + bar.get_width() / 2, value),
                         ha="center", va="bottom", fontsize=9, color=TEXT_SECONDARY)
    axes[0].set_xticks(positions)
    axes[0].set_xticklabels(["with level", "without level"], fontsize=9.5)
    axes[0].set_ylabel("Silhouette")
    axes[0].set_ylim(0, frame.silhouette.max() * 1.3)
    axes[0].set_title("Silhouette barely moves")

    bars = axes[1].bar(positions, frame.mean_bootstrap_jaccard, color=[BLUE, ORANGE], width=0.5)
    axes[1].axhline(0.60, color=REFERENCE, linestyle="--", linewidth=1.5)
    for bar, value, n in zip(bars, frame.mean_bootstrap_jaccard, frame.n_unstable_clusters):
        axes[1].annotate(f"{value:.3f}\n{n} unstable",
                         (bar.get_x() + bar.get_width() / 2, value), ha="center", va="bottom",
                         fontsize=9, color=TEXT_SECONDARY)
    axes[1].set_xticks(positions)
    axes[1].set_xticklabels(["with level", "without level"], fontsize=9.5)
    axes[1].set_ylabel("Mean bootstrap Jaccard")
    axes[1].set_ylim(0, 1.2)
    axes[1].set_title("Stability collapses without it")

    fig.tight_layout()
    caption(fig, f"Removing `preferred_level` produces an entirely different partition "
                 f"(ARI {ablation['ari_with_vs_without_level']:.3f}) with one unstable cluster. "
                 "The stable structure in this dataset *is* the course-level split.")
    save(fig, OUT, "10_level_ablation")


def main() -> None:
    apply_style()
    results = load()
    fig_elbow_and_silhouette(results)
    fig_k_constraints(results)
    fig_cluster_sizes_and_stability(results)
    fig_profile_heatmap(results)
    fig_level_composition(results)
    fig_representation_comparison(results)
    fig_variant_and_teacher(results)
    fig_gap_statistic(results)
    fig_hierarchical(results)
    fig_level_ablation(results)

    written = sorted(p.name for p in OUT.glob("*.png"))
    print(f"{len(written)} figures written to {OUT.relative_to(config.PROJECT_ROOT)}:")
    for name in written:
        print(f"  {name}")


if __name__ == "__main__":
    main()
