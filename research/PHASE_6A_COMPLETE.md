# Phase 6A — Adversarial Validation — COMPLETE

**Phase:** 6A — pre-submission technical audit
**Date:** 19 September 2026
**Decision:** ✅ **PASS**
**Artifact set:** `edupro-1.0.0`, set `b658773c9db8`
**Next phase:** Phase 6B — research paper, executive summary, deployment (**not started; awaiting go-ahead**)

---

## 1. Objective

Try to break the project. Not to demonstrate that it works — the existing suite
already did that, and it was written by the same hand that wrote the code.

---

## 2. Headline

> **Three real defects found and fixed.** All three were invisible to the 245-test
> suite that existed before this phase, and one of them was critical: the data
> validator **crashed** on the first corruption it exists to report.
>
> After the fixes: **59 audit probes, 20 smoke probes, 257 tests — all passing**,
> with the whole thing reproduced in a clean environment built from scratch.

The defects were found because the harness was built to be hostile rather than
confirmatory. Three rules made that real:

**A probe that cannot fail proves nothing.** Every data-corruption probe first
asserts the clean input passes, then corrupts it and *requires* rejection.

**Leakage is tested by experiment, not by reading the code.** The decisive probe
injects a synthetic post-test-cut interaction and requires the training features to
come back byte-identical.

**Privacy is tested against the real values.** 119 actual names and email addresses
from the workbook, searched byte-wise across 97 files. Searching for the *column
name* would pass even if the values had leaked under a different header.

---

## 3. The three defects

### 3.1 (Critical) The validator crashed on the corruption it exists to report

Dropping the `Amount` column raised `KeyError` from inside `validate_transactions`.
Four cross-sheet checks indexed columns without checking they were present, so the
run died before returning the report that named the problem.

**Why it mattered:** a malformed input file produced an opaque `KeyError` instead
of a validation report, and the pipeline's "refuse to train on invalid data" path
never ran. A checker that raises on the first corruption it is meant to report is
worse than no checker — it fails in a way that looks like a bug somewhere else.

**Fixed** with an `_available()` guard across all four functions. **8 regression
tests.**

### 3.2 The "no candidates" error misdiagnosed its own cause

A learner who had taken all 60 courses was told the cause was *filtering*, with a
count of "0 already-enrolled courses" — the message blamed a filter that was never
applied and counted from the wrong structure. **Fixed** to distinguish three
distinct causes and count from the exclusion set the scorer actually used.
**2 regression tests.**

### 3.3 Cluster labels had two dtypes, so identical answers compared unequal

The pipeline persisted scikit-learn's platform-dependent label dtype (`int32`);
inference returned platform `int`. The labels always agreed, but the obvious check
— "does inference reproduce training?" — returned `False` under a strict
comparison. **Fixed** by declaring `CLUSTER_DTYPE` once and applying it in both
places. **2 regression tests.**

---

## 4. Results by check

| Check | Probes | Result | Most significant probe |
| --- | --- | --- | --- |
| 1 · Data | 11 | ✅ | 9 corruptions, each required to be rejected by the right check |
| 2 · Feature pipeline | 9 | ✅ | zero-span learner — no division by zero |
| 3 · Leakage | 7 | ✅ | **future-injection changes nothing** across 2,450 learners |
| 4 · Clustering | 8 | ✅ | reordered columns give a bit-identical scaled matrix |
| 5 · Recommendations | 13 | ✅ | **exhaustive: 3,000 learners, 0 already-taken courses** |
| 6 · Explainability | 6 | ✅ | **30,000 explanations, 0 violations** |
| 7 · Privacy | 5 | ✅ | 119 real values, 0 occurrences in 97 files |
| 8 · Tests | 257 | ✅ | — |
| 9 · Streamlit | 20 | ✅ | missing artifacts handled gracefully in a **cold process** |
| 10 · Clean environment | 8 steps | ✅ | identical segments, 257 tests, HTTP 200 |
| 11 · Reproducibility | 8 results | ✅ | exact in both environments |

Full evidence: [`final_validation_report.md`](final_validation_report.md).
One-page verdict and reproduction: [`FINAL_VALIDATION.md`](FINAL_VALIDATION.md).

### Probes worth singling out

**Leakage, by experiment.** A synthetic interaction dated 45 days after the test
cut was injected into the source data and the training-window features rebuilt.
Every value came back identical. A separate probe requires held-out courses to
*remain* candidates — removing them would be the leak, not the fix. A third probe
confirms 430 learners would route to a different tier on full history, so the two
data sources are genuinely distinguishable and the code demonstrably uses the
training one. That probe reports "cannot distinguish" as a **warning** rather than
a pass when the distinction is not observable.

**Explanations, exhaustively.** For every segment-popularity recommendation, the
integer in "*127 learners in your segment enrolled in this course*" is parsed back
out of the rendered sentence and compared against the contribution the ranking
used. Same number, 30,000 times, because the explanation is generated from the
score decomposition rather than written beside it.

**The application's most likely production failure.** Removing the manifest and
loading a page in a **subprocess** — in-process, `st.cache_resource` would have
served the already-loaded model and the probe would have passed while testing
nothing. The cold process shows the page naming the command that fixes it.

---

## 5. The audit's own mistakes

Five initial "failures" were the harness's fault. An audit that reports its own
bugs as system defects is not trustworthy, so each is recorded:

