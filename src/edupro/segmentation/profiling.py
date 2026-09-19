"""Cluster profiling and evidence-derived segment naming.

Profiling reports, for every cluster: size, demographics, engagement, preference,
behavioural and temporal characteristics — the full set the official brief asks a
segment comparison to show.

Naming discipline (`research/segmentation_research.md` §8)
    Labels are **derived from each cluster's own strongest deviations**, never
    chosen first and justified afterwards. The vocabulary below maps a feature and
    a direction to a phrase that feature actually licenses, so a name cannot
    assert behaviour the data does not evidence.

    Two rules matter especially:

    1. **No borrowed labels.** [R12]'s MOOC learner types — "auditing",
       "completing", "sampling", "disengaging" — were derived from longitudinal
       within-course engagement traces. EduPro has no completion or progress data
       at all, only enrollment transactions. Applying those labels here would
       assert learner behaviour this dataset cannot evidence, and they are
       therefore absent from the vocabulary by design.
    2. **A diffuse cluster gets a neutral name.** If no feature deviates by more
       than ``MIN_DEVIATION`` standard deviations, the cluster is named
       "Segment N - mixed profile" and the ambiguity is reported. Inventing a
       narrative for a shapeless cluster is exactly the fabrication §6 prohibits.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from edupro import config
from edupro.data.schema import COURSE_CATEGORIES

#: A feature must deviate by at least this many standard deviations from the
#: population mean before it is allowed to contribute to a segment's name.
MIN_DEVIATION: float = 0.40

#: Feature -> (phrase when high, phrase when low). Every phrase is something the
#: feature itself licenses; none imports meaning from outside the data.
NAMING_VOCABULARY: dict[str, tuple[str, str]] = {
    "total_courses": ("High-volume", "Single-course"),
    "diversity_score": ("Wide-ranging", "Narrow"),
    "diversity_ratio": ("Non-repeating", "Category-repeating"),
    "category_entropy": ("Spread-out", "Concentrated"),
    "learning_depth_index": ("Advanced-leaning", "Beginner-leaning"),
    "free_ratio": ("Free-course", "Paid-course"),
    "avg_spend": ("High-spend", "Low-spend"),
    "avg_course_rating": ("High-rated", "Low-rated"),
    "activity_span_days": ("Long-tenure", "Single-session"),
    "enrollment_frequency": ("Burst", "Spaced-out"),
    "top_category_share": ("Single-subject", "Multi-subject"),
    "n_teachers": ("Many-instructor", "One-instructor"),
    "teacher_loyalty": ("Instructor-loyal", "Instructor-varied"),
    "age": ("Older", "Younger"),
}

#: Features considered when naming, in priority order. Volume comes first because
#: the Phase 2 audit established it as this dataset's dominant axis — naming
#: should say so plainly rather than dress it up as something subtler.
NAMING_PRIORITY: tuple[str, ...] = (
    "total_courses",
    "learning_depth_index",
    "free_ratio",
    "avg_course_rating",
    "diversity_ratio",
    "top_category_share",
    "activity_span_days",
    "teacher_loyalty",
)


def profile_clusters(
    features: pd.DataFrame,
    labels: np.ndarray,
    interactions: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """One row per cluster, with the characteristics the brief asks to compare."""
    frame = features.copy()
    frame["cluster"] = labels
    total = len(frame)

    rows = []
    for cluster, group in frame.groupby("cluster"):
        row: dict[str, object] = {
            "cluster": int(cluster),
            "n_learners": int(len(group)),
            "share": round(len(group) / total, 4),
        }

        if "age" in group.columns:
            row["age_mean"] = round(float(group["age"].mean()), 2)
            row["age_median"] = float(group["age"].median())
        if "gender" in group.columns:
            counts = group["gender"].value_counts(normalize=True)
            row["pct_female"] = round(float(counts.get("Female", 0.0)) * 100, 2)

        for column in (
            "total_courses", "diversity_score", "avg_courses_per_category",
            "enrollment_frequency", "activity_span_days", "avg_course_rating",
            "avg_spend", "diversity_ratio", "learning_depth_index", "free_ratio",
            "category_entropy", "top_category_share", "recency_days",
            "n_teachers", "teacher_loyalty", "avg_teacher_rating",
        ):
            if column in group.columns:
                row[f"{column}_mean"] = round(float(group[column].mean()), 4)

        if "preferred_category" in group.columns:
            top = group["preferred_category"].value_counts(normalize=True)
            row["top_categories"] = ", ".join(
                f"{name} {share * 100:.0f}%" for name, share in top.head(3).items()
            )
        if "preferred_level" in group.columns:
            levels = group["preferred_level"].value_counts(normalize=True)
            row["level_mix"] = ", ".join(
                f"{name} {share * 100:.0f}%" for name, share in levels.items()
            )

        share_columns = [c for c in group.columns if c.startswith("cat_share_")]
        if share_columns:
            means = group[share_columns].mean().sort_values(ascending=False)
            row["category_profile"] = ", ".join(
                f"{c.replace('cat_share_', '').replace('_', ' ')} {v * 100:.0f}%"
                for c, v in means.head(3).items()
            )

        rows.append(row)

    return pd.DataFrame(rows).set_index("cluster").sort_index()


def centroid_deviations(features: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    """Per-cluster feature means expressed in population standard deviations.

    This is the evidence a segment name must be derived from.
    """
    numeric = features.select_dtypes(include=[np.number])
    numeric = numeric[[c for c in numeric.columns if not c.startswith("cat_share_")]]
    population_mean = numeric.mean()
    population_std = numeric.std().replace(0, np.nan)

    frame = numeric.copy()
    frame["cluster"] = labels
    deviations = (
        frame.groupby("cluster").mean().sub(population_mean, axis=1).div(population_std, axis=1)
    )
    return deviations.round(4)


def derive_label(
    deviations: pd.Series,
    cluster: int,
    max_terms: int = 2,
    allowed_features: set[str] | None = None,
) -> dict[str, object]:
    """Name a cluster from its own strongest deviations.

    Returns the label together with the evidence that produced it, so a reader can
    check the name against the numbers rather than take it on trust.

    Args:
        allowed_features: restrict naming to features the clustering **actually
            used**. Without this, a cluster could be named for a dimension the
            model never saw — e.g. "instructor-loyal" when teacher features were
            excluded — which would imply the segmentation captured something it
            did not. Profiling still reports every feature; only the *name* is
            restricted.
    """
    candidates = []
    for feature in NAMING_PRIORITY:
        if feature not in deviations.index:
            continue
        if allowed_features is not None and feature not in allowed_features:
            continue
        value = deviations[feature]
        if pd.isna(value) or abs(value) < MIN_DEVIATION:
            continue
        high, low = NAMING_VOCABULARY[feature]
        candidates.append({
            "feature": feature,
            "deviation": round(float(value), 3),
            "phrase": high if value > 0 else low,
        })

    candidates.sort(key=lambda c: -abs(c["deviation"]))
    chosen = candidates[:max_terms]

    if not chosen:
        return {
            "label": f"Segment {cluster} - mixed profile",
            "evidence": [],
            "is_neutral": True,
            "note": (
                "No feature deviates by more than "
                f"{MIN_DEVIATION} SD from the population mean, so no descriptive "
                "name is supported by the data."
            ),
        }

    return {
        "label": " ".join(c["phrase"] for c in chosen) + " learners",
        "evidence": chosen,
        "is_neutral": False,
        "note": "",
    }


def label_clusters(
    features: pd.DataFrame,
    labels: np.ndarray,
    allowed_features: set[str] | None = None,
) -> dict[int, dict[str, object]]:
    """Derive an evidence-backed label for every cluster.

    Pass ``allowed_features`` (the columns the clustering actually used) so that a
    segment is never named for a dimension the model did not see.
    """
    deviations = centroid_deviations(features, labels)
    return {
        int(cluster): derive_label(
            deviations.loc[cluster], int(cluster), allowed_features=allowed_features
        )
        for cluster in deviations.index
    }


#: A cluster this pure on one course level has that level named in its label.
LEVEL_PURITY_THRESHOLD: float = 0.90


def compose_segment_names(
    derived: dict[int, dict[str, object]], level_composition: pd.DataFrame
) -> dict[int, dict[str, object]]:
    """Add the course level to a label when the cluster is essentially pure on it.

    Deviation-based naming has a blind spot: a cluster sitting at the *middle* of a
    three-level ordinal scale has a near-zero deviation on ``learning_depth_index``
    even when every one of its members prefers the middle level. On this dataset
    that is exactly what happened to the 100%-Intermediate cluster.

    Level purity is a direct, checkable property of the cluster's members, so using
    it keeps naming evidence-derived while removing the blind spot.
    """
    named = {}
    for cluster, info in derived.items():
        enriched = dict(info)
        if cluster in level_composition.index:
            shares = level_composition.loc[cluster]
            level, purity = shares.idxmax(), float(shares.max())
            enriched["level_purity"] = round(purity, 4)
            enriched["dominant_level"] = str(level)
            if purity >= LEVEL_PURITY_THRESHOLD:
                # The level prefix already states what `learning_depth_index`
                # would say, so its phrase is dropped rather than repeated.
                remaining = [
                    e for e in info["evidence"] if e["feature"] != "learning_depth_index"
                ]
                tail = (
                    " ".join(e["phrase"] for e in remaining) + " learners"
                    if remaining
                    else "learners"
                )
                enriched["label"] = f"{level}-level {tail}"
                enriched["evidence"] = list(info["evidence"]) + [{
                    "feature": "preferred_level",
                    "deviation": None,
                    "phrase": f"{purity:.0%} prefer {level}",
                }]
        named[cluster] = enriched
    return named


def category_preference_matrix(features: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    """Mean category share per cluster — the segment-comparison heatmap's data."""
    share_columns = [c for c in features.columns if c.startswith("cat_share_")]
    if not share_columns:
        return pd.DataFrame()
    frame = features[share_columns].copy()
    frame["cluster"] = labels
    matrix = frame.groupby("cluster").mean()
    matrix.columns = [c.replace("cat_share_", "").replace("_", " ").title() for c in matrix.columns]
    return matrix.round(4)
