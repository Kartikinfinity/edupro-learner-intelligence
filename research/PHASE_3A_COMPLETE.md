# Phase 3A — Learner Segmentation Experiments — COMPLETE

**Phase:** 3A — controlled learner segmentation experiments
**Date:** 19 September 2026
**Decision:** ✅ **PASS**
**Next phase:** Phase 3B — recommendation experiments (**not started; awaiting go-ahead**)

---

## 1. The decision

> **Representation:** Variant B (behaviour only) · category as a 12-dimensional
> share vector · ordinal level one-hot · StandardScaler · no block weighting ·
> **no demographics** · **no teacher block**
>
> **Algorithm:** K-Means, k-means++ seeding, `n_init=10`, seed 42
>
> **k = 4**

Implemented as `RepresentationSpec(name="B_proportion", …)` in
`src/edupro/segmentation/representations.py` — the exact object the Phase 5
production pipeline will load.

| Property | Value |
| --- | --- |
| Silhouette | 0.1946 |
| Intra-cluster similarity (behavioural cosine) | 0.416 |
| Smallest cluster | 19.7% |
| Per-cluster bootstrap Jaccard | 0.983 · 0.996 · 0.996 · 0.981 |
| Subsample consensus ARI | 0.987 |
| Seed stability ARI (5 restarts) | 1.000 |
| Demographic block share of variance | **0.0004** |
| Full-history sensitivity (ARI) | 0.847 |

---

## 2. Experiments completed

All run on the **fit window** (2,650 learners, 7,992 interactions before the
pre-registered 2025-10-18 test cut), so assignments can feed Phase 3B without
leaking (control L4).

| # | Experiment | ID | Outcome |
| --- | --- | --- | --- |
| 1 | Feature representations | EXP-011a | 10 arms swept over k=2–10 |
| 2 | K-Means and k selection | EXP-010 / 010b / 010c | k=4 by the pre-registered rule |
| 3 | Hierarchical validation | EXP-012 | **Negative** — weak cross-algorithm agreement |
| 4 | Cluster stability | EXP-013 | All four clusters ≥0.98 Jaccard |
| 5 | Cluster profiling | — | Labels derived after inspection |
| 6 | Demographic sensitivity | EXP-011 | **ARI 1.000** — identical partitions |
| 7 | Teacher signal | EXP-014 | **Rejected** — +0.0009 silhouette |
| 8 | Level ablation *(added)* | EXP-011g | **Decisive** — structure *is* the level split |
| — | Feature dominance | EXP-011c | Level 31.1%, demographics 0.04% |
| — | Volume dominance | EXP-011f | η²(`total_courses`) = 0.820 |

---

## 3. Major findings

### 3.1 The partition is essentially a course-level split

Three of the four clusters are **100% one course level**:

| Cluster | n | Share | Courses | Level |
| --- | --- | --- | --- | --- |
| 0 | 715 | 27.0% | 1.34 | **100% Beginner** |
| 1 | 522 | 19.7% | **9.65** | mixed (44/39/16) |
| 2 | 881 | 33.2% | 1.51 | **100% Advanced** |
| 3 | 532 | 20.1% | 1.25 | **100% Intermediate** |

The level ablation (EXP-011g) confirms this is not incidental. Removing
`preferred_level` produces an almost entirely different partition (**ARI 0.253**),
drops mean bootstrap Jaccard from **0.999 to 0.656**, and introduces an unstable
cluster. **The stable structure in this dataset *is* the level split**, plus one
high-volume group holding 19.7% of learners and ~63% of enrollments.

For the majority of learners this is a thin axis: clusters 0, 2 and 3 average
1.25–1.51 courses, so "preferred level" is usually the level of a single
enrollment — and Phase 2 found level choice statistically indistinguishable from
chance (z = −2.65, at the Bonferroni boundary, 0.03 levels out of 2.2).

### 3.2 Demographics change nothing — ARI exactly 1.000

| | Variant B | Variant A (+ demographics) |
| --- | --- | --- |
| Silhouette | **0.1946** | 0.1729 |
| Mean bootstrap Jaccard | **0.999** | 0.991 |
| Demographic block share | — | **0.0004** |

