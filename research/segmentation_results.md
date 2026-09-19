# Segmentation Results

**Phase:** 3A — learner segmentation experiments
**Date:** 19 September 2026
**Reproduce:** `python scripts/run_segmentation_experiments.py` → `artifacts/segmentation/segmentation_results.json`
**Figures:** `python scripts/generate_segmentation_figures.py` → `artifacts/segmentation/*.png`
**Reference keys `[Rxx]`** resolve in `research/literature_review.md` §10.

---

## 0. Summary

| Question | Answer | Evidence |
| --- | --- | --- |
| Representation | **Variant B** (behaviour only), category as a 12-dim share vector, StandardScaler | EXP-011a |
| k | **4** | EXP-010 + the pre-registered constraints |
| Do demographics help? | **No — ARI between Variant A and B is exactly 1.000** | EXP-011 |
| Do teacher features help? | **No — +0.0009 silhouette, ARI 0.990** | EXP-014 |
| Is the partition stable? | **Yes — every cluster ≥0.98 bootstrap Jaccard** | EXP-013 |
| Is it algorithm-independent? | **No — average linkage agrees at ARI 0.019** | EXP-012 |
| What is the structure? | **A course-level split plus a high-volume group** | EXP-011g |

**Headline.** A stable, interpretable four-segment partition exists and is
defensible. But it is not a set of rich learner personas: three of its four
clusters are **100% one course level**, and for the 54% of learners with a single
enrollment "preferred level" is simply the level of that one course. The honest
description is *three single-course groups partitioned by course level, plus one
high-volume group* — and that is reported as the finding rather than dressed up.

---

## 1. Experimental setup

**Window.** All experiments run on the **fit window**: every interaction before the
pre-registered test cut of 2025-10-18. The clustering therefore never sees a
test-window interaction, so assignments can feed the Phase 3B recommendation
evaluation without leaking (control L4).

| | Value |
| --- | --- |
| Learners in the fit window | **2,650** (of 3,000; 350 have no pre-cut interaction) |
| Interactions | 7,992 |
| Seed | 42 |
| k range | 2–10 |
| Representations compared | 10 |

**Full-history sensitivity.** Repeating the selection on all 3,000 learners and
10,000 interactions gives ARI **0.847** against the fit-window labels. The
conclusions do not depend on the window choice.

---

## 2. Experiment 1 — Feature representations (EXP-011a)

Ten arms, each a complete recipe. Every arm was swept over the full k range so the
comparison does not depend on a k chosen for one of them.

| Representation | d | Encoding | Best k | Silhouette | Min cluster | Demographic share |
| --- | --- | --- | --- | --- | --- | --- |
| `B_robust_scaled` | 25 | proportion, RobustScaler | 2 | **0.716** ⚠ | 17.1% | 0.000 |
| `B_no_category` | 13 | none | 10 | 0.435 | 4.4% | 0.000 |
| `B_facets` | 15 | facets | 2 | 0.393 | 20.0% | 0.000 |
| `B_no_level` | 22 | proportion, no level | 9 | 0.303 | — | 0.000 |
| `B_proportion_weighted` | 25 | proportion, block-weighted | 4 | 0.292 | 19.7% | 0.000 |
| `B_decorrelated` | 23 | proportion, volume-redundant dropped | 10 | 0.267 | 4.4% | 0.000 |
| `B_teacher` | 28 | proportion + teacher | 2 | 0.221 | — | 0.000 |
| `A_proportion` | 27 | proportion + demographics | 9 | 0.219 | 4.7% | **0.0004** |
| `B_one_hot` | 25 | one-hot | 2 | 0.212 | 20.0% | 0.000 |
| **`B_proportion`** (reference) | 25 | proportion | 6 | 0.209 | 6.2% | 0.000 |

Documented in `research/segmentation_feature_decision.md`; the two findings that
change what can be concluded:

### 2.1 `B_robust_scaled` is a scaling pathology, not a better representation

Its silhouette of 0.716 is more than three times the reference. That is an
artefact. Two mandated features have an **interquartile range of exactly zero**:

| Feature | q25 | q50 | q75 | IQR |
| --- | --- | --- | --- | --- |
| `avg_courses_per_category` | 1.000 | 1.000 | 1.000 | **0.000** |
| `diversity_ratio` | 1.000 | 1.000 | 1.000 | **0.000** |

