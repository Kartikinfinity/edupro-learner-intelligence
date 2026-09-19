"""Tests for the Streamlit dashboard and the reporting layer beneath it.

Two things are checked, and the second matters more than the first.

**Every page runs.** Streamlit pages fail at runtime, not at import, so a broken
chart expression only surfaces when someone opens the page. ``AppTest`` executes
each page exactly as the server would and fails the build instead.

**No page can display a fabricated number.** Every measured figure reaches the
dashboard through :mod:`edupro.reporting`, which reads experiment artifacts and
computes nothing. The tests here assert that the values it returns match the
artifacts, and that the representation table reproduces the frozen document —
which is what stops the dashboard and the research report drifting apart.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from edupro import config, reporting

APP_DIR = config.PROJECT_ROOT / "app"
ENTRY = APP_DIR / "streamlit_app.py"
PAGES = sorted((APP_DIR / "pages").glob("*.py"))

#: Generous: the first page to run loads the artifact set from disk.
TIMEOUT = 180


def _run(path: Path) -> AppTest:
    app = AppTest.from_file(str(path), default_timeout=TIMEOUT)
    app.run()
    return app


#: The overview is a page like any other; the entry script only navigates.
OVERVIEW = APP_DIR / "pages" / "1_Executive_Overview.py"


@pytest.fixture(scope="module")
def entry_app() -> AppTest:
    return _run(OVERVIEW)


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------
def test_the_dashboard_has_the_seven_required_pages():
    assert ENTRY.exists()
    assert len(PAGES) == 7, [p.name for p in PAGES]


def test_page_names_cover_the_official_capabilities():
    names = " ".join(p.stem.lower() for p in PAGES)
    for capability in ("executive_overview", "learner_profile", "recommendations",
                       "segment_intelligence", "cluster_visualization",
                       "segment_comparison", "model_analytics"):
        assert capability in names


def test_navigation_declares_every_page():
    """A page file that is never registered would be unreachable in the app."""
    entry = ENTRY.read_text(encoding="utf-8")
    for page in PAGES:
        assert f"pages/{page.name}" in entry, f"{page.name} is not in the navigation"


# ---------------------------------------------------------------------------
# Every page runs
# ---------------------------------------------------------------------------
def test_overview_page_runs_without_exception(entry_app):
    assert not entry_app.exception, [str(e) for e in entry_app.exception]
    assert entry_app.title[0].value.startswith("EduPro")


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.stem)
def test_page_runs_without_exception(page: Path):
    app = _run(page)
    assert not app.exception, [str(e) for e in app.exception]
    assert len(app.title) >= 1, "every page states what it is"


def test_overview_shows_the_population_and_the_segments(entry_app):
    values = {m.label: m.value for m in entry_app.metric}
    assert values["Learners"] == "3,000"
    assert values["Courses"] == "60"
    assert values["Enrollments"] == "10,000"


def test_overview_reports_the_headline_finding(entry_app):
    """The finding that bounds every claim must be on the first screen, not buried."""
    text = " ".join(e.value for e in entry_app.error)
    assert "no recommendation method beat random" in text.lower()


# ---------------------------------------------------------------------------
# The application uses the production model
# ---------------------------------------------------------------------------
def test_the_app_contains_no_machine_learning():
    """The dashboard must call the production modules, not reimplement them."""
    banned = ("KMeans(", "fit_transform", ".fit(", "cosine_similarity", "train(")
    offenders = []
    for path in [ENTRY, *PAGES, *(APP_DIR / "lib").glob("*.py")]:
        source = path.read_text(encoding="utf-8")
        for token in banned:
            if token in source:
                offenders.append(f"{path.name}: {token}")
    assert not offenders, offenders


def test_pages_reach_the_model_only_through_the_service():
    for path in PAGES:
        source = path.read_text(encoding="utf-8")
        assert "RecommendationService.load" not in source, (
            f"{path.name} loads the model directly; it must use the cached loader"
        )


def test_the_service_is_cached_as_a_resource():
    """A per-rerun reload would refit the counting structures on every click."""
    source = (APP_DIR / "lib" / "loaders.py").read_text(encoding="utf-8")
    assert "@st.cache_resource" in source
    assert source.count("@st.cache_data") >= 10


# ---------------------------------------------------------------------------
# Reporting: no metric is typed in
# ---------------------------------------------------------------------------
def test_recommendation_comparison_matches_the_artifact():
    raw = json.loads(reporting.RECOMMENDATION_RESULTS.read_text(encoding="utf-8"))
    frame = reporting.recommendation_comparison()
    assert len(frame) == len(raw["test"])
    for _, row in frame.iterrows():
        stored = raw["test"][row["method"]]["overall"]["10"]
        assert row["ndcg"] == stored["ndcg"]
        assert row["coverage"] == stored["coverage"]


def test_the_random_reference_is_always_present():
    frame = reporting.recommendation_comparison()
    assert frame["is_reference"].sum() == 1
    assert frame["is_deployed"].sum() == 1


def test_headline_reports_zero_significant_methods():
    """If this ever changes, the dashboard's framing must change with it."""
    headline = reporting.recommendation_headline()
    assert headline["n_significant"] == 0
    assert headline["random_rank"] == 7


