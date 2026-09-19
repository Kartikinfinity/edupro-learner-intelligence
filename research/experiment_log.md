# Experiment Log

Every experiment run in this project, recorded whether it succeeded or failed.

**This log is append-only.** Entries are never deleted or rewritten to look
better in hindsight. CLAUDE.md §6 prohibits hiding failed experiments and
prohibits selectively reporting only favourable results: a method that
underperforms is evidence, and the record of it is what makes the final model
choice defensible rather than asserted.

---

## How to record an experiment

Copy this template. Fill in **Result** and **Interpretation** only after the run
completes — never in advance.

```markdown
### EXP-XXX — <short title>
| Field | Value |
| --- | --- |
| Phase | |
| Date | |
| Question | What specific question does this run answer? |
| Hypothesis | Stated BEFORE running. |
| Method | Algorithm, parameters, feature set. |
| Data | Exact input, split definition, row counts. |
| Seed | `config.RANDOM_SEED` unless stated otherwise. |
| Leakage control | How future information was kept out. |
| Metrics | Which, and why those. |
| Script | Path to the exact script/notebook that produced this. |
| Artifacts | Where outputs were written. |

**Result:** the numbers, as produced.

**Interpretation:** what they support, and — explicitly — what they do not.

**Decision:** adopt / reject / needs another run. Cross-reference the decision log.
```

### Rules

1. **State the hypothesis before the run.** An after-the-fact hypothesis is a
   description, not a test.
2. **Record the seed and the script path.** A number that cannot be regenerated
   cannot be defended.
3. **Record negative results in full.** "K-Means with demographics scored worse"
   is a finding that earns its place in the research paper.
4. **Never tune against the test split.** Model selection uses train/validation;
   the temporal test hold-out is touched once, at the end (§9, §12).
5. **Separate metric from claim.** A proxy is reported as a proxy. Observational
   data does not support causal language (§6).

---

## Experiment index

| ID | Phase | Title | Outcome | Date |
| --- | --- | --- | --- | --- |
| EXP-001 | 2 | Referential integrity and key uniqueness | **PASS** — 0 errors | 19 Sep 2026 |
| EXP-002 | 2 | Is `Amount` identical to `CoursePrice`? | **Hypothesis confirmed** — identical on all 10,000 rows | 19 Sep 2026 |
| EXP-003 | 2 | Per-learner interaction distribution | **Hypothesis partly refuted** — right-skew confirmed, but bimodal with an empty band at 5–8 | 19 Sep 2026 |
| EXP-004 | 2 | Temporal coverage and split viability | **Hypothesis confirmed** — Protocol A viable (791 ≥ 300) | 19 Sep 2026 |
| EXP-005 | 2 | Is `TeacherID` an alias for `CourseID`? | **Hypothesis REFUTED** — 887 pairs, not a bijection. EXP-014 proceeds | 19 Sep 2026 |
| EXP-006 | 2 | Feature distributions; synthetic-data assessment | **Hypothesis confirmed and extended** — near-uniform throughout; **no course-choice signal** | 19 Sep 2026 |
| EXP-010 | 3A | Cluster-count sweep: elbow, silhouette, CH, DB | **k=4** by the pre-registered rule; elbow uninformative | 19 Sep 2026 |
| EXP-010b | 3A | Gap statistic | **Instrument failed** — monotone to k=20, no verdict | 19 Sep 2026 |
| EXP-010c | 3A | GMM/BIC cross-check | Selects the range maximum; no interior optimum | 19 Sep 2026 |
| EXP-011 | 3A | Variant A vs Variant B | **ARI 1.000** — demographics change nothing. Variant B | 19 Sep 2026 |
| EXP-011a | 3A | Encoding comparison | **Phase 1 dominance prediction refuted at k=4** | 19 Sep 2026 |
| EXP-011c | 3A | Feature-dominance diagnostic | Level 31.1%, demographics 0.04% | 19 Sep 2026 |
| EXP-011f | 3A | History-length dominance | eta^2 = 0.820, but ARI vs cohort split only 0.177 | 19 Sep 2026 |
| EXP-011g | 3A | Level ablation *(added post-hoc)* | **Decisive** — the stable structure *is* the level split | 19 Sep 2026 |
| EXP-012 | 3A | Hierarchical validation | **Negative** — average linkage agrees at ARI 0.019 | 19 Sep 2026 |
| EXP-013 | 3A | Cluster stability | All four clusters >=0.98 bootstrap Jaccard | 19 Sep 2026 |
| EXP-014 | 3A | Core vs core + teacher signals | **Rejected** — +0.0009 silhouette, ARI 0.990 | 19 Sep 2026 |
| EXP-019 | 3B | Random reference floor | NDCG@10 **0.1102** on test — ranks 7th of 12 | 19 Sep 2026 |
| EXP-020 | 3B | Global popularity | **Worse than random** on test (0.1072) | 19 Sep 2026 |
| EXP-021 | 3B | Content-based filtering | Best single baseline on test (0.1191), not significant | 19 Sep 2026 |
| EXP-022a | 3B | User-user over interaction history | Worst method on test (0.0947) | 19 Sep 2026 |
| EXP-022b | 3B | User-user over profile features | **Prediction refuted** — worse than the history arm | 19 Sep 2026 |
| EXP-022c | 3B | Item-based CF | **Prediction refuted** — 8th of 12 on test | 19 Sep 2026 |
| EXP-022d | 3B | Teacher affinity | Not retained — 8th, CI contains zero | 19 Sep 2026 |
| EXP-023 | 3B | **Cluster popularity — does segmentation help?** | Beats popularity, **not** random. Q-10 answered | 19 Sep 2026 |
| EXP-024 | 3B | Weighted hybrid + ablation | Weights searched; **lost the parsimony tiebreak** | 19 Sep 2026 |
| EXP-025 | 3B | Tiered switching recommender | Full coverage; recommended for deployment | 19 Sep 2026 |
| EXP-026 | 3B | Protocol A vs B | **Rankings differ** — [R24] reproduced | 19 Sep 2026 |
| EXP-027 | 3B | Demographic-stratified evaluation | Gender gap nominally significant; bounded | 19 Sep 2026 |

