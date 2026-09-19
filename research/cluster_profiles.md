# Cluster Profiles

**Phase:** 3A · **Date:** 19 September 2026
**Configuration:** Variant B (behaviour only) · 12-dim category share vector · StandardScaler · K-Means · **k = 4**
**Population:** 2,650 learners (fit window — all interactions before the 2025-10-18 test cut)
**Source:** `artifacts/segmentation/cluster_profiles.csv` · `artifacts/segmentation/segmentation_results.json`

---

## How these labels were produced

**No label was chosen before looking at the data.** The procedure was mechanical:

1. Compute each cluster's mean for every feature, expressed in population standard
   deviations (`artifacts/segmentation/centroid_deviations.csv`).
2. Keep features deviating by at least **0.40 SD**, ranked by absolute deviation.
3. Map each to a phrase from a **controlled vocabulary** in which every phrase is
   licensed by the feature that produced it — `total_courses` high → "High-volume",
   `diversity_ratio` low → "Category-repeating", and so on.
4. Use only features the clustering **actually used**. An earlier run named a
   cluster "Instructor-loyal" from teacher features that were not in the model;
   that is now prevented by construction.
5. Where a cluster is ≥90% one course level, prefix the level. This closes a
   blind spot: a cluster sitting at the *middle* of a three-level ordinal scale has
   a near-zero deviation on `learning_depth_index` even when every member prefers
   the middle level — which is exactly what happened to cluster 3.
6. A cluster with no feature past 0.40 SD gets a neutral name and the ambiguity is
   reported. None needed one here.

**Excluded by design:** the MOOC learner types from [R12] — "auditing",
"completing", "sampling", "disengaging". They were derived from longitudinal
within-course engagement traces. EduPro has **no completion, progress or
engagement data at all**, only enrollment transactions. Applying them would assert
behaviour this dataset cannot evidence. Their absence is enforced by a test.

---

## Summary

| Cluster | Label | Learners | Share | Courses | Level |
| --- | --- | --- | --- | --- | --- |
| **0** | Beginner-level Single-course learners | 715 | 27.0% | 1.34 | **100% Beginner** |
| **1** | Category-repeating High-volume learners | 522 | 19.7% | **9.65** | mixed (44/39/16) |
| **2** | Advanced-level Non-repeating learners | 881 | 33.2% | 1.51 | **100% Advanced** |
| **3** | Intermediate-level Single-session Single-course learners | 532 | 20.1% | 1.25 | **100% Intermediate** |

> **Read this first.** The partition is essentially **one high-volume group plus
> three low-volume groups separated by course level**. It is stable (every cluster
> ≥0.98 bootstrap Jaccard), balanced (19.7%–33.2%) and reproducible — but it is not
> a set of motivational personas, and the limitations section below states
> plainly what it does and does not support.

---

## Full profile table

| Measure | Cluster 0 | Cluster 1 | Cluster 2 | Cluster 3 | Population |
| --- | --- | --- | --- | --- | --- |
| **Learners** | 715 | 522 | 881 | 532 | 2,650 |
| **Share** | 27.0% | 19.7% | 33.2% | 20.1% | 100% |
| **Bootstrap Jaccard** | 0.983 | 0.996 | 0.996 | 0.981 | — |
| *Demographics* | | | | | |
| Mean age | 25.22 | 24.85 | 24.61 | 25.22 | 24.94 |
| % female | 49.1% | 51.2% | 50.3% | 53.2% | 50.7% |
| *Engagement* | | | | | |
| Total courses | 1.34 | **9.65** | 1.51 | 1.25 | 3.02 |
| Categories explored | 1.34 | **6.84** | 1.50 | 1.25 | 2.46 |
| Avg courses / category | 1.00 | 1.46 | 1.00 | 1.00 | 1.093 |
| Enrollment frequency | 0.745 | **0.044** | 0.637 | 0.859 | 0.594 |
| Activity span (days) | 29.1 | **227.0** | 40.5 | 18.3 | 69.7 |
| Recency (days) | 128.5 | **31.5** | 121.9 | 133.5 | 108.2 |
| *Preference* | | | | | |
| **Preferred level** | **Beginner 100%** | Adv 44% / Beg 39% / Int 16% | **Advanced 100%** | **Intermediate 100%** | — |
| Avg course rating | 3.26 | 3.12 | **2.87** | **3.39** | 3.13 |
| Category entropy | 0.31 | **2.51** | 0.45 | 0.20 | 0.77 |
| Top-category share | 0.855 | **0.301** | 0.791 | **0.911** | 0.736 |
| Top 3 categories | Programming 17%, AI 13%, Data Science 11% | Data Science 10%, Web Dev 9%, AI 9% | **Design 18%**, Business 15%, Web Dev 13% | **Cybersecurity 17%**, Data Science 13%, ML 12% | — |
| *Behavioural* | | | | | |
| Learning depth (0–2) | **0.09** | 0.98 | **1.77** | 1.00 | 1.007 |
| Diversity ratio | 0.999 | **0.703** | 0.999 | 0.999 | 0.941 |
| Avg spend | **102.70** | 93.77 | **77.96** | 83.46 | 88.86 |
| Free-course ratio | 0.674 | 0.627 | 0.609 | **0.713** | 0.65 |
| *Teacher (profiled, not modelled)* | | | | | |
| Distinct teachers | 1.34 | 2.03 | 1.48 | 1.24 | 1.50 |
| Teacher loyalty | 0.003 | **0.730** | 0.009 | 0.004 | 0.149 |

