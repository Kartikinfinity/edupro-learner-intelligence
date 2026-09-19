# Final Validation Report — Adversarial Audit

**Phase:** 6A — pre-submission technical audit
**Date:** 19 September 2026
**Model version:** `edupro-1.0.0`, artifact set `b658773c9db8`
**Source workbook:** SHA-256 `ed555e46…8cc0`, verified unchanged

**Instruments**

| Instrument | Probes | Result |
| --- | --- | --- |
| `scripts/adversarial_audit.py` (CHECK 1–7) | 59 | 59 pass, 0 warn, 0 fail |
| `scripts/app_smoke_test.py` (CHECK 9) | 20 | 20 pass, 0 fail |
| `pytest tests` (CHECK 8) | 257 | 257 pass |
| `scripts/verify_reproducibility.py` (CHECK 11) | 8 | 8 exact |
| Clean-environment build (CHECK 10) | — | installs and runs end to end |

**Three real defects were found and fixed.** They are recorded in §12 with the
regression tests that now guard them. Every one was invisible to the 245-test
suite that existed before this phase, because that suite tests what the code is
*for*; these were failures of what the code does when attacked.

---

## How this audit was built so its verdicts mean something

A validation script that only confirms the author's expectations is worth little.
Three rules shaped the harness:

**A probe that cannot fail proves nothing.** Every data-corruption probe first
asserts that the clean input passes, then corrupts it and *requires* rejection.
Nine corruptions, nine required rejections.

**Leakage is tested by experiment, not by code reading.** The decisive probe
injects a synthetic interaction dated after the test cut, rebuilds the
training-window features and requires them byte-identical. Any code path reading
beyond the frame it was handed — a recency reference taken from "now", a
popularity count over the full table — moves those bytes.

**Privacy is tested against the real values.** The probe loads the workbook with
PII retained, takes 119 actual names and email addresses, and searches every
artifact, source and app file for them byte-wise. Searching for the *column name*
would pass even if the values had leaked under a different header.

The raw workbook is never touched. Corrupted frames are built in memory from
copies; `EduProData` is frozen, so mutation is impossible by construction.

---

## CHECK 1 — Data

**Does validation actually reject bad input, or does it only claim to?**

| Corruption | Detected by | Result |
| --- | --- | --- |
| Clean data (control) | — | ✅ 0 errors, 1 warning |
| Missing column (`Amount` dropped) | `columns_missing` | ✅ |
| Missing values (5 null `CourseID`) | `nulls` | ✅ |
| Duplicate records (3 rows repeated) | `duplicate_rows` | ✅ |
| Duplicate primary key (`UserID` repeated) | `uniqueness` | ✅ |
| Malformed identifier (`XX99999`) | `id_format` | ✅ |
| Orphan foreign key (`U99999`) | `orphan_fk` | ✅ |
| Malformed dates (3 unparseable) | `nulls` | ✅ |
| Invalid category (unknown value) | `value_domain` | ✅ |
| Out-of-range values (rating 47, price −500) | `range` | ✅ |
| **Pipeline refuses to train on invalid data** | `PipelineError` | ✅ |

The last row matters most: a validator whose report nobody acts on is decoration.
The pipeline aborts before fitting anything.

> **Defect found here — see §12.1.** The first corruption probe *crashed the
> validator*. Four cross-sheet checks indexed columns without checking they
> existed, so a missing column raised `KeyError` from inside the validator instead
> of producing the report that names it. Fixed and guarded by 8 regression tests.

## CHECK 2 — Feature pipeline

| Probe | Result |
| --- | --- |
| Single-interaction learner (54% of the base) | ✅ all features finite |
| Median learner | ✅ all features finite |
| Maximum-history learner (16 courses) | ✅ all features finite |
| Nulls across the whole matrix | ✅ 3,000 × 34, zero nulls |
| Every active learner present | ✅ 3,000 of 3,000 |
| Deterministic output | ✅ two builds byte-identical |
| Row-order invariance | ✅ identical under a shuffled input frame |
| Empty input | ✅ rejected with `ValueError: Cannot build learner features from an empty interaction frame` |
| Zero-span learner (all activity on one day) | ✅ no division by zero; `enrollment_frequency` = 11.0 |

The zero-span probe is the one that would normally produce an infinity: a learner
with 11 courses and an activity span of 0 days. The rate feature floors the
denominator, so the value is finite and interpretable.

Refusing empty input is treated as correct, not as a weakness: silently returning
an empty frame would let a broken upstream step propagate into an empty model.

