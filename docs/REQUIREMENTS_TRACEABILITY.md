# Requirements Traceability Matrix

Maps every mandatory requirement to where it is implemented and how it is
verified. Maintained from Phase 0 to submission so that "official requirements
covered" (CLAUDE.md §26) can be demonstrated rather than claimed.

**Sources**
- `references/official/project offical detail.pdf` — authoritative requirements
  (transcribed in `references/official/OFFICIAL_REQUIREMENTS_TRANSCRIPT.md`)
- `CLAUDE.md` — project engineering standard

**Status values:** `Not started` · `In progress` · `Implemented` · `Verified`

A requirement reaches **Verified** only when evidence exists — a passing test, a
logged experiment, or a reviewable artifact. Not before.

---

## A. Learner analysis (official, p.4)

| # | Requirement | Implementation | Verification | Status |
| --- | --- | --- | --- | --- |
| A1 | Aggregate transaction data at UserID level | `edupro.features.learner` | 36 pipeline tests; exercised by the production pipeline | **Verified** |
| A2 | Learner profiles combining demographics and behaviour | `edupro.features.learner`, surfaced by `RecommendationService.learner_profile` | tests + EDA notebook + production tests | **Verified** |
| A3 | Engagement features | `edupro.features.learner` | EXP-006 distributions; persisted in `learner_features.parquet` | **Verified** |
| A4 | Preference features | `edupro.features.learner` | EXP-006 distributions; persisted in `learner_features.parquet` | **Verified** |

## B. Feature engineering (official, pp.3–4)

The official document names eleven learner-level features. Each is implemented
and justified individually; none is dropped without a recorded reason.

| # | Feature | Official group | Status |
| --- | --- | --- | --- |
| B1 | Age | (demographic; Users sheet) | **Implemented** |
| B2 | Gender | (demographic; Users sheet) | **Implemented** |
| B3 | Total courses enrolled | Engagement | **Implemented** |
| B4 | Average courses per category | Engagement | **Implemented** |
| B5 | Enrollment frequency | Engagement | **Implemented** |
| B6 | Preferred course category | Preference | **Implemented** |
| B7 | Preferred course level | Preference | **Implemented** |
| B8 | Average course rating enrolled | Preference | **Implemented** |
| B9 | Average spending per learner | Behavioural | **Implemented** |
| B10 | Diversity score (categories explored) | Behavioural | **Implemented** |
| B11 | Learning depth index (beginner vs advanced ratio) | Behavioural | **Implemented** |

> **RESOLVED (EXP-002).** `Transactions.Amount` **is** `Courses.CoursePrice`, on
> all 10,000 rows. B9 is therefore a deterministic function of catalogue choice,
> not independent spending behaviour. It is retained because the brief mandates it,
> with the redundancy documented wherever it is reported (decision log D-020).

## C. Data preprocessing (official, p.4)

| # | Requirement | Implementation | Status |
| --- | --- | --- | --- |
| C1 | Normalize numerical features | `edupro.segmentation.representations` — StandardScaler, chosen on evidence (D-028) | **Implemented** |
| C2 | Encode categorical variables | `edupro.segmentation.representations` — 4 encodings compared (EXP-011a) | **Implemented** |
| C3 | Reduce noise from sparse enrollments | Four-tier routing on training-window history (L3); sparse learners never scored as personalised | **Verified** (EXP-025, EXP-028) |

## D. Segmentation (official, p.4)

| # | Requirement | Implementation | Verification | Status |
| --- | --- | --- | --- | --- |
| D1 | K-Means clustering (primary) | `edupro.segmentation.clustering` | EXP-010, k=2..10 across 10 representations | **Verified** |
| D2 | Hierarchical clustering (validation) | `edupro.segmentation.clustering` | EXP-012 — Ward + average linkage; **negative result reported** | **Verified** |
| D3 | Elbow method for cluster selection | `edupro.segmentation.clustering` | EXP-010 — produced; no knee; not decisive | **Verified** |
| D4 | Silhouette analysis | `edupro.segmentation.metrics` | EXP-010 — global + per-cluster | **Verified** |
| D5 | Cluster profiling | `edupro.segmentation.profiling` | `research/cluster_profiles.md` | **Verified** |
| D6 | Interpretable segment descriptions | `edupro.segmentation.profiling` — evidence-derived naming, model features only | 37 tests | **Verified** |

## E. Recommendation (official, pp.4–5)

