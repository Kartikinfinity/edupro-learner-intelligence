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

## Phase 2 — Dataset audit (19 September 2026)

### D-019 — No cleaning step; the raw data needs none
**Status:** Settled

EXP-001 returned **0 errors**: zero nulls across 27 columns and 13,120 rows, zero
orphan foreign keys in either direction, zero duplicate keys, zero duplicate rows,
no out-of-domain values, no negative amounts, no unparseable dates.

**Decision:** the pipeline has **no cleaning stage**. A transformation that does
nothing is worse than none — it implies the data needed fixing and invites future
readers to trust a step that was never exercised.

One borderline value was examined and deliberately **left uncorrected**: `CR00028`
is typed *Paid* at a price of 0.78, the lowest non-zero price in a catalogue where
38 courses sit at exactly 0.00. It is internally consistent (Paid ⟺ price > 0), and
rounding it would alter an original value (§8).

---

### D-020 — `avg_spend` kept but documented as degenerate; `total_spend` dropped
**Status:** Settled — answers Q-1

**Evidence (EXP-002):** `Amount` equals `CoursePrice` on **all 10,000 rows**. There
is not one discount, promotion, refund or price change in a full year of data.

`avg_spend` is therefore a deterministic function of which courses a learner chose
— it is the mean price of their basket, not a spending behaviour. The brief
mandates "average spending per learner", so it is **retained and reported**, with
the redundancy stated wherever it appears.

`total_spend` is **dropped**: r = +0.84 with `total_courses`, so it adds volume
information already carried, and nothing else. `free_ratio` is preferred as the
interpretable form of the same underlying choice.

---

### D-021 — Tier boundaries are set by the data, not tuned
**Status:** Settled — answers Q-4

**Evidence (EXP-003):** the interaction distribution is bimodal with a **hard empty
band at 5–8** — not one learner in 3,000. 54.0% have exactly one interaction.

Phase 1 pre-registered a rule for deriving the moderate/rich boundary *t* from
validation performance. **That rule is not needed for this boundary**: the data
supplies it. Tiers are 1 (minimal, 54.0%) / 2–4 (moderate, 30.9%) / ≥9 (rich,
15.1%).

**Why this is better than the pre-registered rule:** a boundary drawn through an
empty region cannot be accused of being fitted to the outcome. The pre-registered
rule remains in force for any boundary the data does not hand over.

---

### D-022 — Protocol A (global temporal) confirmed as primary
**Status:** Settled by the pre-registered rule — answers Q-6

**Evidence (EXP-004):** V = 2025-09-12, T = 2025-10-18, **791 evaluable learners**
against the threshold of 300 fixed in Phase 1.

The leakage-free protocol is viable, so it is primary, exactly as pre-registered.
Leave-one-out (1,380 evaluable) is retained as the labelled leakage-bearing
secondary. The split is persisted to `data/processed/splits/` and **no experiment
re-derives it**.

**Worth noting:** 791 is above the threshold but is only 26% of the user base, so
Protocol A estimates will be noisier than the 10,000-interaction headline suggests.
That is a caveat on precision, not a reason to switch.

---

### D-023 — EXP-014 proceeds: the teacher hypothesis was wrong
**Status:** Settled — answers Q-9; reverses part of D-007's expectation

**Evidence (EXP-005):** the teacher→course mapping is **not** a bijection. There
are **887 distinct `(course, teacher)` pairs**; each course has 7–30 teachers and
each teacher 7–55 courses. Teacher assignment is not independent of course
(χ² = 31,867, p < 0.0001), and `Expertise` matches `CourseCategory` on 41.1% of
transactions against an 8.3% chance rate.

Phase 1 hypothesised a bijection, which would have made every teacher-derived
feature an alias for a course-derived one and cancelled the experiment. **That was
wrong**, and the cheap prerequisite check is what caught it — which is the argument
for gating expensive experiments on cheap ones.

The teacher dimension also turns out to hold the **only detectable behavioural
signal in the dataset** (D-024), so EXP-014 matters more than Phase 1 anticipated,
not less. Teacher features nonetheless remain **out of the core model** until the
ablation provides evidence (§11).

---

### D-024 — The central finding: no course-choice signal exists
**Status:** Settled as a finding; its consequences play out in Phase 3

**Evidence (EXP-006):** against a permutation null in which each learner's courses
are redrawn from the empirical popularity distribution with history length held
fixed (200 replicates, seed 42):

| Statistic | Observed | Null 95% CI | z |
| --- | --- | --- | --- |
| Mean distinct categories | 2.5773 | [2.571, 2.602] | −1.17 |
| Mean top-category share | 0.7210 | [0.717, 0.722] | +1.12 |
| Mean distinct levels | 1.5560 | [1.560, 1.582] | −2.65 |
| Mean free-course share | 0.6501 | [0.626, 0.654] | +1.51 |

Course popularity is near-uniform (140–196, Gini 0.042, χ² p = 0.60). Item–item
co-occurrence is *below* the null. Demographics are independent of choice (all
p > 0.2). There is no level progression (p = 0.664).

