"""Page 5 — Cluster Visualization.

The projection shown here is a **picture of the model, not the model**. Three
things follow, and the page states all three rather than leaving a viewer to infer
them from a scatter plot:

1. The clustering is fitted in the full 25-dimensional feature space. These two
   axes are a lossy view of it, and the page prints exactly how lossy.
2. Clusters that overlap in this view may be cleanly separated in the space the
   model actually uses. Visual overlap is not evidence of a bad segmentation, and
   visual separation is not evidence of a good one.
3. The coordinates are precomputed by the training pipeline, not fitted here. A
   projection refitted per session would move the points between page loads and
   would break the rule that the application fits nothing.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

# Streamlit puts the *entry script's* directory on sys.path, so `lib` resolves
# when this page is reached through navigation but not when the file is run or
# tested on its own. Adding the app directory explicitly makes both work.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import loaders, shell

shell.configure("Cluster Visualization", "🗺️")
service = loaders.require_service()
shell.sidebar_provenance(service)

shell.page_header(
    "Cluster Visualization",
    "A two-dimensional view of the segmentation space.",
)

if service.projection.empty:
    shell.empty_state(
        "No projection in this artifact set",
        "The 2D view is precomputed during training. Regenerate the artifacts to "
        "produce it:",
        "python scripts/train_production_model.py",
    )
    st.stop()

projection = loaders.projection_table()
details = loaders.segment_details()
info = details.get("projection", {})
explained = float(info.get("explained_variance_total", 0.0))

# --- the caveat, before the picture ---------------------------------------
st.warning(
    f"**This is a visualisation, not the model.** The segmentation is fitted in "
    f"**{info.get('n_source_dimensions', 25)} dimensions**; these two principal "
    f"components carry **{explained:.1%}** of the variance in that space. Segments "
    f"that overlap here may be well separated in the space the model uses, and "
    f"apparent distance on this plot is not the distance the model measures."
)
shell.evidence(shell.MODEL, f"PCA, {explained:.1%} of variance retained")

# --- controls --------------------------------------------------------------
with st.sidebar:
    st.markdown("### View")
    visible = st.multiselect(
        "Segments",
        options=sorted(projection["segment_name"].unique()),
        default=sorted(projection["segment_name"].unique()),
    )
    size_by_activity = st.toggle(
        "Size points by courses taken",
        value=False,
        help="Marker area reflects enrollment count, an observed quantity.",
    )
    opacity = st.slider("Point opacity", 0.1, 1.0, 0.55, 0.05)

shown = projection[projection["segment_name"].isin(visible)]
if shown.empty:
    shell.empty_state("No segments selected", "Choose at least one segment in the sidebar.")
    st.stop()

# --- the plot --------------------------------------------------------------
figure = go.Figure()
for cluster in sorted(shown["cluster"].unique()):
    subset = shown[shown["cluster"] == cluster]
    figure.add_trace(
        go.Scattergl(
            x=subset["pc1"],
            y=subset["pc2"],
            mode="markers",
            name=f"{subset['segment_name'].iloc[0]} ({len(subset):,})",
            marker=dict(
                color=shell.segment_color(cluster),
                size=(4 + subset["total_courses"] * 0.8) if size_by_activity else 5,
                opacity=opacity,
                line=dict(width=0),
            ),
            customdata=subset[["UserID", "total_courses", "tier"]],
            hovertemplate=(
                "%{customdata[0]}<br>%{customdata[1]} courses · "
                "%{customdata[2]} history<extra></extra>"
            ),
        )
    )
figure.update_layout(
    xaxis_title=f"PC1 ({info.get('explained_variance_ratio', [0, 0])[0]:.1%} of variance)",
    yaxis_title=f"PC2 ({info.get('explained_variance_ratio', [0, 0])[1]:.1%} of variance)",
)
shell.show(shell.style_figure(figure, height=620))

st.caption(
    f"{len(shown):,} learners shown. Hover for the pseudonymous identifier and "
    "enrollment count."
)

# --- what the numbers say instead -----------------------------------------
st.divider()
st.subheader("What the measurements say")
st.caption(
    "Because the picture cannot settle whether the segmentation is good, the "
    "quantities that can are shown here."
)

quality = loaders.segmentation_quality()
columns = st.columns(4)
columns[0].metric(
    "Silhouette",
    f"{quality['silhouette']:.4f}",
    help=(
        "Cluster separation in the full feature space, from -1 to 1. This value is "
        "weak, and the project reports it as weak."
    ),
    border=True,
)
columns[1].metric(
    "Intra-cluster similarity",
    f"{quality['intra_cluster_similarity']:.3f}",
    help="Behavioural consistency within segments — the brief's required measure.",
    border=True,
)
columns[2].metric(
    "Mean bootstrap Jaccard",
    f"{quality['mean_bootstrap_jaccard']:.3f}",
    help="Do the same clusters reappear when learners are resampled? All four do.",
    border=True,
)
columns[3].metric(
    "Smallest segment",
    f"{quality['min_cluster_share']:.1%}",
    help="Every segment must hold at least 5% of learners to be actionable.",
    border=True,
)
shell.evidence(shell.MODEL, "measured on the held-out fit window, not on this projection")

st.info(
    "**Read together:** the silhouette is weak, so the segments are not "
    "well-separated blobs — which is why they overlap in the plot above. But every "
    "segment reappears under resampling, so they are not noise either. The segments "
    "are real and stable groupings in a space without wide gaps between them."
)
