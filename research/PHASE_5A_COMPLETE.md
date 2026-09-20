# Phase 5A — Production ML Implementation — COMPLETE

**Phase:** 5A — production ML implementation
**Date:** 19 September 2026
**Decision:** ✅ **PASS**
**Artifact set:** `edupro-1.0.0`, set `50c48678d4e5`
**Next phase:** Phase 5B — Streamlit application (**not started; awaiting go-ahead**)

---

## 1. Objectives

Implement the frozen architecture (`research/ARCHITECTURE_FREEZE.md`) as
production-quality, reusable modules; persist a versioned artifact set; and make
recommendation generation possible **without opening a notebook**.

The ML design was not revisited. Phase 5A implements exactly what Phase 4 froze.

---

## 2. What was built

The suggested layout maps onto the existing package, which was already organised
this way; names follow the final architecture rather than the sketch.

| Suggested | Implemented as | Status |
| --- | --- | --- |
| `data/loader.py` | `edupro/data/loader.py` | existed |
| `data/validator.py` | `edupro/data/validation.py` | existed |
| `data/preprocessing.py` | `edupro/data/joins.py` | existed — the audit found **no cleaning is required** (D-019), so a cleaning module would be an empty shell |
| `features/learner_features.py` | `edupro/features/learner.py` | existed |
| `features/course_features.py` | **`edupro/features/course.py`** | **new** |
| `segmentation/preprocess.py` | `edupro/segmentation/representations.py` | extended with an inference transform path |
| `segmentation/model.py` | `edupro/segmentation/clustering.py` | existed |
| `segmentation/profiling.py` | `edupro/segmentation/profiling.py` | existed |
| `recommendation/candidates.py` | `edupro/recommendation/base.py` | existed — exclusion is in the base class, so no scorer can skip it |
| `recommendation/ranking.py` | `edupro/recommendation/baselines.py` | existed |
| `recommendation/hybrid.py` | `edupro/recommendation/hybrid.py` | existed |
| `recommendation/fallback.py` | `baselines.DiversifiedFallback` + `hybrid.TieredRecommender` | existed |
| `evaluation/*` | `edupro/evaluation/` | existed |
| `explainability/explanations.py` | **`edupro/explainability/explanations.py`** | **new** |
| `utils/config.py` | `edupro/config.py` + **`edupro/logging_utils.py`** | extended |
| — | **`edupro/persistence.py`** | **new** — artifacts and version checking |
| — | **`edupro/pipeline.py`** | **new** — the training pipeline |
| — | **`edupro/inference.py`** | **new** — the serving path |

Entry points: `scripts/train_production_model.py`, `scripts/recommend.py`,
`scripts/verify_reproducibility.py`.

---

## 3. The twelve required capabilities

| # | Capability | Where | Evidence |
| --- | --- | --- | --- |
| 1 | Deterministic data loading | `data/loader.py` | SHA-256 verified at every train; identical segment sizes across two runs (test) |
| 2 | Schema validation | `data/validation.py` | pipeline refuses to train on a failing report; **0 errors**, 1 warning, 4 informational findings |
| 3 | Preprocessing | `data/joins.py` | 10,000 interactions built; no cleaning needed (D-019) |
| 4 | Learner feature generation | `features/learner.py` | 3,000 learners × 36 persisted columns — 25 in the model, the rest for display plus cluster, tier and segment name |
| 5 | Course representation | **`features/course.py`** | 60 × 18 content matrix; canonical catalogue order asserted |
| 6 | Clustering inference | `inference.assign_segment` | **reproduces all 3,000 persisted labels exactly** |
| 7 | Recommendation inference | `inference.recommend` | every tier served; 8.4 ms per learner |
| 8 | Unseen-course filtering | `recommendation/base.py` | **0 of 3,000 learners** received an already-taken course |
| 9 | Sparse-user fallback | `hybrid.TieredRecommender` | four routes; cold-start list spans **10 of 12 categories** |
| 10 | Explanation generation | **`explainability/explanations.py`** | quoted counts asserted equal to the scorer's contributions |
| 11 | Artifact loading | `persistence.verify_artifacts` | 11 files, 276 KB, loads in **0.41 s** |
| 12 | Artifact version checking | `persistence.check_compatibility` | model version, scikit-learn version, workbook checksum and per-file hash |

