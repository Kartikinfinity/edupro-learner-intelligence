# Final Validation — Summary and Reproduction

**Status:** ✅ **PASS** · 19 September 2026
**Model:** `edupro-1.0.0`, artifact set `b658773c9db8`
**Data:** `EduPro Online Platform.xlsx`, SHA-256 `ed555e46…8cc0`, verified unchanged


> **Historical record.** The artifact set named here is the one current when this report was written. The submitted configuration is `6892a4f9ef27`, recorded in [`FINAL_FREEZE.md`](FINAL_FREEZE.md). The set was rewritten twice afterwards for platform-independent encoding; no model was refitted and the segments are identical.
This is the one-page verdict and the exact reproduction procedure. The evidence
behind it is in [`final_validation_report.md`](final_validation_report.md).

---

## Verdict

| Check | Probes | Result |
| --- | --- | --- |
| 1 · Data integrity and validation | 11 | ✅ all pass |
| 2 · Feature pipeline and edge cases | 9 | ✅ all pass |
| 3 · Leakage | 7 | ✅ all pass |
| 4 · Clustering | 8 | ✅ all pass |
| 5 · Recommendations | 13 | ✅ all pass |
| 6 · Explainability (30,000 explanations) | 6 | ✅ all pass |
| 7 · Privacy | 5 | ✅ all pass |
| 8 · Automated tests | 257 | ✅ all pass |
| 9 · Streamlit application | 20 | ✅ all pass |
| 10 · Clean environment | 8 steps | ✅ installs and runs end to end |
| 11 · Reproducibility | 8 stored results | ✅ all reproduce exactly |

**Three real defects were found and fixed** during this phase; each is now held by
a regression test. See `final_validation_report.md` §12.

1. The data validator **crashed** on a missing column instead of reporting it.
2. The "no candidates" error **misdiagnosed its own cause**.
3. Cluster labels carried **two dtypes**, so identical answers compared unequal.

---

## What a reviewer should know before reading the dashboard

**No recommendation method beats random ranking on this dataset.** Eleven methods,
leakage-free temporal split, 791 evaluable learners: every 95% confidence interval
on the paired NDCG@10 difference against random contains zero. This is a property
of the data — Phase 2 established that course choice is statistically
indistinguishable from popularity-weighted chance — not a defect in the pipeline,
and the system states it on the first screen, in every recommendation footer and
throughout the analytics page.

The segmentation **is** real: four segments, all reappearing under resampling
(bootstrap Jaccard 0.967–0.994), each holding at least 17% of learners. It is a
course-level grouping rather than a psychological typology, and is described as
one.

---

## Reproduction

### 1. Environment

```bash
py -3.13 -m venv .venv
.venv/Scripts/activate            # Windows;  source .venv/bin/activate elsewhere
pip install -r requirements.txt
pip install -e . --no-deps
```

| | |
| --- | --- |
| **Python** | **3.13.9** — supported range `>=3.11,<3.14` |
| **Runtime dependencies** | `requirements.txt`, pinned exactly |
| **Dev dependencies** | `requirements-dev.txt` (pytest 9.1.1, jupyterlab) |
| **Fully frozen environment** | `requirements.lock.txt` |
| **Seed** | `edupro.config.RANDOM_SEED = 42`, governing every stochastic step |

Key pinned versions: `pandas==3.0.6` · `numpy==2.5.3` · `scipy==1.18.1` ·
`scikit-learn==1.9.1` · `joblib==1.6.0` · `pyarrow==25.0.1` · `streamlit==1.64.0`
· `plotly==7.1.0` · `openpyxl==3.1.5`.

> **Use `py -3.13` explicitly.** On a machine whose default `python` is 3.14 the
> project correctly refuses to install, but the first failure you see is an
> unrelated dependency error.
>
> **Install at a short path on Windows.** A ~250-character installation path
> fails with an opaque missing-DLL `OSError` — that is `MAX_PATH`, not a broken
> dependency.

