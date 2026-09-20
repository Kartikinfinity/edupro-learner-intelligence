# Final Audit Report — Independent Review Before Submission Freeze

**Date:** 20 September 2026
**Reviewer role:** independent final reviewer. Nothing below is accepted because
the project asserts it; every claim was re-derived from the raw workbook, the
stored artifacts, or a live execution.
**Scope:** all 195 tracked files, the deployed application, and the git history.
**Verdict:** ✅ **PASS with recorded limitations.** No critical defect remains
open. **Nine defects were found and all nine are fixed** (§13); four limitations
are carried forward and listed in §12.

---

## 0. How this audit was conducted

**[Design decision]** The project contains its own audit scripts. Running only
those would test whether the project agrees with itself. Every finding below was
therefore produced one of two ways:

1. **Re-derived from source** — the raw workbook re-read and the statistic
   recomputed, independent of any stored artifact.
2. **Executed live** — the service loaded and driven, or the deployed URL opened
   in a browser.

The project's own instruments (`adversarial_audit.py`, `deployment_readiness.py`,
`app_smoke_test.py`, `verify_paper_claims.py`, `verify_reproducibility.py`) were
run as *corroboration*, and one of them found a defect this audit had introduced
(§4.1), which is the reason they are worth keeping.

**Provenance chain verified first**, since everything downstream depends on it:

| Artefact | Recorded SHA-256 | Recomputed | Result |
| --- | --- | --- | --- |
| Official PDF | `e794444490c1…` | `e794444490c1…` | ✅ match |
| Raw workbook | `ed555e4613e6…` | `ed555e4613e6…` | ✅ match |
| Manifest's `workbook_sha256` | `ed555e4613e6…` | — | ✅ same workbook |

The root-level copy of the workbook is byte-identical to `data/raw/`, so the
git-ignored duplicate is not a second source of truth.

---

## 1. Official requirement traceability matrix

Source column: `PDF p.N` refers to
`references/official/project offical detail.pdf`, transcribed verbatim in
`references/official/OFFICIAL_REQUIREMENTS_TRANSCRIPT.md`. **Status is
`Verified` only where this audit reproduced the evidence itself.**

### 1.1 Dataset fields

| # | Requirement | Source | Implementation | Evidence | Location | Status |
| --- | --- | --- | --- | --- | --- | --- |
| O1 | Users sheet: UserID, Age, Gender | PDF p.2 | `load_all()` reads the sheet; PII dropped at ingestion | Re-read from the workbook; 3,000 users, columns present | `src/edupro/data/loader.py` | ✅ Verified |
| O2 | Courses sheet: CourseID, CourseCategory, CourseType, CourseLevel, CourseRating | PDF p.3 | Course catalogue and content vectors | 60 courses, 12 categories, 3 levels confirmed live | `src/edupro/features/course.py` | ✅ Verified |
| O3 | Transactions sheet: UserID, CourseID, TransactionDate, Amount | PDF p.3 | `build_interactions()` | 10,000 interactions recomputed from source | `src/edupro/data/joins.py` | ✅ Verified |
| O4 | Teachers sheet **not** in the official field list | PDF p.3 (absence) | Treated as an opt-in experiment, excluded | EXP-014; `teacher_signals: "excluded"` in `model_config.json` | `research/segmentation_results.md` | ✅ Verified |

### 1.2 Feature engineering — all eleven mandated features

