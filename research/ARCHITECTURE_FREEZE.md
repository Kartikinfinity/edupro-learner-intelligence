# Architecture Freeze

**Phase:** 4 — model selection and architecture freeze
**Date:** 19 September 2026
**Status:** 🔒 **FROZEN.** From this point the ML design does not change without a
recorded decision-log entry stating what new evidence justified it.
**Model version:** `edupro-1.0.0`
**Reference keys `[Rxx]`** resolve in `research/literature_review.md` §10.

---

## Executive Architecture Decision

> **A four-segment learner segmentation feeding a four-tier switching recommender,
> with a category-diversified cold-start fallback and explanations generated from
> the scorer's own component decomposition.**
>
> Segmentation: Variant B (behaviour only) · 12-dimensional category share vector ·
> StandardScaler · K-Means · **k = 4**.
> Recommendation: **tiered router** — diversified fallback (no history) → content-based
> (1 interaction) → **cluster popularity** (2+ interactions).

**And the finding that governs how it must be presented:** across eleven methods
on a leakage-free temporal split of 791 learners, **no method beats random
ranking**. Every 95% confidence interval on the paired NDCG@10 difference against
random contains zero. This architecture is selected for **robustness,
interpretability, coverage and honest degradation** — not for accuracy, because no
option demonstrated any.

That is not a failure of the design. Phase 2 established, before any recommender
existed, that course choice in this dataset is statistically indistinguishable
from popularity-weighted chance. The architecture is sound and would transfer
unchanged to real data; the dataset has no signal to find.

---

## Problem

EduPro's official brief asks for a system that segments learners into
interpretable behavioural groups and recommends courses personalised to each
learner's segment and history, delivered as a research paper, a Streamlit
dashboard and an executive summary.

The engineering standard (`CLAUDE.md`) adds binding constraints: immutable raw
data, mandatory leakage control, evidence-based selection across at least five
recommendation baselines, explicit sparse-user tiers, explanations faithful to the
scoring logic, no PII in modelling, no Docker, and no fabricated results.

---

## Data

| Property | Value |
| --- | --- |
| Source | `data/raw/EduPro Online Platform.xlsx`, SHA-256 `ed555e46…8cc0`, **immutable** |
| Learners | 3,000 |
| Courses | **60** — exactly 5 in each of 12 categories |
| Interactions | 10,000, all distinct `(user, course)` pairs — **purely binary/implicit** |
| Matrix density | 5.56% |
| Interactions per learner | mean 3.333, **median 1**, max 16 |
| Time span | 2025-01-01 → 2025-12-30, no trend or seasonality |
| Missing values | **zero**, across 4 sheets and 27 columns |

**Four properties drive every decision below:**

1. **54% of learners have exactly one interaction.** Personalisation is impossible
   for the majority, which makes tiering a requirement, not a refinement.
2. **Course popularity is near-uniform** (140–196 enrollments, Gini 0.042,
   χ² vs uniform p = 0.60). Popularity carries almost no ranking information.
3. **Course choice is indistinguishable from chance.** Category concentration,
   top-category share, free-course share and item co-occurrence all fall inside a
   popularity-matched permutation null.
4. **The dataset is assessed as almost certainly synthetic** (D-025). Segments
   describe a generative process, not learner psychology.

---

## Decision matrix — Segmentation

All figures from `artifacts/segmentation/segmentation_results.json` (fit window,
2,650 learners). Each arm swept over k = 2…10.