---

## Cluster 0 — Beginner-level Single-course learners

**715 learners · 27.0% · Jaccard 0.983**

**Naming evidence:** `learning_depth_index` **−1.30 SD** · `total_courses` −0.46 SD
· 100% prefer Beginner.

Learners who took one or two **beginner** courses and stopped. Their 1.34 courses
sit almost entirely in one category (top-category share 0.855, entropy 0.31), and
they have not returned in roughly four months (recency 128.5 days).

They carry the **highest average spend** of any segment (102.70) despite the lowest
depth — an artefact worth stating rather than narrating: `Amount` equals
`CoursePrice` exactly (Phase 2, I-1), so this reflects which beginner courses
happen to be priced, not a willingness to pay.

Their categories skew technical-introductory: **Programming 17%**, Artificial
Intelligence 13%, Data Science 11%.

**What EduPro could act on:** this is the largest pool of learners who took a first
step and did not take a second. A follow-on beginner course in the same category is
the obvious intervention — and it is testable.

---

## Cluster 1 — Category-repeating High-volume learners

**522 learners · 19.7% · Jaccard 0.996**

**Naming evidence:** `diversity_ratio` **−1.84 SD** · `total_courses` **+1.83 SD**.

The only genuinely distinct behavioural segment. These learners took **9.65 courses
on average** across **6.84 categories**, over an activity span of **227 days** —
more than seven times the span of any other cluster — and are the only segment
still recently active (recency 31.5 days vs 122–134 elsewhere).

"Category-repeating" is the precise description: their diversity *ratio* is 0.703,
meaning roughly 30% of their enrollments revisit a category they have already
taken. Every other cluster sits at 0.999 — one course per category — because they
have too little history to repeat anything. Their category entropy (2.51, against a population mean of 0.77) and
low top-category share (0.301) confirm genuinely spread interests.

Their enrollment frequency is the **lowest** (0.044/day): they are steady over
months, not bursty.

They are also the only segment with meaningful **teacher loyalty** (0.730 vs
0.003–0.009). This is profiled, not modelled — teacher features were excluded from
the segmentation (§5 of the feature decision) — and it corroborates the Phase 2
finding that instructor reuse is concentrated in the heavy cohort.

**Level mix:** Advanced 44%, Beginner 39%, Intermediate 16% — the only cluster not
defined by a level, because volume separates it first.

**What EduPro could act on:** the platform's most engaged population — **19.7% of
learners accounting for roughly 63% of all fit-window enrollments** (~5,040 of
7,992). Retention here is worth more per learner than acquisition elsewhere.

---

## Cluster 2 — Advanced-level Non-repeating learners

**881 learners · 33.2% · Jaccard 0.996** — the largest segment.

**Naming evidence:** `learning_depth_index` **+1.09 SD** · `diversity_ratio`
+0.45 SD · 100% prefer Advanced.

Learners whose single course (1.51 on average) was **advanced**. They took the
**lowest-rated courses** of any segment (2.87 vs 3.13 population) and spent the
**least** (77.96).

Their category mix is distinctly non-technical relative to cluster 0: **Design
18%**, Business 15%, Web Development 13% — where cluster 0 leads with Programming.
This is the clearest content difference between any two clusters, and it is a
*consequence* of the level split rather than an independent preference axis:
category and level are entangled in a catalogue where each category holds only
five courses.

