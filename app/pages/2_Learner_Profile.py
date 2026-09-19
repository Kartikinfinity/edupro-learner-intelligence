"""Page 2 — Learner Profile Explorer.

Learners are addressed by pseudonymous ``UserID`` only. Names and email addresses
are not filtered out here; they were dropped at ingestion, so there is nothing in
the artifact set for this page to display even if it tried (ADR-0006).

Age and gender are shown because they are part of the learner record an
administrator legitimately sees. Neither is a modelling feature: the segmentation
uses behaviour only, and the page says so where it shows them.
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

shell.configure("Learner Profile", "👤")
service = loaders.require_service()
shell.sidebar_provenance(service)

shell.page_header(
    "Learner Profile Explorer",
    "Behaviour, preferences and assigned segment for one learner.",
)

learners = loaders.learner_table()
ids = loaders.learner_ids()

# --- selection -------------------------------------------------------------
with st.sidebar:
    st.markdown("### Select a learner")
    segment_filter = st.selectbox(
        "Filter by segment",
        options=["All segments", *sorted(learners["segment_name"].unique())],
    )
    tier_filter = st.selectbox(
        "Filter by history depth",
        options=["All", "minimal", "moderate", "rich"],
        help="How much history the learner has, which decides how they are served.",
    )

    pool = learners
    if segment_filter != "All segments":
        pool = pool[pool["segment_name"] == segment_filter]
    if tier_filter != "All":
        pool = pool[pool["tier"] == tier_filter]

    if pool.empty:
        shell.empty_state(
            "No learners match", "Relax one of the filters above to select a learner."
        )
        st.stop()

    learner_id = st.selectbox(
        f"Learner ({len(pool):,} available)",
        options=sorted(pool.index.tolist()),
        help="Pseudonymous identifier. No name or email exists in the artifact set.",
    )

profile = service.learner_profile(learner_id)
history = service.history(learner_id)

# --- identity and segment --------------------------------------------------
left, right = st.columns([2, 3], gap="large")

with left:
    st.subheader(learner_id)
    colour = shell.segment_color(profile["segment"])
    st.markdown(
        f"<div style='border-left:4px solid {colour};padding-left:0.9rem'>"
        f"<div style='opacity:0.7;font-size:0.85rem'>ASSIGNED SEGMENT</div>"
        f"<div style='font-size:1.15rem;font-weight:600'>{profile['segment_name']}</div>"
        f"<div style='opacity:0.7'>Segment {profile['segment']} · "
        f"served by the <b>{profile['tier']}</b>-history route</div></div>",
        unsafe_allow_html=True,
    )
    shell.evidence(shell.MODEL, "segment assigned by the clustering model")

    st.markdown("**Demographics**")
    st.caption(
        f"Age {profile['age']} · {profile['gender']}  \n"
        "Shown for completeness. Neither is used by the segmentation or the "
        "recommender — clustering with and without them produces the same partition."
    )

with right:
    st.subheader("Behaviour")
    shell.evidence(shell.OBSERVED, "aggregated from this learner's enrollments")
    columns = st.columns(4)
    columns[0].metric("Courses taken", profile["total_courses"], border=True)
    columns[1].metric(
        "Categories explored",
        profile["diversity_score"],
        help="Distinct course categories. The catalogue has 12.",
        border=True,
    )
    columns[2].metric(
        "Average rating",
        f"{profile['avg_course_rating']:.2f}",
        help="Mean rating of the courses this learner enrolled in.",
        border=True,
    )
    columns[3].metric(
        "Average spend",
        f"{profile['avg_spend']:,.0f}",
        help=(
            "Mean course price. In this dataset the transaction amount equals the "
            "course price on every row, so spending reflects catalogue choice "
            "rather than independent spending behaviour."
        ),
        border=True,
    )

    columns = st.columns(2)
    with columns[0]:
        st.markdown("**Preferences**")
        st.markdown(
            f"Category · **{profile['preferred_category']}**  \n"
            f"Level · **{profile['preferred_level']}**"
        )
    with columns[1]:
        depth = profile["learning_depth_index"]
        st.markdown("**Learning depth**")
        st.progress(
            min(max(depth / 2.0, 0.0), 1.0),
            text=f"{depth:.2f} on a 0–2 scale (Beginner → Advanced)",
        )

# --- category profile ------------------------------------------------------
st.divider()
left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader("Category profile")
    shell.evidence(shell.OBSERVED)
    share_columns = [c for c in learners.columns if c.startswith("cat_share_")]
    shares = (
        learners.loc[learner_id, share_columns]
        .rename(lambda c: c.replace("cat_share_", "").replace("_", " ").title())
        .sort_values(ascending=True)
    )
    shares = shares[shares > 0]
    if shares.empty:
        shell.empty_state("No category activity", "This learner has no enrollments on record.")
    else:
        figure = go.Figure(
            go.Bar(
                x=shares.to_numpy() * 100,
                y=shares.index,
                orientation="h",
                marker=dict(color=shell.segment_color(profile["segment"])),
                hovertemplate="%{y}: %{x:.0f}% of enrollments<extra></extra>",
            )
        )
        figure.update_layout(xaxis_title="share of enrollments (%)", showlegend=False)
        shell.show(shell.style_figure(figure, height=max(220, 34 * len(shares))))
        st.caption(
            "This share vector — not a single 'preferred category' — is what the "
            "segmentation model reads."
        )

with right:
    st.subheader("Enrollment history")
    shell.evidence(shell.OBSERVED)
    if history.empty:
        shell.empty_state(
            "No enrollments",
            "This learner has no recorded activity, so they are served the cold-start route.",
        )
    else:
        st.dataframe(
            history[["TransactionDate", "CourseName", "CourseCategory", "CourseLevel"]]
            .rename(
                columns={
                    "TransactionDate": "Date",
                    "CourseName": "Course",
                    "CourseCategory": "Category",
                    "CourseLevel": "Level",
                }
            )
            .assign(Date=lambda f: f["Date"].dt.date),
            hide_index=True,
            width="stretch",
            height=min(420, 40 + 35 * len(history)),
        )
        st.caption(f"{len(history)} enrollment{'' if len(history) == 1 else 's'}, most recent first.")

st.divider()
st.caption(
    f"To see what the system would recommend to {learner_id} and why, open "
    "**Recommendations** in the sidebar."
)