def test_engagement_lift_cannot_be_read_without_its_reference():
    """The proxy is meaningless alone, so the accessor returns both values."""
    lift = reporting.engagement_lift_proxy()
    assert set(lift) == {"deployed", "random"}
    assert lift["random"] > 1.0


def test_representation_table_reproduces_the_frozen_document():
    """The dashboard and ARCHITECTURE_FREEZE.md must not drift apart.

    'Best k' applies the pre-registered size constraint, not the raw silhouette
    maximum — an unconstrained table would rank arms by how far they were allowed
    to fragment.
    """
    frozen = {
        "B_proportion": (4, 0.1946),
        "B_robust_scaled": (2, 0.7159),
        "B_no_category": (10, 0.4349),
        "B_facets": (2, 0.3933),
        "B_no_level": (9, 0.3027),
        "B_proportion_weighted": (4, 0.2922),
        "B_decorrelated": (10, 0.2666),
        "B_teacher": (2, 0.2212),
        "A_proportion": (9, 0.2188),
        "B_one_hot": (2, 0.2115),
    }
    frame = reporting.representation_comparison().set_index("representation")
    assert set(frame.index) == set(frozen)
    for name, (k, silhouette) in frozen.items():
        assert int(frame.loc[name, "best_k"]) == k, name
        assert abs(float(frame.loc[name, "silhouette"]) - silhouette) < 5e-5, name


def test_segmentation_quality_matches_the_frozen_configuration():
    quality = reporting.segmentation_quality()
    assert quality["k"] == 4
    assert abs(quality["silhouette"] - 0.1946) < 5e-5
    assert quality["min_cluster_share"] >= 0.05


def test_k_sweep_carries_the_constraints_that_decided_k():
    sweep = reporting.k_sweep()
    assert {"silhouette", "min_cluster_share", "n_unstable_clusters"} <= set(sweep.columns)
    selected = sweep[sweep["k"] == 4].iloc[0]
    assert selected["n_unstable_clusters"] == 0
    # Silhouette alone would have chosen a k whose clusters do not survive resampling.
    best_silhouette = sweep.loc[sweep["silhouette"].idxmax()]
    assert best_silhouette["k"] != 4
    assert best_silhouette["n_unstable_clusters"] > 0


def test_missing_artifact_raises_an_actionable_error(tmp_path, monkeypatch):
    monkeypatch.setattr(reporting, "RECOMMENDATION_RESULTS", tmp_path / "absent.json")
    reporting.recommendation_results.cache_clear()
    try:
        with pytest.raises(reporting.MissingArtifactError, match="scripts/"):
            reporting.recommendation_results()
    finally:
        reporting.recommendation_results.cache_clear()


def test_artifacts_available_reports_every_source():
    available = reporting.artifacts_available()
    assert set(available) == {"segmentation", "recommendation", "architecture", "audit"}
    assert all(available.values())


# ---------------------------------------------------------------------------
# Privacy
# ---------------------------------------------------------------------------
def test_no_page_references_a_personally_identifying_column():
    for path in [ENTRY, *PAGES, *(APP_DIR / "lib").glob("*.py")]:
        source = path.read_text(encoding="utf-8")
        for column in config.PII_COLUMNS:
            assert column not in source, f"{path.name} references {column}"
