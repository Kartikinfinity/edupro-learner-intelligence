# Student Segmentation and Personalized Course Recommendation System for EduPro

**A reproducible study of learner segmentation and course recommendation on the EduPro online learning platform**

**Author:** Anushree Menon
**Date:** 19 September 2026
**Model version:** `edupro-1.0.0` · artifact set `b658773c9db8`
**Source data:** `EduPro Online Platform.xlsx`, SHA-256 `ed555e4613e6a210b73af0d4f64e34bd43cb59650041e2bd05f8a8ffbf5d8cc0`
**Code and artifacts:** all results in this paper are reproducible via `scripts/verify_reproducibility.py`

---

## Note on evidence classes

Every substantive statement in this paper is tagged with what kind of claim it is.
The distinction matters because a dashboard reader, a stakeholder and a reviewer
each weigh these differently, and because the central finding of this study is a
negative one that is easy to overstate in either direction.

| Tag | Meaning |
| --- | --- |
| **[OBSERVED]** | A property counted directly from the source data. |
| **[MODEL]** | An output of a fitted model. |
| **[EXPERIMENT]** | A measured experimental result, with its artifact. |
| **[INTERPRETATION]** | The author's reading of a result. Falsifiable, not measured. |
| **[ENGINEERING]** | A design inference or decision, justified but not itself a measurement. |
| **[FUTURE]** | Work not done here. |

No claim of causal business impact is made anywhere in this paper. Where the
official brief requires an impact metric, it is reported as an **impact proxy**
and shown beside the value a random ranker achieves on the same measure.

---

## 1. Abstract

This paper reports the design, experimental evaluation and production
implementation of a learner segmentation and course recommendation system for the
EduPro online learning platform, using a dataset of **3,000 learners, 60 courses
and 10,000 enrollment transactions** **[OBSERVED]**.

A forensic data audit found the dataset internally consistent — zero missing
values across four sheets and 27 columns, zero referential-integrity violations —
but established three properties that govern everything downstream **[OBSERVED]**:
**54% of learners have exactly one enrollment**; **course popularity is
near-uniform** (140–196 enrollments per course, Gini 0.042, χ² against uniform
p = 0.605); and **course choice is statistically indistinguishable from
popularity-weighted chance** on three of four preference statistics measured
against a permutation null **[EXPERIMENT]**.

Ten feature representations were compared across k = 2…10 under a pre-registered
selection rule requiring every segment to hold at least 5% of learners *and* to
reappear under bootstrap resampling at Jaccard ≥ 0.60. The selected configuration
is a behaviour-only, 25-dimensional representation with K-Means at **k = 4**
(silhouette 0.1946, intra-cluster similarity 0.416, all four segments at bootstrap
Jaccard ≥ 0.9964, smallest segment 19.7%) **[EXPERIMENT]**. Segmentation with and
without demographics produced an **identical partition** (ARI = 1.000), so age and
gender were excluded from the model and retained only for fairness auditing
**[EXPERIMENT]**.

Eleven recommendation methods were evaluated on a leakage-free global temporal
split of 791 evaluable learners, with a random ranker as a mandatory reference in
every table. **No method is significantly better than random**: every 95%
confidence interval on the paired per-learner NDCG@10 difference against random
contains zero, random ranks 7th of 12, and five methods score below it
**[EXPERIMENT]**. A weighted hybrid led the field (NDCG@10 0.1206) but lost a
pre-registered parsimony rule; the deployed system is a four-tier switching
recommender whose personalised route is within-segment popularity, reaching the
**full catalogue** (coverage 1.00 against 0.78 for the flat alternative) at
statistically indistinguishable accuracy **[EXPERIMENT]**.

The negative result is reported as the headline rather than a footnote. The
contribution of this work is therefore methodological: a leakage-controlled
evaluation design, a pre-registered selection procedure, model-intrinsic
explanations verified exhaustively over 30,000 generated explanations, and a
production system whose 257-test suite and adversarial audit reproduce every
reported figure exactly in two independent environments.

---

## 2. Introduction

Online learning platforms accumulate enrollment histories that, in principle,
support two related products: grouping learners into interpretable segments that a
business can act on, and recommending courses that an individual learner is likely
to want next. EduPro's brief asks for both, delivered as a research paper, an
interactive dashboard and an executive summary.

The project was executed under a phase-gated engineering standard that forbids
proceeding to implementation before the data has been audited and the methodology
experimentally justified. That ordering turned out to be decisive. A conventional
project structure — build a recommender, then evaluate it — would have produced a
system whose reported accuracy looked reasonable and whose actual ranking quality
was indistinguishable from chance, because on a 60-course catalogue a ranker that
has learned nothing still achieves a Hit Rate@10 of approximately 0.35
**[EXPERIMENT]**.

Two design commitments made in the research phase, *before* any model was fitted,
are what make this paper's conclusions defensible **[ENGINEERING]**:

1. **A random baseline appears in every results table**, not as a courtesy but as
   the only reference against which a small catalogue's metrics can be read.
2. **Catalogue coverage is a co-primary metric**, because accuracy alone cannot
   distinguish a system that serves the whole catalogue from one that recommends
   the same twenty courses to everybody.

Both decisions were recorded in the experiment plan before results existed. They
are the reason the central finding of this study is stated rather than obscured.

---

## 3. Problem Statement

EduPro requires a system that:

1. segments its learner base into interpretable, actionable groups derived from
   behaviour rather than from assumption;
2. recommends courses to each learner, personalised where the data supports
   personalisation and honestly degraded where it does not;
3. explains every recommendation in terms a learner or administrator can check;
4. is deployable, reproducible and auditable rather than a notebook result.

The scientific problem underneath is narrower and harder: **determining whether
the available data supports personalised recommendation at all**, and reporting
that determination accurately whichever way it falls. A recommender can always be
built; whether it does anything is a separate question, and one that the majority
of the applied literature answers by comparison against under-tuned baselines
rather than against chance [R26].

---

## 4. Project Objectives

| # | Objective | Where addressed |
| --- | --- | --- |
| O1 | Aggregate transaction data to learner level and engineer behavioural, engagement and preference features | §9 |
| O2 | Segment learners using K-Means, validated by hierarchical clustering, with the cluster count chosen by evidence | §10, §11 |
| O3 | Build and compare at least five recommendation approaches, selecting on experimental evidence | §12, §13, §14 |
| O4 | Evaluate segmentation and recommendation with leakage control | §15, §16 |
| O5 | Explain every recommendation faithfully | §18 |
| O6 | Handle sparse and cold-start learners explicitly | §12, §16.5 |
| O7 | Deliver a deployable, reproducible production system | §20 |
| O8 | Report limitations and impact honestly, without causal claims | §17, §21, §22 |

---

## 5. Dataset Description

The source is a single Excel workbook of four sheets. It is treated as immutable:
its SHA-256 is verified before every pipeline run and re-verified afterwards
**[OBSERVED]**.

**Table 5.1 — Dataset composition** *(source: `artifacts/phase2_audit.json`, `sheet_profiles`)*

| Sheet | Rows | Columns | Duplicate rows | Role |
| --- | --- | --- | --- | --- |
| Users | 3,000 | 3 (after PII removal) | 0 | Learner demographics |
| Courses | 60 | 8 | 0 | Course catalogue |
| Transactions | 10,000 | 7 | 0 | Enrollment events |
| Teachers | 60 | 6 (after PII removal) | 0 | Instructor attributes |

**Table 5.2 — Interaction matrix properties** *(source: `artifacts/phase2_audit.json`)*

| Property | Value |
| --- | --- |
| Learners | 3,000 |
| Courses | 60 — exactly 5 in each of 12 categories |
| Interactions | 10,000 |
| Matrix density | 5.56% |
| Repeat `(learner, course)` pairs | **0** |
| Interactions per learner: mean / median / max | 3.333 / **1** / 16 |
| Learner-activity Gini | 0.546 |
| Time span | 2025-01-01 → 2025-12-30 |
| Missing values, all sheets | **0** |

**[OBSERVED]** The complete absence of repeat `(learner, course)` pairs means the
signal is **purely binary and implicit**. No confidence weighting is possible,
which has a direct methodological consequence recorded in §12.

`UserName`, `Email` and `TeacherName` are dropped at ingestion and are absent from
every downstream frame, artifact and figure (§19).

---

## 6. Data Quality Assessment

Twelve check families were run across sheet-level and cross-sheet properties.

**Table 6.1 — Validation outcome** *(source: `artifacts/phase2_audit.json`, `EXP-001_validation`)*

| Class | Count | Notes |
| --- | --- | --- |
| Errors | **0** | Schema, uniqueness, domains, ranges, referential integrity |
| Warnings | 1 | Two course titles are repeated across distinct `CourseID`s |
| Informational | 4 | Including the two findings below |

**[OBSERVED]** Three quality findings materially affected the modelling.

**6.1 `Amount` is identical to `CoursePrice` on all 10,000 rows.**
Both carry exactly 23 distinct values, and the match rate is 1.000
**[EXPERIMENT]**. **[INTERPRETATION]** "Average spending per learner", which the
brief mandates as a feature, is therefore a deterministic function of *which
courses were chosen* rather than an independent behavioural signal. The feature is
retained because the brief requires it, and the redundancy is stated wherever it
is reported.

