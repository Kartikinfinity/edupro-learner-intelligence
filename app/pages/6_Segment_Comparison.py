"""Page 6 — Segment Comparison.

Side-by-side comparison across the characteristics the brief asks to compare.

The comparison is expressed against the **population mean** rather than in raw
units, because raw means invite a reader to compare quantities on different scales
— 9.65 courses against a 3.7 rating tells nobody anything. Deviation in population
standard deviations is also exactly the quantity the naming procedure used, so the
chart and the segment names are reading the same evidence.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Streamlit puts the *entry script's* directory on sys.path, so `lib` resolves
# when this page is reached through navigation but not when the file is run or
# tested on its own. Adding the app directory explicitly makes both work.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import loaders, shell

shell.configure("Segment Comparison", "⚖️")
service = loaders.require_service()
shell.sidebar_provenance(service)

shell.page_header(
    "Segment Comparison",
    "How the segments differ across the characteristics that define them.",
)

learners = loaders.learner_table()
segments = loaders.segment_table().set_index("cluster")

COMPARABLE = {
    "total_courses": "Courses taken",
    "diversity_score": "Categories explored",
    "avg_courses_per_category": "Courses per category",
    "enrollment_frequency": "Enrollment frequency",
    "activity_span_days": "Activity span (days)",
    "avg_course_rating": "Average course rating",
    "avg_spend": "Average spend",
    "learning_depth_index": "Learning depth",
    "free_ratio": "Free-course share",
    "diversity_ratio": "Diversity ratio",
}
available = {c: label for c, label in COMPARABLE.items() if c in learners.columns}

with st.sidebar:
    st.markdown("### Compare")
    chosen = st.multiselect(
        "Characteristics",
        options=list(available),
        default=[
            c
            for c in ("total_courses", "diversity_score", "learning_depth_index", "avg_spend")
            if c in available
        ],
        format_func=lambda c: available[c],
    )
    shown_segments = st.multiselect(
        "Segments",
        options=sorted(segments.index.tolist()),
        default=sorted(segments.index.tolist()),
        format_func=lambda c: segments.loc[c, "segment_name"],
    )

if not chosen or not shown_segments:
    shell.empty_state(
        "Nothing selected",
        "Choose at least one characteristic and one segment in the sidebar.",
    )
    st.stop()

subset = learners[learners["cluster"].isin(shown_segments)]

# --- deviation view --------------------------------------------------------
st.subheader("Difference from the population average")
shell.evidence(shell.OBSERVED, "segment means expressed in population standard deviations")

population_mean = learners[chosen].mean()
population_std = learners[chosen].std().replace(0, np.nan)
deviations = (subset.groupby("cluster")[chosen].mean() - population_mean) / population_std

figure = go.Figure()
for cluster in shown_segments:
    if cluster not in deviations.index:
        continue
    figure.add_trace(
        go.Bar(
            x=[available[c] for c in chosen],
            y=deviations.loc[cluster, chosen].to_numpy(),
            name=str(segments.loc[cluster, "segment_name"])[:34],
            marker=dict(color=shell.segment_color(cluster)),
            hovertemplate="%{x}: %{y:+.2f} SD<extra></extra>",
        )
    )
figure.add_hline(y=0, line_color=shell.REFERENCE_COLOR, line_width=1)
figure.update_layout(barmode="group", yaxis_title="deviation from population mean (SD)")
shell.show(shell.style_figure(figure, height=440))
st.caption(
    f"Zero is the population average across all {len(learners):,} learners. A bar "
    "beyond ±0.40 SD is what the naming procedure treats as a defining characteristic."
)

# --- absolute values -------------------------------------------------------
st.divider()
st.subheader("Absolute values")
shell.evidence(shell.OBSERVED)

table = subset.groupby("cluster")[chosen].mean()
table.index = [segments.loc[c, "segment_name"] for c in table.index]
table.columns = [available[c] for c in table.columns]
population_row = pd.DataFrame(
    [learners[chosen].mean().to_numpy()],
    index=["— Population average —"],
    columns=table.columns,
)
st.dataframe(
    pd.concat([table, population_row]).style.format("{:,.2f}"),
    width="stretch",
)

# --- category profile heatmap ---------------------------------------------
st.divider()
st.subheader("Category preference by segment")
shell.evidence(shell.OBSERVED, "mean category share within each segment")

share_columns = [c for c in learners.columns if c.startswith("cat_share_")]
heat = subset.groupby("cluster")[share_columns].mean() * 100
heat.index = [str(segments.loc[c, "segment_name"])[:34] for c in heat.index]
heat.columns = [c.replace("cat_share_", "").replace("_", " ").title() for c in heat.columns]

figure = go.Figure(
    go.Heatmap(
        z=heat.to_numpy(),
        x=heat.columns.tolist(),
        y=heat.index.tolist(),
        colorscale="Blues",
        hovertemplate="%{y}<br>%{x}: %{z:.1f}%<extra></extra>",
        colorbar=dict(title="%"),
    )
)
shell.show(shell.style_figure(figure, height=110 + 70 * len(heat)))
st.caption(
    "The colour range is narrow by design of the data, not by design of the chart: "
    "the audit found category choice close to uniform, so no segment is dominated "
    "by one subject area."
)

# --- history depth ---------------------------------------------------------
st.divider()
st.subheader("How each segment is served")
shell.evidence(shell.MODEL, "routing tier, assigned from enrollment history")

composition = pd.crosstab(subset["cluster"], subset["tier"], normalize="index") * 100
composition.index = [str(segments.loc[c, "segment_name"])[:34] for c in composition.index]
order = [t for t in ("minimal", "moderate", "rich") if t in composition.columns]
shades = {"minimal": "#c9a26f", "moderate": "#3f7f5e", "rich": "#2f6f9f"}

figure = go.Figure()
for tier in order:
    figure.add_trace(
        go.Bar(
            x=composition.index,
            y=composition[tier],
            name=tier,
            marker=dict(color=shades[tier]),
            hovertemplate=f"{tier}: %{{y:.0f}}%<extra></extra>",
        )
    )
figure.update_layout(barmode="stack", yaxis_title="share of segment (%)")
shell.show(shell.style_figure(figure, height=400))
st.caption(
    "Segments differ in how much history their members have, so they are served by "
    "different recommenders. A segment dominated by single-course learners is served "
    "mostly by content matching, not by segment popularity."
)
