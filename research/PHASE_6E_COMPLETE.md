# Phase 6E — Public Streamlit Deployment — COMPLETE

**Phase:** 6E — public deployment, readiness audit, and the failure it did not catch
**Date:** 20 September 2026
**Decision:** ✅ **PASS**
**Deployment status:** ⚠️ **Deployed. The first build failed; the cause is found, fixed and pushed. The running build has not yet picked up the fix.**
**Public URL:** <https://edupro-learner-intelligence-pmejbef8znwugts2gwtqik.streamlit.app/>

> **Read §4a before quoting this report.** The audit passed 23 of 23 checks and
> the deployment still failed. That is the most useful thing this phase produced.

---

## 1. Objective

Prepare the Streamlit application for public deployment, verify nine readiness
properties, write a deployment guide, and perform a readiness audit — stopping at
any step requiring external login or authorisation rather than attempting it.

---

## 2. Outcome in one line

The app was deployed to Community Cloud, **failed on its first load**, and the
cause was a class of defect the 23-check audit was structurally unable to see: it
verified the artifacts on the Windows machine that wrote them, not the bytes a
Linux runner receives. The audit is now **24 of 24** with a probe that closes
exactly that gap, and a fresh clone of the pushed commit reproduces all twelve
recorded hashes. §7 states the one remaining action.

---

## 3. The readiness audit

`scripts/deployment_readiness.py` — re-runnable, writes
`artifacts/validation/deployment_readiness.json`. **24 checks**; row 3c was
added after the first deployment failed and is the one that would have caught it.

| # | Requirement from the brief | Check | Result |
| --- | --- | --- | --- |
| 1 | No secrets hardcoded | 191 tracked files scanned for credentials, tokens, private keys | ✅ 0 matches |
| 1b | | `.streamlit/secrets.toml` untracked and git-ignored | ✅ |
| 1c | | App contains no `st.secrets` reference at all | ✅ nothing to configure |
| 2 | No personal data exposed | 25 served files vs 3,000 real emails and 3,058 real names | ✅ 0 matches |
| 2b | | Learners keyed by pseudonymous `UserID` | ✅ |
| 3 | Artifacts reliably available | Every manifest file checked against `git ls-files` | ✅ 12 of 12 tracked, 293 KB |
| 3b | | Artifact set internally consistent | ✅ every file matches its recorded hash |
| **3c** | | *(added after the failed deploy)* **Manifest vs the bytes git stores**, via `git show :<path>` | ✅ 12 of 12 — a Linux checkout reproduces the manifest exactly |
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

## 4a. The deployment failed, and the audit had passed

**[Finding]** The app deployed, built cleanly, served every page — and every page
showed **"Model artifacts not found"**. The 23-check readiness audit had passed,
including the check written specifically to catch missing artifacts.

### What actually happened

`.gitattributes` began with `* text=auto`, so git normalised text files to LF in
storage and converted them back to CRLF on Windows checkout. Three of the twelve
artifacts are JSON. Their SHA-256 hashes were recorded **on Windows, from CRLF
bytes**, into `models/manifest.json`. Community Cloud checked the repository out on
Linux and received **LF bytes**, which hash differently. `check_integrity` compared
them, found three mismatches, and refused the set — correctly. The refusal was the
system working. The manifest was wrong.

### Why the audit could not have caught it

| The audit checked | On what | Why it passed |
| --- | --- | --- |
| Every manifest file is tracked by git | `git ls-files` | True — all 12 were committed |
| Every file matches its recorded hash | **the Windows working copy** | True *by construction* — the same machine wrote both |

Both probes were sound. Neither could fail, because neither ever looked at the
bytes **git stores**. The working copy and the repository were assumed to be the
same object, and on a line-ending-converting checkout they are not.

**[Interpretation]** This is the general shape of a deployment bug: not a wrong
computation, but a verification performed in the environment that produced the
artifact rather than the environment that will consume it. A check that runs where
the thing was made can only confirm that it was made.

### The fix, in three parts

| Part | Change | What it prevents |
| --- | --- | --- |
| Write | `LF` constant in `persistence.py`; every JSON artifact written with `newline=LF` | The artifact never contains CRLF, whatever the platform |
| Store | `.gitattributes`: `models/*.json` and `artifacts/production/*.json` marked `-text` | Git does not convert them back on checkout |
| Verify | Readiness probe **3c** and `test_committed_artifact_bytes_match_the_recorded_hashes` hash `git show :<path>` — the index, not the disk | The check now runs against what a clone receives |

**[Verified]** A fresh `git clone` of the pushed commit was hashed independently:
**12 of 12 artifacts match the manifest, and no JSON artifact contains CRLF.**
That is the condition that failed, tested the way it failed.

### Two further defects the same failure exposed

**The empty state said nothing about why** (D-073). The loader wrote the exception
to `st.session_state` from inside a `@st.cache_resource` function — which runs once
per process, in a session context that is not the one that later renders the page.
The diagnostic was written, tested under `AppTest`, and silently lost in the only
situation it existed for. It is now a module-level value, rendered with `st.error`.

**The empty state misdiagnosed the failure** (D-074). Every artifact was present;
the heading said "not found". `require_service()` now selects its heading from a
table keyed by exception type, so an integrity failure says so. Two regression
tests hold the three headings distinct.

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
| Signing in to Streamlit Community Cloud | Requires the owner's GitHub credentials. Entering someone's credentials is prohibited, and the phase brief directs stopping at exactly this action. **The account holder performed the sign-in and the deploy.** |
| Authorising Streamlit's GitHub OAuth app | Same — it grants a third party read access to the account's repositories; that is the owner's decision |
| Rebooting the app from the Cloud dashboard | Behind the same sign-in. This is the one action still outstanding (§7) |
| Claiming the app works before seeing it work | The URL is real and recorded. What is **not** claimed is that the live build currently serves the model — §7 says exactly what was observed |

