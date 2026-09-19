"""Shared page furniture: configuration, provenance, evidence labelling, charts.

Every page imports from here so the dashboard is consistent and so that the rules
the project committed to are enforced in one place rather than remembered on seven
pages:

**Every figure is labelled by what kind of thing it is.** Observed data, a model
output and a proxy carry very different weight, and a stakeholder reading a
dashboard cannot tell them apart unless the dashboard says so
(:func:`evidence`).

**Quality figures never appear without their reference.** On a 60-course catalogue
a ranker that has learned nothing still posts a Hit Rate near 0.35, so "Hit Rate
36%" alone reads as success. :func:`metric_against_reference` makes the comparison
the default rendering rather than an optional extra.

**No page computes a metric.** Pages read measured values through
:mod:`edupro.reporting` and model outputs through
:class:`edupro.inference.RecommendationService`. There is no ML in this package.
"""

from __future__ import annotations

from typing import Any, Iterable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit.errors import StreamlitAPIException

# --- evidence classes ------------------------------------------------------
#: The three kinds of number this dashboard shows, and how each is labelled.
OBSERVED = "observed"
MODEL = "model"
PROXY = "proxy"

_EVIDENCE_LABEL: dict[str, tuple[str, str]] = {
    OBSERVED: ("Observed data", "blue"),
    MODEL: ("Model output", "violet"),
    PROXY: ("Proxy metric — not a causal measurement", "orange"),
}

#: One colour per segment, legible on Streamlit's light and dark themes.
SEGMENT_COLORS: tuple[str, ...] = ("#2f6f9f", "#b4653b", "#3f7f5e", "#7a5aa0")

#: Muted grey for reference rows (random baseline, population mean).
REFERENCE_COLOR = "#8a8f98"


def configure(title: str, icon: str = "📊") -> None:
    """Apply the shared page configuration.

    Every page calls this so that it runs correctly on its own — which is how the
    tests exercise them. Under navigation the entry script has already configured
    the page, and Streamlit allows only one such call per session, so a repeat is
    ignored rather than being an error.
    """
    try:
        st.set_page_config(
            page_title=f"{title} · EduPro",
            page_icon=icon,
            layout="wide",
            initial_sidebar_state="expanded",
        )
    except StreamlitAPIException:
        pass
    st.markdown(
        """
        <style>
          [data-testid="stMetricValue"] { font-size: 1.6rem; }
          [data-testid="stMetricLabel"] { opacity: 0.85; }
          .block-container { padding-top: 2.4rem; max-width: 1400px; }
          h1 { font-size: 1.9rem; }
          h2 { font-size: 1.35rem; margin-top: 1.2rem; }
          h3 { font-size: 1.1rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def evidence(kind: str, detail: str | None = None) -> None:
    """Label what kind of number the section above or below contains."""
    label, colour = _EVIDENCE_LABEL[kind]
    st.badge(label if detail is None else f"{label} · {detail}", color=colour)


def page_header(title: str, subtitle: str, kind: str | None = None) -> None:
    st.title(title)
    st.caption(subtitle)
    if kind is not None:
        evidence(kind)


def sidebar_provenance(service: Any) -> None:
    """Which artifact set is being served. A reviewer should never have to guess."""
    manifest = service.manifest
    with st.sidebar:
        st.markdown("### Model provenance")
        st.caption(
            f"**{manifest.model_version}** · artifact set `{manifest.artifact_set_version}`  \n"
            f"Trained {manifest.created_at[:10]} · seed {manifest.seed}"
        )
        with st.expander("Details"):
            st.markdown(
                f"""
                **Source data** `{manifest.workbook_sha256[:16]}…` (verified)
                **Segmentation** {manifest.segmentation['representation']},
                k = {manifest.segmentation['n_clusters']},
                {manifest.segmentation['n_model_features']} features
                **Recommender** tiered switching
                **Training window** {manifest.training['window']}
                ({manifest.training['n_interactions']:,} interactions)

                Reported evaluation metrics come from the held-out temporal split,
                not from this fit. See *Model Analytics*.
                """
            )
        if service.problems:
            st.error("Artifact problems: " + "; ".join(service.problems))


def metric_against_reference(
    label: str,
    value: float,
    reference: float,
    reference_label: str = "random",
    fmt: str = "{:.4f}",
    help: str | None = None,
) -> None:
    """A quality metric shown with the baseline it must be read against.

    The delta is the honest part: a number that looks strong in isolation is often
    within noise of a ranker that has learned nothing.
    """
    st.metric(
        label,
        fmt.format(value),
        delta=f"{value - reference:+.4f} vs {reference_label}",
        delta_color="off",
        help=help,
        border=True,
    )


def empty_state(title: str, body: str, command: str | None = None) -> None:
    """A dead end that tells the reader how to get out of it."""
    st.info(f"**{title}**\n\n{body}")
    if command:
        st.code(command, language="bash")


def bar_chart(
    frame: pd.DataFrame,
    x: str,
    y: str,
    *,
    colors: Iterable[str] | None = None,
    x_title: str = "",
    y_title: str = "",
    horizontal: bool = False,
    height: int = 360,
    hover: str | None = None,
) -> go.Figure:
    """A plain bar chart with the project's styling and no decoration."""
    marker = {"color": list(colors)} if colors is not None else {"color": SEGMENT_COLORS[0]}
    if horizontal:
        figure = go.Figure(
            go.Bar(x=frame[y], y=frame[x], orientation="h", marker=marker, hovertemplate=hover)
        )
        figure.update_layout(xaxis_title=y_title, yaxis_title=x_title)
    else:
        figure = go.Figure(go.Bar(x=frame[x], y=frame[y], marker=marker, hovertemplate=hover))
        figure.update_layout(xaxis_title=x_title, yaxis_title=y_title)
    figure.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    figure.update_xaxes(showgrid=False)
    figure.update_yaxes(gridcolor="rgba(128,128,128,0.2)")
    return figure


def style_figure(figure: go.Figure, height: int = 420) -> go.Figure:
    """Apply the shared chart styling to a figure built elsewhere."""
    figure.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    figure.update_xaxes(gridcolor="rgba(128,128,128,0.2)")
    figure.update_yaxes(gridcolor="rgba(128,128,128,0.2)")
    return figure


def segment_color(cluster: int) -> str:
    return SEGMENT_COLORS[int(cluster) % len(SEGMENT_COLORS)]


def show(figure: go.Figure) -> None:
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