**6.2 `CourseType` is a deterministic function of `CoursePrice`.**
Free ⟺ price = 0, with no exceptions **[OBSERVED]**. The two fields are redundant;
only the derived `free_ratio` enters the model.

**6.3 Two course titles repeat across distinct course IDs.**
58 distinct names across 60 courses **[OBSERVED]**. **[ENGINEERING]** Titles
therefore cannot identify a course, and text-based content similarity over titles
would be near-degenerate. The content representation uses structured attributes
only (§9.2).

**6.4 The dataset is assessed as almost certainly synthetic.** **[INTERPRETATION]**
Zero missing values across 27 columns; 21 distinct ages in *both* the Users and
Teachers sheets; 23 distinct values in *both* `Amount` and `CoursePrice`; exactly
five courses in each of twelve categories (χ² = 0.0, p = 1.0); age, gender,
payment method and transactions-per-day all statistically indistinguishable from
uniform **[EXPERIMENT]**. This assessment is not a defect finding — the data is
internally consistent — but it bounds what any result here can be claimed to mean
about real learners.

---

## 7. Exploratory Data Analysis

Figures in this section are generated by `scripts/generate_eda_figures.py` and
stored under `artifacts/eda/`. No figure in this paper was drawn by hand.

### 7.1 Interaction sparsity

**Table 7.1 — Enrollments per learner** *(source: `EXP-003_sparsity`; figure: `artifacts/eda/01_interaction_distribution.png`)*

| Enrollments | Learners | Share |
| --- | --- | --- |
| 1 | 1,620 | **54.0%** |
| 2 | 612 | 20.4% |
| 3 | 186 | 6.2% |
| 4 | 128 | 4.3% |
| **5–8** | **0** | **0.0%** |
| 9–16 | 454 | 15.1% |

**[OBSERVED]** The distribution is **bimodal with a hard empty band at 5–8
enrollments**. 2,546 "light" learners (1–4 courses) account for 3,914 interactions;
454 "heavy" learners (9–16) account for 6,086 — more than half the data from 15% of
the learners.

**[ENGINEERING]** The empty band is why the recommendation tier boundary between
"moderate" and "rich" is drawn at 9: the cut passes through a region containing no
learners, so it is handed over by the data rather than tuned.

Activity is heavily over-dispersed relative to Poisson (mean 3.33, variance 18.94)
**[OBSERVED]**.

### 7.2 Course popularity

**Table 7.2 — Popularity concentration** *(source: `EXP-006_distributions`; figures: `artifacts/eda/02_course_popularity.png`, `03_lorenz_concentration.png`)*

| Statistic | Value |
| --- | --- |
| Enrollments per course: min / mean / max | 140 / 166.7 / 196 |
| Standard deviation | 12.52 |
| **Gini coefficient** | **0.042** |
| χ² against uniform | 55.52 (dof 59), **p = 0.605** |

**[INTERPRETATION]** This is the single most consequential property of the
dataset. Real catalogues are heavily long-tailed, and popularity is a strong
recommendation signal precisely because of that skew [R28]. Here popularity is
almost flat, so it carries almost no ranking information — which predicts, before
any recommender is built, that popularity-based methods will be weak.

### 7.3 Signal detection against a permutation null

Four learner-preference statistics were compared against a **popularity-matched
permutation null** (200 permutations, seed 42): if learners chose courses at random
with the observed popularity distribution, what would these statistics look like?

**Table 7.3 — Preference statistics vs null** *(source: `signal_detection`; figure: `artifacts/eda/06_signal_detection.png`)*

| Statistic | Observed | Null mean | Null 95% CI | z | Signal? |
| --- | --- | --- | --- | --- | --- |
| Mean distinct categories | 2.577 | 2.587 | [2.571, 2.602] | −1.17 | No |
| Mean top-category share | 0.721 | 0.719 | [0.717, 0.722] | +1.13 | No |
| Mean free-course share | 0.650 | 0.639 | [0.626, 0.654] | +1.51 | No |
| **Mean distinct levels** | **1.556** | 1.571 | [1.560, 1.582] | **−2.65** | **Yes** |

**[EXPERIMENT]** Three of four statistics fall inside the null. The fourth —
learners concentrate on slightly *fewer* course levels than chance — is marginally
outside it.

**[INTERPRETATION]** Category preference, concentration and price sensitivity are
indistinguishable from chance in this dataset. A weak but real tendency exists for
learners to stay at one course *level*. This single detected signal anticipates the
segmentation result in §11: the structure the clustering finds is a level-based
grouping.

### 7.4 Demographics and choice

**Table 7.4 — Independence tests** *(source: `signal_detection.demographics_vs_choice`; figure: `artifacts/eda/07_demographics.png`)*

| Test | χ² | dof | p | Dependent? |
| --- | --- | --- | --- | --- |
| Gender × category | 8.77 | 11 | 0.643 | No |
| Gender × level | 0.20 | 2 | 0.906 | No |
| Age band × category | 33.17 | 33 | 0.459 | No |
| Age band × level | 8.43 | 6 | 0.208 | No |

**[EXPERIMENT]** No demographic attribute is associated with course choice.
**[INTERPRETATION]** This is the first of three independent lines of evidence
against including demographics in the model (§11.3).

### 7.5 Instructor reuse — the one genuine behavioural signal

**[EXPERIMENT]** Learners take courses from **0.688 distinct teachers per
interaction** against a null of 0.944 (95% CI [0.941, 0.948]) — far outside the
null. Instructor reuse is real and strong.

**[EXPERIMENT]** However, its predictive value for the *next course* is small: a
hit rate of 0.4899 against a chance rate of 0.4470, a lift of **1.096**. Each
teacher covers roughly 25 of a learner's ~55 unseen courses, so knowing the
instructor barely narrows the choice.

**[INTERPRETATION]** A strong signal about *who teaches* need not be a useful
signal about *what to recommend*. This distinction is what the teacher-feature
experiments in §11.4 and §13.6 test, and it is why they were run rather than
assumed either way.

### 7.6 Other structural findings

| Finding | Evidence |
| --- | --- |
| No level progression over time | Slope +0.0053, t = 0.435, **p = 0.664**, n = 735 **[EXPERIMENT]** |
| Median inter-enrollment gap 23 days | mean 39.3, max 347 **[OBSERVED]** |
| Transactions uniform across days | χ² = 380.85, dof 357, p = 0.184 **[EXPERIMENT]** |
| Light and heavy cohorts behave alike | free share 0.652 vs 0.633; mean rating 3.139 vs 3.113; mean age 24.98 vs 24.95 **[OBSERVED]** (figure: `artifacts/eda/10_cohort_comparison.png`) |

**[INTERPRETATION]** The absence of level progression is notable: learners do not
move from Beginner toward Advanced over time. A proposed "learning trajectory"
feature was therefore rejected on measurement rather than retained on intuition.

---

## 8. Literature Review

Forty references were verified by retrieval during the research phase; the full
annotated review is in `research/literature_review.md`. This section summarises
what the literature contributed to each decision. All reference keys resolve in §25.

**8.1 Clustering.** Silhouette [R01] and the gap statistic [R02] are the standard
cluster-count instruments; Milligan & Cooper [R06] compared thirty such procedures
and found none universally reliable, and Ketchen & Shook [R07] document that the
elbow method is subjective. **[ENGINEERING]** This is why the selection rule used
here combines multiple diagnostics with hard constraints rather than trusting any
one curve. Stability-based validation [R03][R04][R05] supplied the constraint that
ultimately decided k: a cluster that does not reappear under resampling is not a
segment. Ward linkage [R08] and k-means++ [R09] are the standard algorithms used.
Kizilcec et al. [R12] provide the best-known MOOC learner taxonomy — and, as §10.4
explains, a cautionary example rather than a template.

**8.2 Recommendation.** Hu et al. [R13] require repeat observations for confidence
weighting; this dataset has none, which excludes implicit-feedback matrix
factorisation on mechanical grounds. BPR [R14] is under-identified at 10,000
positives over 60 items. Item-based collaborative filtering [R15][R16] is
well-suited to a catalogue where each item has far more evidence than each user.
Burke's hybrid taxonomy [R17] separates *weighted* from *switching* hybrids — a
distinction this project uses directly, evaluating both. Content-based methods
[R18] and cold-start analysis [R19] inform the tier design.

**8.3 Evaluation.** Cremonesi et al. [R20] establish top-N protocol conventions;
Järvelin & Kekäläinen [R23] define NDCG. Meng et al. [R24] and Ji et al. [R25]
document that data-splitting strategy changes not just absolute numbers but
*method rankings*, and that per-user leave-one-out leaks along a global timeline —
directly motivating the protocol choice in §15. Ferrari Dacrema et al. [R26]
reproduced only 7 of 18 neural recommendation papers, most of which were beaten by
tuned simple baselines: the strongest available argument for making the baselines
in §13 genuinely competitive rather than strawmen. Coverage as a first-class metric
comes from Ge et al. [R27]; popularity bias from [R28][R29]; demographic evaluation
strata from Ekstrand et al. [R30].

**8.4 Explainability and fairness.** Zhang & Chen [R31] distinguish *model-intrinsic*
from *post-hoc* explanation. **[ENGINEERING]** Only the former can be faithful, and
this distinction, adopted before any recommender was written, is why the scoring
interface returns per-component contributions rather than a scalar (§18). Tintarev
& Masthoff [R32] supply explanation aims; Barocas et al. [R38] the fairness framing
used in §19.

