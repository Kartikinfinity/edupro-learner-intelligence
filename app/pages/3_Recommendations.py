"""Page 3 — Personalized Recommendations.

Every list on this page comes from ``RecommendationService.recommend``, the same
call the command line and the tests use. The page ranks nothing, filters nothing
and scores nothing itself.

Two things this page must do that a conventional recommendation UI does not:

**Show the reference.** The measured quality caveat travels with the result object
and is displayed with the list, because a top-10 presented without it implies an
accuracy that was not demonstrated.

**Expose the cold-start route.** No existing learner has zero history, so the
diversified fallback — the route selected on measured evidence — would otherwise
never be visible to a reviewer. The "new learner" mode reaches it deliberately.
"""

from __future__ import annotations

import streamlit as st

# Streamlit puts the *entry script's* directory on sys.path, so `lib` resolves
# when this page is reached through navigation but not when the file is run or
# tested on its own. Adding the app directory explicitly makes both work.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import loaders, shell
from edupro.inference import InferenceError

shell.configure("Recommendations", "🎯")
service = loaders.require_service()
shell.sidebar_provenance(service)

shell.page_header(
    "Personalized Recommendations",
    "Ranked courses with the reason each one appears.",
)

learners = loaders.learner_table()
catalogue = loaders.catalogue_table()

# --- who, and with what filters -------------------------------------------
with st.sidebar:
    st.markdown("### Recommend for")
    mode = st.radio(
        "Learner",
        options=["Existing learner", "New learner (cold start)"],
        help=(
            "Every learner in this dataset has at least one enrollment, so the "
            "cold-start route is only reachable by simulating a new arrival."
        ),
    )
    if mode == "Existing learner":
        segment_filter = st.selectbox(
            "Filter by segment", options=["All segments", *sorted(learners["segment_name"].unique())]
        )
        pool = learners if segment_filter == "All segments" else learners[
            learners["segment_name"] == segment_filter
        ]
        learner_id = st.selectbox("Learner", options=sorted(pool.index.tolist()))
    else:
        learner_id = "NEW-LEARNER"
        st.caption(
            "A learner the system has never seen. No history means nothing to "
            "personalise from, so the fallback offers breadth instead."
        )

    st.markdown("### Filters")
    category = st.selectbox(
        "Category", options=["Any", *sorted(catalogue["CourseCategory"].unique())]
    )
    level = st.selectbox("Level", options=["Any", "Beginner", "Intermediate", "Advanced"])
    k = st.slider("Number of recommendations", min_value=3, max_value=20, value=10)

try:
    result = service.recommend(
        learner_id,
        k=k,
        category=None if category == "Any" else category,
        level=None if level == "Any" else level,
    )
except InferenceError as error:
    shell.empty_state(
        "No courses match these filters",
        f"{error}\n\nWiden the category or level filter in the sidebar.",
    )
    st.stop()

# --- context for the list --------------------------------------------------
columns = st.columns([2, 1, 1, 1])
with columns[0]:
    if result.is_known_learner:
        st.markdown(
            f"**{result.user_id}** · "
            f"<span style='color:{shell.segment_color(result.segment)}'>●</span> "
            f"{result.segment_name}",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f"**{result.user_id}** · not in the learner base")
columns[1].metric(
    "History",
    f"{result.history_size} course" + ("" if result.history_size == 1 else "s"),
    border=True,
)
columns[2].metric(
    "Route",
    result.tier,
    help="The history tier that decides which recommender serves this learner.",
    border=True,
)
columns[3].metric(
    "Candidates",
    result.n_candidates,
    help="Courses eligible after excluding everything the learner has already taken.",
    border=True,
)

if result.recommendations:
    st.info(f"**How these were chosen** — {result.recommendations[0].explanation.tier_frame}.")

shell.evidence(shell.MODEL, "produced by the deployed recommender")

# --- the list --------------------------------------------------------------
if not result.recommendations:
    shell.empty_state(
        "Nothing to recommend",
        "Every course in the catalogue is already in this learner's history.",
    )
    st.stop()

show_scores = st.toggle(
    "Show recommendation scores",
    value=False,
    help=(
        "The raw score from the scorer serving this learner. It is comparable "
        "within one list and meaningless across lists, because different routes "
        "produce different quantities — enrollment counts for segment popularity, "
        "cosine similarity for content matching."
    ),
)

for item in result.recommendations:
    with st.container(border=True):
        left, right = st.columns([4, 1])
        with left:
            price = "Free" if item.is_free else f"{item.price:,.0f}"
            st.markdown(f"**{item.rank}. {item.course_name}**")
            st.caption(
                f"{item.category} · {item.level} · rated {item.rating:.1f} · {price} · "
                f"`{item.course_id}`"
            )
            st.markdown(item.explanation.sentence)
        with right:
            if show_scores:
                st.metric("Score", f"{item.score:,.3f}")
            st.caption("Not yet taken")

# --- the honest footer -----------------------------------------------------
st.divider()
headline = loaders.recommendation_headline()
st.warning(f"**Measured quality.** {result.caveat}")
st.caption(
    f"On the held-out temporal split the deployed method reached NDCG@10 "
    f"{headline['deployed_ndcg']:.4f} against random ranking's "
    f"{headline['random_ndcg']:.4f} — a difference whose 95% confidence interval "
    f"contains zero. {loaders.evaluation_caption()}. "
    "Full comparison on the Model Analytics page."
)