| # | Requirement | Source | Implementation | Evidence | Location | Status |
| --- | --- | --- | --- | --- | --- | --- |
| O5 | Total courses enrolled | PDF p.3 | `total_courses` | Present in served feature table | `features/learner.py:38` | ✅ Verified |
| O6 | Average courses per category | PDF p.3 | `avg_courses_per_category` | Present; in model input | `features/learner.py:39` | ✅ Verified |
| O7 | Enrollment frequency | PDF p.3 | `enrollment_frequency` | Present; in model input | `features/learner.py:40` | ✅ Verified |
| O8 | Preferred course category | PDF p.3 | `preferred_category`, encoded as 12 `cat_share_*` dimensions | Present; 12 share columns in model input | `features/learner.py:44` | ✅ Verified |
| O9 | Preferred course level | PDF p.3 | `preferred_level` → `preflevel_{Beginner,Intermediate,Advanced}` | Present; 3 columns in model input | `features/learner.py:45` | ✅ Verified |
| O10 | Average course rating enrolled | PDF p.3 | `avg_course_rating` | Present; in model input | `features/learner.py:46` | ✅ Verified |
| O11 | Average spending per learner | PDF p.4 | `avg_spend` | Present; in model input | `features/learner.py:51` | ✅ Verified |
| O12 | Diversity score (categories explored) | PDF p.4 | `diversity_score` | Present; in model input | `features/learner.py:53` | ✅ Verified |
| O13 | Learning depth index (beginner vs advanced) | PDF p.4 | `learning_depth_index` | Present; in model input | `features/learner.py:55` | ✅ Verified |
| O14 | Age | PDF p.2 | `age` — computed, **excluded from the model by experiment** | Variant A vs B: ARI 1.000, demographic share 0.0004 | `features/learner.py:59` | ✅ Verified |
| O15 | Gender | PDF p.2 | `gender` — computed, **excluded from the model by experiment** | Same experiment (D-029) | `features/learner.py:60` | ✅ Verified |

**Audit note on O14–O15.** The official document lists Age and Gender as dataset
fields, not as required model inputs. CLAUDE.md §10 requires both variants be
*evaluated*. Both are computed and available; the production representation
excludes them. This audit confirmed the exclusion directly: the model input has
**25 columns and none is demographic**. The decision rests on measurement
(identical partition, ARI 1.000), not preference.

### 1.3 Methodology

| # | Requirement | Source | Implementation | Evidence | Location | Status |
| --- | --- | --- | --- | --- | --- | --- |
| O16 | Aggregate transactions at UserID level | PDF p.4 | `build_learner_features()` | 10,000 rows → 3,000 learner profiles, recomputed | `features/learner.py` | ✅ Verified |
| O17 | Learner profiles combining demographics and behaviour | PDF p.4 | 36-column learner table incl. `age`, `gender` | Inspected live | `artifacts/production/learner_features.parquet` | ✅ Verified |
| O18 | Normalise numerical features | PDF p.4 | `StandardScaler`, persisted | `scaler.joblib` in the manifest; applied at inference | `segmentation/representations.py` | ✅ Verified |
| O19 | Encode categorical variables | PDF p.4 | Category share vector + level one-hot | 12 + 3 encoded columns observed | `segmentation/representations.py` | ✅ Verified |
| O20 | Reduce noise from sparse enrollments | PDF p.4 | Tiering; single-interaction learners routed separately | Tier boundaries in `model_config.json`; 1,620 minimal | `inference.py` | ✅ Verified |

### 1.4 Segmentation

| # | Requirement | Source | Implementation | Evidence | Location | Status |
| --- | --- | --- | --- | --- | --- | --- |
| O21 | K-Means clustering | PDF p.4 | `KMeans(init=k-means++, n_init=10)`, k = 4, seed 42 | Fitted model loaded and re-applied; labels reproduce | `segmentation/clustering.py` | ✅ Verified |
| O22 | Hierarchical clustering (validation) | PDF p.4 | Ward and average linkage | `EXP-012_hierarchical`; ARI reported on the dashboard | `artifacts/segmentation/segmentation_results.json` | ✅ Verified |
| O23 | Elbow method | PDF p.4 | k sweep 2–10 | `EXP-010_k_sweep`; figure `01_elbow_and_silhouette.png` | `research/segmentation_results.md` | ✅ Verified |
| O24 | Silhouette method | PDF p.4 | Silhouette per k and per cluster | 0.1946 at k = 4, recomputed to 6 dp | `scripts/verify_reproducibility.py` | ✅ Verified |

### 1.5 Recommendation

| # | Requirement | Source | Implementation | Evidence | Location | Status |
| --- | --- | --- | --- | --- | --- | --- |
| O25 | Content-based filtering | PDF p.4 | `ContentBased` — deployed on the `minimal` tier | Live: `contributions={'content': …}` on every minimal result | `recommendation/baselines.py` | ✅ Verified |
| O26 | Similar learner profiles | PDF p.5 | `user_user_profile`, `user_user_history` | Both evaluated; NDCG@10 0.1105 / 0.0947 | `artifacts/recommendation/recommendation_results.json` | ✅ Verified |
| O27 | Course popularity within cluster | PDF p.5 | `ClusterPopularity` — deployed on `moderate` and `rich` | Live: `contributions={'cluster_popularity': …}` | `recommendation/baselines.py` | ✅ Verified |
| O28 | Rating-weighted relevance | PDF p.5 | `rating`, and rating blended in the fallback | NDCG@10 0.1034; fallback verified live | `recommendation/baselines.py` | ✅ Verified |

