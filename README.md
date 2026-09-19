# Student Segmentation and Personalized Course Recommendation System for EduPro

Learner segmentation and personalised course recommendation for the EduPro
online learning platform — built as a reproducible, explainable research-grade
system rather than a single notebook.

> **Project status: Phase 3A complete — learner segmentation experiments.**
> No model has been trained yet. The repository contains the validated
> environment, the authoritative source materials, a research corpus with 40
> verified references and 28 pre-registered experiments, and a tested data
> pipeline with a full forensic audit of the dataset.
> Sections marked *(Phase N)* below describe planned work, not shipped work.

> ### ⚠ Headline finding from the Phase 2 audit
> **Course choice in this dataset is statistically indistinguishable from
> popularity-weighted random selection.** Category concentration, top-category
> share, free-course share and item–item co-occurrence all fall inside a
> permutation null; course popularity is near-uniform (Gini 0.042); demographics
> are unrelated to choice. One real signal exists — learners reuse instructors far
> more than chance — but it lifts next-course prediction only 1.10×.
> The dataset is also **assessed as almost certainly synthetic**.
> This is reported up front because it bounds what the project can honestly claim.
> Full evidence: [`research/dataset_audit.md`](research/dataset_audit.md).

---

## What this project does

EduPro's learners are not homogeneous: some sample beginner courses across many
domains, some specialise deeply, others pursue career-oriented certifications.
One-size-fits-all recommendations serve none of them well.

This system:

1. **Segments learners** into interpretable behavioural groups from their
   enrollment history, using K-Means with hierarchical clustering as an
   independent validation.
2. **Recommends courses** personalised to each learner's segment, content
   preferences and history — with an explicit fallback path for learners whose
   history is too thin to personalise honestly.
3. **Explains every recommendation** in plain language, derived from the actual
   scoring contributions rather than written to sound plausible.

---

## Dataset

`data/raw/EduPro Online Platform.xlsx` — 4 sheets, no missing values anywhere.

| Sheet | Rows | Columns | Role |
| --- | --- | --- | --- |
| `Users` | 3,000 | 5 | Learner demographics |
| `Courses` | 60 | 8 | Course catalogue |
| `Transactions` | 10,000 | 7 | Enrollment interactions |
| `Teachers` | 60 | 7 | Instructor attributes — *opt-in experiment only* |

The interaction matrix is **5.56% dense**: 10,000 enrollments across 3,000
learners and 60 courses, all distinct `(UserID, CourseID)` pairs, giving a mean
of **3.333 courses per learner**. Sparse learner histories are therefore an
inherent property of this problem, not an edge case — and there are no repeat
enrollments, so the interaction signal is purely implicit/binary.

Full structural inventory: [`PROJECT_MANIFEST.md`](PROJECT_MANIFEST.md) §3.

---

## Quickstart

Requires **Python 3.11–3.13** (3.13 recommended; see ADR-0002 for the reasoning,
including a Phase 1 correction to its original rationale).

```bash
python -m venv .venv
```

Activate it — Windows PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install the runtime dependencies and the package itself:

```bash
pip install -r requirements.txt && pip install -e .
```

Verify the environment and the integrity of the source materials:

```bash
pytest -q
```

A clean run reports **104 passed**. That result confirms the modelling stack is
functional, the seed is deterministic, the repository layout is intact, and both
source materials match their recorded checksums.

For exploration and research tooling, add the dev extras:

```bash
pip install -r requirements-dev.txt
```

To reproduce the exact environment behind any reported number, use the full
freeze instead:

```bash
pip install -r requirements.lock.txt
```

---

## Repository layout

