"""Schema and integrity validation for the EduPro workbook.

Validation returns a structured :class:`ValidationReport` rather than raising on
the first problem, so a single run surfaces every issue at once. Nothing here
mutates or repairs data: it reports. Any cleaning decision must be explicit and
recorded (CLAUDE.md §8).

Severity levels
    ``error``   — breaks a documented guarantee; downstream results cannot be trusted.
    ``warning`` — real but tolerable; must be documented and carried forward.
    ``info``    — a notable property worth recording, not a defect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from edupro import config
from edupro.data.loader import EduProData
from edupro.data.schema import SHEET_SPECS, SheetSpec

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class Finding:
    """One validation result."""

    check: str
    severity: Severity
    sheet: str
    message: str
    count: int = 0

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"[{self.severity.upper():7}] {self.sheet}.{self.check}: {self.message}"


@dataclass
class ValidationReport:
    """Collected findings from a validation run."""

    findings: list[Finding] = field(default_factory=list)

    def add(self, check: str, severity: Severity, sheet: str, message: str, count: int = 0) -> None:
        self.findings.append(Finding(check, severity, sheet, message, count))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def infos(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "info"]

    @property
    def ok(self) -> bool:
        """True when no error-severity finding was raised."""
        return not self.errors

    def to_records(self) -> list[dict[str, object]]:
        return [
            {
                "check": f.check,
                "severity": f.severity,
                "sheet": f.sheet,
                "message": f.message,
                "count": f.count,
            }
            for f in self.findings
        ]

    def summary(self) -> str:
        return (
            f"{len(self.errors)} error(s), {len(self.warnings)} warning(s), "
            f"{len(self.infos)} info"
        )


# ---------------------------------------------------------------------------
# Sheet-level checks
# ---------------------------------------------------------------------------
def validate_sheet(frame: pd.DataFrame, spec: SheetSpec, report: ValidationReport) -> None:
    """Check one sheet against its schema."""
    present = set(frame.columns)
    expected = {c.name for c in spec.columns}

    missing = expected - present
    # PII columns are dropped at load time by design, so their absence is expected.
    missing -= set(spec.pii_columns)
    if missing:
        report.add("columns_missing", "error", spec.name,
                   f"missing columns: {sorted(missing)}", len(missing))
    unexpected = present - expected
    if unexpected:
        report.add("columns_unexpected", "warning", spec.name,
                   f"unexpected columns: {sorted(unexpected)}", len(unexpected))

    if len(frame) != spec.expected_rows:
        report.add("row_count", "warning", spec.name,
                   f"expected {spec.expected_rows} rows, found {len(frame)}", len(frame))

    dupes = int(frame.duplicated().sum())
    if dupes:
        report.add("duplicate_rows", "error", spec.name,
                   f"{dupes} fully duplicated row(s)", dupes)

    for column in spec.columns:
        if column.name not in frame.columns:
            continue
        series = frame[column.name]

        nulls = int(series.isna().sum())
        if nulls and not column.nullable:
            report.add("nulls", "error", spec.name,
                       f"{column.name} has {nulls} null value(s)", nulls)

        if column.unique and not series.is_unique:
            n = int(series.duplicated().sum())
            report.add("uniqueness", "error", spec.name,
                       f"{column.name} is not unique ({n} duplicate value(s))", n)

        if column.allowed is not None:
            observed = set(series.dropna().astype(str).unique())
            unknown = observed - set(column.allowed)
            if unknown:
                report.add("value_domain", "error", spec.name,
                           f"{column.name} has values outside the schema: {sorted(unknown)}",
                           len(unknown))

        if column.id_prefix is not None:
            bad = int((~series.dropna().astype(str).str.startswith(column.id_prefix)).sum())
            if bad:
                report.add("id_format", "error", spec.name,
                           f"{column.name}: {bad} value(s) lack prefix {column.id_prefix!r}", bad)

        if column.kind == "numeric":
            numeric = pd.to_numeric(series, errors="coerce")
            if column.minimum is not None:
                below = int((numeric < column.minimum).sum())
                if below:
                    report.add("range", "error", spec.name,
                               f"{column.name}: {below} value(s) below {column.minimum}", below)
            if column.maximum is not None:
                above = int((numeric > column.maximum).sum())
                if above:
                    report.add("range", "error", spec.name,
                               f"{column.name}: {above} value(s) above {column.maximum}", above)


# ---------------------------------------------------------------------------
# Cross-sheet checks
# ---------------------------------------------------------------------------
def _available(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    check: str,
    sheet: str,
    report: ValidationReport,
) -> bool:
    """Guard a cross-sheet check against columns that are not there.

    The sheet-level pass has already recorded ``columns_missing`` as an *error* for
    anything absent, so the report is complete without this check running. What
    matters is that a missing column must not take the validator down with it: a
    checker that raises on the first corruption it exists to report is worse than
    no checker, because the caller gets an opaque ``KeyError`` instead of a
    validation report naming the problem.

    Found by the Phase 6A adversarial audit, which crashed here on the very first
    corruption probe.
    """
    missing = [column for column in columns if column not in frame.columns]
    if not missing:
        return True
    report.add(
        check, "info", sheet,
        f"skipped: required column(s) absent ({sorted(missing)}); "
        "see the columns_missing error above",
        len(missing),
    )
    return False


def validate_referential_integrity(data: EduProData, report: ValidationReport) -> None:
    """Foreign keys resolve, and every parent row is referenced."""
    parents = {
        config.SHEET_USERS: (data.users, config.KEY_USER),
        config.SHEET_COURSES: (data.courses, config.KEY_COURSE),
        config.SHEET_TEACHERS: (data.teachers, config.KEY_TEACHER),
    }
    tx = data.transactions

    for column, (parent_sheet, parent_column) in SHEET_SPECS[
        config.SHEET_TRANSACTIONS
    ].foreign_keys.items():
        parent_frame, key = parents[parent_sheet]
        if not _available(tx, (column,), "referential_integrity",
                          config.SHEET_TRANSACTIONS, report):
            continue
        if not _available(parent_frame, (key,), "referential_integrity",
                          parent_sheet, report):
            continue
        orphans = int((~tx[column].isin(parent_frame[key])).sum())
        if orphans:
            report.add("orphan_fk", "error", config.SHEET_TRANSACTIONS,
                       f"{column}: {orphans} value(s) absent from {parent_sheet}.{key}", orphans)

        unreferenced = int((~parent_frame[key].isin(tx[column])).sum())
        if unreferenced:
            report.add("unreferenced_parent", "warning", parent_sheet,
                       f"{key}: {unreferenced} row(s) never appear in Transactions",
                       unreferenced)


def validate_transactions(data: EduProData, report: ValidationReport) -> None:
    """Interaction-level guarantees the recommendation pipeline relies on."""
    tx = data.transactions

    if _available(tx, (config.KEY_USER, config.KEY_COURSE), "repeat_enrollment",
                  config.SHEET_TRANSACTIONS, report):
        _validate_repeat_enrollment(tx, report)
    if _available(tx, (config.COL_TRANSACTION_DATE,), "date_validity",
                  config.SHEET_TRANSACTIONS, report):
        _validate_dates(tx, report)
    if _available(tx, ("Amount",), "amount_validity", config.SHEET_TRANSACTIONS, report):
        negative = int((pd.to_numeric(tx["Amount"], errors="coerce") < 0).sum())
        if negative:
            report.add("amount_validity", "error", config.SHEET_TRANSACTIONS,
                       f"{negative} negative Amount value(s)", negative)


def _validate_repeat_enrollment(tx: pd.DataFrame, report: ValidationReport) -> None:
    repeat = int(tx.duplicated(subset=[config.KEY_USER, config.KEY_COURSE]).sum())
    if repeat:
        report.add("repeat_enrollment", "warning", config.SHEET_TRANSACTIONS,
                   f"{repeat} repeat (UserID, CourseID) pair(s)", repeat)
    else:
        report.add("repeat_enrollment", "info", config.SHEET_TRANSACTIONS,
                   "no repeat (UserID, CourseID) pairs: the signal is purely binary/implicit",
                   0)


def _validate_dates(tx: pd.DataFrame, report: ValidationReport) -> None:
    dates = tx[config.COL_TRANSACTION_DATE]
    if dates.isna().any():
        report.add("date_validity", "error", config.SHEET_TRANSACTIONS,
                   f"{int(dates.isna().sum())} unparseable date(s)", int(dates.isna().sum()))
    else:
        report.add("date_validity", "info", config.SHEET_TRANSACTIONS,
                   f"dates span {dates.min().date()} to {dates.max().date()} "
                   f"({dates.nunique()} distinct days)", int(dates.nunique()))


def validate_price_consistency(data: EduProData, report: ValidationReport) -> None:
    """Amount vs CoursePrice, and CourseType vs CoursePrice."""
    if not _available(data.transactions, (config.KEY_COURSE, "Amount"), "amount_vs_price",
                      config.SHEET_TRANSACTIONS, report):
        return
    if not _available(data.courses, (config.KEY_COURSE, "CoursePrice", "CourseType"),
                      "amount_vs_price", config.SHEET_COURSES, report):
        return
    merged = data.transactions.merge(
        data.courses[[config.KEY_COURSE, "CoursePrice"]], on=config.KEY_COURSE, how="left"
    )
    mismatch = int((~pd.Series(
        pd.to_numeric(merged["Amount"]).round(2) == pd.to_numeric(merged["CoursePrice"]).round(2)
    )).sum())
    if mismatch:
        report.add("amount_vs_price", "warning", config.SHEET_TRANSACTIONS,
                   f"{mismatch} transaction(s) where Amount != CoursePrice", mismatch)
    else:
        report.add("amount_vs_price", "info", config.SHEET_TRANSACTIONS,
                   "Amount equals CoursePrice for every transaction: spending carries no "
                   "information beyond which courses were taken", 0)

    courses = data.courses
    free_nonzero = int(((courses["CourseType"] == "Free") & (courses["CoursePrice"] > 0)).sum())
    paid_zero = int(((courses["CourseType"] == "Paid") & (courses["CoursePrice"] == 0)).sum())
    if free_nonzero:
        report.add("type_vs_price", "error", config.SHEET_COURSES,
                   f"{free_nonzero} 'Free' course(s) priced above zero", free_nonzero)
    if paid_zero:
        report.add("type_vs_price", "error", config.SHEET_COURSES,
                   f"{paid_zero} 'Paid' course(s) priced at zero", paid_zero)
    if not free_nonzero and not paid_zero:
        report.add("type_vs_price", "info", config.SHEET_COURSES,
                   "CourseType is a deterministic function of CoursePrice "
                   "(Free <=> price == 0), so the two are redundant", 0)


def validate_course_catalogue(data: EduProData, report: ValidationReport) -> None:
    """Catalogue-level properties that affect content-based similarity."""
    courses = data.courses
    if not _available(courses, ("CourseName",), "duplicate_course_names",
                      config.SHEET_COURSES, report):
        return
    dup_names = int(courses["CourseName"].duplicated().sum())
    if dup_names:
        repeated = sorted(
            courses.loc[courses["CourseName"].duplicated(keep=False), "CourseName"].unique()
        )
        report.add("duplicate_course_names", "warning", config.SHEET_COURSES,
                   f"{dup_names} repeated course name(s): {repeated} — distinct courses "
                   "sharing a title, so titles cannot identify a course", dup_names)


def validate(data: EduProData) -> ValidationReport:
    """Run every check and return the collected report."""
    report = ValidationReport()
    for sheet, frame in (
        (config.SHEET_USERS, data.users),
        (config.SHEET_TEACHERS, data.teachers),
        (config.SHEET_COURSES, data.courses),
        (config.SHEET_TRANSACTIONS, data.transactions),
    ):
        validate_sheet(frame, SHEET_SPECS[sheet], report)
    validate_referential_integrity(data, report)
    validate_transactions(data, report)
    validate_price_consistency(data, report)
    validate_course_catalogue(data, report)
    return report