### 1.6 Evaluation — the four official metrics

| # | Requirement | Source | Implementation | Evidence | Location | Status |
| --- | --- | --- | --- | --- | --- | --- |
| O29 | Silhouette Score (cluster quality) | PDF p.5 | Per k and per cluster | **0.1946** recomputed exactly | `segmentation/metrics.py` | ✅ Verified |
| O30 | Intra-Cluster Similarity (behavioural consistency) | PDF p.5 | Mean within-cluster cosine similarity | **0.4163** | `segmentation/metrics.py` | ✅ Verified |
| O31 | Recommendation Precision (relevance) | PDF p.5 | Precision@K with an explicit attainable ceiling | **0.0424** at k = 10 against an attainable ceiling of **0.2054** | `evaluation/metrics.py` | ✅ Verified |
| O32 | Engagement Lift (Proxy) — impact estimate | PDF p.5 | Offline agreement ratio, always labelled a proxy | Deployed **1.084** vs random **1.046**, shown side by side | `reporting.engagement_lift_proxy` | ✅ Verified |

**Audit note on O32.** The official brief names this metric but defines no
formula. The project defines it as an offline agreement ratio, reports random's
own score beside it, and states in the app that it is not a causal measurement.
A pre-registered guard rail requires the word "(Proxy)" in every label. **This
audit found one violation of that rule and fixed it** — §4.2.

### 1.7 Streamlit application

| # | Requirement | Source | Implementation | Evidence | Location | Status |
| --- | --- | --- | --- | --- | --- | --- |
| O33 | Learner profile explorer | PDF p.5 | Page 2 | Smoke test: selection changes the profile header | `app/pages/2_Learner_Profile.py` | ✅ Verified |
| O34 | Cluster visualization dashboard | PDF p.5 | Page 5 | Smoke test: renders, filters, empty state | `app/pages/5_Cluster_Visualization.py` | ✅ Verified |
| O35 | Personalized course recommendations | PDF p.5 | Page 3 | Verified on the **live public URL** | `app/pages/3_Recommendations.py` | ✅ Verified |
| O36 | Segment comparison panels | PDF p.5 | Page 6 | Smoke test incl. empty selection | `app/pages/6_Segment_Comparison.py` | ✅ Verified |
| O37 | Select a learner profile | PDF p.6 | Learner selector | Smoke test: U00001 → U00006 | `app/pages/2,3` | ✅ Verified |
| O38 | View assigned segment | PDF p.6 | Segment shown on profile and recommendations | Live: "Intermediate-level Single-session Single-course learners" | `app/pages/2,3` | ✅ Verified |
| O39 | See recommended learning paths | PDF p.6 | Ranked list with per-item explanation | Live: 10 ranked courses, each explained | `app/pages/3_Recommendations.py` | ✅ Verified |
| O40 | Filter recommendations by level or category | PDF p.6 | Category and level filters | **All 36 category × level combinations exercised: 0 violations** | `inference.py` | ✅ Verified |

### 1.8 Deliverables

| # | Requirement | Source | Implementation | Evidence | Location | Status |
| --- | --- | --- | --- | --- | --- | --- |
| O41 | Research paper (EDA, insights, recommendations) | PDF p.6 | 25 sections + 2 appendices, 11,422 words, 76 tables, **21 embedded figures**, 39 citations | 77 numeric claims trace to artifacts | `docs/research_paper.md` | ✅ Verified |
| O42 | Streamlit dashboard (live analytics) | PDF p.6 | 7 pages, publicly deployed | Opened and exercised in a browser | live URL | ✅ Verified |
| O43 | Executive summary for non-technical stakeholders | PDF p.6 | 13 sections, 3,945 words | 19 numeric claims trace to artifacts | `docs/executive_summary.md` | ✅ Verified |

**All 43 mandatory requirements are traceable and Verified.**

