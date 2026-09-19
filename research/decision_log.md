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
installs cleanly on it, so 3.14 was the path of least resistance. It was rejected
because CLAUDE.md §21 requires the application to be **public-deployment ready**,
and Streamlit Community Cloud is the intended zero-cost deployment target given
the Docker prohibition in §20.

> **Corrected in Phase 1.** The original wording of this entry claimed Community
> Cloud "supports up to Python 3.13". That was **not verified** when written.
> The documented policy is that Community Cloud supports all Python versions
> still receiving security updates, and defaults to 3.12 [R37b] — so 3.14 would
> in fact be permitted. The decision to target 3.13 stands, but on the corrected
> rationale in ADR-0002: 3.13 sits one minor version above the platform default,
> inside a support policy that moves over time, and avoids newest-interpreter
> wheel risk for no forgone benefit.

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

## Phase 1 — Dense research (19 September 2026)

Reference keys `[Rxx]` resolve in `research/literature_review.md` §10.

### D-009 — Correction: an unverified platform claim from Phase 0
**Status:** Settled — correction applied

Phase 0 asserted in ADR-0002, D-002, the manifest, the README, `requirements.txt`
and a test docstring that Streamlit Community Cloud "supports Python 3.9–3.13".
Phase 1 set out to attach a citation and found the documentation says something
different: Community Cloud supports all released Python versions still receiving
security updates, and **defaults to 3.12** [R37b]. Under that policy Python 3.14
would in fact have been permitted.

**Action:** the claim was withdrawn from all six locations and ADR-0002 rewritten
with an accurate rationale. The decision (target 3.13) stands, because it remains
correct for different reasons: 3.13 sits one minor version above the platform
default, inside a support policy that moves over time, and avoids
newest-interpreter wheel risk for no forgone benefit.

**Why this is recorded rather than quietly fixed:** the original reasoning reached
a sound conclusion through a false premise, and it survived Phase 0 precisely
because the conclusion looked right. It was caught only because Phase 1 required
a citation for every claim — which is an argument for the citation discipline
itself.

---

### D-010 — Reject latent-factor and neural recommenders before experimentation
**Status:** Settled, with stated reversal conditions

iALS [R13], BPR [R14] and neural recommenders are **excluded from the Phase 3
baseline set** — not silently omitted, but excluded with reasons:

- **iALS:** its distinctive contribution is confidence weighting derived from
  *repeated* observations. EduPro has **zero repeat `(user, course)` pairs**
  (Phase 0, verified), so the confidence function is constant and the method
  degenerates to weighted binary matrix factorisation. Implementing it and
  describing it as [R13] would misrepresent what the model does.
- **BPR:** 10,000 positives over 60 items under-identifies a conventional
  latent-factor model.
- **All three:** latent factors are uninterpretable, conflicting with §16's
  requirement that explanations correspond to signals actually used.
- **[R26]** reproduced only 7 of 18 neural recommendation papers and found most of
  those beaten by properly-tuned simple baselines. The same paper argues the
  higher-value use of a fixed tuning budget is giving strong simple baselines a
  fair run — which is where this project spends it.

**Reversal:** if Phase 2 contradicts the zero-repeat finding, reconsider iALS.

---

### D-011 — Dual evaluation protocol with a pre-registered primary
**Status:** Settled

Both a global temporal split (Protocol A, leakage-free) and per-user
leave-one-out (Protocol B, leakage-bearing) will be run and reported. A is the
pre-registered primary; B is reported for comparability with published work and
is explicitly labelled as leaking.

**Why both:** [R25] shows per-user leave-one-out violates the global timeline and
that leakage can make relative method orderings unpredictable — so B alone cannot
be trusted to select the production model. But A may leave few evaluable learners
at a mean of 3.333 interactions, and dropping B entirely would make the results
incomparable with the literature. [R24] shows the splitting strategy alone can
reorder systems, so **disagreement between A and B is itself a reportable
finding**.

**Pre-registered fallback:** if EXP-004 shows Protocol A yields fewer than 300
evaluable learners, the primary switches to B and every figure is labelled
leakage-bearing. The threshold is fixed now so the choice cannot be made by
looking at which protocol gives better numbers.

