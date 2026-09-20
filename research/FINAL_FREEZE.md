# Final Freeze — Submission Configuration of Record

**Frozen:** 20 September 2026
**Model version:** `edupro-1.0.0`
**Artifact set:** `6892a4f9ef27`
**Source workbook:** SHA-256 `ed555e4613e6a210b73af0d4f64e34bd43cb59650041e2bd05f8a8ffbf5d8cc0`
**Seed:** 42

This is the configuration the submitted deliverables describe and the public
application serves. Anything not recorded here is not part of the submission.

**Reopening the freeze** requires one of the four conditions in D-044 and a
version bump. It is not reopened to improve a number.

---

## 1. Final model configuration

| Property | Value |
| --- | --- |
| Algorithm | `KMeans(init="k-means++", n_init=10, random_state=42)` |
| Clusters | **k = 4** |
| Representation | **`B_proportion`** — behaviour only |
| Scaler | `StandardScaler`, fitted and persisted |
| Model input | **25 columns** |
| Demographics | **Excluded** — by experiment, not assumption (ARI 1.000 between variants; demographic block explains 0.0004 of between-cluster variance) |
| Teacher signals | **Excluded** — EXP-014 |

**The 25 model input columns**

`total_courses` · `avg_courses_per_category` · `enrollment_frequency` ·
`avg_course_rating` · `avg_spend` · `diversity_score` · `learning_depth_index` ·
`free_ratio` · `diversity_ratio` · `activity_span_days` · 12 × `cat_share_*` ·
`preflevel_Beginner` · `preflevel_Intermediate` · `preflevel_Advanced`

**Why k = 4.** Chosen under constraints fixed *before* any result was seen:
smallest cluster ≥ 5% of the population, and no cluster below bootstrap Jaccard
0.60. The highest silhouette in the whole study (0.7159) was **rejected** as a
scaling artefact of two mandated features whose IQR is exactly zero.

---

## 2. Final segment configuration

| Cluster | Segment name | Learners | Share | Mean courses | Mean diversity | Mean rating |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | Beginner-level Single-course learners | 841 | 28.0% | 1.48 | 1.45 | 3.26 |
| 1 | Advanced-level Non-repeating learners | 1,030 | 34.3% | 1.64 | 1.60 | 2.89 |
| 2 | Intermediate-level Single-session Single-course learners | 607 | 20.2% | 1.35 | 1.32 | 3.36 |
| 3 | Category-repeating High-volume learners | 522 | 17.4% | 11.98 | 7.77 | 3.14 |

Names are **derived mechanically** from each cluster's strongest standardised
deviations (beyond ±0.40 SD), never chosen by hand.

### Segment quality

| Metric | Value | Reading |
| --- | --- | --- |
| Silhouette | **0.1946** | Modest separation — reported, not flattered |
| Intra-cluster similarity | **0.4163** | Official behavioural-consistency metric |
| Calinski–Harabasz | 403.69 | — |
| Davies–Bouldin | 2.1453 | — |
| Mean bootstrap Jaccard | **0.9892** (100 resamples) | Highly stable |
| Clusters above Jaccard 0.75 | **4 of 4** | All reliable |
| Seed-stability ARI | **0.9996** | Near-identical across seeds |
| Smallest cluster share | 19.7% | Well above the 5% floor |
| Per-cluster silhouette | 0.129 / 0.398 / 0.162 / 0.137 | — |

**Honest reading:** the clusters are *stable and interpretable* but *not widely
separated*. Both facts are reported together everywhere.

---

## 3. Final recommendation configuration

**Architecture:** tiered switching recommender (Burke). One route per history
tier; no learned blending weights in production.

| Tier | History | Route | Learners (full history) |
| --- | --- | --- | --- |
| `insufficient` | 0 | `DiversifiedFallback` | 0 |
| `minimal` | 1 | `ContentBased` | 1,620 |
| `moderate` | 2–8 | `ClusterPopularity` | 926 |
| `rich` | ≥ 9 | `ClusterPopularity` | 454 |

Default list length **k = 10**. Already-enrolled courses are always excluded.

**Coverage accounting** (fit window, the basis for the reported metrics):

