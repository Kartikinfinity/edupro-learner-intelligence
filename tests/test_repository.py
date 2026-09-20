"""Repository hygiene tests.

Phase 6D cleaned the repository. These tests keep it clean: they fail if caches,
credentials, personal data or local paths are ever committed, and if the README
stops matching what the project actually contains.

The PII check is the one that matters most. It loads the real names and email
addresses from the workbook and searches every tracked file for them, rather than
grepping for column headings — a leak under a different header would pass a
heading search and fail this one.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from edupro import config

README = config.PROJECT_ROOT / "README.md"
CHECKLIST = config.DOCS_DIR / "submission_checklist.md"
SCREENSHOTS = config.DOCS_DIR / "screenshots"


@pytest.fixture(scope="module")
def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True,
        cwd=config.PROJECT_ROOT, check=True,
    )
    return [config.PROJECT_ROOT / line for line in result.stdout.splitlines() if line.strip()]


@pytest.fixture(scope="module")
def readme() -> str:
    return README.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Nothing that should not be committed, is
# ---------------------------------------------------------------------------
CRUFT = re.compile(
    r"(__pycache__|\.pyc$|\.pyo$|\.pytest_cache|\.ipynb_checkpoints"
    r"|\.DS_Store|Thumbs\.db|\.swp$|\.tmp$|\.bak$|~$|\.log$|\.egg-info)"
)


def test_no_caches_or_temporary_files_are_tracked(tracked_files: list[Path]):
    offenders = [p.name for p in tracked_files if CRUFT.search(str(p))]
    assert not offenders, f"cruft is tracked: {offenders[:10]}"


def test_no_virtual_environment_or_build_output_is_tracked(tracked_files: list[Path]):
    offenders = [
        str(p.relative_to(config.PROJECT_ROOT))
        for p in tracked_files
        if any(part in {".venv", "venv", "build", "dist", "node_modules"} for part in p.parts)
    ]
    assert not offenders, f"environment or build output tracked: {offenders[:5]}"


SECRET_PATTERNS = [
    (r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token|password)\s*[:=]\s*['\"][^'\"]{8,}", "credential"),
    (r"(?i)aws_(access|secret)_key", "aws key"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY", "private key"),
    (r"gh[pousr]_[A-Za-z0-9]{20,}", "github token"),
    (r"sk-[A-Za-z0-9]{32,}", "api key"),
]


def test_no_credentials_or_secrets_are_committed(tracked_files: list[Path]):
    offenders = []
    for path in tracked_files:
        if not path.exists():
            continue
        text = path.read_bytes().decode("utf-8", errors="ignore")
        for pattern, kind in SECRET_PATTERNS:
            if re.search(pattern, text):
                offenders.append(f"{path.name}: {kind}")
    assert not offenders, f"possible secrets committed: {offenders[:5]}"


def test_no_local_user_paths_are_committed(tracked_files: list[Path]):
    """An absolute path from the author's machine is both noise and a small
    disclosure, and it breaks anyone who copies the line."""
    pattern = re.compile(r"C:\\+Users\\+[A-Za-z]|/home/[a-z]+/|/Users/[A-Za-z]+/")
    offenders = []
    for path in tracked_files:
        if not path.exists() or path.suffix in {".png", ".parquet", ".joblib", ".xlsx", ".pdf"}:
            continue
        text = path.read_bytes().decode("utf-8", errors="ignore")
        if pattern.search(text):
            offenders.append(str(path.relative_to(config.PROJECT_ROOT)))
    assert not offenders, f"local user paths committed: {offenders[:5]}"


@pytest.mark.slow
def test_no_real_personal_data_is_committed(tracked_files: list[Path]):
    """Search for the actual values, not the column headings.

    Names are matched at word boundaries: a short name like 'wwest' occurs by
    chance inside the base64 of an embedded notebook image, which is how this
    check produced its one false positive during Phase 6D.
    """
    from edupro.data.loader import load_all

    pii = load_all(drop_pii=False)
    emails = [e for e in pii.users["Email"].astype(str) if "@" in e]
    names = sorted({
        n for n in
        list(pii.users["UserName"].astype(str)) + list(pii.teachers["TeacherName"].astype(str))
        if len(n) >= 4
    })
    name_pattern = re.compile(
        r"(?<![A-Za-z0-9])(" + "|".join(re.escape(n) for n in names[:1500]) + r")(?![A-Za-z0-9])"
    )

    offenders = []
    for path in tracked_files:
        if not path.exists():
            continue
        blob = path.read_bytes()
        if any(email.encode() in blob for email in emails):
            offenders.append(f"{path.name}: email")
            continue
        if name_pattern.search(blob.decode("utf-8", errors="ignore")):
            offenders.append(f"{path.name}: name")
    assert not offenders, f"real personal data committed: {offenders[:5]}"


def test_the_raw_workbook_is_tracked_and_unmodified():
    """CLAUDE.md §8: the raw dataset is version-controlled and immutable."""
    from edupro.data.loader import verify_raw_workbook

    assert config.RAW_WORKBOOK.exists()
    assert verify_raw_workbook() == config.RAW_WORKBOOK_SHA256


# ---------------------------------------------------------------------------
# The declared layout matches reality
# ---------------------------------------------------------------------------
def test_no_empty_placeholder_directories_remain():
    """A directory containing only .gitkeep tells a reviewer something failed to
    generate. Data directories are the exception: they are written at runtime."""
    allowed = {config.INTERIM_DIR, config.PROCESSED_DIR}
    for gitkeep in config.PROJECT_ROOT.glob("*/.gitkeep"):
        directory = gitkeep.parent
        if directory in allowed:
            continue
        siblings = [p for p in directory.iterdir() if p.name != ".gitkeep"]
        assert siblings, f"{directory.name}/ contains only a placeholder"


def test_every_config_directory_constant_points_somewhere_real():
    """A path constant nothing writes to is dead structure."""
    for name in ("RAW_DIR", "INTERIM_DIR", "PROCESSED_DIR", "RESEARCH_DIR",
                 "MODELS_DIR", "ARTIFACTS_DIR", "DOCS_DIR", "OFFICIAL_DIR"):
        path = getattr(config, name)
        assert path.is_dir(), f"config.{name} points at a missing directory: {path}"


def test_no_docker_artifacts_exist():
    """CLAUDE.md §20."""
    for name in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore"):
        assert not (config.PROJECT_ROOT / name).exists(), f"{name} must not exist"


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------
README_SECTIONS = [
    "Project Overview", "Problem Statement", "Objectives", "Key Features",
    "Architecture", "Dataset", "Feature Engineering", "Learner Segmentation",
    "Recommendation System", "Evaluation", "Explainability", "Privacy",
    "Streamlit Application", "Screenshots / Demo", "Installation",
    "Running the Pipeline", "Running the Application",
    "Retraining / Reproducing Results", "Project Structure", "Testing",
    "Limitations", "Future Work", "Deployment", "References", "License",
]


@pytest.mark.parametrize("section", README_SECTIONS)
def test_readme_has_required_section(readme: str, section: str):
    headings = re.findall(r"^# (.+)$", readme, flags=re.M)
    assert section in headings, f"README is missing the '{section}' section"


def test_readme_states_the_headline_limitation_before_the_features(readme: str):
    """A reader who stops after the first screen must still learn the main thing."""
    opening = readme[:1800]
    assert "no recommendation method" in opening.lower()
    assert "random" in opening.lower()


@pytest.mark.parametrize("pattern", [
    r"engagement (?:increased|improved|rose|grew)",
    r"boost(?:ed|s)? (?:engagement|retention|completion)",
    r"significantly outperform",
    r"statistically significant improvement",
])
def test_readme_makes_no_unsupported_claim(readme: str, pattern: str):
    from test_paper import asserts_claim

    offenders = [line.strip() for line in readme.splitlines() if asserts_claim(line, pattern)]
    assert not offenders, f"unsupported claim asserted in the README: {offenders[:2]}"


def test_readme_images_exist(readme: str):
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", readme)
    assert images, "the README shows no screenshots"
    missing = [i for i in images if not (config.PROJECT_ROOT / i).exists()]
    assert not missing, f"README references missing images: {missing}"


def test_readme_internal_links_resolve(readme: str):
    links = re.findall(r"\]\((?!http)([^)#]+\.(?:md|html|py|toml|txt|png))\)", readme)
    missing = sorted({l for l in links if not (config.PROJECT_ROOT / l).exists()})
    assert not missing, f"broken internal links: {missing}"


def test_readme_test_count_matches_reality(readme: str):
    """A README claiming a test count it no longer has is the most common way
    documentation starts lying."""
    # sys.executable, not "python": the interpreter on PATH may be a different
    # version without pytest installed, which would make this check silently
    # unable to run rather than able to fail.
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q"],
        capture_output=True, text=True, cwd=config.PROJECT_ROOT,
    )
    match = re.search(r"(\d+) tests collected", result.stdout)
    assert match, "could not determine the collected test count"
    actual = int(match.group(1))
    claimed = {int(n) for n in re.findall(r"(\d{3}) (?:passed|tests)", readme)}
    assert actual in claimed, f"README claims {claimed or 'no'} tests; pytest collects {actual}"


# ---------------------------------------------------------------------------
# Submission checklist
# ---------------------------------------------------------------------------
def test_submission_checklist_exists_and_lists_open_items():
    assert CHECKLIST.exists()
    text = CHECKLIST.read_text(encoding="utf-8")
    assert "Known open items" in text, "the checklist must disclose open items"
    assert "Pushed to GitHub" in text


def test_screenshots_are_present_and_non_trivial():
    images = sorted(SCREENSHOTS.glob("*.png"))
    assert len(images) >= 4, f"only {len(images)} screenshots"
    for image in images:
        assert image.stat().st_size > 25_000, f"{image.name} looks blank"