## CHECK 3 — Leakage

| Probe | Result |
| --- | --- |
| **Future-injection**: a synthetic post-test-cut interaction | ✅ changes **nothing** in the training window across 2,450 learners |
| Split windows disjoint | ✅ train 6,992 / validation 1,000 / test 2,008, zero shared transactions |
| Training precedes test in time | ✅ train ends 2025-09-11, test begins 2025-10-18 |
| Held-out items remain candidates | ✅ 347 learners checked; every held-out course still eligible |
| Popularity is window-scoped | ✅ training counts sum to 6,992 against 10,000 for full history |
| Tiering uses training history | ✅ 430 learners would route differently on full history, so the two sources are **distinguishable** and the code uses the training one |
| Inference reuses the training scaler | ✅ a learner scaled alone reproduces their persisted segment |

Two of these deserve comment.

**"Held-out items remain candidates" tests the opposite of the intuitive
direction.** Removing the held-out course from the candidate pool would *leak* —
it tells the model which course to avoid. The probe requires the held-out course
to still be offerable.

**The tiering probe was designed to be able to fail.** If no learner changed tier
between windows, the probe could not distinguish the two data sources and would
prove nothing; it reports that case as a warning rather than a pass. 430 learners
do change, so the distinction is real and the code takes the training-window
count.

## CHECK 4 — Clustering

| Probe | Result |
| --- | --- |
| Artifact set loads | ✅ 12 files, 0 problems |
| Inference reproduces training labels | ✅ all 3,000 exactly |
| Every learner has a segment | ✅ 3,000 across 4 segments |
| Cluster label dtype is consistent | ✅ both `int64`; strict `equals()` holds |
| Labels stable across independent loads | ✅ |
| Column order cannot corrupt scaling | ✅ reordered input gives a **bit-identical** scaled matrix (max deviation 0.0) |
| Cluster profiles match their members | ✅ stored means match recomputed to 4.9 × 10⁻⁵ |
| Segment names use model features only | ✅ 4 names, none referencing an excluded feature |

> **Defect found here — see §12.3.** The dtype probe exists because the
> column-order probe initially *failed*: two identical answers compared unequal
> because the pipeline persisted scikit-learn's platform-dependent label dtype
> (`int32`) while inference returned platform `int`. The labels always agreed, but
> the obvious check — "does inference reproduce training?" — could not be asked
> with a strict comparison. Fixed by declaring one width in both places.

## CHECK 5 — Recommendations

| History profile | Route | Result |
| --- | --- | --- |
| Rich (9+ courses) | `cluster_popularity` | ✅ 10 items, 49 candidates |
| Moderate (2–8) | `cluster_popularity` | ✅ 10 items, 58 candidates |
| Minimal (1) | `content_based` | ✅ 10 items, 59 candidates |
| Insufficient (new learner) | `diversified_fallback` | ✅ 10 items, 60 candidates |
| **59 of 60 courses taken** | — | ✅ exactly 1 recommendation; k truncated, not padded |
| **All 60 courses taken** | — | ✅ typed error naming the real cause |

| Behaviour | Result |
| --- | --- |
| Known courses excluded | ✅ **exhaustive: all 3,000 learners, 0 violations, 0 empty lists** |
| Deterministic ranking | ✅ three runs identical |
| Tie-breaking | ✅ 21 tied adjacent pairs, all resolved deterministically |
| Category and level filters | ✅ 12 categories × 3 levels, every result matched |
| Impossible filter combination | ✅ typed error naming the filters |
| Hostile arguments | ✅ k ≤ 0 rejected; k = 10,000 truncated to the 59 available |
| Unknown / non-ASCII identifier | ✅ flagged `is_known_learner=False`, routed to cold start |

> **Defect found here — see §12.2.** The "no candidates" error *misdiagnosed its
> own cause*: a learner who had taken all 60 courses was told the problem was
> filtering, with a count of "0 already-enrolled courses". An error that sends the
> reader to the wrong place is worse than a generic one.

## CHECK 6 — Explainability

**Exhaustive: 30,000 explanations across all 3,000 learners.**

| Property | Violations |
| --- | --- |
| Names only signals the model actually used | **0** |
| Quoted number equals the scorer's own contribution | **0** |
| Category claims true of the learner's real history | **0** |
| Cold-start lists never imply personalisation | **0** |
| Measured-quality caveat attached to every result | **0 missing** |