**The one real signal is instructor loyalty**: 0.688 distinct teachers per
interaction against a null of 0.944 — but it lifts next-course prediction only
**1.10×**, because each teacher covers ~15 of ~55 unseen courses.

**Consequence, stated plainly:** the most likely honest Phase 3 outcome is that **no
recommender meaningfully beats random on this dataset**. This is a property of the
data, not a failure of method. §6 requires it be reported as the headline rather
than buried, and the Phase 1 evaluation design — random baseline in every table,
coverage co-primary, pre-registered selection rules — exists precisely so this
outcome can be stated clearly.

**What is *not* concluded:** that the methods do not work, or that personalisation
is impossible in education. Neither follows. The pipeline, leakage controls and
evaluation protocol would transfer unchanged to real EduPro data.

---

### D-025 — The dataset is assessed as synthetic
**Status:** Settled as an assessment — answers Q-8

Empty band at 5–8 · exactly 5 courses in each of 12 categories · zero nulls across
13,120 rows · zero orphans in any direction · uniform popularity (p = 0.60), age
(p = 0.67), gender (p = 0.47), payment method (p = 0.40), daily volume (p = 0.18) ·
sequential gapless IDs · `Amount` ≡ `CoursePrice` all year.

Stated as an **assessment with its evidence**, not as a proven fact: no generation
metadata accompanies the workbook.

**Consequence:** segment descriptions must be phrased as descriptions of *this
dataset*, not of learner psychology. Registered as threat V8; must appear in the
research paper's limitations. It is also why the gap statistic and per-cluster
stability added in Phase 1 (D-017) became essential — they are the instruments that
can report "no real structure" if that is the answer.

Instructively, **`Teachers.Expertise` is not uniform** and teacher reuse is strongly
non-random: whoever generated this data modelled the teacher dimension with
structure and the course-choice dimension without it.

---

### D-026 — Level-progression feature rejected on measurement
**Status:** Settled

Phase 1 listed "level progression" as a defensible additional feature candidate.
**Measured:** within-learner level slope over time is +0.0053, t = 0.435,
**p = 0.664** across 735 eligible learners; mean first-course level 0.988 vs mean
last-course level 0.980.

**Decision:** rejected. Learners do not progress from beginner to advanced in this
data, so the feature would encode noise. Recorded here rather than silently omitted
— it was proposed, tested, and failed.

---

## Phase 3A — Segmentation experiments (19 September 2026)

### D-027 — Segmentation configuration frozen for Phase 3B
**Status:** Settled; reversible if EXP-023 contradicts it

Variant B (behaviour only) · 12-dim category share vector · ordinal level one-hot ·
StandardScaler · no block weighting · no demographics · no teacher block ·
K-Means · **k = 4**.

**Evidence:** silhouette 0.1946; every cluster bootstrap Jaccard >=0.981;
subsample ARI 0.987; seed ARI 1.000; smallest cluster 19.7%; full-history
sensitivity ARI 0.847. Ten representations and nine k values were compared, and
every losing arm is reported.

**Reversal:** if Phase 3B's EXP-023 shows cluster-popularity recommendation does
not beat global popularity, the segmentation has no demonstrated *recommendation*
value. It would retain standalone analytical value for the brief's learner-analysis
requirement, and that distinction must be drawn carefully rather than blurred.

---

### D-028 — StandardScaler, because RobustScaler is degenerate here
**Status:** Settled — answers the D5 choice deferred in Phase 1

**Evidence:** `avg_courses_per_category` and `diversity_ratio` have an
**interquartile range of exactly zero** — 54% of learners have a single course, so
their 25th, 50th and 75th percentiles all equal 1.0. RobustScaler leaves those
columns unscaled while compressing the others, manufacturing a separable axis. Its
silhouette of **0.716** is three times any other arm, and the k=2 split it produces
(2,198/452) is a rediscovery of the Phase 2 activity bimodality through a scaling
bug.

**Why this is recorded prominently:** the highest-scoring arm in the entire
experiment was an artefact. Accepting it would have been a textbook case of
optimising for the number instead of the structure (§6).

---

### D-029 — Variant B: demographics are invisible, not merely secondary
**Status:** Settled — answers Q-5 and CLAUDE.md §10

**Evidence:** **ARI between Variant A and Variant B = 1.000** — the partitions are
identical. The demographic block explains **0.04%** of between-cluster variance,
against a pre-registered "secondary" band of <20%. Variant A's silhouette is
*lower* (0.1729 vs 0.1946), the cost of two uninformative dimensions.

**Decision:** Variant B. The pre-registered tie rule prefers the simpler, more
privacy-respecting, more actionable model — and this is not even a tie.

Age and gender are retained as **evaluation strata** for Phase 3B (EXP-027) [R30].
Auditing with a protected attribute is not the same as modelling with it.

---

### D-030 — Teacher features rejected for segmentation, scope stated
**Status:** Settled — answers CLAUDE.md §11 for segmentation