| Representation | d | Best k | Silhouette | Intra-cluster sim. | Min cluster | Stability | Interpretable? | Complexity | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **B_proportion** ✅ | 25 | 4 | 0.1946 | **0.416** | **19.7%** | **all ≥0.98** | **yes** | low | **SELECTED** |
| B_robust_scaled | 25 | 2 | *0.7159* | 0.239 | 17.1% | — | no | low | **Rejected — scaling artefact** |
| B_no_category | 13 | 10 | 0.4349 | 0.711 | 6.0% | 5 unstable | no category identity | low | Rejected |
| B_facets | 15 | 2 | 0.3933 | 0.287 | 20.4% | — | loses identity | low | Rejected |
| B_no_level | 22 | 9 | 0.3027 | 0.358 | 5.6% | 1 unstable | yes | low | Rejected |
| B_proportion_weighted | 25 | 4 | 0.2922 | 0.420 | 19.6% | — | yes | medium | Rejected — no dominance to correct |
| B_decorrelated | 23 | 10 | 0.2666 | 0.386 | 5.0% | unstable | yes | low | Rejected — drops mandated features |
| B_teacher | 28 | 2 | 0.2212 | 0.288 | 20.1% | 0.989 | yes | medium | **Rejected — +0.0009, ARI 0.990** |
| A_proportion | 27 | 9 | 0.2188 | 0.398 | 5.1% | 0.991 | yes | medium | **Rejected — ARI 1.000 vs B** |
| B_one_hot | 25 | 2 | 0.2115 | 0.285 | 20.0% | — | yes | low | Rejected — discards distribution |

**Why the highest silhouette did not win.** `B_robust_scaled`'s 0.716 is a
pathology: two mandated features (`avg_courses_per_category`, `diversity_ratio`)
have an **interquartile range of exactly zero**, because 54% of learners have one
course so their quartiles coincide. RobustScaler leaves those columns unscaled
while compressing the others, manufacturing a separable axis. Accepting it would
have been a textbook case of optimising for the number instead of the structure.

### Choosing k

| k | Silhouette | Min cluster | Clusters below Jaccard 0.60 | Passes? |
| --- | --- | --- | --- | --- |
| 2 | 0.1771 | 20.0% | 0 | ✅ |
| 3 | 0.1733 | 19.9% | 0 | ✅ |
| **4** | **0.1946** | **19.7%** | **0** | ✅ **SELECTED** |
| 5 | 0.2019 | 5.4% | 1 | ❌ |
| 6 | 0.2089 | 6.2% | 2 | ❌ |
| 7 | 0.2305 | 4.6% | 5 | ❌ |
| 10 | 0.2685 | 4.4% | 5 | ❌ |

Silhouette alone would have chosen k = 10, where five of ten clusters fail to
reappear under resampling. The pre-registered rule — every cluster ≥5% of learners
**and** bootstrap Jaccard ≥0.60 — leaves only k ∈ {2, 3, 4}, and 4 has the highest
silhouette among them.

**Hierarchical validation (EXP-012) is a negative result and is reported as one.**
ARI K-Means vs Ward **0.350**; vs average linkage **0.019**, which collapses 91% of
learners into one cluster. The structure is **not algorithm-independent** — it is
found by variance-minimising methods and not by others.

---

## Decision matrix — Recommendation

Test window, 791 learners, leakage-free. From
`artifacts/recommendation/recommendation_results.json`.

| Method | NDCG@10 | Δ vs random | 95% CI | Coverage | Gini | Complexity | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid | 0.1206 | +0.0162 | [−0.0033, +0.0355] | 0.92 | — | **6 signals** | Rejected — parsimony |
| content_based | 0.1191 | +0.0147 | [−0.0040, +0.0340] | 1.00 | 0.530 | low | **Retained — minimal tier** |
| preference_match | 0.1165 | +0.0121 | [−0.0068, +0.0305] | 1.00 | 0.483 | low | Not retained |
| **cluster_popularity** ✅ | **0.1138** | +0.0093 | [−0.0092, +0.0271] | 0.75 | 0.606 | medium | **SELECTED — personalised tiers** |
| tiered | 0.1117 | +0.0072 | [−0.0126, +0.0245] | **1.00** | 0.608 | medium | **Architecture** |
| user_user_profile | 0.1105 | +0.0061 | [−0.0113, +0.0251] | 1.00 | 0.233 | medium | Not retained |
| **random** *(floor)* | **0.1102** | — | — | 1.00 | 0.055 | none | Reference |
| teacher_affinity | 0.1076 | +0.0032 | [−0.0150, +0.0209] | 1.00 | 0.666 | low | **Rejected — §11** |
| global_popularity | 0.1072 | +0.0028 | [−0.0155, +0.0205] | **0.32** | 0.807 | trivial | Rejected — below random |
| item_item_cf | 0.1047 | +0.0002 | [−0.0179, +0.0174] | 1.00 | 0.468 | medium | Not retained |
| rating | 0.1034 | −0.0010 | [−0.0193, +0.0163] | 0.30 | 0.811 | trivial | Component only |
| user_user_history | 0.0947 | −0.0098 | [−0.0269, +0.0067] | 1.00 | 0.142 | medium | Not retained |

