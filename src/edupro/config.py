"""Project-wide paths, dataset constants and reproducibility settings.

Every module resolves filesystem locations through this file rather than
hard-coding relative paths, so the pipeline behaves identically whether it is
invoked from a script, a test, a notebook or the Streamlit application.

The constants describing the workbook (sheet names, key columns) are recorded
from the authoritative dataset itself; see ``artifacts/phase0_source_inventory.json``
for the structural inventory they were taken from.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------
# config.py lives at <root>/src/edupro/config.py, so the project root is three
# levels up.
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

DATA_DIR: Final[Path] = PROJECT_ROOT / "data"
RAW_DIR: Final[Path] = DATA_DIR / "raw"
INTERIM_DIR: Final[Path] = DATA_DIR / "interim"
PROCESSED_DIR: Final[Path] = DATA_DIR / "processed"

REFERENCES_DIR: Final[Path] = PROJECT_ROOT / "references"
OFFICIAL_DIR: Final[Path] = REFERENCES_DIR / "official"

RESEARCH_DIR: Final[Path] = PROJECT_ROOT / "research"
MODELS_DIR: Final[Path] = PROJECT_ROOT / "models"
DOCS_DIR: Final[Path] = PROJECT_ROOT / "docs"

#: Every generated output - experiment results, figures and the production
#: artifact set - lives under here. Phase 1 had planned separate `experiments/`
#: and `reports/figures/` trees; the implementation consolidated on one location
#: and those directories were never written to, so they were removed in Phase 6D
#: rather than left in the repository as empty shells.
ARTIFACTS_DIR: Final[Path] = PROJECT_ROOT / "artifacts"

# ---------------------------------------------------------------------------
# Authoritative source materials
# ---------------------------------------------------------------------------
RAW_WORKBOOK: Final[Path] = RAW_DIR / "EduPro Online Platform.xlsx"
OFFICIAL_DOCUMENTATION: Final[Path] = OFFICIAL_DIR / "project offical detail.pdf"

# SHA-256 of the source materials as received. Verifying against these detects
# accidental modification of an input that is required to remain immutable.
RAW_WORKBOOK_SHA256: Final[str] = (
    "ed555e4613e6a210b73af0d4f64e34bd43cb59650041e2bd05f8a8ffbf5d8cc0"
)
OFFICIAL_DOCUMENTATION_SHA256: Final[str] = (
    "e794444490c19f85b8bef6534d844a629150971189eaf71448122ed402c4e8cf"
)

# ---------------------------------------------------------------------------
# Workbook structure
# ---------------------------------------------------------------------------
SHEET_USERS: Final[str] = "Users"
SHEET_TEACHERS: Final[str] = "Teachers"
SHEET_COURSES: Final[str] = "Courses"
SHEET_TRANSACTIONS: Final[str] = "Transactions"

#: Sheets required by the official documentation's "Dataset Fields Utilized"
#: section. The Teachers sheet is deliberately absent - it is an opt-in
#: experiment, not a core input (CLAUDE.md section 11).
CORE_SHEETS: Final[tuple[str, ...]] = (SHEET_USERS, SHEET_COURSES, SHEET_TRANSACTIONS)

#: Every sheet physically present in the workbook.
ALL_SHEETS: Final[tuple[str, ...]] = (
    SHEET_USERS,
    SHEET_TEACHERS,
    SHEET_COURSES,
    SHEET_TRANSACTIONS,
)

#: Primary/foreign keys used to join the sheets.
KEY_USER: Final[str] = "UserID"
KEY_COURSE: Final[str] = "CourseID"
KEY_TEACHER: Final[str] = "TeacherID"
KEY_TRANSACTION: Final[str] = "TransactionID"
COL_TRANSACTION_DATE: Final[str] = "TransactionDate"

#: Columns that identify a real person and must never be used as modelling
#: features or surfaced in the dashboard (CLAUDE.md section 17).
PII_COLUMNS: Final[tuple[str, ...]] = ("UserName", "Email", "TeacherName")

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
#: Single seed used for every stochastic operation (train/test shuffling,
#: K-Means initialisation, bootstrap stability sampling, UMAP/t-SNE embeddings).
RANDOM_SEED: Final[int] = 42


def ensure_directories() -> None:
    """Create the writable output directories if they do not already exist.

    Only generated-output directories are created; source directories are never
    created implicitly, so a missing input fails loudly instead of silently
    producing an empty pipeline run.
    """
    for directory in (
        INTERIM_DIR,
        PROCESSED_DIR,
        MODELS_DIR,
        ARTIFACTS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