**Evidence:** +0.0009 silhouette (0.1946 → 0.1955), ARI 0.990, mean bootstrap
Jaccard slightly *worse* (0.999 → 0.989). The teacher block takes 16.1% of
between-cluster variance and `teacher_loyalty` becomes the top single feature — but
it correlates **+0.963** with `total_courses` (Phase 2) and is zero by construction
for the 54% of learners with one course. Its eta-squared reflects that correlation,
not new information.

**Scope:** this rejects teacher features for *grouping learners*. Phase 2
established instructor loyalty as the only genuine behavioural signal in the
dataset (0.688 distinct teachers per interaction vs a 0.944 null), and it remains a
live candidate for the Phase 3B **recommender**, where predicting the next course
is a different problem.

---

### D-031 — The segmentation is a course-level split, and is described as one
**Status:** Settled as a finding

**Evidence:** three of four clusters are **100% one course level**. The level
ablation (EXP-011g) removes `preferred_level` and produces an almost entirely
different partition (**ARI 0.253**), with mean bootstrap Jaccard falling from 0.999
to 0.656 and one cluster becoming unstable.

**What follows:** the partition is stable, balanced and interpretable — but it is
*course depth plus activity volume*, not a set of motivational personas. For the
~80% of learners in clusters 0, 2 and 3 (1.25-1.51 courses each), "preferred level"
is the level of a single enrollment, and Phase 2 found level choice statistically
indistinguishable from chance.

**Consequence for the deliverables:** segment descriptions in the dashboard,
research paper and executive summary must say this plainly. `research/cluster_profiles.md`
carries the wording, and the limitation travels with the profiles wherever they go.

---

### D-032 — Two Phase 1 predictions recorded as wrong
**Status:** Settled — recorded rather than quietly dropped

1. **One-hot dominance.** Phase 1 identified one-hot encoding of
   `preferred_category` as the project's largest methodological risk. Measured at
   the common selected k=4, the category block takes **5.0%** (proportion) and
   **3.7%** (one-hot) of between-cluster variance. Neither dominates; one-hot is
   marginally lower. The mechanism *is* real at k>=9 (46-58%), so the reasoning was
   sound — it simply does not apply at the k the stability constraint selects.

2. **The gap statistic as a falsification instrument.** Added in Phase 1 (D-017)
   precisely because it is the only criterion that can report "no structure". On
   this data it rises monotonically to k=20 and returns no verdict. **The project
   therefore has no instrument capable of falsifying cluster structure** — a real
   limitation, and the more important of the two corrections.

---

## Phase 3B — Recommendation experiments (19 September 2026)

### D-033 — The headline finding: no method beats random
**Status:** Settled as a finding

**Evidence:** paired bootstrap of per-learner NDCG@10 differences against random,
2,000 resamples, on 791 evaluable learners under the leakage-free temporal split.
**All eleven 95% intervals contain zero**, in aggregate and within every history
tier (minimal, moderate, rich). Random ranks **7th of 12** on the test window, and
global popularity is **worse** than random (0.1072 vs 0.1102).

**Why this was foreseeable and still had to be measured:** Phase 2 established
that course choice is statistically indistinguishable from popularity-weighted
chance, that popularity is near-uniform (Gini 0.042), and that demographics are
independent of choice. A recommender cannot find structure that is not there.

**What is NOT concluded:** that the methods are wrong, the pipeline is broken, or
personalisation is impossible in education. Every component is unit-tested and
would transfer unchanged to real EduPro data. The limitation is the dataset, which
Phase 2 assessed as almost certainly synthetic (D-025).

**Consequence:** this is the project's headline result. §6 requires it be reported
as such rather than buried behind a favourable-looking metric, and the Phase 1
evaluation design — random baseline in every table, coverage co-primary,
pre-registered rules, a paired significance test — exists precisely so it could be
stated plainly.

---

### D-034 — `cluster_popularity` selected by the parsimony tiebreak
**Status:** Settled by the pre-registered rule

The hybrid led validation NDCG@10 at 0.1148 against `cluster_popularity`'s 0.1098
— a margin of **0.0051**, inside the **0.01** parsimony margin fixed in Phase 1
(D-018). The rule therefore selects the simpler method.

**Why the rule is right here:** a six-signal hybrid that adds 0.005 NDCG carries
real maintenance and explanation cost for a gain that the significance test shows
is indistinguishable from zero. Phase 1's pre-registered expectation P-3 predicted
this outcome exactly.

**Reversal:** none needed on this data. On data with real signal the margin could
exceed 0.01 and the rule would select the hybrid.

---

### D-035 — Recommend the tiered recommender for deployment, despite ranking lower
**Status:** Recommendation to Phase 4, not a reversal of D-034

| | cluster_popularity | tiered |
| --- | --- | --- |
| Test NDCG@10 | 0.1138 | 0.1117 |
| Catalogue coverage | 0.75 | **1.00** |
| Zero-history handling | global fallback | **explicit tier, labelled as such** |
| Explanation faithfulness | popularity only | **routes by the signal actually used** |

The 0.0021 accuracy difference is far inside the noise band established in D-033.
**Where accuracy cannot distinguish two options, coverage, transparency and honest
cold-start handling should** — and those are what §15 and §16 actually require.
`cluster_popularity` leaves 15 of 60 courses permanently unrecommended for no
accuracy gain.