The partitions are **identical**. The demographic block explains 0.04% of
between-cluster variance — far below the 20% "secondary" band of the
pre-registered rule. Demographics do not merely fail to dominate; they are
**invisible**.

This is the cleanest possible answer to CLAUDE.md §10, and it corroborates Phase 2
at the modelling level (age and gender were already independent of course choice,
all χ² p > 0.2). Age and gender are retained for **evaluation stratification** in
Phase 3B [R30] — auditing with a protected attribute is not modelling with it.

### 3.3 Teacher features rejected on evidence

| | Core | Core + teacher |
| --- | --- | --- |
| Silhouette | 0.1946 | 0.1955 (**+0.0009**) |
| Mean bootstrap Jaccard | **0.999** | 0.989 |
| Teacher block share | — | 16.1% |
| Top feature | `preflevel_Intermediate` | `teacher_loyalty` |

**ARI core vs teacher: 0.990.** The teacher block becomes the most explanatory
single feature yet moves the partition almost not at all. The reason is in the
Phase 2 audit: `teacher_loyalty` correlates **+0.963** with `total_courses` and is
zero by construction for the 54% of learners with one course — its η² reflects that
correlation, not new information.

**Scope:** this rejects teacher features for *segmentation only*. Phase 2 found
instructor loyalty to be the one genuine behavioural signal in the dataset, and it
remains a live candidate for the Phase 3B recommender.

### 3.4 Hierarchical validation is a negative result

| Comparison | ARI | Sizes |
| --- | --- | --- |
| K-Means vs **Ward** | **0.350** | 747 · 374 · 1,005 · 524 |
| K-Means vs **average linkage** | **0.019** | **21 · 110 · 113 · 2,406** |

Ward and K-Means optimise the same objective family, so 0.350 is already the weak
form of confirmation Phase 1 warned about — and it is modest even by that standard.
Average linkage, which optimises something different, agrees essentially not at all
and collapses 91% of learners into one cluster.

**The structure is not algorithm-independent.** It is found by variance-minimising
methods and not by others. That does not invalidate the K-Means partition — the
brief mandates K-Means, and the partition is stable and interpretable — but the
segmentation must be described as *one defensible view of the data*, not as
discovered natural groupings.

### 3.5 The gap statistic failed as an instrument

Added in Phase 1 (D-017) precisely because it is the only criterion that can report
"no structure". Over k = 1…20 the gap rises **monotonically** and never turns over.
Its uniform bounding-box reference is a poor null for discrete, bounded, bimodal
features — which describes most of this feature set.

Reported as a failed instrument rather than read as endorsing k=20. The consequence
is a genuine limitation: **this project has no criterion capable of falsifying the
existence of cluster structure.** GMM/BIC also selects the range maximum, consistent
with "more components always fit better" rather than an identified optimum.

### 3.6 RobustScaler is degenerate here — settling a deferred decision

`B_robust_scaled` posted by far the highest silhouette (**0.716**, three times any
other arm). That is a pathology, not a result. Two mandated features have an
**interquartile range of exactly zero**:

| Feature | q25 | q50 | q75 | IQR |
| --- | --- | --- | --- | --- |
| `avg_courses_per_category` | 1.000 | 1.000 | 1.000 | **0.000** |
| `diversity_ratio` | 1.000 | 1.000 | 1.000 | **0.000** |

54% of learners have a single course, so all three quartiles coincide. RobustScaler
leaves those columns unscaled while compressing the others, manufacturing a
separable axis; the k=2 split it produces (2,198/452) is a rediscovery of the Phase
2 activity bimodality through a scaling bug.

**Decision: StandardScaler**, settling the D5 choice deferred in Phase 1 on
evidence. A high silhouette obtained this way is a defect, and reporting it as the
best representation would have been a textbook case of optimising for the number
instead of the structure.

### 3.7 The Phase 1 one-hot dominance prediction was wrong at k=4

Measured at the common selected k:

| Representation | Category block share | Level block share |
| --- | --- | --- |
| `B_proportion` (share vector) | 5.0% | 31.1% |
| `B_one_hot` | **3.7%** | 31.5% |

Neither encoding lets category dominate — one-hot is marginally *lower*. Phase 1
expected 12 one-hot columns to swamp the distance metric; at k=4 level and volume
swamp them instead.

