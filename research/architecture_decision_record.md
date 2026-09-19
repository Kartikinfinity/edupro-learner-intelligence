# Architecture Decision Record

Durable architectural decisions, in ADR format. An ADR is written when a choice
is **hard to reverse** or **constrains later phases**. Lighter, tactical
decisions go in `research/decision_log.md`.

**Status values:** `Proposed` · `Accepted` · `Superseded by ADR-XXXX` · `Deprecated`

---

## ADR-0001 — Modular `src/` package, with notebooks excluded from the runtime path

**Status:** Accepted (Phase 0)

### Context
CLAUDE.md §18 requires the production system to have modular source code with
clear separation between ingestion, validation, feature engineering,
segmentation, recommendation, evaluation, explainability and application. §19
permits notebooks for exploration but forbids them from being the only
implementation. §21 forbids the Streamlit app from retraining on startup.

A notebook-centric project is the default failure mode for this kind of work:
logic ends up duplicated between a notebook and an app, they drift, and the
reported results stop matching what the app actually does.

### Decision
All reusable logic lives in the `edupro` package under `src/`, installed in
editable mode. One subpackage per pipeline stage, each with a module docstring
stating its responsibility:

```
edupro.config           paths, sheet names, seed, PII column list
edupro.data             ingestion + schema validation
edupro.features         learner-level aggregation + feature engineering
edupro.segmentation     clustering, selection, profiling
edupro.recommendation   candidate generation, scoring, ranking, tiering
edupro.evaluation       segmentation + recommendation metrics
edupro.explainability   human-readable justifications
```

Notebooks and the Streamlit app are **consumers** of this package. Neither may
define modelling logic. The app loads persisted artifacts and never fits a model.

### Consequences
- Anything reported in the research paper is produced by the same code the app
  runs, so the two cannot disagree.
- Every stage is unit-testable in isolation (§23).
- Costs a small amount of ceremony early; pays for itself by removing the
  notebook-to-app port that would otherwise land near the deadline.

### Alternatives rejected
- **Notebook-first, extract later.** The extraction reliably slips, and the
  extracted code is then untested at the point it matters most.
- **Flat module layout.** Cheaper now, but it lets leakage-sensitive feature code
  and evaluation code sit side by side with nothing marking the boundary.

---

## ADR-0002 — Target Python 3.13; do not use the system-default 3.14

**Status:** Accepted (Phase 0)

### Context
Four interpreters are installed: 3.14.0 (system default), 3.13.9, 3.12.0, 3.11.0.
The full scientific stack installs and passes a modelling smoke test on 3.14, so
it was viable on technical grounds.

CLAUDE.md §20 prohibits Docker, and §21 requires the application to be
public-deployment ready. Together these point at Streamlit Community Cloud as the
deployment target.

> **Correction (Phase 1).** This ADR originally justified the choice by asserting
> that Streamlit Community Cloud "supports Python 3.9–3.13". That claim was
> written from prior knowledge and **was not verified against the documentation**.
> On checking in Phase 1, the documented policy is different: Community Cloud
> "supports all released versions of Python that are still receiving security
> updates" and "defaults to version 3.12" [R37b]. Under that policy Python 3.14
> would in fact be permitted. The original rationale is therefore withdrawn. The
> decision below is retained on the corrected rationale, which is weaker but
> accurate.

### Decision
Pin the project to `>=3.11,<3.14` and build `.venv` on **3.13.9**. Enforced by
`requires-python` in `pyproject.toml` and asserted by
`test_python_version_is_within_supported_range`.

### Rationale (corrected)
1. **The platform default is 3.12.** The default is the best-trodden path on any
   hosting platform. 3.13 is one minor version above it — comfortably inside the
   documented policy, and not the frontier.
2. **The support policy is a moving target, not a fixed list.** "Still receiving
   security updates" means the supported set changes over time without the
   project being consulted. The documentation warns that an app on a version that
   becomes unsupported may be forcibly upgraded and may break. A version near the
   platform default is the least exposed to that.
3. **Newest-interpreter risk is real and asymmetric.** On a just-released
   interpreter, some dependency in a 130-package tree may lack a wheel or ship a
   less-exercised build. The upside of 3.14 is zero here — the project uses no
   3.14-only feature — so any risk at all is a bad trade.

### Consequences
- The project forgoes 3.14-only features. It uses none.
- The cap must be revisited if a dependency ever requires 3.14+, or if Community
  Cloud's default moves past 3.13.

### Alternatives rejected
- **Target 3.14 (the system default).** Permitted under the documented policy,
  but furthest from the platform default with no compensating benefit.
- **Target 3.11 for maximum compatibility.** Unnecessarily old, and closer to
  falling out of the security-update window that defines platform support.

### Note on process
The original version of this ADR reached the right decision via a false premise.
That is worth recording rather than quietly overwriting: an unverified claim that
happens to support a sound conclusion is still an unverified claim, and it was
found only because Phase 1 set out to attach a citation to it.

---

## ADR-0003 — `data/raw/` is immutable, enforced by checksum in the test suite

**Status:** Accepted (Phase 0)

### Context
CLAUDE.md §8 requires the raw dataset to remain immutable and forbids silent
alteration of IDs, original values, transaction amounts, dates and categorical
labels. A convention alone does not prevent an accidental in-place write from a
notebook or a mis-scoped script.