| | |
| --- | --- |
| Total learners | 3,000 |
| With training history | 2,650 |
| Receiving a recommendation | **3,000 (100%)** |
| Receiving a *personalised* recommendation | 2,650 |
| On the cold-start fallback | 350 |
| Mean candidate pool | 57.4 of 60 |
| Learners with an empty candidate pool | **0** |

**Note on the two tier tables.** The production artifacts are fitted on the full
history, where every learner has at least one interaction, so no learner is
`insufficient`. The coverage table is computed on the fit window, where 350
learners have no prior history. Both are correct; they answer different
questions, and the manifest records which window produced the artifacts.

---

## 4. Final evaluation metrics

**Protocol A — global temporal split (primary, leakage-free).** Validation cut
2025-09-12, test cut 2025-10-18. 791 evaluable learners, 1,625 held-out
interactions.

### The headline result

> **0 of 11 methods are significantly better than random ranking.**
> Every 95% confidence interval on the paired per-learner NDCG@10 difference
> contains zero. Random ranks **7th of 12**. Five methods score below it.

| Method | NDCG@10 | Δ vs random | 95% CI | Significant |
| --- | --- | --- | --- | --- |
| hybrid | 0.1206 | +0.0162 | [−0.0033, +0.0355] | No |
| content_based | 0.1191 | +0.0147 | [−0.0040, +0.0340] | No |
| preference_match | 0.1165 | +0.0121 | [−0.0068, +0.0305] | No |
| **cluster_popularity (deployed)** | **0.1138** | **+0.0093** | **[−0.0092, +0.0271]** | **No** |
| tiered | 0.1117 | +0.0072 | [−0.0126, +0.0245] | No |
| user_user_profile | 0.1105 | +0.0061 | [−0.0113, +0.0251] | No |
| **random (reference)** | **0.1102** | — | — | — |
| teacher_affinity | 0.1076 | +0.0032 | [−0.0150, +0.0209] | No |
| global_popularity | 0.1072 | +0.0028 | [−0.0155, +0.0205] | No |
| item_item_cf | 0.1047 | +0.0002 | [−0.0179, +0.0174] | No |
| rating | 0.1034 | −0.0010 | [−0.0193, +0.0163] | No |
| user_user_history | 0.0947 | −0.0098 | [−0.0269, +0.0067] | No |

### The four official metrics

| Official metric | Value | Note |
| --- | --- | --- |
| Silhouette Score | **0.1946** | Cluster quality |
| Intra-Cluster Similarity | **0.4163** | Behavioural consistency |
| Recommendation Precision@10 | **0.0424** | Random: 0.0422. Attainable ceiling **0.2054** |
| Engagement Lift **(Proxy)** | **1.084** | Random scores **1.046** on the same measure. **A proxy, not measured causal impact.** |

Deployed method, other @10 figures: Hit Rate 0.3590 · Recall 0.2080 ·
MRR 0.1412 · Coverage 0.75.

**Why precision looks low.** Learners average about two held-out interactions, so
a perfect ranker would still leave eight of ten slots uncreditable. Precision is
always reported against that ceiling.

**Reproduction:** 8 of 8 stored values recompute exactly to six decimal places.

---

## 5. Final application status

| | |
| --- | --- |
| Framework | Streamlit 1.64.0, 7 pages |
| Entry point | `app/streamlit_app.py` |
| Model loading | `st.cache_resource` — once per process, never refitted |
| Theme | Pinned light, so every viewer sees what the README shows |
| Error disclosure | `showErrorDetails = "type"` |
| Smoke test | **20 probes, 20 pass** |
| ML logic in the UI | **None** |

Pages: Executive Overview · Learner Profile · Recommendations · Segment
Intelligence · Cluster Visualization · Segment Comparison · Model Analytics.

---

## 6. Final deployment status

| | |
| --- | --- |
| **Public URL** | <https://edupro-learner-intelligence-pmejbef8znwugts2gwtqik.streamlit.app/> |
| Platform | Streamlit Community Cloud |
| Repository | `Kartikinfinity/edupro-learner-intelligence`, branch `main` |
| Readiness audit | **25 of 25** |
| Artifact set served | `6892a4f9ef27` — the set committed here |
| Verification | Opened in a browser and exercised end to end |
| Docker | Not introduced |

