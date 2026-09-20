# Phase 6E — Public Streamlit Deployment — COMPLETE (blocked at authorisation)

**Phase:** 6E — public deployment preparation and readiness audit
**Date:** 20 September 2026
**Decision:** ✅ **PASS** for everything automatable
**Deployment status:** ⏳ **Blocked at one step: GitHub sign-in on Streamlit Community Cloud**
**Public URL:** **Not yet issued.** No deployment success is claimed anywhere in this project.

---

## 1. Objective

Prepare the Streamlit application for public deployment, verify nine readiness
properties, write a deployment guide, and perform a readiness audit — stopping at
any step requiring external login or authorisation rather than attempting it.

---

## 2. Outcome in one line

The repository is **deployment-ready: 23 of 23 audit checks pass**. Creating the
app on Streamlit Community Cloud requires signing in to <https://share.streamlit.io>
with the GitHub account that owns the repository, which is an interactive
authorisation only the account holder can give. §7 states the exact remaining
action.

---

## 3. The readiness audit

`scripts/deployment_readiness.py` — re-runnable, writes
`artifacts/validation/deployment_readiness.json`.

| # | Requirement from the brief | Check | Result |
| --- | --- | --- | --- |
| 1 | No secrets hardcoded | 191 tracked files scanned for credentials, tokens, private keys | ✅ 0 matches |
| 1b | | `.streamlit/secrets.toml` untracked and git-ignored | ✅ |
| 1c | | App contains no `st.secrets` reference at all | ✅ nothing to configure |
| 2 | No personal data exposed | 25 served files vs 3,000 real emails and 3,058 real names | ✅ 0 matches |
| 2b | | Learners keyed by pseudonymous `UserID` | ✅ |
| 3 | Artifacts reliably available | Every manifest file checked against `git ls-files` | ✅ 12 of 12 tracked, 293 KB |
| 3b | | Artifact set internally consistent | ✅ every file matches its recorded hash |
| 4 | No retraining on startup | No model-fitting call anywhere under `app/` | ✅ 11 files |
| 4b | | Service cached with `st.cache_resource` | ✅ once per process |
| 5 | Deterministic startup | Two independent loads compared | ✅ identical labels for all 3,000 learners and an identical top-10 |
| 5b | | Single seed | ✅ `RANDOM_SEED = 42` |
| 6 | Dependency compatibility | No Windows- or macOS-only packages | ✅ 12 packages |
| 6b | | Versions pinned exactly | ✅ all |
| 6c | | Every import declared in `requirements.txt` | ✅ 8 third-party imports |
| 6d | | Python range declared | ✅ `>=3.11,<3.14` |
| 7 | Relative paths repo-safe | No absolute path literals in `app/` or `src/` | ✅ |
| 7b | | Project root derived from `__file__` | ✅ |
| 8 | No local-machine-only paths | **Linux case-sensitivity check** | ✅ 18 referenced filenames, no mismatch |
| 9 | No Docker | No Dockerfile, compose file or Procfile | ✅ |
| 10 | *(added)* Public error disclosure | `showErrorDetails` | ✅ `type` |
| 10b | *(added)* Theme determinism | `theme.base` | ✅ `light` |
| 10c | *(added)* Entry point exists | `app/streamlit_app.py` | ✅ |
| 11 | *(added)* File size limits | Largest tracked file | ✅ 3.1 MB of a 13 MB repository |

### Three checks that exist because they catch invisible failures

**[Design decision]** An audit is worth something only if it tests what actually
breaks deployments, not what is easy to check.

**Linux case sensitivity.** This project was developed on Windows, where
`Models/Scaler.joblib` and `models/scaler.joblib` are the same file. On Community
Cloud they are not. A case mismatch works locally forever and fails on the first
deploy. The probe extracts every filename referenced in code and matches it
case-exactly against the tracked tree.

**Fresh-clone availability.** The app loads an artifact set. If any file in that
set were git-ignored, the app would work for the author and show an empty state to
everyone else — a failure that is invisible on the machine that built it. The probe
checks the manifest against `git ls-files`, deliberately **not** against the
filesystem.

**Public error disclosure.** A config that prints full tracebacks is helpful
locally and an information leak on a public URL. This one found something (§4).

---

## 4. What the audit found and fixed

### 4.1 Full tracebacks would have been shown to any visitor

**[Finding]** `.streamlit/config.toml` had `showErrorDetails = "full"`, set in
Phase 5B so that a deployment problem would be visible to whoever opened the page.
That reasoning was right for a local app and wrong for a public URL: `"full"`
prints server-side file paths, library versions and internal structure to anyone
who triggers an error.

**[Fix]** Changed to `"type"`. A visitor sees the exception type and a generic
message — enough for a reviewer to report "it showed a `KeyError`" — while the full
message and traceback go to the server log, where the owner reads them in the
Community Cloud log viewer.

**[Verified]** The four valid values were read from Streamlit's own
`ShowErrorDetailsConfigOptions` enum rather than guessed, the config was confirmed
to parse (`showErrorDetails = 'type'`), and the app was started to confirm it still
serves HTTP 200.

### 4.2 A bug in the audit script itself