---

## 4. Decisions taken in this phase

Four implementation decisions and one finding, recorded as D-045…D-049.

### D-045 — the deployed model is fitted on the full history

Selection used the temporal split so every reported metric is out-of-sample; the
deployed artifact set is fitted on all 10,000 interactions, which is standard after
selection and is what a live platform would do.

The two are not identical, so the manifest records which is which:

| | Fit window (evaluated) | Full history (deployed) |
| --- | --- | --- |
| Learners | 2,650 | 3,000 |
| Segment sizes | 715 / 522 / 881 / 532 | 841 / 1,030 / 607 / 522 |
| Smallest segment | 19.7% | **17.4%** |
| Mean bootstrap Jaccard | 0.9892 | **0.9805** |

**The four segment names come out identical** — Beginner-level single-course,
Category-repeating high-volume, Advanced-level non-repeating, Intermediate-level
single-session. The same structure was found again on 350 additional learners, and
the deployed fit still satisfies the frozen k-selection rule (smallest segment
17.4% ≥ 5%, per-cluster Jaccard 0.967–0.994, all ≥ 0.60). Cluster *numbering* differs because
K-Means labels are arbitrary.

### D-046 — load what was learned, recompute what is merely counted

The fitted scaler and K-Means are loaded and never refitted (§21). The counting
structures — per-segment enrollment counts, content profiles, the category
round-robin order — are rebuilt at load time in 0.40 s **by the same recommender
classes the experiments used**.

A separate serving implementation reading precomputed arrays would be a second
scoring path that can drift from the evaluated one, and an explanation generated
from a drifted scorer is exactly what §16 prohibits. `popularity.parquet` is
persisted redundantly and compared against the recomputed counts by test, so a
drift fails loudly.

### D-047 — the artifact set is committed (**closes open item P-2**)

276 KB total. Streamlit Community Cloud deploys from the repository and cannot run
the training pipeline. `.gitignore` is relaxed for five named files rather than the
whole directory, so a stray experiment written into `models/` is still ignored.

### D-048 — the tier frame and the caveat belong to the list, not the item

The first rendering repeated "You are new here, so these are broad…" ten times in a
ten-item list. The frame is a property of the routing decision, so it moved to
`Explanation.tier_frame` and is shown once; `full_sentence` recombines them when an
explanation appears alone.

### D-049 — on the full history, no existing learner is in the cold-start tier

Tier distribution: **minimal 1,620 · moderate 926 · rich 454 · insufficient 0.**
All 3,000 learners have at least one interaction. The `insufficient` route is not
dead code — it serves genuinely *new* learners, reached when an identifier is
absent from the artifact set, with `is_known_learner = False` rather than an
invented profile.

**Consequence for Phase 5B:** the cold-start experience cannot be demonstrated by
selecting an existing learner. The dashboard must expose a "new learner" path
explicitly, or the diversified fallback chosen on evidence in EXP-029 will never be
visible to a reviewer.

---

## 5. End-to-end offline inference test

Run from a cold start with no notebook involved:

```
artifact load: 0.408s  (set 50c48678d4e5, 0 problems)

tier                        route                   k  cats      ms  first
minimal                     content_based          10     6    32.5  CR00033
moderate                    cluster_popularity     10     5     7.5  CR00014
rich                        cluster_popularity     10     6    10.7  CR00021
insufficient (new learner)  diversified_fallback   10    10     2.3  CR00058

500 learners served in 4.19s  (8.4 ms each)
all 3000 learners: 0 empty lists, 0 with an already-taken course
```

Every tier routes to the frozen recommender. The cold-start list spans **10 of 12
categories**, reproducing the property `DiversifiedFallback` was selected for.

### Command-line inference

```bash
python scripts/train_production_model.py      # 18 s, writes 11 files
python scripts/recommend.py --user U00001     # explained top-10
python scripts/recommend.py --user U00001 --category "Data Science" --level Beginner
python scripts/recommend.py --user NEW-LEARNER            # cold-start route
python scripts/recommend.py --describe                    # artifact set summary
```

