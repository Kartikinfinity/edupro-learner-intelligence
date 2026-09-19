"""Phase 3B — figures for the recommendation experiments.

Reads ``artifacts/recommendation/recommendation_results.json`` and writes figures
to ``artifacts/recommendation/``. Every chart comes from the same results file the
write-up quotes.

Usage
-----
    python scripts/generate_recommendation_figures.py
"""

from __future__ import annotations

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from edupro import config
from edupro.viz import (
    BLUE,
    GRID,
    ORANGE,
    REFERENCE,
    TEXT_MUTED,
    TEXT_SECONDARY,
    apply_style,
    caption,
    save,
)

OUT = config.ARTIFACTS_DIR / "recommendation"
K = "10"


def load() -> dict:
    return json.loads((OUT / "recommendation_results.json").read_text(encoding="utf-8"))


def frame_for(results: dict, stage: str) -> pd.DataFrame:
    rows = []
    for method, payload in results[stage].items():
        metrics = payload["overall"][K]
        rows.append({"method": method, **metrics})
    return pd.DataFrame(rows).sort_values("ndcg", ascending=False).reset_index(drop=True)


def fig_method_comparison(results: dict) -> None:
    """The headline: every method against the random floor."""
    frame = frame_for(results, "test").sort_values("ndcg")
    random_ndcg = float(frame.loc[frame.method == "random", "ndcg"].iloc[0])

    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    colours = [
        REFERENCE if m == "random" else (ORANGE if v > random_ndcg else GRID)
        for m, v in zip(frame.method, frame.ndcg)
    ]
    bars = ax.barh(frame.method, frame.ndcg, color=colours, height=0.62)
    ax.axvline(random_ndcg, color=REFERENCE, linestyle="--", linewidth=1.8)
    ax.annotate("random floor", xy=(random_ndcg, len(frame) - 0.4), xytext=(6, 0),
                textcoords="offset points", fontsize=9, color=TEXT_SECONDARY)
    for bar, value in zip(bars, frame.ndcg):
        ax.annotate(f"{value:.4f}", (value, bar.get_y() + bar.get_height() / 2),
                    xytext=(6, 0), textcoords="offset points", va="center",
                    fontsize=8.5, color=TEXT_SECONDARY)
    ax.set_xlabel("NDCG@10 (test window)")
    ax.set_xlim(0, frame.ndcg.max() * 1.3)
    ax.set_title("No method separates from the random floor")
    fig.tight_layout()
    caption(fig, "791 evaluable learners, leakage-free global temporal split. The spread "
                 "between the best and worst method is 0.026 NDCG; random sits in the "
                 "middle of the field.")
    save(fig, OUT, "01_method_comparison")


def fig_significance(results: dict) -> None:
    """A forest plot: the comparison that settles whether any gap is real."""
    significance = results["significance_vs_random"]["per_method"]
    rows = [
        {"method": m, **v["vs_random"]}
        for m, v in significance.items()
    ]
    frame = pd.DataFrame(rows).sort_values("mean_difference")

    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    positions = np.arange(len(frame))
    ax.axvspan(-1, 0, color="#f4f3f0", zorder=0)
    ax.axvline(0, color=REFERENCE, linewidth=1.5)
    for position, (_, row) in zip(positions, frame.iterrows()):
        colour = ORANGE if row["significant"] else BLUE
        ax.plot([row["ci_95_low"], row["ci_95_high"]], [position, position],
                color=colour, linewidth=2.2, solid_capstyle="round")
        ax.plot(row["mean_difference"], position, "o", color=colour, markersize=7)
    ax.set_yticks(positions)
    ax.set_yticklabels(frame.method)
    ax.set_xlabel("Difference in NDCG@10 vs random (paired bootstrap, 95% CI)")
    ax.set_xlim(-0.05, 0.05)
    ax.set_title("Every interval contains zero")
    ax.annotate("worse than random", xy=(-0.045, len(frame) - 0.5), fontsize=8.5,
                color=TEXT_MUTED)
    ax.annotate("better than random", xy=(0.012, len(frame) - 0.5), fontsize=8.5,
                color=TEXT_MUTED)
    fig.tight_layout()
    caption(fig, "Paired bootstrap over per-learner NDCG@10 differences, 2,000 resamples. "
                 "No method is distinguishable from random ranking on this dataset — the "
                 "outcome Phase 2's signal detection predicted.")
    save(fig, OUT, "02_significance_vs_random")


