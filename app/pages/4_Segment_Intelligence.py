"""Page 4 — Segment Intelligence.

Segment names are read from the artifact set, where the pipeline derived them
mechanically: rank each cluster's feature deviations, keep those beyond 0.40
population standard deviations, map them through a controlled vocabulary, and
restrict the whole procedure to features the clustering actually used. The
evidence behind each name is shown beside it, so a reader can check the label
against the numbers rather than take it on trust.
"""

from __future__ import annotations

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

shell.configure("Segment Intelligence", "🧩")
service = loaders.require_service()
shell.sidebar_provenance(service)

shell.page_header(
    "Segment Intelligence",
    "What each learner segment looks like, and the evidence behind its name.",
)

learners = loaders.learner_table()
segments = loaders.segment_table()
details = loaders.segment_details()
profiles = service.profiles

# --- overview --------------------------------------------------------------
st.subheader("Segment sizes")
shell.evidence(shell.MODEL, "K-Means, k = 4, fitted on behaviour only")

columns = st.columns(len(segments))
for column, (_, row) in zip(columns, segments.iterrows()):
    with column:
        colour = shell.segment_color(row["cluster"])
        st.markdown(
            f"<div style='border-top:4px solid {colour};padding-top:0.6rem'>"
            f"<div style='font-weight:600;min-height:3.2rem'>{row['segment_name']}</div>"
            f"<div style='font-size:1.6rem;font-weight:600'>{row['n_learners']:,}</div>"
            f"<div style='opacity:0.7'>{row['share'] * 100:.1f}% of learners</div></div>",
            unsafe_allow_html=True,
        )

# --- behavioural characteristics ------------------------------------------
st.divider()
st.subheader("Behavioural characteristics")
shell.evidence(shell.OBSERVED, "means computed within each model-assigned segment")

CHARACTERISTICS = [
    ("total_courses_mean", "Courses taken", "{:.2f}"),
    ("diversity_score_mean", "Categories explored", "{:.2f}"),
    ("avg_courses_per_category_mean", "Courses per category", "{:.2f}"),
    ("enrollment_frequency_mean", "Enrollment frequency", "{:.3f}"),
    ("activity_span_days_mean", "Activity span (days)", "{:.0f}"),
    ("avg_course_rating_mean", "Average course rating", "{:.2f}"),
    ("avg_spend_mean", "Average spend", "{:,.0f}"),
    ("learning_depth_index_mean", "Learning depth (0–2)", "{:.2f}"),
    ("free_ratio_mean", "Free-course share", "{:.0%}"),
    ("diversity_ratio_mean", "Diversity ratio", "{:.2f}"),
]

available = [(c, label, fmt) for c, label, fmt in CHARACTERISTICS if c in profiles.columns]
table = pd.DataFrame(
    {
        segments.set_index("cluster").loc[cluster, "segment_name"]: {
            label: fmt.format(profiles.loc[cluster, column])
            for column, label, fmt in available
        }
        for cluster in profiles.index
    }
)
st.dataframe(table, width="stretch")

population = learners[["total_courses", "diversity_score", "avg_course_rating", "avg_spend"]].mean()
st.caption(
    f"Population means for reference — courses {population['total_courses']:.2f}, "
    f"categories {population['diversity_score']:.2f}, "
    f"rating {population['avg_course_rating']:.2f}, "
    f"spend {population['avg_spend']:,.0f}."
)

# --- dominant categories and levels ---------------------------------------
st.divider()
left, right = st.columns(2, gap="large")

share_columns = [c for c in learners.columns if c.startswith("cat_share_")]

with left:
    st.subheader("Dominant categories")
    shell.evidence(shell.OBSERVED)
    frames = []
    for cluster in sorted(learners["cluster"].unique()):
        member_shares = learners.loc[learners["cluster"] == cluster, share_columns].mean()
        top = member_shares.sort_values(ascending=False).head(3)
        for name, value in top.items():
            frames.append(
                {
                    "segment": segments.set_index("cluster").loc[cluster, "segment_name"],
                    "cluster": cluster,
                    "category": name.replace("cat_share_", "").replace("_", " ").title(),
                    "share": value * 100,
                }
            )
    dominant = pd.DataFrame(frames)
    figure = go.Figure()
    for cluster in sorted(dominant["cluster"].unique()):
        subset = dominant[dominant["cluster"] == cluster]
        figure.add_trace(
            go.Bar(
                x=subset["share"],
                y=subset["category"],
                orientation="h",
                name=str(subset["segment"].iloc[0])[:34],
                marker=dict(color=shell.segment_color(cluster)),
                hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
            )
        )
    figure.update_layout(xaxis_title="mean share of enrollments (%)", barmode="group")
    shell.show(shell.style_figure(figure, height=460))
    st.caption(
        "Top three categories per segment. The spread is narrow, which is "
        "consistent with the audit's finding that category choice is close to "
        "uniform across the catalogue."
    )

with right:
    st.subheader("Course levels")
    shell.evidence(shell.OBSERVED)
    composition = (
        pd.crosstab(learners["cluster"], learners["preferred_level"], normalize="index") * 100
    )
    order = [c for c in ("Beginner", "Intermediate", "Advanced") if c in composition.columns]
    figure = go.Figure()
    shades = {"Beginner": "#6fa8c9", "Intermediate": "#3f7f5e", "Advanced": "#7a5aa0"}
    for level in order:
        figure.add_trace(
            go.Bar(
                x=composition.index.map(
                    lambda c: segments.set_index("cluster").loc[c, "segment_name"][:26]
                ),
                y=composition[level],
                name=level,
                marker=dict(color=shades[level]),
                hovertemplate=f"{level}: %{{y:.0f}}%<extra></extra>",
            )
        )
    figure.update_layout(barmode="stack", yaxis_title="share of segment (%)")
    shell.show(shell.style_figure(figure, height=460))
    st.caption(
        "Three of the four segments are effectively pure on course level. This is "
        "the honest description of what the segmentation found: a course-level "
        "grouping, not a psychological typology."
    )

# --- naming evidence -------------------------------------------------------
st.divider()
st.subheader("How each name was derived")
shell.evidence(shell.MODEL, "deviation-ranked, restricted to features the model used")

for cluster_key, info in sorted(details["segments"].items(), key=lambda kv: int(kv[0])):
    cluster = int(cluster_key)
    with st.expander(f"{info['label']}  ·  {info['n_learners']:,} learners"):
        if info.get("is_neutral"):
            st.caption(info.get("note", "No feature deviates enough to support a name."))
        evidence_rows = info.get("evidence", [])
        if evidence_rows:
            st.dataframe(
                pd.DataFrame(evidence_rows).rename(
                    columns={
                        "feature": "Feature",
                        "deviation": "Deviation (population SD)",
                        "phrase": "Contributed phrase",
                    }
                ),
                hide_index=True,
                width="stretch",
            )
        if "level_purity" in info:
            st.caption(
                f"{info['level_purity']:.0%} of this segment prefers "
                f"**{info['dominant_level']}** courses, which is why the level appears "
                "in the name."
            )
        stability = details.get("stability", {})
        per_cluster = stability.get("per_cluster_jaccard", {})
        if str(cluster) in per_cluster:
            st.caption(
                f"Stability: bootstrap Jaccard **{per_cluster[str(cluster)]:.3f}** "
                "(above 0.75 is considered reliable)."
            )

st.caption(details.get("naming_method", ""))
