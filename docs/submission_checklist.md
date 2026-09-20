# Submission Checklist

**Project:** Student Segmentation and Personalized Course Recommendation System for EduPro
**Model version:** `edupro-1.0.0` · artifact set `b658773c9db8`
**Date:** 20 September 2026
**Source data:** SHA-256 `ed555e4613e6a210b73af0d4f64e34bd43cb59650041e2bd05f8a8ffbf5d8cc0`, verified unchanged

This checklist is written for an assessor. Every row names **where to look** and, where
possible, **a command that checks it** — so nothing here has to be taken on trust.

---

## How to verify this submission in five minutes

```bash
py -3.13 -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -e . --no-deps

python -m pytest tests -q                    # 385 passed
python scripts/verify_reproducibility.py     # 8 stored results recomputed exactly
python scripts/verify_paper_claims.py        # 96 document figures vs the artifacts
streamlit run app/streamlit_app.py           # the dashboard
```

If those four commands succeed, every claim in the table below has been executed
rather than asserted.

---

## 1. Official deliverables

| # | Deliverable | Location | Status |
| --- | --- | --- | --- |
| 1 | **Research paper** | [`docs/research_paper.md`](research_paper.md), [`.html`](research_paper.html) | ✅ 25 sections, 11,353 words, 33 tables |
| 2 | **Streamlit dashboard** | [`app/streamlit_app.py`](../app/streamlit_app.py) | ✅ 7 pages, screenshots in [`docs/screenshots/`](screenshots/) |
| 3 | **Executive summary** | [`docs/executive_summary.md`](executive_summary.md) | ✅ 13 topics, 3,945 words |

---

## 2. Official requirements

Full matrix with evidence: [`docs/REQUIREMENTS_TRACEABILITY.md`](REQUIREMENTS_TRACEABILITY.md).

| Group | Requirement | Where | Status |
| --- | --- | --- | --- |
| **A** | Learner-level aggregation, profiles, engagement and preference features | `src/edupro/features/learner.py` | ✅ Verified |
| **B** | All 11 named features (age, gender, total courses, avg per category, frequency, preferred category, preferred level, avg rating, avg spending, diversity, learning depth) | Paper §9.1 | ✅ All implemented |
| **C** | Normalisation, categorical encoding, sparse-enrollment handling | `segmentation/representations.py`, 4-tier routing | ✅ Verified |
| **D** | K-Means (primary), hierarchical (validation), elbow, silhouette, cluster profiling, interpretable descriptions | Paper §10–11 | ✅ Verified — hierarchical reported as a **negative result** |
| **E** | Content-based, similar learners, cluster popularity, rating-weighted, personalised ranking, cold-start | Paper §12–14 | ✅ All six evaluated |
| **F** | Silhouette, intra-cluster similarity, recommendation precision, engagement lift | Paper §15–16 | ✅ Precision reported against its ceiling; lift labelled a **proxy** |
| **G** | Dashboard: profile explorer, cluster visualisation, recommendations, segment comparison, learner selection, assigned segment, learning paths, category/level filters | 7 pages | ✅ All eight capabilities |

**Requirements investigated but not retained** are individually accounted for in
[`research/ARCHITECTURE_FREEZE.md`](../research/ARCHITECTURE_FREEZE.md) §"Official
requirements evaluated but not retained" — how each was investigated, why it was not
promoted, and where it is still addressed. None was skipped.

---

## 3. Engineering standard (`CLAUDE.md`)

| § | Requirement | Evidence | Status |
| --- | --- | --- | --- |
| 6 | No fabricated metrics, citations or results | 96 document figures machine-checked against artifacts | ✅ |
| 6 | Failed experiments not hidden | Gap statistic failure, RobustScaler artefact, hierarchical negative result, 4 refuted predictions — all in the paper | ✅ |
| 7 | No novel algorithm invented | Established methods throughout | ✅ |
| 8 | Raw data immutable | Checksum verified before and after every run | ✅ |
| 9 | Leakage detection | 6 controls; verified by **experiment**, not inspection | ✅ |
| 10 | Variant A vs B decided on evidence | ARI 1.000 — identical partitions | ✅ |
| 11 | Teachers sheet as an explicit experiment | 3 experiments; rejected on evidence | ✅ |
| 13 | ≥5 recommendation baselines | 11 evaluated | ✅ |
| 14 | Hybrid weights justified, not asserted | 400-sample simplex search + ablation | ✅ |
| 15 | Sparse-user tiers | 4 tiers; boundaries from the data | ✅ |
| 16 | Explanations match scoring logic | 30,000 verified exhaustively | ✅ |
| 17 | Privacy; no email as a feature | PII dropped at ingestion; 858 real values searched, 0 found | ✅ |
| 18–19 | Modular source; inference without notebooks | `src/edupro/` + two CLI scripts | ✅ |
| 20 | **No Docker** | No Dockerfile or compose file; asserted by test | ✅ |
| 21 | App loads artifacts, never retrains | `st.cache_resource`; no ML call under `app/` (tested) | ✅ |
| 22 | Artifacts version-consistent | Manifest with library versions + per-file hashes | ✅ |
| 23 | Tests incl. failure and edge cases | 385 tests | ✅ |
| 24 | Commits at phase boundaries | 13 commits, one per phase | ✅ |
| 25 | Decision log, experiment log, ADRs | 62 decisions, 29 experiments, 6 ADRs | ✅ |
| 27 | Phase reports with PASS/FAIL and evidence | 11 reports in `research/` | ✅ |

---

## 4. Repository hygiene

