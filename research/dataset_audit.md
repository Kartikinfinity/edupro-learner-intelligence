# Dataset Audit

**Phase:** 2 — dataset audit and EDA
**Date:** 19 September 2026
**Source:** `data/raw/EduPro Online Platform.xlsx` · SHA-256 `ed555e46…8cc0` — **unmodified**
**Reproduce:** `python scripts/run_data_audit.py` → `artifacts/phase2_audit.json`
**Figures:** `python scripts/generate_eda_figures.py` → `artifacts/eda/`
**Reference keys `[Rxx]`** resolve in `research/literature_review.md` §10.

---

## 0. Executive summary

The workbook is **technically immaculate and behaviourally almost empty.**

Integrity is perfect: zero nulls across 27 columns, zero orphan foreign keys, zero
duplicate keys, zero duplicate rows, all four sheets joining cleanly. There is no
cleaning to do, because there is nothing wrong.

But the audit's central finding is not about quality — it is about **signal**:

> **Course choice in this dataset is statistically indistinguishable from
> popularity-weighted random selection.** Category concentration, top-category
> share, free-course share and item–item co-occurrence all fall inside a
> permutation null. Course popularity itself is nearly uniform (Gini 0.042,
> chi-square vs uniform p = 0.60). Demographics have no association with choice
> (all p > 0.2).

One real behavioural signal does exist — **learners reuse instructors far more than
chance** — but it predicts the *next course* only weakly, because each teacher
covers roughly a quarter of the catalogue.

This does not stop the project. It changes what an honest project can claim, and
it is reported here rather than discovered later (CLAUDE.md §6).

---

## 1. Sheet profiles (Step 1)

Four sheets. **No missing value anywhere.** No fully duplicated row anywhere.

| Sheet | Rows | Cols | Primary key | Unique? |
| --- | --- | --- | --- | --- |
| `Users` | 3,000 | 5 | `UserID` (`U#####`) | yes |
| `Teachers` | 60 | 7 | `TeacherID` (`TC#####`) | yes |
| `Courses` | 60 | 8 | `CourseID` (`CR#####`) | yes |
| `Transactions` | 10,000 | 7 | `TransactionID` (`TT#####`) | yes |

### Observed value domains

| Field | Domain |
| --- | --- |
| `Users.Age` | 15–35, all 21 integer values present |
| `Users.Gender` | Female 1,520 / Male 1,480 |
| `Teachers.Age` | 27–50 |
| `Teachers.YearsOfExperience` | 1–24 |
| `Teachers.TeacherRating` | 1.05–4.97 |
| `Teachers.Expertise` | the same 12 labels as `CourseCategory`, **unevenly distributed** (Digital Marketing 11 … Programming 1, Marketing 1) |
| `Courses.CourseCategory` | 12 categories, **exactly 5 courses each** |
| `Courses.CourseType` | Free 38 / Paid 22 |
| `Courses.CourseLevel` | Beginner 21 / Advanced 21 / Intermediate 18 |
| `Courses.CoursePrice` | 0.00–490.90, 23 distinct values (38 courses priced 0.00) |
| `Courses.CourseDuration` | 1.20–49.73 hours, 60 distinct |
| `Courses.CourseRating` | 1.13–4.94 |
| `Transactions.TransactionDate` | 2025-01-01 → 2025-12-30, 358 distinct days |
| `Transactions.PaymentMethod` | PayPal 3,389 / Credit Card 3,333 / Bank Transfer 3,278 |

PII (`UserName`, `Email`, `TeacherName`) is **dropped at load time**, not filtered
downstream, so it is never present in any frame that could reach a feature matrix,
a persisted artifact or a figure (ADR-0006). All three columns are fully populated
and unique in the raw file; no other analysis of them was performed.

---

## 2. Data integrity (Step 2) — EXP-001

**Result: 0 errors, 1 warning, 4 informational findings. PASS.**

| Check | Result |
| --- | --- |
| `Transactions.UserID` → `Users` | **0 orphans** |
| `Transactions.CourseID` → `Courses` | **0 orphans** |
| `Transactions.TeacherID` → `Teachers` | **0 orphans** |
| Users never transacting | **0** |
| Courses never enrolled | **0** |
| Teachers never appearing | **0** |
| Primary-key uniqueness (all 4 sheets) | **all unique** |
| Duplicate `(UserID, CourseID)` pairs | **0** |
| Duplicate full rows | **0** |
| Negative or null amounts | **0** |
| Unparseable dates | **0** |
| Values outside the schema domain | **0** |

