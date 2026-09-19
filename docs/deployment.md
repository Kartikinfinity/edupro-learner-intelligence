# Running and Deploying the Dashboard

**Application:** EduPro learner segmentation and course recommendation dashboard
**Model version:** `edupro-1.0.0`
**Platform:** Streamlit. **No Docker** (CLAUDE.md §20).

---

## 1. Run it locally

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

The dashboard opens at <http://localhost:8501>.

**If the artifact set is missing**, every page shows an empty state naming the
command that produces it rather than a stack trace:

```bash
python scripts/train_production_model.py
```

That takes about 20 seconds and writes 12 files totalling 276 KB. It is only
needed once — the artifact set is committed to the repository, so a fresh clone
can run the dashboard immediately.

### Without the dashboard

The same model is available from the command line, which is useful for checking a
deployment or scripting against it:

```bash
python scripts/recommend.py --describe          # which artifact set is loaded
python scripts/recommend.py --user U00001       # explained top-10
python scripts/recommend.py --user U00001 --category "Data Science" --json
```

---

## 2. Dependencies

Runtime dependencies are pinned in `requirements.txt` and validated on
**Python 3.13.9**. The application itself needs only:

| Package | Version | Used for |
| --- | --- | --- |
| `streamlit` | 1.64.0 | the application |
| `plotly` | 7.1.0 | every chart in the dashboard |
| `pandas` | 3.0.6 | tabular data |
| `numpy` | 2.5.3 | numeric arrays |
| `scikit-learn` | 1.9.1 | loading the fitted scaler and clusterer |
| `joblib` | 1.6.0 | reading the persisted estimators |
| `pyarrow` | 25.0.1 | reading the parquet artifacts |

`openpyxl`, `matplotlib` and `seaborn` are needed by the training pipeline and the
experiment scripts, not by the dashboard. `requirements.lock.txt` records the fully
frozen environment for exact reproduction.

**The scikit-learn version matters.** The fitted estimators are loaded from disk,
and scikit-learn does not support loading an estimator across versions — a mismatch
usually loads successfully and then produces subtly different numbers. The manifest
records the versions that wrote the artifacts and the loader compares them, so a
mismatch fails loudly at startup instead of silently at inference.

---

## 3. Deploying to Streamlit Community Cloud

1. Push the repository to GitHub.
2. At <https://share.streamlit.io>, create an app pointing at:
   - **Repository:** this repository
   - **Branch:** `main`
   - **Main file path:** `app/streamlit_app.py`
3. Set the Python version to **3.13** in *Advanced settings* if it is offered.
   The project supports 3.11–3.13; the platform's default may be older.
4. Deploy.

No secrets, environment variables or external services are required. The dashboard
reads only files inside the repository.

### Why the artifacts are committed

Streamlit Community Cloud deploys from the repository and cannot run the training
pipeline, so an untracked artifact set would mean an application with no model. The
full set is 276 KB — small enough to track directly, with no need for Git LFS. The
`.gitignore` rule for `models/` names the five files explicitly rather than
un-ignoring the directory, so a stray experiment written into `models/` is still
ignored.

Tracked artifacts:

```
models/                        manifest.json, model_config.json, feature_schema.json,
                               scaler.joblib, clusterer.joblib
artifacts/production/          learner_features, learner_projection, cluster_profiles,
                               course_catalogue, course_vectors, interactions,
                               popularity, segments.json
```

### Cold start and memory

The service loads in **0.41 s** and answers a recommendation in about **8 ms**. The
whole artifact set sits comfortably within Community Cloud's memory limit: the
largest single object is a 3,000-row feature table.

Loading happens **once per process**, not once per page view —
`RecommendationService.load` is wrapped in `st.cache_resource`, and derived frames
use `st.cache_data`. The application never fits a model (CLAUDE.md §21); a test
asserts that no ML call appears anywhere under `app/`.

---

## 4. Configuration

`.streamlit/config.toml` is deliberately minimal: usage statistics off, full error
details shown in the browser so a deployment problem is visible to whoever opens
the page, and no theme override — the dashboard is legible under both the light and
dark Streamlit themes, and chart colours are chosen in `app/lib/shell.py` to work
against either background.

---

## 5. Updating the deployed model

The ML design is frozen (`research/ARCHITECTURE_FREEZE.md`). Updating the artifact
set for new **data** — not a new design — is:

```bash
python scripts/train_production_model.py
python -m pytest tests -q
git add models artifacts/production
git commit -m "Refresh production artifacts"
git push
```

Streamlit Community Cloud redeploys on push.

Changing the model *design* requires the four conditions in decision log D-044: a
recorded decision, new experimental evidence, an impact assessment across every
affected layer, and a full test-suite run.

---

## 6. Verifying a deployment

```bash
python scripts/recommend.py --describe
```

This prints the loaded artifact set version, the learner and course counts, the
segment names and any artifact problems. An empty `problems` list means the
manifest, the library versions and every file hash agree.

To check the whole application, run the test suite — it executes every page exactly
as the server would:

```bash
python -m pytest tests/test_app.py -q
```