Because 54% of learners have a single course, both features equal 1.0 for the
majority and all three quartiles coincide. RobustScaler leaves those columns
unscaled while compressing the others, manufacturing a separable axis. The k=2
split it produces (2,198 / 452) is close to the Phase 2 light/heavy cohort
boundary — it is re-finding the activity bimodality through a scaling bug.

**This settles the scaler decision deferred in Phase 1 (D5): StandardScaler.**

### 2.2 The one-hot dominance risk did not materialise — at the selected k

Phase 1 identified one-hot encoding of `preferred_category` as the project's
largest methodological risk (`segmentation_research.md` §3): 12 indicator columns
against ~8 behavioural ones would spend over half the distance budget on one
variable, and K-Means would largely rediscover the course taxonomy.

Measured at the **common selected k = 4**, so the comparison is like-for-like:

| Representation | Category block share | Level block share | Top feature |
| --- | --- | --- | --- |
| `B_proportion` (E-B) | **5.0%** | 31.1% | `preflevel_Intermediate` |
| `B_one_hot` (E-A) | **3.7%** | 31.5% | `learning_depth_index` |
| `B_facets` (E-C) | 13.3% | 28.4% | `learning_depth_index` |
| `B_no_level` | 18.1% | — | `cat_share_digital_marketing` |

**Neither encoding lets category dominate.** One-hot is in fact marginally *lower*
than the proportion vector. **The Phase 1 inference was wrong at k=4**, and is
recorded as wrong rather than quietly dropped.

The mechanism Phase 1 described is nonetheless real — it simply does not bite at
this k. Read at each arm's own best k, the category block does take over once the
partition is allowed to fragment:

| Representation | Own best k | Category block share |
| --- | --- | --- |
| `A_proportion` | 9 | **46.3%** |
| `B_decorrelated` | 10 | **58.3%** |
| `B_no_level` | 9 | 57.2% |
| `B_proportion` | 6 | 17.4% |

So the honest statement is: **at k=4 the partition is driven by level and volume,
which swamp the category columns under either encoding; at k≥9 category dominance
becomes exactly the problem Phase 1 predicted.** The stability constraint that
selected k=4 therefore also, incidentally, avoided the dominance risk.

The proportion encoding is still preferred — on the interpretability and coherence
grounds set out in `research/segmentation_feature_decision.md`, not because it
averted a dominance problem it turned out not to need to avert.

---

## 3. Experiment 2 — K-Means and the choice of k (EXP-010)

| k | Inertia | Silhouette | CH | DB | Min cluster | Intra-cluster sim. | Seed ARI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 55,391 | 0.1771 | 519.1 | 1.554 | 20.0% | 0.272 | 1.000 |
| 3 | 49,369 | 0.1733 | 452.5 | 2.214 | 19.9% | 0.374 | 1.000 |
| **4** | **45,448** | **0.1946** | **403.7** | **2.145** | **19.7%** | **0.416** | **1.000** |
| 5 | 43,231 | 0.2019 | 352.1 | 1.998 | 5.4% | 0.423 | 0.863 |
| 6 | 40,925 | 0.2089 | 327.2 | 1.947 | 6.2% | 0.497 | 0.798 |
| 7 | 39,662 | 0.2305 | 295.3 | 1.869 | 4.6% | 0.404 | 0.677 |
| 8 | 37,077 | 0.2349 | 297.0 | 1.717 | 4.9% | 0.500 | 0.639 |
| 9 | 35,416 | 0.2613 | 287.4 | 1.786 | 4.7% | 0.435 | 0.617 |
| 10 | 33,312 | 0.2685 | 290.0 | 1.636 | 4.4% | 0.463 | 0.557 |

### 3.1 The elbow is uninformative

Inertia falls smoothly with no knee (`01_elbow_and_silhouette.png`). It is produced
because the brief mandates it, and it decides nothing — exactly as Phase 1
anticipated from [R07].

### 3.2 Silhouette alone would have chosen k=10

Unconstrained, silhouette rises monotonically to 0.2685 at k=10. Selecting on
silhouette alone would have produced ten segments, five of which fail to reappear
under resampling.

### 3.3 The constraints are what decide

The pre-registered rule (`segmentation_research.md` §6.2) requires **both**: every
cluster holds ≥5% of learners, **and** every cluster reaches bootstrap Jaccard
≥0.60.

