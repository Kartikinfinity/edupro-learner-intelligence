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
| A1 | Aggregate transaction data at UserID level | `edupro.features.learner` | 36 pipeline tests | **Implemented** |
| A2 | Learner profiles combining demographics and behaviour | `edupro.features.learner` | tests + EDA notebook | **Implemented** |
| A3 | Engagement features | `edupro.features.learner` | EXP-006 distributions | **Implemented** |
| A4 | Preference features | `edupro.features.learner` | EXP-006 distributions | **Implemented** |

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
| C3 | Reduce noise from sparse enrollments | Four-tier routing on training-window history; sparse learners never scored as personalised | **Implemented** |

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
| E4 | Rating-weighted relevance | `RatingRecommender` standalone + weight 0.249 in the hybrid | EXP-024 — largest ablation loss | **Verified** |
| E5 | Personalized ranking | `WeightedHybrid` with searched weights | EXP-024 — 400-sample search + ablation | **Verified** |
| E6 | Cold-start / fallback logic | `TieredRecommender`, four tiers | EXP-025 — 100% of learners receive a recommendation | **Verified** |

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
| G1 | Learner profile explorer | `app/` | Not started |
| G2 | Cluster visualization dashboard | `app/` | Not started |
| G3 | Personalized course recommendations | `app/` | Not started |
| G4 | Segment comparison panels | `app/` | Not started |
| G5 | Select a learner profile | `app/` | Not started |
| G6 | View assigned segment | `app/` | Not started |
| G7 | See recommended learning paths | `app/` | Not started |
| G8 | Filter recommendations by level or category | `app/` | Not started |

## H. Deliverables (official, p.6)

| # | Deliverable | Location | Priority | Status |
| --- | --- | --- | --- | --- |
| H1 | Research paper (EDA, insights, recommendations) | `docs/` | P1 | Not started |
| H2 | Streamlit dashboard (live analytics) | `app/` | P2 | Not started |
| H3 | Executive summary | `docs/` | P3 | Not started |

---

## I. Engineering standard (CLAUDE.md)

| # | Requirement | § | Implementation | Status |
| --- | --- | --- | --- | --- |
| I1 | Raw data immutable | 8 | ADR-0003; checksums in `edupro.config` | **Verified** |
| I2 | `data/raw/` + `data/processed/` maintained | 8 | Repository layout | **Verified** |
| I3 | Leakage detection for temporal evaluation | 9 | All six controls verified in-run at both stages; the checker is itself tested able to fail | **Verified** |
| I4 | Variant A vs Variant B segmentation | 10 | EXP-011 run: ARI 1.000, demographic share 0.0004, Variant B by the pre-registered rule (D-029) | **Verified** |
| I5 | Teachers sheet as explicit experiment | 11 | EXP-005 refuted the bijection; EXP-014 run and **rejected on evidence** (D-030) | **Verified** for segmentation |
| I6 | Temporal hold-out; sparse users handled separately | 12 | Both protocols run; 350 zero-history learners excluded from personalised evaluation and counted | **Verified** |
| I7 | Five recommendation baselines | 13 | Ten baselines evaluated on both splits with identical treatment | **Verified** |
| I8 | Hybrid weights justified, not asserted | 14 | 400-sample simplex search on validation + 6-component ablation + sensitivity spread | **Verified** |
| I9 | Sparse-history recommendation tiers | 15 | Four tiers implemented and routed on training-window history (L3); per-tier metrics reported | **Verified** |
| I10 | Explanations consistent with scoring logic | 16 | Scorer returns per-component contributions; tests assert the decomposition sums to the total and that zero-weighted components never appear | **Verified** |
| I11 | Email never a modelling feature; UI anonymised | 17 | ADR-0006; `PII_COLUMNS` | In progress |
| I12 | Modular source; app independent of notebooks | 18, 19 | ADR-0001 | **Verified** |
| I13 | No Docker | 20 | `test_no_docker_artifacts_are_present` | **Verified** |
| I14 | App loads artifacts; never retrains on startup | 21 | ADR-0001; `app/` | Not started |
| I15 | Artifacts persisted and version-consistent | 22 | `models/`, `artifacts/` | Not started |
| I16 | Test coverage of the listed surfaces | 23 | `tests/` — **160 tests** across environment, pipeline, segmentation and recommendation | In progress |
| I17 | Commits at phase boundaries | 24 | git history | In progress |
| I18 | Decision log, experiment log, ADRs maintained | 25 | `research/` | **Verified** |
| I19 | Phase reports with PASS/FAIL and evidence | 27 | `research/PHASE_X_COMPLETE.md` | In progress |
| I20 | Reproducible environment | 3, 26 | `requirements*.txt`, `.venv` | **Verified** |

---

## Phase 0 status summary

Nothing in sections A–H is implemented, which is correct: Phase 0 is project
initialization, and CLAUDE.md §4 gates implementation behind the research and
audit phases.

Six engineering requirements reach **Verified** in Phase 0 — I1, I2, I12, I13,
I18 and I20 — each backed by a passing test or a reviewable artifact. Five are
**In progress** (I5, I11, I16, I17, I19). The remaining nine are correctly not
started.
