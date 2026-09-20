# Submission Checklist

**Project:** Student Segmentation and Personalized Course Recommendation System for EduPro
**Author:** Kartik
**Date:** 20 September 2026
**Model version:** `edupro-1.0.0` · **Artifact set:** `6892a4f9ef27`

**Rule applied:** an item is **PASS** only when this audit reproduced its
evidence. **PARTIAL** means the requirement is met but something material is
worth stating. **FAIL** means it is not met.

**Result: 0 FAIL · 4 PARTIAL · 112 PASS**, across 116 checked items. No PARTIAL is a critical item, so the
project is declared **FINAL** under the stated rule.

Full evidence: [`research/FINAL_AUDIT_REPORT.md`](research/FINAL_AUDIT_REPORT.md).

---

## 1. Official Requirements

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 1.1 | All 43 mandatory requirements traceable to an implementation | **PASS** | Matrix, audit report §1 |
| 1.2 | Dataset fields used as specified (Users, Courses, Transactions) | **PASS** | Re-read from the workbook; O1–O3 |
| 1.3 | All 11 mandated learner features implemented | **PASS** | O5–O15, each located to a source line |
| 1.4 | Teachers sheet treated as opt-in, not assumed | **PASS** | EXP-014; excluded in `model_config.json` |
| 1.5 | Learner-level aggregation | **PASS** | 10,000 interactions → 3,000 profiles |
| 1.6 | Preprocessing: normalise, encode, reduce sparse noise | **PASS** | O18–O20 |
| 1.7 | K-Means clustering | **PASS** | k = 4, seed 42, labels reproduce |
| 1.8 | Hierarchical clustering as validation | **PASS** | Ward + average linkage, ARI reported |
| 1.9 | Elbow and Silhouette for cluster selection | **PASS** | k sweep 2–10, both reported |
| 1.10 | Content-based filtering | **PASS** | Deployed on the `minimal` tier |
| 1.11 | Similar learner profiles | **PASS** | Two variants evaluated |
| 1.12 | Course popularity within cluster | **PASS** | Deployed on `moderate` and `rich` |
| 1.13 | Rating-weighted relevance | **PASS** | Evaluated; blended into the fallback |
| 1.14 | Silhouette Score reported | **PASS** | 0.1946, recomputed exactly |
| 1.15 | Intra-Cluster Similarity reported | **PASS** | 0.4163 |
| 1.16 | Recommendation Precision reported | **PASS** | 0.0424 @10 against a 0.2054 ceiling |
| 1.17 | Engagement Lift **(Proxy)** reported and labelled | **PASS** | 1.084 vs random 1.046, side by side |

## 2. Research Paper

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 2.1 | All 25 required sections present | **PASS** | Plus two appendices |
| 2.2 | Every numeric claim traces to an artifact | **PASS** | 77 values, artifact read first |
| 2.3 | No fabricated figures | **PASS** | 21 figures, all script-generated, all paths resolve |
| 2.4 | Figures visible in the document | **PASS** | Embedded during this audit; HTML carries 21 `<img>` |
| 2.5 | Evidence classes distinguished (observed / model / experiment / interpretation) | **PASS** | "Note on evidence classes" + inline tags |
| 2.6 | Negative result reported, not buried | **PASS** | Stated in the abstract |
| 2.7 | Citations real and resolvable | **PASS** | 39 references with DOIs |
| 2.8 | Limitations section honest | **PASS** | §21, incl. the synthetic-data risk |
| 2.9 | Submission-ready rendering | **PARTIAL** | Markdown + HTML provided; **no PDF is built** — print the HTML to PDF |

## 3. Streamlit

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 3.1 | Learner profile explorer | **PASS** | Page 2, smoke-tested |
| 3.2 | Cluster visualization dashboard | **PASS** | Page 5, smoke-tested |
| 3.3 | Personalized recommendations | **PASS** | Verified on the live URL |
| 3.4 | Segment comparison | **PASS** | Page 6, incl. empty-selection state |
| 3.5 | Learner selection works | **PASS** | Selection changes the rendered profile |
| 3.6 | Assigned segment displayed | **PASS** | Shown live |
| 3.7 | Recommended learning paths displayed | **PASS** | 10 ranked courses with explanations |
| 3.8 | Category and level filtering | **PASS** | 36/36 combinations, 0 violations |
| 3.9 | No ML logic duplicated in the UI | **PASS** | No fitting call anywhere under `app/` |
| 3.10 | No retraining on startup | **PASS** | `st.cache_resource`, once per process |
| 3.11 | Informative empty states | **PASS** | 20/20 smoke probes |
| 3.12 | No fabricated metric displayed | **PASS** | 3 static captions replaced with derived values |