```
.
├── app/                  Streamlit application                      (Phase 5)
├── artifacts/            generated artifacts: source inventory, rendered PDF pages
├── data/
│   ├── raw/              IMMUTABLE authoritative dataset
│   ├── interim/          intermediate outputs
│   └── processed/        modelling-ready datasets
├── docs/                 technical docs, requirements traceability, deliverables
├── experiments/          experiment configs and results               (Phase 3)
├── models/               persisted model artifacts                    (Phase 4+)
├── notebooks/            exploration only — never the sole implementation
├── references/official/  authoritative PDF + verbatim transcript
├── reports/figures/      generated figures
├── research/             decision log, experiment log, ADRs, phase reports
├── scripts/              reproducible entry points
├── src/edupro/           production package
└── tests/                test suite
```

### The `edupro` package

One subpackage per pipeline stage, so each is independently testable and the
boundaries that matter (especially leakage) are visible in the structure itself:

| Module | Responsibility |
| --- | --- |
| `edupro.config` | Paths, sheet names, seed, PII column list, source checksums |
| `edupro.data` | Workbook ingestion and schema validation |
| `edupro.features` | Learner-level aggregation and feature engineering |
| `edupro.segmentation` | Scaling, encoding, clustering, selection, profiling |
| `edupro.recommendation` | Candidate generation, scoring, ranking, sparse-history tiers |
| `edupro.evaluation` | Segmentation and recommendation metrics |
| `edupro.explainability` | Human-readable justifications |

The Streamlit app and every notebook are **consumers** of this package. Neither
defines modelling logic, and the app loads persisted artifacts rather than
training on startup.

---

## Methodology

A six-phase gated sequence; each phase must pass its acceptance criteria before
the next begins, and each ends with a `research/PHASE_N_COMPLETE.md` report
carrying an evidence-backed PASS/FAIL.

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Project initialization | ✅ **PASS** |
| 1 | Research and methodology investigation | ✅ **PASS** |
| 2 | Dataset audit and EDA | ✅ **PASS** |
| 3A | ML experimentation — segmentation | ✅ **PASS** |
| 3B | ML experimentation — recommendation | Not started |
| 4 | Model selection and architecture freeze | Not started |
| 5 | Production implementation | Not started |
| 6 | Validation, documentation, deployment | Not started |

### Segmentation *(Phase 3)*

K-Means as the primary method, with cluster count selected by elbow and
silhouette analysis, and hierarchical clustering as an independent structural
validation. Two feature variants are compared on evidence — behaviour +
demographics vs behaviour only — because demographic features must not dominate
learner segmentation without justification.

### Recommendation *(Phase 3)*

Five baselines are evaluated before any hybrid is proposed: global popularity,
content-based, similar-learner, cluster-popularity, and hybrid. Hybrid weights
are set by ablation, not by assertion. Evaluation uses a leakage-controlled
temporal hold-out, and learners with insufficient history are evaluated
separately rather than being scored as if personalisation had applied to them.

---

## Reproducibility

- **Single seed.** `edupro.config.RANDOM_SEED = 42` governs every stochastic
  operation; determinism is asserted by test.
- **Immutable inputs.** `data/raw/` is verified by SHA-256 on every test run, so
  an accidental write becomes a loud failure rather than a silent invalidation of
  every downstream result.
- **Pinned environment.** Direct dependencies pinned exactly in
  `requirements.txt`; the complete resolved environment frozen in
  `requirements.lock.txt`.
- **No hidden steps.** Reported results come from scripts in `scripts/` and code
  in `src/`, never from a notebook that has to be run by hand.

---

## Scientific integrity

This project reports what it finds, including what does not work.

- Failed and underperforming experiments are recorded in
  `research/experiment_log.md`, not discarded — the record of what lost is what
  makes the winner defensible.
- The data is observational, so no causal claim is made. The engagement metric
  the official brief requires is a **proxy** and is labelled as one everywhere it
  appears.
- No metric, citation, dataset statistic or result in this repository is
  fabricated. Every number traces to a script that regenerates it.

---

## Privacy

