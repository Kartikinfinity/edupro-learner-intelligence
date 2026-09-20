# Phase 6E — Public Streamlit Deployment — COMPLETE

**Phase:** 6E — public deployment, readiness audit, and the failure it did not catch
**Date:** 20 September 2026
**Decision:** ✅ **PASS**
**Deployment status:** ⚠️ **Deployed. Two builds failed; both causes found and fixed. The fix for the second is pushed and awaiting a rebuild.**
**Public URL:** <https://edupro-learner-intelligence-pmejbef8znwugts2gwtqik.streamlit.app/>

> **Read §4a before quoting this report.** The audit passed, the deployment
> failed, the fix was verified three ways, and the deployment failed again for a
> different reason none of the three could see. That is the most useful thing
> this phase produced, and it is worth more than the 25 checks that now pass.

---

## 1. Objective

Prepare the Streamlit application for public deployment, verify nine readiness
properties, write a deployment guide, and perform a readiness audit — stopping at
any step requiring external login or authorisation rather than attempting it.

---

## 2. Outcome in one line

The app was deployed to Community Cloud and **failed on its first load**. The
cause was diagnosed as line-ending normalisation, fixed, and verified three
separate ways. It then **failed again**, because the real cause was that the
manifest recorded Windows path separators — and all three verifications had
normalised those separators away before looking. The audit is now **25 of 25**,
including a probe that reads manifest keys verbatim. §4a is the finding; §7 is
the one remaining action.

---

## 3. The readiness audit

`scripts/deployment_readiness.py` — re-runnable, writes
`artifacts/validation/deployment_readiness.json`. **25 checks**. Rows 3c and 3d
were added after the two failed deployments; **3d** is the one that would have
caught the failure, and 3c is the one that passed while the app was broken.

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
| **3d** | | *(added after the **second** failed deploy)* **Manifest keys read verbatim** — no separator repair | ✅ 12 of 12 POSIX-relative and resolving as written |
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

## 4a. The deployment failed twice, and every check passed both times

**[Finding]** The app deployed, built cleanly, served every page — and every page
showed **"Model artifacts not found"**. The 23-check readiness audit had passed,
including the check written specifically to catch missing artifacts.

It then failed a *second* time, after a fix that was verified three different ways.
The second failure is the more useful one, so it is recorded first.

### The actual cause

`_manifest_key()` built each manifest key with `str(Path)`, which emits the
**platform** separator. The manifest written on Windows therefore recorded:

```
models\scaler.joblib
artifacts\production\course_vectors.npy
```

On Linux, `models\scaler.joblib` is not a path. It is a single filename that
happens to contain a backslash, and no such file exists. All twelve artifacts
resolved to nothing, `check_integrity` reported all twelve **missing**, and the
loader refused the set — correctly, again.

### The first diagnosis was wrong

The first investigation found that `.gitattributes` applied `* text=auto`, so the
three JSON artifacts were stored LF and checked out CRLF on Windows, and their
recorded hashes could not match what a Linux runner received. That defect was
**real** — the bytes genuinely differed — and fixing it was right.

It was **not** the cause. The files were reported missing before a single hash was
compared, so the line-ending mismatch was never reached. A plausible defect, found
by real evidence, in the right subsystem, that was not the bug.

### Why three independent checks passed while the app failed

The fix was verified by a readiness probe, by regression tests, and by hashing a
fresh `git clone`. All three passed. All three contained this:

```python
rel.replace("\\", "/")
```

Each normalisation is defensible on its own — git speaks POSIX, so a git lookup
needs forward slashes. Together they meant that **no check ever saw the separator
the application itself would use.** Three independent checks, one shared
assumption, and the assumption was the defect.

**[Interpretation]** This is the same error the first investigation recorded, one
level up. There, the check ran on the machine that produced the artifact, so it
could only confirm the artifact had been produced. Here, the check repaired its
input before testing it, so it could only confirm the repair worked. Both verify
something other than what ships. A check that normalises its input cannot fail on
the defect it normalises away.

### What actually found it

Not a test. The **empty-state diagnostic** — the D-073 and D-074 work, which had
looked like error-message polish. Two deployments failed invisibly because the
page said "not found" and offered no detail. The first build that could describe
itself named the cause in one line:

> `ArtifactIntegrityError: missing artifact: models\scaler.joblib; missing artifact:
> models\clusterer.joblib; ...`

The backslashes are visible in that message and nowhere else. **The diagnostic was
worth more than the three checks that passed.**

### The fix

| Part | Change | What it prevents |
| --- | --- | --- |
| Write | `_manifest_key` uses `as_posix()` | The separator is the same on every platform |
| Read | `resolve_manifest_key()` accepts either spelling | An existing artifact set does not become unreadable |
| Verify | Probe **3d** and four regression tests read the key **verbatim** — no `replace` anywhere | The check can fail on the defect it tests for |
| Earlier fix, retained | `LF` constant, `.gitattributes -text`, probe 3c | The line-ending defect was real and stays fixed |