**Zero of eleven methods are significantly better than random.** Random ranks 7th
of 12. Five methods score below it.

### The assembled architecture (Phase 4, validation window)

Phase 3B evaluated *methods*. The architecture is an *assembly*, and no Phase 3B
row represents it — so it was measured
(`artifacts/architecture/architecture_validation.json`), on **validation only**,
because the test budget was spent once as pre-registered.

Validation window, 511 evaluable learners (rich 231, moderate 178, minimal 102;
the insufficient tier has no evaluable members by definition).

| Architecture | NDCG@10 | HR@10 | Coverage | Gini | Δ random | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| A — flat `cluster_popularity` | 0.1098 | 0.3033 | 0.78 | 0.606 | +0.0125 n.s. | Dominated by C |
| B — tiered, hybrid core | 0.1135 | 0.3327 | **1.00** | 0.608 | +0.0162 n.s. | Rejected — parsimony |
| **C — tiered, selected core** ✅ | **0.1104** | 0.3053 | **1.00** | **0.581** | +0.0131 n.s. | **FROZEN** |

Per-tier for C: rich NDCG 0.1109 (coverage 0.32) · moderate 0.1139 (0.75) ·
minimal 0.1030 (**1.00**). The minimal tier — half the learner base — is where the
tiered design buys its coverage.

**C dominates A**: equal accuracy (+0.0006, noise), **full catalogue coverage
against 0.78**, lower concentration, and an explicitly labelled cold-start route.
B is +0.0031 over C but re-introduces the six-signal hybrid the pre-registered
parsimony rule rejected.

---

## The twelve decisions

### 1. Final learner feature schema

**25 features in four blocks.** All eleven brief-mandated features are present.

| Block | Features |
| --- | --- |
| Engagement (4) | `total_courses`, `avg_courses_per_category`, `enrollment_frequency`, `activity_span_days` |
| Behavioural (6) | `avg_course_rating`, `avg_spend`, `diversity_score`, `learning_depth_index`, `free_ratio`, `diversity_ratio` |
| Category (12) | `cat_share_<category>` — row-normalised share vector |
| Level (3) | `preflevel_{Beginner,Intermediate,Advanced}` one-hot |

**Excluded, with evidence:** `age`/`gender` (§4 below) · teacher block (§10) ·
`total_spend` (r = +0.84 with `total_courses`) · level-progression slope (measured
p = 0.664, no progression exists) · `PaymentMethod` (uniform, no plausible link) ·
PII (§17, ADR-0006).

### 2. Final segmentation representation

**`B_proportion`** — Variant B (behaviour only), category as a 12-dimensional
**share vector**, ordinal level one-hot, **StandardScaler**, no block weighting.

