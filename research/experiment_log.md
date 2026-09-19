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

Registered now so the plan is on record before any results exist, and so a
disappointing result cannot be quietly dropped from the programme. Nothing below
has been run.

### Phase 2 — dataset audit
- **EXP-001** Referential integrity and key uniqueness across all four sheets.
- **EXP-002** Is `Transactions.Amount` identical to `Courses.CoursePrice`? (Q-1)
- **EXP-003** Per-learner interaction distribution; derive sparse-history tier
  boundaries from the actual distribution. (Q-4)
- **EXP-004** Temporal coverage of `TransactionDate`; is a temporal hold-out
  viable at this history depth? (Q-6)

### Phase 3 — segmentation
- **EXP-010** Cluster-count selection: elbow + silhouette sweep over k.
- **EXP-011** Variant A (behaviour + demographics) vs Variant B (behaviour only),
  on cluster quality, stability, behavioural consistency and feature
  dominance. (Q-5, CLAUDE.md §10)
- **EXP-012** Hierarchical clustering as an independent validation of the
  K-Means structure.
- **EXP-013** Cluster stability under resampling and reseeding.
- **EXP-014** Core model vs core model + teacher-derived signals. (D-007, §11)

### Phase 3 — recommendation
- **EXP-020** Global popularity baseline.
- **EXP-021** Content-based filtering.
- **EXP-022** Similar-learner recommendation.
- **EXP-023** Cluster-popularity recommendation.
- **EXP-024** Hybrid, with weights justified by experiment rather than asserted
  (§14).
- **EXP-025** Cold-start / sparse-history tier behaviour, evaluated separately
  from the personalised path so that one-interaction learners are not scored as
  if they were personalised (§12).

All recommendation experiments share one leakage-controlled temporal split,
defined once in Phase 2 and never re-derived per experiment.