Phase 0 was project initialization: **environment validation**, not
experimentation, so it produced no entries. Those checks are recorded in
`research/PHASE_0_COMPLETE.md` and enforced by `tests/test_phase0_environment.py`.
Phase 1 was literature research and produced no experiments either.

---

## Phase 2 results

Full detail in `research/dataset_audit.md`; machine-readable record in
`artifacts/phase2_audit.json`. Reproduce with `python scripts/run_data_audit.py`
(seed 42).

### EXP-001 — Referential integrity and key uniqueness
| Field | Value |
| --- | --- |
| Hypothesis | All foreign keys resolve; all primary keys unique. |
| Method | `edupro.data.validation.validate` — 12 check families across 4 sheets. |
| Script | `scripts/run_data_audit.py` |

**Result:** 0 errors, 1 warning, 4 info. Zero orphans on all three foreign keys in
both directions; all four primary keys unique; zero duplicate rows; zero nulls
across 27 columns; no out-of-domain values.

**Interpretation:** the data requires no cleaning. It does **not** support any
claim about learner behaviour — integrity is not signal.

**Decision:** proceed with no cleaning step. Warning I-4 (two repeated course
names, distinct courses) documented; `CourseName` cannot identify a course.

---

### EXP-002 — Is `Amount` identical to `CoursePrice`? (Q-1)
| Field | Value |
| --- | --- |
| Hypothesis | Identical — both have exactly 23 distinct values. |
| Method | Row-wise join and comparison, 10,000 transactions. |

**Result:** identical on **10,000 / 10,000 rows (100.00%)**.

**Interpretation:** "average spending" is a deterministic function of which
courses were chosen, not independent behaviour. It does **not** mean spending is
uninformative — it means it is not *additional* information beyond catalogue choice.

**Decision:** `avg_spend` retained (brief-mandated) with the redundancy documented;
`total_spend` dropped; `free_ratio` preferred as the interpretable form. **Q-1
answered.**

---

