# Phase 5B — Production Streamlit Application — COMPLETE

**Phase:** 5B — Streamlit dashboard
**Date:** 19 September 2026
**Decision:** ✅ **PASS**
**Artifact set served:** `edupro-1.0.0`, set `247e3eac337f`
**Next phase:** Phase 6 — validation, documentation, deployment (**not started; awaiting go-ahead**)

---

## 1. Objectives

Build the dashboard around the *actual* production ML system: seven pages for
stakeholders, administrators, analysts and the internship reviewer, with no ML
logic duplicated inside Streamlit, no fabricated metrics, and caching that keeps
the model out of the request path.

---

## 2. What was built

```
app/
├── streamlit_app.py              entry point — declares navigation, nothing else
├── lib/
│   ├── shell.py                  page config, evidence badges, provenance, charts
│   └── loaders.py                cached access to the model and measured results
└── pages/
    ├── 1_Executive_Overview.py
    ├── 2_Learner_Profile.py
    ├── 3_Recommendations.py
    ├── 4_Segment_Intelligence.py
    ├── 5_Cluster_Visualization.py
    ├── 6_Segment_Comparison.py
    └── 7_Model_Analytics.py
```

One new production module supports it: **`src/edupro/reporting.py`**, which reads
measured results out of the experiment artifacts as tidy frames. It computes
nothing and contains no typed-in number, so the dashboard is *incapable* of
displaying a fabricated metric — the only alternative to a real artifact value is a
missing-artifact empty state.

The pipeline also gained one display artifact: a precomputed 2D PCA projection
(D-050).

---

## 3. The seven pages

| Page | Required content | Delivered |
| --- | --- | --- |
| **1 Executive Overview** | population, courses, segments, system summary, validated metrics, distribution, key insights | 3,000 learners / 60 courses / 10,000 enrollments; segment bar with names and sizes; the four-tier routing table; NDCG, Hit Rate, engagement proxy and cluster stability each against its reference; four key insights |
| **2 Learner Profile** | selection by anonymised ID, profile, behaviour, segment, preferences, depth, diversity, spending | pseudonymous `UserID` filterable by segment and history depth; behaviour metrics; category share chart; full enrollment history |
| **3 Recommendations** | course, category, level, rating, score, explanation, category and level filters | explained top-K, filters applied to candidates before scoring, optional score display, explicit cold-start mode |
| **4 Segment Intelligence** | sizes, behaviour, dominant categories, levels, activity, diversity, spending, representative patterns | ten behavioural characteristics per segment against population means; category and level composition; **the deviation evidence behind each segment name** |
| **5 Cluster Visualization** | a 2D representation, clearly explained as visualisation not inference | PCA scatter over 3,000 learners, with the caveat and the retained variance stated *before* the chart |
| **6 Segment Comparison** | comparison across key characteristics | deviation-from-population chart, absolute table with a population row, category heatmap, routing composition |
| **7 Model Analytics** | clustering metrics, recommendation metrics, baseline comparison, coverage, proxy impact — loaded from artifacts | twelve-method comparison with confidence intervals; coverage; per-tier metrics; k-selection under its constraints; ten representations; architecture selection |

### Distinguishing observed data, model output and proxy

Every section carries a badge, because a stakeholder cannot otherwise tell the
three apart:

| Badge | Meaning |
| --- | --- |
| **Observed data** | counted from the source workbook |
| **Model output** | produced by the segmentation or the recommender |
| **Proxy metric — not a causal measurement** | Engagement Lift, which the brief names but does not define |

---

## 4. Decisions taken in this phase

### D-050 — the 2D projection is a persisted display artifact

Fitting a projection in the app was rejected (the app must fit nothing, and a
stochastic projection would move points between page loads, which reads as model
instability). t-SNE and UMAP were rejected for a subtler reason: both produce a
*more separated-looking* picture, and on a segmentation whose silhouette is weak
that is exactly the wrong property — it would flatter the result.