Every one of the 3,000 users, 60 courses and 60 teachers appears in the transaction
table. This is itself unusual — real platforms have dormant accounts and unsold
catalogue items — and is the first of several indications that the data is generated.

### Issue register

Four properties are worth recording. **None is a defect requiring cleaning**; all
three "info" items are *redundancies* that constrain modelling, and the single
warning is a nuance for content-based similarity.

| # | Severity | Finding | Consequence |
| --- | --- | --- | --- |
| **I-1** | info | **`Amount` equals `CoursePrice` on all 10,000 rows** (EXP-002) | "Average spending" is not an independent behavioural feature — it is a deterministic function of which courses were chosen. §5 |
| **I-2** | info | **`CourseType` is determined by `CoursePrice`**: Free ⟺ price = 0.00 (38 courses), Paid ⟺ price > 0 (22) | The two columns carry one bit of shared information; using both double-counts it |
| **I-3** | info | **Zero repeat `(User, Course)` pairs** | The signal is purely binary/implicit. Confirms the Phase 1 rejection of iALS (D-010): its confidence weighting requires repeated observations |
| **I-4** | warning | **Two course names each appear twice**: "Deep Learning" (CR00028 Machine Learning / CR00049 Artificial Intelligence) and "Natural Language Processing" (CR00029 ML / CR00047 AI) | They are **distinct courses** with different category, level, price and duration — not duplicates. But `CourseName` cannot identify a course, and the dashboard must display category alongside the name |

**Q-2 from Phase 0 is answered:** the repeated names are genuine sibling courses
across adjacent categories, not data errors. No de-duplication is warranted.

### One borderline value, examined

`CR00028 "Deep Learning"` is typed **Paid** at a price of **0.78**. That is the
lowest non-zero price in the catalogue and sits oddly beside 38 courses at exactly
0.00. It is nonetheless **internally consistent** — Paid means price > 0 — so it is
recorded as a curiosity, not corrected. Silently rounding it to zero would alter an
original value, which §8 forbids.

---

## 3. Learner analysis (Step 3)

| Measure | Value |
| --- | --- |
| Learners | 3,000 (all active) |
| Interactions per learner | mean **3.333**, median **1**, max 16, std 4.35 |
| Distinct courses per learner | identical to interactions (no repeats) |
| Distinct categories per learner | mean 2.577, max 11 |
| Total spend | mean 303.77, median 53.86, **46.5% spend exactly zero** |
| Activity span | mean 91.6 days, **median 0** (54% of learners act on one day only) |
| Age | uniform 15–35, mean 24.97 |
| Gender | 50.7% Female |
| Learners touching all three levels | 536 |

**Age is unrelated to activity** (Pearson r = −0.001 with interaction count), and
the gender means are near-identical (3.34 vs 3.33 interactions; 304.3 vs 303.3
spend). No demographic slice behaves differently from any other.

### Activity concentration

Gini of learner activity is **0.546** — activity is genuinely unequal. Gini of
course popularity is **0.042** — items are not. The Lorenz curves
(`artifacts/eda/03_lorenz_concentration.png`) show this asymmetry directly: **people
differ a lot in how much they do, and courses barely differ in how often they are
chosen.**

---

## 4. Course analysis (Step 4)

| Measure | Value |
| --- | --- |
| Catalogue | 60 courses, **exactly 5 per category across 12 categories** |
| Enrollments per course | **140 – 196**, mean 166.7, std 12.5 |
| Gini of popularity | **0.042** |
| Chi-square vs uniform | χ² = 55.5, df = 59, **p = 0.60 — does not reject uniform** |
| Free vs Paid | 38 free (6,403 enrollments) vs 22 paid (3,597); means 168.5 vs 163.5 |
| By level | Beginner 170.1 · Advanced 165.5 · Intermediate 164.0 mean enrollments |
| Rating vs enrollments | r = **+0.294** |
| Price vs enrollments | r = −0.163 |
| Duration vs enrollments | r = −0.103 |

Most popular: *Data Analysis with Python* (196). Least: *AI for Beginners* and
*SEO for E-commerce* (140 each). The spread between the most and least popular
course in the entire catalogue is **1.4×**.

