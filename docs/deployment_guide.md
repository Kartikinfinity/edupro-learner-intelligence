# Public Deployment Guide — Streamlit Community Cloud

**Application:** EduPro learner segmentation and course recommendation dashboard
**Repository:** <https://github.com/Kartikinfinity/edupro-learner-intelligence>
**Model version:** `edupro-1.0.0` · artifact set `b658773c9db8`
**Platform:** Streamlit Community Cloud. **No Docker** (CLAUDE.md §20).

**Readiness:** audited by `scripts/deployment_readiness.py` — **23 of 23 checks pass**.

> **This guide stops at one step that cannot be automated.** Creating the app on
> Streamlit Community Cloud requires signing in to <https://share.streamlit.io>
> with the GitHub account that owns the repository. That is an interactive
> authorisation only the account holder can give. Everything before it is done;
> §5 is the exact sequence of clicks.

---

## 1. GitHub repository

| | |
| --- | --- |
| URL | `https://github.com/Kartikinfinity/edupro-learner-intelligence` |
| Visibility | Public |
| Branch to deploy | `main` |
| Size | 13 MB — well inside the platform's limits |

Community Cloud clones the repository and installs from it. It **cannot** run the
training pipeline, which is why the model artifacts are committed (§4).

## 2. Main application file

```
app/streamlit_app.py
```

This is the value to type into the *Main file path* box. It declares the
navigation and nothing else; each of the seven pages lives under `app/pages/`.

The entry point makes `app/` importable before loading anything, and
`app/lib/loaders.py` adds `src/` to the path, so the `edupro` package resolves
without being pip-installed. No `setup.py`, no `pip install -e .` step, no
`PYTHONPATH` configuration is needed on the platform.

## 3. Dependency configuration

Community Cloud installs `requirements.txt` from the repository root
automatically. Nothing else is required.

| Package | Version | Needed for |
| --- | --- | --- |
| `streamlit` | 1.64.0 | the application |
| `plotly` | 7.1.0 | every chart |
| `pandas` | 3.0.6 | tabular data |
| `numpy` | 2.5.3 | arrays |
| `scikit-learn` | 1.9.1 | **loading** the fitted scaler and clusterer |
| `scipy` | 1.18.1 | scikit-learn dependency used directly |
| `joblib` | 1.6.0 | reading the persisted estimators |
| `pyarrow` | 25.0.1 | reading the parquet artifacts |
| `matplotlib`, `seaborn` | 3.11.2, 0.13.2 | the experiment scripts (imported by the package) |
| `openpyxl`, `PyYAML` | 3.1.5, 6.0.3 | the training pipeline |

Every version is pinned exactly, and the audit confirms **no package is
Windows- or macOS-only**, so the Linux build will not fail on a platform wheel.

**The scikit-learn pin is the one that matters.** The app loads estimators that
were pickled by scikit-learn 1.9.1. scikit-learn does not support loading across
versions, and the failure is silent — a mismatched pickle usually loads and then
returns different numbers. The artifact manifest records the versions that wrote
it and the loader compares them, so a mismatch surfaces as a visible problem in
the sidebar rather than as quietly wrong recommendations.

**Python version.** The project declares `requires-python = ">=3.11,<3.14"`. Pick
**3.13** in *Advanced settings* if offered; **3.12** also works. Do not pick 3.14 —
the project excludes it and the install will fail.

## 4. Artifact availability

The dashboard **never trains**. It loads a persisted artifact set, and that set is
committed to the repository:

```
models/                     manifest.json · model_config.json · feature_schema.json
                            scaler.joblib · clusterer.joblib
artifacts/production/       learner_features.parquet · learner_projection.parquet
                            cluster_profiles.parquet · segments.json
                            course_catalogue.parquet · course_vectors.npy
                            interactions.parquet · popularity.parquet
```

**12 files, 293 KB.** The audit verifies every file named in the manifest is
tracked by git — not merely present on the author's disk, which is the failure
that makes an app work for its author and show an empty state to everyone else.

Loading takes **0.41 s** and happens **once per process**, cached with
`st.cache_resource`. A recommendation takes about **8 ms**.

**If the artifacts were ever missing**, the app does not crash: every page shows
an empty state naming the command that regenerates them
(`python scripts/train_production_model.py`). This is tested from a cold process,
not just assumed.

## 5. Streamlit deployment settings

> **This section requires signing in to Streamlit Community Cloud with the
> GitHub account `Kartikinfinity`. That authorisation cannot be automated.**

1. Open <https://share.streamlit.io>. The landing page reads *"Streamlit
   Community Cloud — A place for the community to publicly share Streamlit
   apps"* with a single **Continue to sign-in** button. *(Verified 20 September
   2026.)*
2. Click **Continue to sign-in** and choose **GitHub**. Sign in as
   `Kartikinfinity` and authorise Streamlit — it needs read access to list and
   clone the repository. This is the step that cannot be automated.
3. Once signed in, click **Create app** and choose the option for deploying a
   public app from a GitHub repository.
4. Fill in exactly:

   | Field | Value |
   | --- | --- |
   | Repository | `Kartikinfinity/edupro-learner-intelligence` |
   | Branch | `main` |
   | Main file path | `app/streamlit_app.py` |
   | App URL | your choice, e.g. `edupro-learner-intelligence` |

5. Open **Advanced settings** and set **Python version** to **3.13**
   (3.12 also works). Leave *Secrets* empty — the app reads none.
6. Click **Deploy**.

First build takes roughly 3–6 minutes, most of it installing pandas, numpy,
scikit-learn and pyarrow. Subsequent pushes to `main` redeploy automatically in
under a minute.

