# Phase 6D — Repository Polish — COMPLETE

**Phase:** 6D — GitHub / repository polish
**Date:** 20 September 2026
**Decision:** ✅ **PASS**
**Repository:** 190 tracked files, 14 MB, 373 tests
**Next phase:** public deployment (**not started; awaiting explicit instruction**)

---

## 1. Objective

Make the repository submission-ready: review every folder, finalise the README with
24 required sections, clean temporary files, caches, accidental outputs, credentials,
secrets and personal data, verify `.gitignore`, and produce a submission checklist.

**Constraint observed:** do not claim anything that cannot be demonstrated. Every
figure in the README is either traced to an artifact or checked by a test.

---

## 2. Cleaning — what was found

### 2.1 What was already clean

| Check | Result |
| --- | --- |
| Caches, `.pyc`, `.pytest_cache`, `.ipynb_checkpoints` tracked | **0** — present on disk, correctly ignored |
| Virtual environment or build output tracked | **0** |
| Credentials, API keys, tokens, private keys | **0** across all tracked files |
| Local user paths (`C:\Users\…`, `/home/…`) | **0** |
| Docker artifacts | **0** |

### 2.2 Personal data — one hit, investigated, false positive

A byte-wise scan of 858 real names and email addresses across every tracked file
returned **one hit**: the string `wwest` in
`notebooks/03_segmentation_experiments.ipynb`.

**[Finding]** It is a five-character substring occurring by chance inside the
base64 of an embedded PNG — not a leak. A re-scan requiring **whole-word** matches
for names, and exact matches for emails, returned **zero** across 190 files.

**[Interpretation]** Worth recording rather than quietly dropping: short PII values
make substring scanning noisy against binary blobs, and a scanner that reports a
coincidence as a leak trains its reader to ignore it. The whole-word matcher is now
what `tests/test_repository.py` uses, with the false positive documented in the
test's docstring so the next person does not re-derive it.

### 2.3 Empty placeholder directories — removed

**[Finding]** `experiments/` and `reports/figures/` contained nothing but
`.gitkeep`. Tracing back, `research/experiment_plan.md` (Phase 1) had planned
experiment results into `experiments/<EXP-ID>/results.json` and figures into
`reports/figures/` — but the implementation consolidated everything under
`artifacts/`, and the two directories were never written to.

This is a **plan-versus-implementation divergence that was never reconciled**. A
reviewer cloning the repository would find two empty directories and reasonably
wonder what failed to generate.

**Resolved by:**

- Removing `EXPERIMENTS_DIR`, `REPORTS_DIR` and `FIGURES_DIR` from
  `edupro.config`, from `ensure_directories()`, from the layout test and from
  `.gitignore`.
- Deleting the directories.
- Adding a note to `research/experiment_plan.md` pointing readers at where the
  outputs actually went. **The plan itself is left as written** — it is a record of
  what was planned, not a document to retrofit.
- Removing the now-redundant `notebooks/.gitkeep`.

A new test, `test_no_empty_placeholder_directories_remain`, prevents this
reappearing.

### 2.4 Notebook outputs — kept, deliberately

The four notebooks carry 3.6 MB of embedded output images, and every one of those
figures is also committed as a PNG under `artifacts/`.

**[Decision]** Kept. For an internship submission the reviewer may never run the
code, and a notebook that renders its results inline on GitHub is worth more than
3.6 MB of saved space in a 14 MB repository. The trade-off is recorded in the
submission checklist so the choice is visible rather than accidental.

### 2.5 Root-level files — left alone, by design

| File | Status |
| --- | --- |
| `EduPro Online Platform.xlsx` | Byte-identical to `data/raw/…`; git-ignored |
| `project offical detail.pdf` | Byte-identical to `references/official/…`; git-ignored |
| `claude.md.txt` (0 bytes) | Git-ignored |

All three are the user's own files. They are already excluded from the repository,
so they cost the submission nothing. **Deleting a user's source files is not the
agent's call**, so they are listed as open items for the user's decision instead.

---

## 3. README

Rewritten with all **25 required H1 sections** (24 specified plus `License`),
verified by a parametrised test rather than by eye.

**[Decision] The headline limitation appears before any feature.** A README that
opens with capabilities and mentions "does not beat random" in a Limitations section
near the end would be technically complete and practically misleading. A test
asserts the finding appears in the first 1,800 characters.

Three properties are enforced by test rather than trusted:

| Property | Test |
| --- | --- |
| Every referenced image exists | `test_readme_images_exist` |
| Every internal link resolves | `test_readme_internal_links_resolve` |
| The stated test count matches `pytest --collect-only` | `test_readme_test_count_matches_reality` |
| No unsupported causal claim is asserted | `test_readme_makes_no_unsupported_claim` |