> **Implication for the recommendation work.** A popularity recommender's whole
> value is that some items are much more likely than others. Here they are not.
> This directly challenges Phase 1's pre-registered expectation **P-1** ("global
> popularity will be hard to beat"): popularity will indeed be hard to *beat*, but
> because it is close to random, not because it is strong.

The rating–popularity correlation of +0.294 is the only content attribute with a
material relationship to enrollment, and it explains under 9% of the variance.

---

## 5. Transaction analysis (Step 5)

| Measure | Value |
| --- | --- |
| Transactions | 10,000 across 358 distinct days of 2025 |
| Per day | mean 27.9, range 16–57, χ² vs uniform p = 0.18 |
| Per month | 762 (Oct) – 899 (Jun); **under 10% variation** |
| Weekday effect | 1,378 (Mon) – 1,488 (Thu); no weekend dip |
| Inter-purchase gap | mean 39.3 days, median 23, max 347; 1.6% same-day |
| Matrix density | **5.56%** (10,000 / 3,000 × 60) |
| Repeat behaviour | **none** — zero repeat pairs |

**There is no trend, seasonality, launch effect or weekday pattern.** For a
temporal evaluation this is convenient: no period is unrepresentative, so the
split cut is not confounded with a regime change.

`Amount` mirrors `CoursePrice` exactly (I-1), so the transaction amount
distribution is simply the price distribution weighted by enrollment.

---

## 6. Sparsity (Step 6) — EXP-003

**The finding that shapes the entire recommendation design.**

| Interactions | Learners | % | Cumulative % |
| --- | --- | --- | --- |
| 1 | **1,620** | 54.00 | 54.00 |
| 2 | 612 | 20.40 | 74.40 |
| 3 | 186 | 6.20 | 80.60 |
| 4 | 128 | 4.27 | 84.87 |
| **5–8** | **0** | **0.00** | 84.87 |
| 9 | 1 | 0.03 | 84.90 |
| 10 | 4 | 0.13 | 85.03 |
| 11 | 31 | 1.03 | 86.07 |
| 12 | 72 | 2.40 | 88.47 |
| 13 | 122 | 4.07 | 92.53 |
| 14 | 132 | 4.40 | 96.93 |
| 15 | 74 | 2.47 | 99.40 |
| 16 | 18 | 0.60 | 100.00 |

Three consequences:

1. **54% of learners have exactly one interaction.** They cannot be evaluated as
   personalised-recommendation users at all (§12), and they cannot be personalised
   in production beyond a single content anchor.
2. **Only 1,380 learners (46%) have ≥2 interactions** and are therefore evaluable
   under leave-one-out.
3. **The distribution is bimodal with a hard empty band at 5–8.** Not a single
   learner in 3,000 has 5, 6, 7 or 8 interactions. Mean 3.33 against variance 18.94
   — six times overdispersed relative to Poisson.

### The two cohorts

| | Light (1–4) | Heavy (9–16) |
| --- | --- | --- |
| Learners | 2,546 (84.9%) | 454 (15.1%) |
| Interactions | 3,914 (39.1%) | 6,086 (60.9%) |
| Free-course share | 0.652 | 0.633 |
| Mean course rating | 3.139 | 3.113 |
| Mean level (0–2) | 1.008 | 0.979 |
| Mean age | 24.98 | 24.95 |

**The cohorts differ in volume and in nothing else.** Their content preferences,
demographics and rating profiles are nearly identical
(`artifacts/eda/10_cohort_comparison.png`).

> **Q-8 partially answered.** An empty band this clean cannot arise from sampling.
> Two populations were generated with different count distributions. See §9.

### Effect on the tier design

The Phase 1 four-tier scheme (`recommendation_evaluation_plan.md` §4) survives, but
the boundaries are now data-determined rather than hypothetical:

| Tier | Training-window history | Learners (full data) |
| --- | --- | --- |
| Insufficient | 0 | learners with no training interaction |
| Minimal | 1 | 1,620 (54.0%) on full history |
| Moderate | 2–4 | 926 (30.9%) |
| Rich | ≥9 | 454 (15.1%) |

The "moderate" tier's upper bound is **4, not a tuned value** — because 5–8 is
empty, the boundary is handed to us by the data.

---

## 7. Is there any personalisation signal? (the decisive analysis)