| k | Silhouette | Min cluster | Clusters below J=0.60 | Passes? |
| --- | --- | --- | --- | --- |
| 2 | 0.1771 | 20.0% | 0 | ✅ |
| 3 | 0.1733 | 19.9% | 0 | ✅ |
| **4** | **0.1946** | **19.7%** | **0** | **✅ selected** |
| 5 | 0.2019 | 5.4% | 1 | ❌ |
| 6 | 0.2089 | 6.2% | 2 | ❌ |
| 7 | 0.2305 | 4.6% | 5 | ❌ |
| 8 | 0.2349 | 4.9% | 6 | ❌ |
| 9 | 0.2613 | 4.7% | 6 | ❌ |
| 10 | 0.2685 | 4.4% | 5 | ❌ |

**k = 4** is the highest-silhouette value satisfying both. The fragmentation above
k=4 is severe: at k=7, five of seven clusters fail to reappear reliably.

> **A correction worth recording.** The first run of these experiments selected
> k=6, because the implementation applied only the size constraint and measured
> stability afterwards. Two of those six clusters had Jaccard 0.33 and 0.54 — they
> would have failed the rule. The rule was then applied as written, over every
> candidate k, and the answer changed to k=4. A constraint evaluated after the
> choice is not a constraint.

### 3.4 The gap statistic failed

Added in Phase 1 (D-017) precisely because it is the only criterion that can
return "no structure". Over k = 1…20 the gap rises **monotonically** to the range
ceiling and never turns over (`08_gap_statistic.png`).

Its uniform bounding-box reference is a poor null for features that are discrete,
bounded and bimodal — which describes most of this feature set. **The statistic is
uninformative here**, and is reported as a failed instrument rather than read as
endorsing k=20. The consequence is that this project has **no criterion capable of
falsifying the existence of cluster structure**, which is a genuine limitation.

GMM/BIC also selects the range maximum (k=10), consistent with "more components
always fit better" on this data rather than with an identified optimum.

---

## 4. Experiment 3 — Hierarchical validation (EXP-012)

| Comparison | ARI |
| --- | --- |
| K-Means vs **Ward** | **0.350** |
| K-Means vs **average linkage** | **0.019** |
| Ward vs average linkage | 0.026 |

| Method | Cluster sizes |
| --- | --- |
| K-Means | 715 · 522 · 881 · 532 |
| Ward | 747 · 374 · 1,005 · 524 |
| Average linkage | **21 · 110 · 113 · 2,406** |

### This is a negative result and is reported as one

Ward and K-Means both minimise within-cluster variance, so their ARI of 0.350 is
already the *weak* form of confirmation Phase 1 warned about
(`segmentation_research.md` §9) — and 0.350 is modest even by that standard.

Average linkage, which optimises something different, **agrees essentially not at
all** and degenerates into one cluster holding 91% of learners — textbook chaining.

**Conclusion: the structure is not algorithm-independent.** It is found by
variance-minimising methods and not by others. That does not make the K-Means
partition wrong — the brief mandates K-Means, and the partition is stable and
interpretable — but it does mean the segmentation should be described as *one
defensible view of the data*, not as discovered natural groupings.

---

## 5. Experiment 4 — Stability (EXP-013)

At k=4, over 100 bootstrap resamples:

| Cluster | Bootstrap Jaccard |
| --- | --- |
| 0 | **0.983** |
| 1 | **0.996** |
| 2 | **0.996** |
| 3 | **0.981** |

Mean 0.989; all four above the 0.75 reliability convention. Subsample consensus
ARI = **0.987** (sd 0.095). Seed stability ARI = **1.000** across five restarts.

Stability degrades sharply with k:

| k | Mean Jaccard | Clusters below 0.60 |
| --- | --- | --- |
| 2 | 0.983 | 0 |
| 3 | 0.990 | 0 |
| **4** | **0.999** | **0** |
| 5 | 0.748 | 1 |
| 6 | 0.703 | 2 |
| 7 | 0.512 | 5 |
| 8 | 0.549 | 6 |
| 9 | 0.534 | 6 |
| 10 | 0.633 | 5 |

The k=4 partition is exceptionally stable. The cliff between k=4 and k=5 is the
clearest signal in the whole selection.

---

## 6. Experiment 5 — Cluster profiling