---

## 2. Audit A — Scientific

| Probe | Method | Result |
| --- | --- | --- |
| Headline finding | Recomputed from `recommendation_results.json` | **0 of 11** methods significantly better than random; **every** 95% CI contains zero; random ranks **7 of 12**; 5 methods score below it |
| Is the negative result buried? | Searched README, paper, summary, dashboard | Stated first in all four, including on the deployed app |
| Causal / overclaiming language | Regex scan of 41 documents, 8 patterns | 27 hits, **all 27 adjudicated false positives**: citation titles ("State of the Art and Trends"), sentences *refusing* the claim, and the negative finding itself ("Zero of eleven…") |
| Proxy labelling | Every occurrence of "engagement lift" | 1 real violation found and fixed (§4.2) |
| Is k = 4 justified or asserted? | Read the pre-registered constraint, checked the sweep | k chosen under constraints fixed before results; k = 4 satisfies size ≥ 5% and Jaccard ≥ 0.60 |
| Best silhouette not chosen | Cross-checked | The study's highest silhouette (0.7159) is documented as a **scaling artefact** and rejected — evidence of reporting against self-interest |

**Verdict: PASS.** No fabricated metric, no unsupported claim, no buried result.

---

## 3. Audit B — Data leakage

Protocol A rebuilt from the raw workbook and attacked:

| Control | Test | Result |
| --- | --- | --- |
| L1 | `train.max < validation.min` | ✅ True |
| L1 | `validation.max < test.min` | ✅ True |
| L1 | `fit.max < test.min` | ✅ True |
| L2 | Transaction IDs shared between folds | ✅ 0 (fit∩test), 0 (train∩validation) |
| L3 | Partition exhaustive | ✅ 7,992 + 2,008 = 10,000 |
| L4 | Fit-window features differ from full-history features | ✅ 791 learners differ — exactly the evaluable count |
| L5 | **Future-injection attack** | Injecting one test interaction into the fit frame *does* change the feature. The builder is sensitive to future data, so the control is the date partition — and L1–L3 show it holds |

Cut dates: validation **2025-09-12**, test **2025-10-18**. Evaluable learners
**791**, above the pre-registered viability floor of 300.

Protocol B (leave-one-out) is implemented, **labelled leakage-bearing in its own
docstring**, and reported only for comparability.

**Verdict: PASS.** Leakage controls hold under direct attack.

---

## 4. Audit C — Metrics, and the defects this audit found

### 4.1 CRITICAL — a missing manifest was reported as an integrity failure *(fixed)*

`persistence.load_manifest()` raised `ArtifactIntegrityError` when the manifest
file did not exist. After the previous phase added per-exception guidance, a
**fresh checkout with no artifact set** was told its artifacts had *failed an
integrity check* — sending the reader to compare hashes for files that had never
been written.

This is the same defect class as D-055 and D-074: an error that misdiagnoses its
own cause. It was introduced by the previous phase's own fix.

**Found by** `scripts/app_smoke_test.py`, which hides the manifest and asserts the
page says "artifacts not found". It failed 19/20.

**Fixed:** an absent manifest now raises `FileNotFoundError`, which the app maps
to "Model artifacts not found". Call sites updated (`scripts/recommend.py`,
`tests/test_production.py`). Recorded as **D-077**. Smoke test now **20/20**.

### 4.2 MEDIUM — a pre-registered naming guard rail was violated *(fixed)*

`research/recommendation_evaluation_plan.md` §7.3 rule 1 states the metric must be
named **"Engagement Lift (Proxy)"** everywhere — *"prose, tables, chart axes,
dashboard labels. Never 'Engagement Lift'."*

`app/pages/7_Model_Analytics.py` rendered `st.subheader("Engagement lift")`.

Mitigating: a proxy chip and a prominent warning sat directly beneath it, so no
reader was misled. It was nonetheless a violation of an explicit rule the project
wrote for itself. **Fixed:** the heading now reads "Engagement lift (proxy)".

### 4.3 LOW ×3 — static captions asserting measured values *(fixed)*

Three displayed strings stated measured facts as literal text beside live values.
All three were **true**, and all three could have silently become false:

