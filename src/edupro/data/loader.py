"""Loading the authoritative EduPro workbook.

The raw workbook is never modified: it is opened read-only, and its SHA-256 can
be verified against the value recorded in :mod:`edupro.config` (ADR-0003).

PII is dropped **at load time**, not filtered downstream, so that ``UserName``,
``Email`` and ``TeacherName`` are never present in any frame that could reach a
feature matrix, a persisted artifact or a figure (ADR-0006, CLAUDE.md §17).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from edupro import config
from edupro.data.schema import SHEET_SPECS, SheetSpec


class DataIntegrityError(RuntimeError):
    """Raised when the raw workbook is missing or has been altered."""


@dataclass(frozen=True)
class EduProData:
    """The four sheets of the workbook, loaded and PII-stripped.

    ``transactions`` is sorted by ``(UserID, TransactionDate)`` so that any
    per-learner sequence logic (temporal splits, leave-one-out, progression
    analysis) operates on a deterministic ordering rather than on whatever order
    the file happened to use.
    """

    users: pd.DataFrame
    teachers: pd.DataFrame
    courses: pd.DataFrame
    transactions: pd.DataFrame

    def __repr__(self) -> str:  # pragma: no cover - convenience only
        return (
            f"EduProData(users={len(self.users)}, teachers={len(self.teachers)}, "
            f"courses={len(self.courses)}, transactions={len(self.transactions)})"
        )


def sha256(path: Path) -> str:
    """SHA-256 of a file, streamed so large files do not need to fit in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_raw_workbook(path: Path | None = None) -> str:
    """Confirm the raw workbook exists and matches its recorded checksum.

    Returns the checksum. Raises :class:`DataIntegrityError` if the file is
    missing or has changed — a loud failure is the point, because a silently
    altered input invalidates every downstream number.
    """
    path = path or config.RAW_WORKBOOK
    if not path.is_file():
        raise DataIntegrityError(
            f"Raw workbook not found at {path}. It is the authoritative dataset "
            "and must be present; it is never regenerated."
        )
    digest = sha256(path)
    if digest != config.RAW_WORKBOOK_SHA256:
        raise DataIntegrityError(
            "Raw workbook checksum mismatch — data/raw/ is immutable (CLAUDE.md §8).\n"
            f"  expected {config.RAW_WORKBOOK_SHA256}\n"
            f"  found    {digest}"
        )
    return digest


def _coerce(frame: pd.DataFrame, spec: SheetSpec) -> pd.DataFrame:
    """Apply the schema's dtype expectations without altering any value."""
    frame = frame.copy()
    for column in spec.columns:
        if column.name not in frame.columns:
            continue
        if column.kind == "datetime":
            frame[column.name] = pd.to_datetime(frame[column.name])
        elif column.kind in {"id", "categorical", "pii"}:
            frame[column.name] = frame[column.name].astype("string")
    return frame


def load_sheet(
    sheet: str,
    *,
    path: Path | None = None,
    drop_pii: bool = True,
) -> pd.DataFrame:
    """Load one sheet, coerced to the schema's dtypes.

    Args:
        sheet: Sheet name; must be one of :data:`edupro.config.ALL_SHEETS`.
        path: Workbook path. Defaults to the authoritative raw workbook.
        drop_pii: Drop name/email columns. Defaults to ``True``; pass ``False``
            only for an explicit data-quality audit of those columns, never for
            modelling.
    """
    if sheet not in SHEET_SPECS:
        raise KeyError(f"Unknown sheet {sheet!r}; expected one of {sorted(SHEET_SPECS)}")
    spec = SHEET_SPECS[sheet]
    frame = pd.read_excel(path or config.RAW_WORKBOOK, sheet_name=sheet, engine="openpyxl")
    frame = _coerce(frame, spec)
    if drop_pii and spec.pii_columns:
        frame = frame.drop(columns=[c for c in spec.pii_columns if c in frame.columns])
    return frame


def load_all(
    *,
    path: Path | None = None,
    drop_pii: bool = True,
    verify: bool = True,
) -> EduProData:
    """Load all four sheets.

    Args:
        path: Workbook path. Defaults to the authoritative raw workbook.
        drop_pii: Drop PII columns at load time (default, and the intended use).
        verify: Verify the workbook checksum first. Only disable when loading a
            deliberately different file, e.g. a fixture in a test.
    """
    path = path or config.RAW_WORKBOOK
    if verify:
        verify_raw_workbook(path)

    transactions = load_sheet(config.SHEET_TRANSACTIONS, path=path, drop_pii=drop_pii)
    transactions = transactions.sort_values(
        [config.KEY_USER, config.COL_TRANSACTION_DATE, config.KEY_TRANSACTION]
    ).reset_index(drop=True)

    return EduProData(
        users=load_sheet(config.SHEET_USERS, path=path, drop_pii=drop_pii),
        teachers=load_sheet(config.SHEET_TEACHERS, path=path, drop_pii=drop_pii),
        courses=load_sheet(config.SHEET_COURSES, path=path, drop_pii=drop_pii),
        transactions=transactions,
    )