---

## 7. State of the deployment, and the one remaining action

### What is established

| Fact | How it was established |
| --- | --- |
| The app exists at a real public URL | Loaded in a browser; it renders, routes between all seven pages, and serves the committed light theme |
| The first build could not load the model | Every page showed the artifacts empty state |
| The cause is the line-ending mismatch | Three artifacts' on-disk bytes compared against their git blobs (§4a) |
| The fix is on GitHub | Commit `64532da`, pushed; local and remote `HEAD` verified identical |
| A clone of that commit would load | Fresh clone hashed independently: **12 of 12 match, no CRLF** |
| The **running** build does not yet include the fix | The page still shows the pre-fix empty state — specifically, it lacks the `st.error` diagnostic that the pushed code always renders on a failed load. Community Cloud has not rebuilt |

**[Design decision]** The last row is stated from evidence rather than assumed.
Community Cloud exposes no build identifier to an unauthenticated visitor: the app
metadata endpoints all return the SPA shell. The only observable that distinguishes
the two builds is the diagnostic block, and it is absent.

### The remaining action

Community Cloud normally redeploys within a minute or two of a push. It has not.
The app needs to be rebuilt by hand:

1. Open <https://share.streamlit.io> and sign in as **`Kartikinfinity`**.
2. Find **edupro-learner-intelligence** in the app list.
3. Open the **⋮** menu → **Reboot app**. If a reboot alone does not take, delete
   the app and redeploy it from `main`, which forces a clean checkout.
4. Wait about 2–4 minutes.

### Verifying it worked

| Check | What it proves |
| --- | --- |
| Sidebar shows `edupro-1.0.0 · artifact set d997e9092047` | The committed artifact set loaded, and it is the one in the repository |
| **Model Analytics** renders its tables | Experiment artifacts load end to end |
| **Recommendations → New learner** returns 10 courses across 10 categories | Routing, scoring and explanation all work in the deployed process |

If it still fails, the page will now **name the reason** — that is what D-073 and
D-074 changed. The heading and the `The loader reported:` line identify the cause.

---

## 8. Validation

| Check | Result |
| --- | --- |
| Deployment readiness audit | ✅ **24 of 24**, 0 warnings, 0 failures |
| Committed bytes vs recorded hashes (**new probe 3c**) | ✅ 12 of 12 identical from `git show :<path>` |
| Fresh clone of the pushed commit | ✅ 12 of 12 hashes reproduce; 0 JSON artifacts contain CRLF |
| App starts with the changed config | ✅ HTTP 200; `showErrorDetails = 'type'`, `theme.base = 'light'` |
| Full test suite | ✅ **378 passed** |
| Reproducibility | ✅ 8 of 8 exact |
| Raw workbook SHA-256 | ✅ unchanged |
| Docker introduced | ✅ None |
| Deployment success claimed | ✅ **Only what was observed** — the URL is real and recorded; the live build is stated as not yet carrying the fix |

---

## 9. PASS / FAIL

### ✅ **PASS**

| Criterion | Evidence |
| --- | --- |
| Nine required properties verified | §3, rows 1–9 |
| Readiness audit performed and re-runnable | §3 — 24 checks, artifact written |
| `docs/deployment_guide.md` created | §5 — all six required areas, plus §6.1 recording this failure |
| Public URL recorded in the documentation | README, deployment guide §8, submission checklist, this report |
| Deployment failure diagnosed rather than worked around | §4a — cause identified by direct byte comparison, not inference |
| Fix verified in the environment that failed | §4a — fresh clone, not the working copy |
| The gap that let it through is closed by a check | Probe 3c and three regression tests |
| No fabricated deployment success | §6, §7 — what is observed and what is not are stated separately |

**[Design decision]** This phase is marked PASS with a live failure outstanding,
which needs justifying. The phase's deliverable was a deployable repository and an
honest account of its state. The repository is deployable — demonstrated by clone,
not asserted. The outstanding item is a rebuild on a third-party host behind a
sign-in this project cannot perform, and it is documented with the exact steps.
Marking it FAIL would say the engineering is unfinished; it is not. Marking it
PASS *silently* would be the dishonesty the phase brief warns against, which is
why the status line, §4a and §7 all state it plainly.

---

## 10. Open items

1. **The live build has not rebuilt** — §7 is the remaining action.
2. **Nothing beats random.** Unchanged, and stated on the dashboard the
   deployment serves.
3. **Repository About section is empty** on GitHub — description and topics are a
   two-minute web-UI task that would help a visitor.
4. **Gender gap** is disclosed in the paper and summary but still not surfaced in
   the dashboard.
5. **No PDF of the executive summary.**
6. **Artifact staleness is not automated.**

---

## 11. Stop

Per CLAUDE.md §28 and the phase brief, work **stops here** — at the Community
Cloud rebuild, which requires the account holder.

🔒 The ML design remains frozen. This phase changed configuration, artifact
encoding and error reporting; it changed **no model behaviour**. The artifact set
version moved from `b658773c9db8` to `d997e9092047` because the files were
rewritten with LF, not because anything was refitted — the cluster assignments and
the recommendations are identical.
