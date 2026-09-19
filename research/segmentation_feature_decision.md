# Segmentation Feature Decision

**Phase:** 3A
**Date:** 19 September 2026
**Status:** Decided on evidence. Reversible in Phase 3B if the downstream check (EXP-023) contradicts it.
**Evidence:** `artifacts/segmentation/segmentation_results.json` · results narrative in `research/segmentation_results.md`

---

## The decision

> **Representation:** Variant B (behaviour only) · category as a 12-dimensional
> **share vector** · ordinal level one-hot · **StandardScaler** · no block
> weighting · no teacher block · no PCA.
>
> **Algorithm:** K-Means, k-means++ seeding, `n_init=10`, seed 42.
>
> **k = 4.**

Implemented as `RepresentationSpec(name="B_proportion", …)` in
`src/edupro/segmentation/representations.py`, which is the exact object the Phase
5 production pipeline will load.

---

## 1. Feature list

**25 columns**, in four blocks. Every feature the official brief mandates is
present; nothing was dropped to make the numbers look better.

### Engagement block (4)
| Feature | Definition |
| --- | --- |
| `total_courses` | count of interactions in the window |
| `avg_courses_per_category` | `total_courses / diversity_score` |
| `enrollment_frequency` | `total_courses / (activity_span_days + 1)` |
| `activity_span_days` | last interaction − first interaction |

### Behavioural block (6)
| Feature | Definition |
| --- | --- |
| `avg_course_rating` | mean `CourseRating` of enrolled courses |
| `avg_spend` | mean `Amount` |
| `diversity_score` | distinct categories explored |
| `learning_depth_index` | mean level ordinal (Beginner 0 → Advanced 2) |
| `free_ratio` | share of free courses |
| `diversity_ratio` | `diversity_score / total_courses` |

### Category block (12)
`cat_share_<category>` — the learner's share of enrollments in each of the twelve
categories, row-normalised to sum to 1.

### Level block (3)
`preflevel_Beginner`, `preflevel_Intermediate`, `preflevel_Advanced` — one-hot on
the modal course level.

### Excluded, with reasons
| Feature | Why excluded |
| --- | --- |
| `age`, `gender` | Variant A measured: ARI 1.000, demographic share 0.04%. No benefit; excluded on parsimony and privacy (§4) |
| `n_teachers`, `teacher_loyalty`, `avg_teacher_rating` | Teacher arm measured: +0.0009 silhouette, ARI 0.990. Not evidence of improvement (§5) |
| `total_spend` | r = +0.84 with `total_courses`; adds only volume already carried (Phase 2, D-020) |
| `category_entropy`, `top_category_share` | Available, but superseded by the full share vector which carries the same information with identity |
| `recency_days`, `first_interaction_days` | Reference-date dependent; useful for the recommender, not for a stable learner grouping |
| Level-progression slope | Measured in Phase 2: p = 0.664. No progression exists; the feature would encode noise (D-026) |
| `UserName`, `Email`, teacher `Age`/`Gender` | PII (§17) and third-party demographics (D-016) |

---

## 2. Encoding

### The decision: category as a proportion vector (E-B)

Four encodings were compared as complete arms:

| | Encoding | Category dims |
| --- | --- | --- |
| **E-A** | one-hot on the modal category | 12 |
| **E-B** | **share vector across categories** | **12** |
| E-C | breadth/concentration facets only | 3 |
| E-D | no category representation | 0 |

**Why E-B, given that the dominance risk turned out not to bite at k=4:**

1. **It carries preference shape, not just an argmax.** With a mean of 3.3 courses,
   the modal category is frequently a coin-toss between ties; the share vector
   represents a 50/50 learner as 50/50 rather than forcing them to one label.
2. **It is what the brief's own features are gesturing at.** "Average courses per
   category" and "diversity score" are both summaries of this same distribution.
3. **It is bounded in [0,1]** and sums to 1, so it needs no separate scaling
   decision and cannot silently acquire a large scale.
4. **It is directly readable** in a dashboard: "38% Data Science, 25% Business" is
   a sentence a stakeholder understands.

**Why not the alternatives:**