**8.5 Production.** Sculley et al. [R33] name the CACE problem — *changing anything
changes everything* — which motivates the versioned, matched artifact set in §20.
Breck et al. [R34] supply the production-readiness rubric. [R35][R36][R37] are the
tooling references.

**[ENGINEERING]** The literature shaped the *methodology* and the *evaluation
design*. It did not select the model: every selection in this paper was made from
measurements on this dataset, several of which contradicted what the literature
predicted (§16.6).

---

## 9. Feature Engineering

### 9.1 Learner features

All eleven features named in the official brief are implemented. The production
representation is 25-dimensional in four blocks.

**Table 9.1 — Learner feature schema** *(implementation: `src/edupro/features/learner.py`; figures: `artifacts/eda/08_feature_correlation.png`, `09_feature_distributions.png`)*

| # | Feature | Block | Definition | In model? | Note |
| --- | --- | --- | --- | --- | --- |
| 1 | `total_courses` | Engagement | Distinct courses enrolled | ✅ | Brief-mandated |
| 2 | `avg_courses_per_category` | Engagement | `total_courses / diversity_score` | ✅ | Brief-mandated |
| 3 | `enrollment_frequency` | Engagement | Enrollments per active day | ✅ | Brief-mandated |
| 4 | `activity_span_days` | Engagement | Last minus first enrollment | ✅ | Added, §7.6 |
| 5 | `avg_course_rating` | Behavioural | Mean rating of chosen courses | ✅ | Brief-mandated |
| 6 | `avg_spend` | Behavioural | Mean transaction amount | ✅ | Brief-mandated; degenerate (§6.1) |
| 7 | `diversity_score` | Behavioural | Distinct categories | ✅ | Brief-mandated |
| 8 | `learning_depth_index` | Behavioural | Mean level ordinal (0–2) | ✅ | Brief-mandated |
| 9 | `free_ratio` | Behavioural | Share of free courses | ✅ | Added |
| 10 | `diversity_ratio` | Behavioural | `diversity_score / total_courses` | ✅ | Added |
| 11 | `cat_share_*` (12) | Category | Row-normalised category shares | ✅ | Implements "preferred category" |
| 12 | `preflevel_*` (3) | Level | One-hot preferred level | ✅ | Brief-mandated |
| 13 | `age`, `gender` | Demographic | From Users sheet | ❌ | Implemented; excluded on evidence (§11.3) |
| 14 | `category_entropy`, `top_category_share` | Facets | Breadth and concentration | ❌ | Used in an ablation arm only |
| 15 | Teacher block (3) | Teacher | Loyalty, count, mean rating | ❌ | Rejected on evidence (§11.4, §13.6) |

**[ENGINEERING]** Two representation decisions deserve explicit justification.

**Category as a share vector, not a modal label.** The brief asks for "preferred
course category". At a mean of 3.3 enrollments the *modal* category is close to a
coin toss, and one-hot encoding it would add 12 binary columns against ~10
behavioural ones — spending more than half the Euclidean distance budget on a
single conceptual variable. The 12-dimensional share vector preserves the shape of
a learner's preference and is bounded in [0, 1]. Both encodings were evaluated
(§11.2); this reasoning is an inference, the comparison is the evidence.

**Features excluded by measurement, not by taste.** `total_spend` correlates
+0.84 with `total_courses`; a level-progression slope was measured at p = 0.664
(§7.6) and dropped; `PaymentMethod` is uniform (p = 0.397) with no plausible
mechanism.

### 9.2 Course features

The content representation is an 18-dimensional vector per course: 12 category
one-hot, 3 level one-hot, plus `is_free`, min-max scaled `rating`, and min-max
scaled `duration` **[ENGINEERING]**. Numeric attributes are scaled so that course
duration — which spans hours — does not dominate cosine similarity over rating,
which spans roughly one point. Course titles are excluded for the reason in §6.3.

---

## 10. Learner Segmentation Methodology

### 10.1 Pipeline

```
learner features (25 columns)
  → StandardScaler (fitted on the training window)
  → KMeans(n_clusters=4, init="k-means++", n_init=10, random_state=42)
  → segment label per learner
```

### 10.2 Cluster-count selection rule (pre-registered)

Registered before results existed:

> Use the gap statistic first; if it indicates k = 1, report no cluster structure.
> Otherwise select the k maximising mean silhouette **subject to both constraints**:
> every cluster holds ≥ 5% of learners **and** every cluster reaches bootstrap
> Jaccard ≥ 0.60.

**[ENGINEERING]** The size constraint makes segments actionable; the stability
constraint makes them real. Pre-registering both is what prevents the selection
from drifting toward whatever k the data happened to favour.

### 10.3 Scaling

StandardScaler was selected over RobustScaler on evidence (§11.5).

### 10.4 Segment naming

Names are derived mechanically, never chosen **[ENGINEERING]**:

1. Compute per-cluster feature means in population standard deviations.
2. Keep deviations ≥ 0.40 SD, ranked by magnitude.
3. Map each to a controlled vocabulary in which every phrase is licensed by the
   feature that produced it.
4. Restrict naming to **features the clustering actually used** — an early run
   produced "Instructor-loyal" from teacher features the model never saw.
5. Where a cluster is ≥ 90% pure on one course level, prefix that level.

**[ENGINEERING]** Kizilcec et al.'s MOOC vocabulary [R12] — "auditing",
"completing", "sampling" — is deliberately barred and the exclusion is enforced by
test. Those labels were derived from longitudinal engagement traces; EduPro has no
completion data at all, so borrowing them would import conclusions the data cannot
support.

---

## 11. Segmentation Experiments

All results below are measured on the fit window (2,650 learners) and stored in
`artifacts/segmentation/segmentation_results.json`.

### 11.1 Cluster-count sweep

**Table 11.1 — k sweep under the pre-registered constraints** *(figures: `artifacts/segmentation/01_elbow_and_silhouette.png`, `02_k_selection_constraints.png`)*

| k | Silhouette | Smallest cluster | Clusters below Jaccard 0.60 | Passes rule? |
| --- | --- | --- | --- | --- |
| 2 | 0.1771 | 20.0% | 0 | ✅ |
| 3 | 0.1733 | 19.9% | 0 | ✅ |
| **4** | **0.1946** | **19.7%** | **0** | ✅ **SELECTED** |
| 5 | 0.2019 | 5.4% | 1 | ❌ |
| 6 | 0.2089 | 6.2% | 2 | ❌ |
| 7 | 0.2305 | 4.6% | 5 | ❌ |
| 8 | 0.2349 | 4.9% | 6 | ❌ |
| 9 | 0.2613 | 4.7% | 6 | ❌ |
| 10 | 0.2685 | 4.4% | 5 | ❌ |

**[EXPERIMENT]** Silhouette rises monotonically with k. Unconstrained, it selects
k = 10 — where **five of ten clusters fail to reappear under bootstrap
resampling**. The constraints leave k ∈ {2, 3, 4}, and 4 has the highest silhouette
among them.

**[INTERPRETATION]** This is the clearest illustration in the project of why a
single metric cannot choose a model. Reported alone, "silhouette 0.269 at k = 10"
would look like the better result.

**The elbow method was produced as the brief requires and did not decide the
answer.** Inertia falls monotonically from 55,391 at k = 2 with no knee
**[EXPERIMENT]** — exactly the subjectivity [R07] documents.

**The gap statistic failed as an instrument.** Extended to k = 1…20 specifically so
that "no cluster structure" could be reported if true, it rose monotonically from
0.413 to 1.311 with no interior optimum **[EXPERIMENT]**. **[INTERPRETATION]** It
returned no verdict. This is reported as a failed instrument rather than omitted,
and it means the project has **no instrument capable of falsifying cluster
structure** — a real limitation (§21).

### 11.2 Representation comparison

**Table 11.2 — Ten representations** *(each at its best k under the 5% size constraint; figure: `artifacts/segmentation/06_representation_comparison.png`)*

| Representation | d | Best k | Silhouette | Intra-cluster sim. | Smallest cluster | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| B_robust_scaled | 25 | 2 | *0.7159* | 0.239 | 17.1% | **Rejected — scaling artefact** |
| B_no_category | 13 | 10 | 0.4349 | 0.711 | 6.0% | Rejected — no category identity |
| B_facets | 15 | 2 | 0.3933 | 0.287 | 20.4% | Rejected — loses identity |
| B_no_level | 22 | 9 | 0.3027 | 0.393 | 4.7% | Rejected — 1 unstable cluster |
| B_proportion_weighted | 25 | 4 | 0.2922 | 0.420 | 19.6% | Rejected — no dominance to correct |
| B_decorrelated | 23 | 10 | 0.2666 | 0.386 | 5.0% | Rejected — drops mandated features |
| B_teacher | 28 | 2 | 0.2212 | 0.288 | 20.1% | Rejected — §11.4 |
| A_proportion | 27 | 9 | 0.2188 | 0.398 | 5.1% | Rejected — §11.3 |
| B_one_hot | 25 | 2 | 0.2115 | 0.285 | 20.0% | Rejected — discards distribution |
| **B_proportion** ✅ | 25 | **4** | 0.1946 | **0.416** | **19.7%** | **SELECTED** |

