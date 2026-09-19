"""Joining the workbook sheets into analysis-ready frames.

One function builds the enriched interaction frame that every later stage reads.
Centralising the join means the feature pipeline, the evaluation split and the
application all see identical columns with identical semantics.
"""

from __future__ import annotations

import pandas as pd

from edupro import config
from edupro.data.loader import EduProData
from edupro.data.schema import LEVEL_ORDER

#: Course columns carried onto each interaction.
COURSE_ATTRIBUTES: tuple[str, ...] = (
    "CourseName",
    "CourseCategory",
    "CourseType",
    "CourseLevel",
    "CoursePrice",
    "CourseDuration",
    "CourseRating",
)

#: Teacher columns carried onto each interaction when ``with_teacher=True``.
#: ``Age`` and ``Gender`` are deliberately absent: they are demographics of a
#: third party who is not the subject of the recommendation, and routing
#: recommendations by them would be discriminatory allocation (decision log D-016).
TEACHER_ATTRIBUTES: tuple[str, ...] = (
    "Expertise",
    "YearsOfExperience",
    "TeacherRating",
)


def build_interactions(
    data: EduProData,
    *,
    with_user_demographics: bool = True,
    with_teacher: bool = False,
) -> pd.DataFrame:
    """Return one row per transaction, enriched with course (and optional) attributes.

    Args:
        data: Loaded workbook.
        with_user_demographics: Attach ``Age`` and ``Gender``. Needed for the
            Variant A segmentation experiment and for demographic-stratified
            evaluation, both of which are legitimate uses (CLAUDE.md §10, §17).
        with_teacher: Attach the validated teacher attributes. Off by default —
            the Teachers sheet is an opt-in experiment, not a core input (§11).

    The returned frame is sorted by ``(UserID, TransactionDate, TransactionID)``
    so that per-learner sequence operations are deterministic.
    """
    frame = data.transactions.merge(
        data.courses[[config.KEY_COURSE, *COURSE_ATTRIBUTES]],
        on=config.KEY_COURSE,
        how="left",
        validate="many_to_one",
    )

    if with_user_demographics:
        frame = frame.merge(
            data.users[[config.KEY_USER, "Age", "Gender"]],
            on=config.KEY_USER,
            how="left",
            validate="many_to_one",
        )

    if with_teacher:
        frame = frame.merge(
            data.teachers[[config.KEY_TEACHER, *TEACHER_ATTRIBUTES]],
            on=config.KEY_TEACHER,
            how="left",
            validate="many_to_one",
        )

    # Ordinal encoding of course level, used by the learning-depth index.
    frame["LevelOrdinal"] = frame["CourseLevel"].map(LEVEL_ORDER).astype("int8")
    frame["IsFree"] = (frame["CourseType"] == "Free").astype("int8")

    return frame.sort_values(
        [config.KEY_USER, config.COL_TRANSACTION_DATE, config.KEY_TRANSACTION]
    ).reset_index(drop=True)


def course_popularity(interactions: pd.DataFrame) -> pd.Series:
    """Enrollment count per course, descending.

    Computed from whatever interaction frame is passed, so that a training-window
    frame yields training-window popularity. Passing the full frame when a
    training frame was intended is leakage control L5's failure mode, which is
    why this takes the frame explicitly rather than reading the raw data itself.
    """
    return (
        interactions.groupby(config.KEY_COURSE)
        .size()
        .sort_values(ascending=False)
        .rename("enrollments")
    )