**No secrets, environment variables or external services are required.** The
audit confirms the app contains no `st.secrets` reference at all, so there is
nothing to configure and nothing that can be left misconfigured.

### Configuration already committed

`.streamlit/config.toml` is read by the platform. It sets:

| Setting | Value | Why |
| --- | --- | --- |
| `theme.base` | `light` | Every viewer sees what the README screenshots show |
| `client.showErrorDetails` | `type` | A visitor sees the exception *type*; the full traceback goes to the server log only, so a public URL does not print internal paths |
| `browser.gatherUsageStats` | `false` | No telemetry |

## 6. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| **"Model artifacts not found"** on every page | The artifact set is missing from the clone | Confirm `models/` and `artifacts/production/` are committed: `git ls-files models artifacts/production` should list 13 files. They are committed as of `edupro-1.0.0` |
| **Sidebar shows "Artifact problems"** | scikit-learn version differs from the one that wrote the pickles | Check the platform actually installed `scikit-learn==1.9.1`; if it silently resolved something else, the build log will show it |
| **Build fails installing `pyarrow`** | Python version outside the supported range | Set Python to 3.13 or 3.12 in *Advanced settings*. 3.14 is explicitly excluded |
| **`ModuleNotFoundError: edupro`** | The path shim did not run | Confirm the main file path is exactly `app/streamlit_app.py`, not `streamlit_app.py` |
| **`ModuleNotFoundError: lib`** | A page was launched directly as the main file | The main file must be the entry point; individual pages are reached through navigation |
| **App builds but is blank** | Usually a crashed first run | Open **Manage app → Logs**. With `showErrorDetails = "type"` the browser shows only the exception type; the full traceback is in the log |
| **Charts render but tables are empty** | A parquet file failed to load | The manifest hash check would have flagged a corrupt file; re-run `python scripts/train_production_model.py` and push |
| **Slow first load after idle** | Community Cloud sleeps inactive apps | Expected. The first visitor wakes it; subsequent loads use the cached model |
| **Changes pushed but not live** | Redeploy not triggered | **Manage app → Reboot app** |

### Verifying a live deployment

Once the URL is live, three checks confirm it is serving the real model:

1. The sidebar shows **`edupro-1.0.0 · artifact set b658773c9db8`** — the same set
   as `models/manifest.json` in the repository.
2. **Model Analytics** loads its tables. Those numbers come from the committed
   experiment artifacts; if they render, artifact loading works end to end.
3. **Recommendations → New learner (cold start)** returns ten courses spanning
   ten of the twelve categories. That exercises the routing, the scorer and the
   explanation layer in one click.

The same checks can be run locally without a browser:

```bash
python scripts/recommend.py --describe
```

---

## 7. Readiness audit

`python scripts/deployment_readiness.py` — re-runnable, writes
`artifacts/validation/deployment_readiness.json`.

| # | Check | Result |
| --- | --- | --- |
| 1 | No hardcoded secrets | ✅ 191 tracked files scanned, 0 matches |
| 1b | `secrets.toml` not committed | ✅ untracked and git-ignored |
| 1c | App requires no secrets | ✅ no `st.secrets` reference |
| 2 | No personal data served | ✅ 25 served files vs 3,000 emails and 3,058 names, 0 matches |
| 2b | Pseudonymous identifiers | ✅ keyed by `UserID` |
| 3 | Artifacts committed | ✅ all 12 manifest files tracked, 293 KB |
| 3b | Artifact set internally consistent | ✅ every file matches its recorded hash |
| 4 | No training on startup | ✅ no model-fitting call under `app/` |
| 4b | Model cached per process | ✅ `st.cache_resource` |
| 5 | Deterministic startup | ✅ two loads agree on all 3,000 labels and an identical top-10 |
| 5b | Seeded | ✅ `RANDOM_SEED = 42` |
| 6 | No platform-specific dependencies | ✅ 12 packages, none OS-locked |
| 6b | Versions pinned | ✅ all exact |
| 6c | Every import declared | ✅ 8 third-party imports, all in `requirements.txt` |
| 6d | Python version declared | ✅ `>=3.11,<3.14` |
| 7 | No absolute paths | ✅ all derived from `PROJECT_ROOT` or `__file__` |
| 7b | Project root is package-relative | ✅ `Path(__file__).resolve().parents[2]` |
| 8 | Filename case matches on Linux | ✅ 18 referenced filenames, no mismatch |
| 9 | No Docker or container config | ✅ none |
| 10 | Error detail on a public URL | ✅ `type` |
| 10b | Theme pinned | ✅ `light` |
| 10c | Entry point exists | ✅ `app/streamlit_app.py` |
| 11 | No file over GitHub's limit | ✅ 13 MB total, largest file 3.1 MB |

**23 of 23 pass.**

Three of these exist because they catch failures invisible on the development
machine: Linux **case sensitivity** (Windows treats `Models/` and `models/` as the
same path), **fresh-clone availability** (an artifact that is on disk but
git-ignored), and **public error disclosure**.

---

## 8. Deployment status

| | |
| --- | --- |
| Repository pushed | ✅ `main` at `Kartikinfinity/edupro-learner-intelligence` |
| Readiness audit | ✅ 23 of 23 |
| App created on Community Cloud | ⏳ **Requires the account holder to sign in** (§5) |
| Public URL | *Not yet issued — will be recorded here once the app is deployed* |

**Nothing about a live deployment is claimed in this repository until the URL
exists.** When it does, record it in this table, in `README.md` under
*Deployment*, and in `docs/submission_checklist.md`.
