# Project Manifest

**Project:** Student Segmentation and Personalized Course Recommendation System for EduPro
**Programme:** Unified Mentor internship project `id=18743`
**Repository root:** `PROJECT 2/`
**Manifest generated:** Phase 0 — 19 September 2026
**Status:** Phase 0 complete. Phases 1–6 not started.

---

## 1. Project objective

Build a learner-centric personalization system for the EduPro online learning
platform that (a) segments learners into interpretable behavioural groups and
(b) recommends courses personalised to each learner's segment and history,
delivered as a research paper, a Streamlit dashboard and an executive summary.

The official document frames the shift explicitly: from predicting course demand
to understanding and personalising the learner journey
(`references/official/project offical detail.pdf`, page 6).

---

## 2. Source documents

Both authoritative sources were supplied by the user and are present. Neither
has been modified; integrity is asserted by checksum in
`tests/test_phase0_environment.py`.

| Role | Canonical path | SHA-256 | Size |
| --- | --- | --- | --- |
| Official project documentation (authoritative for **requirements**) | `references/official/project offical detail.pdf` | `e794444490c19f85b8bef6534d844a629150971189eaf71448122ed402c4e8cf` | 3,217,155 B |
| Official dataset (authoritative for **data facts**) | `data/raw/EduPro Online Platform.xlsx` | `ed555e4613e6a210b73af0d4f64e34bd43cb59650041e2bd05f8a8ffbf5d8cc0` | 525,199 B |

The user's original copies remain untouched in the workspace root. The files
above are byte-identical copies placed at canonical paths; the root originals
are git-ignored so the repository holds exactly one authoritative copy of each.

**The documentation PDF is image-based** — six raster pages with no text layer.
`scripts/render_official_pdf.py` rasterises it; a transcription is kept at
`references/official/OFFICIAL_REQUIREMENTS_TRANSCRIPT.md`. The PDF, not the
transcript, remains authoritative.

---

## 3. Dataset file and expected sheets

Structural inventory taken read-only; full detail in
`artifacts/phase0_source_inventory.json`, regenerable via
`python scripts/inspect_sources.py`.

The workbook contains **4 sheets**. No column has any missing value.

### `Users` — 3,000 rows x 5 columns

| Column | dtype | Distinct |
| --- | --- | --- |
| `UserID` | str | 3,000 |
| `UserName` | str | 3,000 |
| `Age` | int64 | 21 |
| `Gender` | str | 2 |
| `Email` | str | 3,000 |

`UserID` is unique per row — one row per learner. `UserName` and `Email` are
**PII**: excluded from modelling and from the dashboard (CLAUDE.md §17), and not
listed in the official field set.

### `Teachers` — 60 rows x 7 columns

| Column | dtype | Distinct |
| --- | --- | --- |
| `TeacherID` | str | 60 |
| `TeacherName` | str | 60 |
| `Age` | int64 | 21 |
| `Gender` | str | 2 |
| `Expertise` | str | 12 |
| `YearsOfExperience` | int64 | 16 |
| `TeacherRating` | float64 | 56 |

**Not named in the official "Dataset Fields Utilized" section.** Treated as an
opt-in experiment, not a core input (CLAUDE.md §11).

### `Courses` — 60 rows x 8 columns

| Column | dtype | Distinct |
| --- | --- | --- |
| `CourseID` | str | 60 |
| `CourseName` | str | 58 |
| `CourseCategory` | str | 12 |
| `CourseType` | str | 2 |
| `CourseLevel` | str | 3 |
| `CoursePrice` | float64 | 23 |
| `CourseDuration` | float64 | 60 |
| `CourseRating` | float64 | 56 |

`CourseID` is unique but `CourseName` has 58 distinct values across 60 rows —
**two names repeat**. To be characterised in Phase 2; not assumed to be an error.
`CoursePrice` and `CourseDuration` are not in the official field list.

### `Transactions` — 10,000 rows x 7 columns

| Column | dtype | Distinct |
| --- | --- | --- |
| `TransactionID` | str | 10,000 |
| `UserID` | str | 3,000 |
| `CourseID` | str | 60 |
| `TransactionDate` | datetime64[us] | 358 |
| `Amount` | float64 | 23 |
| `PaymentMethod` | str | 3 |
| `TeacherID` | str | 60 |

This is the **interaction matrix**: 10,000 interactions over 3,000 learners and
60 courses. All 10,000 rows are **distinct `(UserID, CourseID)` pairs** — there
are zero repeat enrollments — so the matrix is exactly
10,000 / (3,000 x 60) = **5.56% dense**, with a mean of **3.333 distinct courses
per learner**. Sparse learner histories are therefore expected, making the
tiered strategy of CLAUDE.md §15 a real requirement rather than a precaution.
The per-learner *distribution* (as opposed to the mean) is a Phase 2 question,
and it determines where the sparse-history tier boundaries fall.

The absence of repeat pairs also means the interaction signal is **purely
binary/implicit**: there is no repeat-purchase frequency to weight by.

`Amount` has 23 distinct values, exactly matching `CoursePrice`. Whether
`Amount` is the course price at purchase is a **Phase 2 audit question**, not an
assumption.

### Join keys

```
Users.UserID        1 --- n  Transactions.UserID
Courses.CourseID    1 --- n  Transactions.CourseID
Teachers.TeacherID  1 --- n  Transactions.TeacherID     (opt-in experiment only)
```

All three foreign keys show full coverage at the cardinality level (3,000 / 60 /
60 distinct values respectively). Referential integrity is verified in Phase 2.

