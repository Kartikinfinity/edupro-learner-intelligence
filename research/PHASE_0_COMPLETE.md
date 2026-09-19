# Phase 0 — Project Initialization — COMPLETE

**Phase:** 0 of 6 — Project initialization
**Date:** 19 September 2026
**Decision:** ✅ **PASS**
**Next phase:** Phase 1 — dense research and methodology investigation (**not started; awaiting go-ahead**)

---

## 1. Objectives

Phase 0 establishes the research-first execution environment. It explicitly does
**not** build the model, the recommender or the application — CLAUDE.md §4 gates
those behind the research and audit phases.

| # | Objective | Outcome |
| --- | --- | --- |
| 1 | Inspect the workspace: root, files, Python versions, git, existing code | ✅ Done |
| 2 | Locate both authoritative source materials | ✅ Both present |
| 3 | Create a clean professional repository structure | ✅ Done |
| 4 | Preserve the original PDF and Excel workbook unmodified | ✅ Verified by checksum |
| 5 | Initialize project configuration and package structure | ✅ Done |
| 6 | Create the decision log and experiment log | ✅ Done (+ ADR file) |
| 7 | Create a project manifest | ✅ Done |
| 8 | Run only safe initialization checks | ✅ Structural inventory only |
| 9 | Run git status; create an initial commit | ✅ Repository initialized and committed |
| 10 | Produce this phase report | ✅ This document |

---

## 2. Environment findings

### Workspace as found

The project root contained four files and no subdirectories:

| File | Note |
| --- | --- |
| `CLAUDE.md` | 646 lines — the project engineering standard |
| `EduPro Online Platform.xlsx` | 525,199 B — the dataset |
| `project offical detail.pdf` | 3,217,155 B — the official brief |
| `claude.md.txt` | **0 bytes, empty** — see unresolved issues |

**No git repository, no virtual environment, and no pre-existing source code.**
Phase 0 therefore started from a genuinely clean slate; nothing was inherited or
overwritten.

### Interpreters available

| Version | Path | Scientific stack as found |
| --- | --- | --- |
| 3.14.0 (system default) | `C:\Python314` | Nearly complete; `openpyxl` missing |
| **3.13.9** | `…\Programs\Python\Python313` | Partial (`scikit-learn`, `seaborn`, `joblib` missing) |
| 3.12.0 | `…\Programs\Python\Python312` | Empty |
| 3.11.0 | `…\Programs\Python\Python311` | Empty |

git 2.51.2.windows.1 is available. OS: Windows 11 Pro 10.0.26200.

### Interpreter choice — and why it changed mid-phase

The venv was **first built on 3.14.0**, the system default, and the full stack
installed and passed a modelling smoke test there. It was then **rebuilt on
3.13.9**.

The reason is a deployment constraint, not a technical failure: CLAUDE.md §20
prohibits Docker and §21 requires the app to be public-deployment ready, which
points at Streamlit Community Cloud — supporting Python 3.9–3.13. Shipping a
3.14-only local environment would have surfaced as an undeployable app in Phase
6, the phase with the least slack before the 20 September deadline. The rebuild
cost minutes now; the same discovery later would have cost a deliverable.

Recorded as ADR-0002 and decision-log D-002. Enforced by
`test_python_version_is_within_supported_range` and by `requires-python` in
`pyproject.toml`.

### Environment as built

`.venv/` on **Python 3.13.9**, with the package installed in editable mode.

| Runtime | Version | | Dev tooling | Version |
| --- | --- | --- | --- | --- |
| pandas | 3.0.6 | | pytest | 9.1.1 |
| numpy | 2.5.3 | | jupyterlab | 4.6.3 |
| scipy | 1.18.1 | | ipykernel | 7.3.0 |
| scikit-learn | 1.9.1 | | pypdf | 6.19.0 |
| joblib | 1.6.0 | | pymupdf | 1.28.2 |
| matplotlib | 3.11.2 | | | |
| seaborn | 0.13.2 | | | |
| plotly | 7.1.0 | | | |
| streamlit | 1.64.0 | | | |
| openpyxl | 3.1.5 | | | |
| pyarrow | 25.0.1 | | | |
| PyYAML | 6.0.3 | | | |

Declared in `requirements.txt` / `requirements-dev.txt`; the complete resolved
tree (130 packages) is frozen in `requirements.lock.txt`.

---

## 3. Source material status

**Both required source materials were present. Nothing was missing, and nothing
was fabricated or substituted.**