### EXP-003 — Per-learner interaction distribution (Q-4)
| Field | Value |
| --- | --- |
| Hypothesis | Right-skewed with substantial mass at 1–2 interactions. |

**Result:** mean 3.333, median **1**, max 16. 1 → 1,620 (54.0%); 2 → 612 (20.4%);
3 → 186; 4 → 128; **5–8 → 0 learners**; 9–16 → 454. Variance 18.94 vs mean 3.33.
Gini 0.546.

**Interpretation:** the skew hypothesis was right but incomplete — the distribution
is **bimodal with a hard empty band**. No sampling process produces that; two
populations were generated with different count distributions. This does **not**
tell us the cohorts differ behaviourally; measured separately, they do not.

**Decision:** tier boundaries 1 / 2–4 / ≥9, **handed over by the data** rather than
tuned. **Q-4 answered.**

---

### EXP-004 — Temporal coverage and split viability (Q-6)
| Field | Value |
| --- | --- |
| Hypothesis | ~1 year of data; the 80th-percentile cut leaves enough evaluable learners. |
| Pre-registered rule | Protocol A is primary if ≥300 learners are evaluable. |

**Result:** 2025-01-01 → 2025-12-30, 358 distinct days, no trend or seasonality
(monthly variation < 10%). V = 2025-09-12, T = 2025-10-18. Partitions: train 6,992
· validation 1,000 · fit 7,992 · test 2,008. **791 evaluable learners.**

**Interpretation:** the leakage-free protocol is viable. 791 is comfortably above
the threshold but is still only 26% of the user base — estimates will be noisier
than the raw interaction count suggests.

**Decision:** **Protocol A (global temporal) is PRIMARY**, by the pre-registered
rule. Leave-one-out (1,380 evaluable) retained as the labelled leakage-bearing
secondary. Split persisted to `data/processed/splits/`. **Q-6 answered.**

---

### EXP-005 — Is `TeacherID` an alias for `CourseID`? (Q-9) — **hypothesis refuted**
| Field | Value |
| --- | --- |
| Hypothesis | Plausibly a bijection (60 teachers, 60 courses), which would make EXP-014 vacuous. |

**Result:** **887 distinct `(course, teacher)` pairs.** 7–30 teachers per course
(mean 14.8); 7–55 courses per teacher (mean 14.8). Not a bijection. Teacher
assignment is not independent of course (χ² = 31,867, df = 3,481, p < 0.0001), and
`Expertise` matches `CourseCategory` on 41.1% of transactions vs 8.3% chance.

**Interpretation:** the Phase 1 hypothesis was **wrong**. The teacher dimension is
independently structured, so teacher features are not aliases for course features.

**Decision:** **EXP-014 proceeds.** Pre-registered expectation P-6 is half-refuted:
the cancellation branch is closed.

---

### EXP-006 — Distributions and signal detection
| Field | Value |
| --- | --- |
| Hypothesis | Some features skewed; cardinalities suggest synthetic data. |
| Method | Chi-square uniformity tests; permutation null (200 replicates, seed 42) for preference statistics; chi-square independence for demographics. |

**Result — course choice carries no signal:**

| Statistic | Observed | Null mean | Null 95% CI | z |
| --- | --- | --- | --- | --- |
| Mean distinct categories | 2.5773 | 2.5869 | [2.571, 2.602] | −1.17 |
| Mean top-category share | 0.7210 | 0.7194 | [0.717, 0.722] | +1.12 |
| Mean distinct levels | 1.5560 | 1.5707 | [1.560, 1.582] | −2.65 |
| Mean free-course share | 0.6501 | 0.6394 | [0.626, 0.654] | +1.51 |

Course popularity near-uniform (140–196, Gini 0.042, χ² p = 0.60). Item–item
co-occurrence std 5.46 vs null 5.87 [5.58, 6.12] — *below* the null. Demographics
independent of choice (all p > 0.2). No level progression (slope +0.005, p = 0.664).

**Result — one real signal:** distinct teachers per interaction **0.688** vs null
**0.944** [0.939, 0.950]. Heavy learners take ~13.4 courses from **2.0**
instructors. But next-course lift is only **1.10×** (49.0% vs 44.7% chance),
because each teacher covers ~15 of ~55 unseen courses.