PCA is precomputed by the pipeline and retains **30.7% of 25 dimensions**, which
the page states before the chart rather than after.

**This does not reopen the freeze.** No scorer, clusterer or metric consumes the
projection; it changes no model behaviour, which is the test D-044 sets.

### D-051 — quality figures cannot render without their reference

`metric_against_reference` takes the baseline as a *required* argument, and
`reporting.engagement_lift_proxy()` returns the deployed and random values in one
dict. A caller cannot take the flattering number and leave the reference behind.

### D-052 — the dashboard reproduces the frozen document, enforced by test

The representation table initially **contradicted `ARCHITECTURE_FREEZE.md`**:
reading "each arm at its own best k" as the raw silhouette maximum put
`B_proportion` at k = 10 / 0.269 instead of k = 4 / 0.195.

Both numbers are real; they answer different questions. The unconstrained maximum
ranks arms by how far they were allowed to fragment — and at k = 10 half of
`B_proportion`'s clusters fail to reappear under resampling. The page now applies
the pre-registered size constraint and reproduces **all ten rows** of the frozen
table exactly, with a test asserting it. A reviewer opening the dashboard and the
research report will not find two different numbers for the same quantity.

### D-053 — explicit navigation, and a reachable cold-start route

Pages are declared with `st.navigation` so they carry stakeholder-facing names
rather than filenames. The Recommendations page has a **"New learner (cold start)"**
mode — necessary, not decorative: all 3,000 learners have at least one enrollment
(D-049), so without it the diversified fallback selected in EXP-029 would be
unreachable in the application.

---

## 5. No ML logic inside Streamlit

Asserted, not asserted-by-comment. `tests/test_app.py` greps every file under
`app/` for `KMeans(`, `fit_transform`, `.fit(`, `cosine_similarity` and `train(`,
and fails if any appears. Pages are also forbidden from calling
`RecommendationService.load` directly; they must go through the cached loader.

| Concern | Where it lives |
| --- | --- |
| Segmentation, recommendation, explanation | `edupro.inference.RecommendationService` |
| Measured experiment results | `edupro.reporting` |
| Page layout, charts, wording | `app/` |

### Caching

| Object | Decorator | Effect |
| --- | --- | --- |
| `RecommendationService` | `@st.cache_resource` | loaded **once per process**, 0.41 s, shared across sessions and page navigations |
| Derived frames (20 loaders) | `@st.cache_data` | a filter interaction does not re-read parquet |

The application never fits a model (§21).

---

## 6. Testing

`tests/test_app.py` adds **26 tests**, bringing the suite to **245**.

| What | Why it matters |
| --- | --- |
| Every one of the seven pages executes under `AppTest` | Streamlit pages fail at *runtime*, not at import; a broken chart expression would otherwise surface only when someone opened the page |
| Navigation declares every page file | an unregistered page would be unreachable |
| No ML call anywhere under `app/` | the dashboard must call the production modules, not reimplement them |
| The representation table matches the frozen document | stops the dashboard and the research report drifting apart |
| `engagement_lift_proxy` returns both values | the proxy cannot be displayed without its reference |
| Comparison values equal the stored artifact values | no metric is typed in |
| The headline is still "0 of 11 significant" | if this ever changes, the dashboard's framing must change with it |
| No page references a PII column | privacy, checked at the source level |

Two real defects were found and fixed by this work:

1. **`reporting._load` raised the wrong exception** for a path outside the project
   — `relative_to` threw a `ValueError`, so the "artifact is missing" message
   failed instead of reporting. The error path failing is worse than the error.
2. **The representation table contradicted the frozen document** (D-052).

---

## 7. Local verification

Launched with `streamlit run app/streamlit_app.py` and driven in a browser:

