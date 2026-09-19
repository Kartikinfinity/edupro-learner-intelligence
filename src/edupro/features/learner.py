"""Learner-level aggregation and feature engineering.

Turns the interaction frame into one row per learner. Every official feature
from the project brief is implemented, plus the additional candidates justified
in ``research/dataset_audit.md``.

Leakage discipline
    :func:`build_learner_features` computes features from **whatever interaction
    frame it is given**. It never reads the raw data itself. To build leakage-free
    training features, pass the training-window frame — the function cannot
    accidentally see the future because it is never shown it (leakage control L1,
    ``research/recommendation_evaluation_plan.md`` §2.5).

Honesty note
    The Phase 2 audit established that several of these features are near-exact
    functions of ``total_courses`` (correlations above 0.9) and that ``avg_spend``
    is a deterministic function of which courses were taken, because ``Amount``
    equals ``CoursePrice`` for every transaction. They are implemented because the
    brief mandates them and because the redundancy must be *demonstrated* rather
    than asserted; ``FEATURE_BLOCKS`` records which block each belongs to so the
    Phase 3 dominance diagnostic can quantify it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from edupro import config
from edupro.data.schema import COURSE_CATEGORIES

#: Feature blocks, used by the Phase 3 feature-dominance diagnostic (eta-squared
#: per block) and by block weighting. Keeping the grouping here means the
#: diagnostic cannot drift out of step with the feature builder.
FEATURE_BLOCKS: dict[str, tuple[str, ...]] = {
    "engagement": (
        "total_courses",
        "avg_courses_per_category",
        "enrollment_frequency",
        "activity_span_days",
    ),
    "preference": (
        "preferred_category",
        "preferred_level",
        "avg_course_rating",
        "category_entropy",
        "top_category_share",
    ),
    "behavioural": (
        "avg_spend",
        "total_spend",
        "diversity_score",
        "diversity_ratio",
        "learning_depth_index",
        "free_ratio",
    ),
    "demographic": (
        "age",
        "gender",
    ),
    "teacher": (
        "n_teachers",
        "teacher_loyalty",
        "avg_teacher_rating",
    ),
    "temporal": (
        "recency_days",
        "first_interaction_days",
    ),
}

#: Columns produced by :func:`category_profile`, one per course category.
CATEGORY_SHARE_COLUMNS: tuple[str, ...] = tuple(
    f"cat_share_{c.lower().replace(' ', '_')}" for c in COURSE_CATEGORIES
)


def _entropy(series: pd.Series) -> float:
    """Shannon entropy (base 2) of a categorical series. Zero for a single value."""
    proportions = series.value_counts(normalize=True)
    if len(proportions) <= 1:
        return 0.0
    return float(stats.entropy(proportions, base=2))


def category_profile(interactions: pd.DataFrame) -> pd.DataFrame:
    """Per-learner distribution across the 12 course categories.

    Returns a row-normalised share vector. This is the encoding variant E-B from
    ``research/segmentation_research.md`` §3: same dimensionality as one-hot but
    carrying the full preference shape rather than only the modal category.
    """
    counts = (
        interactions.pivot_table(
            index=config.KEY_USER,
            columns="CourseCategory",
            values=config.KEY_TRANSACTION,
            aggfunc="count",
            fill_value=0,
        )
        .reindex(columns=list(COURSE_CATEGORIES), fill_value=0)
    )
    shares = counts.div(counts.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    shares.columns = list(CATEGORY_SHARE_COLUMNS)
    return shares


def build_learner_features(
    interactions: pd.DataFrame,
    *,
    users: pd.DataFrame | None = None,
    reference_date: pd.Timestamp | None = None,
    include_category_profile: bool = True,
) -> pd.DataFrame:
    """Aggregate interactions to one row per learner.

    Args:
        interactions: Enriched interaction frame from
            :func:`edupro.data.joins.build_interactions`. **Pass a training-window
            frame to obtain leakage-free features.**
        users: Optional user sheet, to attach ``age`` and ``gender``. Omit for a
            behaviour-only (Variant B) feature matrix.
        reference_date: "Now" for recency. Defaults to the latest date present in
            ``interactions`` — which keeps recency inside the training window
            rather than silently referencing the real present.
        include_category_profile: Append the 12 category-share columns.

    Returns:
        DataFrame indexed by ``UserID``. Learners absent from ``interactions``
        are absent from the result; the caller decides how to handle them, since
        a zero-history learner is a recommendation-tier decision, not a feature
        decision.
    """
    if interactions.empty:
        raise ValueError("Cannot build learner features from an empty interaction frame.")

    reference = reference_date or interactions[config.COL_TRANSACTION_DATE].max()
    grouped = interactions.groupby(config.KEY_USER)

    features = pd.DataFrame(index=grouped.size().index)
    features.index.name = config.KEY_USER

    # --- engagement --------------------------------------------------------
    features["total_courses"] = grouped.size()
    features["diversity_score"] = grouped["CourseCategory"].nunique()
    features["avg_courses_per_category"] = (
        features["total_courses"] / features["diversity_score"]
    )

    first = grouped[config.COL_TRANSACTION_DATE].min()
    last = grouped[config.COL_TRANSACTION_DATE].max()
    features["activity_span_days"] = (last - first).dt.days.astype("int64")
    # +1 so a single-day learner has a defined frequency rather than a division
    # by zero. 54% of learners have a span of 0, so this is the common case.
    features["enrollment_frequency"] = features["total_courses"] / (
        features["activity_span_days"] + 1
    )

    # --- preference --------------------------------------------------------
    features["preferred_category"] = grouped["CourseCategory"].agg(
        lambda s: s.mode().iat[0]
    )
    features["preferred_level"] = grouped["CourseLevel"].agg(lambda s: s.mode().iat[0])
    features["avg_course_rating"] = grouped["CourseRating"].mean()
    features["category_entropy"] = grouped["CourseCategory"].agg(_entropy)
    features["top_category_share"] = grouped["CourseCategory"].agg(
        lambda s: s.value_counts(normalize=True).iat[0]
    )

    # --- behavioural -------------------------------------------------------
    # Amount == CoursePrice for every transaction (Phase 2 audit), so these
    # measure catalogue choice, not independent spending behaviour.
    features["avg_spend"] = grouped["Amount"].mean()
    features["total_spend"] = grouped["Amount"].sum()
    features["diversity_ratio"] = features["diversity_score"] / features["total_courses"]
    features["learning_depth_index"] = grouped["LevelOrdinal"].mean()
    features["free_ratio"] = grouped["IsFree"].mean()

    # --- temporal ----------------------------------------------------------
    features["recency_days"] = (reference - last).dt.days.astype("int64")
    features["first_interaction_days"] = (reference - first).dt.days.astype("int64")

    # --- teacher (opt-in; present only if the columns were joined) ---------
    if config.KEY_TEACHER in interactions.columns:
        features["n_teachers"] = grouped[config.KEY_TEACHER].nunique()
        features["teacher_loyalty"] = 1.0 - (
            features["n_teachers"] / features["total_courses"]
        )
    if "TeacherRating" in interactions.columns:
        features["avg_teacher_rating"] = grouped["TeacherRating"].mean()

    # --- demographics (opt-in) ---------------------------------------------
    if users is not None:
        demographics = users.set_index(config.KEY_USER)[["Age", "Gender"]]
        features = features.join(demographics.rename(columns={"Age": "age", "Gender": "gender"}))

    if include_category_profile:
        features = features.join(category_profile(interactions))

    return features


def summarise_features(features: pd.DataFrame) -> pd.DataFrame:
    """Distribution summary used by the audit and the EDA notebooks."""
    numeric = features.select_dtypes(include=[np.number])
    summary = numeric.describe().T
    summary["skew"] = numeric.skew()
    summary["pct_zero"] = (numeric == 0).mean() * 100
    summary["n_unique"] = numeric.nunique()
    return summary.round(4)