The secrets probe contained `if "\.streamlit/secrets\.toml" in " ".join(tracked)`
— regex escaping inside a plain string comparison, which raised a `SyntaxWarning`
and could never match. Replaced with a direct set membership test.

**[Interpretation]** Worth recording because the probe still *passed*: the second
half of the `or` did the real work. A check that passes for the wrong reason is the
kind of thing an audit is supposed to catch in other people's code, and this one
was in mine.

---

## 5. Deployment guide

`docs/deployment_guide.md` covers the six required areas:

| Section | Contents |
| --- | --- |
| GitHub repository | URL, visibility, branch, size |
| Main application file | `app/streamlit_app.py`, and why no `pip install -e .` is needed |
| Dependency configuration | All 12 pinned packages with what each is for; the scikit-learn pin explained; the Python version range |
| Artifact availability | The 12 committed files, load time, and the empty-state behaviour if they were missing |
| Streamlit deployment settings | The exact click sequence, field values, and the committed `.streamlit/config.toml` |
| Troubleshooting | Nine symptoms mapped to cause and fix, plus three post-deployment verification checks |

**[Design decision]** The sign-in flow was **verified against the live site**
rather than written from memory: <https://share.streamlit.io> presents a single
**Continue to sign-in** button on a signed-out landing page. Deployment
instructions that name buttons which do not exist are worse than none.

No sign-in was attempted. The browser pane reached the public landing page and
stopped there.

---

## 6. What was deliberately not done

| Action | Why not |
| --- | --- |
| Signing in to Streamlit Community Cloud | Requires the owner's GitHub credentials. Entering someone's credentials is prohibited, and the phase brief directs stopping at exactly this action |
| Authorising Streamlit's GitHub OAuth app | Same — it grants a third party read access to the account's repositories; that is the owner's decision to make |
| Creating the app / choosing the public URL | Downstream of the sign-in |
| Claiming a deployment URL | There is no URL. Fabricating one would be the single worst thing this phase could produce |

---

## 7. The exact remaining action

**Everything else is done.** This is the complete remaining work:

1. Open <https://share.streamlit.io>
2. Click **Continue to sign-in** → **GitHub**, sign in as **`Kartikinfinity`**,
   and authorise Streamlit to read your repositories.
3. Click **Create app** → deploy a public app from GitHub.
4. Enter:

   | Field | Value |
   | --- | --- |
   | Repository | `Kartikinfinity/edupro-learner-intelligence` |
   | Branch | `main` |
   | Main file path | `app/streamlit_app.py` |

5. **Advanced settings** → Python **3.13** (3.12 also works; **not** 3.14).
   Leave *Secrets* empty.
6. **Deploy.** First build takes about 3–6 minutes.

**Then tell me the URL** and I will record it in `docs/deployment_guide.md` §8,
`README.md` under *Deployment*, and `docs/submission_checklist.md`.

### Verifying it worked

| Check | What it proves |
| --- | --- |
| Sidebar shows `edupro-1.0.0 · artifact set b658773c9db8` | The committed artifact set loaded, and it is the same one in the repository |
| **Model Analytics** renders its tables | Experiment artifacts load end to end |
| **Recommendations → New learner** returns 10 courses across 10 categories | Routing, scoring and explanation all work in the deployed process |

---

## 8. Validation

| Check | Result |
| --- | --- |
| Deployment readiness audit | ✅ **23 of 23**, 0 warnings, 0 failures |
| App starts with the changed config | ✅ HTTP 200; `showErrorDetails = 'type'`, `theme.base = 'light'` |
| Full test suite | ✅ **373 passed** |
| Reproducibility | ✅ 8 of 8 exact |
| Document claims | ✅ 96 of 96 |
| Raw workbook SHA-256 | ✅ unchanged |
| Docker introduced | ✅ None |
| Deployment success claimed | ✅ **No** — no URL exists yet |

---

## 9. PASS / FAIL

### ✅ **PASS** for the automatable scope

| Criterion | Evidence |
| --- | --- |
| Inspected requirements, entry point, artifacts, structure, compatibility | §3 — 23 checks |
| Nine required properties verified | §3, rows 1–9 |
| Community Cloud configuration prepared | `.streamlit/config.toml`, committed |
| `docs/deployment_guide.md` created | §5 — all six required areas |
| Readiness audit performed | §3, re-runnable, artifact written |
| Stopped at the authorisation step | §6, §7 |
| No fabricated deployment success | §7 — the URL field reads "not yet issued" everywhere |
| Remaining action documented exactly | §7 — six numbered steps |

---

## 10. Open items

1. **The app is not yet deployed** — §7 is the remaining action.
2. **Nothing beats random.** Unchanged, and stated on the dashboard the
   deployment will serve.
3. **Repository About section is empty** on GitHub — description and topics are a
   two-minute web-UI task that would help a visitor.
4. **Gender gap** is disclosed in the paper and summary but still not surfaced in
   the dashboard.
5. **No PDF of the executive summary.**
6. **Artifact staleness is not automated.**

---

## 11. Stop

Per CLAUDE.md §28 and the phase brief, work **stops here** — specifically at the
Streamlit Community Cloud sign-in, which is the one action that requires the
account holder.

🔒 The ML design remains frozen. This phase changed one configuration value and
added one audit script; it changed no model behaviour.