| Check | Result |
| --- | --- |
| App starts | ✅ on port 8501, no errors in the server log |
| All seven pages render | ✅ verified in the browser and by `AppTest` |
| Learner selection | ✅ 3,000 learners, filterable by segment and history depth |
| Recommendation filtering | ✅ category and level; a filtered top-5 still returns five items |
| Explanations | ✅ each recommendation carries an evidence-backed sentence |
| Cold-start mode | ✅ routes to the diversified fallback, list spans 10 of 12 categories |
| Cluster visualisation | ✅ 3,000 points, four segments, hover shows the pseudonymous ID |
| Model analytics | ✅ full comparison table with the random row marked *← reference* |
| Empty states | ✅ missing artifacts, no matching learners, impossible filter combination |

One rendering defect was found in the browser and fixed: the learner header read
"1 courses".

---

## 8. Validation checks

| Check | Result |
| --- | --- |
| Full test suite | ✅ **245 passed** (219 + 26) |
| App starts successfully | ✅ |
| All seven pages execute | ✅ |
| Production model used | ✅ no ML under `app/`, asserted by test |
| Learner selection works | ✅ |
| Recommendation filtering works | ✅ filters applied before scoring |
| Explanations work | ✅ generated from the scorer's own decomposition |
| Segment visualisation works | ✅ with its explained-variance caveat |
| Metrics are evidence-backed | ✅ every figure read from an experiment artifact |
| No fabricated metric is possible | ✅ `reporting` computes nothing |
| PII in the app | ✅ none, asserted by test |
| Raw workbook SHA-256 | ✅ `ed555e46…8cc0` unchanged |
| Docker | ✅ none |

---

## 9. PASS / FAIL

### ✅ **PASS**

| Criterion | Evidence |
| --- | --- |
| All official Streamlit capabilities present | §3 — G1–G8 all Verified in the traceability matrix |
| Production model used | §5 — asserted by test, not by convention |
| Learner selection works | §7 |
| Recommendation filtering works | §7 — and applied to candidates, so a filtered list still fills |
| Explanations work | §7, and the Phase 5A faithfulness tests still pass |
| Segment visualization works | §7, with the caveat stated before the chart |
| Metrics are evidence-backed | §6 — values asserted equal to the stored artifacts |
| App starts successfully | §7 |

### CLAUDE.md compliance

| § | Requirement | Status |
| --- | --- | --- |
| 6 | No fabricated metrics | ✅ The dashboard cannot produce one |
| 6 | Proxy not presented as causal impact | ✅ Badged, and shown beside random's own lift |
| 16 | Explanations match the scoring logic | ✅ Unchanged from Phase 5A; displayed verbatim |
| 17 | Privacy; anonymised identifiers | ✅ Pseudonymous IDs; no PII reference anywhere in `app/` |
| 18 | Modular source; app depends on modules | ✅ |
| 20 | No Docker | ✅ |
| 21 | Loads artifacts, never retrains; clean navigation; informative empty states | ✅ |
| 23 | Critical UI workflows tested | ✅ 26 tests, every page executed |
| 29 | UI polish not at the expense of research validity | ✅ The headline finding is on the first screen |

---

## 10. Unresolved issues

1. **Not yet deployed publicly.** Streamlit Community Cloud deployment is Phase 6;
   `docs/deployment.md` documents the procedure, and the artifact set is committed
   so the platform has a model to serve.
2. **Nothing beats random.** Unchanged, and now stated on the first screen, in
   every recommendation footer, and in the analytics page.
3. **The segmentation is a course-level split** (D-031). The Segment Intelligence
   page says so where the level composition is shown.
4. **Gender gap requires monitoring** on real data. It is recorded in the research
   artifacts but is **not currently surfaced in the dashboard** — Phase 6 should
   decide whether a fairness panel belongs there.
5. **Phase 0's two open items remain open**: the empty `claude.md.txt`, and the
   git-identity/authorship question. Both need confirmation before publication.

---

## 11. Stop

Per CLAUDE.md §28, work **stops here**. Phase 6 will not begin automatically.

🔒 The ML design remains frozen. Phase 5B added a display artifact and a reporting
layer; it changed no model behaviour, and the 245-test suite — including the
reproducibility check from Phase 5A — is the evidence.