---

### D-012 — NDCG@10 as primary accuracy metric; Precision reported with its ceiling
**Status:** Settled

**Evidence (arithmetic, `scripts/analytical_baselines.py`):** with 60 courses and
one held-out item, **Precision@10 is capped at 0.10** and Precision@20 at 0.05.
A random ranker achieves **HR@10 ≈ 0.175**.

The brief mandates "Recommendation Precision", so it is computed and reported —
but reported bare it would make a strong model look like a failure and a weak
model look adequate. Every accuracy figure is therefore reported **against the
random baseline and the analytical ceiling**, and NDCG@10 [R23] is the primary
metric because it is rank-sensitive and not ceiling-limited in the same way.

---

### D-013 — Catalogue coverage is co-primary, with a disqualifying gate
**Status:** Settled

Coverage@10 below **25%** (15 of 60 courses) disqualifies a method regardless of
accuracy. The brief's stated purpose is helping learners *discover relevant
content*; a system routing every learner to the same handful of courses defeats
that while scoring well on accuracy — exactly the failure mode [R27] and [R29]
describe. The threshold is set in advance so it cannot later be relaxed to admit
a preferred method.

---

### D-014 — "Engagement Lift (Proxy)" defined before results are seen
**Status:** Settled

Defined as the ratio of the recommender's HR@10 to the global-popularity
baseline's HR@10, on the same population and split. Defining it now prevents
choosing, later, the formulation that flatters the model.

**Guard rails (§6):** the word "Proxy" is part of the metric's name everywhere
including chart axes; every appearance states it is an offline agreement ratio and
**not** measured causal impact; and no statement of the form "this system would
increase engagement by X%" appears anywhere in the project. The data is
observational with no impressions and no control group — no offline computation
can support that claim.

---

### D-015 — The scorer must return per-component contributions
**Status:** Settled — a Phase 5 interface requirement, decided in Phase 1

The hybrid recommender's scoring function must return the **decomposition**
(content, similarity, cluster-popularity and rating contributions), not just a
scalar total.

**Why decided now:** §16 requires explanations that correspond to the signals the
recommender actually used. [R31] distinguishes model-intrinsic from post-hoc
explanation; only the former can guarantee faithfulness. If the scorer returns
only a total, faithful explanation becomes impossible after the fact, and the
alternative is a post-hoc explainer that can assert reasons the model did not use
— the precise §16 violation. Retrofitting this interface later would be
expensive, so it is fixed before implementation begins.

**Consequence:** this is also why the uninterpretable methods in D-010 were
rejected rather than merely deprioritised.

---

### D-016 — Teacher Age and Gender excluded before experimentation
**Status:** Settled — not subject to experiment

`Teachers.Age` and `Teachers.Gender` are excluded from every model and every
experiment. They are demographics of a **third party** who is not the subject of
the recommendation. Clustering learners by their instructors' gender, or routing
recommendations by it, would be discriminatory allocation with no legitimate
rationale [R38].

This is distinct from the §11 teacher experiment, which proceeds for
`TeacherRating`, `Expertise` and learner–teacher affinity. Some hypotheses should
not be run, and recording the exclusion is more honest than testing and then
discarding.

---

### D-017 — Methods added beyond the brief's minimum, with justification
**Status:** Settled

Three methods not required by the official documentation are added, each because
a mandated method cannot do the job:

1. **Gap statistic [R02]** — elbow, silhouette, CH and DB all *assume* structure
   exists and merely locate the best k. **None can return "there is no cluster
   structure".** Given short histories and the synthetic-data risk (Q-8), that is
   a live possibility, and a project unable to detect it would be structurally
   incapable of reporting it.
2. **Per-cluster bootstrap Jaccard [R03]** — the deliverable is segments a
   stakeholder will act on. A per-segment reliability figure prevents
   recommending a strategy for a segment that dissolves under resampling.
