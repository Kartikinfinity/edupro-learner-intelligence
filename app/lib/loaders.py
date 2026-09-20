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
from dataclasses import dataclass
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


@dataclass(frozen=True)
class LoadOutcome:
    """The model, or the reason there isn't one. **One cached value, not two.**

    The failure reason has now escaped twice. First it was written to
    ``st.session_state`` from inside a ``@st.cache_resource`` function, whose
    session context is not the one that later renders the page (D-073). Then it
    was a module-level variable — which is still *parallel* state: the cache
    holds ``None`` and the variable holds the reason, and nothing keeps them
    together. A rerun that hits the cache without re-running the body renders
    from a variable the cached value never set, and the page falls back to "could
    not be loaded" with nothing attached (D-076).

    Returning both in one object removes the failure mode rather than relocating
    it: whatever the cache hands back carries its own explanation.
    """

    service: RecommendationService | None
    error: Exception | None = None

    @property
    def ok(self) -> bool:
        return self.service is not None


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
        "At least one file listed in `models/manifest.json` is missing, or is "
        "present but no longer hashes to the value recorded for it. The loader "
        "refuses a set it cannot vouch for, because a half-updated set pairs a "
        "fresh model with a stale lookup table and answers confidently with the "
        "wrong numbers. **The line below says which files and which problem.**",
        "If they are reported *missing* while the files are plainly there, compare "
        "the manifest's path separators with this platform's. If they are reported "
        "*changed*, the committed bytes differ from the bytes that were hashed. "
        "Both cases are documented in `docs/deployment_guide.md` §6.1.",
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
def load_outcome() -> LoadOutcome:
    """The production model, loaded once — or the reason it could not be.

    Catching rather than raising lets every page render a useful empty state
    naming the actual cause, instead of a stack trace. ``Exception`` is
    deliberately broad: the three expected failures are matched to specific
    guidance below, and anything else must still reach the page rather than
    disappearing, which is how the last two outages stayed invisible.
    """
    try:
        return LoadOutcome(RecommendationService.load())
    except Exception as error:  # noqa: BLE001 - see docstring
        return LoadOutcome(None, error)


def load_service() -> RecommendationService | None:
    """The model, or ``None``. Kept for the cached table helpers below."""
    return load_outcome().service


def require_service() -> RecommendationService:
    """Return the loaded service, or stop the page explaining why it could not."""
    outcome = load_outcome()
    if outcome.ok:
        return outcome.service

    error = outcome.error
    heading, cause, remedy = _FAILURE_GUIDE.get(
        type(error),
        (
            "The model could not be loaded",
            "The artifact set could not be opened. The exact error is below.",
            "Regenerate the set, and check the server log for the full traceback.",
        ),
    )
    st.title(heading)
    st.info(cause)
    st.caption(remedy)
    st.code("python scripts/train_production_model.py", language="bash")
    # Unconditional: an empty state with no reason is what made the last two
    # deployment failures take three attempts to diagnose (D-073, D-076).
    st.error(
        f"**The loader reported:** `{type(error).__name__}`: {error}"
        if error is not None
        else "**No reason was recorded** — this should be impossible; "
        "please report it with the server log."
    )
    st.stop()


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