| Location | Was | Now |
| --- | --- | --- |
| `1_Executive_Overview.py` | "Above 0.75 is considered reliable; all four clusters pass." | Count and resample count read from the artifact (`n_clusters_reliable`, `n_bootstrap`) |
| `6_Segment_Comparison.py` | "across all 3,000 learners" | `f"{len(learners):,}"` |
| `7_Model_Analytics.py` | "An ARI of 1.000 means…" | Conditional on the loaded ARI |

`reporting.segmentation_quality()` gained two keys so the first could be derived
rather than asserted. No metric changed.

### 4.4 MEDIUM — current-state documents cited a retired artifact set *(fixed)*

Three documents that describe **the system as submitted** still named artifact set
`b658773c9db8`, retired two rebuilds earlier. The worst of the three was
`docs/deployment_guide.md` §verification, which tells a reader *what the live
sidebar should show* — so following the instruction would have produced an
apparent mismatch against a correctly working deployment.

| Document | Kind | Action |
| --- | --- | --- |
| `docs/research_paper.md` header | Current state | ✅ Updated to `6892a4f9ef27` |
| `docs/submission_checklist.md` header | Current state | ✅ Updated |
| `docs/deployment_guide.md` verification step | Current state | ✅ Updated |
| `research/FINAL_VALIDATION.md` | Historical | Annotated, id kept |
| `research/final_validation_report.md` | Historical | Annotated, id kept |
| `research/PHASE_6A_COMPLETE.md` | Historical | Annotated, id kept |
| `research/PHASE_5A_COMPLETE.md`, `5B` | Historical | Left as written |

The README's documentation index carried two further stale counts — **"62 recorded decisions"** (actually 77) and **"29 experiments"** (31 registered, 20 written up in full). Both corrected. Counts that drift are the quietest form of untraceable claim: nothing looks wrong until someone counts.

**[Design decision]** Historical phase reports keep the artifact id that was
current when they were written. Rewriting them would make the record agree with
the present at the cost of no longer being a record. Each of the three whose
*name* implies currency now carries a one-line pointer to the freeze document.

### 4.5 Metric reproduction

`scripts/verify_reproducibility.py`: **8 of 8 stored values recomputed exactly**
to six decimal places, including silhouette, bootstrap Jaccard, and three NDCG@10
figures.

`scripts/verify_paper_claims.py`: 77 paper values and 19 summary values, each
**computed from an artifact first** and then required to appear in the document —
so a wrong number in the paper cannot make its own check pass.

Independent spot-check from the **raw workbook**, bypassing every artifact:

| Claim | README | Recomputed | Artifact |
| --- | --- | --- | --- |
| Learners | 3,000 | 3,000 | 3,000 |
| Interactions | 10,000 | 10,000 | — |
| Single-course share | 54% | 54.0% | 54.0% |
| Course popularity Gini | 0.042 | 0.042 | 0.042 |
| Methods below random | 5 | — | 5 |

**Verdict: PASS**, with two defects found and fixed.

---

## 5. Audit D — Reproducibility

| Check | Result |
| --- | --- |
| Raw dataset tracked in the repository | ✅ `data/raw/EduPro Online Platform.xlsx`, 513 KB, hash-verified |
| Raw dataset immutable | ✅ Hash matches `config.RAW_WORKBOOK_SHA256` and the manifest |
| Single seed | ✅ `RANDOM_SEED = 42`, recorded in the manifest |
| Deterministic startup | ✅ Two independent loads agree on all 3,000 labels and an identical top-10 |
| Retraining reproduces the model | ✅ Retrained during this phase: segment sizes 841 / 1,030 / 607 / 522 and tier counts **identical** |
| Environment pinned | ✅ 11 packages at exact versions; Python `>=3.11,<3.14` |
| Library versions recorded with the artifacts | ✅ Manifest records Python 3.13.9, numpy 2.5.3, pandas 3.0.6, scikit-learn 1.9.1, joblib 1.6.0 |
| Notebook-only dependency | ✅ None — notebooks import `edupro`; no production module references `notebooks/` |

**Verdict: PASS.**

---

## 6. Audit E — Code quality