| Material | Canonical path | SHA-256 | Status |
| --- | --- | --- | --- |
| Official documentation | `references/official/project offical detail.pdf` | `e794444490c19f85b8bef6534d844a629150971189eaf71448122ed402c4e8cf` | ✅ Unmodified |
| Official dataset | `data/raw/EduPro Online Platform.xlsx` | `ed555e4613e6a210b73af0d4f64e34bd43cb59650041e2bd05f8a8ffbf5d8cc0` | ✅ Unmodified |

Files were **copied, never moved**, so the user's originals remain exactly where
they were left; the root copies are git-ignored so the repository tracks exactly
one authoritative copy of each. Post-operation checksums of all four paths
(original and copy, for both files) are identical — evidence in §6.

### The official PDF is image-based

`pypdf` extracts **0 characters from all 6 pages**: there is no embedded text
layer. Requirements that cannot be quoted or diffed cannot be traced, so the
pages were rasterised (`scripts/render_official_pdf.py`) and read, and a
transcription was written to
`references/official/OFFICIAL_REQUIREMENTS_TRANSCRIPT.md`.

The transcript states that the **PDF remains authoritative** on any
disagreement, records the PDF's checksum, and segregates observations from
transcription. The rendering script re-verifies the checksum before and after
running.

Document identity confirmed from the page footers:
`https://projects.unifiedmentor.com/project_instructions?id=18743`, headed
"Unified Mentor | Project Allotment Portal".

---

## 4. Repository structure created

All directories required by the brief were created, plus four justified
additions (`reports/`, `scripts/`, `data/interim/`, `src/edupro/`).

```
PROJECT 2/
├── app/                    Streamlit application              (Phase 5)
├── artifacts/              source inventory, rendered PDF pages
├── data/{raw,interim,processed}/
├── docs/                   technical docs + traceability matrix
├── experiments/            experiment configs and results     (Phase 3)
├── models/                 persisted artifacts                (Phase 4+)
├── notebooks/              exploration only
├── references/official/    authoritative PDF + transcript
├── reports/figures/        generated figures
├── research/               decision log, experiment log, ADRs, phase reports
├── scripts/                reproducible entry points
├── src/edupro/             production package (7 modules)
└── tests/                  test suite
```

**Files created: 35.** Configuration (`pyproject.toml`, `.gitignore`,
`.gitattributes`, three requirements files), the `edupro` package (7 modules
with stated responsibilities), two reproducible scripts, the test suite, and
seven documentation files.

The package boundaries follow CLAUDE.md §18 exactly — `data`, `features`,
`segmentation`, `recommendation`, `evaluation`, `explainability` — so that the
separation which matters most (leakage-sensitive feature code vs evaluation
code) is visible in the structure itself rather than left to discipline.

---

## 5. Safe initialization checks performed

Only structural and environmental checks were run. **No EDA, no modelling, no
data findings** — CLAUDE.md §4 gates those behind Phase 2.

`scripts/inspect_sources.py` reports sheet names, row/column counts, dtypes,
null counts and cardinalities, and deliberately computes no distributions or
summary statistics. Output: `artifacts/phase0_source_inventory.json`.

### Workbook structure (4 sheets, zero missing values anywhere)

| Sheet | Rows | Cols | Role |
| --- | --- | --- | --- |
| `Users` | 3,000 | 5 | Learner demographics (+ 2 PII columns) |
| `Teachers` | 60 | 7 | Instructor attributes — **not in the official field list** |
| `Courses` | 60 | 8 | Course catalogue |
| `Transactions` | 10,000 | 7 | Interactions: 3,000 users × 60 courses |

### One deliberate exception to "structure only"

The manifest was going to assert a matrix-density figure, and CLAUDE.md §6
forbids asserting an unverified number. So the distinct `(UserID, CourseID)` pair
count was checked:

```
transactions rows          : 10000
distinct (User, Course)    : 10000
repeat pairs               : 0
distinct-pair density      : 5.56%
mean distinct courses/user : 3.333
```

This is a structural integrity fact, not a finding. It matters immediately: with
**zero repeat enrollments**, the interaction signal is purely implicit/binary —
there is no repeat-purchase frequency available to weight by, which constrains
the recommender design in Phase 3.

---

## 6. Validation checks and evidence

### Test suite: **31 passed**, 1 warning, 5.18s

```
$ .venv/Scripts/python.exe -m pytest -q
...............................                                   [100%]
31 passed, 1 warning in 5.18s
```

