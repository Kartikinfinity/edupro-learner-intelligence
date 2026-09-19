"""EduPro dashboard — entry point.

Run with::

    streamlit run app/streamlit_app.py

Navigation is declared explicitly rather than inferred from filenames, so the
pages carry the names a stakeholder should see rather than the names the files
happen to have. Each page is a normal script under ``app/pages/`` and can also be
run or tested on its own.

The dashboard contains no machine learning. It loads the persisted artifact set
through :class:`edupro.inference.RecommendationService` and reads measured results
through :mod:`edupro.reporting`; a test asserts that no ML call appears anywhere
under ``app/``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_APP = Path(__file__).resolve().parent
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

st.set_page_config(
    page_title="EduPro Analytics",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = [
    st.Page("pages/1_Executive_Overview.py", title="Executive Overview", icon="📊", default=True),
    st.Page("pages/2_Learner_Profile.py", title="Learner Profile", icon="👤"),
    st.Page("pages/3_Recommendations.py", title="Recommendations", icon="🎯"),
    st.Page("pages/4_Segment_Intelligence.py", title="Segment Intelligence", icon="🧩"),
    st.Page("pages/5_Cluster_Visualization.py", title="Cluster Visualization", icon="🗺️"),
    st.Page("pages/6_Segment_Comparison.py", title="Segment Comparison", icon="⚖️"),
    st.Page("pages/7_Model_Analytics.py", title="Model Analytics", icon="📐"),
]

st.navigation(PAGES).run()