Method: each observed statistic is compared against a **permutation null** in which
every learner's courses are redrawn from the empirical popularity distribution with
that learner's history length held fixed (200 replicates, seed 42). If the observed
value sits inside the null's 95% interval, the data carries no preference signal on
that dimension.

### Course choice — no signal

| Statistic | Observed | Null mean | Null 95% CI | z | Verdict |
| --- | --- | --- | --- | --- | --- |
| Mean distinct categories | 2.5773 | 2.5869 | [2.571, 2.602] | −1.17 | **no signal** |
| Mean top-category share | 0.7210 | 0.7194 | [0.717, 0.722] | +1.12 | **no signal** |
| Mean distinct levels | 1.5560 | 1.5707 | [1.560, 1.582] | −2.65 | marginal |
| Mean free-course share | 0.6501 | 0.6394 | [0.626, 0.654] | +1.51 | **no signal** |

Restricting to the 1,380 multi-interaction learners gives the same answer
(z = −1.05, +1.29, −2.75, +1.10).

The one marginal result — **distinct levels, z ≈ −2.7** — is a *very* weak effect:
2.209 observed against 2.240 expected, a difference of 0.03 levels out of ~2.2.
Across eight tests (four statistics × two populations) a Bonferroni threshold sits
at roughly |z| = 2.7, so this is at the edge of significance and negligible in
magnitude. It is **not** a basis for a level-preference feature.

**Item–item co-occurrence is also flat**: the observed co-occurrence matrix has
standard deviation 5.46 against a null of 5.87 [5.58, 6.12] — *below* the null.
There is no collaborative structure to exploit.

### Demographics — no signal

| Test | χ² | df | p | Verdict |
| --- | --- | --- | --- | --- |
| Gender × CourseCategory | 8.77 | 11 | 0.643 | independent |
| Gender × CourseLevel | 0.20 | 2 | 0.906 | independent |
| AgeBand × CourseCategory | 33.17 | 33 | 0.459 | independent |
| AgeBand × CourseLevel | 8.43 | 6 | 0.208 | independent |

This is direct evidence bearing on **Q-5 / RQ3**: age and gender carry no
information about what learners choose. It does not settle the Variant A vs B
question by itself — demographics could still produce *tighter clusters* while
being useless for recommendation — but it means Variant A cannot improve
recommendation. EXP-011 will confirm rather than assume.

### Teacher choice — signal

| Measure | Value |
| --- | --- |
| Observed distinct teachers per interaction (learners with ≥2) | **0.688** |
| Null (teacher drawn at random from those attached to each course) | **0.944** [0.939, 0.950] |
| Verdict | **strong signal** |

Learners return to the same instructor far more often than the course–teacher
structure alone would produce. The effect is concentrated in the heavy cohort:

| Cohort | Mean interactions | Mean distinct teachers | Ratio |
| --- | --- | --- | --- |
| Light multi (2–4) | 2.48 | 2.35 | 0.952 |
| **Heavy (9–16)** | **13.41** | **2.00** | **0.151** |

A heavy learner takes ~13 courses from **exactly 2 instructors**.

Supporting evidence that the teacher dimension is structured rather than random:
teacher assignment is not independent of course (χ² = 31,867, df = 3,481,
p < 0.0001), and `Teacher.Expertise` matches `Course.Category` on **41.1%** of
transactions against an 8.3% chance expectation.

### But does the teacher signal predict the next *course*?

This is the question that matters for a course recommender, and the answer is
**barely**:

| Measure | Value |
| --- | --- |
| Learners evaluated (≥2 interactions, leave-last-out) | 1,380 |
| Mean "taught by one of my prior teachers" pool | 24.6 courses |
| Mean unseen catalogue | 54.9 courses |
| Held-out course inside that pool | **49.0%** |
| Chance expectation (pool ÷ unseen) | **44.7%** |
| **Lift** | **1.10×** |

Because each teacher covers ~15 courses, knowing two teachers spans nearly half the
catalogue. The signal is real but **low-resolution**. A 1.10× lift is worth testing
in Phase 3, not worth assuming will carry the system.

### No level progression

Within-learner level slope over time: mean **+0.0053**, t = 0.435, **p = 0.664**
across 735 eligible learners. Mean first-course level 0.988, mean last-course level
0.980. **Learners do not progress from beginner to advanced.** A "level progression"
feature would be measuring noise.

---