The pre-registered selection stands; this is a separate, documented deployment
decision for Phase 4 to confirm.

---

### D-036 — Q-10 answered: the segmentation has not demonstrated recommendation value
**Status:** Settled — answers Q-10

**Evidence (EXP-023):** `cluster_popularity` beats `global_popularity` by +0.0066
NDCG@10 on test, but beats random by only +0.0036 with a CI of [-0.0092, +0.0271].

**Interpretation:** recommending within segment is better than recommending
globally popular courses — but global popularity is itself worse than random here,
so that is a low bar and not evidence of value.

ADR-0005 deliberately made the cluster signal ablatable so this question could be
answered rather than assumed. The segmentation retains **standalone analytical
value** for the brief's learner-analysis requirement; that distinction must be
drawn carefully in the research paper rather than blurred.

---

### D-037 — Four Phase 1 predictions recorded as wrong
**Status:** Settled — recorded rather than dropped

1. **P-1 (popularity hard to beat)** — refuted as stated. Global popularity is
   *worse* than random on the test window.
2. **P-2 (item-based CF strongest single personalised method)** — refuted. 8th of
   12 on test; content-based led the baselines.
3. **User-user over profile features would beat the raw-history arm** — refuted on
   both splits (0.0944 vs 0.1065 validation; 0.1105 vs 0.0947 test, i.e. the
   ordering even reverses between splits, which is itself a noise signature).
4. **Item-based CF better-conditioned than user-based** — not borne out.

Two predictions were confirmed: **P-3** (hybrid wins narrowly and loses the
tiebreak) exactly, and **P-7** (coverage separates methods more than accuracy) —
accuracy spans 1.3x, coverage 3.3x.

---

### D-038 — The Engagement Lift proxy is reported with random's own lift beside it
**Status:** Settled

The selected method scores a proxy lift of **1.084**. **Random scores 1.046 on the
same measure.**

Reporting 1.084 alone would invite the reading "8% better engagement". Printing
random's 1.046 next to it makes the interpretation unavoidable: the measure is an
offline agreement ratio against a weak incumbent, not an effect size. This
operationalises the guard rails fixed in D-014 and is why no statement of the form
"this system would increase engagement by X%" appears anywhere in the project.

---

### D-039 — The gender gap is reported and bounded, not called discrimination
**Status:** Settled as an observation requiring monitoring

**Evidence:** female NDCG@10 0.1002 vs male 0.1285; gap **-0.0283**, CI
[-0.0543, -0.0010], consistent in direction across all three tiers.

**Reported**, because [R30] is explicit that aggregate numbers hide group
differences and because not looking is a weaker position than looking.

**Bounded**, because: no demographic feature enters any model; Phase 2 found gender
independent of course choice (p = 0.643); the interval barely excludes zero and is
**uncorrected for four strata tests**; and no method beats random at all, so this
is a disparity in chance-level performance.

**Decision:** monitor on real data. Not a finding of discrimination.

---

## Phase 4 — Model selection and architecture freeze (19 September 2026)

### D-040 — The frozen architecture is the tiered router, not the flat scorer
**Status:** Settled by measurement (EXP-028). Reconciles D-034 and D-035.

Phase 3B left a genuine tension. The pre-registered parsimony rule selected
`cluster_popularity` as the best *method* (D-034); the coverage evidence
recommended the *tiered* recommender for deployment (D-035). Neither decision was
wrong, because they answer different questions — but an architecture cannot be
frozen on an unresolved tension, and **no Phase 3B row measured the assembly that
would actually be deployed**.

So it was measured. Three candidates, validation window, 511 evaluable learners:

| Architecture | NDCG@10 | HR@10 | Coverage | Gini |
| --- | --- | --- | --- | --- |
| A — flat `cluster_popularity` | 0.1098 | 0.3033 | 0.78 | 0.606 |
| B — tiered, hybrid core | 0.1135 | 0.3327 | **1.00** | 0.608 |
| **C — tiered, `cluster_popularity` core** | 0.1104 | 0.3053 | **1.00** | **0.581** |

**C dominates A**: +0.0006 NDCG (noise), **+0.22 coverage**, lower concentration,
and a labelled cold-start route instead of an implicit one. B is +0.0031 over C but
re-introduces the six-signal hybrid the parsimony rule rejected — and its margin is
smaller than the margin that rule already judged too small to pay for.

**Resolution:** the tiering is not a competing *method*; it is the *routing* around
the selected method. D-034 chose the core, D-035 chose the shell, and C is both.
None of the three differences is statistically significant against random.

---

### D-041 — The cold-start fallback is diversified, because the naive reading failed §15
**Status:** Settled by measurement (EXP-029)

CLAUDE.md §15 specifies "popularity/rating/diversity fallback" for learners with
insufficient history. The obvious implementation — blend popularity and rating —
was built first, and **measured to fail the diversity third of that requirement**:
it showed a cold-start learner **7 of 12 categories**, fewer than plain popularity's
8, because the two signals concentrate on the same courses.