`UserName`, `Email` and `TeacherName` are dropped at ingestion, not merely
excluded by convention downstream — so PII is never present to leak into a
feature matrix, a persisted artifact or a figure. Learners are identified in the
dashboard by pseudonymous `UserID` only. Email is never a modelling feature.

---

## Documentation

| Document | Contents |
| --- | --- |
| [`PROJECT_MANIFEST.md`](PROJECT_MANIFEST.md) | Source materials, dataset inventory, environment |
| [`docs/REQUIREMENTS_TRACEABILITY.md`](docs/REQUIREMENTS_TRACEABILITY.md) | Every requirement → implementation → verification |
| [`research/decision_log.md`](research/decision_log.md) | Decisions with evidence; open questions |
| [`research/architecture_decision_record.md`](research/architecture_decision_record.md) | Durable architectural decisions (ADRs) |
| [`research/experiment_log.md`](research/experiment_log.md) | Experiment results, successes and failures |
| [`research/literature_review.md`](research/literature_review.md) | Eight research areas; 40 verified references |
| [`research/methodology_comparison.md`](research/methodology_comparison.md) | 40 methods compared; decision status for each |
| [`research/segmentation_research.md`](research/segmentation_research.md) | Feature design, encoding, k-selection, stability |
| [`research/recommendation_evaluation_plan.md`](research/recommendation_evaluation_plan.md) | Pre-registered evaluation protocol and metrics |
| [`research/production_research.md`](research/production_research.md) | Artifacts, deployment, testing strategy |
| [`research/experiment_plan.md`](research/experiment_plan.md) | 8 research questions, 28 experiments |
| [`research/dataset_audit.md`](research/dataset_audit.md) | **Full forensic data-quality report and EDA findings** |
| [`research/segmentation_results.md`](research/segmentation_results.md) | All segmentation experiments, including the negative results |
| [`research/segmentation_feature_decision.md`](research/segmentation_feature_decision.md) | The chosen representation and its reversal conditions |
| [`research/cluster_profiles.md`](research/cluster_profiles.md) | The four segments, with limitations |
| [`references/official/OFFICIAL_REQUIREMENTS_TRANSCRIPT.md`](references/official/OFFICIAL_REQUIREMENTS_TRANSCRIPT.md) | Verbatim transcript of the official brief |
| `research/PHASE_N_COMPLETE.md` | Per-phase report with PASS/FAIL and evidence |

---

## Deliverables

| # | Deliverable | Status |
| --- | --- | --- |
| 1 | Research paper (EDA, insights, recommendations) | Phase 6 |
| 2 | Streamlit dashboard (live analytics) | Phase 5 |
| 3 | Executive summary for non-technical stakeholders | Phase 6 |

---

## Scripts

| Script | Purpose |
| --- | --- |
| `scripts/inspect_sources.py` | Read-only structural inventory of the workbook → `artifacts/phase0_source_inventory.json` |
| `scripts/render_official_pdf.py` | Rasterise the image-based official PDF so its requirements can be read and verified |
| `scripts/analytical_baselines.py` | Random-ranker and Precision@K ceiling reference values implied by the 60-course catalogue |
| `scripts/run_data_audit.py` | EXP-001…006 plus permutation signal detection → `artifacts/phase2_audit.json` |
| `scripts/generate_eda_figures.py` | The ten EDA figures → `artifacts/eda/` |
| `scripts/run_segmentation_experiments.py` | EXP-010…014 → `artifacts/segmentation/segmentation_results.json` |
| `scripts/generate_segmentation_figures.py` | The ten segmentation figures → `artifacts/segmentation/` |

Both scripts re-verify the source checksum after reading, so even the inspection
tooling proves it did not mutate its input.

---

## Notes

- **No Docker.** Deployment is a Python environment plus Streamlit, by design.
- The official documentation PDF is image-based (no text layer), which is why a
  rendering script and a transcript exist. The PDF remains authoritative on any
  disagreement.

---

## Acknowledgements

Project brief and dataset provided by **Unified Mentor** (project `id=18743`).
