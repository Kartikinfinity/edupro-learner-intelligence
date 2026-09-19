# Decision Log

Chronological record of every non-obvious project decision, with the evidence
that justified it. Per CLAUDE.md §25, project knowledge lives here, not in
conversation history.

**Format.** Each entry states the decision, why it was needed, what evidence
supported it, what was rejected, and how it could be reversed. A decision taken
without evidence is recorded as **provisional** and carries the experiment that
will settle it.

**Related documents**
- `research/architecture_decision_record.md` — durable architectural choices (ADRs)
- `research/experiment_log.md` — experiment results, including failures
- `docs/REQUIREMENTS_TRACEABILITY.md` — official requirement → implementation

---

## Phase 0 — Project initialization (19 September 2026)

### D-001 — Copy source materials to canonical paths rather than moving them
**Status:** Settled

The two authoritative files arrived in the workspace root. They were **copied**
(not moved) to `data/raw/` and `references/official/`, and the root originals
were added to `.gitignore`.

**Why:** CLAUDE.md §8 forbids overwriting or modifying original source files.
Copying is non-destructive, so the user's originals stay exactly where they left
them, while the repository still gets a clean canonical layout with exactly one
tracked copy of each file.

**Evidence:** SHA-256 of each copy matches its original byte-for-byte
(`ed555e46…` workbook, `e7944444…` PDF). Both checksums are asserted on every
test run by `tests/test_phase0_environment.py`, so any future modification of
`data/raw/` fails the suite loudly.

