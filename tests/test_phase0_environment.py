"""Phase 0 acceptance tests.

These tests assert only what Phase 0 is responsible for: that the environment
is usable, that the repository layout exists, and that the authoritative source
materials are present and byte-for-byte unmodified. They deliberately assert
nothing about data content or model behaviour - that belongs to later phases.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

from edupro import config


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
def test_python_version_is_within_supported_range():
    """Python must be >=3.11 and <3.14 (see ADR-0002: Streamlit Community Cloud
    defaults to 3.12, so the project stays near that default rather than on the
    newest interpreter)."""
    assert (3, 11) <= sys.version_info[:2] < (3, 14), (
        f"Unsupported Python {sys.version_info[:3]}; expected >=3.11,<3.14"
    )


@pytest.mark.parametrize(
    "module_name",
    [
        "pandas",
        "numpy",
        "scipy",
        "sklearn",
        "matplotlib",
        "seaborn",
        "plotly",
        "streamlit",
        "openpyxl",
        "pyarrow",
        "joblib",
        "yaml",
    ],
)
def test_runtime_dependency_is_importable(module_name):
    pytest.importorskip(module_name, reason=f"{module_name} is a required runtime dependency")


def test_core_modelling_stack_is_functional():
    """A minimal end-to-end exercise of the algorithms the project depends on:
    scaling -> K-Means -> silhouette, plus hierarchical clustering."""
    import numpy as np
    from scipy.cluster.hierarchy import fcluster, linkage
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    rng = np.random.default_rng(config.RANDOM_SEED)
    # Three well-separated blobs, so the assertions below are about the stack
    # working, not about any property of the EduPro data.
    blobs = np.vstack(
        [rng.normal(loc=loc, scale=0.35, size=(60, 4)) for loc in (-5.0, 0.0, 5.0)]
    )
    scaled = StandardScaler().fit_transform(blobs)

    labels = KMeans(n_clusters=3, n_init=10, random_state=config.RANDOM_SEED).fit_predict(scaled)
    assert len(set(labels)) == 3
    assert silhouette_score(scaled, labels) > 0.5

    hierarchical = fcluster(linkage(scaled, method="ward"), t=3, criterion="maxclust")
    assert len(set(hierarchical)) == 3


def test_kmeans_is_deterministic_under_the_project_seed():
    """Reproducibility is a hard project requirement: the same seed must give
    the same labels."""
    import numpy as np
    from sklearn.cluster import KMeans

    rng = np.random.default_rng(config.RANDOM_SEED)
    data = rng.normal(size=(200, 5))

    def fit():
        return KMeans(n_clusters=4, n_init=10, random_state=config.RANDOM_SEED).fit_predict(data)

    assert (fit() == fit()).all()


def test_seaborn_plots_on_the_installed_pandas_major_version():
    """Guards the known risk recorded in ADR-0004.

    seaborn 0.13.2 predates pandas 3.x, so the plot types this project will
    actually use are exercised here against the installed pandas. If this test
    fails, the documented fallback is to pin ``pandas>=2.2,<3``.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    import seaborn as sns

    rng = np.random.default_rng(config.RANDOM_SEED)
    frame = pd.DataFrame(
        {
            "value": rng.normal(size=200),
            "spend": rng.gamma(2.0, 30.0, size=200),
            "segment": rng.choice(["A", "B", "C"], size=200),
        }
    )

    for plot in (
        lambda ax: sns.histplot(data=frame, x="value", ax=ax),
        lambda ax: sns.boxplot(data=frame, x="segment", y="spend", ax=ax),
        lambda ax: sns.countplot(data=frame, x="segment", ax=ax),
        lambda ax: sns.barplot(data=frame, x="segment", y="spend", ax=ax),
        lambda ax: sns.scatterplot(data=frame, x="value", y="spend", hue="segment", ax=ax),
        lambda ax: sns.heatmap(
            frame[["value", "spend"]].corr(numeric_only=True), annot=True, ax=ax
        ),
    ):
        figure, axes = plt.subplots()
        plot(axes)
        plt.close(figure)


# ---------------------------------------------------------------------------
# Repository layout
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "directory",
    [
        config.RAW_DIR,
        config.INTERIM_DIR,
        config.PROCESSED_DIR,
        config.OFFICIAL_DIR,
        config.RESEARCH_DIR,
        config.EXPERIMENTS_DIR,
        config.MODELS_DIR,
        config.ARTIFACTS_DIR,
        config.DOCS_DIR,
        config.FIGURES_DIR,
    ],
)
def test_required_directory_exists(directory):
    assert directory.is_dir(), f"Missing required directory: {directory}"


def test_package_boundaries_exist():
    """CLAUDE.md section 18 requires an explicit separation of pipeline stages."""
    package_root = config.PROJECT_ROOT / "src" / "edupro"
    for stage in (
        "data",
        "features",
        "segmentation",
        "recommendation",
        "evaluation",
        "explainability",
    ):
        assert (package_root / stage / "__init__.py").is_file(), f"Missing stage package: {stage}"


def test_no_docker_artifacts_are_present():
    """CLAUDE.md section 20 forbids Docker in this project."""
    forbidden = ["Dockerfile", "dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore"]
    found = [name for name in forbidden if (config.PROJECT_ROOT / name).exists()]
    assert not found, f"Docker artifacts must not exist: {found}"


# ---------------------------------------------------------------------------
# Source material integrity
# ---------------------------------------------------------------------------
def test_raw_workbook_is_present_and_unmodified():
    assert config.RAW_WORKBOOK.is_file(), f"Missing dataset: {config.RAW_WORKBOOK}"
    assert sha256(config.RAW_WORKBOOK) == config.RAW_WORKBOOK_SHA256, (
        "The raw workbook has changed. data/raw/ is immutable (CLAUDE.md section 8)."
    )


def test_official_documentation_is_present_and_unmodified():
    assert config.OFFICIAL_DOCUMENTATION.is_file(), (
        f"Missing official documentation: {config.OFFICIAL_DOCUMENTATION}"
    )
    assert sha256(config.OFFICIAL_DOCUMENTATION) == config.OFFICIAL_DOCUMENTATION_SHA256, (
        "The official documentation PDF has changed; it must remain unmodified."
    )


def test_workbook_exposes_the_expected_sheets():
    import openpyxl

    workbook = openpyxl.load_workbook(config.RAW_WORKBOOK, read_only=True)
    try:
        sheet_names = set(workbook.sheetnames)
    finally:
        workbook.close()
    assert set(config.ALL_SHEETS) == sheet_names, (
        f"Workbook sheets changed: expected {config.ALL_SHEETS}, found {sorted(sheet_names)}"
    )
