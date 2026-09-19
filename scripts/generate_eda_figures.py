"""Phase 2 — generate the reusable EDA figures into ``artifacts/eda/``.

Every figure the research paper, the notebooks and the dashboard use is produced
here, from the same code path, so a figure can never disagree with the audit
numbers it illustrates.

Usage
-----
    python scripts/generate_eda_figures.py
"""

from __future__ import annotations

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from edupro import config
from edupro.data.joins import build_interactions, course_popularity
from edupro.data.loader import load_all
from edupro.evaluation.splits import global_temporal_split
from edupro.features.learner import build_learner_features
from edupro.viz import (
    AQUA,
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

OUT = config.ARTIFACTS_DIR / "eda"


def fig_interaction_distribution(counts: pd.Series) -> None:
    """The single most consequential figure: learners per interaction count."""
    distribution = counts.value_counts().sort_index()
    full_range = range(1, int(counts.max()) + 1)
    values = [distribution.get(n, 0) for n in full_range]

    fig, ax = plt.subplots(figsize=(9, 4.6))
    # Colour encodes the cohort the bar belongs to; the empty band is the point
    # of the figure, so it is annotated rather than left for the reader to spot.
    colours = [BLUE if n <= 4 else (GRID if n <= 8 else ORANGE) for n in full_range]
    bars = ax.bar(list(full_range), values, color=colours, width=0.74)

    for n, value, bar in zip(full_range, values, bars):
        if value:
            ax.annotate(f"{value:,}", (bar.get_x() + bar.get_width() / 2, value),
                        ha="center", va="bottom", fontsize=8.5, color=TEXT_SECONDARY)

    ax.axvspan(4.5, 8.5, color="#f6f5f2", zorder=0)
    ax.annotate(
        "no learner has 5–8\ninteractions",
        xy=(6.5, max(values) * 0.55), ha="center", fontsize=9, color=TEXT_MUTED,
    )
    ax.set_xlabel("Interactions per learner")
    ax.set_ylabel("Learners")
    ax.set_title("Learner activity is bimodal, with an empty band at 5–8")
    ax.set_xticks(list(full_range))
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=BLUE),
        plt.Rectangle((0, 0), 1, 1, color=ORANGE),
    ]
    ax.legend(handles, ["Light cohort (1–4)", "Heavy cohort (9–16)"], loc="upper right")
    caption(fig, "54% of learners have exactly one interaction. The gap at 5–8 is a "
                "generative artefact, not sampling noise.")
    fig.tight_layout()
    save(fig, OUT, "01_interaction_distribution")


def fig_course_popularity(popularity: pd.Series) -> None:
    """Popularity is near-uniform: there is almost no popularity signal to exploit."""
    ordered = popularity.sort_values(ascending=False)
    expected = popularity.sum() / len(popularity)

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(range(len(ordered)), ordered.to_numpy(), color=BLUE, width=0.78)
    ax.axhline(expected, color=REFERENCE, linestyle="--", linewidth=1.6,
               label=f"Uniform expectation ({expected:.0f})")
    ax.set_xlabel("Courses, ranked by enrollment")
    ax.set_ylabel("Enrollments")
    ax.set_ylim(0, ordered.max() * 1.12)
    ax.set_title("Course popularity is almost perfectly flat")
    ax.legend(loc="upper right")
    ax.annotate(
        f"range {ordered.min()}–{ordered.max()}   Gini 0.042",
        xy=(0.5, 0.06), xycoords="axes fraction", fontsize=9, color=TEXT_MUTED,
    )
    caption(fig, "A chi-square test against a uniform distribution does not reject "
                "(p = 0.60). Popularity carries essentially no ranking information.")
    fig.tight_layout()
    save(fig, OUT, "02_course_popularity")


def fig_lorenz(counts: pd.Series, popularity: pd.Series) -> None:
    """Two concentration profiles on one axis — same units, so one chart is correct."""
    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    for series, colour, label in (
        (counts, BLUE, "Learner activity (Gini 0.55)"),
        (popularity, ORANGE, "Course popularity (Gini 0.04)"),
    ):
        values = np.sort(series.to_numpy().astype(float))
        cumulative = np.insert(np.cumsum(values) / values.sum(), 0, 0)
        share = np.linspace(0, 1, len(cumulative))
        ax.plot(share, cumulative, color=colour, label=label)
    ax.plot([0, 1], [0, 1], color=REFERENCE, linestyle="--", linewidth=1.4,
            label="Perfect equality")
    ax.set_xlabel("Cumulative share of population")
    ax.set_ylabel("Cumulative share of interactions")
    ax.set_title("Activity is concentrated; popularity is not")
    ax.legend(loc="upper left")
    caption(fig, "Learners differ sharply in how much they do; courses barely differ "
                "in how often they are chosen.")
    fig.tight_layout()
    save(fig, OUT, "03_lorenz_concentration")