- **E-A (one-hot)** performs almost identically at k=4 (silhouette 0.212 vs 0.209
  at each arm's own best k; category share 3.7% vs 5.0% at the common k). It is
  rejected on information grounds — it discards the distribution — not on
  performance.
- **E-C (facets)** posts a higher silhouette (0.393) but **discards category
  identity entirely**, so no segment could be described as preferring anything in
  particular. It trades the interpretability the brief requires for a number.
- **E-D (no category)** posts the highest non-degenerate silhouette (0.435) at
  k=10 — but at k=10 five of ten clusters are unstable, and the arm cannot support
  the brief's "preferred course category" requirement at all.

> **The Phase 1 prediction was wrong, and is recorded as wrong.** Phase 1 expected
> one-hot to let a 12-level categorical dominate the distance metric. At k=4 the
> category block takes 3.7–5.0% of between-cluster variance under either encoding:
> level and volume swamp it. The mechanism does appear at k≥9 (46–58%), so the
> reasoning was sound — it simply does not apply at the k the stability constraint
> selects.

---

## 3. Scaling

**Decision: StandardScaler.** This settles the scaler choice deferred in Phase 1
(D5), on evidence rather than convention.

RobustScaler was tested and is **degenerate on this data**. Two mandated features
have an interquartile range of exactly zero:

| Feature | q25 | q50 | q75 | IQR |
| --- | --- | --- | --- | --- |
| `avg_courses_per_category` | 1.000 | 1.000 | 1.000 | **0.000** |
| `diversity_ratio` | 1.000 | 1.000 | 1.000 | **0.000** |

54% of learners have a single course, so for the majority both features equal 1.0
and all three quartiles coincide. RobustScaler leaves those columns unscaled while
compressing the others, manufacturing an artificially separable axis: its
silhouette of **0.716** is more than three times any other arm, and the k=2 split
it produces (2,198 / 452) is a rediscovery of the Phase 2 activity bimodality
through a scaling bug.

**A high silhouette obtained this way is a defect, not a result.** Reporting it as
the best representation would have been a clean example of optimising for the
number instead of the structure.

---

## 4. Variant A vs Variant B (CLAUDE.md §10)

| | Variant B (behaviour only) | Variant A (+ demographics) |
| --- | --- | --- |
| Dimensions | 25 | 27 |
| Silhouette @ k=4 | **0.1946** | 0.1729 |
| Intra-cluster similarity | 0.416 | 0.415 |
| Mean bootstrap Jaccard | 0.999 | 0.991 |
| Demographic block share | — | **0.0004** |
| Top feature | `preflevel_Intermediate` | `preflevel_Intermediate` |

**ARI between the two partitions: 1.000 — they are identical.**

Adding age and gender changes the segmentation *not at all*. The demographic block
explains **0.04%** of between-cluster variance, far below the 20% "secondary" band
of the pre-registered interpretation rule. Silhouette falls slightly, which is
simply the geometric cost of two uninformative dimensions.

**Decision: Variant B.** The pre-registered tie rule applies — on equal
performance, prefer the simpler, more privacy-respecting, more actionable model —
and here it is not even a tie, since Variant A is marginally worse on every metric.

This is the cleanest possible answer to §10: demographics do not merely fail to
dominate, they are **invisible**. It corroborates Phase 2, which already found age
and gender independent of course choice (all χ² p > 0.2).

**Retained for evaluation, not modelling.** Age and gender remain available as
*stratification variables* for Phase 3B (EXP-027), so the project can report
whether recommendation quality is equivalent across demographic groups [R30].
Auditing with a protected attribute is not the same as modelling with it.

---

## 5. Teacher features (CLAUDE.md §11)

| | Core (`B_proportion`) | Core + teacher (`B_teacher`) |
| --- | --- | --- |
| Dimensions | 25 | 28 |
| Silhouette @ k=4 | 0.1946 | **0.1955** (+0.0009) |
| Intra-cluster similarity | **0.416** | 0.415 |
| Mean bootstrap Jaccard | **0.999** | 0.989 |
| Teacher block share | — | 16.1% |
| Top feature | `preflevel_Intermediate` | **`teacher_loyalty`** |

**ARI core vs teacher: 0.990 — the partition barely moves.**

The teacher block becomes the *single most explanatory feature* and takes 16.1% of
between-cluster variance, yet changes nothing. The explanation is in the Phase 2
audit: `teacher_loyalty` correlates **+0.963** with `total_courses` and is zero by
construction for the 54% of learners with one course. Its η² reflects that
correlation, not new information.

**Decision: teacher features are NOT retained for segmentation.** §11 requires
defensible evidence of improvement; +0.0009 silhouette with an unchanged partition
and slightly worse stability is not that.

**Scope.** This rejection is about *grouping learners*. Phase 2 established
instructor loyalty as the one genuine behavioural signal in the dataset (0.688
distinct teachers per interaction against a 0.944 null), and it remains a live
candidate for the Phase 3B **recommender**, where predicting the next course is a
different problem.

---

## 6. Ablations that did not change the decision

| Ablation | Result | Decision |
| --- | --- | --- |
| **Block weighting** (1/√columns per block) | Silhouette 0.292 at its own best k=4; block shares nearly identical to unweighted at k=4 | **Not adopted** — no dominance to correct at k=4 |
| **Drop volume-redundant features** (`diversity_score`, `avg_courses_per_category`, `category_entropy`) | Best k=10, silhouette 0.267, but 5 unstable clusters and category share 58% | **Not adopted** — removes brief-mandated features and destabilises |
| **PCA before clustering** | Not adopted: components are linear combinations, destroying the interpretable centroid profiles the brief requires. PCA is used for the dashboard's 2-D projection only | **Visualisation only** |

---

## 7. The decisive ablation: `preferred_level` (EXP-011g)

Added after the first run revealed three of four clusters were 100% one course
level.

| | With level | Without level |
| --- | --- | --- |
| Dimensions | 25 | 22 |
| Silhouette | 0.1946 | 0.1877 |
| Mean bootstrap Jaccard | **0.999** | **0.656** |
| Unstable clusters | **0** | **1** |
| Top feature | `preflevel_Intermediate` | `cat_share_digital_marketing` |

**ARI with vs without: 0.253 — an almost entirely different partition.**

**The stable structure in this dataset *is* the course-level split.** Remove it and
the clustering falls back on category shares and stops being reproducible.

This is not a reason to reject the representation — `preferred_level` is a
brief-mandated feature (B7) and the partition it produces is stable, balanced and
interpretable. It *is* a reason to describe the result accurately: this is a
segmentation by **course depth and activity volume**, not a discovery of learner
motivations.

---

## 8. Dimensionality and missingness

**Dimensionality:** 25 columns for 2,650 learners — roughly 106 observations per
dimension, comfortable for K-Means. Distributed as engagement 4 · behavioural 6 ·
category 12 · level 3.

**Missingness treatment:** none required. The Phase 2 audit found **zero missing
values** across all 27 source columns, and the feature builder produces a value
for every active learner. A defensive `fillna(0.0)` exists in
`build_representation`, and a test asserts no representation ever contains NaN — so
that path is a bug detector, not an imputation strategy.

The one structural absence is **350 learners with no interaction before the test
cut**. They have no features in the fit window and are therefore not segmented
there. That is correct rather than a gap: a learner with no history is a
recommendation-tier decision (the "insufficient" tier), not a clustering problem.
The production artifact, refit on full history at deployment, covers all 3,000.

---

## 9. What would overturn this decision

Recorded so the decision is falsifiable rather than final by assertion.

| Finding | Consequence |
| --- | --- |
| **EXP-023 (Phase 3B):** cluster-popularity recommendation does not beat global popularity | The segmentation has no demonstrated *recommendation* value. It would retain standalone analytical value for the brief's learner-analysis requirement, and that distinction would need drawing carefully rather than blurring |
| Variant A produces materially better downstream NDCG@10 | Revisit Variant A despite the identical partitions — though with ARI 1.000 this is close to impossible |
| The teacher block improves downstream recommendation | Retain teacher features *in the recommender*; the segmentation decision stands regardless |
| Real (non-synthetic) EduPro data becomes available | Re-run the entire grid. Every conclusion here is conditioned on a dataset assessed as almost certainly generated (Phase 2, D-025) |