**A caution that belongs with this segment.** "Advanced-level" describes the course
they chose, not demonstrated expertise. The dataset has no completion, assessment
or progress data, so nothing here supports calling them advanced *learners*.

---

## Cluster 3 — Intermediate-level Single-session Single-course learners

**532 learners · 20.1% · Jaccard 0.981**

**Naming evidence:** `activity_span_days` **−0.52 SD** · `total_courses` −0.48 SD
· 100% prefer Intermediate.

The most concentrated segment: fewest courses (1.25), **shortest activity span
(18.3 days)**, highest top-category share (**0.911**) and lowest category entropy
(0.20). Essentially a single-session population.

They chose the **highest-rated courses** (3.39) and the **highest share of free
courses** (0.713), and their categories lead with **Cybersecurity 17%**, Data
Science 13%, Machine Learning 12%.

**Why the level appears in the label but not in the deviation evidence.** This
cluster is 100% Intermediate, yet its `learning_depth_index` is 1.003 — almost
exactly the population mean of 1.00, because Intermediate *is* the middle of the
scale. Deviation-based naming alone would have missed the single most defining
property of the segment. Level purity was added to the naming rule for exactly this
case.

---

## Segment comparison — what actually separates them

| Axis | Separates | Evidence |
| --- | --- | --- |
| **Course level** | 0 vs 2 vs 3 | 100% pure in each; level block = 31.1% of between-cluster variance |
| **Activity volume** | 1 vs all others | `total_courses` η² = 0.820 |
| **Category breadth** | 1 vs all others | entropy 2.51 vs 0.20–0.45 |
| **Category identity** | weakly, 0 vs 2 | Design spread 0.17, Programming 0.15 across clusters |
| **Demographics** | **nothing** | age range 24.61–25.22; female 49.1–53.2%; block share **0.04%** |
| **Spend** | weakly | 77.96–102.70, and it is a function of catalogue choice, not behaviour |

**Demographics separate nothing.** Age varies by 0.6 years across four segments and
gender by 4 percentage points. This is the modelling-level confirmation of the
Phase 2 finding that age and gender are independent of course choice.

---

## Honest limitations

These belong with the profiles wherever the profiles are presented — in the
dashboard, the research paper and the executive summary.

1. **Three of four segments are defined by the level of a single course.** Mean
   courses in clusters 0, 2 and 3 are 1.34, 1.51 and 1.25. For most of these
   learners "preferred level" is simply the level of their one enrollment.

2. **Phase 2 found level choice statistically indistinguishable from chance**
   (z = −2.65, at the Bonferroni boundary across eight tests; 0.03 levels out of
   2.2). The segmentation's dominant axis is therefore a near-arbitrary attribute
   of a single interaction for the majority of learners.

3. **The structure is not algorithm-independent.** Average-linkage hierarchical
   clustering agrees with K-Means at ARI 0.019 and collapses 91% of learners into
   one cluster. Only variance-minimising algorithms find this partition.

4. **The dataset is assessed as almost certainly synthetic** (Phase 2, D-025).
   These segments describe a generative process. They should not be presented as
   discoveries about real learner motivation.

5. **No completion, progress or outcome data exists.** Nothing here supports any
   claim about whether learners finished, succeeded, or benefited.

6. **Practical value is not yet established.** Whether these segments improve
   recommendation is answered in Phase 3B by EXP-023 (cluster popularity vs global
   popularity). ADR-0005 made the cluster signal ablatable so that question can be
   answered rather than assumed.

---

## Stakeholder-facing one-liners

Wording checked against the evidence above. Every claim is traceable to a number
in the profile table; none extends past what the data supports.

| Segment | One-liner |
| --- | --- |
| **0 — Beginner-level Single-course** | *27% of learners took one beginner course, mostly in Programming or AI, and have not returned in about four months.* |
| **1 — Category-repeating High-volume** | *20% of learners are the platform's committed core: ~10 courses across ~7 categories over 7½ months, still recently active, and the only group that returns to the same instructors.* |
| **2 — Advanced-level Non-repeating** | *33% of learners took a single advanced course — most often in Design or Business — with the lowest average course rating of any group.* |
| **3 — Intermediate-level Single-session** | *20% of learners took one intermediate course, usually free and highly rated, within a single short session concentrated in Cybersecurity or Data Science.* |

Each must be accompanied by the caveat that segments 0, 2 and 3 are defined by a
single enrollment, and that this dataset is assessed as synthetic.