## 8. Feature candidates (Step 7)

All eleven official features are implemented in
[`src/edupro/features/learner.py`](../src/edupro/features/learner.py), plus
justified additions. Distributions: `artifacts/eda/09_feature_distributions.png`.

**Leakage risk** below refers to computation, not to the feature's meaning: every
feature is computed from whatever interaction frame it is given, so passing the
training window yields leakage-free values (control L1, enforced by
`test_features_never_see_beyond_the_frame_they_are_given`). Features marked
*temporal* additionally depend on the reference date, which defaults to the maximum
date **within the given frame** rather than the real present.

### Official features (brief-mandated)

| Feature | Definition | Rationale | Distribution | Sparsity | Leakage risk | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `age` | `Users.Age` | Mandated demographic | Uniform 15–35, mean 24.97 | none | none (static) | **KEEP — Variant A only.** No association with choice (§7) |
| `gender` | `Users.Gender` | Mandated demographic | 50.7% F | none | none (static) | **KEEP — Variant A only.** Same |
| `total_courses` | count of interactions | Mandated engagement | mean 3.33, median 1, skew +1.88, **bimodal** | none | window-dependent | **KEEP.** The dominant axis of the feature space |
| `avg_courses_per_category` | `total_courses / diversity_score` | Mandated engagement | mean 1.11, 75th pct = 1.00 | none | window-dependent | **KEEP, flag redundancy.** r = +0.77 with `total_courses`; exact reciprocal of `diversity_ratio` (r = −0.98) |
| `enrollment_frequency` | `total_courses / (span + 1)` | Mandated engagement | mean 0.56; **= 1.0 for all single-day learners** | 0% zero but degenerate for 54% | window-dependent | **KEEP with caveat.** Bimodal by construction; the `+1` is documented, not silent |
| `preferred_category` | modal category | Mandated preference | 12 levels; ties common at short history | n/a | window-dependent | **KEEP as `cat_share_*` vector.** Argmax of a 1–3 item history is near-arbitrary; the 12-dim share vector (encoding E-B) is the tested form |
| `preferred_level` | modal level | Mandated preference | 3 levels | n/a | window-dependent | **KEEP with caveat.** Same argmax instability |
| `avg_course_rating` | mean `CourseRating` | Mandated preference | mean 3.13, std 0.95, near-symmetric | none | window-dependent | **KEEP.** One of the few features *not* dominated by volume (max \|r\| < 0.5 with volume features) |
| `avg_spend` | mean `Amount` | Mandated behavioural | mean 89.3, **46.5% exactly zero** | high | window-dependent | **KEEP, degenerate.** I-1: identical to mean course price. r = −0.81 with `free_ratio`. Not independent spending behaviour |
| `diversity_score` | distinct categories | Mandated behavioural | mean 2.58, max 11 | none | window-dependent | **KEEP, flag.** r = **+0.983** with `total_courses` — at a mean history of 3.3 this largely measures activity, not breadth |
| `learning_depth_index` | mean level ordinal (0–2) | Mandated behavioural | mean 1.00, 21.8% zero | moderate | window-dependent | **KEEP.** Genuinely independent of volume (\|r\| < 0.2 with everything) |

### Additional candidates (justified, not padding)