Chosen on interpretability and coherence: the share vector carries preference
*shape* rather than an argmax that is a coin-toss at 3.3 courses, is naturally
bounded in [0,1], and reads directly in a dashboard ("38% Data Science, 25%
Business").

### 3. Final K

**k = 4**, by the pre-registered rule. Every cluster ≥19.7% of learners; every
cluster bootstrap Jaccard ≥0.981; subsample consensus ARI 0.987; seed ARI 1.000.

### 4. Final clustering pipeline

```
learner features (25 cols)
  → StandardScaler (fitted on the training window)
  → KMeans(n_clusters=4, init="k-means++", n_init=10, random_state=42)
  → cluster label per learner
```

**Demographics excluded.** Variant A and Variant B produce **identical
partitions** (ARI = 1.000); the demographic block explains **0.04%** of
between-cluster variance. Age and gender are retained **as evaluation strata only**
[R30] — auditing with a protected attribute is not modelling with it.

### 5. Final segment naming methodology

Mechanical and evidence-derived, never chosen first:

1. Compute per-cluster means in population standard deviations.
2. Keep features deviating ≥0.40 SD, ranked by magnitude.
3. Map to a **controlled vocabulary** in which each phrase is licensed by the
   feature producing it.
4. Use **only features the clustering actually used** — an earlier run produced
   "Instructor-loyal" from teacher features not in the model.
5. Where a cluster is ≥90% one course level, prefix the level (closes the blind
   spot where a mid-scale cluster has near-zero depth deviation).
6. No distinguishing feature → neutral name, ambiguity reported.

**[R12]'s MOOC labels are barred by design and guarded by a test.** "Auditing",
"completing", "sampling" were derived from longitudinal engagement traces; EduPro
has no completion data at all.

### 6. Final recommendation architecture

**Tiered switching recommender** (Burke's *switching* hybrid [R17]), routed on
**training-window history only** (leakage control L3).

| Tier | Training history | Learners | Route |
| --- | --- | --- | --- |
| insufficient | 0 | 350 (11.7%) | **DiversifiedFallback** |
| minimal | 1 | 1,514 (50.5%) | **ContentBased** |
| moderate | 2–8 | 731 (24.4%) | **ClusterPopularity** |
| rich | ≥9 | 405 (13.5%) | **ClusterPopularity** |

Boundaries come from the Phase 2 distribution, not tuning: the interaction
histogram has a **hard empty band at 5–8**, so the moderate/rich boundary is drawn
through a region containing no learners.

### 7. Final ranking logic

For a learner in a personalised tier:

1. Candidates = all 60 courses **minus** those enrolled in the **training window**
   (L2 — using full history would leak the held-out item's existence).
2. Score each candidate by within-segment enrollment count, computed from the
   training window only (L5).
3. Sort descending; **ties broken by catalogue index** so the ranking is
   deterministic — essential on a near-uniform catalogue where ties are common.
4. Return the top K.

### 8. Final sparse-user fallback strategy

**`DiversifiedFallback`** — §15's prescribed popularity + rating **+ diversity**.

The naive reading (blend popularity and rating) was implemented first and
**measured to fail the diversity half**: it showed a cold-start learner **7 of 12
categories** with 20% of the list in one category. The frozen fallback blends the
same quality signal but re-ranks **round-robin across categories**:

| Fallback | Distinct categories in top 10 | Largest category share |
| --- | --- | --- |
| global_popularity | 8 | 0.30 |
| rating | 8 | 0.20 |
| popularity + rating blend | 7 | 0.20 |
| **DiversifiedFallback** ✅ | **10** | **0.10** |

For a learner the system knows nothing about there is no preference to exploit, so
the useful thing to offer is breadth — and Phase 2 showed the accuracy cost is nil.

> **A measurement correction worth recording.** Cross-user catalogue coverage was
> tried first as the fallback's diversity metric and gave 0.17 for *every*
> candidate. That is not a tie — it is a meaningless metric: zero-history learners
> are indistinguishable, so every deterministic ranker gives all of them the same
> list, fixing coverage at K/60. Within-list category spread is the property that
> actually varies.

### 9. Final explanation logic

**Model-intrinsic, generated from the scorer's own decomposition** [R31] — the
interface requirement fixed in Phase 1 (D-015) *before* any recommender was
written, because retrofitting faithfulness is impossible.

- Every scorer returns `Scores(candidates, total, components)`.
- `contribution_at(course)` yields the per-component contribution.
- A component with **zero weight never appears** in the decomposition, so an
  explanation cannot name a signal the model did not use (tested).
- **Tier-honest**: a minimal-tier learner is told the basis is content similarity;
  an insufficient-tier learner is told it is popularity and breadth. No
  personalisation narrative the model cannot support.

Post-hoc/LLM explanation is **rejected**: it can assert reasons the model never
used, the precise §16 violation.

### 10. Teacher signals — **NOT in the production model**

Investigated in three separate experiments and rejected on evidence in all three:

| Experiment | Result |
| --- | --- |
| EXP-005 (Phase 2) | Mapping is **not** a bijection — 887 `(course, teacher)` pairs, so the experiment is **not** vacuous and had to run |
| EXP-014 (Phase 3A, segmentation) | +0.0009 silhouette, ARI 0.990, **worse** stability. `teacher_loyalty` correlates **+0.963** with `total_courses` — it re-measures volume |
| EXP-022d (Phase 3B, recommendation) | NDCG 0.1076, **8th of 12**, CI [−0.0150, +0.0209] contains zero |

Phase 2 established instructor loyalty as the dataset's **only genuine behavioural
signal** (0.688 distinct teachers per interaction vs a 0.944 null) — but its lift
on next-course prediction is only **1.10×**, because each teacher covers ~15 of ~55
unseen courses. Real but too low-resolution to be useful.

Teacher `Age` and `Gender` were **excluded before experimentation** (D-016):
third-party demographics with no legitimate role in allocating recommendations
[R38].

### 11. Model/artifact persistence strategy

`joblib` for fitted estimators, `parquet` for tabular artifacts, `json` for config
and manifest — config human-readable so a reviewer can check what produced a result
without running code.

| Artifact | Contents |
| --- | --- |
| `scaler.joblib` | Fitted StandardScaler |
| `clusterer.joblib` | Fitted KMeans (k=4) |
| `learner_features.parquet` | Feature matrix + cluster label |
| `cluster_profiles.parquet` | Centroids, sizes, derived labels, stability |
| `course_catalogue.parquet` | Course attributes + content vectors |
| `popularity.parquet` | Global and per-cluster counts, **training window only** |
| `feature_schema.json` | Column names, order, dtypes, block map |
| `model_config.json` | k, encoding, tier boundaries, seed |
| **`manifest.json`** | Artifact-set version + Python/sklearn/numpy versions + raw-data SHA-256 |

**Two guarantees, both load-time and both failing loudly:**
- **Version consistency** — scikit-learn documents cross-version loading as
  unsupported [R36]; a mismatch produces subtly different numbers rather than a
  crash, which is worse. The manifest is verified on load.
- **Matched set (CACE, [R33])** — every artifact carries one
  `artifact_set_version`. Re-fitting the clustering changes the cluster-popularity
  recommender's inputs; pairing a new clusterer with a stale popularity table would
  be wrong in a way no single-component test would catch.

### 12. Final evaluation methodology

**Protocol A — global temporal split (primary, leakage-free)**, exactly as
pre-registered and confirmed viable by EXP-004 (791 evaluable ≥ the 300 threshold).

| Window | Range | Role |
| --- | --- | --- |
| Training | < 2025-09-12 | features, popularity, similarity |
| Validation | 09-12 → 10-18 | **all model selection** |
| Fit | < 2025-10-18 | final training |
| Test | ≥ 2025-10-18 | **used exactly once** |

**Metrics:** NDCG@10 primary (rank-sensitive, not ceiling-limited) · HR@K ·
**Precision@K always reported against its analytical ceiling** · Recall@K · MRR ·
**catalogue coverage co-primary** · Gini · Engagement Lift (Proxy).

**Mandatory in every results table:** the **random baseline** and, where relevant,
the **analytical ceiling**. On a 60-course catalogue a random ranker achieves
HR@10 ≈ 0.35 and Precision@10 is capped at ~0.21; omitting either is misleading.

**Protocol B (leave-one-out)** is retained as a labelled **leakage-bearing**
secondary. EXP-026 showed five methods move ≥3 ranks between protocols — Meng et
al. [R24] reproduced on EduPro, and the concrete justification for the primary
choice.

---

## Feature Layer

```
raw workbook (immutable)
  → loader (PII dropped at ingestion)
  → schema validation (12 check families, 0 errors)
  → enriched interactions (course + optional teacher attributes)
  → build_learner_features(window)   ← reads ONLY the frame it is given (L1)
  → 25-column representation + 12 category shares
```

`build_learner_features` never reads raw data itself, so passing the training
window yields leakage-free features by construction. `recency_days` defaults its
reference to the maximum date **inside the given frame**, never the real present.

## Segmentation Layer

StandardScaler → KMeans(k=4, k-means++, n_init=10, seed 42) → four segments:

| Cluster | Label | n | Share | Courses | Level |
| --- | --- | --- | --- | --- | --- |
| 0 | Beginner-level Single-course learners | 715 | 27.0% | 1.34 | 100% Beginner |
| 1 | Category-repeating High-volume learners | 522 | 19.7% | 9.65 | mixed |
| 2 | Advanced-level Non-repeating learners | 881 | 33.2% | 1.51 | 100% Advanced |
| 3 | Intermediate-level Single-session Single-course learners | 532 | 20.1% | 1.25 | 100% Intermediate |

## Recommendation Layer

Tiered router → candidate generation (exclude training-window enrollments) →
component scoring → weighted total + component decomposition → deterministic
ranking → top K.

## Evaluation Layer

Six leakage controls verified **in-run** at every stage, plus a test proving the
checker can fail. Per-tier reporting throughout. Paired bootstrap against random
for every claim of improvement.

## Explainability Layer

Score decomposition → threshold on contribution → phrase from a controlled
vocabulary → tier-honest sentence. Never names a zero-weight component.

## Privacy Layer

`UserName`, `Email`, `TeacherName` **dropped at load time**, not filtered
downstream — so PII is never present in any frame that could reach a feature
matrix, artifact or figure (ADR-0006, asserted by test). Learners addressed by
pseudonymous `UserID`. Age and gender never enter a model; used only as evaluation
strata.

## Application Layer

Streamlit, loading **persisted artifacts only** — `st.cache_resource` for
estimators, `st.cache_data` for frames [R37]. **The app never fits a model** (§21).
Pages: learner profile explorer · cluster visualization · personalised
recommendations with explanations · segment comparison · category/level filters.

**The dashboard must display the random reference** wherever it reports
recommendation quality. "Hit Rate 36%" without "random achieves 35%" would mislead.

## Deployment Layer

Python 3.13 + Streamlit Community Cloud. **No Docker** (§20). Artifacts committed
to the repository — the platform deploys from the repo and cannot run the training
pipeline, so the `.gitignore` rule for `models/` must be relaxed for the final
artifact set (open item P-2).

## Model Artifacts

See decision 11. Small enough to commit (60×60 similarity, a few thousand-row
tables); no Git LFS required.

## Fallback Logic

```
history == 0  → DiversifiedFallback   (popularity + rating, round-robin by category)
history == 1  → ContentBased          (works from a single anchor)
history 2–8   → ClusterPopularity
history ≥ 9   → ClusterPopularity
```

**100% of learners receive a recommendation. 0 have an empty candidate pool.**
Minimum pool 45 of 60, so top-10 can always be filled.

---

## Known Limitations

1. **No method beats random.** 0 of 11, aggregate and per tier. The honest
   description of what EduPro would deploy is a segment-aware popularity
   recommender whose ranking quality on this dataset is indistinguishable from
   chance.
2. **The dataset is almost certainly synthetic** (D-025). Segments describe a
   generative process, not learner psychology.
3. **The segmentation is a course-level split.** Three of four clusters are 100%
   one level; removing `preferred_level` gives a different partition (ARI 0.253)
   with an unstable cluster. For ~80% of learners that level is the level of a
   single enrollment — and Phase 2 measured level choice as near-random.
4. **The structure is not algorithm-independent.** Average linkage agrees with
   K-Means at ARI 0.019.
5. **No falsification instrument.** The gap statistic — added specifically to be
   able to report "no cluster structure" — rose monotonically to k = 20 and
   returned no verdict. Nothing in the toolkit can falsify cluster structure.
6. **Missing-not-at-random.** A non-enrollment is not a negative; no impression
   data exists. Unavoidable offline.
7. **No causal claim is possible.** Engagement Lift is a proxy. Random scores
   1.046 on the same measure against the selected method's 1.084.
8. **Gender gap under monitoring.** −0.0283 NDCG@10 (CI [−0.0543, −0.0010]),
   consistent across tiers, but uncorrected for four strata tests, in a system
   using no demographic feature, on data where nothing beats chance.
9. **Popularity bias present.** The selected method recommends at mean popularity
   rank 16.8 while learners' actual next courses sit at 28.6. Fifteen of sixty
   courses are never recommended by the flat scorer — which is part of why the
   tiered architecture was chosen.
10. **Segmentation has no demonstrated recommendation value** (Q-10, D-036). It
    beats global popularity (+0.0066) but not random.

---

## Rejected Alternatives

| Alternative | Why rejected | Evidence |
| --- | --- | --- |
| **iALS / implicit MF** [R13] | Confidence weighting requires *repeat* observations; EduPro has **zero** repeat `(user, course)` pairs, so the mechanism is inoperative | Phase 2 verified; D-010 |
| **BPR** [R14] | 10,000 positives over 60 items under-identifies a latent-factor model; latent factors conflict with §16 | D-010 |
| **Neural recommenders** | [R26] reproduced only 7 of 18 papers, most beaten by tuned simple baselines; uninterpretable; far too little data | D-010, §7 |
| **DBSCAN** | No centroid → no interpretable segment profile; ε unsettable in 25 dimensions | Phase 1 methodology comparison |
| **RobustScaler** | Two mandated features have **IQR = 0**; produces an artificial silhouette of 0.716 | D-028 |
| **Variant A (demographics)** | **ARI 1.000** — identical partition; demographic block explains 0.04% | D-029 |
| **Teacher features** | +0.0009 silhouette (segmentation); 8th of 12, CI contains zero (recommendation) | D-030, §10 |
| **Weighted hybrid** | Won validation by 0.0051 — **inside the pre-registered 0.01 parsimony margin** | D-034 |
| **Flat `cluster_popularity`** | Coverage 0.78 vs the tiered architecture's 1.00 at equal accuracy | Phase 4 §Decision matrix |
| **Naive popularity+rating fallback** | Fails §15's diversity requirement — 7 categories vs 10 | Decision 8 |
| **Post-hoc / LLM explanation** | Can assert reasons the model never used — the §16 violation | D-015 |
| **Per-user leave-one-out as primary** | Leaks by the global-timeline definition; reorders five methods by ≥3 ranks | D-011, EXP-026 |

---

## Official requirements evaluated but not retained

CLAUDE.md requires that where an official requirement was investigated and not
retained, the investigation, the reason, and **how the requirement is still
addressed** are documented.

| Official requirement | How investigated | Why not retained as the primary mechanism | How it is still addressed |
| --- | --- | --- | --- |
| **Age, Gender** as clustering features (B1, B2) | Variant A vs B, full k sweep, η² dominance diagnostic (EXP-011) | ARI **1.000** — identical partition; demographic block explains 0.04% of variance; Variant A's silhouette is *lower* | **Implemented in the feature builder** and available; used as **evaluation strata** (EXP-027) so demographic parity can be reported [R30]. The dashboard's learner profile displays them |
| **Average spending** (B9) | EXP-002 — row-wise comparison with `CoursePrice` | `Amount` **equals** `CoursePrice` on all 10,000 rows, so it is a function of catalogue choice, not independent behaviour | **Retained in the 25-feature schema** and reported in cluster profiles, with the redundancy documented wherever it appears (D-020) |
| **Similar learner profiles** (E2) | Two arms — over interaction history and over engineered features (EXP-022a/b), both splits | 0.0947 and 0.1105 NDCG@10; the history arm is the **worst** method on test | **Both implemented and reported** in the comparison table. Learner similarity also enters the hybrid candidate that was evaluated and rejected on parsimony |
| **Rating-weighted relevance** (E4) | Isolated as its own baseline **and** as a hybrid component (EXP-024) | Alone it scores **below random** (0.1034) with 30% coverage | **Retained as a component**: second-largest hybrid weight (0.249) and the largest ablation loss (−0.0102). Also drives the cold-start `DiversifiedFallback` |
| **Content-based filtering** (E1) | EXP-021, both splits | Best single baseline (0.1191) but still not significant vs random | **Retained as the minimal-tier route** — it is the only method that works from a single interaction |
| **Personalized ranking / hybrid** (E5) | 400-sample weight search + 6-component ablation (EXP-024) | Won validation by 0.0051, inside the pre-registered parsimony margin | **Evaluated and reported in full**; the ranking logic it informed (per-component decomposition) is what makes explanations faithful |
| **Elbow method** (D3) | Produced for k = 2…10 (EXP-010) | Inertia falls monotonically with no knee — subjective and non-decisive, as [R07] predicts | **Produced and reported** as a mandated figure, alongside silhouette, CH, DB, gap and stability. It informs; it does not decide |
| **Hierarchical clustering** (D2) | Ward **and** average linkage at k=4 (EXP-012) | Ward agrees at ARI 0.350, average linkage at 0.019 — the structure is not algorithm-independent | **Run and reported as a validation step**, including the negative result and the shared-objective caveat |
| **Teachers sheet** (§11) | Three experiments: EXP-005, EXP-014, EXP-022d | No defensible improvement anywhere | **Investigated in full and documented**; `Expertise`, `TeacherRating` and affinity remain available in the joins layer behind an opt-in flag |

**Every official requirement remains satisfied.** None was skipped; several were
implemented, measured, and then not promoted to the primary mechanism — which is
what evidence-based selection means.

---

## Evidence

| Artifact | Contains |
| --- | --- |
| `artifacts/phase2_audit.json` | Integrity, sparsity, signal detection, distributions |
| `artifacts/segmentation/segmentation_results.json` | 10 representations × 9 k values, stability, dominance, ablations |
| `artifacts/recommendation/recommendation_results.json` | 11 methods × 2 splits × 3 K values, significance, error analysis |
| `artifacts/architecture/architecture_validation.json` | The three assembled architectures; cold-start diversity |
| `research/dataset_audit.md` · `segmentation_results.md` · `recommendation_results.md` · `recommendation_error_analysis.md` | Narratives |
| `research/decision_log.md` | D-001 … D-039 |
| `research/experiment_log.md` | EXP-001 … EXP-027, including failures |
| `tests/` | **163 tests** |

---

## Final Metrics

**Segmentation** (fit window, 2,650 learners)

| Metric | Value |
| --- | --- |
| Silhouette | 0.1946 |
| Intra-cluster similarity | 0.416 |
| Per-cluster bootstrap Jaccard | 0.983 / 0.996 / 0.996 / 0.981 |
| Subsample consensus ARI | 0.987 |
| Seed stability ARI | 1.000 |
| Smallest cluster | 19.7% |
| Demographic block share | 0.0004 |

**Recommendation** (test window, 791 learners — the selected scorer)

| Metric | Value | Random |
| --- | --- | --- |
| NDCG@10 | 0.1138 | **0.1102** |
| Hit Rate@10 | 0.3590 | 0.3464 |
| Precision@10 | 0.0424 (21% of the 0.2054 ceiling) | 0.0422 |
| Recall@10 | 0.2080 | 0.1975 |
| MRR | 0.1412 | 0.1440 |
| Catalogue coverage@10 | 0.75 *(1.00 for the frozen tiered architecture)* | 1.00 |
| Engagement Lift (**Proxy**) | 1.084 | **1.046** |
| **Δ NDCG vs random** | **+0.0093, CI [−0.0092, +0.0271] — not significant** | — |

**Coverage**: 3,000 of 3,000 learners receive a recommendation; 2,650 (88.3%)
personalised; 350 (11.7%) on the labelled fallback; 0 with an empty pool.

---

## Final Model Version

```
edupro-1.0.0
  data          : EduPro Online Platform.xlsx  sha256 ed555e46…8cc0
  seed          : 42
  split         : validation 2025-09-12 · test 2025-10-18
  segmentation  : B_proportion · StandardScaler · KMeans(k=4, n_init=10)
  recommender   : TieredRecommender
                    insufficient → DiversifiedFallback
                    minimal      → ContentBased
                    moderate     → ClusterPopularity
                    rich         → ClusterPopularity
  explanation   : score decomposition, tier-honest
  environment   : Python 3.13.9 · scikit-learn 1.9.1 · numpy 2.5.3 · pandas 3.0.6
```

---

## 🔒 Freeze

**The methodology is frozen as of 19 September 2026.**

From this point the ML design does not change. Phase 5 implements exactly what is
specified here; Phase 6 validates and documents it.

**A change requires all four of:**
1. A new decision-log entry stating the change and the evidence for it.
2. New experimental evidence — not a preference, an intuition, or a nicer-looking
   number.
3. A recorded impact assessment on every affected layer (the CACE problem [R33]:
   re-fitting the clustering invalidates cluster popularity and any hybrid weights
   tuned against it).
4. Re-running the full test suite.

**What would legitimately reopen the freeze:** real (non-synthetic) EduPro data —
which would invalidate none of the *methodology* and all of the *findings*.