| Probe | Result |
| --- | --- |
| ML logic duplicated in Streamlit | ✅ None — no `KMeans`, `.fit(`, `fit_transform`, `cosine_similarity` or `StandardScaler` anywhere under `app/` |
| Hardcoded course or learner IDs in app/src | ✅ None |
| Hardcoded model output | 3 found in static captions, all fixed (§4.3) |
| App imports | ✅ Only `edupro.*` and `app/lib` — no reimplementation |
| Unused pinned dependency | **PyYAML** was pinned, never imported, and no YAML file exists. **Removed** (11 packages remain) |
| `.gitattributes` accuracy | The comment claimed `.npy` was marked binary; **it was not** — it fell under `* text=auto` and was safe only by NUL-byte auto-detection. `*.npy binary` added, verified with `git check-attr` (`text: unset`) |
| Tracked junk | ✅ No `.pyc`, cache, log, backup or OS files tracked |

**Verdict: PASS**, with two hygiene defects fixed.

---

## 7. Audit F — Security and privacy

| Probe | Method | Result |
| --- | --- | --- |
| PII in served artifacts | Loaded all 3,000 real emails and 3,000 real names from the workbook, searched 30 served files | ✅ **0 occurrences** |
| PII columns in served frames | Inspected the 36-column learner table | ✅ None — index is the pseudonymous `UserID` |
| Email as a modelling feature | Inspected the 25-column model input | ✅ Absent |
| Secrets in tracked files | 6 patterns over all 195 tracked files | ✅ **0 matches** |
| Secrets in git history | `git log --all -S` for AWS keys, private keys, GitHub and Slack tokens | ✅ **0 strict matches** (one base64 PNG substring, not a key) |
| `.streamlit/secrets.toml` | Tracking status | ✅ Untracked and git-ignored |
| `st.secrets` in the app | Grep | ✅ Appears only in the audit script that searches for it |
| Public error disclosure | `.streamlit/config.toml` | ✅ `showErrorDetails = "type"` |

**Author contact** (`kartikshreekumar2006@gmail.com`) appears in
`pyproject.toml` as package authorship metadata. This is deliberate attribution,
not a leak, and is the author's own address.

**Verdict: PASS.**

---

## 8. Audit G — User interface

`scripts/app_smoke_test.py`: **20 probes, 20 pass** (after the §4.1 fix).

Independent behavioural audit — **300 randomly sampled learners**, live service:

| Probe | Result |
| --- | --- |
| Recommended a course the learner already took | ✅ **0** |
| Empty recommendation lists | ✅ 0 |
| Lists shorter than k = 10 | ✅ 0 |
| Missing explanations | ✅ 0 |
| Duplicate courses within one list | ✅ 0 |
| Routes exercised | minimal 153, moderate 94, rich 53 |
| Cold start (unknown learner) | ✅ 10 items across 10 categories, tier `insufficient`, caveat attached |
| Category × level filters | ✅ **36 of 36 combinations, 0 off-filter items** |

The project's own exhaustive pass covers all 3,000 learners and 30,000
explanations with the same result.

**Verdict: PASS.**

---

## 9. Audit H — Explainability

| Probe | Result |
| --- | --- |
| Every recommendation carries an explanation | ✅ Verified on 300 sampled learners and, by the project's own scan, all 3,000 |
| Does the explanation match the scoring route? | ✅ `minimal` cites only `content`; `moderate`/`rich` cite only `cluster_popularity` — exactly the frozen routing table. **0 mismatches** |
| Explanation tier equals result tier | ✅ 0 mismatches |
| Cold-start lists claim personalisation | ✅ No cold-start explanation references a segment |
| Quality caveat travels with the result | ✅ No result can be rendered without the random-reference caveat |

Explanations are **model-intrinsic** — derived from the score decomposition the
ranker actually used, not generated alongside it. That is why they cannot
contradict the scoring logic.

**Verdict: PASS.**

---

## 10. Audit I — Deployment

| Check | Result |
| --- | --- |
| Readiness audit | ✅ **25 of 25**, 0 warnings, 0 failures |
| Live application | ✅ Opened in a browser and exercised: overview, recommendations, analytics |
| Artifact set served | ✅ Sidebar reports `edupro-1.0.0 · artifact set 6892a4f9ef27` — the set committed here |
| Retraining on startup | ✅ None; `st.cache_resource`, loaded once per process |
| Docker | ✅ Not introduced |
| Absolute paths | ✅ None; everything derives from `PROJECT_ROOT` or `__file__` |
| Linux filename case | ✅ 18 referenced filenames, no mismatch |
| Manifest keys resolve on any platform | ✅ 12 of 12 POSIX-relative, read **verbatim** with no separator repair |
| Committed bytes match recorded hashes | ✅ 12 of 12 identical from `git show` |