**[INTERPRETATION]** The selected representation has the *lowest* silhouette in the
table. It was chosen because it is the only arm that combines an interpretable
category representation, a stable partition at an actionable k, and the highest
behavioural consistency (intra-cluster similarity 0.416) — the measure the brief
actually names. Optimising the headline number would have selected a pathology
(§11.5) or a fragmented partition.

### 11.3 Demographics: Variant A vs Variant B

**Table 11.3 — With and without demographics, at k = 4** *(figure: `artifacts/segmentation/07_variant_and_teacher.png`)*

| Arm | d | Silhouette | Demographic block share of between-cluster variance |
| --- | --- | --- | --- |
| B_proportion (behaviour only) | 25 | **0.1946** | — |
| A_proportion (+ age, gender) | 27 | 0.1729 | **0.0004** |
| **Adjusted Rand Index between the two partitions** | | **1.000** | |

**[EXPERIMENT]** The two variants produce an **identical partition**. The
demographic block explains 0.04% of between-cluster variance, and adding it
*lowers* silhouette.

**[INTERPRETATION]** Demographics are not secondary to the segmentation — they are
invisible to it. Combined with the independence tests in §7.4, the evidence against
including them is unambiguous. **[ENGINEERING]** Age and gender are retained in the
feature builder and displayed in the dashboard, and are used as **evaluation
strata** for fairness auditing [R30] — auditing with a protected attribute is not
modelling with it.

### 11.4 Teacher signals

**Table 11.4 — Core vs core + teacher block, at k = 4**

| Arm | d | Silhouette | Intra-cluster sim. | Mean bootstrap Jaccard |
| --- | --- | --- | --- | --- |
| B_proportion | 25 | 0.194600 | 0.4163 | **0.9985** |
| B_teacher | 28 | 0.195515 | 0.4154 | 0.9891 |
| **ARI between the two partitions** | | **0.990** | | |

**[EXPERIMENT]** Adding the teacher block changes silhouette by **+0.0009**,
slightly *worsens* intra-cluster similarity and stability, and yields a near-identical
partition. The teacher block absorbs 16.1% of between-cluster variance while
changing nothing, and `teacher_loyalty` correlates **+0.963** with `total_courses`.

**[INTERPRETATION]** The teacher features are re-measuring enrollment volume under
another name. They are excluded. This experiment was run rather than skipped
because §7.5 showed instructor reuse to be the dataset's only genuine behavioural
signal — the hypothesis was reasonable and the measurement rejected it.

### 11.5 The RobustScaler artefact

**[EXPERIMENT]** `B_robust_scaled` achieves silhouette **0.716** — three times any
other arm. Investigation found the cause: two brief-mandated features
(`avg_courses_per_category`, `diversity_ratio`) have an **interquartile range of
exactly zero**, because 54% of learners have one course and their quartiles
coincide. RobustScaler divides by the IQR, leaving those columns unscaled while
compressing the others, and manufactures a separable axis.

**[INTERPRETATION]** The highest number in the entire segmentation study is an
artefact of an interaction between a scaler and a sparsity property. It is reported
here because rejecting it is the single clearest demonstration that this project
optimised for structure rather than for metrics.

### 11.6 Hierarchical validation — a negative result

**Table 11.5 — Algorithm agreement at k = 4** *(figure: `artifacts/segmentation/09_hierarchical_validation.png`)*

| Comparison | ARI |
| --- | --- |
| K-Means vs Ward linkage | 0.350 |
| K-Means vs average linkage | **0.019** |
| Ward vs average linkage | 0.026 |

**[EXPERIMENT]** Average linkage places 2,406 of 2,650 learners (91%) in a single
cluster. Agreement with K-Means is essentially zero.

**[INTERPRETATION]** The structure is **not algorithm-independent**. It is found by
variance-minimising methods (K-Means, Ward — which share an objective family) and
not by others. This is a genuine weakness of the segmentation and is reported as
one rather than omitted because the brief asked for hierarchical clustering as
"validation".

### 11.7 The segments

**Table 11.6 — Segment profiles** *(fit window, n = 2,650; source: `artifacts/segmentation/cluster_profiles.csv`; figures: `03_cluster_sizes_and_stability.png`, `04_cluster_profile_heatmap.png`, `05_level_composition.png`)*

| # | Name | n | Share | Courses | Categories | Depth | Span (days) | Rating | Spend | Level mix |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Beginner-level Single-course learners | 715 | 27.0% | 1.34 | 1.34 | 0.09 | 29.1 | 3.26 | 102.7 | Beginner 100% |
| 1 | Category-repeating High-volume learners | 522 | 19.7% | **9.65** | 6.84 | 0.98 | **227.0** | 3.12 | 93.8 | Advanced 44%, Beginner 39%, Intermediate 16% |
| 2 | Advanced-level Non-repeating learners | 881 | 33.3% | 1.51 | 1.50 | 1.77 | 40.5 | 2.87 | 78.0 | Advanced 100% |
| 3 | Intermediate-level Single-session learners | 532 | 20.1% | 1.25 | 1.25 | 1.00 | 18.3 | 3.39 | 83.5 | Intermediate 100% |

**Table 11.7 — Segment stability** *(source: `EXP-013_stability`)*

| Measure | Value |
| --- | --- |
| Mean bootstrap Jaccard (100 resamples) | **0.9892** |
| Clusters below the 0.60 threshold | **0** |
| Subsample consensus ARI | 0.987 |
| Seed-stability ARI (10 seeds) | 0.99959 |

**[EXPERIMENT]** All four segments are highly stable.

**[INTERPRETATION]** Three of the four segments are **100% pure on one course
level**, and a level ablation confirms the dependence: removing the level block
drops the smallest cluster to 4.7% and produces an unstable cluster. Block
attribution assigns 31.1% of between-cluster variance to the level block, 32.0% to
engagement, 31.9% to behavioural features and just 5.0% to the 12 category columns
**[EXPERIMENT]**.

**The honest description is therefore: the segmentation is a course-level split
crossed with an activity-volume split.** Segment 1 is a genuine behavioural group —
high-volume learners who repeat within categories, with a 227-day activity span
against ~30 for everyone else. The other three separate mainly by the level of the
single course their members took. For roughly 80% of learners, "preferred level" is
the level of one enrollment, and §7.3 measured level choice as only marginally
non-random. This bounds the interpretive weight the segments can carry (§21).

---

## 12. Recommendation System Methodology

### 12.1 What the data permits

**[ENGINEERING]** Three dataset properties eliminate whole method families before
any experiment:

| Property | Consequence |
| --- | --- |
| Zero repeat `(user, course)` pairs | Implicit-feedback matrix factorisation [R13] is inoperative — confidence weighting requires repeat observations |
| 10,000 positives over 60 items | BPR [R14] is under-identified |
| 54% single-interaction learners | User-user similarity is estimated from almost nothing for the majority |
| 60-item catalogue, near-uniform popularity | Random ranking is a strong baseline; reporting accuracy without it would mislead |

Neural recommenders were excluded on three independent grounds: far too little
data, uninterpretable latent factors conflicting with the explainability
requirement, and [R26]'s reproducibility finding.

### 12.2 The deployed architecture

A **switching hybrid** [R17] routing on training-window history only:

**Table 12.1 — Routing tiers** *(learner counts from `EXP-009_coverage_accounting`, fit window)*

| Tier | Training history | Learners | Share | Route |
| --- | --- | --- | --- | --- |
| insufficient | 0 | 350 | 11.7% | `DiversifiedFallback` |
| minimal | 1 | 1,514 | 50.5% | `ContentBased` |
| moderate | 2–8 | 731 | 24.4% | `ClusterPopularity` |
| rich | ≥ 9 | 405 | 13.5% | `ClusterPopularity` |

**[ENGINEERING]** Boundaries come from the interaction distribution (§7.1), not
from tuning. Routing on training-window history — not total history — is a leakage
control: a learner with one training and one held-out interaction has two in total,
and routing on the total would let the held-out item's existence influence the
routing decision.

### 12.3 Ranking logic

1. Candidates = all 60 courses minus those enrolled **in the training window**.
2. Score each candidate by the routed scorer.
3. Sort descending, **ties broken by catalogue index**.
4. Return the top K.

**[ENGINEERING]** Deterministic tie-breaking is not cosmetic: on a near-uniform
catalogue ties are common (21 tied adjacent pairs in a top-60 for a typical rich
learner **[EXPERIMENT]**), and an arbitrary order would make results irreproducible
across processes.

---

## 13. Recommendation Baselines

Eleven methods were implemented, each given the same treatment rather than serving
as a strawman [R26].

| # | Method | Signal |
| --- | --- | --- |
| 1 | `random` | Uniform ranking — the reference floor |
| 2 | `global_popularity` | Training-window enrollment count |
| 3 | `rating` | Course rating alone |
| 4 | `content_based` | Cosine between learner content profile and course vector |
| 5 | `preference_match` | Category share vector + level proximity |
| 6 | `item_item_cf` | Item co-occurrence cosine [R15][R16] |
| 7 | `user_user_history` | Learner similarity over raw interaction vectors |
| 8 | `user_user_profile` | Learner similarity over engineered features |
| 9 | `cluster_popularity` | Popularity within the learner's segment |
| 10 | `teacher_affinity` | Overlap with previously chosen instructors |
| 11 | `diversified_fallback` | Popularity + rating, re-ranked round-robin by category |