def fig_accuracy_vs_coverage(results: dict) -> None:
    """The co-primary trade-off: accuracy means little without catalogue reach."""
    frame = frame_for(results, "test")
    random_ndcg = float(frame.loc[frame.method == "random", "ndcg"].iloc[0])

    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    ax.axhline(random_ndcg, color=REFERENCE, linestyle="--", linewidth=1.5)
    ax.axvline(0.25, color=ORANGE, linestyle="--", linewidth=1.5)
    ax.annotate("25% coverage gate", xy=(0.26, frame.ndcg.min() * 0.97), fontsize=8.5,
                color=ORANGE, rotation=90, va="bottom")
    ax.annotate("random NDCG", xy=(1.0, random_ndcg), xytext=(-4, 5),
                textcoords="offset points", ha="right", fontsize=8.5, color=TEXT_SECONDARY)
    for _, row in frame.iterrows():
        colour = REFERENCE if row.method == "random" else BLUE
        ax.plot(row.coverage, row.ndcg, "o", color=colour, markersize=9)
        ax.annotate(row.method, (row.coverage, row.ndcg), xytext=(7, 3),
                    textcoords="offset points", fontsize=8.5, color=TEXT_SECONDARY)
    ax.set_xlabel("Catalogue coverage@10")
    ax.set_ylabel("NDCG@10")
    ax.set_xlim(0.2, 1.12)
    ax.set_title("Accuracy versus catalogue reach")
    fig.tight_layout()
    caption(fig, "Popularity and rating concentrate on ~30% of the catalogue without "
                 "gaining accuracy. Nothing sits meaningfully above the random line at "
                 "any coverage.")
    save(fig, OUT, "03_accuracy_vs_coverage")


def fig_tiers(results: dict) -> None:
    """Per-tier behaviour, and why rising hit rate is arithmetic, not skill."""
    analysis = results["EXP-error_analysis"]
    tiers = ["minimal", "moderate", "rich"]
    by_tier = analysis["by_tier"]
    targets = analysis["by_n_targets"]

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4))

    per_tier = results["per_tier_significance_vs_random"]["per_tier"]
    positions = np.arange(len(tiers))
    differences = [per_tier[t]["mean_difference"] for t in tiers]
    lows = [per_tier[t]["ci_95_low"] for t in tiers]
    highs = [per_tier[t]["ci_95_high"] for t in tiers]
    axes[0].axhline(0, color=REFERENCE, linewidth=1.5)
    axes[0].errorbar(positions, differences,
                     yerr=[np.array(differences) - np.array(lows),
                           np.array(highs) - np.array(differences)],
                     fmt="o", color=BLUE, capsize=5, markersize=8, linewidth=2)
    for position, (tier, value) in zip(positions, zip(tiers, differences)):
        axes[0].annotate(f"n={per_tier[tier]['n_users']}", (position, value),
                         xytext=(10, -4), textcoords="offset points",
                         fontsize=8.5, color=TEXT_MUTED)
    axes[0].set_xticks(positions)
    axes[0].set_xticklabels([f"{t}\n({by_tier[t]['n']} learners)" for t in tiers])
    axes[0].set_ylabel("NDCG@10 vs random")
    axes[0].set_title("The method does not help in any tier")

    counts = sorted(int(n) for n in targets)
    rates = [targets[str(n)]["hit_rate"] for n in counts]
    sizes = [targets[str(n)]["n"] for n in counts]
    bars = axes[1].bar([str(n) for n in counts], rates, color=BLUE, width=0.62)
    for bar, rate, size in zip(bars, rates, sizes):
        axes[1].annotate(f"{rate:.2f}\nn={size}", (bar.get_x() + bar.get_width() / 2, rate),
                         ha="center", va="bottom", fontsize=8.5, color=TEXT_SECONDARY)
    axes[1].set_xlabel("Held-out courses per learner")
    axes[1].set_ylabel("Hit Rate@10")
    axes[1].set_ylim(0, max(rates) * 1.28)
    axes[1].set_title("Hit rate rises with targets, not with skill")

    fig.tight_layout()
    caption(fig, "Left: paired against random within each tier; every interval contains "
                 "zero. Right: a learner with six held-out courses has six chances to be "
                 "hit in ten slots, so the apparent advantage of high-history learners is "
                 "arithmetic.")
    save(fig, OUT, "04_tier_behaviour")


