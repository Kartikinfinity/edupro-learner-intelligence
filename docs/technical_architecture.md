# Technical Architecture

**System:** EduPro Student Segmentation & Personalized Course Recommendation
**Version:** `edupro-1.0.0` (frozen 19 September 2026)
**Audience:** engineers implementing, reviewing, operating or extending the system

This document describes *how the system is built*. For *why each choice was made*,
see `research/ARCHITECTURE_FREEZE.md`. For the visual view, see
`research/architecture_diagram.md`.

---

## 1. Design principles

| Principle | Consequence in the code |
| --- | --- |
| **Raw data is immutable** | The loader opens the workbook read-only and verifies its SHA-256. Nothing in `src/` writes to `data/raw/`. |
| **Leakage is prevented structurally, not by discipline** | `build_learner_features(frame)` computes only from the frame handed to it. There is no code path by which a feature builder can reach data it was not given. |
| **The app never fits a model** | Streamlit loads persisted artifacts. Every `fit` lives in `scripts/` or the training pipeline. |
| **Explanations come from the scorer** | `Scores` carries `components`; explanations are rendered from that decomposition, so they cannot name a signal the model did not use. |
| **PII never enters a frame** | Dropped at load time, not filtered downstream. |
| **Every number is reproducible** | Seed 42 throughout; every experiment script writes a JSON artifact with the workbook checksum in its provenance block. |

---

## 2. Module map

```
src/edupro/
├── config.py                  paths · sheet + key names · RANDOM_SEED · PII_COLUMNS · checksums
├── viz.py                     shared figure styling
│
├── data/
│   ├── schema.py              ColumnSpec / SheetSpec · COURSE_CATEGORIES · LEVEL_ORDER
│   ├── loader.py              load_all() · verify_raw_workbook() — drops PII at ingestion
│   ├── validation.py          12 check families → ValidationReport (reports, never repairs)
│   └── joins.py               build_interactions() · course_popularity(frame)
│
├── features/
│   └── learner.py             build_learner_features() · FEATURE_BLOCKS · CATEGORY_SHARE_COLUMNS
│
├── segmentation/
│   ├── representations.py     RepresentationSpec · build_representation() · REPRESENTATION_GRID
│   ├── clustering.py          fit_kmeans() · fit_hierarchical() · sweep helpers
│   ├── metrics.py             gap_statistic() · block_dominance() · intra_cluster_similarity()
│   ├── stability.py           bootstrap_jaccard() · subsample_consensus() · assess_stability()
│   └── profiling.py           derive_label() · compose_segment_names() · NAMING_VOCABULARY
│
├── recommendation/
│   ├── base.py                BaseRecommender · FitContext · Scores · minmax()
│   ├── baselines.py           10 scorers + DiversifiedFallback
│   └── hybrid.py              WeightedHybrid · TieredRecommender · tier_of() · TIER_BOUNDARIES
│
├── evaluation/
│   ├── splits.py              global_temporal_split() · apply_global_split() · leave_one_out_split()
│   ├── metrics.py             ndcg · precision (+ ceiling) · recall · hit_rate · mrr · coverage · gini
│   └── protocol.py            build_evaluation_set() · evaluate() · paired_bootstrap()
│                              · verify_leakage_controls()
└── explainability/            explanation rendering (Phase 5)
```

**Dependency direction is strictly downward.** `data` knows nothing of `features`;
`features` knows nothing of `segmentation`; `recommendation` depends on
`base.FitContext` and not on how the clustering was produced. `evaluation` depends
only on the `BaseRecommender` interface, so a new scorer is evaluable without
touching the evaluation code.

---

## 3. Data flow

```
data/raw/EduPro Online Platform.xlsx        (immutable, checksum-verified)
        |
        v  loader.load_all()                 PII dropped here
   LoadedData(users, courses, transactions, teachers)
        |
        v  validation.validate_all()         12 check families -> ValidationReport
        |
        v  joins.build_interactions()
   interactions  (10,000 rows x user/course/teacher attributes)
        |
        v  splits.global_temporal_split()
   +------------+--------------+------------+
   |  train     |  validation  |    test    |
   |  < 09-12   |  09-12→10-18 |  >= 10-18  |
   +------------+--------------+------------+
        |
        v  features.build_learner_features(train)      <- sees ONLY train
   learner features (25 cols + 12 category shares)
        |
        +--v  representations.build_representation(B_proportion)
        |     -> StandardScaler -> KMeans(k=4) -> cluster labels
        |
        v  base.build_fit_context(train, catalogue, features, clusters)
   FitContext -- shared by every scorer
        |
        v  TieredRecommender.fit(context)
        |
        v  evaluation.protocol.evaluate(recommender, context, evaluation_set)
   EvaluationResult (overall + per-tier + per-K)
```