`DiversifiedFallback` keeps the same quality blend but re-ranks it round-robin
across categories:

| Fallback | Distinct categories in top 10 | Largest category share |
| --- | --- | --- |
| global_popularity | 8 | 0.30 |
| rating | 8 | 0.20 |
| popularity + rating blend | 7 | 0.20 |
| **DiversifiedFallback** | **10** | **0.10** |

**Why the accuracy cost is acceptable:** for a learner with no history there is no
preference to exploit, so breadth is the useful offer — and Phase 2 established
that on this data there is no ranking signal to sacrifice in the first place.
Three tests now guard the property.

---

### D-042 — A measurement was discarded for being meaningless, not for being inconvenient
**Status:** Recorded as a method correction

The first attempt to compare cold-start fallbacks used cross-user catalogue
coverage. It returned **0.17 for all three candidates**. That is not a tie: learners
with zero history are indistinguishable, so every deterministic ranker hands all of
them the *same* list, fixing cross-user coverage at K/60 ≈ 0.17 by construction.
The metric could not vary and therefore measured nothing.

It was replaced with within-list category spread, which does vary (7 to 10
categories) and is the property §15 actually names. Recorded because a metric that
returns identical numbers for every candidate is easy to read as "no difference"
rather than "wrong instrument".

---

### D-043 — Validation, not test: the architecture comparison spends no new test budget
**Status:** Settled by the Phase 1 pre-registration

EXP-028 and EXP-029 run on the **validation** window only. The test window was
opened once in Phase 3B, as pre-registered (D-018, L6), and re-opening it to
compare three architectures would convert a held-out estimate into a selection
surface — the exact failure the single-use rule exists to prevent.

The consequence is stated rather than hidden: the frozen architecture's *assembled*
metrics are validation-window estimates. Its *components* carry Phase 3B test
metrics, which remain the best out-of-sample evidence available and are quoted as
such throughout `ARCHITECTURE_FREEZE.md`.

---

### D-044 — The methodology is frozen
**Status:** Freeze in force from 19 September 2026

`edupro-1.0.0` is frozen: representation `B_proportion`, StandardScaler, K-Means
k=4, tiered router with `DiversifiedFallback` / `ContentBased` / `ClusterPopularity`,
explanations from score decomposition, Protocol A evaluation.

**Reopening requires all four of:** a decision-log entry naming the change and its
evidence; new experimental evidence (not a preference or a better-looking number); a
recorded impact assessment across every affected layer — re-fitting the clustering
invalidates the cluster-popularity inputs and any hybrid weights tuned against them;
and a full test-suite re-run.

**What would legitimately reopen it:** real, non-synthetic EduPro data. That would
invalidate none of the methodology and all of the findings.

---

## Phase 5A — Production ML implementation (19 September 2026)

### D-045 — The deployed model is fitted on the full history; the reported metrics are not
**Status:** Settled; recorded in the manifest so the two can never be conflated

Model *selection* used the Protocol A temporal split so that every reported metric
is out-of-sample. The *deployed* artifact set is fitted on all 10,000 interactions.
That is standard practice after selection, and it is what a platform serving live
learners would do: there is nothing to hold out at serving time, and discarding the
most recent two months of behaviour would make recommendations worse for no benefit.

The risk is that someone later reads the artifact set's segment sizes as if they
were the evaluated model's. They are not identical:

| | Fit window (evaluated) | Full history (deployed) |
| --- | --- | --- |
| Learners | 2,650 | 3,000 |
| Segment sizes | 715 / 522 / 881 / 532 | 841 / 1,030 / 607 / 522 |
| Smallest segment | 19.7% | 17.4% |
| Mean bootstrap Jaccard | 0.9892 | 0.9805 |

**The four segment names are identical** — Beginner-level single-course,
Category-repeating high-volume, Advanced-level non-repeating, Intermediate-level
single-session — which is the useful evidence here: the structure is the same
structure, found again on 350 more learners. Cluster *numbering* differs, because
K-Means labels are arbitrary.

**Mitigation:** `manifest.json` records `training.window = "full history"` and a
note pointing at the temporal-split provenance of the reported metrics. A test
asserts both are present.

---

### D-046 — Load what was learned; recompute what is merely counted
**Status:** Settled

CLAUDE.md §21 forbids retraining the model at application start. The serving path
loads the fitted scaler and the fitted K-Means from disk and never refits them.

It does rebuild the *counting* structures — per-segment enrollment counts, learner
content profiles, the category round-robin order — from the persisted tables at
load time. Measured cost: **0.41 s**, once per process, behind
`st.cache_resource`.

**Why not persist those too.** A serving path that reads precomputed arrays needs a
second implementation of the scoring logic, which can drift from the evaluated one.
An explanation generated from a drifted scorer is precisely the failure §16 exists
to prevent. Here the code that produced the reported metrics is the code that
serves, and the redundantly persisted `popularity.parquet` is compared against the
recomputed counts by test — so a drift fails loudly instead of silently.

---