Sample output, a minimal-tier learner:

```
Learner U00001
  segment   2 - Intermediate-level Single-session Single-course learners
  tier      minimal (1 course in history)
  prefers   Cybersecurity, Intermediate
  candidates 59 unseen courses

  You have one course in your history, so this is a similarity match to it
  rather than a behavioural profile.

 1. Cybersecurity Fundamentals  [CR00033]
    Cybersecurity | Intermediate | rated 3.9 | free
    Matches your learning profile: same category as 1 of your 1 course
    (Cybersecurity) and at the Intermediate level you usually choose.
```

---

## 6. Do the explanations correspond to the actual logic?

This is a PASS criterion, so it is measured rather than asserted.

| Check | How | Result |
| --- | --- | --- |
| A component the model did not use is never named | contributions at or below 1e-9 are dropped before any phrase is built | test |
| The quoted number is the number the scorer ranked by | the integer parsed out of the sentence must equal `contributions["cluster_popularity"]`, which for that scorer **is** the within-segment enrollment count | test |
| The explanation agrees with the persisted artifact | the same count must equal `popularity.parquet` | test |
| A category claim is verified, not assumed | "same category as N of your M" only appears when the learner's history actually contains that category | test |
| Cold-start explanations do not claim personalisation | the insufficient-tier frame says "rather than personalised picks"; no item may say "your segment" or "learners like you" | test |
| No accuracy claim | the measured-quality caveat is attached to every result | test |

The caveat carried on every result:

> Measured on held-out data, no ranking method beat random selection on this
> dataset, so treat the ordering as a reasonable default rather than a prediction
> of what you will choose.

---

## 7. Do the existing experiments still reproduce?

Phase 5A refactored code the Phase 3A and 3B experiments ran through: the
segmentation representation gained a transform path for inference, and the course
content matrix moved into the feature layer. Neither was supposed to change a
number. `scripts/verify_reproducibility.py` recomputes headline results from
scratch and compares them to the stored artifacts:

```
Segmentation (fit window, B_proportion, k=4)
  [OK] silhouette, B_proportion k=4        stored 0.194600  recomputed 0.194600
  [OK] mean bootstrap Jaccard, k=4         stored 0.989200  recomputed 0.989200

Recommendation (test window, Protocol A)
  [OK] NDCG@10, random                     stored 0.110215  recomputed 0.110215
  [OK] NDCG@10, content_based              stored 0.119113  recomputed 0.119113
  [OK] NDCG@10, cluster_popularity         stored 0.113773  recomputed 0.113773

Architecture C (validation window)
  [OK] ndcg@10                             stored 0.110354  recomputed 0.110354
  [OK] hit_rate@10                         stored 0.305284  recomputed 0.305284
  [OK] coverage@10                         stored 1.000000  recomputed 1.000000

All 8 checks reproduce the stored results exactly.
```

---

## 8. Artifact set

| File | Purpose |
| --- | --- |
| `models/scaler.joblib` | fitted StandardScaler |
| `models/clusterer.joblib` | fitted KMeans, k=4 |
| `models/feature_schema.json` | column names, dtypes, model/display split |
| `models/model_config.json` | the frozen configuration, human-readable |
| `models/manifest.json` | set version, library versions, workbook checksum, per-file hash |
| `artifacts/production/learner_features.parquet` | 3,000 × 36, plus cluster, tier and segment name |
| `artifacts/production/cluster_profiles.parquet` | per-segment behaviour |
| `artifacts/production/segments.json` | labels, naming evidence, stability |
| `artifacts/production/course_catalogue.parquet` | 60 courses in canonical order |
| `artifacts/production/course_vectors.npy` | 60 × 18 content matrix |
| `artifacts/production/interactions.parquet` | 10,000 × 3, PII-free |
| `artifacts/production/popularity.parquet` | global and per-segment counts |

**276 KB total.** No Git LFS. No Docker.

Two load-time guarantees, both failing loudly and both tested:

- **Version compatibility** — a scikit-learn mismatch raises, because cross-version
  estimator loading usually *succeeds* and then returns different numbers.