### 2. Model artifacts

```bash
python scripts/train_production_model.py
```

Takes about 16 seconds and writes **12 files, 276 KB**:

```
models/          manifest.json · model_config.json · feature_schema.json
                 scaler.joblib · clusterer.joblib
artifacts/production/
                 learner_features.parquet · learner_projection.parquet
                 cluster_profiles.parquet · segments.json
                 course_catalogue.parquet · course_vectors.npy
                 interactions.parquet · popularity.parquet
```

The artifact set is **committed**, so a fresh clone runs without this step.
Re-running it reproduces identical segments (841 / 1,030 / 607 / 522).

### 3. Application

```bash
streamlit run app/streamlit_app.py
```

Opens at <http://localhost:8501>. Loads in 0.41 s and fits nothing.
Deployment notes: [`../docs/deployment.md`](../docs/deployment.md).

### 4. Command line

```bash
python scripts/recommend.py --describe                  # which artifact set is loaded
python scripts/recommend.py --user U00001               # explained top-10
python scripts/recommend.py --user U00001 --category "Data Science" --level Beginner
python scripts/recommend.py --user NEW-LEARNER          # cold-start route
```

### 5. Verification

```bash
python -m pytest tests -q                    # 257 passed, ~2 min
python scripts/verify_reproducibility.py     # 8 stored results, recomputed
python scripts/adversarial_audit.py          # 59 probes, ~2.5 min
python scripts/app_smoke_test.py             # 20 probes
```

### 6. Regenerating the research artifacts

Only needed to reproduce the experiments themselves; the results are committed.

```bash
python scripts/run_data_audit.py
python scripts/run_segmentation_experiments.py
python scripts/run_recommendation_experiments.py
python scripts/validate_final_architecture.py
```

Each writes a JSON artifact whose `provenance` block records the workbook
checksum, the seed, the split dates and the evaluable-learner count.

---

## Reproducibility evidence

`scripts/verify_reproducibility.py` recomputes headline results from scratch and
compares them to the stored artifacts. Run in the development environment **and**
in a clean one built from `requirements.txt`:

| Result | Stored | Recomputed |
| --- | --- | --- |
| Silhouette, `B_proportion` k=4 | 0.194600 | 0.194600 |
| Mean bootstrap Jaccard, k=4 | 0.989200 | 0.989200 |
| NDCG@10, random | 0.110215 | 0.110215 |
| NDCG@10, content-based | 0.119113 | 0.119113 |
| NDCG@10, cluster popularity | 0.113773 | 0.113773 |
| NDCG@10, architecture C | 0.110354 | 0.110354 |
| Hit Rate@10, architecture C | 0.305284 | 0.305284 |
| Coverage@10, architecture C | 1.000000 | 1.000000 |

**8 of 8 exact, in both environments.**

---

## Standing limitations

These are properties of the data or the study design, not open defects. They are
repeated here so no reader mistakes a passing audit for a claim of accuracy.

1. **No method beats random.** The system is deployed for coverage, robustness,
   interpretability and honest degradation, not for demonstrated accuracy.
2. **The dataset is assessed as almost certainly synthetic** (D-025). The segments
   describe a generative process, not learner psychology.
3. **The segmentation is a course-level split** (D-031).
4. **The cluster structure is not algorithm-independent**: average-linkage
   hierarchical clustering agrees with K-Means at ARI 0.019.
5. **Engagement Lift is a proxy**, never a causal measurement, and is always shown
   beside random's own lift (1.084 against 1.046).
6. **A gender gap is under monitoring**: −0.0283 NDCG@10, nominally significant but
   uncorrected for four strata tests, in a system that uses no demographic feature.
7. **Artifact freshness is not automated**: editing the pipeline without re-running
   it leaves a stale set on disk. The manifest detects an *inconsistent* set, not
   an *old* one.