**Deployment history is recorded honestly.** Three builds failed before one
worked, one diagnosis was wrong and is annotated as wrong rather than rewritten
(D-072 → D-075), and the sequence is documented because it is the phase's most
transferable finding.

**Verdict: PASS.**

---

## 11. Git cleanliness

| Check | Result |
| --- | --- |
| Working tree | Clean at audit start |
| Commits | 21, phase-tagged (`phase-0/…` … `phase-6e/…`) plus five named fixes |
| Branches | `main` only; remote in sync |
| Tracked files | 195 |
| Largest tracked file | 3.1 MB (the official PDF) |
| Junk tracked | None |
| Secrets in history | None |

---

## 12. Limitations carried forward

These are **not defects**. They are real constraints, stated so no reader
overestimates what this project demonstrates.

1. **No recommendation method beats random ranking on this dataset.** This is the
   central finding, established before any recommender existed. The system is
   built, measured and deployed; the measurement says the ranking signal is not
   there. It is reported first everywhere.
2. **"Engagement Lift" is a proxy, not a measured business outcome.** Establishing
   real engagement impact requires an online controlled experiment that this
   project did not and could not run.
3. **The dataset is almost certainly synthetic** (D-025). Zero missing values
   across 27 columns and suspiciously regular cardinalities. Learned structure may
   partly be a generator artefact, which is disclosed in the paper.
4. **Segment separation is modest.** Silhouette 0.1946 — the clusters are stable
   (Jaccard 0.9892, ARI 0.9996) and interpretable, but not widely separated. The
   project reports both numbers rather than the flattering one.

### Open non-blocking items

| Item | Why it is not blocking |
| --- | --- |
| GitHub **About** section is empty | Web-UI only; cannot be set from a repository commit |
| No PDF build of the executive summary | Markdown and HTML are provided; `build_paper.py` prints the PDF route |
| Gender gap disclosed in the paper but not surfaced in the dashboard | Disclosure exists; surfacing it is an enhancement, not a correction |

---

## 13. Defects found and fixed during this audit

| # | Severity | Defect | Status |
| --- | --- | --- | --- |
| 1 | **Critical** | A missing manifest reported as an integrity failure (§4.1) | ✅ Fixed — D-077 |
| 2 | Medium | Pre-registered "(Proxy)" naming rule violated in the dashboard (§4.2) | ✅ Fixed |
| 3 | Low | Static caption asserting cluster reliability (§4.3) | ✅ Fixed — now derived |
| 4 | Low | Static caption asserting the learner count (§4.3) | ✅ Fixed — now derived |
| 5 | Low | Static caption asserting the ARI value (§4.3) | ✅ Fixed — now conditional |
| 6 | Low | `.gitattributes` claimed `.npy` was binary when it was not (§6) | ✅ Fixed |
| 7 | Low | `PyYAML` pinned but never imported (§6) | ✅ Removed |
| 8 | Low | Research paper cited 21 figures but displayed none | ✅ Fixed — all 21 embedded |
| 9 | Medium | Three current-state documents cited a retired artifact set (§4.4) | ✅ Fixed |

**Nothing was found in these categories:** fabricated metric · hardcoded
recommendation · data leakage · broken path · notebook-only dependency · raw
personal information · broken learner filter · recommendation of an
already-enrolled course · unexplained model behaviour · missing official feature
requirement · untraceable result.

---

## 14. Final verdict

✅ **PASS.** All 43 mandatory requirements are traceable and independently
verified. Nine defects were found and all nine are fixed. Four limitations are
documented and disclosed in the deliverables rather than hidden.

The project is **submission-ready**. The word "complete" is used only of the
engineering; the recommendation system's *measured performance* is a negative
result, and this report does not dress it as anything else.

**Evidence base for this verdict:** 385 tests · 59 adversarial probes · 25
deployment-readiness checks · 20 application smoke probes · 8 exact reproduction
checks · 96 numeric document claims · 300 live recommendation samples · 36 filter
combinations · one live public deployment.