### Decision
1. `data/raw/` holds byte-identical copies of the authoritative sources.
2. Their SHA-256 digests are recorded as constants in `edupro.config`.
3. `tests/test_phase0_environment.py` verifies both digests on every run.
4. Every pipeline stage writes to `data/interim/` or `data/processed/`, never to
   `data/raw/`.
5. Read-only tooling (`scripts/inspect_sources.py`, `scripts/render_official_pdf.py`)
   re-verifies the checksum *after* reading, so even the inspection tools prove
   they did not mutate their input.

### Consequences
- Modifying the raw data becomes a loud test failure rather than a silent change
  that invalidates every downstream number.
- The raw workbook is version-controlled (525 KB) so the repository is
  self-contained and reproducible from a fresh clone.

### Alternatives rejected
- **Read-only filesystem permissions.** Platform-specific, and easily lost when
  files move between machines or through OneDrive sync.
- **Convention only.** Undetectable when it fails, which is precisely when
  detection matters.

---

## ADR-0004 — Accept pandas 3.x, guarded by an explicit interop regression test

**Status:** Accepted with monitoring (Phase 0)

### Context
Dependency resolution produced pandas 3.0.6 — a major release with
copy-on-write semantics by default and a new default string dtype. seaborn
0.13.2 predates pandas 3.x, and the project depends heavily on seaborn for the
EDA figures that go into the research paper.

Discovering a plotting incompatibility during Phase 2 EDA, or worse during the
Phase 6 write-up, would cost time the schedule does not have.

### Decision
Accept pandas 3.0.6 and convert the risk into a test rather than a hope.
`test_seaborn_plots_on_the_installed_pandas_major_version` renders the six
seaborn plot types the project will actually use — `histplot`, `boxplot`,
`countplot`, `barplot`, `scatterplot`, `heatmap` — against the installed pandas
on every test run. It passes on pandas 3.0.6 / seaborn 0.13.2 / matplotlib 3.11.2.

The documented fallback, if a 3.x incompatibility appears later, is to pin
`pandas>=2.2,<3` and rebuild. This is a one-line change because no project code
depends on 3.x-only behaviour.

### Consequences
- The risk is monitored continuously instead of being assumed away.
- The test is kept permanently, not deleted once it has passed once.
- **Related finding:** the same run surfaced that seaborn 0.13.2's `boxplot`
  passes matplotlib's deprecated `vert=` argument, removed in matplotlib 3.13.
  `matplotlib==3.11.2` is therefore a load-bearing pin, not a cosmetic one
  (decision log D-005).

### Alternatives rejected
- **Pin `pandas<3` pre-emptively.** Defensible, but it trades a tested risk for
  an untested assumption and pins the project to a line that will age out.
- **Accept pandas 3 without a guard test.** The failure would then surface as a
  broken figure during the write-up.

---

## ADR-0005 — Segmentation and recommendation are separate, composable stages

**Status:** Accepted (Phase 0)

### Context
The official documentation asks for "cluster-aware recommendations", which could
be read as one monolithic model. But CLAUDE.md §13 requires at least five
recommendation baselines to be evaluated independently, and §10 requires two
segmentation variants to be compared. A monolith makes both comparisons
impossible: it cannot answer "how much did the clustering actually contribute?"

### Decision
Segmentation produces a learner→segment assignment. Recommendation consumes that
assignment as **one input among several**, alongside content similarity, learner
similarity and rating relevance. The cluster-popularity recommender is one
evaluable baseline, not a mandatory stage every recommendation must pass through.

This means the pipeline can be run with the cluster signal ablated, which is what
makes its contribution measurable.

### Consequences
- Each of the five required baselines is independently evaluable, so the final
  method is selected on evidence (§13).
- Hybrid weights can be justified by ablation rather than asserted (§14).
- The sparse-history tiers (§15) can fall back to cluster or global signals
  without special-casing, because those signals are already separate components.
- If clustering turns out to add little, that is a measurable, reportable result
  rather than an architectural embarrassment.

### Alternatives rejected
- **Cluster-gated recommendation** (recommend only within a learner's cluster).
  Simpler, but it hard-codes the assumption that the clustering is good, makes
  its contribution unmeasurable, and collapses catalogue coverage.

---

## ADR-0006 — Privacy by construction: PII never enters the modelling path

**Status:** Accepted (Phase 0)

### Context
The `Users` sheet carries `UserName` and `Email`; `Teachers` carries
`TeacherName`. CLAUDE.md §17 forbids email as a modelling feature and requires
anonymised identifiers in the dashboard. Notably, the official documentation's
own field list omits these columns too — so excluding them costs nothing against
the requirements.

### Decision
`edupro.config.PII_COLUMNS` names `UserName`, `Email` and `TeacherName` as a
single source of truth. The ingestion layer drops them at load time, so they are
absent from every downstream frame rather than merely unused by convention. The
dashboard addresses learners by `UserID` only.

Making this a Phase 0 structural decision — rather than a Phase 5 UI filter —
means PII is never present to leak into a feature matrix, a persisted artifact,
a cached dataframe or a figure.

### Consequences
- A leak requires deliberately circumventing the ingestion layer.
- Enforceable by test: assert `PII_COLUMNS` are absent from processed outputs.
- `UserID` remains a pseudonymous identifier, which is what the learner-selection
  workflow needs; no re-identification capability is added.