---

## 4. Official requirements

Transcribed verbatim in `references/official/OFFICIAL_REQUIREMENTS_TRANSCRIPT.md`;
traceability to implementation is tracked in `docs/REQUIREMENTS_TRACEABILITY.md`.
In summary, the official document mandates:

- **Feature engineering** — engagement (total courses enrolled, average courses
  per category, enrollment frequency), preference (preferred category, preferred
  level, average course rating enrolled), behavioural (average spending,
  diversity score, learning depth index).
- **Methodology** — learner-level aggregation; normalisation, categorical
  encoding, sparse-enrollment noise reduction; K-Means with hierarchical
  clustering as validation; elbow and silhouette for cluster selection.
- **Recommendation** — content-based filtering, similar learner profiles, course
  popularity within cluster, rating-weighted relevance.
- **Evaluation** — Silhouette Score (cluster quality), Intra-Cluster Similarity
  (behavioural consistency), Recommendation Precision (relevance), Engagement
  Lift Proxy (impact estimate).
- **Streamlit** — learner profile explorer, cluster visualization dashboard,
  personalized course recommendations, segment comparison panels; the user can
  select a learner, view the assigned segment, see recommended learning paths,
  and filter by level or category.
- **Deliverables** — research paper, Streamlit dashboard, executive summary.

The official document specifies **no target cluster count and no metric
thresholds**. Every such value must come from experiment.

---

## 5. Current environment

| Item | Value |
| --- | --- |
| OS | Windows 11 Pro 10.0.26200 |
| Project Python | **3.13.9**, isolated in `.venv/` |
| Python versions available | 3.14.0, 3.13.9, 3.12.0, 3.11.0 |
| pip | upgraded within `.venv` |
| git | 2.51.2.windows.1 |
| Containerisation | **none** — Docker is prohibited (CLAUDE.md §20) |

3.13 was chosen over the system-default 3.14 to stay close to the Streamlit
Community Cloud default (3.12) and away from newest-interpreter risk; see
ADR-0002, whose original rationale was corrected in Phase 1.

### Runtime dependencies (exact, validated)

`pandas 3.0.6` · `numpy 2.5.3` · `scipy 1.18.1` · `scikit-learn 1.9.1` ·
`joblib 1.6.0` · `matplotlib 3.11.2` · `seaborn 0.13.2` · `plotly 7.1.0` ·
`streamlit 1.64.0` · `openpyxl 3.1.5` · `pyarrow 25.0.1` · `PyYAML 6.0.3`

Development extras: `pytest 9.1.1` · `jupyterlab 4.6.3` · `ipykernel 7.3.0` ·
`pypdf 6.19.0` · `pymupdf 1.28.2`

Declared in `requirements.txt` / `requirements-dev.txt`; the fully-resolved
environment including transitive packages is frozen in `requirements.lock.txt`.

---

## 6. Deliverable inventory

| # | Deliverable | Source | Status |
| --- | --- | --- | --- |
| 1 | Research paper | Official + CLAUDE.md §29 P1 | Not started |
| 2 | Streamlit dashboard | Official + CLAUDE.md §29 P2 | Not started |
| 3 | Executive summary | Official + CLAUDE.md §29 P3 | Not started |
| 4 | GitHub-ready repository | CLAUDE.md §3 | Scaffolded (Phase 0) |
| 5 | Technical architecture | CLAUDE.md §3 | Not started |
| 6 | Experiment logs | CLAUDE.md §25 | Initialised (Phase 0) |
| 7 | Trained artifacts | CLAUDE.md §22 | Not started |
| 8 | Tests | CLAUDE.md §23 | Phase 0 suite only (31 tests) |
| 9 | Reproducible environment | CLAUDE.md §3 | Complete (Phase 0) |
| 10 | Final validation report | CLAUDE.md §3 | Not started |

---

## 7. Repository layout

```
PROJECT 2/
├── app/                    Streamlit application (Phase 5)
├── artifacts/              generated artifacts; source inventory, rendered PDF pages
├── data/
│   ├── raw/                IMMUTABLE authoritative dataset
│   ├── interim/            intermediate outputs (git-ignored)
│   └── processed/          modelling-ready datasets (git-ignored)
├── docs/                   technical documentation, traceability
├── experiments/            experiment configurations and results (Phase 3)
├── models/                 persisted model artifacts (git-ignored)
├── notebooks/              exploration; never the only implementation (CLAUDE.md §19)
├── references/official/    authoritative PDF + transcript
├── reports/figures/        generated figures (git-ignored)
├── research/               decision log, experiment log, ADRs, phase reports
├── scripts/                reproducible entry-point scripts
├── src/edupro/             production package (data/features/segmentation/
│                           recommendation/evaluation/explainability)
└── tests/                  test suite
```

---

## 8. Governing constraints

Carried from `CLAUDE.md` — these are binding on every later phase:

- `data/raw/` is immutable; all cleaning is explicit and reproducible (§8).
- Temporal leakage control is mandatory for recommendation evaluation (§9).
- Segmentation must be evaluated **both** with and without demographics (§10).
- The Teachers sheet is an experiment with a documented keep/drop decision (§11).
- Recommendation method is selected from experimental evidence across at least
  five baselines (§13); hybrid weights must be justified, not asserted (§14).
- Every recommendation carries an explanation consistent with its actual score (§16).
- Email is never a modelling feature; learners are anonymised in the UI (§17).
- The app loads persisted artifacts; it never retrains on startup (§21).
- No Docker (§20). No novel algorithms (§7). No fabricated results (§6).