| Feature | Definition | Rationale | Distribution | Sparsity | Leakage risk | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `diversity_ratio` | `diversity_score / total_courses` | **Normalises breadth by opportunity** — the §2.3 mitigation for diversity being bounded by history length | mean 0.931, 75th pct = 1.0 | none | window-dependent | **KEEP.** Directly addresses the confound |
| `category_entropy` | Shannon entropy of category mix | Breadth measure robust to argmax instability | mean 0.81, **55.5% zero** | very high | window-dependent | **KEEP with caveat.** Zero for every single-interaction learner; r = +0.92 with `total_courses` |
| `top_category_share` | share in modal category | Concentration, continuous alternative to `preferred_category` | mean 0.72 | none | window-dependent | **KEEP** |
| `free_ratio` | share of free courses | Price sensitivity, independent of absolute spend | mean 0.650, 21.4% zero | moderate | window-dependent | **KEEP.** More interpretable than `avg_spend` given I-1/I-2 |
| `total_spend` | sum of `Amount` | Lifetime value framing | mean 303.8, 46.5% zero, skew +2.13 | high | window-dependent | **DROP.** r = +0.84 with `total_courses`; adds nothing over `avg_spend` + volume |
| `activity_span_days` | last − first | Tenure | mean 91.6, **median 0** (54.1% zero) | very high | window-dependent | **KEEP with caveat.** Degenerate for the majority |
| `recency_days` | reference − last | Standard RFM recency; needed for a live dashboard | mean/dist window-dependent | none | **temporal** | **KEEP.** Reference date must come from the training window |
| `first_interaction_days` | reference − first | Tenure, reference-anchored | window-dependent | none | **temporal** | **KEEP** |
| `n_teachers` | distinct teachers | The one real behavioural signal (§7) | mean 1.57, **only 4 distinct values** | none | window-dependent | **KEEP — teacher block.** Very low cardinality |
| `teacher_loyalty` | `1 − n_teachers/total_courses` | Direct encoding of the teacher-reuse effect | mean 0.143, **80.9% zero** | very high | window-dependent | **KEEP — teacher block.** r = +0.96 with `total_courses`: it is near-zero for light learners by construction |
| `avg_teacher_rating` | mean `TeacherRating` | Quality prior beyond course rating | mean ≈ course rating | none | window-dependent | **KEEP — teacher block** |
| `cat_share_*` (12) | per-category share vector | **Encoding E-B**; preserves preference shape rather than argmax | row-normalised, sums to 1 | 0 rows all-zero | window-dependent | **KEEP.** The primary encoding candidate for EXP-011a |

### Rejected before implementation

| Candidate | Why rejected |
| --- | --- |
| **Level progression slope** | Measured: mean slope +0.005, **p = 0.664**. No progression exists; the feature would encode noise |
| `PaymentMethod` mix | Uniformly distributed across three methods, no plausible link to learning preference; would add 3 dimensions of noise |
| `CourseType` preference | Redundant with `free_ratio` by I-2 |
| Teacher `Age` / `Gender` | **Excluded before testing** (D-016): third-party demographics with no legitimate role in allocating recommendations [R38] |
| `TeacherName`, `UserName`, `Email` | PII (§17, ADR-0006) |

### The correlation problem

`artifacts/eda/08_feature_correlation.png`. `total_courses` correlates at |r| ≥ 0.8
with **seven** other candidates:

| Pair | r |
| --- | --- |
| `total_courses` ~ `diversity_score` | **+0.983** |
| `avg_courses_per_category` ~ `diversity_ratio` | **−0.984** |
| `total_courses` ~ `teacher_loyalty` | **+0.963** |
| `total_courses` ~ `category_entropy` | +0.924 |
| `activity_span_days` ~ `category_entropy` | +0.910 |
| `total_courses` ~ `total_spend` | +0.842 |
| `total_courses` ~ `activity_span_days` | +0.834 |

> **Phase 1's §2.3 prediction is confirmed:** the feature space is dominated by
> **activity volume**. A K-Means run on the raw mandated features will largely
> recover the light/heavy cohort split. EXP-011e (correlated-feature ablation) and
> EXP-011f (history-length dominance) are therefore the two most important
> segmentation experiments, not optional extras.

The features that are *not* volume proxies — `avg_course_rating`,
`learning_depth_index`, `free_ratio`, and the `cat_share_*` vector — are the only
places where non-volume structure could live.

---

## 9. Is the dataset synthetic? (Q-8)

**Assessment: almost certainly generated.** Stated as an assessment, with the
evidence, not as a proven fact.

| Evidence | Detail |
| --- | --- |
| **Empty band at 5–8 interactions** | Not one learner in 3,000. No sampling process produces this |
| Perfect catalogue balance | **Exactly** 5 courses in each of 12 categories |
| No missing values | Zero nulls across 4 sheets, 27 columns, 13,120 rows |
| No orphans in any direction | Every user, course and teacher appears in transactions |
| Uniform course popularity | χ² p = 0.60 against uniform |
| Uniform demographics | Age χ² p = 0.67 across 21 values; gender p = 0.47 |
| Uniform payment methods | p = 0.40 |
| Uniform daily volume | p = 0.18; no weekday or seasonal effect |
| Sequential IDs | `U00001…`, `CR00001…`, `TT00001…` with no gaps |
| `Amount` ≡ `CoursePrice` | No discounts, promotions, refunds or price changes in a full year |