| Apparent failure | Actual cause |
| --- | --- |
| Orphan FK detected by the "wrong" check | The probe expected the wrong check name |
| Empty input "should return an empty frame" | Refusing loudly is correct behaviour |
| Column reordering "changed the assignment" | `.equals()` is dtype-strict — it exposed defect 3.3, not an ordering bug |
| Category filter "not applied" | The probe read only markdown; the category renders in a caption |
| Missing artifacts "handled ungracefully" | The resource cache served a warm model; needed a subprocess |

The third is the useful one: a probe that was wrong about *what it was testing*
still surfaced a real inconsistency underneath.

---

## 6. Environment findings (not project defects)

1. **The machine's default `python` is 3.14**, which the project excludes
   (`>=3.11,<3.14`). `pip install -e .` correctly refuses — but a user running
   `python -m venv .venv` without thinking meets an unrelated dependency error
   first. Reproduction instructions now specify `py -3.13` explicitly.
2. **A ~250-character install path breaks `pip install` on Windows** with an
   opaque missing-DLL `OSError`. That is `MAX_PATH`; the same install at
   `C:\Temp\edupro-clean` succeeded. Recorded because the error points nowhere
   near its cause.

Both are documented in `FINAL_VALIDATION.md` §Reproduction.

---

## 7. Artifacts created

| Artifact | Contents |
| --- | --- |
| `scripts/adversarial_audit.py` | CHECK 1–7, 59 probes |
| `scripts/app_smoke_test.py` | CHECK 9, 20 probes including the cold-process failure path |
| `tests/test_regressions.py` | 12 tests holding the three fixes |
| `artifacts/validation/adversarial_audit.json` | every probe's verdict and evidence |
| `artifacts/validation/app_smoke_test.json` | smoke results |
| `research/final_validation_report.md` | the detailed audit record |
| `research/FINAL_VALIDATION.md` | verdict and reproduction procedure |
| `research/PHASE_6A_COMPLETE.md` | this report |
| Modified | `data/validation.py` (3.1), `inference.py` (3.2), `pipeline.py` (3.3) |

---

## 8. Validation checks

| Check | Result |
| --- | --- |
| Adversarial audit | ✅ 59 probes, 0 warn, 0 fail (exhaustive mode) |
| Application smoke test | ✅ 20 probes, 0 fail |
| Full test suite | ✅ **257 passed** |
| Clean-environment build | ✅ install, train, test, CLI, app — all working |
| Reproducibility | ✅ 8 of 8 exact, in two environments |
| Raw workbook SHA-256 | ✅ `ed555e46…8cc0` unchanged |
| Raw data modified | ✅ No — corrupted frames built in memory from copies |
| Docker | ✅ None introduced |
| New features added | ✅ None — this phase only found, fixed and documented |

---

## 9. PASS / FAIL

### ✅ **PASS**

| PASS condition | Evidence |
| --- | --- |
| No critical data issue | CHECK 1 — 11 of 11 after fixing 3.1 |
| No leakage issue | CHECK 3 — 7 of 7, including the future-injection experiment |
| No broken production path | CHECKS 4, 5, 10 — exhaustive over 3,000 learners; clean build works end to end |
| Tests pass | 257 passed |
| Application runs | CHECK 9 — 20 of 20, plus HTTP 200 from a clean environment |
| Explanations are valid | CHECK 6 — 30,000 explanations, 0 violations |
| Privacy checks pass | CHECK 7 — 119 real values, 0 occurrences |

### CLAUDE.md compliance

| § | Requirement | Status |
| --- | --- | --- |
| 6 | No fabricated results; failures not hidden | ✅ Three defects reported prominently, plus the audit's own five mistakes |
| 8 | Raw data immutable | ✅ Checksum verified; corruption performed on in-memory copies of a frozen dataclass |
| 9 | Leakage detection mandatory | ✅ Tested by experiment, not by inspection |
| 16 | Explanations match scoring logic | ✅ 30,000 checked exhaustively |
| 17 | Privacy | ✅ Real values searched byte-wise |
| 20 | No Docker | ✅ |
| 23 | Failure and edge cases tested | ✅ Exhausted learners, hostile arguments, non-ASCII ids, empty selections |
| 26 | Reproducibility instructions work | ✅ Executed in a clean environment, not just written down |
| 27 | Phase report with evidence | ✅ This document plus two evidence artifacts |

---

## 10. Unresolved issues

No unresolved **critical** finding. Carried forward:

1. **Nothing beats random.** Unchanged, and stated throughout the system.
2. **Gender gap requires monitoring** on real data — recorded in the research
   artifacts but still not surfaced in the dashboard. Phase 6B should decide
   whether a fairness panel belongs there.
3. **Artifact freshness is not automated.** The manifest detects an *inconsistent*
   artifact set, not a *stale* one; editing the pipeline without re-running it
   leaves old artifacts in place silently.
4. **Phase 0's two open items remain open**: the empty `claude.md.txt`, and the
   git-identity/authorship question (`Kartik <kartikshreekumar2006@gmail.com>` in
   the global git config vs the session account; `pyproject.toml` recorded a name
   inferred from that account). Both need confirmation before publication.
5. **The project has not been deployed publicly yet.** Phase 6B.

   **RESOLVED 20 September 2026: the author is Kartik (`kartikshreekumar2006@gmail.com`), confirmed by the project owner. `pyproject.toml`, the paper byline and the rendered paper now all say so.**

---

## 11. Stop

Per CLAUDE.md §28, work **stops here**. Phase 6B will not begin automatically.

🔒 The ML design remains frozen. This phase changed three implementation defects
and no model behaviour — the reproducibility check, run in two independent
environments, is the evidence.