**Rejected:** Moving the files (would alter the user's workspace); working
directly from the root paths (leaves the repository layout non-standard and the
paths space-laden and ambiguous).

---

### D-002 — Target Python 3.13, not the system-default 3.14
**Status:** Settled — see ADR-0002

**Why:** The system default is Python 3.14.0 and the full scientific stack
installs cleanly on it, so 3.14 was the path of least resistance. It was
rejected because CLAUDE.md §21 requires the application to be **public-deployment
ready**, and Streamlit Community Cloud — the intended zero-cost deployment
target given the Docker prohibition in §20 — supports up to Python 3.13.
Discovering that at Phase 6 would be an expensive, deadline-adjacent failure.

**Evidence:** Both environments were actually built and smoke-tested. The stack
resolves and passes the modelling smoke test on 3.13.9 (`31 passed`), so nothing
is given up by targeting it.

**Reversal:** If the deployment target changes to one supporting 3.14, relax
`requires-python` in `pyproject.toml` and rebuild `.venv`. No source change.

---

### D-003 — Pin runtime dependencies exactly; keep a separate full lockfile
**Status:** Settled

`requirements.txt` pins the 12 **direct** runtime dependencies exactly.
`requirements.lock.txt` is a full `pip freeze` (130 packages) of the validated
environment. Dev-only tooling is split into `requirements-dev.txt`.

**Why:** Exact pins on direct dependencies make results reproducible without
over-constraining the transitive tree, which is where hosted deployment
environments most often conflict. The full freeze is retained so the exact
environment behind any reported number can always be reconstructed.

**Reversal:** If a host rejects a pin, relax that single line and re-run the test
suite; the lockfile still records what the reported results were produced on.

---

### D-004 — Accept pandas 3.0.6 rather than pinning to the 2.x line
**Status:** Settled with monitoring — see ADR-0004

pandas 3.0.6 resolved on install. It is a major version with breaking changes
(copy-on-write by default, new default string dtype), and seaborn 0.13.2 predates
it.

**Why accepted:** All project code is being written fresh against 3.x, so there
is no legacy-API exposure. The risk was concentrated in seaborn interop, and that
was tested rather than assumed.

**Evidence:** `test_seaborn_plots_on_the_installed_pandas_major_version` exercises
the six seaborn plot types this project will actually use (`histplot`, `boxplot`,
`countplot`, `barplot`, `scatterplot`, `heatmap`) against the installed pandas.
It passes. The test is retained as a regression guard, not deleted after use.

**Reversal:** If a pandas 3.x incompatibility appears in a later phase, pin
`pandas>=2.2,<3` in `requirements.txt` and rebuild. The guard test will be the
thing that catches it.

---

### D-005 — Pin matplotlib to 3.11.2 (a deprecation becomes a break at 3.13)
**Status:** Settled

**Evidence:** The Phase 0 test run surfaced exactly one warning:

```
seaborn/categorical.py:700: MatplotlibDeprecationWarning: vert: bool was
deprecated in Matplotlib 3.11 and will be removed in 3.13.
```

seaborn 0.13.2's `boxplot` passes the deprecated `vert=` argument. It works on
matplotlib 3.11.2 and will **break** on matplotlib 3.13. The exact pin
`matplotlib==3.11.2` is therefore load-bearing, not cosmetic.

**Reversal:** Upgrade seaborn past 0.13.2 once a release drops `vert=`, then the
matplotlib pin can be relaxed. Until then, do not float matplotlib.

---

### D-006 — Transcribe the official PDF, but keep the PDF authoritative
**Status:** Settled

**Why needed:** The official PDF has **no text layer** — `pypdf` extracts 0
characters from all 6 pages. Requirements that cannot be quoted or diffed cannot
be traced, so a transcript was produced by rendering each page and reading it
(`scripts/render_official_pdf.py`).

**Guard against drift:** `references/official/OFFICIAL_REQUIREMENTS_TRANSCRIPT.md`
states explicitly that the PDF wins on any disagreement, records the PDF's
SHA-256, and the rendering script re-verifies that checksum before and after
running. The transcript adds nothing and interprets nothing; observations are
segregated into a clearly-labelled section at the end.

---

### D-007 — Teachers sheet excluded from `CORE_SHEETS`
**Status:** Provisional — settles in Phase 3

`src/edupro/config.py` defines `CORE_SHEETS = (Users, Courses, Transactions)`
and a separate `ALL_SHEETS` that includes `Teachers`.

**Evidence:** The official documentation's "Dataset Fields Utilized" section
names only the Users, Courses and Transactions sheets. The workbook nonetheless
contains a `Teachers` sheet (60 rows x 7 columns). This corroborates CLAUDE.md
§11 independently of it.

**What settles it:** The Phase 3 experiment *core model* vs *core model +
validated teacher-derived signals*, judged on segmentation quality and
recommendation metrics. Teacher signals are retained **only** on defensible
evidence. Either outcome — including "teacher signals did not help" — is a
publishable result and will be recorded in the experiment log.

---

### D-008 — Phase 0 records dataset *structure* only, never dataset *findings*
**Status:** Settled

`scripts/inspect_sources.py` deliberately reports sheet names, row/column counts,
dtypes, null counts and cardinalities — and computes no distributions, no summary
statistics and no interpretations.

**Why:** CLAUDE.md §4 gates EDA behind Phase 2. Producing findings in Phase 0
would let un-audited numbers leak into later documents before the data has been
validated. The one exception was made explicitly: the distinct `(UserID,
CourseID)` pair count was checked because the manifest asserted a matrix-density
figure, and an asserted number must be a verified number (§6).

**Result of that check:** all 10,000 transaction rows are distinct user-course
pairs (zero repeats), giving exactly 5.56% density and 3.333 distinct courses per
learner. The interaction signal is therefore purely binary/implicit — there is no
repeat-purchase frequency available to weight by, which constrains the
recommender design in Phase 3.

---

## Open questions carried into later phases

These are recorded now so they are not quietly forgotten. None is answered yet.

| # | Question | Raised by | Settles in |
| --- | --- | --- | --- |
| Q-1 | Is `Transactions.Amount` simply `Courses.CoursePrice` at purchase time? Both have exactly 23 distinct values. If they are identical, "average spending" and "average course price" are the same feature under two names, and only one belongs in the model. | Phase 0 inventory | Phase 2 |
| Q-2 | `Courses.CourseName` has 58 distinct values across 60 unique `CourseID`s — two names repeat. Are these genuinely distinct courses, or duplicates? Affects content-based similarity and the de-duplication of recommendations. | Phase 0 inventory | Phase 2 |
| Q-3 | Should `CoursePrice` and `CourseDuration` be used at all? They are in the workbook but absent from the official field list. Using them needs justification; ignoring them may discard signal. | Phase 0 transcript | Phase 2/3 |
| Q-4 | Where do the sparse-history tier boundaries fall? The mean is 3.333 courses per learner, but the mean is not the distribution. | CLAUDE.md §15 | Phase 2 |
| Q-5 | Variant A (behaviour + demographics) or Variant B (behaviour only)? Must be decided on cluster quality, stability, behavioural consistency, interpretability and feature dominance — not assumed. | CLAUDE.md §10 | Phase 3 |
| Q-6 | Is a temporal hold-out even viable? It requires enough per-learner history; at a mean of 3.333 interactions, a leave-one-out scheme may leave very little to train on, and one-interaction learners must not be evaluated as if personalised (§12). | CLAUDE.md §9, §12 | Phase 2/3 |
| Q-7 | How is "Engagement Lift (Proxy)" defined so that it is honest? The official document requires the metric but defines no formula. Whatever is used must be labelled a proxy and must not be presented as measured causal impact (§6). | Official doc, p.5 | Phase 3 |