| Check | Evidence |
| --- | --- |
| Python within supported range | `test_python_version_is_within_supported_range` |
| All 12 runtime dependencies importable | 12 parametrised import tests |
| K-Means + silhouette + hierarchical functional | `test_core_modelling_stack_is_functional` (synthetic blobs; silhouette > 0.5) |
| Seed determinism | `test_kmeans_is_deterministic_under_the_project_seed` |
| seaborn ↔ pandas 3.x interop | `test_seaborn_plots_on_the_installed_pandas_major_version` — 6 plot types |
| All 10 required directories exist | 10 parametrised tests |
| All 6 pipeline stage packages exist | `test_package_boundaries_exist` |
| No Docker artifacts (§20) | `test_no_docker_artifacts_are_present` |
| Dataset unmodified | `test_raw_workbook_is_present_and_unmodified` |
| Documentation unmodified | `test_official_documentation_is_present_and_unmodified` |
| Workbook sheets as expected | `test_workbook_exposes_the_expected_sheets` |

The synthetic-data tests assert nothing about the EduPro dataset. They verify
that the **tooling** works. No EduPro finding exists yet.

### Source integrity — original vs canonical copy

```
ed555e46…8cc0 *EduPro Online Platform.xlsx                  (root original)
ed555e46…8cc0 *data/raw/EduPro Online Platform.xlsx         (canonical copy)
e7944444…e8cf *project offical detail.pdf                   (root original)
e7944444…e8cf *references/official/project offical detail.pdf (canonical copy)
```

Identical. **No official source was modified.**

### The one warning is load-bearing

```
seaborn/categorical.py:700: MatplotlibDeprecationWarning: vert: bool was
deprecated in Matplotlib 3.11 and will be removed in 3.13.
```

seaborn 0.13.2's `boxplot` passes matplotlib's deprecated `vert=` argument, which
**is removed in matplotlib 3.13**. The exact pin `matplotlib==3.11.2` is
therefore a functional requirement, not cosmetic tidiness. Recorded as D-005. It
is left visible rather than suppressed, because a suppressed warning here would
become a broken figure during the research-paper write-up.

### Git

Repository initialized on `main`; commit `d31ae3e` `phase-0/project-bootstrap`
tracks **36 files** (35 created this phase, plus the pre-existing `CLAUDE.md`).
Working tree clean. Root-level source duplicates, `.venv/`, `*.egg-info/` and
the regenerable rendered PDF pages are correctly excluded. Not pushed —
CLAUDE.md §24 permits pushing only on explicit instruction.

The commit is authored `Kartik <kartikshreekumar2006@gmail.com>` from the
machine's existing global git config, which was used rather than silently
overridden. See unresolved issue 2.

---

## 7. Important findings

These come from the source materials themselves, not from analysis.

1. **The Teachers sheet is absent from the official field list.** "Dataset Fields
   Utilized" names only Users, Courses and Transactions, yet the workbook carries
   a fourth sheet. This corroborates CLAUDE.md §11 *independently* — the sheet is
   an opt-in experiment (EXP-014), not a core input. `config.CORE_SHEETS` encodes
   this separation structurally.

2. **The interaction matrix is sparse and purely implicit.** 5.56% dense, 3.333
   distinct courses per learner, zero repeat enrollments. The tiered
   sparse-history strategy of §15 is a core requirement of this dataset, not a
   defensive nicety — and the absence of repeat purchases removes frequency as a
   possible weighting signal.

3. **The workbook contains columns the official brief does not list.**
   `CoursePrice`, `CourseDuration` (Courses) and `UserName`, `Email` (Users). The
   PII columns are excluded by §17 regardless. Whether the other two are used is
   a Phase 2/3 decision requiring justification either way (Q-3).

4. **`Amount` and `CoursePrice` both have exactly 23 distinct values.** If
   `Amount` is simply the course price at purchase, then "average spending" and
   "average course price" are one feature wearing two names, and only one belongs
   in the model. Flagged as Q-1; **not assumed** in either direction.

5. **`CourseName` has 58 distinct values across 60 unique `CourseID`s.** Two
   names repeat. Affects content-based similarity and recommendation
   de-duplication. Flagged as Q-2; not assumed to be an error.

6. **The official document specifies no target cluster count and no metric
   thresholds.** It mandates methods and metrics only. Every such value in this
   project must therefore come from experiment — there is no official number to
   defer to, and none may be invented.

7. **"Engagement Lift (Proxy)" is required but undefined.** The brief names the
   metric and its purpose ("impact estimate") but gives no formula. Whatever is
   adopted must be labelled a proxy and must never be presented as measured
   causal impact (§6). Flagged as Q-7.

---

## 8. Artifacts created