def fig_weights_and_ablation(results: dict) -> None:
    search = results["EXP-024_weight_search"]
    ablation = pd.DataFrame(results["EXP-024b_ablation"])

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4), width_ratios=[1, 1.2])

    weights = pd.Series(search["best_weights"]).sort_values()
    bars = axes[0].barh(weights.index, weights.to_numpy(), color=BLUE, height=0.62)
    for bar, value in zip(bars, weights.to_numpy()):
        axes[0].annotate(f"{value:.3f}", (value, bar.get_y() + bar.get_height() / 2),
                         xytext=(5, 0), textcoords="offset points", va="center",
                         fontsize=8.5, color=TEXT_SECONDARY)
    axes[0].set_xlabel("Weight in the best hybrid")
    axes[0].set_xlim(0, max(weights.max() * 1.3, 0.1))
    axes[0].set_title(f"Weights found by search ({search['n_samples']} samples)")

    ablation = ablation.sort_values("delta_vs_full")
    colours = [ORANGE if d < -0.005 else GRID for d in ablation.delta_vs_full]
    bars = axes[1].barh(ablation.removed, ablation.delta_vs_full, color=colours, height=0.62)
    axes[1].axvline(0, color=REFERENCE, linewidth=1.4)
    for bar, value in zip(bars, ablation.delta_vs_full):
        axes[1].annotate(f"{value:+.4f}", (value, bar.get_y() + bar.get_height() / 2),
                         xytext=(-6 if value < 0 else 6, 0), textcoords="offset points",
                         va="center", ha="right" if value < 0 else "left",
                         fontsize=8.5, color=TEXT_SECONDARY)
    axes[1].set_xlabel("Change in validation NDCG@10 when the component is removed")
    axes[1].set_title("Component ablation")

    fig.tight_layout()
    caption(fig, "Weights were searched on the validation split, never chosen by hand "
                 "(CLAUDE.md §14). Removing content_based or user_user_profile changes "
                 "nothing: the search had already assigned them near-zero weight.")
    save(fig, OUT, "05_weights_and_ablation")


def fig_protocol_comparison(results: dict) -> None:
    """[R24] reproduced: the split strategy reorders the methods."""
    comparison = pd.DataFrame(results["EXP-026_protocol_b"]["comparison"])
    ranking_a = results["EXP-026_protocol_b"]["ranking_a"]
    ranking_b = results["EXP-026_protocol_b"]["ranking_b"]

    fig, ax = plt.subplots(figsize=(9, 6))
    for method in ranking_a:
        left = ranking_a.index(method)
        right = ranking_b.index(method)
        moved = abs(left - right) >= 3
        ax.plot([0, 1], [left, right], color=ORANGE if moved else GRID,
                linewidth=2.2 if moved else 1.4, zorder=2 if moved else 1)
        ax.plot(0, left, "o", color=ORANGE if moved else BLUE, markersize=7)
        ax.plot(1, right, "o", color=ORANGE if moved else BLUE, markersize=7)
        ax.annotate(method, (0, left), xytext=(-8, 0), textcoords="offset points",
                    ha="right", va="center", fontsize=8.5, color=TEXT_SECONDARY)
        ax.annotate(method, (1, right), xytext=(8, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=8.5, color=TEXT_SECONDARY)
    ax.set_xlim(-0.55, 1.55)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Protocol A\n(global temporal, leakage-free)",
                        "Protocol B\n(leave-one-out, leakage-bearing)"])
    ax.set_ylabel("Rank by NDCG@10")
    ax.invert_yaxis()
    ax.set_yticks([])
    ax.grid(False)
    ax.set_title("The evaluation protocol reorders the methods")
    fig.tight_layout()
    caption(fig, "Highlighted methods move three or more places. Random falls from 6th to "
                 "11th and item-based CF rises from 9th to 3rd purely by changing the "
                 "split — Meng et al.'s finding reproduced on EduPro.")
    save(fig, OUT, "06_protocol_comparison")


