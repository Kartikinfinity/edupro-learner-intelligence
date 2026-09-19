# Production ML Research

**Phase:** 1 — research and methodology investigation
**Date:** 19 September 2026
**Reference keys `[Rxx]`** resolve in `literature_review.md` §10.
**Scope:** reproducible pipelines, artifact persistence, experiment/production
separation, Streamlit deployment, and testing.

---

## 1. Why this is a research area and not just implementation

Sculley et al. argue that ML systems accrue technical debt through mechanisms
ordinary software does not have — entanglement, hidden feedback loops, undeclared
consumers, data dependencies and configuration debt — and that the ML code itself
is a small fraction of a real system [R33]. Breck et al. turn this into 28
concrete tests and monitoring practices scored as a production-readiness rubric
[R34].

> **[INFERENCE]** This project's specific exposure is **entanglement**, and it is
> structural rather than incidental. The segmentation feeds the cluster-popularity
> recommender, which feeds the hybrid, whose optimal weights were tuned against
> that specific clustering. Re-fitting the clustering silently changes all three
> downstream behaviours. Nothing in the code would fail; the numbers would just
> quietly become wrong. §2 below is the mitigation.

---

## 2. Artifact persistence and the CACE problem

### 2.1 What must be persisted

CLAUDE.md §22 requires the scaler, encoder, clustering model, course
representations, recommendation metadata, feature schema and model configuration.

| Artifact | Contents | Why persisted |
| --- | --- | --- |
| `scaler.joblib` | Fitted `StandardScaler`/`RobustScaler` | Inference must apply the **training** scaling, not re-fit |
| `encoder.joblib` | Fitted categorical encoder | Same — and category ordering must be stable |
| `clusterer.joblib` | Fitted K-Means | §21: never retrain on startup |
| `course_representations.parquet` | Course feature vectors + 60×60 similarity | Trivially small; avoids recomputation |
| `cluster_profiles.parquet` | Centroids, sizes, labels, per-cluster metrics | Drives the dashboard's segment comparison |
| `popularity.parquet` | Global and per-cluster popularity, **from the training window only** | Leakage control L5 |
| `feature_schema.json` | Column names, order, dtypes, blocks | Detects schema drift at load |
| `model_config.json` | k, encoding, weights, seed | Reproducibility |
| **`manifest.json`** | **Artifact-set version + environment versions + source checksum** | §2.2 |

### 2.2 The manifest is the mitigation

scikit-learn's documentation states plainly that loading a model in a different
version than the one that fitted it is unsupported, and that pickle-family
formats (joblib included) carry documented security risks and should only be
loaded from trusted, verified sources [R36].

> **[INFERENCE] Two distinct requirements follow, and they are often conflated.**
>
> **Version consistency (§22).** The manifest records the Python, scikit-learn,
> numpy and `edupro` versions used to fit, plus the raw workbook's SHA-256.
> Loading **verifies** these and **fails loudly** on mismatch. A silent
> version mismatch does not usually crash — it produces subtly different numbers,
> which is worse than a crash because it is invisible.
>
> **Matched-set loading (CACE, [R33]).** The manifest also records a single
> `artifact_set_version`, and every artifact carries it. Loading verifies all
> artifacts share one version. This prevents the specific failure where a
> regenerated clustering is paired with a stale popularity table — the resulting
> recommendations would be wrong in a way no test of either component alone would
> detect.
>
> **Trusted-source condition [R36].** Satisfied here: artifacts are produced by
> this repository's own pipeline and committed alongside it. Worth stating
> explicitly in the deployment documentation rather than leaving implicit, since
> the general warning against loading pickles does apply to anyone reusing this
> pattern with third-party artifacts.

### 2.3 Format choices

| Data | Format | Rationale |
| --- | --- | --- |
| Fitted estimators | `joblib` | scikit-learn's documented option for objects with large numpy arrays [R36] |
| Tabular artifacts | `parquet` (pyarrow) | Typed, compressed, fast; preserves dtypes across the pandas 3.x string-dtype change |
| Config, schema, manifest | `json` | Human-readable and diffable — these are the artifacts a reviewer should be able to inspect without running code |