The second row is the strongest: for segment-popularity recommendations the
integer in "*127 learners in your segment enrolled in this course*" is parsed back
out of the sentence and compared against the contribution the ranking used. They
are the same number in all 30,000 cases, because the explanation is generated from
the score decomposition rather than written alongside it.

## CHECK 7 — Privacy

| Probe | Result |
| --- | --- |
| **Real names and addresses searched byte-wise** | ✅ 119 real values across 97 files — **0 occurrences** |
| No PII column in any served frame | ✅ 4 frames |
| Learner profile is minimal | ✅ 13 fields, identifier is the pseudonymous `UserID` |
| Email is not a modelling feature | ✅ no identity-derived column |
| PII dropped at ingestion | ✅ absent from the default load, so it cannot reach a downstream frame by accident |

The files searched include every persisted artifact, every module under `src/`,
and every page under `app/`.

## CHECK 8 — Tests

**257 passed**, 1 warning (a Matplotlib deprecation in seaborn), 120 s.

| Suite | Tests |
| --- | --- |
| `test_phase0_environment.py` | 31 |
| `test_data_pipeline.py` | 36 |
| `test_segmentation.py` | 37 |
| `test_recommendation.py` | 59 |
| `test_production.py` | 56 |
| `test_app.py` | 26 |
| **`test_regressions.py`** *(new this phase)* | **12** |

## CHECK 9 — Streamlit

20 probes, all passing. Beyond rendering, the app was *operated*:

| Probe | Result |
| --- | --- |
| All seven pages render | ✅ 0.4–3.3 s each |
| Learner selection changes the page | ✅ header follows the selection |
| Segment filter narrows the pool | ✅ "Learner (1,030 available)" |
| Recommendations render | ✅ History / Route / Candidates |
| Category filter applies | ✅ only the chosen category appears |
| Cold-start mode reaches the fallback | ✅ route metric reads `insufficient` |
| List-length control | ✅ |
| Segment visualisation | ✅ caveat block rendered *before* the chart |
| Visualisation filter | ✅ |
| Empty selections (2 pages) | ✅ guidance, not a crash |
| Measured metrics render | ✅ 5 evidence tables, 11 metrics |
| **Missing artifacts** | ✅ a cold process shows the page naming the fixing command |
| Artifact set restored afterwards | ✅ |

The missing-artifact probe runs in a **subprocess**. In-process it would have been
handed the already-cached model by `st.cache_resource` and passed while testing
nothing — a false pass that a less careful harness would have recorded.

## CHECK 10 — Clean environment

Built from scratch with `py -3.13 -m venv`, at `C:\Temp\edupro-clean`:

| Step | Result |
| --- | --- |
| `pip install -r requirements.txt` | ✅ 71 s, exact pinned versions |
| `pip install -e . --no-deps` | ✅ |
| `pip install -r requirements-dev.txt` | ✅ |
| `python scripts/train_production_model.py` | ✅ 16 s — **identical segment sizes** to the development environment |
| `python -m pytest tests -q` | ✅ **257 passed** |
| `python scripts/recommend.py --user U00001` | ✅ identical output |
| `python scripts/verify_reproducibility.py` | ✅ 8 of 8 exact |
| `streamlit run app/streamlit_app.py` | ✅ HTTP 200, dashboard renders |

**Two environment findings, neither a project defect but both worth recording:**

1. **The machine's default `python` is 3.14, which the project excludes**
   (`requires-python = ">=3.11,<3.14"`). `pip install -e .` correctly refuses, but
   a user who runs `python -m venv .venv` without thinking gets an unsupported
   interpreter. The reproduction instructions now specify `py -3.13` explicitly.
2. **A very long installation path breaks `pip install` on Windows.** Installing
   into a ~250-character path failed with an opaque
   `OSError: No such file or directory: …pyarrow.libs\msvcp140_atomic_wait-….dll`
   — Windows `MAX_PATH`, not a dependency problem. The same install at
   `C:\Temp\edupro-clean` succeeded. Recorded because the error message points
   nowhere near the cause.

## CHECK 11 — Reproducibility

See `research/FINAL_VALIDATION.md` §Reproduction for the exact commands. Summary:

| | |
| --- | --- |
| Python | **3.13.9** (supported: ≥3.11, <3.14) |
| Runtime deps | `requirements.txt`, pinned exactly (pandas 3.0.6, numpy 2.5.3, scikit-learn 1.9.1, streamlit 1.64.0, plotly 7.1.0, pyarrow 25.0.1, joblib 1.6.0) |
| Dev deps | `requirements-dev.txt` (pytest 9.1.1) |
| Frozen environment | `requirements.lock.txt` |
| Seed | 42, everywhere |
| Artifact generation | `python scripts/train_production_model.py` → 12 files, 276 KB |
| Launch | `streamlit run app/streamlit_app.py` |