**[ENGINEERING]** Three inclusions beyond the brief's five require justification.
**Random** is the reference floor — on 60 courses it achieves Hit Rate@10 ≈ 0.35,
so its omission would make every other number look like success. **Item-based CF**
is included because each course has ~167 interactions while each learner has ~3.3,
so item-item similarity is estimated from roughly 50× more evidence per entity.
**Teacher affinity** tests §7.5's signal on the recommendation task directly.

---

## 14. Hybrid Recommendation Method

A **weighted hybrid** [R17] combining six min-max-scaled component scores. Weights
were found by a 400-sample Dirichlet search over the simplex on the **validation**
window — never asserted.

**Table 14.1 — Searched weights** *(source: `EXP-024_weight_search`; figure: `artifacts/recommendation/05_weights_and_ablation.png`)*

| Component | Weight |
| --- | --- |
| `cluster_popularity` | **0.557** |
| `rating` | 0.249 |
| `item_item_cf` | 0.173 |
| `preference_match` | 0.021 |
| `content_based` | 0.000 |
| `user_user_profile` | 0.000 |

**Table 14.2 — Component ablation** *(source: `EXP-024b_ablation`; validation NDCG@10 of the full hybrid = 0.1148)*

| Removed | Δ NDCG@10 | Δ Coverage |
| --- | --- | --- |
| `rating` | **−0.0102** | +0.167 |
| `cluster_popularity` | −0.0088 | −0.267 |
| `item_item_cf` | −0.0036 | −0.117 |
| `preference_match` | +0.0002 | 0.000 |
| `content_based` | 0.000 | 0.000 |
| `user_user_profile` | 0.000 | 0.000 |

**[EXPERIMENT]** The search assigned zero weight to two of six components, and
ablation confirms that removing them changes nothing. Rating contributes most to
accuracy while *costing* coverage — removing it raises coverage from 0.80 to 0.97.

**[INTERPRETATION]** The hybrid is effectively a three-signal model. The
accuracy–coverage tension inside it is visible in a single row: the component that
helps accuracy most is the one that most concentrates recommendations.

---

## 15. Temporal Evaluation Methodology

### 15.1 Protocol A — global temporal split (primary)

**Table 15.1 — Split** *(source: `EXP-004_temporal_split`)*

| Window | Range | Rows | Role |
| --- | --- | --- | --- |
| Training | < 2025-09-12 | 6,992 | Features, popularity, similarity |
| Validation | 09-12 → 10-18 | 1,000 | **All model selection** |
| Fit | < 2025-10-18 | 7,992 | Final training |
| Test | ≥ 2025-10-18 | 2,008 | **Opened exactly once** |

Evaluable learners: **791** (≥1 training and ≥1 held-out interaction), against a
pre-registered viability threshold of 300 **[EXPERIMENT]**.

### 15.2 Leakage controls

Six controls, verified in-run at every evaluation:

| ID | Control | Enforced by |
| --- | --- | --- |
| L1 | Features from the training window only | `build_learner_features` reads only its argument |
| L2 | Candidates exclude training-window enrollments only | Base recommender class |
| L3 | Tier assignment from training history only | `context.history_length` |
| L4 | Held-out items absent from every fitted structure | Fit context built from the training frame |
| L5 | Popularity counted on the training window | `course_popularity(frame)` takes the frame explicitly |
| L6 | Selection on validation; test opened once | Pre-registered protocol |

**[ENGINEERING]** L2 is counter-intuitive and worth stating precisely: candidates
exclude *training-window* enrollments, not full history. Removing the held-out
course from the candidate pool would leak — it tells the model which course to
avoid.

**[EXPERIMENT]** The controls were verified by experiment, not inspection. A
synthetic interaction dated 45 days after the test cut was injected into the source
data and the training-window features rebuilt: **every value came back identical**
across 2,450 learners. The leakage checker is itself tested against a deliberately
leaky fixture, so it is known to be capable of failing.

### 15.3 Protocol B — per-user leave-one-out (secondary, labelled leaky)

**[EXPERIMENT]** Protocol B moves five methods by three or more rank positions
relative to Protocol A: `item_item_cf` rises 9th → 3rd; `random` falls 6th → 11th.

**[INTERPRETATION]** Meng et al. [R24] reproduced on EduPro. A project using
leave-one-out alone would have concluded that item-based CF was a top-three method
and random was near-worst. Neither holds under the leakage-free protocol. Protocol
B is retained and reported, labelled as leaky, because it is the convention much
published work uses.

### 15.4 Metrics

NDCG@10 primary [R23]; catalogue coverage co-primary [R27]; Hit Rate, Recall, MRR,
Gini secondary. **Precision is always reported against its analytical ceiling.**

**[ENGINEERING]** On this evaluation Precision@10 cannot exceed **0.2054**: learners
have on average 2.05 held-out courses, so a perfect ranker still fills eight of ten
slots with courses it cannot be credited for. Reporting Precision@10 = 0.042
without that ceiling would understate performance by a factor of five.

---

## 16. Experimental Results

### 16.1 The headline

**Table 16.1 — All methods, test window, 791 learners, K = 10**
*(source: `artifacts/recommendation/recommendation_results.json`; figures: `01_method_comparison.png`, `02_significance_vs_random.png`, `08_precision_ceiling.png`)*

| Method | NDCG@10 | Hit Rate | Precision (ceiling 0.2054) | Recall | MRR | Coverage | Gini | Δ vs random | 95% CI | Sig.? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid | 0.1206 | 0.3578 | 0.0435 | 0.2101 | 0.1511 | 0.92 | 0.631 | +0.0162 | [−0.0033, +0.0355] | No |
| content_based | 0.1191 | 0.3666 | 0.0439 | 0.2205 | 0.1427 | 1.00 | 0.498 | +0.0147 | [−0.0040, +0.0340] | No |
| preference_match | 0.1165 | 0.3654 | 0.0416 | 0.2112 | 0.1454 | 1.00 | 0.465 | +0.0121 | [−0.0068, +0.0305] | No |
| **cluster_popularity** | **0.1138** | 0.3590 | 0.0424 | 0.2080 | 0.1412 | 0.75 | 0.573 | +0.0093 | [−0.0092, +0.0271] | No |
| tiered | 0.1117 | 0.3451 | 0.0425 | 0.1998 | 0.1423 | **1.00** | 0.551 | +0.0072 | [−0.0126, +0.0245] | No |
| user_user_profile | 0.1105 | 0.3477 | 0.0411 | 0.2010 | 0.1397 | 1.00 | 0.267 | +0.0061 | [−0.0113, +0.0251] | No |
| **random** *(reference)* | **0.1102** | **0.3464** | 0.0422 | 0.1975 | 0.1440 | 1.00 | 0.049 | — | — | — |
| teacher_affinity | 0.1076 | 0.3527 | 0.0410 | 0.2018 | 0.1350 | 1.00 | 0.626 | +0.0032 | [−0.0150, +0.0209] | No |
| global_popularity | 0.1072 | 0.3312 | 0.0389 | 0.1873 | 0.1440 | **0.32** | 0.807 | +0.0028 | [−0.0155, +0.0205] | No |
| item_item_cf | 0.1047 | 0.3515 | 0.0420 | 0.2069 | 0.1253 | 1.00 | 0.478 | +0.0002 | [−0.0179, +0.0174] | No |
| rating | 0.1034 | 0.3325 | 0.0397 | 0.1885 | 0.1363 | 0.30 | 0.811 | −0.0010 | [−0.0193, +0.0163] | No |
| user_user_history | 0.0947 | 0.3097 | 0.0362 | 0.1738 | 0.1233 | 1.00 | 0.193 | −0.0098 | [−0.0269, +0.0067] | No |

**[EXPERIMENT] Zero of eleven methods is significantly better than random.** Every
95% CI on the paired per-learner NDCG@10 difference contains zero. Random ranks
**7th of 12**. Five methods score below it, including global popularity.

**[INTERPRETATION]** This is the expected outcome given §7.2 and §7.3, not a
surprise or a failure of implementation. Course choice in this dataset is
statistically indistinguishable from popularity-weighted chance, popularity itself
is near-uniform, and demographics are unrelated to choice. A recommender cannot
find structure that is not present.

**[INTERPRETATION]** The result does *not* imply the pipeline is wrong. Every
component is tested, leakage-controlled and transfers unchanged to real data. What
it bounds is the claim that may be made from *this* dataset.

### 16.2 Method selection

The pre-registered rule required a method to beat both random and global popularity
on validation, pass a coverage gate, and — among qualifying methods — be selected
on a **parsimony margin of 0.01 NDCG**: a more complex method must win by more than
that to be preferred.

**[EXPERIMENT]** On validation the hybrid led `cluster_popularity` by 0.1148 vs
0.1098, a margin of **0.0051** — inside the parsimony margin. The rule selected the
simpler method.

**[INTERPRETATION]** A six-signal hybrid that adds 0.005 NDCG carries real
maintenance and explanation cost for a gain the significance test cannot separate
from zero.

### 16.3 Architecture selection

Phase 3B evaluated *methods*; the deployed system is an *assembly* that no single
row represents. Three architectures were measured on the **validation** window (the
test budget having been spent once, as pre-registered).

**Table 16.2 — Assembled architectures, validation window, 511 evaluable learners**
*(source: `artifacts/architecture/architecture_validation.json`)*