**Interpretation:** course selection in this dataset is statistically
indistinguishable from popularity-weighted random choice. This says nothing about
whether the *methods* work — it says this dataset contains little for them to find.
The marginal level result (z = −2.65) is 0.03 levels out of 2.2, at the Bonferroni
boundary across eight tests, and is **not** treated as a usable signal.

**Decision:** dataset assessed as almost certainly synthetic; registered as threat
V8. Phase 3 expectations revised (below). **Q-8 answered.**

---

## Phase 3A results

Full detail in `research/segmentation_results.md`; machine-readable record in
`artifacts/segmentation/segmentation_results.json`. Reproduce with
`python scripts/run_segmentation_experiments.py` (seed 42).

**Window:** the fit window — 2,650 learners, 7,992 interactions before the
pre-registered 2025-10-18 test cut, so assignments can feed Phase 3B without
leaking (control L4).

### EXP-010 — Cluster-count selection
| Field | Value |
| --- | --- |
| Hypothesis | A modest k (3-6) optimises silhouette; the elbow is ambiguous. |
| Method | K-Means (k-means++, n_init=10) for k=2..10; inertia, silhouette, CH, DB, sizes, intra-cluster similarity, 5-seed ARI. |

**Result:** the elbow has no knee. Silhouette rises monotonically from 0.177 (k=2)
to 0.269 (k=10). Unconstrained, it would select k=10.

Applying both pre-registered constraints — every cluster >=5% of learners **and**
every cluster bootstrap Jaccard >=0.60 — only k = 2, 3, 4 qualify. **k = 4** has
the highest silhouette among them (0.1946).

**Interpretation:** the hypothesis about the elbow was right. The silhouette
hypothesis was right about the range but for the wrong reason: a modest k wins
because larger k fragments, not because silhouette peaks there.

**Decision:** k = 4.

---

### EXP-010b — Gap statistic — **the instrument failed**
| Field | Value |
| --- | --- |
| Hypothesis | The gap statistic indicates k >= 2, i.e. structure exists. |
| Method | Tibshirani-Walther-Hastie gap over k=1..20, 50 uniform reference datasets. |

**Result:** the gap rises **monotonically** across the whole range and never turns
over. No interior optimum.

**Interpretation:** the uniform bounding-box reference is a poor null for discrete,
bounded, bimodal features. The statistic returns **no verdict** — it does not
endorse k=20. This is reported as a failed instrument rather than dropped.

**Consequence:** this project has **no criterion capable of falsifying the
existence of cluster structure.** A genuine limitation, recorded for the research
paper. GMM/BIC (EXP-010c) also selects the range maximum, consistent with "more
components always fit better".

---

### EXP-011 — Variant A vs Variant B — **demographics change nothing**
| Field | Value |
| --- | --- |
| Hypothesis | Variant B is no worse and more actionable; demographics risk dominating. |

**Result:** **ARI between the two partitions = 1.000.** They are identical.
Demographic block share of between-cluster variance = **0.0004**. Silhouette
0.1946 (B) vs 0.1729 (A).

**Interpretation:** demographics do not merely fail to dominate — they are
invisible. The slight silhouette drop is the geometric cost of two uninformative
dimensions. This confirms Phase 2 at the modelling level.

**Decision:** **Variant B** by the pre-registered tie rule. Age and gender retained
for evaluation stratification in Phase 3B only.

---

### EXP-011a — Encoding comparison — **Phase 1 prediction refuted**
**Result (at the common selected k=4):** category block share is **5.0%**
(proportion vector) and **3.7%** (one-hot). Neither dominates; one-hot is
marginally lower.

**Interpretation:** Phase 1 predicted 12 one-hot columns would swamp the distance
metric. **Wrong at k=4** — level and volume swamp them instead. The mechanism is
real at higher k (46.3% for `A_proportion` at k=9; 58.3% for `B_decorrelated` at
k=10), so the reasoning was sound but does not apply at the selected k.