| # | Requirement | Implementation | Verification | Status |
| --- | --- | --- | --- | --- |
| E1 | Content-based filtering | `edupro.recommendation.baselines.ContentBased` | EXP-021 — best single baseline on test (0.1191) | **Verified** |
| E2 | Similar learner profiles | `UserUserHistory` + `UserUserProfile` (two arms) | EXP-022a/b | **Verified** |
| E3 | Course popularity within cluster | `edupro.recommendation.baselines.ClusterPopularity` | EXP-023 — selected method; answers Q-10 | **Verified** |
| E4 | Rating-weighted relevance | `RatingRecommender` standalone + weight 0.249 in the hybrid + quality signal in `DiversifiedFallback` | EXP-024 — largest ablation loss; EXP-029 | **Verified** |
| E5 | Personalized ranking | `WeightedHybrid` with searched weights | EXP-024 — 400-sample search + ablation | **Verified** |
| E6 | Cold-start / fallback logic | `TieredRecommender`, four tiers; `DiversifiedFallback` for zero history | EXP-025 — 100% of learners receive a recommendation; EXP-029 — 10/12 categories at cold start | **Verified** |

## F. Evaluation (official, p.5)

| # | Metric | Official purpose | Implementation | Status |
| --- | --- | --- | --- | --- |
| F1 | Silhouette Score | Cluster quality | `edupro.segmentation.metrics` | **Verified** |
| F2 | Intra-Cluster Similarity | Behavioural consistency | `edupro.segmentation.metrics` — behavioural cosine, formula defined in `segmentation_research.md` §5 | **Verified** |
| F3 | Recommendation Precision | Relevance | `edupro.evaluation.metrics` — always reported against its analytical ceiling | **Verified** |
| F4 | Engagement Lift (Proxy) | Impact estimate | `edupro.evaluation.metrics.engagement_lift_proxy` — reported with random's own lift beside it (D-038) | **Verified** |

Additional metrics where scientifically appropriate (CLAUDE.md §3): Recall@K,
Hit Rate@K, NDCG@K, catalogue coverage.

> **Constraint on F4.** The official document names the metric but defines no
> formula. Whatever definition is adopted must be labelled a proxy and must never
> be presented as measured causal impact (CLAUDE.md §6). See decision log Q-7.

## G. Streamlit application (official, pp.5–6)

| # | Requirement | Implementation | Status |
| --- | --- | --- | --- |
| G1 | Learner profile explorer | `app/pages/2_Learner_Profile.py` | **Verified** |
| G2 | Cluster visualization dashboard | `app/pages/5_Cluster_Visualization.py` — PCA, with its 30.7% explained variance stated | **Verified** |
| G3 | Personalized course recommendations | `app/pages/3_Recommendations.py` — with per-item explanations | **Verified** |
| G4 | Segment comparison panels | `app/pages/6_Segment_Comparison.py` + `4_Segment_Intelligence.py` | **Verified** |
| G5 | Select a learner profile | pseudonymous `UserID`, filterable by segment and history depth | **Verified** |
| G6 | View assigned segment | shown on the profile and recommendation pages, with the naming evidence | **Verified** |
| G7 | See recommended learning paths | ranked top-K with category, level, rating, score and reason | **Verified** |
| G8 | Filter recommendations by level or category | applied to candidates before scoring, so a filtered list still returns k items | **Verified** |

## H. Deliverables (official, p.6)

| # | Deliverable | Location | Priority | Status |
| --- | --- | --- | --- | --- |
| H1 | Research paper (EDA, insights, recommendations) | `docs/` | P1 | Not started |
| H2 | Streamlit dashboard (live analytics) | `app/` | P2 | **Implemented** — deployment pending |
| H3 | Executive summary | `docs/` | P3 | Not started |

---

## I. Engineering standard (CLAUDE.md)