| Architecture | NDCG@10 | Hit Rate | Coverage | Gini | Δ vs random |
| --- | --- | --- | --- | --- | --- |
| A — flat `cluster_popularity` | 0.1098 | 0.3033 | 0.78 | 0.606 | +0.0125 n.s. |
| B — tiered, hybrid core | 0.1135 | 0.3327 | **1.00** | 0.608 | +0.0162 n.s. |
| **C — tiered, selected core** ✅ | 0.1104 | 0.3053 | **1.00** | **0.581** | +0.0131 n.s. |

**[EXPERIMENT]** C dominates A: +0.0006 NDCG (noise), **+0.22 coverage**, lower
concentration. B exceeds C by 0.0031 but re-introduces the hybrid already rejected
at a larger margin.

**[INTERPRETATION]** The deployed architecture was not the most accurate one. It
was selected because it reaches the whole catalogue at indistinguishable accuracy
and degrades honestly for learners it cannot personalise.

### 16.4 Segmentation's contribution to recommendation

**[EXPERIMENT]** `cluster_popularity` beats `global_popularity` by +0.0066 NDCG@10,
but beats random by only +0.0093 with a CI containing zero.

**[INTERPRETATION]** Segment-aware popularity is better than global popularity —
the segmentation *is* carrying information relative to the naive alternative — but
the segmentation has **no demonstrated recommendation value** against chance. Both
halves of that sentence are necessary.

### 16.5 Performance by tier

**Table 16.3 — Test-window metrics by history tier** *(figure: `artifacts/recommendation/04_tier_behaviour.png`)*

| Tier | n | NDCG@10 | Hit Rate@10 | Coverage | Δ vs random | 95% CI |
| --- | --- | --- | --- | --- | --- | --- |
| minimal (1 course) | 213 | 0.1046 | 0.2441 | 0.55 | +0.0307 | [−0.0076, +0.0687] |
| moderate (2–8) | 193 | 0.0986 | 0.3264 | 0.73 | **−0.0112** | [−0.0463, +0.0229] |
| rich (≥ 9) | 385 | 0.1265 | 0.4390 | 0.33 | +0.0079 | [−0.0165, +0.0342] |

**[EXPERIMENT]** No tier shows a significant improvement over random, and in the
moderate tier the selected method is *worse* than random on average.

**[INTERPRETATION]** The apparent rise in Hit Rate with history (0.244 → 0.439) is
largely mechanical rather than a personalisation effect: learners with more history
also have more held-out targets (1.11 → 2.56 on average), and more targets make a
hit easier. §17 quantifies this.

### 16.6 Pre-registered expectations versus outcomes

Seven predictions were recorded before any data was examined.

| # | Prediction | Outcome |
| --- | --- | --- |
| P-1 | Popularity will be hard to beat | **Refuted** — global popularity is *worse* than random |
| P-2 | Item-based CF will be the strongest personalised method | **Refuted** — 10th of 12 |
| P-3 | Hybrid wins by a small margin, possibly losing parsimony | **Confirmed, including the caveat** |
| P-4 | Cluster structure weak; gap statistic may indicate k = 1 | **Half-confirmed** — structure is weak; the gap statistic returned no verdict |
| P-5 | Variant B (behaviour only) preferred | **Confirmed** — ARI 1.000 |
| P-6 | Teacher signals add nothing | **Half-refuted** — reuse is the one real signal, but adds nothing to prediction |
| P-7 | Coverage separates methods more sharply than accuracy | **Confirmed** — NDCG spans 0.095–0.121; coverage spans 0.30–1.00 |

**[INTERPRETATION]** Two predictions were refuted outright and two partially. This
table exists because a project that records only its confirmed predictions has not
tested anything.

---

## 17. Error Analysis

Conducted on `cluster_popularity` over the 791 test learners
*(source: `EXP-error_analysis`; figure: `artifacts/recommendation/07_error_analysis.png`)*.

### 17.1 Hit rate rises with the number of targets, not with history

**Table 17.1 — Hit Rate@10 by number of held-out targets**

| Held-out targets | Learners | Hit Rate@10 |
| --- | --- | --- |
| 1 | 405 | 0.207 |
| 2 | 155 | 0.381 |
| 3 | 103 | 0.573 |
| 4 | 65 | 0.569 |
| 5 | 44 | 0.659 |
| 6 | 13 | 0.846 |

**[INTERPRETATION]** More chances to be right produce more hits. Any claim that the
system "works better for engaged learners" must control for this; the per-tier
figures in §16.5 do not, which is why they are reported alongside the significance
tests rather than alone.

### 17.2 Where the method succeeds and fails

**Table 17.2 — Conditional hit rates**

| Condition | Hit Rate@10 | n |
| --- | --- | --- |
| Held-out course shares a **category** with history | 0.443 | 429 |
| It does not | 0.260 | — |
| Held-out course shares a **level** with history | 0.456 | 621 |
| **It does not** | **0.006** | — |

**[EXPERIMENT]** When the held-out course is at a level the learner has not taken
before, the hit rate collapses to **0.6%**.

**[INTERPRETATION]** The system is effectively blind to level-switching. Given that
§7.6 found no level progression, this is a coherent failure rather than a random
one — but it means the recommender cannot support a learner moving from Beginner to
Intermediate, which is arguably the most valuable moment in a learning journey.

### 17.3 Popularity bias

**[EXPERIMENT]** Recommended courses sit at mean popularity rank **16.8** (of 60)
while learners' actual next courses sit at **28.6** — close to the catalogue
midpoint of 30. Hits have a mean target rank of 23.3; misses, 31.5.

**[INTERPRETATION]** The method recommends more popular courses than learners
actually choose, and misses disproportionately on unpopular ones — classic
popularity bias [R29], visible even though popularity here is nearly flat. This is
part of why the tiered architecture, which reaches full coverage, was preferred.

### 17.4 Candidate pools

**[OBSERVED]** Mean candidate pool 53.5 courses, minimum 45, and **no learner has a
pool smaller than K**. Every learner can receive a full list.

---

## 18. Explainability

### 18.1 Design

**[ENGINEERING]** The decision that makes faithful explanation possible was taken in
the research phase, before any recommender existed: **the scoring interface returns
per-component contributions, not a scalar.** Following [R31]'s distinction, only
model-intrinsic explanation can be faithful; post-hoc narration can assert reasons
the model never used. Retrofitting faithfulness is impossible, so the interface
carried the decomposition from the start.

Three rules are enforced in code:

1. **A component with zero contribution is absent from the decomposition** and
   therefore cannot be named.
2. **The tier frames the claim.** A learner with no history is told the list is
   broad and popular — not that it is personalised.
3. **No accuracy claim.** Every result carries a caveat stating what §16 measured.

### 18.2 Verification

**[EXPERIMENT]** All **30,000 explanations** (3,000 learners × 10 recommendations)
were checked exhaustively:

| Property | Violations |
| --- | --- |
| Names only components the model used | **0** |
| Quoted number equals the scorer's own contribution | **0** |
| Category claims true of the learner's actual history | **0** |
| Cold-start lists never imply personalisation | **0** |
| Measured-quality caveat present | **0 missing** |

The second row is the strongest check available: for segment-popularity
recommendations, the integer in "*127 learners in your segment enrolled in this
course*" is parsed back out of the rendered sentence and compared against the
contribution the ranking used. The same number appears in all 30,000 cases, because
the sentence is generated *from* the score decomposition rather than written beside
it.

### 18.3 Example

For a minimal-tier learner:

> **You have one course in your history, so this is a similarity match to it rather
> than a behavioural profile.**
>
> 1. Cybersecurity Fundamentals — *Matches your learning profile: same category as
>    1 of your 1 course (Cybersecurity) and at the Intermediate level you usually
>    choose.*

---

## 19. Privacy Considerations

**[ENGINEERING]** `UserName`, `Email` and `TeacherName` are dropped **at ingestion**,
not filtered downstream. The distinction is structural: PII is never present in any
frame that could reach a feature matrix, a persisted artifact, a cached dataframe
or a figure, so a leak would require deliberately circumventing the loader.

**[EXPERIMENT]** Verified adversarially rather than by inspection. The audit loads
the workbook *with* PII retained, extracts 119 real names and email addresses, and
searches every persisted artifact, source module and application page byte-wise:
**0 occurrences across 97 files**. Searching for the column *name* would have passed
even if the values had leaked under a different header.

**[ENGINEERING]** Email is never a modelling feature — it cannot be, because it does
not exist downstream. Learners are addressed by pseudonymous `UserID`. Age and
gender are displayed in the administrator-facing profile (a legitimate operational
view) but enter no model; §11.3 established they would change nothing if they did.

**Fairness auditing.** **[EXPERIMENT]** Demographic strata [R30] show female
learners at NDCG@10 0.1002 (n = 412) against male learners at 0.1285 (n = 379), a
gap of **−0.0283** with CI [−0.0543, −0.0010] — nominally significant.
**[INTERPRETATION]** It is reported and bounded rather than dismissed or amplified:
no demographic feature enters any model; §7.4 found gender independent of course
choice (p = 0.643); the interval barely excludes zero and is **uncorrected for four
strata tests**; and no method beats random at all, so this is a disparity in
chance-level performance. **[FUTURE]** It requires monitoring on real data, and is
not a finding of discrimination.