Full profiles in `research/cluster_profiles.md`. Summary:

| Cluster | n | Share | Courses | Level | Label |
| --- | --- | --- | --- | --- | --- |
| 0 | 715 | 27.0% | 1.34 | **100% Beginner** | Beginner-level Single-course learners |
| 1 | 522 | 19.7% | **9.65** | mixed (44/39/16) | Category-repeating High-volume learners |
| 2 | 881 | 33.2% | 1.51 | **100% Advanced** | Advanced-level Non-repeating learners |
| 3 | 532 | 20.1% | 1.25 | **100% Intermediate** | Intermediate-level Single-session Single-course learners |

Labels were derived **after** examining centroid deviations, from a controlled
vocabulary in which each phrase is licensed by the feature that produced it, and
**only from features the clustering actually used**. [R12]'s MOOC labels
("auditing", "completing", "sampling") are excluded from the vocabulary by design
and guarded by a test — EduPro has no completion data, so applying them would
assert behaviour this dataset cannot evidence.

### 6.1 Feature dominance (EXP-011c)

| Block | Share of between-cluster variance |
| --- | --- |
| engagement | 32.0% |
| behavioural | 31.9% |
| **level** | **31.1%** |
| category | 5.0% |
| demographic | 0.0% |

Top features by η²: `preflevel_Intermediate` 0.851 · `learning_depth_index` 0.851 ·
`diversity_ratio` 0.830 · `total_courses` 0.820 · `preflevel_Advanced` 0.800.

### 6.2 Volume dominance (EXP-011f)

η²(`total_courses`) = **0.820** — the segmentation accounts for 82% of the
variance in how many courses a learner took. Phase 2 predicted exactly this.

But ARI against the Phase 2 light/heavy cohort split is only **0.177**: the
partition is *not* merely the cohort boundary. It subdivides the low-volume
population by course level, which is where the other 3 clusters come from.

---

## 7. Experiment 6 — Demographic sensitivity (EXP-011)

| Arm | d | Silhouette | Intra-cluster sim. | Mean Jaccard | Demographic share |
| --- | --- | --- | --- | --- | --- |
| `B_proportion` (behaviour only) | 25 | **0.1946** | 0.416 | 0.999 | — |
| `A_proportion` (+ demographics) | 27 | 0.1729 | 0.415 | 0.991 | **0.0004** |

**ARI between the two partitions: 1.000.**

The partitions are **identical**. Adding age and gender changes nothing: the
demographic block explains **0.04%** of between-cluster variance, and the top
feature in both arms is `preflevel_Intermediate`. Silhouette falls slightly, which
is simply the cost of two extra dimensions that carry no cluster information.

Against the pre-registered interpretation bands (`segmentation_research.md` §4):

| Demographic share | Reading | This result |
| --- | --- | --- |
| < 20% | secondary | **0.04%** — far below |
| 20–40% | material | |
| > 40% | dominant, reject A | |

Demographics do not dominate — they are **invisible**. The pre-registered tie rule
applies: on equal performance, prefer Variant B as simpler, more privacy-respecting
and more actionable.

**Decision: Variant B (behaviour only).** The cost of the decision is zero, which
is the cleanest possible answer to CLAUDE.md §10.

This corroborates Phase 2 at the modelling level: age and gender were already shown
independent of course choice (all χ² p > 0.2). They are retained for **evaluation
stratification** in Phase 3B [R30] — auditing with a protected attribute is not the
same as modelling with it.

---

## 8. Experiment 7 — Teacher signal (EXP-014)

Isolated comparison: the teacher block added, everything else held fixed.

| Arm | d | Silhouette | Intra-cluster sim. | Mean Jaccard | Teacher block share | Top feature |
| --- | --- | --- | --- | --- | --- | --- |
| `B_proportion` (core) | 25 | 0.1946 | 0.416 | 0.999 | — | `preflevel_Intermediate` |
| `B_teacher` | 28 | 0.1955 | 0.415 | 0.989 | **16.1%** | `teacher_loyalty` |

**ARI core vs teacher: 0.990.**

The teacher block becomes the single most explanatory feature (`teacher_loyalty`)
and takes 16.1% of between-cluster variance — yet the partition barely moves
(ARI 0.990) and silhouette improves by **0.0009**, which is noise. Intra-cluster
similarity falls marginally.