**Also found:** `B_robust_scaled` posted silhouette **0.716**, three times any other
arm. Investigated rather than accepted: two mandated features have **IQR exactly
zero** (54% of learners have one course, so their quartiles coincide), and
RobustScaler leaves those unscaled while compressing the rest. A scaling
pathology, not a better representation.

**Decision:** proportion encoding (on interpretability grounds, not dominance) and
**StandardScaler** — settling the D5 choice deferred in Phase 1.

---

### EXP-011g — Level ablation *(added post-hoc)* — **decisive**
Added after the first run showed three of four clusters were 100% one course level.
Recorded as a post-hoc addition, not presented as planned.

| | With level | Without level |
| --- | --- | --- |
| Silhouette | 0.1946 | 0.1877 |
| Mean bootstrap Jaccard | **0.999** | **0.656** |
| Unstable clusters | **0** | **1** |

**ARI with vs without: 0.253.**

**Interpretation:** removing `preferred_level` produces an almost entirely
different, unstable partition. **The stable structure in this dataset *is* the
course-level split.**

---

### EXP-012 — Hierarchical validation — **negative result**
**Result:** ARI K-Means vs Ward **0.350**; vs average linkage **0.019**. Average
linkage collapses 91% of learners into one cluster (21 / 110 / 113 / 2,406).

**Interpretation:** Ward shares K-Means's objective family, so 0.350 is already
weak confirmation — and it is modest even by that standard. Average linkage, which
optimises something different, agrees essentially not at all. **The structure is
not algorithm-independent.**

---

### EXP-013 — Cluster stability
**Result:** per-cluster bootstrap Jaccard at k=4: **0.983 / 0.996 / 0.996 / 0.981**
(100 resamples). Subsample consensus ARI **0.987**. Seed ARI **1.000**.

Stability collapses beyond k=4: 1 unstable cluster at k=5, 2 at k=6, 5 at k=7, 6 at
k=8 and k=9.

**Interpretation:** the cliff between k=4 and k=5 is the clearest signal in the
entire selection.

**Process correction:** the first run selected k=6 because the implementation
applied the size constraint and measured stability *afterwards*. Two of those six
clusters scored 0.33 and 0.54. Applying the rule as written, over every candidate
k, changed the answer to **k=4**. A constraint evaluated after the choice is not a
constraint.

---

### EXP-014 — Teacher signal — **rejected**
| | Core | Core + teacher |
| --- | --- | --- |
| Silhouette | 0.1946 | 0.1955 (**+0.0009**) |
| Mean bootstrap Jaccard | **0.999** | 0.989 |
| Teacher block share | — | 16.1% |

**ARI core vs teacher: 0.990.**

**Interpretation:** `teacher_loyalty` becomes the most explanatory single feature
yet barely moves the partition, because it correlates **+0.963** with
`total_courses` (Phase 2) and is zero by construction for single-course learners.
Its eta-squared reflects that correlation, not new information.

**Decision:** not retained for segmentation. §11 requires defensible evidence of
improvement; +0.0009 silhouette with a worse stability profile is not that. The
rejection is scoped to segmentation — instructor loyalty remains a live candidate
for the Phase 3B recommender.

---

## Phase 3B results

Full detail in `research/recommendation_results.md` and
`research/recommendation_error_analysis.md`; machine-readable record in
`artifacts/recommendation/recommendation_results.json`. Reproduce with
`python scripts/run_recommendation_experiments.py` (seed 42).

**Protocol:** train < 2025-09-12 | validation 09-12 to 10-18 (all selection) |
fit < 2025-10-18 | test >= 2025-10-18 (**used exactly once**). 511 evaluable
learners at validation, 791 at test. All six leakage controls passed at both
stages.

### The headline result
| Field | Value |
| --- | --- |
| Question | Does any recommendation method beat random ranking on this dataset? |
| Method | Paired bootstrap of per-learner NDCG@10 differences vs random, 2,000 resamples |

**Result:** **0 of 11 methods** are significantly better than random. Every 95%
interval contains zero, in aggregate and within every history tier. Random ranks
**7th of 12** on the test window; global popularity is **worse** than random
(0.1072 vs 0.1102).