| Artifact | Purpose |
| --- | --- |
| `README.md` | Project overview, quickstart, reproducibility, status |
| `PROJECT_MANIFEST.md` | Source documents, dataset inventory, environment, constraints |
| `docs/REQUIREMENTS_TRACEABILITY.md` | Every requirement → implementation → verification |
| `research/decision_log.md` | D-001…D-008 with evidence; 7 open questions |
| `research/architecture_decision_record.md` | ADR-0001…ADR-0006 |
| `research/experiment_log.md` | Template, rules, and the registered experiment programme |
| `research/PHASE_0_COMPLETE.md` | This report |
| `references/official/OFFICIAL_REQUIREMENTS_TRANSCRIPT.md` | Verbatim transcript of the image-based PDF |
| `artifacts/phase0_source_inventory.json` | Machine-readable structural inventory |
| `scripts/inspect_sources.py` | Reproducible read-only workbook inventory |
| `scripts/render_official_pdf.py` | Reproducible PDF rasterisation |
| `src/edupro/` | Package skeleton: config + 6 stage packages |
| `tests/test_phase0_environment.py` | 31 Phase 0 acceptance tests |
| `pyproject.toml`, `requirements{,-dev,.lock}.txt`, `.gitignore`, `.gitattributes` | Project configuration |

---

## 9. Unresolved issues

None blocking. Three items carried forward:

1. **`claude.md.txt` (0 bytes) in the project root.** An empty file resembling a
   truncated copy of `CLAUDE.md`. It was **not deleted** — removing a user's file
   is not Phase 0's call — and is git-ignored so it cannot be mistaken for a
   second source of project rules. `CLAUDE.md` (646 lines) is unambiguously the
   authoritative standard and was read in full. *Recommend deletion, at the
   user's discretion.*

2. **Git identity vs project authorship.** The machine's global git config is
   `Kartik <kartikshreekumar2006@gmail.com>`, while the session account is
   `menonanushree897@gmail.com`. The existing global config was used for the
   commit rather than silently overridden. `pyproject.toml` records the author as
   *Anushree Menon*, **inferred** from the account email. *Both should be
   confirmed before the repository is published.*

3. **Seven open research questions** (Q-1…Q-7) are registered in the decision log
   with the phase that settles each. They are open by design — settling them now
   would mean assuming answers the data has not yet given.

---

## 10. PASS / FAIL decision

### ✅ **PASS**

| Pass criterion | Evidence | Verdict |
| --- | --- | --- |
| Project structure exists | 13 top-level directories; 6 stage packages; verified by 11 tests | ✅ |
| Source materials accessible | Both present; workbook parsed to 4 sheets; PDF rendered and read in full | ✅ |
| Environment usable | Python 3.13.9 venv; 31/31 tests pass; K-Means, hierarchical, silhouette, seaborn all exercised | ✅ |
| Project configuration exists | `pyproject.toml`, 3 requirements files, `.gitignore`, `.gitattributes`, editable install | ✅ |
| No official source modified | All four checksums identical pre/post; asserted on every test run | ✅ |
| CLAUDE.md rules respected | See compliance table below | ✅ |

### CLAUDE.md compliance

| § | Rule | How Phase 0 complied |
| --- | --- | --- |
| 4 | Research-first; do not build the product | No model, recommender or app built. Structure only. |
| 5 | Operate autonomously | Proceeded without questions; both required files were present. |
| 6 | Scientific integrity | No metric, statistic or finding fabricated. The one computed number was verified, not asserted. Two wrong version guesses were corrected against the installed reality rather than left standing. |
| 7 | No novel algorithms | None proposed. |
| 8 | Raw data immutable | Copied not moved; checksums enforced by test (ADR-0003). |
| 11 | Teachers sheet as experiment | Excluded from `CORE_SHEETS`; registered as EXP-014 (D-007). |
| 17 | Privacy | `PII_COLUMNS` defined; dropped at ingestion by design (ADR-0006). |
| 18 | Modular source | Six stage packages with stated responsibilities (ADR-0001). |
| 20 | No Docker | None created; absence asserted by test. |
| 24 | Meaningful phase commits | `phase-0/project-bootstrap`. Not pushed. |
| 25 | Documentation | Decision log, experiment log and ADR file all created and populated. |
| 27 | Phase report with evidence | This document; every claim traced to a command output or file. |
| 28 | Stop condition | Phase 0 evaluated; PASS; **stopping here.** |

---

## 11. Stop

Per CLAUDE.md §28 and the Phase 0 brief, work **stops here**. Phase 1 (dense
research and methodology investigation) will not begin automatically.

**Phase 1 will, on instruction, cover:** clustering methodology for mixed
categorical/numerical learner features; cluster validation and stability
methods; recommender approaches appropriate to a 5.56%-dense implicit matrix
with ~3.3 interactions per user; leakage-free temporal evaluation protocol
design at this history depth; and defensible formulations of the engagement
proxy.