The explanation is in the Phase 2 audit: `teacher_loyalty` correlates **+0.963**
with `total_courses`. It is near-zero for light learners by construction, so it is
largely re-measuring activity volume under a different name. Its high η² reflects
that correlation, not new information.

**Decision: teacher features are NOT retained in the segmentation.** CLAUDE.md §11
requires defensible evidence of improvement; +0.0009 silhouette with an unchanged
partition is not that.

**Scope of this rejection.** It applies to *segmentation only*. Phase 2 found
instructor loyalty to be the one genuine behavioural signal in the dataset (0.688
distinct teachers per interaction against a 0.944 null), and it remains a live
candidate for the Phase 3B **recommender**, where predicting the next course is a
different question from grouping learners.

Teacher `Age` and `Gender` were excluded before experimentation (D-016) and were
never in any arm.

---

## 9. Experiment 8 (added) — The level ablation (EXP-011g)

Added **after** the first run revealed that three of four clusters were 100% one
course level. Recorded as a post-hoc addition, not presented as planned.

| Arm | d | Silhouette | Mean Jaccard | Unstable clusters | Top feature |
| --- | --- | --- | --- | --- | --- |
| `B_proportion` (with level) | 25 | 0.1946 | **0.999** | **0** | `preflevel_Intermediate` |
| `B_no_level` | 22 | 0.1877 | 0.656 | **1** | `cat_share_digital_marketing` |

**ARI with vs without level: 0.253.**

Removing `preferred_level` produces an almost entirely different partition, drops
mean stability from 0.999 to 0.656, and introduces an unstable cluster. Silhouette
barely changes.

**Conclusion: the stable structure in this dataset *is* the course-level split.**
Without it, the clustering falls back on category shares and stops being
reproducible.

This is the most important qualification on the whole Phase 3A result, and it is
why §10 below is written as it is.

---

## 10. What this segmentation is, and what it is not

**It is:**
- statistically stable (every cluster ≥0.98 bootstrap Jaccard, subsample ARI 0.987)
- balanced (19.7%–33.2% per cluster)
- interpretable (three clusters are a pure course level; one is high-volume)
- reproducible (seed-deterministic; ARI 0.847 against the full-history variant)
- free of demographic dominance (0.04%) and of the one-hot dominance Phase 1 feared

**It is not:**
- a set of rich learner personas. It is *course level* plus *activity volume*.
- algorithm-independent. Average linkage agrees at ARI 0.019.
- built on a strong signal. For 54% of learners, "preferred level" is the level of
  their single enrollment — and Phase 2 found level choice statistically
  indistinguishable from chance (z = −2.65, at the Bonferroni boundary, 0.03 levels
  out of 2.2).

> **The honest statement.** The segmentation is a defensible, stable partition of
> this dataset. Its dominant axis encodes an essentially arbitrary attribute of a
> single interaction for the majority of learners. It should be presented to
> stakeholders as *a reproducible way to group this catalogue's learners by the
> depth and volume of what they take*, not as a discovery about learner motivation.

Whether it carries any **practical** value is a separate question, answered in
Phase 3B by EXP-023: does cluster-popularity recommendation beat global
popularity? ADR-0005 made the cluster signal ablatable so that question can be
answered rather than assumed.

---

## 11. Deviations from the pre-registered plan

| # | Deviation | Why | Recorded |
| --- | --- | --- | --- |
| 1 | Gap statistic range extended from 1–10 to 1–20 | The curve had not turned over by k=10; stopping there would have disguised a monotone curve as "optimum at the boundary" | §3.4 |
| 2 | Stability evaluated for **every** candidate k, not only the chosen one | The first implementation applied the size constraint but measured stability afterwards, which is not applying the rule. Correcting it changed k from 6 to 4 | §3.3 |
| 3 | `B_no_level` arm added (EXP-011g) | The first run showed the partition was essentially a level split; the ablation is the direct test | §9 |
| 4 | Segment naming restricted to features the clustering used | The first run produced "Instructor-loyal" labels from teacher features that were not in the model | §6 |
| 5 | Level purity folded into naming | Deviation-based naming is blind to a cluster sitting at the middle of an ordinal scale — the 100%-Intermediate cluster had a near-zero depth deviation | §6 |

All five were applied before the results were finalised, and all five are visible
in the code and in this document rather than folded silently into the outcome.