**Interpretation:** this is what Phase 2's signal detection predicted. It does
**not** show the methods are wrong or the pipeline broken — every component is
tested and transfers unchanged. It shows the dataset contains no course-choice
signal to find.

**Decision:** reported as the project headline (CLAUDE.md §6), not a footnote.

---

### EXP-023 — Does the segmentation help recommendation? (**answers Q-10**)
| Comparison | Validation | Test |
| --- | --- | --- |
| cluster_popularity vs global_popularity | +0.0044 | **+0.0066** |
| cluster_popularity vs random | +0.0125 | +0.0036 |
| Paired CI vs random (test) | — | **[-0.0092, +0.0271] — contains zero** |

**Interpretation:** segmenting learners and recommending within segment beats
recommending globally popular courses — but global popularity is itself worse than
random here, so that is a low bar. **The Phase 3A segmentation has not
demonstrated recommendation value.** It retains standalone analytical value for
the brief's learner-analysis requirement; the distinction must be drawn rather
than blurred.

---

### EXP-024 — Hybrid weight search and ablation
**Result:** best validation NDCG@10 **0.1148** with weights cluster_popularity
0.557, rating 0.249, item_item_cf 0.173, preference_match 0.021, and **zero** for
content_based and user_user_profile. Across 400 samples NDCG ranged 0.0832-0.1148,
sd **0.0057**.

Ablation: removing `rating` costs -0.0102 (largest), `cluster_popularity` -0.0088,
`item_item_cf` -0.0036; the two zero-weight components cost nothing.

**Interpretation:** `rating` is useless alone (below random, 0.0956) yet takes the
second-largest weight — it works as a tie-break on another signal. Isolating it as
its own baseline is what made that visible.

**Decision:** the hybrid won validation by **0.0051** over `cluster_popularity`,
inside the pre-registered 0.01 parsimony margin, so the rule selected the simpler
method. Expectation **P-3** confirmed exactly.

---

### EXP-026 — Protocol A vs Protocol B
**Result:** five methods move three or more ranks between protocols. `item_item_cf`
rises 9th -> 3rd; `random` falls 6th -> 11th.

**Interpretation:** Meng et al. [R24] reproduced on EduPro. A project using
leave-one-out alone would have concluded item-based CF was top-three and random
bottom-ranked; neither holds under the leakage-free protocol. **Caution:** Protocol
B's lower absolute scores are an artefact of holding out one course instead of
2.05, **not** evidence of leakage deflation.

---

### EXP-027 — Demographic strata
**Result:** female NDCG@10 0.1002 vs male 0.1285. Gap **-0.0283**, CI
[-0.0543, -0.0010], consistent in direction across all three tiers.

**Interpretation:** nominally significant and reported, but bounded: no demographic
feature enters any model; Phase 2 found gender independent of course choice
(p = 0.643); the interval barely excludes zero and is uncorrected for four strata
tests; and no method beats random at all.

**Decision:** recorded as requiring monitoring on real data, **not** as a finding
of discrimination.

---

## Pre-registered expectations — status after Phase 3B

Phase 1 recorded seven predictions before any data was examined. Comparing them
against evidence is itself part of the record.

| # | Phase 1 expectation | Phase 2 evidence | Status |
| --- | --- | --- | --- |
| P-1 | Popularity hard to beat | **Refuted as stated, confirmed as revised** — global popularity is *worse* than random on test (0.1072 vs 0.1102) | **Settled (EXP-020)** |
| P-2 | Item-based CF strongest | **REFUTED** — 8th of 12 on test (0.1047); content-based led the baselines | **Settled (EXP-022c)** |
| P-3 | Hybrid wins by a small margin | — | Unchanged; awaiting EXP-024 |
| P-4 | Cluster structure weak; gap may say k=1 | Silhouette 0.195 at k=4 is weak, as predicted. But the gap statistic **failed** — it could not deliver any verdict, so the k=1 half is untestable with this instrument | **Half-confirmed, half-untestable** |
| P-5 | Variant B preferred | **CONFIRMED** — ARI 1.000, demographic share 0.0004 | **Confirmed (EXP-011)** |
| P-6 | Teacher signals add nothing; EXP-005 may cancel | EXP-005 refuted the cancellation; teacher reuse is the only real signal, but 1.10× on next-course | **Half-refuted, now genuinely uncertain** |
| P-7 | Coverage separates methods more than accuracy | — | Unchanged; awaiting EXP-019–024 |