Every stage is a pure function of its inputs. Re-running the pipeline with the
same seed and the same workbook reproduces every number in `research/`.

---

## 4. Key interfaces

### `FitContext`

The single object every scorer is fitted against. Constructed once per experiment
so all methods see byte-identical inputs — a precondition for the paired bootstrap
to be valid.

| Field | Meaning |
| --- | --- |
| `interactions` | training-window interactions only |
| `courses` | catalogue, ordered by `course_ids` |
| `course_ids` | canonical index order — a scorer's array position *is* this index |
| `features`, `clusters` | learner features and cluster labels from the same window |
| `seen` | `user -> set(course index)` from the **training window** (candidate exclusion) |
| `history_length` | `user -> int`, the basis for tier routing (leakage control L3) |

### `BaseRecommender`

```python
class BaseRecommender:
    name: str
    component: str

    def fit(self, context: FitContext) -> "BaseRecommender": ...
    def score(self, user, candidates) -> Scores: ...
    def recommend(self, user, k: int) -> list[int]: ...
```

`recommend()` is implemented once in the base class: it excludes `context.seen[user]`,
scores the remainder, and sorts with a deterministic tie-break on catalogue index.
A subclass implements only `_fit` and `_raw_scores`, so **no scorer can forget to
exclude already-enrolled courses** — the exclusion is structural, and a test asserts
it for every registered scorer.

### `Scores`

```python
@dataclass
class Scores:
    candidates: np.ndarray              # catalogue indices
    total: np.ndarray                   # final score per candidate
    components: dict[str, np.ndarray]   # per-signal contribution, same length

    def contribution_at(self, course_index) -> dict[str, float]: ...
```

`components` is what makes explanations faithful. A component with weight zero is
absent from the dict, so an explanation generator cannot name it.

---

## 5. Segmentation subsystem

```python
features = build_learner_features(train_frame, users=users)
spec     = next(s for s in REPRESENTATION_GRID if s.name == "B_proportion")
matrix   = build_representation(features, spec).matrix       # StandardScaler inside
labels   = fit_kmeans(matrix, n_clusters=4).labels_
profiles = compose_segment_names(features, labels, allowed_features=spec.columns)
```

- `REPRESENTATION_GRID` holds all ten arms compared in Phase 3A; the production arm
  is selected **by name**, so the rejected arms stay runnable for audit.
- `allowed_features` restricts naming to columns the clustering actually used.
- `assess_stability()` returns per-cluster bootstrap Jaccard, subsample consensus
  ARI and seed ARI — run at fit time, persisted with the profiles.

## 6. Recommendation subsystem

```python
router = TieredRecommender(routes={
    "insufficient": DiversifiedFallback(),   # 0 training interactions
    "minimal":      ContentBased(),          # 1
    "moderate":     ClusterPopularity(),     # 2-8
    "rich":         ClusterPopularity(),     # 9+
}).fit(context)

top_10 = router.recommend(user_id, k=10)
```

`tier_of(history_length)` reads `TIER_BOUNDARIES` and is called with
`context.history_length` — training-window counts, never full history. This is
leakage control **L3**, and it is the control most easily broken by a careless
refactor, so it is asserted by test.

`WeightedHybrid` remains in the codebase, fitted and tested, because it is the
evaluated alternative in the decision matrix. It is **not** wired into the
production router.

## 7. Evaluation subsystem

| Concern | Mechanism |
| --- | --- |
| Split | `global_temporal_split` — V at the 70th percentile date, T at the 80th |
| Evaluable set | learners with ≥1 training interaction **and** ≥1 held-out interaction |
| Primary metric | NDCG@10 |
| Co-primary | catalogue coverage@10 |
| Always shown | the **random baseline**, and Precision@K's **analytical ceiling** |
| Significance | `paired_bootstrap` over per-learner NDCG differences |
| Leakage | `verify_leakage_controls()` runs L1–L6 in-run at every evaluation |

### The six leakage controls

| ID | Control | Enforced by |
| --- | --- | --- |
| L1 | Features computed from the training window only | `build_learner_features` reads only its argument |
| L2 | Candidates exclude training-window enrollments only | `BaseRecommender.recommend` |
| L3 | Tier assignment from training history only | `context.history_length` |
| L4 | Held-out items never appear in any fitted structure | `FitContext` built from `frames["train"]` |
| L5 | Popularity counted on the training window | `course_popularity(frame)` takes the frame explicitly |
| L6 | Model selection on validation; test opened once | Pre-registered protocol; enforced by review |