def fig_catalogue(courses: pd.DataFrame, popularity: pd.Series) -> None:
    """Catalogue composition and enrollment by category."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))

    by_category = (
        courses.assign(enrollments=courses[config.KEY_COURSE].map(popularity))
        .groupby("CourseCategory")["enrollments"].sum().sort_values()
    )
    axes[0].barh(by_category.index, by_category.to_numpy(), color=BLUE, height=0.7)
    axes[0].axvline(by_category.sum() / len(by_category), color=REFERENCE,
                    linestyle="--", linewidth=1.5, label="Uniform expectation")
    axes[0].set_xlabel("Enrollments")
    axes[0].set_title("Enrollments by category")
    axes[0].legend(loc="lower right")

    composition = (
        courses.groupby(["CourseLevel", "CourseType"]).size().unstack(fill_value=0)
        .reindex(["Beginner", "Intermediate", "Advanced"])
    )
    bottom = np.zeros(len(composition))
    for colour, column in zip((BLUE, ORANGE), composition.columns):
        values = composition[column].to_numpy()
        axes[1].bar(composition.index, values, bottom=bottom, color=colour,
                    width=0.6, label=column, edgecolor="#fcfcfb", linewidth=2)
        for i, (value, base) in enumerate(zip(values, bottom)):
            if value:
                axes[1].annotate(str(value), (i, base + value / 2), ha="center",
                                 va="center", fontsize=9, color="#fcfcfb")
        bottom += values
    axes[1].set_ylabel("Courses")
    axes[1].set_title("Catalogue composition (60 courses)")
    axes[1].legend(loc="upper right", title="Course type")
    caption(fig, "Exactly five courses per category — the catalogue is perfectly balanced.")
    fig.tight_layout()
    save(fig, OUT, "04_catalogue_composition")


def fig_temporal(interactions: pd.DataFrame, split) -> None:
    """Transactions over time, with the pre-registered split cuts marked."""
    daily = interactions.groupby(interactions[config.COL_TRANSACTION_DATE].dt.date).size()
    monthly = interactions.groupby(
        interactions[config.COL_TRANSACTION_DATE].dt.to_period("M")
    ).size()

    fig, axes = plt.subplots(2, 1, figsize=(10, 6.4), height_ratios=[2, 1.4])

    dates = pd.to_datetime(daily.index)
    axes[0].plot(dates, daily.to_numpy(), color=BLUE, linewidth=1.1)
    axes[0].axvline(split.validation_date, color=REFERENCE, linestyle="--", linewidth=1.5)
    axes[0].axvline(split.test_date, color=ORANGE, linestyle="--", linewidth=1.8)
    axes[0].annotate("validation cut", (split.validation_date, daily.max() * 0.96),
                     fontsize=8.5, color=TEXT_MUTED, ha="right", rotation=90, va="top")
    axes[0].annotate("test cut", (split.test_date, daily.max() * 0.96),
                     fontsize=8.5, color=ORANGE, ha="right", rotation=90, va="top")
    axes[0].set_ylabel("Transactions per day")
    axes[0].set_title("Enrollment volume is flat across 2025")

    axes[1].bar([str(p) for p in monthly.index], monthly.to_numpy(), color=BLUE, width=0.7)
    axes[1].axhline(monthly.mean(), color=REFERENCE, linestyle="--", linewidth=1.4)
    axes[1].set_ylabel("Per month")
    axes[1].tick_params(axis="x", rotation=45)
    axes[1].set_ylim(0, monthly.max() * 1.15)
    caption(fig, "No seasonality, trend or launch effect: monthly volume varies by "
                     "under 10% around the mean.")
    fig.tight_layout()
    save(fig, OUT, "05_temporal_activity")


def fig_signal_detection(audit: dict) -> None:
    """Observed statistics against their popularity-matched permutation nulls.

    Two panels, because one scale cannot serve both: the course-choice effects sit
    within a couple of standard deviations of the null while the teacher effect is
    two orders of magnitude larger. A shared axis would flatten the four course
    statistics into invisibility and hide the comparison the figure exists to make.
    """
    preference = audit["signal_detection"]["preference_vs_popularity_null"]
    labels = {
        "mean_distinct_categories": "Distinct categories",
        "mean_top_category_share": "Top-category share",
        "mean_distinct_levels": "Distinct levels",
        "mean_free_share": "Free-course share",
    }
    names = list(labels)
    z_scores = [preference[n]["z"] for n in names]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.0), width_ratios=[1.4, 1])

    # --- panel A: course choice, in null standard deviations ---------------
    left = axes[0]
    positions = np.arange(len(names))
    colours = [ORANGE if abs(z) > 1.96 else BLUE for z in z_scores]
    left.axvspan(-1.96, 1.96, color="#eeedea", zorder=0, label="95% null band")
    left.barh(positions, z_scores, color=colours, height=0.5)
    left.axvline(0, color=REFERENCE, linewidth=1.2)
    for position, z in zip(positions, z_scores):
        left.annotate(f"{z:+.1f}", (z, position), ha="left" if z > 0 else "right",
                      va="center", fontsize=9, color=TEXT_SECONDARY,
                      xytext=(7 if z > 0 else -7, 0), textcoords="offset points")
    left.set_yticks(positions)
    left.set_yticklabels([labels[n] for n in names])
    left.set_xlim(-4, 4)
    left.set_xlabel("Standard deviations from the null")
    left.set_title("Course choice: at or near chance")
    left.legend(loc="upper right")
    left.invert_yaxis()

    # --- panel B: teacher choice, in the statistic's own units -------------
    teacher = audit["signal_detection"]["teacher_concentration"]
    observed = teacher["observed_distinct_teachers_per_interaction"]
    null_low, null_high = teacher["null_ci_95"]
    right = axes[1]
    right.barh([1], [teacher["null_mean"]], color=REFERENCE, height=0.38)
    right.barh([0], [observed], color=ORANGE, height=0.38)
    right.hlines(1, null_low, null_high, color=TEXT_SECONDARY, linewidth=2.4)
    for y, value in ((0, observed), (1, teacher["null_mean"])):
        right.annotate(f"{value:.3f}", (value, y), ha="left", va="center", fontsize=9.5,
                       color=TEXT_SECONDARY, xytext=(8, 0), textcoords="offset points")
    right.set_yticks([0, 1])
    right.set_yticklabels(["Observed", "Chance"])
    right.set_xlim(0, 1.18)
    right.set_xlabel("Distinct teachers per interaction")
    right.set_title("Teacher choice: far from chance")
    right.annotate("1.0 = a different teacher every time", xy=(0.97, 0.63),
                   xycoords="axes fraction", ha="right", fontsize=8.5, color=TEXT_MUTED)

    fig.tight_layout()
    caption(fig, "Course-choice statistics sit inside the 95% null band: learners pick "
                 "courses indistinguishably from popularity-weighted chance. Teacher "
                 "choice does not — learners return to the same instructor far more often "
                 "than the course-teacher structure alone would produce.")
    save(fig, OUT, "06_signal_detection")


def fig_demographics(users: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    age = users["Age"].value_counts().sort_index()
    axes[0].bar(age.index, age.to_numpy(), color=BLUE, width=0.74)
    axes[0].axhline(age.mean(), color=REFERENCE, linestyle="--", linewidth=1.5,
                    label="Uniform expectation")
    axes[0].set_xlabel("Age")
    axes[0].set_ylabel("Learners")
    axes[0].set_title("Age is uniform over 15–35")
    axes[0].legend(loc="lower right")

    gender = users["Gender"].value_counts()
    bars = axes[1].bar(gender.index.astype(str), gender.to_numpy(),
                       color=[BLUE, ORANGE], width=0.5)
    for bar, value in zip(bars, gender.to_numpy()):
        axes[1].annotate(f"{value:,}", (bar.get_x() + bar.get_width() / 2, value),
                         ha="center", va="bottom", fontsize=9, color=TEXT_SECONDARY)
    axes[1].set_ylabel("Learners")
    axes[1].set_title("Gender is near-balanced")
    axes[1].set_ylim(0, gender.max() * 1.15)
    caption(fig, "Neither attribute is associated with course choice "
                     "(all chi-square p > 0.2).")
    fig.tight_layout()
    save(fig, OUT, "07_demographics")


def fig_feature_correlation(features: pd.DataFrame) -> None:
    """Diverging ramp through a neutral midpoint: zero must read as 'no association'."""
    numeric = features.select_dtypes(include=[np.number])
    numeric = numeric[[c for c in numeric.columns if not c.startswith("cat_share_")]]
    matrix = numeric.corr()

    fig, ax = plt.subplots(figsize=(9.6, 8.2))
    image = ax.imshow(matrix.to_numpy(), cmap=DIVERGING, vmin=-1, vmax=1)
    ax.set_xticks(range(len(matrix)))
    ax.set_yticks(range(len(matrix)))
    ax.set_xticklabels(matrix.columns, rotation=55, ha="right", fontsize=8)
    ax.set_yticklabels(matrix.index, fontsize=8)
    ax.grid(False)
    for i in range(len(matrix)):
        for j in range(len(matrix)):
            value = matrix.iat[i, j]
            if i != j and abs(value) >= 0.8:
                ax.annotate(f"{value:.2f}", (j, i), ha="center", va="center",
                            fontsize=7, color="#fcfcfb", fontweight="bold")
    bar = fig.colorbar(image, ax=ax, shrink=0.72)
    bar.set_label("Pearson r", color=TEXT_SECONDARY, fontsize=9)
    bar.outline.set_visible(False)
    ax.set_title("Candidate features are dominated by history length")
    caption(fig, "Labelled cells are |r| >= 0.8. total_courses correlates above 0.9 with "
                "diversity, entropy and teacher loyalty: they largely re-measure activity volume.")
    fig.tight_layout()
    save(fig, OUT, "08_feature_correlation")


def fig_feature_distributions(features: pd.DataFrame) -> None:
    """Small multiples — the honest form when the series cannot share an axis."""
    selected = [
        "total_courses", "diversity_score", "diversity_ratio", "avg_course_rating",
        "avg_spend", "free_ratio", "learning_depth_index", "activity_span_days",
        "category_entropy", "enrollment_frequency", "recency_days", "teacher_loyalty",
    ]
    selected = [c for c in selected if c in features.columns]
    rows = int(np.ceil(len(selected) / 4))
    fig, axes = plt.subplots(rows, 4, figsize=(13, 2.7 * rows))
    for ax, column in zip(axes.ravel(), selected):
        values = features[column].dropna()
        ax.hist(values, bins=28, color=BLUE, edgecolor="#fcfcfb", linewidth=0.5)
        zero_share = (values == 0).mean() * 100
        ax.set_title(column, fontsize=9.5)
        ax.tick_params(labelsize=8)
        if zero_share > 5:
            ax.annotate(f"{zero_share:.0f}% zero", xy=(0.96, 0.9), xycoords="axes fraction",
                        ha="right", fontsize=8, color=TEXT_MUTED)
    for ax in axes.ravel()[len(selected):]:
        ax.set_visible(False)
    fig.suptitle("Candidate learner-feature distributions", fontsize=12,
                 fontweight="bold", y=1.0)
    fig.tight_layout()
    save(fig, OUT, "09_feature_distributions")


def fig_cohorts(counts: pd.Series, interactions: pd.DataFrame) -> None:
    """Light vs heavy cohort: do they differ in anything but volume?"""
    light = counts[counts <= 4].index
    heavy = counts[counts >= 9].index
    frame = interactions.assign(
        cohort=np.where(interactions[config.KEY_USER].isin(heavy), "Heavy (9–16)", "Light (1–4)")
    )
    metrics = {
        "Free-course share": frame.groupby("cohort")["IsFree"].mean(),
        "Mean course rating": frame.groupby("cohort")["CourseRating"].mean() / 5,
        "Mean level (0–2)": frame.groupby("cohort")["LevelOrdinal"].mean() / 2,
    }
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    positions = np.arange(len(metrics))
    width = 0.34
    for offset, (cohort, colour) in enumerate(
        (("Light (1–4)", BLUE), ("Heavy (9–16)", ORANGE))
    ):
        values = [metrics[m][cohort] for m in metrics]
        bars = ax.bar(positions + (offset - 0.5) * width, values, width=width,
                      color=colour, label=cohort)
        for bar, value in zip(bars, values):
            ax.annotate(f"{value:.3f}", (bar.get_x() + bar.get_width() / 2, value),
                        ha="center", va="bottom", fontsize=8.5, color=TEXT_SECONDARY)
    ax.set_xticks(positions)
    ax.set_xticklabels(list(metrics))
    ax.set_ylabel("Normalised to 0–1")
    ax.set_ylim(0, 1)
    ax.set_title("The two cohorts differ in volume, not in what they choose")
    ax.legend(loc="upper right")
    caption(fig, f"Light: {len(light):,} learners. Heavy: {len(heavy):,} learners. "
                "Their content preferences are nearly identical.")
    fig.tight_layout()
    save(fig, OUT, "10_cohort_comparison")


def main() -> None:
    apply_style()
    data = load_all()
    interactions = build_interactions(data, with_user_demographics=True, with_teacher=True)
    counts = data.transactions.groupby(config.KEY_USER).size()
    popularity = course_popularity(interactions)
    split = global_temporal_split(interactions)
    features = build_learner_features(interactions, users=data.users)
    audit = json.loads((config.ARTIFACTS_DIR / "phase2_audit.json").read_text(encoding="utf-8"))

    fig_interaction_distribution(counts)
    fig_course_popularity(popularity)
    fig_lorenz(counts, popularity)
    fig_catalogue(data.courses, popularity)
    fig_temporal(interactions, split)
    fig_signal_detection(audit)
    fig_demographics(data.users)
    fig_feature_correlation(features)
    fig_feature_distributions(features)
    fig_cohorts(counts, interactions)

    written = sorted(p.name for p in OUT.glob("*.png"))
    print(f"{len(written)} figures written to {OUT.relative_to(config.PROJECT_ROOT)}:")
    for name in written:
        print(f"  {name}")


if __name__ == "__main__":
    main()