---

## 20. Production Architecture

### 20.1 Structure

```
src/edupro/
├── data/          loading (PII dropped here) · validation · joins
├── features/      learner.py · course.py
├── segmentation/  representations · clustering · profiling · stability · metrics
├── recommendation/ base (candidates + ranking) · baselines · hybrid
├── evaluation/    splits · metrics · protocol (leakage controls)
├── explainability/ explanations
├── pipeline.py    training: raw workbook in, versioned artifacts out
├── inference.py   serving: RecommendationService
├── persistence.py manifest, version checking, integrity checking
└── reporting.py   reads measured results out of experiment artifacts
```

**[ENGINEERING]** Dependencies run strictly downward. The Streamlit application
contains **no machine learning** — a test greps every file under `app/` for model
calls and fails if any appears.

### 20.2 Artifacts and versioning

Twelve files, **276 KB** total. Two load-time guarantees, both failing loudly:

1. **Library-version match.** scikit-learn does not support loading estimators
   across versions [R36], and the failure mode is silent — a mismatched pickle
   usually loads and then returns different numbers. The manifest records the
   versions that wrote the set and the loader compares them.
2. **Matched artifact set.** Per-segment popularity counts are indexed by the
   labels the clusterer produced, so pairing a new clusterer with a stale
   popularity table is wrong in a way no single-component test would catch — the
   CACE problem [R33]. Every file is hashed at write time and re-hashed on load.

### 20.3 Serving

**[ENGINEERING]** What was *learned* is loaded (the fitted scaler and K-Means); what
is merely *counted* is rebuilt at load time **by the same recommender classes the
experiments used**. A separate serving implementation reading precomputed arrays
would be a second scoring path that could drift from the evaluated one — and an
explanation generated from a drifted scorer is precisely the failure §18 exists to
prevent. The redundantly persisted popularity table is compared against the
recomputed counts by test, so drift fails loudly.

**[EXPERIMENT]** Measured: artifact load **0.41 s** (once per process, cached);
recommendation **8.4 ms** per learner; all 3,000 learners receive a recommendation
with **0 empty lists and 0 already-enrolled courses**.

### 20.4 Validation

**[EXPERIMENT]** 257 automated tests; a 59-probe adversarial audit; a 20-probe
application smoke test; and eight stored experiment results that recompute exactly
in two independent environments. The adversarial audit found three real defects —
a validator that crashed on the corruption it exists to report, an error message
that misdiagnosed its own cause, and an inconsistent label dtype — all fixed and
held by regression tests.

---

## 21. Limitations

Stated plainly, and ordered by how much they bound the conclusions.

1. **No recommendation method beats random on this dataset** (§16.1). The honest
   description of what EduPro would deploy is a segment-aware popularity
   recommender whose ranking quality here is indistinguishable from chance.
2. **The dataset is assessed as almost certainly synthetic** (§6.4). Segments
   describe a generative process, not learner psychology, and no finding here
   should be read as a fact about real learners.
3. **The segmentation is a course-level split** (§11.7). Three of four segments are
   100% pure on one level, and for ~80% of learners that level is the level of a
   single enrollment.
4. **The cluster structure is not algorithm-independent** (§11.6). Average-linkage
   agreement is ARI 0.019.
5. **No instrument can falsify cluster structure here** (§11.1). The gap statistic,
   included specifically for that purpose, returned no verdict.
6. **Missing-not-at-random.** A non-enrollment is not a negative signal; no
   impression data exists. Unavoidable in offline evaluation, and it means recall
   and precision are both understated by an unknown amount.