def fig_error_analysis(results: dict) -> None:
    analysis = results["EXP-error_analysis"]

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4))

    bias = analysis["popularity_bias"]
    labels = ["Courses\nrecommended", "Courses learners\nactually took"]
    values = [bias["mean_recommended_popularity_rank"], bias["mean_target_popularity_rank"]]
    bars = axes[0].bar(labels, values, color=[ORANGE, BLUE], width=0.5)
    axes[0].axhline(bias["catalogue_midpoint"], color=REFERENCE, linestyle="--", linewidth=1.5)
    axes[0].annotate("catalogue midpoint", xy=(1.42, bias["catalogue_midpoint"]),
                     xytext=(0, 4), textcoords="offset points", ha="right",
                     fontsize=8.5, color=TEXT_MUTED)
    for bar, value in zip(bars, values):
        axes[0].annotate(f"{value:.1f}", (bar.get_x() + bar.get_width() / 2, value),
                         ha="center", va="bottom", fontsize=9.5, color=TEXT_SECONDARY)
    axes[0].set_ylabel("Mean popularity rank (0 = most popular)")
    axes[0].set_ylim(0, 40)
    axes[0].set_title("Popularity bias")

    match = analysis["category_match"]
    labels = ["History category\noverlaps target", "It does not"]
    values = [match["when_history_category_overlaps_target"], match["when_it_does_not"]]
    bars = axes[1].bar(labels, values, color=[BLUE, GRID], width=0.5)
    for bar, value in zip(bars, values):
        axes[1].annotate(f"{value:.3f}", (bar.get_x() + bar.get_width() / 2, value),
                         ha="center", va="bottom", fontsize=9.5, color=TEXT_SECONDARY)
    axes[1].set_ylabel("Hit Rate@10")
    axes[1].set_ylim(0, max(values) * 1.28)
    axes[1].set_title("Where the misses concentrate")

    fig.tight_layout()
    caption(fig, "Left: the reported method recommends courses well above median "
                 "popularity while learners' actual next courses sit near the median. "
                 "Right: learners who return to a category they have already taken are "
                 "far easier to predict — a property of the learner, not of the model.")
    save(fig, OUT, "07_error_analysis")


def fig_precision_ceiling(results: dict) -> None:
    """Precision@K against what was achievable — the brief's mandated metric, in context."""
    frame = frame_for(results, "test").sort_values("precision")
    fig, ax = plt.subplots(figsize=(9.5, 5.0))
    positions = np.arange(len(frame))
    ax.barh(positions, frame.precision_ceiling, color=GRID, height=0.62,
            label="Ceiling (achievable given held-out counts)")
    ax.barh(positions, frame.precision, color=BLUE, height=0.62, label="Achieved")
    for position, (achieved, ceiling) in enumerate(zip(frame.precision, frame.precision_ceiling)):
        ax.annotate(f"{achieved:.4f}  ({achieved / ceiling:.0%} of ceiling)",
                    (ceiling, position), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=8.5, color=TEXT_SECONDARY)
    ax.set_yticks(positions)
    ax.set_yticklabels(frame.method)
    ax.set_xlabel("Precision@10")
    ax.set_xlim(0, frame.precision_ceiling.max() * 1.55)
    ax.set_title("Precision@10 against its ceiling")
    ax.legend(loc="lower right")
    fig.tight_layout()
    caption(fig, "With a 60-course catalogue and ~2.05 held-out courses per learner, "
                 "Precision@10 cannot exceed 0.205. Reporting the raw number without the "
                 "ceiling would make every method look like a failure.")
    save(fig, OUT, "08_precision_ceiling")


def main() -> None:
    apply_style()
    results = load()
    fig_method_comparison(results)
    fig_significance(results)
    fig_accuracy_vs_coverage(results)
    fig_tiers(results)
    fig_weights_and_ablation(results)
    fig_protocol_comparison(results)
    fig_error_analysis(results)
    fig_precision_ceiling(results)

    written = sorted(p.name for p in OUT.glob("*.png"))
    print(f"{len(written)} figures written to {OUT.relative_to(config.PROJECT_ROOT)}:")
    for name in written:
        print(f"  {name}")


if __name__ == "__main__":
    main()