## 4. Executive Summary

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 4.1 | All 13 required topics covered | **PASS** | 3,945 words |
| 4.2 | Written for a non-technical reader | **PASS** | No unexplained jargon |
| 4.3 | Not a copy of the research paper | **PASS** | Different structure and register |
| 4.4 | Every proxy metric identified as a proxy | **PASS** | Stated explicitly |
| 4.5 | No overclaimed business impact | **PASS** | "Cannot be measured with current data" stated plainly |
| 4.6 | Numeric claims trace to artifacts | **PASS** | 19 values verified |

## 5. GitHub

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 5.1 | Repository public and pushed | **PASS** | `Kartikinfinity/edupro-learner-intelligence` |
| 5.2 | README complete (24 sections) | **PASS** | Headline claims re-verified from raw data |
| 5.3 | Working tree clean, `main` in sync | **PASS** | Final `git status` |
| 5.4 | Meaningful phase-tagged commits | **PASS** | 21 commits |
| 5.5 | No cache, temp or OS junk tracked | **PASS** | 195 tracked files, none junk |
| 5.6 | `.gitignore` correct | **PASS** | Raw data deliberately tracked; artifacts selectively tracked |
| 5.7 | No secrets in files or history | **PASS** | 6 patterns, 0 matches; history searched |
| 5.8 | Repository **About** section filled in | **PARTIAL** | Web-UI only; cannot be set from a commit |

## 6. ML Artifacts

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 6.1 | Scaler persisted | **PASS** | `models/scaler.joblib` |
| 6.2 | Clustering model persisted | **PASS** | `models/clusterer.joblib` |
| 6.3 | Feature schema persisted | **PASS** | `models/feature_schema.json` |
| 6.4 | Model configuration persisted | **PASS** | `models/model_config.json` |
| 6.5 | Course representations persisted | **PASS** | `course_vectors.npy`, `course_catalogue.parquet` |
| 6.6 | Recommendation metadata persisted | **PASS** | `popularity.parquet`, `interactions.parquet` |
| 6.7 | Manifest with per-file SHA-256 | **PASS** | 12 files, all verified |
| 6.8 | Library versions recorded and checked at load | **PASS** | Enforced on every startup |
| 6.9 | Artifacts version-consistent with the code | **PASS** | Single `artifact_set_version` across all 12 |
| 6.10 | Artifacts platform-independent | **PASS** | POSIX keys, LF JSON, `.npy` marked binary |

## 7. Tests

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 7.1 | Full suite passes | **PASS** | **385 passed**, 0 failed |
| 7.2 | Data loading and schema validation | **PASS** | 36 tests |
| 7.3 | Feature generation | **PASS** | Covered by the pipeline suite |
| 7.4 | Clustering inference | **PASS** | 37 tests |
| 7.5 | Recommendation inference | **PASS** | 59 tests |
| 7.6 | Filtering | **PASS** | 36/36 combinations audited live |
| 7.7 | Exclusion of already-enrolled courses | **PASS** | 0 violations across 3,000 learners |
| 7.8 | Explanation generation | **PASS** | 30,000 explanations, 0 mismatches |
| 7.9 | Artifact loading and integrity | **PASS** | 56 production tests |
| 7.10 | App startup and UI workflows | **PASS** | 26 app tests + 20 smoke probes |
| 7.11 | Failure and edge cases | **PASS** | 24 regression tests for real past defects |
| 7.12 | Document claims machine-checked | **PASS** | 74 paper tests, 44 repository tests |

## 8. Documentation

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 8.1 | Decision log | **PASS** | 77 numbered decisions, incl. one annotated as wrong |
| 8.2 | Experiment log | **PASS** | Every experiment recorded, failures included |
| 8.3 | Architecture decision record | **PASS** | `research/architecture_decision_record.md` |
| 8.4 | Technical architecture | **PASS** | `docs/technical_architecture.md` + diagram |
| 8.5 | Architecture freeze | **PASS** | 18 sections, 12 named decisions |
| 8.6 | Requirements traceability | **PASS** | `docs/REQUIREMENTS_TRACEABILITY.md` + audit §1 |
| 8.7 | Phase reports with PASS/FAIL | **PASS** | 15 phase reports |
| 8.8 | Deployment guide | **PASS** | Six areas + failure post-mortem |
| 8.9 | Failed experiments documented | **PASS** | Rejected representations and methods retained |