Three builds failed before one worked. The causes — a line-ending mismatch (real
but **not** the cause), Windows path separators in the manifest (the actual
cause), and a failure reason stored beside the cache instead of inside it — are
documented in `docs/deployment_guide.md` §6.1 and decisions D-072 to D-077. The
wrong first diagnosis is annotated as wrong rather than rewritten.

---

## 7. Known limitations

1. **No recommendation method beats random ranking on this dataset.** Established
   by permutation test in Phase 2, before any recommender existed. Course
   popularity is near-uniform (Gini 0.042) and 54% of learners have taken exactly
   one course. The system is built, tested and deployed; the measurement says the
   ranking signal is not present.
2. **Engagement Lift is a proxy.** An offline agreement ratio. Real engagement
   impact needs an online controlled experiment this project did not run.
3. **The dataset is almost certainly synthetic** (D-025). Zero missing values
   across 27 columns and implausibly regular cardinalities. Learned structure may
   partly be a generator artefact.
4. **Cluster separation is modest.** Silhouette 0.1946. Stable and interpretable,
   not widely separated.
5. **Segmentation is not demonstrated to improve recommendation.** Cluster
   popularity beats global popularity by +0.0066 NDCG@10 but does not beat random
   (+0.0093, CI contains zero).
6. **Single dataset, single time window.** 2025-01-01 to 2025-12-30. Nothing here
   generalises beyond it without re-validation.
7. **Not re-run on independent hardware.** Reproduced across Windows and Linux
   from one codebase, which is the stronger half of the check, but not
   independently re-executed on a third machine.

---

## 8. Frozen artifact set

12 files, each SHA-256 recorded in `models/manifest.json`, verified on every
application start.

| File | Purpose |
| --- | --- |
| `models/scaler.joblib` | Fitted `StandardScaler` |
| `models/clusterer.joblib` | Fitted `KMeans`, k = 4 |
| `models/feature_schema.json` | Column contract |
| `models/model_config.json` | Frozen configuration |
| `artifacts/production/learner_features.parquet` | 3,000 learner profiles |
| `artifacts/production/learner_projection.parquet` | 2D display projection |
| `artifacts/production/cluster_profiles.parquet` | Segment profiles |
| `artifacts/production/segments.json` | Names and derivation evidence |
| `artifacts/production/course_catalogue.parquet` | 60 courses |
| `artifacts/production/course_vectors.npy` | Content representation |
| `artifacts/production/interactions.parquet` | Serving interactions |
| `artifacts/production/popularity.parquet` | Global and per-cluster popularity |

Environment recorded with the artifacts: Python 3.13.9 · numpy 2.5.3 ·
pandas 3.0.6 · scikit-learn 1.9.1 · joblib 1.6.0. A scikit-learn mismatch is a
**hard error** at load, because a cross-version pickle usually loads and then
returns subtly different numbers rather than raising.

---

## 9. Exact run instructions

Verified on a clean checkout. No notebook is required at any step.

### Install

```bash
git clone https://github.com/Kartikinfinity/edupro-learner-intelligence.git
```

```bash
python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt
```

On macOS or Linux use `source .venv/bin/activate`. Python must be ≥ 3.11 and < 3.14.

### Run the dashboard against the committed model

```bash
streamlit run app/streamlit_app.py
```

### Get recommendations without the UI

```bash
python scripts/recommend.py --user U00001
```

### Reproduce the model from the raw workbook

```bash
python scripts/train_production_model.py
```

### Reproduce the experiments

```bash
python scripts/run_segmentation_experiments.py
```

```bash
python scripts/run_recommendation_experiments.py
```

### Verify everything

```bash
python -m pytest -q
```

```bash
python scripts/verify_reproducibility.py
```

```bash
python scripts/verify_paper_claims.py
```

```bash
python scripts/adversarial_audit.py
```

```bash
python scripts/deployment_readiness.py
```

**Expected:** 385 tests pass · 8 of 8 values reproduce exactly · 96 document
claims verified · 59 of 59 adversarial probes pass · 25 of 25 readiness checks
pass.

---

## 10. Freeze declaration

The configuration above is the submission of record. It was independently
audited on 20 September 2026 (`research/FINAL_AUDIT_REPORT.md`): 43 of 43
mandatory requirements traceable and verified, 9 defects found and fixed, 0
critical items outstanding.

🔒 **Frozen.**