- **Set integrity** — every file is hashed at write time and re-hashed at load. A
  half-updated directory, where each file is individually valid but they come from
  different runs, is detected.

---

## 9. Validation checks

| Check | Result |
| --- | --- |
| Full test suite | ✅ **219 passed** (163 previous + 56 new) |
| Experiments reproduce after the refactor | ✅ 8 of 8 exact |
| Raw workbook SHA-256 | ✅ `ed555e46…8cc0` unchanged |
| Raw data modified | ✅ No |
| Artifact set loads | ✅ 0.41 s, 0 problems |
| Clustering inference matches training | ✅ all 3,000 labels reproduced |
| No already-enrolled course recommended | ✅ 0 of 3,000 |
| Every learner receives a recommendation | ✅ 3,000 of 3,000 |
| PII in any persisted artifact | ✅ None (asserted per file) |
| No `fit` call on the serving path's estimators | ✅ scaler and clusterer are loaded |
| Docker artifacts | ✅ None |
| Notebook required for inference | ✅ No — two command-line scripts |

---

## 10. PASS / FAIL

### ✅ **PASS**

| Criterion | Evidence |
| --- | --- |
| Production ML modules work | §3 — twelve capabilities, each with evidence |
| Artifacts load successfully | §8 — 0.40 s, 0 problems, integrity and version checks pass |
| Recommendation generation works | §5 — all four tiers, 3,000 learners, 8 ms each |
| Explanations correspond to actual logic | §6 — six checks, each a test rather than a claim |
| Existing experiments remain reproducible | §7 — 8 of 8 exact |
| Tests pass | 219 passed |

### CLAUDE.md compliance

| § | Requirement | Status |
| --- | --- | --- |
| 6 | No fabricated results | ✅ Every figure here came from an executed run |
| 8 | Raw data immutable | ✅ Checksum verified; nothing writes to `data/raw/` |
| 16 | Explanations match scoring logic | ✅ Generated from the scorer's own decomposition |
| 17 | Privacy | ✅ PII dropped at ingestion; no persisted artifact contains it |
| 18 | Modular source, clear separation | ✅ Dependencies run strictly downward |
| 19 | Inference works without notebooks | ✅ `scripts/recommend.py` |
| 20 | No Docker | ✅ |
| 21 | App loads artifacts, never retrains | ✅ D-046 |
| 22 | Artifacts version-consistent | ✅ Manifest + per-file hash |
| 23 | Tests of the listed surfaces | ✅ 56 new tests including failure cases |
| 25 | Decisions documented | ✅ D-045…D-049 |
| 27 | Phase report with evidence | ✅ This document |

---

## 11. Unresolved issues

1. **Nothing beats random.** Unchanged. The dashboard, paper and executive summary
   must lead with it; the service already attaches the caveat to every result.
2. **The cold-start route needs an explicit UI path** (D-049) — no existing learner
   reaches it, so without one the fallback is invisible to a reviewer.
3. **The segmentation is a course-level split** (D-031) and must be described as
   one, not as a psychological typology.
4. **Gender gap requires monitoring** on real data — nominally significant,
   uncorrected, in a system using no demographic feature.
5. **Phase 0's two open items remain open**: the empty `claude.md.txt`, and the
   git-identity/authorship question (`Kartik <kartikshreekumar2006@gmail.com>` in
   the global git config vs the session account; `pyproject.toml` recorded a name
   inferred from that account). Both need confirmation before publication.
6. **Artifact freshness is not automated.** Editing the pipeline without re-running
   it leaves a stale set on disk. The manifest detects an *inconsistent* set, not an
   *old* one. Phase 6 should add a staleness check to the validation run.

   **RESOLVED 20 September 2026: the author is Kartik (`kartikshreekumar2006@gmail.com`), confirmed by the project owner. `pyproject.toml`, the paper byline and the rendered paper now all say so.**

---

## 12. Stop

Per CLAUDE.md §28, work **stops here**. Phase 5B will not begin automatically.

🔒 The ML design remains frozen. Phase 5A changed no model behaviour — the
reproducibility check is the evidence — and Phase 5B builds the Streamlit
application on top of `edupro.inference`, adding no ML logic of its own.