7. **No causal claim is possible.** Engagement Lift is an **impact proxy**
   (deployed 1.084 against random's 1.046 on the same measure), never a measured
   business outcome.
8. **A gender gap is under monitoring** (§19), uncorrected for multiple comparisons.
9. **The system is blind to level-switching** (§17.2): 0.6% hit rate when the
   held-out course is at an unseen level.
10. **Popularity bias is present** (§17.3) despite near-uniform popularity.
11. **Artifact freshness is not automated.** The manifest detects an *inconsistent*
    artifact set, not a *stale* one.

---

## 22. Practical and Industry Implications

**[INTERPRETATION]** Three implications follow for an organisation considering this
class of system.

**22.1 Measure whether the signal exists before building the recommender.** The
permutation-null test in §7.3 cost a few hours and predicted the entire
recommendation outcome. Deployed without it, this system would have reported Hit
Rate@10 = 36% — a number that sounds like success and means nothing without the
35% a random ranker achieves on the same catalogue. **The cheapest useful thing an
organisation can do before a recommender project is to test its data against
chance.**

**22.2 Coverage is the metric that separates these methods, not accuracy.** NDCG
spans 0.095–0.121 across eleven methods — a range within noise. Coverage spans
0.30 to 1.00. **[INTERPRETATION]** For a catalogue owner, the difference between a
system that surfaces 18 courses and one that surfaces all 60 is a real business
difference, and it is invisible in an accuracy-only report.

**22.3 Honest degradation is a product feature.** Half this learner base cannot be
personalised. A system that says so — and offers breadth instead — is more useful,
and more defensible to a regulator or an executive, than one that dresses a
popularity ranking as personalisation.

**22.4 What EduPro can act on today.** **[MODEL]** The segmentation is stable and
actionable even though it did not improve recommendation: 19.7% of learners are
high-volume, category-repeating learners with a 227-day activity span against ~30
days for everyone else. **[INTERPRETATION]** That group is identifiable, durable
and behaviourally distinct — a reasonable target for retention or
advanced-catalogue work — whereas the other three segments are largely defined by
the level of a single course and support weaker inferences.

---

## 23. Future Work

**[FUTURE]** In descending order of expected value.

1. **Re-run this study on real interaction data.** Every method, control and test
   transfers unchanged. The methodology is not invalidated by the negative result;
   the findings are specific to this dataset.
2. **Capture the signals the dataset lacks**: completion, progress, dwell time,
   ratings *given* rather than ratings *of* courses, and impression logs. Without
   impressions, missing-not-at-random cannot be addressed at all.
3. **Online evaluation.** No offline proxy can establish engagement impact. An
   interleaving or A/B design would replace the impact proxy with a measurement.
4. **Revisit matrix factorisation when repeat interactions exist.** The mechanical
   objection in §12.1 disappears the moment the platform records repeat or graded
   engagement.
5. **Address level-switching explicitly** (§17.2) — possibly a curriculum-aware
   component rather than a similarity-based one.
6. **Monitor the demographic gap** (§19) on real data with multiple-comparison
   correction.
7. **Automate artifact staleness detection** (§21.11).

---

## 24. Conclusion

This study built a learner segmentation and course recommendation system for
EduPro and evaluated it under leakage control against a mandatory random reference.

**[EXPERIMENT]** The segmentation is real and stable: four segments, every one
reappearing under bootstrap resampling at Jaccard ≥ 0.967, the smallest holding
19.7% of learners, selected by a pre-registered rule that rejected the
highest-silhouette configuration because half its clusters were not reproducible.
Demographics were excluded because they produce an identical partition (ARI 1.000);
teacher features were excluded because they change silhouette by 0.0009 while
re-measuring enrollment volume.

**[EXPERIMENT]** The recommendation result is negative and is reported as the
headline: across eleven methods on 791 evaluable learners, none is significantly
better than random ranking, and five score below it. The deployed architecture — a
four-tier switching recommender — was selected for reaching the full catalogue at
indistinguishable accuracy and for degrading honestly when it cannot personalise.

**[INTERPRETATION]** The contribution of this work is not a recommender that works.
It is a demonstration that the question "does this work?" can be answered honestly
on a small catalogue, and a system built so that the answer is visible rather than
obscured: a random baseline in every table, coverage as a co-primary metric, a
precision ceiling reported alongside precision, explanations generated from the
scorer's own decomposition and verified 30,000 times, and an adversarial audit that
found three real defects in the author's own code.

**[INTERPRETATION]** On a dataset with genuine signal, the same pipeline would
produce a working recommender, and the evaluation design would be what allowed
anyone to believe it.

---

## 25. References

All entries were verified by retrieval during the research phase (19 September
2026): title, authors, venue, year and identifier confirmed against a publisher
page, DBLP or the canonical proceedings listing. The full annotated review is in
`research/literature_review.md`.

### Clustering and segmentation

**[R01]** Rousseeuw, P. J. (1987). Silhouettes: a graphical aid to the interpretation and validation of cluster analysis. *Journal of Computational and Applied Mathematics*, 20, 53–65. DOI: 10.1016/0377-0427(87)90125-7

**[R02]** Tibshirani, R., Walther, G., & Hastie, T. (2001). Estimating the number of clusters in a data set via the gap statistic. *Journal of the Royal Statistical Society: Series B*, 63(2), 411–423. DOI: 10.1111/1467-9868.00293

**[R03]** Hennig, C. (2007). Cluster-wise assessment of cluster stability. *Computational Statistics & Data Analysis*, 52(1), 258–271. DOI: 10.1016/j.csda.2006.11.025

**[R04]** Ben-Hur, A., Elisseeff, A., & Guyon, I. (2002). A stability based method for discovering structure in clustered data. *Pacific Symposium on Biocomputing*, 6–17.

**[R05]** von Luxburg, U. (2010). Clustering Stability: An Overview. *Foundations and Trends in Machine Learning*, 2(3), 235–274. DOI: 10.1561/2200000008

**[R06]** Milligan, G. W., & Cooper, M. C. (1985). An examination of procedures for determining the number of clusters in a data set. *Psychometrika*, 50(2), 159–179. DOI: 10.1007/BF02294245

**[R07]** Ketchen, D. J., & Shook, C. L. (1996). The application of cluster analysis in strategic management research: an analysis and critique. *Strategic Management Journal*, 17(6), 441–458.

**[R08]** Ward, J. H. (1963). Hierarchical Grouping to Optimize an Objective Function. *Journal of the American Statistical Association*, 58(301), 236–244. DOI: 10.1080/01621459.1963.10500845

**[R09]** Arthur, D., & Vassilvitskii, S. (2007). k-means++: The Advantages of Careful Seeding. *SODA '07*, 1027–1035.

**[R10]** Huang, Z. (1998). Extensions to the k-Means Algorithm for Clustering Large Data Sets with Categorical Values. *Data Mining and Knowledge Discovery*, 2(3), 283–304. DOI: 10.1023/A:1009769707641

**[R11]** Gower, J. C. (1971). A General Coefficient of Similarity and Some of Its Properties. *Biometrics*, 27(4), 857–871. DOI: 10.2307/2528823

**[R12]** Kizilcec, R. F., Piech, C., & Schneider, E. (2013). Deconstructing disengagement: analyzing learner subpopulations in massive open online courses. *LAK '13*, 170–179. DOI: 10.1145/2460296.2460330

### Recommender systems

**[R13]** Hu, Y., Koren, Y., & Volinsky, C. (2008). Collaborative Filtering for Implicit Feedback Datasets. *ICDM '08*, 263–272. DOI: 10.1109/ICDM.2008.22

**[R14]** Rendle, S., Freudenthaler, C., Gantner, Z., & Schmidt-Thieme, L. (2009). BPR: Bayesian Personalized Ranking from Implicit Feedback. *UAI '09*, 452–461. arXiv: 1205.2618

**[R15]** Sarwar, B., Karypis, G., Konstan, J., & Riedl, J. (2001). Item-based collaborative filtering recommendation algorithms. *WWW '01*, 285–295. DOI: 10.1145/371920.372071

**[R16]** Deshpande, M., & Karypis, G. (2004). Item-based top-N recommendation algorithms. *ACM TOIS*, 22(1), 143–177. DOI: 10.1145/963770.963776

**[R17]** Burke, R. (2002). Hybrid Recommender Systems: Survey and Experiments. *User Modeling and User-Adapted Interaction*, 12(4), 331–370. DOI: 10.1023/A:1021240730564

**[R18]** Lops, P., de Gemmis, M., & Semeraro, G. (2011). Content-based Recommender Systems: State of the Art and Trends. In *Recommender Systems Handbook*, 73–105. DOI: 10.1007/978-0-387-85820-3_3

**[R19]** Schein, A. I., Popescul, A., Ungar, L. H., & Pennock, D. M. (2002). Methods and metrics for cold-start recommendations. *SIGIR '02*, 253–260. DOI: 10.1145/564376.564421

### Evaluation

**[R20]** Cremonesi, P., Koren, Y., & Turrin, R. (2010). Performance of recommender algorithms on top-N recommendation tasks. *RecSys '10*, 39–46. DOI: 10.1145/1864708.1864721

**[R21]** Herlocker, J. L., Konstan, J. A., Terveen, L. G., & Riedl, J. T. (2004). Evaluating collaborative filtering recommender systems. *ACM TOIS*, 22(1), 5–53. DOI: 10.1145/963770.963772

**[R22]** Shani, G., & Gunawardana, A. (2011). Evaluating Recommendation Systems. In *Recommender Systems Handbook*, 257–297. DOI: 10.1007/978-0-387-85820-3_8

**[R23]** Järvelin, K., & Kekäläinen, J. (2002). Cumulated gain-based evaluation of IR techniques. *ACM TOIS*, 20(4), 422–446. DOI: 10.1145/582415.582418

**[R24]** Meng, Z., McCreadie, R., Macdonald, C., & Ounis, I. (2020). Exploring Data Splitting Strategies for the Evaluation of Recommendation Models. *RecSys '20*, 681–686. DOI: 10.1145/3383313.3418479

**[R25]** Ji, Y., Sun, A., Zhang, J., & Li, C. (2023). A Critical Study on Data Leakage in Recommender System Offline Evaluation. *ACM TOIS*, 41(3), Article 75. DOI: 10.1145/3569930

**[R26]** Ferrari Dacrema, M., Cremonesi, P., & Jannach, D. (2019). Are We Really Making Much Progress? A Worrying Analysis of Recent Neural Recommendation Approaches. *RecSys '19*, 101–109. DOI: 10.1145/3298689.3347058

**[R27]** Ge, M., Delgado-Battenfeld, C., & Jannach, D. (2010). Beyond accuracy: evaluating recommender systems by coverage and serendipity. *RecSys '10*, 257–260. DOI: 10.1145/1864708.1864761

**[R28]** Cañamares, R., & Castells, P. (2018). Should I Follow the Crowd? A Probabilistic Analysis of the Effectiveness of Popularity in Recommender Systems. *SIGIR '18*, 415–424. DOI: 10.1145/3209978.3210014

**[R29]** Abdollahpouri, H., Mansoury, M., Burke, R., & Mobasher, B. (2019). The Unfairness of Popularity Bias in Recommendation. *RecSys 2019 Workshop on Recommendation in Multistakeholder Environments*. arXiv: 1907.13286

**[R30]** Ekstrand, M. D., Tian, M., Madrazo Azpiazu, I., Ekstrand, J. D., Anuyah, O., McNeill, D., & Pera, M. S. (2018). All The Cool Kids, How Do They Fit In? Popularity and Demographic Biases in Recommender Evaluation and Effectiveness. *PMLR* 81 (FAT* 2018), 172–186.

### Explainability and fairness

**[R31]** Zhang, Y., & Chen, X. (2020). Explainable Recommendation: A Survey and New Perspectives. *Foundations and Trends in Information Retrieval*, 14(1), 1–101. DOI: 10.1561/1500000066

**[R32]** Tintarev, N., & Masthoff, J. (2011). Designing and Evaluating Explanations for Recommender Systems. In *Recommender Systems Handbook*, 479–510. DOI: 10.1007/978-0-387-85820-3_15

**[R38]** Barocas, S., Hardt, M., & Narayanan, A. (2023). *Fairness and Machine Learning: Limitations and Opportunities*. MIT Press.

### Production ML and tooling

**[R33]** Sculley, D., et al. (2015). Hidden Technical Debt in Machine Learning Systems. *NIPS 28*.

**[R34]** Breck, E., Cai, S., Nielsen, E., Salib, M., & Sculley, D. (2017). The ML Test Score: A Rubric for ML Production Readiness and Technical Debt Reduction. *IEEE Big Data*.

**[R35]** Pedregosa, F., et al. (2011). Scikit-learn: Machine Learning in Python. *Journal of Machine Learning Research*, 12, 2825–2830.

**[R36]** scikit-learn developers. *Model persistence* (documentation). Retrieved 19 September 2026.

**[R37]** Streamlit. *Caching* (documentation). Retrieved 19 September 2026.

**[R37b]** Streamlit. *Deploy your app on Community Cloud* (documentation). Retrieved 19 September 2026.

### Education-specific

**[R39]** Urdaneta-Ponte, M. C., Mendez-Zorrilla, A., & Oleagordia-Ruiz, I. (2021). Recommendation Systems for Education: Systematic Review. *Electronics*, 10(14), 1611. DOI: 10.3390/electronics10141611

---

## Appendix A — Artifact index

Every table and figure in this paper resolves to a file in the repository.

| Paper element | Artifact |
| --- | --- |
| Tables 5.1–5.2, 6.1, 7.1–7.4 | `artifacts/phase2_audit.json` |
| Figures §7 | `artifacts/eda/01–10*.png` |
| Tables 11.1–11.7 | `artifacts/segmentation/segmentation_results.json`, `cluster_profiles.csv` |
| Figures §11 | `artifacts/segmentation/01–10*.png` |
| Tables 14.1–14.2, 16.1, 16.3, 17.1–17.2 | `artifacts/recommendation/recommendation_results.json` |
| Figures §14, §16, §17 | `artifacts/recommendation/01–08*.png` |
| Table 16.2 | `artifacts/architecture/architecture_validation.json` |
| §18.2, §19, §20.4 | `artifacts/validation/adversarial_audit.json` |
| §20.3 | `models/manifest.json` |

**Verification.** `python scripts/verify_reproducibility.py` recomputes eight
headline results from scratch and compares them to the stored artifacts. All eight
match exactly, in the development environment and in a clean environment built from
`requirements.txt`.

## Appendix B — Reproduction

```bash
py -3.13 -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
pip install -e . --no-deps

python scripts/train_production_model.py    # 12 artifacts, 276 KB, ~16 s
python -m pytest tests -q                   # 257 passed
python scripts/verify_reproducibility.py    # 8 stored results, recomputed
streamlit run app/streamlit_app.py          # the dashboard
```

Python 3.13.9; seed 42 throughout; full environment in `requirements.lock.txt`.
Detailed procedure and caveats: `research/FINAL_VALIDATION.md`.