The contrast is instructive: **`Teachers.Expertise` is *not* uniform** (11 Digital
Marketing vs 1 Programming), and teacher–learner reuse is strongly non-random.
Whoever generated this data modelled the teacher dimension with structure and the
course-choice dimension without it.

### What this means for the project — and what it does not

**It does not invalidate the work.** The methodology, the pipeline, the leakage
controls, the evaluation protocol and the application are all exercised on real
data of a realistic shape, and every one of them would transfer to genuine EduPro
data unchanged.

**It does constrain the claims.** Specifically:

1. Segments discovered here describe **this dataset's generative process**, not
   real learner psychology. Segment descriptions must be phrased accordingly.
2. Recommendation metrics will be low and close to random, and that is a property
   of the data, not a failure of the methods. Reporting them as though they
   demonstrated a working personalisation engine would be fabrication (§6).
3. The gap statistic [R02] and per-cluster stability [R03] added in Phase 1
   (D-017) become essential rather than nice-to-have: they are the tools that can
   report "no real structure" if that is the answer.

This is registered as threat **V8** in `recommendation_evaluation_plan.md` §9 and
must appear in the research paper's limitations section.

---

## 10. Teacher experiment preparation (Step 11)

### What exists

| Attribute | Cardinality | Usable? |
| --- | --- | --- |
| `TeacherID` | 60 | **Yes** — the linkage that carries the reuse signal |
| `Expertise` | 12 (same labels as `CourseCategory`) | **Yes** — matches course category on 41.1% of transactions vs 8.3% chance |
| `YearsOfExperience` | 1–24 | **Yes** — a course-independent quality proxy |
| `TeacherRating` | 1.05–4.97 | **Yes** — a quality prior alongside `CourseRating` |
| `TeacherName` | 60 | **No** — PII (§17) |
| `Age` | 27–50 | **No** — third-party demographic (D-016) |
| `Gender` | 2 | **No** — third-party demographic (D-016) |

### EXP-005 verdict: the experiment is **not** vacuous

Phase 1 hypothesised (Q-9) that `TeacherID` might be a deterministic function of
`CourseID`, which would have made every teacher feature an alias and cancelled
EXP-014. **That hypothesis is refuted:**

- **887 distinct `(course, teacher)` pairs**, not 60
- 7–30 teachers per course (mean 14.8)
- 7–55 courses per teacher (mean 14.8)
- Not a bijection