Eight stored experiment results recompute **exactly** — in the development
environment and again in the clean one.

---

## §12. Defects found and fixed

### 12.1 (Critical) The validator crashed on the corruption it exists to report

**Symptom.** The first corruption probe — dropping the `Amount` column — raised
`KeyError: 'Amount'` from inside `validate_transactions`.

**Cause.** Four cross-sheet checks (`validate_referential_integrity`,
`validate_transactions`, `validate_price_consistency`,
`validate_course_catalogue`) indexed columns without checking they were present.
The sheet-level pass had already recorded `columns_missing` as an error, but the
run died before returning the report.

**Why it mattered.** A caller feeding the pipeline a malformed file got an opaque
`KeyError` instead of a report naming the missing column, and the pipeline's
"refuse to train on invalid data" path never ran. A checker that raises on the
first corruption it exists to report is worse than no checker: it fails in a way
that looks like a bug in the loader.

**Fix.** A `_available()` guard records an informational finding and skips the
cross-sheet check when a required column is absent; the sheet-level error still
carries the verdict.

**Guarded by.** 8 regression tests across 6 column/sheet combinations, plus a
multi-column case and the pipeline-refusal path.

### 12.2 The "no candidates" error misdiagnosed its own cause

**Symptom.** A learner who had taken all 60 courses was told:
*"No candidate courses remain after filtering (category=None, level=None) and
excluding 0 already-enrolled courses."*

**Cause.** The message blamed filters that were never applied, and read the
excluded-course count from the history table rather than from the exclusion set
the scorer actually used.

**Fix.** The error now distinguishes three cases — catalogue exhausted, filters
too narrow, nothing unseen — and counts from the structure that produced the
result. Now: *"No candidate courses for 'X': this learner has already taken all 60
courses in the catalogue."*

**Guarded by.** 2 regression tests, one asserting the message must **not** mention
a filter that was not applied.

### 12.3 Cluster labels had two dtypes, so identical answers compared unequal

**Symptom.** `assign_segment(...).equals(features["cluster"])` was `False` while
`(assign_segment(...) == features["cluster"]).all()` was `True`.

**Cause.** The pipeline persisted scikit-learn's native label dtype (`int32` on
this platform); inference returned platform `int` (`int64`).

**Why it mattered.** Nothing was wrong with the labels, but the obvious way to ask
"does inference reproduce training?" gave the wrong answer — and a future
comparison, merge or artifact check written the obvious way would silently fail.

**Fix.** `CLUSTER_DTYPE = "int64"` declared once and applied in both the pipeline
and inference. Artifacts regenerated.

**Guarded by.** 2 regression tests, one asserting the strict comparison holds.

### Also corrected: four faults in the audit itself

An audit that reports its own mistakes as system defects is not trustworthy. Four
initial "failures" were the harness's fault and were fixed rather than filed:

| Apparent failure | Actual cause |
| --- | --- |
| Orphan FK "detected by the wrong check" | The probe expected the wrong check name |
| Empty input "should return an empty frame" | Refusing is correct; the probe's expectation was wrong |
| Column reordering "changed the assignment" | `.equals()` is dtype-strict — it exposed 12.3, not an ordering bug |
| Category filter "not applied" | The probe read only markdown; the category renders in a caption |
| Missing artifacts "handled ungracefully" | `st.cache_resource` served the warm model — the probe had to run in a subprocess |

---

## Verdict

| PASS condition | Evidence |
| --- | --- |
| No critical data issue | CHECK 1 — 11 of 11 probes pass after fixing 12.1 |
| No leakage issue | CHECK 3 — 7 of 7, including the future-injection experiment |
| No broken production path | CHECKS 4, 5, 10 — exhaustive over 3,000 learners; clean-environment build works end to end |
| Tests pass | CHECK 8 — 257 passed |
| Application runs | CHECK 9 — 20 of 20, plus HTTP 200 from a clean environment |
| Explanations are valid | CHECK 6 — 30,000 explanations, 0 violations |
| Privacy checks pass | CHECK 7 — 119 real values, 0 occurrences |

## ✅ **PASS**

Three real defects were found and fixed, each now guarded by regression tests. No
unresolved critical finding remains.