> **[INFERENCE]** Keeping config and schema as JSON rather than pickling them is
> deliberate: a reviewer can see exactly what k, which weights and which features
> produced a result by opening a file, which supports the project's
> defensibility requirement directly.

---

## 3. Separating experimentation from production

CLAUDE.md §18 requires modular source; §19 forbids notebooks being the only
implementation; §21 forbids the app retraining on startup.

```
  notebooks/          scripts/              app/
  exploration         pipeline entry points  Streamlit UI
       \                   |                    /
        \                  |                   /
         +--------- src/edupro/ ---------------+
                    (all reusable logic)
                            |
                    models/ + artifacts/
                    (persisted, versioned)
```

**The rule: nothing outside `src/edupro/` defines modelling logic.** Notebooks,
scripts and the app are all consumers.

> **[INFERENCE]** The failure mode this prevents is specific and common: logic is
> prototyped in a notebook, partially copied into the app, the two drift, and the
> research paper's numbers no longer describe what the app does. On a project
> whose *primary deliverable is a research paper* (§29 P1), that divergence is
> not a maintenance annoyance — it invalidates the paper. This is the concrete
> reason ADR-0001 chose a package-first layout over notebook-first.

**Pipeline as scripts, not notebooks.** Each Phase 3–5 stage gets an idempotent
script in `scripts/` that reads declared inputs and writes declared outputs. The
full pipeline is therefore reproducible from a clean clone with a documented
command sequence — which is what §26's "reproducibility instructions work"
requires.

---

## 4. Streamlit deployment

### 4.1 Caching — the mechanism that implements §21

Streamlit documents `st.cache_data` for serializable return values (a fresh copy
is returned per call, preventing cross-session mutation) and `st.cache_resource`
for unserializable global resources such as ML models and database connections
(the same instance is shared) [R37].

| Object | Decorator | Why |
| --- | --- | --- |
| Fitted estimators (scaler, encoder, clusterer) | `st.cache_resource` | The documented case for ML models; loaded once per process [R37] |
| DataFrames (profiles, courses, popularity) | `st.cache_data` | Serializable; the per-call copy prevents one session mutating another's view [R37] |
| Derived per-interaction results | `st.cache_data` with TTL or no cache | Cheap to recompute; not worth cache-invalidation complexity |

> **[INFERENCE]** `cache_resource` shares one instance across all sessions, so the
> cached objects **must be treated as immutable**. A `.fit()` call on a cached
> estimator would corrupt every concurrent user's session. Since §21 already
> forbids retraining in the app, this is consistent — but it is worth an explicit
> test that the app never calls a `fit` method.

### 4.2 Platform constraints

The Community Cloud documentation states that it supports all released Python
versions still receiving security updates, and **defaults to 3.12** [R37b].

> **[INFERENCE]** Two consequences:
> 1. The support set is a **moving target** — a version that falls out of security
>    support may cause a forced upgrade. Targeting 3.13 (one above the platform
>    default) rather than the newest interpreter minimises this exposure. This is
>    the corrected rationale in ADR-0002, replacing an unverified Phase 0 claim.
> 2. `requirements.txt` must resolve on the platform. Direct dependencies are
>    pinned exactly; the full 130-package freeze is kept separately in
>    `requirements.lock.txt` so it can be consulted without over-constraining the
>    transitive tree at deploy time (decision-log D-003).

### 4.3 Application design constraints

| Constraint | Source | Implementation |
| --- | --- | --- |
| Never retrain on startup | §21 | Load artifacts via `cache_resource`; test that no `fit` is called |
| Anonymised learner identifiers | §17 | PII dropped at ingestion (ADR-0006), so it is never present to display |
| Informative empty states | §21 | Explicit UI for zero-history learners and empty filter results |
| Artifacts committed to the repo | Deployment | Community Cloud deploys from the repository; artifacts must be tracked, not generated at runtime |

> **[INFERENCE] A conflict between ADR-0003 and deployment that must be resolved
> in Phase 5.** `.gitignore` currently ignores `models/*` as regenerable output.
> But Community Cloud deploys the repository and cannot run the training
> pipeline — so if artifacts are not committed, the deployed app has nothing to
> load. **The `.gitignore` rule for `models/` will need to be relaxed for the
> final artifact set.** Flagged now so it is a deliberate decision in Phase 5
> rather than a deployment-day surprise. The artifacts are small (a 60×60
> similarity matrix and a few thousand-row tables), so committing them is
> unproblematic.