**EXP-014 proceeds.** Pre-registered expectation **P-6** ("teacher signals will add
nothing; EXP-005 may cancel the experiment") is **half-refuted already** — the
cancellation branch is closed — and the "adds nothing" half is now genuinely
uncertain, since the teacher dimension holds the only detectable behavioural signal
in the dataset.

### How it could influence learner behaviour

Three mechanisms, each testable:

1. **Instructor loyalty as a personalisation signal.** Learners demonstrably return
   to instructors (0.688 vs 0.944 null). Recommending courses taught by a learner's
   prior instructors is a legitimate candidate — measured lift on next-course
   prediction is **1.10×**, small but real.
2. **Teacher rating as a quality prior.** `TeacherRating` is independent of
   `CourseRating` and could sharpen the rating-weighted relevance term the brief
   requires.
3. **Expertise as a second content facet.** Expertise aligns with category well
   above chance (41.1% vs 8.3%) but is not identical to it, so it may carry
   information category alone does not.

### Aggregation is possible

Teacher attributes aggregate cleanly to the learner level: `n_teachers`,
`teacher_loyalty`, `avg_teacher_rating` are all well-defined for every active
learner and are implemented in the `teacher` feature block.

### Redundancy and leakage risks

| Risk | Assessment |
| --- | --- |
| **Redundancy with course attributes** | Real but partial. Expertise↔Category alignment is 41%, not 100%, so the overlap is substantial but incomplete. EXP-014 must ablate against a core model, not report teacher features in isolation |
| **Redundancy with volume** | `teacher_loyalty` correlates **+0.963** with `total_courses` — it is ~0 for light learners by construction. Any apparent segmentation value must be checked against the volume confound |
| **Leakage** | Same window discipline as every other feature. `avg_teacher_rating` uses a static attribute joined to interactions, so it is safe provided the interaction frame is the training window |
| **Fairness** | Teacher `Age`/`Gender` excluded before experimentation (D-016). No teacher-identity feature is exposed in the dashboard |

**Decision: teacher features remain OUT of the core model.** They enter Phase 3 as
EXP-014, an explicit ablation, and are retained only on defensible evidence of
improvement (§11).

---

## 11. Leakage risks identified

| Control | Status |
| --- | --- |
| **L1** — features computed only from the frame given | **Implemented + tested** (`test_features_never_see_beyond_the_frame_they_are_given`) |
| **L2** — already-enrolled exclusion from training-window history | Specified; enforced in Phase 3 |
| **L3** — tier assignment from training-window history only | Specified; enforced in Phase 3. **Critical**: a learner with 1 train + 1 test interaction must be routed as tier-1, not tier-2 |
| **L4** — clustering fitted on training-window features only | Specified; Phase 3 |
| **L5** — popularity from training-window interactions | **Implemented + tested** (`course_popularity` takes the frame explicitly) |
| **L6** — test interactions present in candidate pools | Specified; Phase 3 |

Two additional risks surfaced by this audit:

- **`recency_days` and `first_interaction_days`** depend on a reference date. The
  default is the maximum date *within the passed frame*, never the real present, so
  a training-window build cannot reference a future date. Tested.
- **The split is computed once and persisted** (`data/processed/splits/`). No
  experiment re-derives it, so tie-breaking differences cannot silently make
  results non-comparable.

---

## 12. Open questions — status after Phase 2

| # | Question | Status |
| --- | --- | --- |
| Q-1 | Is `Amount` = `CoursePrice`? | **ANSWERED — yes, on all 10,000 rows.** `avg_spend` is not independent behaviour |
| Q-2 | Duplicate course names? | **ANSWERED — 2 repeated names, distinct courses.** No de-duplication |
| Q-3 | Use `CoursePrice` / `CourseDuration`? | **ANSWERED — partially.** `CoursePrice` enters via `free_ratio`/`avg_spend` (I-2 redundancy noted). `CourseDuration` correlates −0.10 with popularity; **kept as a content-similarity attribute only**, not a learner feature |
| Q-4 | Tier boundaries? | **ANSWERED — handed over by the data.** 1 / 2–4 / ≥9, because 5–8 is empty |
| Q-5 | Variant A or B? | **Evidence gathered, not settled.** Demographics are independent of choice, so A cannot help recommendation. EXP-011 decides on cluster quality |
| Q-6 | Temporal hold-out viable? | **ANSWERED — yes.** 791 evaluable learners ≥ 300 threshold. **Protocol A is primary** |
| Q-7 | Engagement Lift definition | Settled in Phase 1 (D-014); magnitude in Phase 3 |
| Q-8 | Synthetic data? | **ANSWERED — almost certainly yes.** §9. Registered as threat V8 |
| Q-9 | `TeacherID` an alias for `CourseID`? | **ANSWERED — no.** 887 pairs. EXP-014 proceeds |
| Q-10 | Does segmentation improve recommendation? | Open — EXP-023 in Phase 3 |

---

## 13. What Phase 3 should expect

Recorded now so that the Phase 3 results are read against a stated prior rather
than rationalised afterwards. These **update** the Phase 1 pre-registered
expectations in light of evidence:

| # | Phase 1 expectation | Phase 2 evidence | Revised expectation |
| --- | --- | --- | --- |
| P-1 | Popularity hard to beat | Popularity is near-uniform (Gini 0.042) | **Revised**: popularity ≈ random; *nothing* will beat it by much |
| P-2 | Item-based CF strongest | Co-occurrence is *below* the null | **Revised**: item-based CF will also be ≈ random |
| P-4 | Cluster structure weak | Volume dominates; content choice is random | **Strengthened**: clusters will largely encode activity volume |
| P-5 | Variant B preferred | Demographics independent of choice | **Strengthened** |
| P-6 | Teacher signals add nothing | Teacher reuse is the only real signal, but only 1.10× on next-course | **Genuinely uncertain** — the strongest reason to run EXP-014 properly |

> **The most likely honest Phase 3 outcome is that no recommender meaningfully
> beats random on this dataset.** That is a legitimate, publishable result — it is
> what §6 requires and what [R26] indicates is common — and the evaluation design
> (random baseline in every table, coverage as co-primary, pre-registered selection
> rules) was built in Phase 1 precisely so this outcome could be reported clearly
> rather than hidden behind a favourable-looking metric.
