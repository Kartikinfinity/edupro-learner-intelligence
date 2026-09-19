"""Declarative schema for the EduPro workbook.

The schema is the single source of truth for what each sheet must contain. It is
used by the loader (to coerce dtypes), by the validator (to check conformance)
and by the tests (to detect drift in the raw file).

Every expectation recorded here was **observed in the Phase 2 audit of the actual
workbook** — none is assumed. Where a value domain is enumerated, it is the
complete set present in the data, so an unexpected new value fails loudly rather
than flowing silently into a feature.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from edupro import config

ColumnKind = Literal["id", "categorical", "numeric", "datetime", "pii"]


@dataclass(frozen=True)
class ColumnSpec:
    """Expectations for a single column."""

    name: str
    kind: ColumnKind
    nullable: bool = False
    #: Complete set of permitted values, for low-cardinality categoricals.
    allowed: tuple[str, ...] | None = None
    #: Inclusive bounds for numeric columns.
    minimum: float | None = None
    maximum: float | None = None
    #: True if the column must be unique across the sheet (primary key).
    unique: bool = False
    #: Prefix every identifier must carry, e.g. "U" for UserID.
    id_prefix: str | None = None


@dataclass(frozen=True)
class SheetSpec:
    """Expectations for a whole sheet."""

    name: str
    primary_key: str
    expected_rows: int
    columns: tuple[ColumnSpec, ...]
    #: Foreign keys as {column: (referenced sheet, referenced column)}.
    foreign_keys: dict[str, tuple[str, str]] = field(default_factory=dict)

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    @property
    def pii_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.kind == "pii"]


# ---------------------------------------------------------------------------
# Value domains observed in the audited workbook
# ---------------------------------------------------------------------------
GENDERS: tuple[str, ...] = ("Female", "Male")

COURSE_CATEGORIES: tuple[str, ...] = (
    "Artificial Intelligence",
    "Business",
    "Cybersecurity",
    "Data Science",
    "Design",
    "Digital Marketing",
    "Finance",
    "Machine Learning",
    "Marketing",
    "Programming",
    "Project Management",
    "Web Development",
)

COURSE_TYPES: tuple[str, ...] = ("Free", "Paid")

#: Ordered from introductory to advanced. The order is meaningful and is used by
#: the learning-depth index, so it is defined here rather than re-derived.
COURSE_LEVELS: tuple[str, ...] = ("Beginner", "Intermediate", "Advanced")

#: Numeric encoding of ``COURSE_LEVELS`` for the learning-depth index.
LEVEL_ORDER: dict[str, int] = {level: i for i, level in enumerate(COURSE_LEVELS)}

PAYMENT_METHODS: tuple[str, ...] = ("Bank Transfer", "Credit Card", "PayPal")


# ---------------------------------------------------------------------------
# Sheet specifications
# ---------------------------------------------------------------------------
USERS_SPEC = SheetSpec(
    name=config.SHEET_USERS,
    primary_key="UserID",
    expected_rows=3_000,
    columns=(
        ColumnSpec("UserID", "id", unique=True, id_prefix="U"),
        ColumnSpec("UserName", "pii"),
        ColumnSpec("Age", "numeric", minimum=15, maximum=35),
        ColumnSpec("Gender", "categorical", allowed=GENDERS),
        ColumnSpec("Email", "pii"),
    ),
)

TEACHERS_SPEC = SheetSpec(
    name=config.SHEET_TEACHERS,
    primary_key="TeacherID",
    expected_rows=60,
    columns=(
        ColumnSpec("TeacherID", "id", unique=True, id_prefix="TC"),
        ColumnSpec("TeacherName", "pii"),
        ColumnSpec("Age", "numeric", minimum=27, maximum=50),
        ColumnSpec("Gender", "categorical", allowed=GENDERS),
        ColumnSpec("Expertise", "categorical", allowed=COURSE_CATEGORIES),
        ColumnSpec("YearsOfExperience", "numeric", minimum=1, maximum=24),
        ColumnSpec("TeacherRating", "numeric", minimum=1.0, maximum=5.0),
    ),
)

COURSES_SPEC = SheetSpec(
    name=config.SHEET_COURSES,
    primary_key="CourseID",
    expected_rows=60,
    columns=(
        ColumnSpec("CourseID", "id", unique=True, id_prefix="CR"),
        # Not unique: two names each appear on two distinct courses in different
        # categories. Audited and confirmed to be distinct courses, not duplicates.
        ColumnSpec("CourseName", "categorical"),
        ColumnSpec("CourseCategory", "categorical", allowed=COURSE_CATEGORIES),
        ColumnSpec("CourseType", "categorical", allowed=COURSE_TYPES),
        ColumnSpec("CourseLevel", "categorical", allowed=COURSE_LEVELS),
        ColumnSpec("CoursePrice", "numeric", minimum=0.0),
        ColumnSpec("CourseDuration", "numeric", minimum=0.0),
        ColumnSpec("CourseRating", "numeric", minimum=1.0, maximum=5.0),
    ),
)

TRANSACTIONS_SPEC = SheetSpec(
    name=config.SHEET_TRANSACTIONS,
    primary_key="TransactionID",
    expected_rows=10_000,
    columns=(
        ColumnSpec("TransactionID", "id", unique=True, id_prefix="TT"),
        ColumnSpec("UserID", "id", id_prefix="U"),
        ColumnSpec("CourseID", "id", id_prefix="CR"),
        ColumnSpec("TransactionDate", "datetime"),
        ColumnSpec("Amount", "numeric", minimum=0.0),
        ColumnSpec("PaymentMethod", "categorical", allowed=PAYMENT_METHODS),
        ColumnSpec("TeacherID", "id", id_prefix="TC"),
    ),
    foreign_keys={
        "UserID": (config.SHEET_USERS, "UserID"),
        "CourseID": (config.SHEET_COURSES, "CourseID"),
        "TeacherID": (config.SHEET_TEACHERS, "TeacherID"),
    },
)

SHEET_SPECS: dict[str, SheetSpec] = {
    spec.name: spec
    for spec in (USERS_SPEC, TEACHERS_SPEC, COURSES_SPEC, TRANSACTIONS_SPEC)
}
