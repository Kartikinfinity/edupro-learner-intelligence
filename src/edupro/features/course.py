"""Course-side representation: the catalogue and its content feature matrix.

The learner side of the feature layer lives in :mod:`edupro.features.learner`.
This module is its counterpart: it turns the 60-row course sheet into the two
objects every recommender needs — a **canonically ordered catalogue** and a
**content vector matrix** aligned to that order.

Why the ordering is a first-class concern
    Every recommender works in integer catalogue positions, not course IDs, and a
    persisted popularity array or similarity matrix is meaningless if the order it
    was built under is lost. :func:`build_course_catalogue` sorts by ``CourseID``
    so the order is a deterministic function of the data rather than of dictionary
    iteration or join order, and the order is persisted with the artifacts and
    verified on load.

``CourseName`` is deliberately excluded from the content vector: the Phase 1
review found 58 distinct names across 60 courses with no descriptive text
attached, so TF-IDF over titles would be near-degenerate
(`research/literature_review.md` §2.2).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from edupro import config
from edupro.data.schema import COURSE_CATEGORIES, COURSE_LEVELS

#: Course attributes retained in the persisted catalogue. Everything the
#: recommenders, the filters and the dashboard need; nothing else.
CATALOGUE_COLUMNS: tuple[str, ...] = (
    config.KEY_COURSE,
    "CourseName",
    "CourseCategory",
    "CourseLevel",
    "CourseType",
    "CoursePrice",
    "CourseDuration",
    "CourseRating",
)


def build_course_catalogue(courses: pd.DataFrame) -> pd.DataFrame:
    """Return the catalogue in canonical order, with a stable integer position.

    Sorted by ``CourseID`` so the ordering is reproducible from the data alone.
    The resulting row order defines the integer positions every recommender,
    similarity matrix and popularity array is indexed by.

    Raises:
        ValueError: if ``CourseID`` is not unique, which would make the position
            mapping ambiguous.
    """
    missing = [c for c in CATALOGUE_COLUMNS if c not in courses.columns]
    if missing:
        raise ValueError(f"Course frame is missing required columns: {missing}")

    catalogue = (
        courses.loc[:, list(CATALOGUE_COLUMNS)]
        .drop_duplicates(subset=[config.KEY_COURSE])
        .sort_values(config.KEY_COURSE)
        .reset_index(drop=True)
    )
    if catalogue[config.KEY_COURSE].duplicated().any():
        raise ValueError("CourseID is not unique; catalogue positions would be ambiguous.")
    catalogue["position"] = np.arange(len(catalogue), dtype=int)
    return catalogue


def course_vector_columns() -> list[str]:
    """Column names of the content matrix, in the order it is built.

    Persisted alongside the matrix so a stored vector can be read back and
    attributed to the attribute it came from.
    """
    return [
        *(f"category_{value}" for value in COURSE_CATEGORIES),
        *(f"level_{value}" for value in COURSE_LEVELS),
        "is_free",
        "rating",
        "duration",
    ]


def _minmax(values: np.ndarray) -> np.ndarray:
    """Scale to [0, 1]; a constant vector becomes all zeros.

    Duplicated deliberately from :func:`edupro.recommendation.base.minmax` rather
    than imported, so the feature layer does not depend on the recommendation
    layer. The behaviour is identical and is asserted by test.
    """
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return values
    low, high = float(values.min()), float(values.max())
    if high - low < 1e-12:
        return np.zeros_like(values)
    return (values - low) / (high - low)


def build_course_vectors(courses: pd.DataFrame, course_ids: list[str]) -> np.ndarray:
    """Content feature matrix: category one-hot, level one-hot, type, rating, duration.

    Numeric attributes are min-max scaled so that no single one dominates cosine
    similarity through its raw range — course duration spans hours while rating
    spans roughly one point, so unscaled duration would decide every comparison.

    Args:
        courses: course attributes; must cover every id in ``course_ids``.
        course_ids: catalogue order. Row *i* of the result is ``course_ids[i]``.

    Returns:
        Array of shape ``(len(course_ids), len(course_vector_columns()))``.

    Raises:
        ValueError: if any id in ``course_ids`` is absent from ``courses``.
    """
    indexed = courses.set_index(config.KEY_COURSE).reindex(course_ids)
    unknown = [
        course for course, missing in zip(course_ids, indexed["CourseCategory"].isna()) if missing
    ]
    if unknown:
        raise ValueError(f"Courses absent from the catalogue frame: {unknown[:5]}")

    category = pd.get_dummies(
        indexed["CourseCategory"].astype("string"), dtype=float
    ).reindex(columns=list(COURSE_CATEGORIES), fill_value=0.0)
    level = pd.get_dummies(
        indexed["CourseLevel"].astype("string"), dtype=float
    ).reindex(columns=list(COURSE_LEVELS), fill_value=0.0)
    numeric = pd.DataFrame(
        {
            "is_free": (indexed["CourseType"] == "Free").astype(float),
            "rating": _minmax(indexed["CourseRating"].to_numpy(dtype=float)),
            "duration": _minmax(indexed["CourseDuration"].to_numpy(dtype=float)),
        },
        index=indexed.index,
    )
    return pd.concat([category, level, numeric], axis=1).to_numpy(dtype=float)
