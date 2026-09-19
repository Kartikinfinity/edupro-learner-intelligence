"""Page 1 — Executive Overview.

This page is written for a stakeholder who will read it once and act on it, so it
does three things in order: state what the system is, state what it was measured
to do, and state plainly where the measurement stops. The third is not a
disclaimer bolted on at the end — on this dataset it is the finding.
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

shell.configure("Executive Overview", "📊")
service = loaders.require_service()
shell.sidebar_provenance(service)

st.title("EduPro — Learner Segmentation & Course Recommendation")
st.caption(
    "Segment the learner base, recommend courses, and explain every recommendation. "
    "Built as a reproducible research-grade system; every figure below is traceable "
    "to an executed experiment or to the source data."
)

described = service.describe()
catalogue = loaders.catalogue_table()
learners = loaders.learner_table()

# --- what exists -----------------------------------------------------------
st.subheader("The platform")
shell.evidence(shell.OBSERVED, "counted from the source workbook")

columns = st.columns(4)
columns[0].metric("Learners", f"{described['n_learners']:,}", border=True)
columns[1].metric("Courses", f"{described['n_courses']}", border=True)
columns[2].metric("Enrollments", f"{described['n_interactions']:,}", border=True)
columns[3].metric(
    "Course categories",
    f"{catalogue['CourseCategory'].nunique()}",
    border=True,
    help="Each category holds exactly five courses.",
)

st.markdown(
    f"Learners average **{described['n_interactions'] / described['n_learners']:.2f} "
    f"enrollments**, but the median is **1** — half the learner base has taken a "
    "single course. That single fact shapes the whole recommendation design."
)

# --- what the model produces ----------------------------------------------
st.divider()
st.subheader("The segmentation")
shell.evidence(shell.MODEL, "K-Means, k = 4, behaviour-only features")

segments = loaders.segment_table()
left, right = st.columns([3, 2], gap="large")

with left:
    figure = go.Figure()
    for _, row in segments.iterrows():
        figure.add_trace(
            go.Bar(
                y=["Learner base"],
                x=[row["n_learners"]],
                name=f"{row['segment_name']} ({row['n_learners']:,})",
                orientation="h",
                marker=dict(color=shell.segment_color(row["cluster"])),
                hovertemplate=f"{row['segment_name']}<br>%{{x:,}} learners<extra></extra>",
            )
        )
    figure.update_layout(barmode="stack", showlegend=True, yaxis=dict(visible=False))
    shell.show(shell.style_figure(figure, height=220))

    st.caption(
        "Segment names are derived mechanically from each cluster's strongest "
        "deviations, using only the features the model actually saw — never chosen "
        "by hand."
    )

with right:
    for _, row in segments.iterrows():
        st.markdown(
            f"<span style='color:{shell.segment_color(row['cluster'])};font-size:1.3rem'>●</span> "
            f"**{row['segment_name']}**  \n"
            f"{row['n_learners']:,} learners · {row['share'] * 100:.1f}% · "
            f"{row.get('total_courses_mean', float('nan')):.1f} courses on average",
            unsafe_allow_html=True,
        )

# --- how recommendations are produced -------------------------------------
st.divider()
st.subheader("The recommendation system")
shell.evidence(shell.MODEL, "tiered switching recommender")

coverage = loaders.coverage_accounting()
tiers = learners["tier"].value_counts()

route_rows = [
    ("No history", "Diversified fallback", "Popularity and rating, re-ranked across categories", 0),
    ("1 course", "Content-based", "Similarity to the single course taken", int(tiers.get("minimal", 0))),
    ("2–8 courses", "Segment popularity", "What this learner's segment chooses", int(tiers.get("moderate", 0))),
    ("9+ courses", "Segment popularity", "What this learner's segment chooses", int(tiers.get("rich", 0))),
]

columns = st.columns(4)
for column, (history, route, detail, count) in zip(columns, route_rows):
    with column:
        st.markdown(f"**{history}**")
        st.markdown(f"{route}")
        st.caption(detail)
        st.caption(
            f"{count:,} learners" if count else "New learners only — none in the current base"
        )

served = coverage["learners_receiving_recommendations"]
st.success(
    f"**{served:,} of {coverage['total_learners']:,} learners receive a recommendation.** "
    f"No learner has an empty candidate list, and no learner is shown a course they "
    f"have already taken."
)

# --- what was measured -----------------------------------------------------
st.divider()
st.subheader("Validated performance")
headline = loaders.recommendation_headline()
shell.evidence(shell.MODEL, "held-out temporal split — never used for model selection")
st.caption(loaders.evaluation_caption())

columns = st.columns(4)
with columns[0]:
    shell.metric_against_reference(
        "NDCG@10", headline["deployed_ndcg"], headline["random_ndcg"],
        help="Ranking quality. The deployed method against a random ranker on the same learners.",
    )
with columns[1]:
    shell.metric_against_reference(
        "Hit Rate@10", headline["deployed_hit_rate"], headline["random_hit_rate"], fmt="{:.1%}",
        help="Share of learners whose held-out course appeared in their top 10.",
    )
proxy = loaders.engagement_lift_proxy()
with columns[2]:
    shell.metric_against_reference(
        "Engagement lift (proxy)", proxy["deployed"], proxy["random"], fmt="{:.3f}",
        help="The official impact metric. A proxy, not a causal measurement.",
    )
with columns[3]:
    quality = loaders.segmentation_quality()
    st.metric(
        "Cluster stability",
        f"{quality['mean_bootstrap_jaccard']:.3f}",
        help="Mean bootstrap Jaccard. Above 0.75 is considered reliable; all four clusters pass.",
        border=True,
    )

st.error(
    f"**The central finding: no recommendation method beat random ranking on this "
    f"dataset.** Across {headline['n_methods']} methods evaluated on a leakage-free "
    f"temporal split, **{headline['n_significant']} were significantly better than "
    f"random** — every 95% confidence interval on the difference contains zero. "
    f"Random ranking places **{headline['random_rank']}th of "
    f"{headline['n_methods'] + 1}**.\n\n"
    "This is reported here rather than in a footnote because it bounds what the "
    "system can honestly claim. It does **not** mean the pipeline is wrong: every "
    "component is tested and transfers unchanged to real data."
)

# --- key insights ----------------------------------------------------------
st.divider()
st.subheader("Key insights")

insight_columns = st.columns(2)
with insight_columns[0]:
    st.markdown(
        """
        **Half the learner base cannot be personalised.**
        54% of learners have exactly one enrollment. Tiered routing is a
        requirement here, not a refinement — and it is why the system reaches the
        whole catalogue instead of recommending the same popular courses to
        everyone.

        **Course choice is statistically indistinguishable from chance.**
        Category concentration, top-category share and item co-occurrence all fall
        inside a popularity-matched permutation null. Course popularity is
        near-uniform, so popularity carries almost no ranking information.
        """
    )
with insight_columns[1]:
    st.markdown(
        """
        **Demographics add nothing to the segmentation.**
        Clustering with and without age and gender produces an *identical*
        partition. Both are available for reporting and fairness auditing; neither
        is used as a modelling feature.

        **The segments are real and stable, but they are course-level groupings.**
        All four clusters reappear under resampling, and three of the four are
        defined by course level rather than by a behavioural signature. The
        dashboard describes them as what they are.
        """
    )

st.divider()
st.caption(
    "Where to go next — **Learner Profile** for one learner, **Recommendations** to "
    "see the system's output and its reasoning, **Segment Intelligence** and "
    "**Segment Comparison** for the groups, **Cluster Visualization** for the shape "
    "of the space, and **Model Analytics** for every measured number behind the "
    "figures above."
)