| # | Requirement | § | Implementation | Status |
| --- | --- | --- | --- | --- |
| I1 | Raw data immutable | 8 | ADR-0003; checksums in `edupro.config` | **Verified** |
| I2 | `data/raw/` + `data/processed/` maintained | 8 | Repository layout | **Verified** |
| I3 | Leakage detection for temporal evaluation | 9 | All six controls verified in-run at both stages; the checker is itself tested able to fail; Phase 6A added a future-injection *experiment* — a synthetic post-test-cut interaction changes no training feature | **Verified** |
| I4 | Variant A vs Variant B segmentation | 10 | EXP-011 run: ARI 1.000, demographic share 0.0004, Variant B by the pre-registered rule (D-029) | **Verified** |
| I5 | Teachers sheet as explicit experiment | 11 | EXP-005 refuted the bijection; EXP-014 (segmentation) and EXP-022d (recommendation) both run and **rejected on evidence** (D-030); excluded from `edupro-1.0.0` | **Verified** |
| I6 | Temporal hold-out; sparse users handled separately | 12 | Both protocols run; 350 zero-history learners excluded from personalised evaluation and counted | **Verified** |
| I7 | Five recommendation baselines | 13 | Ten baselines evaluated on both splits with identical treatment | **Verified** |
| I8 | Hybrid weights justified, not asserted | 14 | 400-sample simplex search on validation + 6-component ablation + sensitivity spread | **Verified** |
| I9 | Sparse-history recommendation tiers | 15 | Four tiers implemented and routed on training-window history (L3); per-tier metrics reported | **Verified** |
| I10 | Explanations consistent with scoring logic | 16 | Scorer returns per-component contributions; tests assert the decomposition sums to the total and that zero-weighted components never appear | **Verified** |
| I11 | Email never a modelling feature; UI anonymised | 17 | ADR-0006; `PII_COLUMNS`; every persisted artifact **and every app file** asserted PII-free by test | **Verified** |
| I12 | Modular source; app independent of notebooks | 18, 19 | ADR-0001 | **Verified** |
| I13 | No Docker | 20 | `test_no_docker_artifacts_are_present` | **Verified** |
| I14 | App loads artifacts; never retrains on startup | 21 | `st.cache_resource` around a 0.41 s load; a test asserts no ML call appears anywhere under `app/` | **Verified** |
| I15 | Artifacts persisted and version-consistent | 22 | `edupro.persistence` — manifest with library versions, workbook checksum and a per-file hash; 11 files; mismatch and half-update both asserted to raise | **Verified** |
| I16 | Test coverage of the listed surfaces | 23 | `tests/` — **257 tests**; every dashboard page executed by `AppTest`, plus 12 regression tests holding the Phase 6A defects | **Verified** |
| I17 | Commits at phase boundaries | 24 | git history | In progress |
| I18 | Decision log, experiment log, ADRs maintained | 25 | `research/` | **Verified** |
| I19 | Phase reports with PASS/FAIL and evidence | 27 | `research/PHASE_X_COMPLETE.md` | In progress |
| I20 | Reproducible environment | 3, 26 | `requirements*.txt`, `.venv` | **Verified** |

---

## Phase 6A status summary (19 September 2026)

An adversarial audit (59 probes) and an application smoke test (20 probes) found
**three real defects**, all now fixed and held by regression tests. Sections A-G
remain Verified; I3 and I16 are strengthened by the new evidence.

The project installs and runs end to end in a clean environment built from
`requirements.txt`, and eight stored experiment results recompute exactly in both
environments. Remaining scope is section **H**: the research paper, the executive
summary and public deployment.

---

## Phase 5B status summary (19 September 2026)

**Every official Streamlit capability (G1–G8) is Verified**, and the engineering
requirements that were waiting on the application — I11, I14 and I16 — close with
it. Section **A–G is complete**; only section **H (research paper, executive
summary) and the deployment itself remain**, which is Phase 6.

Evidence: 245 tests pass, including one that executes each of the seven dashboard
pages exactly as the server would; a test asserts that no machine-learning call
appears anywhere under `app/`; and a test asserts the dashboard's representation
table reproduces `ARCHITECTURE_FREEZE.md` row for row, so the application and the
research report cannot drift apart silently.

---

## Phase 5A status summary (19 September 2026)

The frozen architecture is implemented as reusable production modules and a
versioned artifact set. **Sections A-F are Verified**; section **I** advances I15
to Verified and I14/I16 to In progress.

Evidence: 219 tests pass; the artifact set loads in 0.41 s and serves ~8 ms per
learner; all 3,000 learners receive a recommendation with none containing an
already-enrolled course; and `scripts/verify_reproducibility.py` reproduces eight
stored experiment results exactly after the refactor.

Section **G (Streamlit)** and the UI halves of I11, I14 and I16 remain the Phase 5B
scope. Section **H (deliverables)** is Phase 6.

---

## Phase 4 status summary (19 September 2026)

The architecture is frozen as `edupro-1.0.0`. Sections **A–F are complete**: every
official learner-analysis, feature, preprocessing, segmentation, recommendation and
evaluation requirement is implemented, measured and evidenced.

Section **G (Streamlit) and H (deliverables) remain Not started**, which is correct
— CLAUDE.md §4 gates them behind the architecture freeze, and the Phase 4 brief
explicitly forbids writing production UI code yet.

Requirements **investigated and not retained as the primary mechanism** — Age and
Gender as clustering features, similar-learner recommendation, rating-weighted
relevance standalone, the weighted hybrid, the elbow method as a decision rule, and
the entire teacher block — are individually accounted for in
`research/ARCHITECTURE_FREEZE.md` §"Official requirements evaluated but not
retained", with how each is still addressed. **None was skipped.**

Two engineering requirements remain **In progress** by design: I14/I15 (artifact
persistence and the app loading them) land in Phase 5; I11's UI half lands with the
app, its data half already Verified at the ingestion layer.

---

## Phase 0 status summary

Nothing in sections A–H is implemented, which is correct: Phase 0 is project
initialization, and CLAUDE.md §4 gates implementation behind the research and
audit phases.

Six engineering requirements reach **Verified** in Phase 0 — I1, I2, I12, I13,
I18 and I20 — each backed by a passing test or a reviewable artifact. Five are
**In progress** (I5, I11, I16, I17, I19). The remaining nine are correctly not
started.