### D-047 — The frozen artifact set is committed to the repository
**Status:** Settled; resolves open item P-2

Streamlit Community Cloud deploys from the repository and cannot run the training
pipeline, so an untracked artifact set means no deployed application. The whole set
is **276 KB** (60×60 content matrix, a few thousand-row tables), which is not a
reason to reach for Git LFS.

The `.gitignore` rule for `models/` is relaxed to five named files rather than
un-ignoring the directory, so a stray experiment written into `models/` is still
ignored by default.

---

### D-048 — The tier frame is stated once per list, the caveat once per list
**Status:** Settled after seeing the rendered output

The first implementation prefixed every recommendation with its tier frame ("You
are new here, so these are broad..."), which made a ten-item list repeat the same
clause ten times. The frame is a property of the *list*, not of each course, so it
moved to `Explanation.tier_frame` and is rendered once; `full_sentence` recombines
them when an explanation is shown alone.

The measured-quality caveat is on `RecommendationResult`, not on each item, for the
same reason. It is never omitted: a quality figure shown without the random
reference would mislead (§6, D-035).

---

### D-049 — On the full history no existing learner is in the cold-start tier
**Status:** Recorded as a finding with a consequence for Phase 5B

All 3,000 learners have at least one interaction, so the full-history tier
distribution is **minimal 1,620 / moderate 926 / rich 454 / insufficient 0**. The
`insufficient` route is not dead code — it serves genuinely *new* learners, and the
service reaches it by design when an identifier is absent from the artifact set,
flagging `is_known_learner = False` rather than silently inventing a profile.

**Consequence for the dashboard:** the cold-start experience cannot be demonstrated
by picking an existing learner. Phase 5B must expose a "new learner" path
explicitly, or the diversified fallback — the route chosen on measured evidence in
EXP-029 — will never be visible to a reviewer.

---

## Phase 5B — Streamlit application (19 September 2026)

### D-050 — A 2D projection is persisted as a display artifact; the freeze is untouched
**Status:** Settled; explicitly **not** a reopening of the architecture freeze

The cluster-visualisation page needs 2D coordinates. Three options were available
and two were rejected:

- **Fit a projection in the app.** Rejected: the application must fit nothing
  (§21), and a stochastic projection refitted per session would move the points
  between page loads, which looks like instability in the *model* to anyone who
  did not know the projection was being recomputed.
- **t-SNE or UMAP.** Rejected: both produce a more separated-looking picture, and
  on a segmentation whose silhouette is weak that is precisely the wrong property
  — it would flatter the result. Neither preserves distance, so a viewer's natural
  reading of the plot would be wrong.
- **PCA, precomputed by the training pipeline.** Adopted. Deterministic,
  distance-preserving in the directions it keeps, and it reports how much variance
  it retained: **30.7% of 25 dimensions**, which the page states before the chart.

**This does not reopen the freeze** (D-044). The projection is written by the
pipeline and read by one page; no scorer, no clusterer and no metric consumes it.
It changes no model behaviour, which is the test D-044 sets.

---

### D-051 — Every figure is labelled by what kind of thing it is
**Status:** Settled

A dashboard mixes three kinds of number that carry very different weight, and a
stakeholder cannot tell them apart unless the dashboard says so. Each section
carries a badge:

| Label | Meaning |
| --- | --- |
| **Observed data** | Counted from the source workbook |
| **Model output** | Produced by the segmentation or the recommender |
| **Proxy metric — not a causal measurement** | Engagement Lift, which the brief names but does not define |

Two rules are enforced in `app/lib/shell.py` rather than left to each page:

**A quality metric never renders without its reference.**
`metric_against_reference` takes the baseline as a required argument, so the
comparison is the default rendering and omitting it takes deliberate effort. On a
60-course catalogue a ranker that has learned nothing still posts a Hit Rate near
0.35; "Hit Rate 36%" alone reads as success.

**The engagement proxy cannot be read without random's own value.**
`reporting.engagement_lift_proxy()` returns both numbers in one dict, so a caller
cannot take the flattering figure and leave the reference behind.

---

### D-052 — The dashboard reproduces the frozen document, and a test enforces it
**Status:** Settled after the representation table disagreed with the freeze

The Model Analytics page shows each feature representation at "its own best k".
The first implementation read that as the raw silhouette maximum and produced a
table that **contradicted `ARCHITECTURE_FREEZE.md`** — `B_proportion` appeared at
k = 10 with silhouette 0.269 rather than at k = 4 with 0.195.

Both numbers are real; they answer different questions. The unconstrained maximum
ranks arms by how far they were allowed to fragment, and at k = 10 half of
`B_proportion`'s clusters fail to reappear under resampling. The frozen table
applies the pre-registered size constraint, which is the rule the project actually
committed to.

The dashboard now applies that rule and reproduces all ten rows of the frozen
table exactly. A test asserts it, so the dashboard and the research report cannot
drift apart silently — which is the failure mode this catches: a reviewer opening
both and finding different numbers for the same quantity.

---

### D-053 — Navigation is declared explicitly, and the cold-start route is reachable
**Status:** Settled

Streamlit's filename-based navigation labelled the entry page "streamlit app".
Pages are now declared with `st.navigation`, so they carry the names a stakeholder
should see. Each page also still runs standalone, which is how the tests exercise
them — `shell.configure` tolerates the repeat `set_page_config` call that implies.

The Recommendations page carries an explicit **"New learner (cold start)"** mode.
This is not a convenience: on the full history every one of the 3,000 learners has
at least one enrollment (D-049), so without it the diversified fallback — the route
selected on measured evidence in EXP-029 — would be unreachable in the application
and invisible to a reviewer.

---

## Phase 6A — Adversarial validation (19 September 2026)

### D-054 — A validator must never raise; it must report
**Status:** Settled by a critical defect found under attack

The Phase 6A audit's *first* corruption probe — dropping a column — crashed the
validator. Four cross-sheet checks indexed columns without checking they existed,
so a missing column raised `KeyError` from inside `validate_transactions` and the
run died before returning the report that named the problem.

**Why this is worse than it looks.** The sheet-level pass had *already* recorded
`columns_missing` as an error. The verdict existed; the crash destroyed it. A
caller feeding the pipeline a malformed file got an opaque `KeyError` that looks
like a bug in the loader, and the pipeline's "refuse to train on invalid data"
guard never ran — so the most basic corruption defeated both the validator and the
protection built on top of it.

**Rule adopted:** a validation function reports; it does not raise on the input it
is validating. Cross-sheet checks now guard on the columns they need and record an
informational skip, because the error that matters has already been recorded.

**Guarded by** 8 regression tests over 6 column/sheet combinations, a
multi-column case, and the pipeline-refusal path.

---

### D-055 — An error message must name its own cause
**Status:** Settled

A learner who had taken all 60 courses was told: *"No candidate courses remain
after filtering (category=None, level=None) and excluding 0 already-enrolled
courses."* Two things wrong: it blamed a filter that was never applied, and it
counted from the history table rather than from the exclusion set the scorer used.

**Why it matters more than its size suggests.** A wrong diagnosis is worse than a
generic one. "No candidates after filtering" sends whoever reads it to look at the
filters, which are fine. The message now distinguishes catalogue exhaustion,
over-narrow filters and an empty unseen set, and counts from the structure that
produced the result.

**Guarded by** 2 regression tests, one asserting the message must *not* mention a
filter that was not applied.

---

### D-056 — One declared dtype for cluster labels
**Status:** Settled

`assign_segment(...).equals(features["cluster"])` was `False` while
`(... == ...).all()` was `True`. The pipeline persisted scikit-learn's
platform-dependent label dtype (`int32` here); inference returned platform `int`.

Nothing was wrong with the labels. What was wrong is that **the obvious way to ask
"does inference reproduce training?" gave the wrong answer** — and any future
comparison, merge or artifact check written the obvious way would have failed
silently. `CLUSTER_DTYPE = "int64"` is now declared once and applied in both
places.

**Guarded by** 2 regression tests, one requiring the strict comparison to hold.

---

### D-057 — An audit records its own mistakes
**Status:** Methodological rule adopted in Phase 6A

Five of the audit's initial "failures" were the harness's fault, not the system's:
a probe expecting the wrong check name; a probe treating a correct refusal as a
weakness; a probe using a dtype-strict comparison to ask a value question; a probe
reading the wrong element type; and a probe defeated by `st.cache_resource`
serving it a warm model.

All five are recorded in `research/final_validation_report.md` rather than quietly
deleted. An audit that files its own bugs as system defects inflates its findings;
one that deletes them hides how much of its coverage was illusory. The third case
is the instructive one — a probe that was wrong about *what it was testing* still
surfaced a real inconsistency underneath (D-056).

**Rule:** a probe that cannot fail proves nothing, and a probe that fails for its
own reasons is reported as such.

---

## Phase 6B — Research paper (19 September 2026)

### D-058 — The paper's traceability is machine-checked, not asserted
**Status:** Settled

"Every result is traceable to an artifact" is a claim a paper can make about
itself and get wrong in a dozen quiet ways: a number copied from an earlier run, a
figure cited that was never generated, a reference keyed to nothing.

Three instruments make it checkable instead:

1. **`scripts/verify_paper_claims.py`** reads 77 values *out of the artifacts*,
   formats each the way the paper prints it, and requires that string to appear in
   the text. The checks read the artifact first and the paper second, so a wrong
   number cannot make its own check pass.
2. **`tests/test_paper.py`** verifies every cited figure file exists, every cited
   reference is listed with an identifier, and all 25 required sections are present.
3. **The Markdown is the source of truth**; the HTML submission copy is generated
   from it by `scripts/build_paper.py`. A separately edited "final" copy is how a
   paper and its data drift apart.

---

### D-059 — Unsupported claims are prevented by pattern, not by care
**Status:** Settled

The brief forbids claims like "engagement increased by X%" when no engagement
measure exists. **A numeric check cannot catch this**, because the violation is a
sentence rather than a number — and the sentence is easy to write by accident when
the artifact says "impact proxy 1.084".

Nine forbidden claim shapes are therefore tested for directly: causal engagement
and retention claims, percentage attributions, and assertions of statistical
significance that the confidence intervals do not support. Two pairing rules are
also enforced: the impact proxy may not appear on a line without random's own
value (1.046), and the deployed method's NDCG may not be quoted in prose without
the random reference.

**The patterns were verified able to fail** against six synthetic violating
sentences, all caught, with a correctly-phrased sentence not flagged. The Phase 6A
rule applies to documentation checks too: a probe that cannot fail proves nothing.

---

### D-060 — A mixed-provenance table found while rebuilding it from the artifact
**Status:** Corrected in `ARCHITECTURE_FREEZE.md`

Assembling the paper's results table from the artifacts revealed that the Gini
column of the Phase 4 recommendation decision matrix carried **validation**-window
values while every other column in the same table came from the **test** window.

No decision changes — Gini was never a selection criterion and the ordering is
materially the same — but a table whose columns come from different evaluation
windows is wrong whether or not it changed an outcome. It is corrected to
test-window values with the correction recorded in place.

**This is the third document-level inconsistency the late phases have caught**,
after the stale prediction table (Phase 4) and the representation table (Phase 5B).
All three were found by **rebuilding a table from its artifact rather than copying
it forward**, which is the practice worth generalising: any table that appears in
two documents should be generated from the artifact in both, or generated once and
referenced.

---

## Open questions carried into later phases

Recorded so they are not quietly forgotten. **None is answered yet.** Q-1…Q-7 were
raised in Phase 0; Q-8…Q-10 were added by the Phase 1 research. Segmentation-
specific questions S-1…S-10 are in `segmentation_research.md` §10; production
questions P-1…P-5 are in `production_research.md` §7.

| # | Question | Raised by | Settles in |
| --- | --- | --- | --- |
| Q-1 | Is `Transactions.Amount` simply `Courses.CoursePrice` at purchase time? Both have exactly 23 distinct values. If they are identical, "average spending" and "average course price" are the same feature under two names, and only one belongs in the model. | Phase 0 inventory | **ANSWERED (D-020)** — identical on all 10,000 rows |
| Q-2 | `Courses.CourseName` has 58 distinct values across 60 unique `CourseID`s — two names repeat. Are these genuinely distinct courses, or duplicates? Affects content-based similarity and the de-duplication of recommendations. | Phase 0 inventory | **ANSWERED** — 2 repeated names, distinct courses; no de-duplication |
| Q-3 | Should `CoursePrice` and `CourseDuration` be used at all? They are in the workbook but absent from the official field list. Using them needs justification; ignoring them may discard signal. | Phase 0 transcript | **ANSWERED** — price enters via `free_ratio`; duration kept as a content attribute only |
| Q-4 | Where do the sparse-history tier boundaries fall? The mean is 3.333 courses per learner, but the mean is not the distribution. | CLAUDE.md §15 | **ANSWERED (D-021)** — 1 / 2–4 / ≥9, handed over by the empty band |
| Q-5 | Variant A (behaviour + demographics) or Variant B (behaviour only)? Must be decided on cluster quality, stability, behavioural consistency, interpretability and feature dominance — not assumed. | CLAUDE.md §10 | **ANSWERED (D-029)** — ARI 1.000 between variants; demographic share 0.0004. Variant B |
| Q-6 | Is a temporal hold-out even viable? It requires enough per-learner history; at a mean of 3.333 interactions, a leave-one-out scheme may leave very little to train on, and one-interaction learners must not be evaluated as if personalised (§12). | CLAUDE.md §9, §12 | **ANSWERED (D-022)** — viable; Protocol A primary, 791 evaluable |
| Q-7 | How is "Engagement Lift (Proxy)" defined so that it is honest? The official document requires the metric but defines no formula. Whatever is used must be labelled a proxy and must not be presented as measured causal impact (§6). | Official doc, p.5 | **ANSWERED (D-014, D-038)** — definition fixed in Phase 1; magnitude 1.084 against random's own 1.046, reported side by side |
| Q-8 | **Is the dataset synthetic?** Zero missing values across 27 columns; 21 distinct ages in *both* Users and Teachers; 23 distinct values in *both* Amount and CoursePrice. If generated, learned cluster structure may be a generator artefact rather than real learner behaviour — a material threat to validity. | Phase 1 review of Phase 0 cardinalities | **ANSWERED (D-025)** — almost certainly synthetic |
| Q-9 | **Is `Transactions.TeacherID` a deterministic function of `CourseID`?** With exactly 60 teachers and 60 courses it may be a bijection — in which case every teacher-derived feature is an alias for a course-derived one and the §11 experiment is vacuous. | Phase 1 research on the teacher experiment | **ANSWERED (D-023)** — not a bijection; EXP-014 proceeds |
| Q-10 | **Does the segmentation improve recommendation at all?** | ADR-0005; RQ6 | **ANSWERED (D-036)** — it beats global popularity (+0.0066) but not random (+0.0036, CI contains zero). No demonstrated recommendation value |