`verify_leakage_controls()` is itself tested with a deliberately leaky fixture, so
the checker is known to be capable of failing — a checker that has never failed is
not evidence.

---

## 8. Artifacts and versioning

```
models/
├── scaler.joblib               fitted StandardScaler
├── clusterer.joblib            fitted KMeans(k=4)
├── feature_schema.json         column names, order, dtypes, block map
├── model_config.json           k, encoding, tier boundaries, seed
└── manifest.json               artifact_set_version + library versions + workbook SHA-256

artifacts/
├── learner_features.parquet    features + cluster label
├── cluster_profiles.parquet    centroids, sizes, labels, stability
├── course_catalogue.parquet    course attributes + content vectors
└── popularity.parquet          global + per-cluster counts (training window)
```

**Two load-time guarantees, both failing loudly:**

1. **Library version match.** scikit-learn does not support loading estimators
   across versions; a mismatch changes numbers silently rather than raising. The
   manifest records `sklearn`, `numpy` and `pandas` versions and the loader
   compares them.
2. **Matched artifact set.** Every artifact carries the same
   `artifact_set_version`. Re-fitting the clustering changes the inputs to cluster
   popularity, so pairing a new clusterer with a stale popularity table would be
   wrong in a way no single-component test would catch.

---

## 9. Application layer (Phase 5 target)

```
app/
├── Home.py                     overview, dataset facts, the headline finding
└── pages/
    ├── 1_Learner_Explorer.py   profile, segment, history (pseudonymous IDs)
    ├── 2_Segments.py           cluster visualisation + comparison
    ├── 3_Recommendations.py    top-K + explanation + category/level filters
    └── 4_Methodology.py        evaluation results, limitations, random reference
```

Contract:

- `st.cache_resource` for estimators, `st.cache_data` for frames.
- **No `fit` call anywhere under `app/`** — assertable by grep and by test.
- Learners addressed by pseudonymous `UserID`; no name or email is loadable
  because the loader already dropped those columns.
- Wherever recommendation quality is displayed, **the random reference is displayed
  beside it**. This is a hard requirement, not a stylistic one: "Hit Rate 36%" is
  meaningless without "random achieves 35%".

## 10. Deployment

Streamlit Community Cloud from the repository. Python 3.13, `requirements.txt`.
**No Docker.** Because the platform deploys from the repo and cannot run the
training pipeline, the final artifact set must be committed — the `.gitignore` rule
for `models/` is relaxed at Phase 5 (open item P-2).

Cold start: artifacts load in well under a second (60×60 similarity matrix, a few
thousand-row tables); no lazy-loading or LFS required.

---

## 11. Testing

| Suite | Tests | Covers |
| --- | --- | --- |
| `test_phase0_environment.py` | 31 | layout, imports, config, **no Docker artifacts**, reproducibility |
| `test_data_pipeline.py` | 36 | loading, checksum, **PII absence**, 12 validation families, joins, features |
| `test_segmentation.py` | 37 | representations, clustering, metrics, stability, naming, **naming-vocabulary guard** |
| `test_recommendation.py` | 59 | all scorers, candidate exclusion, tiering, hybrid, metrics, leakage checker, fallback diversity |
| **Total** | **163** | |

Notable guards, each protecting a mistake that was actually made during development:

- Naming may not use a feature the model did not see.
- The leakage checker must fail on a leaky fixture.
- A zero-weight component must not appear in an explanation.
- `DiversifiedFallback` must span more categories than plain popularity.

---

## 12. Reproduction

```bash
python -m pytest tests -q
python scripts/run_data_audit.py
python scripts/run_segmentation_experiments.py
python scripts/run_recommendation_experiments.py
python scripts/validate_final_architecture.py
```

Each script writes a JSON artifact whose `provenance` block records the workbook
SHA-256, the seed, the split dates and the evaluable-learner count. Any figure in
`research/` can be traced to the artifact and script that produced it.

---

## 13. Extension points

| To add… | Do this | Nothing else changes |
| --- | --- | --- |
| a new scorer | subclass `BaseRecommender`, implement `_fit` / `_raw_scores` | exclusion, tie-breaking and evaluation are inherited |
| a new representation | append a `RepresentationSpec` to `REPRESENTATION_GRID` | the sweep picks it up |
| a new metric | add to `evaluation/metrics.py`, reference in `protocol.evaluate` | all methods gain it |
| a new tier | add to `TIER_BOUNDARIES` and `routes` | per-tier reporting is automatic |

**What must not change without reopening the freeze:** k, the representation, the
tier boundaries, the routed scorers, or the split dates. See
`research/ARCHITECTURE_FREEZE.md` §Freeze for the four conditions.
