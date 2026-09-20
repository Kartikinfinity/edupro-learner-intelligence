"""Cached access to the production model and the measured results.

The service is cached with ``st.cache_resource``: it is loaded **once per process**
and shared across sessions and page navigations, so the application never refits
anything and never re-reads the artifact set on a rerun (CLAUDE.md §21).

Derived frames are cached with ``st.cache_data``. They are cheap, but a Streamlit
page reruns top to bottom on every widget interaction, so caching them is the
difference between a responsive filter and a visibly stalling one.

Nothing here computes a model quantity. Everything is either loaded from the
artifact set through :class:`edupro.inference.RecommendationService` or read from
an experiment artifact through :mod:`edupro.reporting`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

# The app is launched from the repository root; make the package importable when
# it has not been pip-installed (which is the normal case on Streamlit Cloud).
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from edupro import reporting  # noqa: E402
from edupro.inference import RecommendationService  # noqa: E402
from edupro.persistence import ArtifactIntegrityError, ArtifactVersionError  # noqa: E402


#: Why the last load failed, if it did. A module-level variable rather than
#: ``st.session_state``: a ``cache_resource`` function runs once for the whole
#: process and its session context is not the one that later renders the error,
#: so anything written to session state there is lost. That is why the first
#: failed deployment showed an empty state with no reason attached (D-072).
_LOAD_ERROR: Exception | None = None

#: Heading, cause and remedy for each way the load can fail.
#:
#: One entry per exception type, because the three failures are not the same
#: problem and must not share a heading. The first failed deployment was an
#: *integrity* failure — the artifacts were present and readable, and their bytes
#: disagreed with the manifest — but the page announced "not found", sending the
#: reader to look for missing files that were sitting right there. An error that
#: misdiagnoses its own cause costs more than no error at all (D-074).
_FAILURE_GUIDE: dict[type[Exception], tuple[str, str, str]] = {
    ArtifactIntegrityError: (
        "Model artifacts failed their integrity check",
        "The artifact files are present, but at least one no longer hashes to the "
        "value `models/manifest.json` recorded for it. The loader refuses a set it "
        "cannot vouch for, because a half-updated set pairs a fresh model with a "
        "stale lookup table and answers confidently with the wrong numbers.",
        "Usually the committed bytes differ from the bytes that were hashed - the "
        "line-ending case is documented in `docs/deployment_guide.md` §6.1. "
        "Retraining rewrites the set and the manifest together.",
    ),
    ArtifactVersionError: (
        "Model artifacts came from a different environment",
        "The artifacts were written by library versions, a code version or a source "
        "workbook that differ from the ones running now. scikit-learn does not "
        "support loading an estimator across versions: it usually loads and then "
        "returns subtly different numbers rather than raising.",
        "Install the pinned versions in `requirements.txt`, or retrain.",
    ),
    FileNotFoundError: (
        "Model artifacts not found",
        "This dashboard serves a **persisted** model and does not train one, so the "
        "artifact set has to exist before any page can render.",
        "Generate it once; it is written to `models/` and `artifacts/production/`.",
    ),
}


@st.cache_resource(show_spinner="Loading the model…")
def load_service() -> RecommendationService | None:
    """The production model, loaded once. ``None`` when it cannot be served.

    Returning ``None`` rather than raising lets every page render a useful empty
    state naming the actual cause, instead of a stack trace.
    """
    global _LOAD_ERROR
    try:
        service = RecommendationService.load()
        _LOAD_ERROR = None
        return service
    except (ArtifactIntegrityError, ArtifactVersionError, FileNotFoundError) as error:
        _LOAD_ERROR = error
        return None


def require_service() -> RecommendationService:
    """Return the loaded service, or stop the page explaining why it could not."""
    service = load_service()
    if service is None:
        heading, cause, remedy = _FAILURE_GUIDE.get(
            type(_LOAD_ERROR),
            (
                "The model could not be loaded",
                "The artifact set could not be opened.",
                "Regenerate it and check the server log for the reason.",
            ),
        )
        st.title(heading)
        st.info(cause)
        st.caption(remedy)
        st.code("python scripts/train_production_model.py", language="bash")
        if _LOAD_ERROR is not None:
            st.error(f"**The loader reported:** {type(_LOAD_ERROR).__name__}: {_LOAD_ERROR}")
        st.stop()
    return service


@st.cache_data(show_spinner=False)
def segment_table() -> pd.DataFrame:
    """One row per segment: label, size, share and headline behaviour."""
    service = load_service()
    summary = service.segment_summary().reset_index()
    return summary


@st.cache_data(show_spinner=False)
def learner_table() -> pd.DataFrame:
    """Learner features with cluster, tier and segment name. Pseudonymous by design."""
    service = load_service()
    return service.features.copy()


@st.cache_data(show_spinner=False)
def projection_table() -> pd.DataFrame:
    """Precomputed 2D projection joined to segment labels, for the cluster view."""
    service = load_service()
    projection = service.projection.join(
        service.features[["cluster", "tier", "segment_name", "total_courses"]]
    )
    return projection.reset_index()


@st.cache_data(show_spinner=False)
def catalogue_table() -> pd.DataFrame:
    service = load_service()
    return service.catalogue.copy()


@st.cache_data(show_spinner=False)
def learner_ids() -> list[str]:
    service = load_service()
    return sorted(service.features.index.tolist())


@st.cache_data(show_spinner=False)
def segment_details() -> dict[str, Any]:
    """Segment labels, the evidence that produced them, stability and projection info."""
    return load_service().segments


# --- measured results ------------------------------------------------------
# Thin cached wrappers so a page never reaches into an artifact file itself.


@st.cache_data(show_spinner=False)
def results_available() -> dict[str, bool]:
    return reporting.artifacts_available()


@st.cache_data(show_spinner=False)
def recommendation_comparison() -> pd.DataFrame:
    return reporting.recommendation_comparison()


@st.cache_data(show_spinner=False)
def recommendation_headline() -> dict[str, Any]:
    return reporting.recommendation_headline()


@st.cache_data(show_spinner=False)
def per_tier_metrics() -> pd.DataFrame:
    return reporting.per_tier_metrics()


@st.cache_data(show_spinner=False)
def architecture_comparison() -> pd.DataFrame:
    return reporting.architecture_comparison()


@st.cache_data(show_spinner=False)
def segmentation_quality() -> dict[str, Any]:
    return reporting.segmentation_quality()


@st.cache_data(show_spinner=False)
def k_sweep() -> pd.DataFrame:
    return reporting.k_sweep()


@st.cache_data(show_spinner=False)
def k_selection() -> dict[str, Any]:
    return reporting.k_selection()


@st.cache_data(show_spinner=False)
def representation_comparison() -> pd.DataFrame:
    return reporting.representation_comparison()


@st.cache_data(show_spinner=False)
def coverage_accounting() -> dict[str, Any]:
    return reporting.coverage_accounting()


@st.cache_data(show_spinner=False)
def engagement_lift_proxy() -> dict[str, float]:
    return reporting.engagement_lift_proxy()


@st.cache_data(show_spinner=False)
def evaluation_caption() -> str:
    return reporting.evaluation_provenance().caption()


@st.cache_data(show_spinner=False)
def hierarchical_validation() -> dict[str, Any]:
    return reporting.hierarchical_validation()


@st.cache_data(show_spinner=False)
def demographic_variant_comparison() -> dict[str, Any]:
    return reporting.demographic_variant_comparison()