3. **Item-based CF [R15][R16]** — items have ~167 interactions each; users have
   ~3.3. The mandated user-similarity method is estimated from far less evidence,
   and [R26] argues strong simple baselines are essential to a valid comparison.

None of these replaces a mandated method; all are additions.

---

### D-018 — Pre-registration of every decision rule
**Status:** Settled

The k-selection rule, the Variant A/B rule, the model-selection rule (including a
**parsimony tiebreak** selecting the simpler method when the margin is <0.01
NDCG@10), the coverage gate, the tier-boundary rule and the split-protocol
fallback are all written down in Phase 1, **before any result exists**.

**Why:** §6 prohibits selectively reporting favourable results. The most reliable
defence is to fix the decision rules before the numbers are visible, so no rule
can be chosen because it favours a preferred outcome. Any later change must be
recorded here with its reason and date, making post-hoc modification visible
rather than silent.

---

## Open questions carried into later phases

Recorded so they are not quietly forgotten. **None is answered yet.** Q-1…Q-7 were
raised in Phase 0; Q-8…Q-10 were added by the Phase 1 research. Segmentation-
specific questions S-1…S-10 are in `segmentation_research.md` §10; production
questions P-1…P-5 are in `production_research.md` §7.

| # | Question | Raised by | Settles in |
| --- | --- | --- | --- |
| Q-1 | Is `Transactions.Amount` simply `Courses.CoursePrice` at purchase time? Both have exactly 23 distinct values. If they are identical, "average spending" and "average course price" are the same feature under two names, and only one belongs in the model. | Phase 0 inventory | Phase 2 |
| Q-2 | `Courses.CourseName` has 58 distinct values across 60 unique `CourseID`s — two names repeat. Are these genuinely distinct courses, or duplicates? Affects content-based similarity and the de-duplication of recommendations. | Phase 0 inventory | Phase 2 |
| Q-3 | Should `CoursePrice` and `CourseDuration` be used at all? They are in the workbook but absent from the official field list. Using them needs justification; ignoring them may discard signal. | Phase 0 transcript | Phase 2/3 |
| Q-4 | Where do the sparse-history tier boundaries fall? The mean is 3.333 courses per learner, but the mean is not the distribution. | CLAUDE.md §15 | Phase 2 |
| Q-5 | Variant A (behaviour + demographics) or Variant B (behaviour only)? Must be decided on cluster quality, stability, behavioural consistency, interpretability and feature dominance — not assumed. | CLAUDE.md §10 | Phase 3 |
| Q-6 | Is a temporal hold-out even viable? It requires enough per-learner history; at a mean of 3.333 interactions, a leave-one-out scheme may leave very little to train on, and one-interaction learners must not be evaluated as if personalised (§12). | CLAUDE.md §9, §12 | Phase 2/3 |
| Q-7 | How is "Engagement Lift (Proxy)" defined so that it is honest? The official document requires the metric but defines no formula. Whatever is used must be labelled a proxy and must not be presented as measured causal impact (§6). | Official doc, p.5 | **Answered by D-014** (definition fixed); magnitude in Phase 3 |
| Q-8 | **Is the dataset synthetic?** Zero missing values across 27 columns; 21 distinct ages in *both* Users and Teachers; 23 distinct values in *both* Amount and CoursePrice. If generated, learned cluster structure may be a generator artefact rather than real learner behaviour — a material threat to validity. | Phase 1 review of Phase 0 cardinalities | Phase 2 (EXP-006) |
| Q-9 | **Is `Transactions.TeacherID` a deterministic function of `CourseID`?** With exactly 60 teachers and 60 courses it may be a bijection — in which case every teacher-derived feature is an alias for a course-derived one and the §11 experiment is vacuous. | Phase 1 research on the teacher experiment | Phase 2 (EXP-005) |
| Q-10 | **Does the segmentation improve recommendation at all?** ADR-0005 deliberately made the cluster signal ablatable so this can be measured. If cluster-popularity does not beat global popularity, the segmentation has no demonstrated recommendation value — though it may retain standalone analytical value for the brief's learner-analysis requirement. | ADR-0005; RQ6 | Phase 3 (EXP-023 vs EXP-020) |