---

## Planned experiments

Registered in Phase 1 so the programme is on record **before** any result exists,
and so a disappointing result cannot be quietly dropped. **Nothing below has been
run.** Full specifications — hypotheses, methods, metrics and acceptance criteria
— are in `research/experiment_plan.md`; this is the index.

### Phase 2 — dataset audit (prerequisites)

| ID | Title | Blocks |
| --- | --- | --- |
| EXP-001 | Referential integrity and key uniqueness | everything |
| EXP-002 | Is `Amount` identical to `CoursePrice`? (Q-1) | feature B9 |
| EXP-003 | Per-learner interaction distribution (Q-4) | tier boundaries |
| EXP-004 | Temporal coverage and split viability | **the split protocol decision** |
| EXP-005 | Is `TeacherID` an alias for `CourseID`? | **go/no-go on EXP-014** |
| EXP-006 | Feature distributions; synthetic-data assessment (V8) | scaler choice |

### Phase 3 — segmentation

| ID | Title |
| --- | --- |
| EXP-010 | Cluster-count sweep: elbow, silhouette, CH, DB |
| EXP-010b | **Gap statistic — can falsify the existence of structure** |
| EXP-010c | GMM/BIC cross-check on k |
| EXP-011 | **Variant A (behaviour+demographics) vs Variant B (behaviour only)** |
| EXP-011a | Encoding comparison: one-hot vs proportion vector vs reduced facets vs Gower |
| EXP-011b | Feature-block weighting ablation |
| EXP-011c | Feature-dominance diagnostic (eta-squared per block) |
| EXP-011d | PCA before clustering |
| EXP-011e | Correlated-feature ablation |
| EXP-011f | Does history length dominate the segmentation? |
| EXP-012 / 012b | Hierarchical validation: Ward, then average linkage / Gower |
| EXP-013 / 013b | Per-cluster bootstrap Jaccard stability; subsample consensus |
| EXP-014 | Core model vs core + teacher signals (blocked on EXP-005) |

### Phase 3 — recommendation

| ID | Title |
| --- | --- |
| EXP-019 | Random reference floor |
| EXP-020 | Global popularity |
| EXP-021 | Content-based filtering |
| EXP-022a | User-user similarity over interaction history |
| EXP-022b | User-user similarity over engineered profile features |
| EXP-022c | Item-based collaborative filtering |
| EXP-023 | **Cluster popularity — does segmentation help recommendation?** |
| EXP-024 | Weighted hybrid + component ablation (determines weights) |
| EXP-025 | Tiered switching; sparse-history boundary *t* |
| EXP-026 | Leakage demonstration: random vs temporal split |
| EXP-027 | Demographic-stratified evaluation |

All recommendation experiments share **one** leakage-controlled split, computed
once in EXP-004 and persisted — never re-derived per experiment.

---

## Pre-registered expectations

Recorded in Phase 1, before any experiment, so that hindsight cannot later be
presented as foresight. **These are predictions, not findings.** Each will be
compared against its actual outcome when the corresponding experiment runs.

| # | Expectation | Settled by |
| --- | --- | --- |
| P-1 | Global popularity will be hard to beat on raw accuracy | EXP-020 vs others |
| P-2 | Item-based CF will be the strongest single personalised method | EXP-022c |
| P-3 | The hybrid will win by a small margin, possibly losing the parsimony tiebreak | EXP-024 |
| P-4 | Cluster structure will be weak; the gap statistic may indicate k=1 | EXP-010b |
| P-5 | Variant B (behaviour only) will be preferred | EXP-011 |
| P-6 | Teacher signals will add nothing; EXP-005 may cancel the experiment | EXP-005, EXP-014 |
| P-7 | Coverage will separate methods more sharply than accuracy | EXP-019…024 |

If the experiments contradict these, **the experiments win** and the contradiction
is recorded here as a finding.
