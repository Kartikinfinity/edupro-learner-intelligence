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
| — | — | *No experiments run yet.* | — | — |

Phase 0 is project initialization. It performs **environment validation**, not
experimentation, so it produces no entries here. The validation checks it did
run — dependency imports, a K-Means/hierarchical smoke test on synthetic blobs,
seed determinism, seaborn/pandas interop, and source-material checksums — are
recorded as test results in `research/PHASE_0_COMPLETE.md` and are enforced
continuously by `tests/test_phase0_environment.py`.

The synthetic-data smoke tests deliberately assert nothing about the EduPro
dataset. They verify that the *tooling* works. No EduPro finding exists yet.

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