The mechanism is real at higher k: read at each arm's own best k, the category
block takes **46.3%** (`A_proportion`, k=9) and **58.3%** (`B_decorrelated`, k=10).
So the reasoning was sound but does not apply at the k the stability constraint
selects. Recorded as a wrong prediction rather than quietly dropped.

---

## 4. Corrections made during this phase

Five, all applied before the results were finalised and all visible in the code:

| # | Correction | Why it mattered |
| --- | --- | --- |
| 1 | **Stability evaluated for every candidate k** | The first implementation applied the size constraint but measured stability *afterwards*. Two of the six clusters it selected had Jaccard 0.33 and 0.54 — they would have failed the rule. Applying the rule as written changed **k from 6 to 4**. A constraint evaluated after the choice is not a constraint. |
| 2 | Gap range extended 1–10 → 1–20 | Stopping at 10 would have disguised a monotone curve as "optimum at the boundary". |
| 3 | `B_no_level` arm added (EXP-011g) | The first run showed the partition was essentially a level split; the ablation is the direct test. Recorded as post-hoc. |
| 4 | Naming restricted to features the model used | The first run produced "Instructor-loyal" labels from teacher features not in the model — implying the segmentation captured something it did not. |
| 5 | Level purity folded into naming | Deviation-based naming is blind to a cluster at the middle of an ordinal scale; the 100%-Intermediate cluster had a near-zero depth deviation. |

---

## 5. Artifacts created

| Artifact | Contents |
| --- | --- |
| `src/edupro/segmentation/representations.py` | 10 representation specs; block map; encodings |
| `src/edupro/segmentation/clustering.py` | K-Means sweep, hierarchical, GMM, seed stability |
| `src/edupro/segmentation/metrics.py` | Silhouette, intra-cluster similarity, η² dominance, gap statistic |
| `src/edupro/segmentation/stability.py` | Per-cluster bootstrap Jaccard, subsample consensus |
| `src/edupro/segmentation/profiling.py` | Profiles, centroid deviations, evidence-derived naming |
| `scripts/run_segmentation_experiments.py` | The full experiment programme |
| `scripts/generate_segmentation_figures.py` | 10 figures |
| `artifacts/segmentation/segmentation_results.json` | Machine-readable results |
| `artifacts/segmentation/*.csv` | Profiles, deviations, level composition, assignments |
| `artifacts/segmentation/*.png` | Elbow, silhouette, constraints, sizes, profiles, level composition, representation comparison, variant/teacher, gap, hierarchical, level ablation |
| `notebooks/03_segmentation_experiments.ipynb` | Executed: 14 cells, 0 errors |
| `research/segmentation_results.md` | Full experimental narrative |
| `research/segmentation_feature_decision.md` | The representation decision and its reversal conditions |
| `research/cluster_profiles.md` | Stakeholder-facing profiles with limitations |
| `tests/test_segmentation.py` | 37 tests |

---

## 6. PASS / FAIL decision

### ✅ **PASS**

| Pass criterion | Evidence | Verdict |
| --- | --- | --- |
| **K-Means experiments completed** | k=2–10 swept across 10 representations; inertia, silhouette, CH, DB, sizes, intra-cluster similarity and 5-seed ARI for every k | ✅ |
| **Hierarchical validation completed** | Ward and average linkage at k=4; ARI reported for all three pairings, with the shared-objective caveat stated. Result is negative and reported as such | ✅ |
| **Elbow and silhouette evaluated** | Both produced (`01_elbow_and_silhouette.png`). Elbow has no knee; silhouette alone would have chosen k=10. Neither was allowed to decide alone | ✅ |
| **Demographic sensitivity evaluated** | EXP-011: ARI 1.000, demographic share 0.0004, decided by the pre-registered rule | ✅ |
| **Teacher experiment evaluated** | EXP-014 ran — EXP-005 in Phase 2 had already refuted the bijection hypothesis that would have made it infeasible. Rejected on evidence, with scope stated | ✅ |
| **Chosen segmentation supported by evidence** | k=4 selected by a rule written before the results; all four clusters ≥0.98 Jaccard; full-history ARI 0.847; every competing arm and k reported including the losers | ✅ |
| **Cluster profiles interpretable** | Four balanced segments, each named from its own deviations using a controlled vocabulary, with the evidence printed beside the name | ✅ |