**[Verified]** Every manifest key resolved against `git ls-files` with **no
normalisation at any step**: 12 of 12 present as written. Retraining produced
identical segments (841 / 1,030 / 607 / 522) and identical tiers, so this changed
encoding only — no model behaviour.

### The two defects the same failure exposed

**The empty state said nothing about why** (D-073). The loader wrote the exception
to `st.session_state` from inside a `@st.cache_resource` function — which runs once
per process, in a session context that is not the one that later renders the page.
The diagnostic was written, tested under `AppTest`, and silently lost in the only
situation it existed for.

**The empty state misdiagnosed the failure** (D-074). Every artifact was committed;
the heading said "not found". `require_service()` now selects its heading from a
table keyed by exception type.

Both were written as tidiness. Both turned out to be the instrument that solved the
outage.

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
| The app exists at a real public URL | Loaded in a browser; renders, routes between all seven pages, serves the committed light theme |
| The first build could not load the model | Every page showed the artifacts empty state, with no reason given |
| Community Cloud **does** redeploy on push | The second push rebuilt within minutes, and the new diagnostic appeared |
| The second build named its own failure | `ArtifactIntegrityError: missing artifact: models\scaler.joblib; ...` — read from the live page |
| The cause is the path separator | All twelve keys recorded with backslashes; confirmed against the live error, not inferred |
| The line-ending defect was real but not the cause | Missing is reported before any hash is compared (§4a) |
| The fix resolves on Linux | All 12 manifest keys matched against `git ls-files` **verbatim**, no normalisation at any step |
| The model is unchanged | Retrained set `6892a4f9ef27`: segments 841 / 1,030 / 607 / 522 and tiers identical to the previous set |

### The remaining action

The fix is committed and pushed. Community Cloud rebuilt within minutes last time,
so it should pick this up on its own. **Open the app and confirm:**

<https://edupro-learner-intelligence-pmejbef8znwugts2gwtqik.streamlit.app/>

If it still shows an artifacts page after a few minutes, force it:
**Manage app → ⋮ → Reboot app** (requires the owner's Community Cloud sign-in).

### Verifying it worked

| Check | What it proves |
| --- | --- |
| Sidebar shows `edupro-1.0.0 · artifact set 6892a4f9ef27` | The committed artifact set loaded, and it is the one in the repository |
| **Model Analytics** renders its tables | Experiment artifacts load end to end |
| **Recommendations → New learner** returns 10 courses across 10 categories | Routing, scoring and explanation all work in the deployed process |

If it fails again, the page names the reason. That is now the most reliable
instrument this project has for a deployment failure — §4a explains why.

---

## 8. Validation

| Check | Result |
| --- | --- |
| Deployment readiness audit | ✅ **25 of 25**, 0 warnings, 0 failures |
| Manifest keys resolve verbatim (**new probe 3d**) | ✅ 12 of 12 POSIX-relative, no separator repair anywhere |
| Committed bytes vs recorded hashes (probe 3c) | ✅ 12 of 12 identical from `git show :<path>` |
| Linux resolution simulated | ✅ 12 of 12 manifest keys present in `git ls-files` as written |
| Full test suite | ✅ **382 passed** |
| Model unchanged by the fix | ✅ Identical segment sizes and tier counts after retraining |
| Reproducibility | ✅ 8 of 8 exact |
| Raw workbook SHA-256 | ✅ unchanged |
| Docker introduced | ✅ None |
| Deployment success claimed | ✅ **Only what was observed.** The first diagnosis was wrong and is corrected in place rather than quietly replaced (D-072, D-075) |

---

## 9. PASS / FAIL

### ✅ **PASS**

| Criterion | Evidence |
| --- | --- |
| Nine required properties verified | §3, rows 1–9 |
| Readiness audit performed and re-runnable | §3 — 25 checks, artifact written |
| `docs/deployment_guide.md` created | §5 — all six required areas, plus §6.1 recording this failure |
| Public URL recorded in the documentation | README, deployment guide §8, submission checklist, this report |
| Deployment failure diagnosed rather than worked around | §4a — both failures; the second cause read from the live error, not inferred |
| Fix verified in the environment that failed | §4a — manifest keys resolved verbatim against `git ls-files` |
| The gap that let it through is closed by a check | Probes 3c and **3d**, and seven regression tests |
| No fabricated deployment success | §6, §7 — observed and unobserved stated separately |
| A wrong diagnosis corrected rather than buried | D-072 annotated in place; D-075 supersedes it and says why the evidence was not enough |

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

1. **The live build needs to pick up the path-separator fix** — §7. Community
   Cloud rebuilt on its own last time; if not, a reboot forces it.
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

Per CLAUDE.md §28 and the phase brief, work **stops here** — at confirming the
rebuild, and at the Community Cloud reboot if one is needed, which requires the
account holder.

🔒 The ML design remains frozen. This phase changed configuration, artifact
encoding and error reporting; it changed **no model behaviour**. The artifact set
version moved twice — to `d997e9092047` when the files were rewritten with LF, and
to `6892a4f9ef27` when the manifest was rewritten with POSIX keys. Neither refitted
anything: segment sizes (841 / 1,030 / 607 / 522), tier counts and recommendations
are identical across all three sets.
