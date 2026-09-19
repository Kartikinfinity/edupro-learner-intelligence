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

## Pre-registered expectations — status after Phase 2

Phase 1 recorded seven predictions before any data was examined. Comparing them
against evidence is itself part of the record.

| # | Phase 1 expectation | Phase 2 evidence | Status |
| --- | --- | --- | --- |
| P-1 | Popularity hard to beat | Popularity near-uniform, Gini 0.042 | **Revised** — popularity ≈ random; hard to beat *because it is weak*, not strong |
| P-2 | Item-based CF strongest | Co-occurrence *below* the null | **Revised** — expect ≈ random |
| P-3 | Hybrid wins by a small margin | — | Unchanged; awaiting EXP-024 |
| P-4 | Cluster structure weak; gap may say k=1 | Volume dominates; choice is random | **Strengthened** |
| P-5 | Variant B preferred | Demographics independent of choice | **Strengthened** |
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