| Check | Method | Result |
| --- | --- | --- |
| No credentials or secrets | Regex scan for API keys, tokens, private keys across 190 tracked files | ✅ **0 found** |
| No personal data | 858 real names/emails searched byte-wise, whole-word | ✅ **0 found** |
| No local user paths | Scan for `C:\Users\…`, `/home/…`, `/Users/…` | ✅ **0 found** |
| No caches or temp files tracked | `git ls-files` vs `__pycache__`, `.pyc`, `.pytest_cache`, `.ipynb_checkpoints`, `*.log`, `*.tmp`, `*.bak` | ✅ **0 tracked** |
| `.gitignore` correct | Reviewed; covers Python, venvs, caches, IDE/OS, Streamlit secrets, derived data | ✅ |
| No empty placeholder directories | `experiments/` and `reports/figures/` were declared but never written to — removed in Phase 6D | ✅ |
| Repository size | `git ls-files` total | ✅ 14 MB |
| Raw data tracked and immutable | `data/raw/` is deliberately version-controlled | ✅ |

**Two working-directory files are deliberately left untracked** and are the user's own
originals, byte-identical to the canonical copies in the repository:

| File | Canonical copy | Action |
| --- | --- | --- |
| `EduPro Online Platform.xlsx` (root) | `data/raw/…` | Git-ignored; not deleted — it is the user's source file |
| `project offical detail.pdf` (root) | `references/official/…` | Git-ignored; not deleted |
| `claude.md.txt` (root, 0 bytes) | — | Git-ignored; see open item below |

---

## 5. Verification instruments

Each is a script an assessor can run.

| Instrument | Command | Result |
| --- | --- | --- |
| Test suite | `python -m pytest tests -q` | **385 passed** |
| Reproducibility | `python scripts/verify_reproducibility.py` | **8 of 8 exact** |
| Document traceability | `python scripts/verify_paper_claims.py` | **96 of 96 figures match** |
| Adversarial audit | `python scripts/adversarial_audit.py` | **59 probes, 0 fail** |
| Dashboard smoke test | `python scripts/app_smoke_test.py` | **20 probes, 0 fail** |
| Screenshot regeneration | `python scripts/capture_screenshots.py` | 6 images |
| Paper rendering | `python scripts/build_paper.py` | HTML submission copy |

---

## 6. Honesty review

The single most important thing an assessor should check about this submission.

| Claim type | Position taken |
| --- | --- |
| Recommendation accuracy | **Not demonstrated.** 0 of 11 methods beat random; stated in the README, the abstract, the executive summary's opening, and every recommendation footer in the app |
| Engagement / completion impact | **Explicitly refused.** EduPro records no such measure; the executive summary says so in those words |
| Engagement Lift | Reported as a **proxy**, always beside random's own value (1.084 vs 1.046) |
| Segmentation quality | Demonstrated — but described as a **course-level split**, not behavioural personas |
| Hierarchical validation | Reported as a **negative result** (ARI 0.019) |
| Gap statistic | Reported as a **failed instrument** |
| Demographic gap | Reported and bounded, not dismissed and not amplified |

Enforced mechanically: nine forbidden causal-claim patterns are tested for across both
written deliverables, and the patterns were themselves verified able to fail against
six synthetic violating sentences.

---

## 7. Known open items

Carried honestly into submission rather than quietly closed. Closed items are struck through rather than deleted, so the record of what was open remains.

| # | Item | Impact | Owner |
| --- | --- | --- | --- |
| ~~1~~ | ~~Authorship unconfirmed~~ — **resolved 20 September 2026.** The author is **Kartik** (`kartikshreekumar2006@gmail.com`), confirmed by the project owner and matching the git identity on all commits. | ✅ Closed | — |
| 2 | `claude.md.txt` at the repository root is empty (0 bytes) and git-ignored | Cosmetic; left because deleting a user file is not the agent's call | **User decision** |
| 3 | Root-level duplicates of the source workbook and brief | None — git-ignored, byte-identical to the tracked copies | **User decision** |
| ~~4~~ | ~~Not yet deployed publicly~~ — **resolved 20 September 2026.** Live at the URL above. The first attempt failed on a line-ending/integrity mismatch, fixed and documented in `docs/deployment_guide.md` §6.1. | ✅ Closed | — |
| 5 | Gender gap is disclosed in the paper and summary but **not surfaced in the dashboard** | Deliberate; whether a fairness panel belongs in a stakeholder dashboard is a product decision | **User decision** |
| 6 | No PDF of the executive summary | The paper has an HTML copy that prints to PDF; the summary is Markdown only | Optional |
| 7 | Artifact staleness is not automated | The manifest detects an *inconsistent* artifact set, not an *old* one | Future work |

---

## 8. Final state

| | |
| --- | --- |
| Phases completed | 0, 1, 2, 3A, 3B, 4, 5A, 5B, 6A, 6B, 6C, 6D |
| Commits | 13, one per phase boundary |
| Tests | 385 |
| Decisions recorded | 62 |
| Experiments logged | 29, including failures |
| References verified | 40 |
| Documentation | 35 Markdown files |
| Source data | Unmodified — checksum verified |
| Pushed to GitHub | ✅ Yes — `Kartikinfinity/edupro-learner-intelligence` |
| Deployed publicly | ✅ <https://edupro-learner-intelligence-pmejbef8znwugts2gwtqik.streamlit.app/> |

---

### Assessor's shortest path

1. Read [`docs/executive_summary.md`](executive_summary.md) — 10 minutes, no technical background needed.
2. Skim [`docs/research_paper.md`](research_paper.md) §16 (Experimental Results) and §21 (Limitations).
3. Run `python -m pytest tests -q` and `python scripts/verify_reproducibility.py`.
4. Run `streamlit run app/streamlit_app.py` and open **Model Analytics**.

Step 4 shows every measured number in the project, loaded from the experiment
artifacts, with the random baseline as a row in the table.