### Tests

```
104 passed
```
31 environment + 36 pipeline + 37 segmentation, including a test that the
vocabulary cannot produce [R12]'s MOOC labels and a test that naming can be
restricted to features the model used.

### CLAUDE.md compliance

| § | Rule | How Phase 3A complied |
| --- | --- | --- |
| 4 | Gated phases | Segmentation only. No recommender, no Streamlit app |
| 6 | Scientific integrity | Two Phase 1 predictions reported as **wrong** (one-hot dominance; and the k=6 selection corrected to k=4 when the rule was applied properly). A failed instrument (gap statistic) reported rather than dropped. A suspiciously good result (RobustScaler 0.716) investigated and rejected as a bug |
| 7 | No novel algorithms | K-Means, Ward, average linkage, GMM — all established |
| 9 | Leakage | Experiments on the fit window only (L4); full-history run reported as a separate sensitivity check |
| 10 | Demographics | Measured, not assumed. ARI 1.000, share 0.04%. Variant B by the pre-registered rule |
| 11 | Teachers sheet | Isolated arm, rejected on evidence, scope of the rejection stated |
| 16 | Explainability | Naming derived mechanically from centroid deviations, restricted to model features, with evidence recorded per label |
| 17 | Privacy | No PII in any representation; teacher Age/Gender excluded before experimentation |
| 23 | Testing | 37 new tests including the vocabulary and naming-restriction guards |
| 25 | Documentation | Three research documents + this report; decision log and experiment log updated |
| 27 | Phase report with evidence | This document; every number traces to `segmentation_results.json` |
| 28 | Stop condition | Phase 3A evaluated; PASS; **stopping here** |

---

## 7. What this segmentation is, and is not

**It is:** stable (≥0.98 Jaccard per cluster), balanced (19.7%–33.2%),
interpretable, reproducible (seed-deterministic, ARI 0.847 across windows), free of
demographic dominance, and selected by a rule written before the numbers were seen.

**It is not:** a set of motivational learner personas. It is *course level* plus
*activity volume*. It is not algorithm-independent. And its dominant axis encodes a
near-arbitrary attribute of a single enrollment for the ~80% of learners in
clusters 0, 2 and 3.

> **The honest statement for the research paper and the executive summary:** this
> is a reproducible way to group this catalogue's learners by the depth and volume
> of what they take. It is not a discovery about learner motivation, and the
> dataset it describes is assessed as almost certainly synthetic (Phase 2, D-025).

---

## 8. Unresolved issues

None blocking. Four carried forward:

1. **Practical value is unproven.** Whether these segments improve recommendation
   is answered in Phase 3B by EXP-023 (cluster popularity vs global popularity).
   ADR-0005 made the cluster signal ablatable so the question can be answered
   rather than assumed. Given Phase 2 found course popularity near-uniform, the
   expected answer is "little or none" — and that would be a legitimate result.
2. **No falsification instrument.** The gap statistic failed, so nothing in the
   toolkit can report "no cluster structure exists". A limitation to state in the
   research paper.
3. **Synthetic-data caveat (V8)** continues to bound every claim.
4. **Phase 0's two open items remain open**: the empty `claude.md.txt`, and the
   git-identity/authorship question (`Kartik <kartikshreekumar2006@gmail.com>` in
   the global git config vs the session account; `pyproject.toml` recorded a name
   inferred from that account). Both still need confirmation before publication.

   **RESOLVED 20 September 2026: the author is Kartik (`kartikshreekumar2006@gmail.com`), confirmed by the project owner. `pyproject.toml`, the paper byline and the rendered paper now all say so.**

---

## 9. Stop

Per CLAUDE.md §28 and the Phase 3A brief, work **stops here**. Phase 3B will not
begin automatically.

**Phase 3B will, on instruction, run** the nine recommendation experiments
(EXP-019–027) against the persisted Protocol A split, with the random baseline in
every table, coverage as a co-primary metric, Precision@K reported against its
analytical ceiling, and the pre-registered selection rules — including the
parsimony tiebreak — applied as written.