The last reuses the Phase 6C refinement: a forbidden phrase counts only when
*asserted*, so the README may name a claim in order to refuse it.

---

## 4. Screenshots — generated, not hand-taken

The README requires a Screenshots / Demo section. Screenshots are the part of a
README most likely to go stale, because they are usually captured once by hand.

`scripts/capture_screenshots.py` regenerates all six from the running app in one
command, driving headless Chrome rather than adding a ~130 MB browser-automation
dependency for six images.

**[Finding]** The first capture of a session failed — Chrome wrote an 11 KB blank
page while Streamlit was still rendering. The script now retries once with a longer
virtual-time budget and validates each file against a minimum rendered size, so a
blank capture is reported rather than silently committed.

| Page | Size |
| --- | --- |
| Executive Overview | 178 KB |
| Learner Profile | 144 KB |
| Recommendations | 184 KB |
| Segment Intelligence | 145 KB |
| Cluster Visualization | 247 KB |
| Model Analytics | 192 KB |

---

## 5. New tests

`tests/test_repository.py` — **44 tests** that keep the repository clean rather
than merely observing that it is clean today:

| Group | What it prevents |
| --- | --- |
| Cruft, venv and build output | Caches or environments being committed later |
| Secrets | Credentials, tokens or private keys entering the history |
| Personal data | Real names or emails appearing in any tracked file |
| Local paths | `C:\Users\…` leaking into a committed file |
| Layout | Dead path constants or empty placeholder directories returning |
| README | Missing sections, broken links, missing images, a stale test count |
| Checklist and screenshots | Missing or blank |

---

## 6. Validation

| Check | Result |
| --- | --- |
| Full test suite | ✅ **373 passed** (329 + 44) |
| Reproducibility | ✅ 8 of 8 exact |
| Document traceability | ✅ 96 of 96 figures |
| README sections | ✅ 25 of 25, tested |
| README links and images | ✅ all resolve |
| Tracked files | 190 · 14 MB |
| Secrets / PII / local paths | ✅ 0 / 0 / 0 |
| Raw workbook SHA-256 | ✅ `ed555e46…8cc0` unchanged |
| Docker | ✅ none |
| Pushed to GitHub | ❌ **No** — awaiting explicit instruction |

---

## 7. A correction made in this phase

While updating the statistics table I changed `scripts/` from 18 files to 20 on the
assumption that two scripts had been added since the figure was taken. Re-counting
showed the actual figure was still 18 — `build_paper.py` and
`capture_screenshots.py` were already included. The value was restored to the
measured one.

**[Interpretation]** Small, but exactly the failure mode this project has been
guarding against all along: a number changed by inference rather than measurement.
It is recorded because the README now claims a count that a test verifies, and the
honest account of how that number was arrived at includes the moment it was briefly
wrong.

---

## 8. PASS / FAIL

### ✅ **PASS**

| Criterion | Evidence |
| --- | --- |
| Every folder reviewed | §2 — root, all 14 directories, tracked-file inventory |
| README complete with required sections | 25 of 25, parametrised test |
| Nothing claimed that cannot be demonstrated | Every figure traced or tested; screenshots regenerable |
| Temporary and cache files cleaned | 0 tracked; verified by test |
| Credentials and secrets | 0, verified by test |
| Personal data | 0 whole-word matches across 190 files |
| `.gitignore` verified | Reviewed and updated; stale `reports/` rule removed |
| Source logically organised | Dead directory constants removed; layout matches reality |
| `docs/submission_checklist.md` | Created, with open items disclosed |
| `research/PHASE_6D_COMPLETE.md` | This document |
| Clean final commit | See §9 |

---

## 9. Open items carried into submission

Unchanged from Phase 6C except where noted; all are user decisions rather than
engineering gaps.

| # | Item | Owner |
| --- | --- | --- |
| 1 | **Authorship unconfirmed** — the paper credits *Anushree Menon* from `pyproject.toml`; the git identity is `Kartik <kartikshreekumar2006@gmail.com>` | **User** |
| 2 | `claude.md.txt` (0 bytes, git-ignored) | **User** |
| 3 | Root-level duplicates of the workbook and brief (git-ignored, byte-identical) | **User** |
| 4 | Not yet deployed publicly; not yet pushed to GitHub | Pending instruction |
| 5 | Gender gap disclosed in the paper and summary, not surfaced in the dashboard | **User** |
| 6 | No PDF of the executive summary | Optional |
| 7 | Artifact staleness not automated | Future work |

---

## 10. Stop

Per CLAUDE.md §28, work **stops here**. Nothing has been pushed to GitHub.

🔒 The ML design remains frozen. This phase changed documentation, repository
structure and test coverage; it changed no model behaviour, and the reproducibility
check confirms it.