## 9. Deployment

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 9.1 | Publicly deployed and reachable | **PASS** | Opened in a browser |
| 9.2 | Readiness audit | **PASS** | **25 of 25**, 0 warnings |
| 9.3 | Serves the committed artifact set | **PASS** | Sidebar reports `6892a4f9ef27` |
| 9.4 | No secrets required | **PASS** | No `st.secrets` in the app |
| 9.5 | Deterministic startup | **PASS** | Two loads agree on 3,000 labels |
| 9.6 | Dependencies compatible and pinned | **PASS** | 11 packages, exact versions |
| 9.7 | Repository-safe relative paths | **PASS** | No absolute path literals |
| 9.8 | No Docker | **PASS** | No container or process-manager file |
| 9.9 | Deployment failures recorded honestly | **PASS** | Three failures and one wrong diagnosis, all documented |

## 10. Reproducibility

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 10.1 | Raw dataset version-controlled and immutable | **PASS** | Hash matches config and manifest |
| 10.2 | Single seed, recorded | **PASS** | `RANDOM_SEED = 42` |
| 10.3 | Stored metrics recompute exactly | **PASS** | **8 of 8** to six decimal places |
| 10.4 | Retraining reproduces the model | **PASS** | Identical segments and tiers after a retrain this phase |
| 10.5 | Environment reproducible | **PASS** | `requirements.txt` + `requirements.lock.txt` |
| 10.6 | Runs without opening a notebook | **PASS** | Two commands, §11 of the freeze record |
| 10.7 | Reproduced on a second machine | **PARTIAL** | Reproduced across two *platforms* (Windows dev, Linux deploy), but not re-run end-to-end on independent hardware |

## 11. Privacy

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 11.1 | No name or email in any served artifact | **PASS** | 6,000 real values searched, **0 hits** |
| 11.2 | Email never a modelling feature | **PASS** | Absent from the 25-column model input |
| 11.3 | Learners anonymised in the UI | **PASS** | Pseudonymous `UserID` throughout |
| 11.4 | PII dropped at ingestion | **PASS** | Cannot reach a downstream frame by accident |
| 11.5 | Minimal profile exposure | **PASS** | 13 fields, no identifying data |
| 11.6 | No secrets committed | **PASS** | Files and full history searched |
| 11.7 | Public error disclosure limited | **PASS** | `showErrorDetails = "type"` |

## 12. Final Validation

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 12.1 | Adversarial audit | **PASS** | **59 probes, 59 pass** |
| 12.2 | Application smoke test | **PASS** | **20 probes, 20 pass** |
| 12.3 | Deployment readiness | **PASS** | **25 checks, 25 pass** |
| 12.4 | Leakage controls hold under attack | **PASS** | L1–L5 verified independently |
| 12.5 | No fabricated metric | **PASS** | 96 document claims traced |
| 12.6 | No hardcoded model output | **PASS** | 3 static captions fixed |
| 12.7 | No already-enrolled recommendation | **PASS** | 0 across all 3,000 learners |
| 12.8 | Explanations match the scoring logic | **PASS** | 0 mismatches in 30,000 |
| 12.9 | All audit defects fixed | **PASS** | 9 found, 9 fixed |
| 12.10 | Recommendation performance demonstrated | **PARTIAL** | **The system is built, tested and deployed; its ranking is not measurably better than random on this data.** This is a finding, not an unfinished item — see §12.1 of the audit report |

---

## The four PARTIAL items, stated plainly

| Item | What it means | Why it does not block submission |
| --- | --- | --- |
| **2.9** No PDF of the paper | Markdown and HTML are provided | A PDF is one browser print away; the content is complete |
| **5.8** Empty GitHub About section | Description and topics are blank | Settable only through the GitHub web UI, not from a commit |
| **10.7** Not re-run on independent hardware | Reproduced across Windows and Linux, one codebase | Cross-platform reproduction is the stronger half of this check |
| **12.10** Recommendation not better than random | The measured outcome is negative | Reporting it is the requirement; hiding it would be the failure |

---

## Declaration

All **critical** items are **PASS**. The four PARTIAL items are packaging or
disclosure matters, not defects, and each is stated above rather than rounded up.

**Status: FINAL.**