---

## 5. Testing strategy

CLAUDE.md §23 enumerates required surfaces. [R34] provides a rubric organised by
category, from which the applicable subset is selected.

| [R34] category | Applicable here | Planned tests |
| --- | --- | --- |
| **Data** | Yes | Schema validation; raw-data immutability (checksums, already implemented); referential integrity; no PII in processed outputs; no nulls introduced by transformations |
| **Model** | Yes | Clustering inference determinism under the seed; recommendation inference shape and ordering; already-enrolled exclusion; tier routing; explanation-scoring consistency |
| **Infrastructure** | Yes | Artifact round-trip (save→load→identical predictions); manifest version verification; matched-set verification; app startup; full pipeline reproducibility |
| **Monitoring** | **Mostly not applicable** | No live serving, no production traffic, no label pipeline. Recorded as a deliberate scope exclusion, not an oversight. |

### 5.1 Tests that matter most here

> **[INFERENCE]** Three tests carry disproportionate value, because each guards a
> failure that is silent rather than loud:
>
> 1. **Explanation–score consistency (§16).** Assert that every component named in
>    an explanation had a **non-zero contribution** to that item's score, and that
>    no component with a material contribution is omitted. This is the only
>    mechanical guard against the §16 violation of generating an explanation that
>    contradicts the scoring logic — and it is only possible because G1 requires
>    the scorer to return components.
> 2. **Leakage controls L1–L6** (`recommendation_evaluation_plan.md` §2.5) as
>    executable tests, not review checklist items. Leakage produces
>    plausible-looking numbers, so it cannot be caught by inspection.
> 3. **Artifact round-trip identity.** Save, reload in a fresh process, and assert
>    predictions are *identical* — not merely close. This catches version drift
>    and serialisation loss, which otherwise surface as small unexplained
>    differences between the paper and the app.

### 5.2 Edge cases (§23 requires failure-case tests)

Learner with zero interactions · learner with exactly one · learner who has
enrolled in every course in a category · filter combination yielding no
candidates · unknown `UserID` · missing artifact file · **version-mismatched
artifact** · corrupt manifest · empty recommendation list.

> **[INFERENCE]** "Learner who has enrolled in many courses" deserves specific
> attention at this catalogue size: with only 60 courses, a high-activity learner
> could have a candidate pool smaller than K, so top-10 cannot be filled. The
> system must degrade gracefully and say so, rather than padding with arbitrary
> items — which would be both a bug and a small dishonesty in the UI.

---

## 6. Reproducibility

| Mechanism | Status |
| --- | --- |
| Single seed (`RANDOM_SEED = 42`) | Implemented, asserted by test |
| Pinned direct dependencies + full lockfile | Implemented (D-003) |
| Immutable raw data verified by checksum | Implemented (ADR-0003) |
| Scripted pipeline, no manual notebook steps | Planned, Phase 5 |
| Split artifacts persisted and shared across experiments | Planned, Phase 3 |
| Experiment provenance (method, params, seed, script) recorded per result | Planned, Phase 3 |
| Documented clean-clone reproduction sequence | Planned, Phase 6 |

> **[INFERENCE]** The single highest-value addition is **persisting the
> train/validation/test split as an artifact** rather than re-deriving it in each
> experiment. If each experiment recomputes the split, a subtle difference in
> sorting or tie-breaking silently makes results non-comparable — and the
> comparison across methods is the entire basis for the model-selection decision.
> One split, computed once, loaded by all.

---

## 7. What this phase does not settle

| # | Question | Decided in |
| --- | --- | --- |
| P-1 | Exact artifact schema and manifest fields | Phase 4 (architecture freeze) |
| P-2 | Whether `models/` must be committed for deployment | Phase 5 — see §4.3; expected **yes** |
| P-3 | Streamlit page structure and navigation | Phase 5 |
| P-4 | Whether artifact size warrants Git LFS | Phase 5 — expected **no**, artifacts are small |
| P-5 | Final test count and coverage targets | Phase 5/6 |
