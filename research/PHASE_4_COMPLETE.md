# Phase 4 — Model Selection and Architecture Freeze — COMPLETE

**Phase:** 4 — model selection and architecture freeze
**Date:** 19 September 2026
**Decision:** ✅ **PASS**
**Model version:** 🔒 `edupro-1.0.0` — **FROZEN**
**Next phase:** Phase 5 — production implementation (**not started; awaiting go-ahead**)

---

## 1. Objectives

Per the Phase 4 brief:

1. Review every artifact produced by Phases 0–3B as lead ML architect and reviewer.
2. Produce **formal decision matrices** for segmentation and recommendation from
   **actual experimental metrics**.
3. Settle twelve named decisions.
4. Confirm every official requirement remains satisfied — and where one was
   evaluated but not retained, document the investigation, the reason, and where the
   requirement is still addressed.
5. Produce `ARCHITECTURE_FREEZE.md`, `technical_architecture.md`,
   `architecture_diagram.md` and this report.
6. Freeze the methodology.

Explicitly **out of scope**: production UI code.

---

## 2. Headline

> **Architecture C is frozen: a four-segment K-Means segmentation feeding a
> four-tier switching recommender.**
>
> It was selected on **coverage, robustness, interpretability and honest
> degradation** — not accuracy, because no method demonstrated any. Zero of eleven
> methods beat random ranking on the leakage-free temporal split.

Phase 4's substantive contribution is that it **did not simply ratify Phase 3B**.
Phase 3B left a real tension — the pre-registered rule selected `cluster_popularity`
as the best *method* (D-034), while the coverage evidence recommended the *tiered*
recommender for deployment (D-035) — and **no Phase 3B row measured the assembly
that would actually ship**. Freezing an unmeasured configuration would have been a
gap, so it was measured.

---

## 3. Review of prior artifacts

All ten areas reviewed. The review was not a formality: it produced four corrections.

| Area | Reviewed | Outcome |
| --- | --- | --- |
| Official requirements transcript | ✅ | All A–F requirements traced to implementation + evidence |
| `dataset_audit.md` + `phase2_audit.json` | ✅ | Four data properties confirmed as architecture drivers |
| `segmentation_results.md` + artifacts | ✅ | Decision matrix rebuilt from the JSON, not the prose |
| `segmentation_feature_decision.md` | ✅ | Variant B confirmed; ARI 1.000 re-checked |
| `cluster_profiles.md` | ✅ | Segment names confirmed derivable from model features only |
| `recommendation_results.md` + artifacts | ✅ | Decision matrix rebuilt from the JSON |
| `recommendation_error_analysis.md` | ✅ | Popularity-bias and tier findings carried into §Known Limitations |
| `decision_log.md` (D-001…D-039) | ✅ | Q-7 found stale — it had been settled by D-038 but never marked |
| `experiment_log.md` (EXP-001…027) | ✅ | P-3 and P-7 found stale — settled by EXP-024 but still "awaiting" |
| `architecture_decision_record.md` | ✅ | ADR-0001…0006 all still hold under the freeze |
| `REQUIREMENTS_TRACEABILITY.md` | ✅ | Test count stale (160 → 163); I5, C3, E4, E6 advanced |

**Corrections made:** Q-7, P-3, P-7 marked settled with their evidence; the
traceability matrix updated. None changes a conclusion; all four were records
lagging behind the work.

---

## 4. Decision matrices

Both matrices are in `research/ARCHITECTURE_FREEZE.md`, built from
`artifacts/segmentation/segmentation_results.json` and
`artifacts/recommendation/recommendation_results.json` — not from prose summaries.

**Segmentation:** 10 representations × 9 values of k, scored on silhouette,
intra-cluster similarity, minimum cluster share, stability, interpretability and
complexity. **`B_proportion` at k=4 selected.**

**Recommendation:** 11 methods + random, scored on NDCG@10, significance vs random,
coverage, Gini and complexity. **`cluster_popularity` core, tiered routing.**

Two entries in those matrices are worth naming because they are where a decision
matrix earns its keep:

- The **highest silhouette lost.** `B_robust_scaled` scores 0.716 — three times
  any other arm — and was rejected as a scaling pathology: two brief-mandated
  features have an interquartile range of exactly zero, so RobustScaler manufactures
  a separable axis out of a degeneracy.
- The **best-scoring recommender lost.** The hybrid leads at 0.1206 and was
  rejected by the pre-registered parsimony margin it failed to clear.

---

## 5. The twelve decisions

| # | Decision | Answer |
| --- | --- | --- |
| 1 | Final learner feature schema | 25 features in 4 blocks; all 11 mandated features present |
| 2 | Final segmentation representation | `B_proportion` — behaviour only, 12-dim category shares, StandardScaler |
| 3 | Final K | **k = 4** |
| 4 | Final clustering pipeline | StandardScaler → KMeans(k-means++, n_init=10, seed 42) |
| 5 | Final segment naming methodology | Deviation-ranked, controlled vocabulary, model features only, level-purity prefix |
| 6 | Final recommendation architecture | Tiered switching recommender, routed on training-window history |
| 7 | Final ranking logic | Exclude training enrollments → within-segment count → deterministic tie-break |
| 8 | Final sparse-user fallback | `DiversifiedFallback` — popularity + rating, re-ranked round-robin by category |
| 9 | Final explanation logic | Model-intrinsic score decomposition; tier-honest; zero-weight components cannot appear |
| 10 | Teacher signals | **Not in the production model** — rejected in three separate experiments |
| 11 | Artifact persistence | joblib + parquet + json; manifest verifies library versions **and** matched artifact set |
| 12 | Evaluation methodology | Protocol A primary, test opened once, random baseline and Precision ceiling always shown |

Each is stated with its evidence in `ARCHITECTURE_FREEZE.md`.

---

## 6. New evidence produced in this phase

Two experiments, **validation window only** — the test budget was spent once in
Phase 3B and re-opening it to compare architectures would convert a held-out
estimate into a selection surface (D-043).

### EXP-028 — the assembly Phase 3B never measured

511 evaluable learners (rich 231, moderate 178, minimal 102).

| Architecture | NDCG@10 | HR@10 | Coverage | Gini | Δ random |
| --- | --- | --- | --- | --- | --- |
| A — flat `cluster_popularity` | 0.1098 | 0.3033 | 0.78 | 0.606 | +0.0125 n.s. |
| B — tiered, hybrid core | 0.1135 | 0.3327 | 1.00 | 0.608 | +0.0162 n.s. |
| **C — tiered, selected core** ✅ | 0.1104 | 0.3053 | **1.00** | **0.581** | +0.0131 n.s. |

**C dominates A**: +0.0006 NDCG (noise), **+0.22 coverage**, lower concentration, and
an explicitly labelled cold-start route. The gain is located in the minimal tier —
half the learner base — where content-based routing reaches the whole catalogue
(coverage 1.00) and a cluster-popularity scorer does not. B is +0.0031 over C but
re-introduces the hybrid the parsimony rule rejected at a *larger* margin.

### EXP-029 — the cold-start fallback, and a discarded metric

`DiversifiedFallback` reaches **10 of 12 categories** with a 0.10 top-category
share, against 7–8 categories and 0.20–0.30 for the alternatives. The naive
popularity + rating blend — the obvious reading of §15 — is **worse than plain
popularity** on breadth, because the two signals concentrate on the same courses.

**A measurement was discarded for being meaningless.** The first attempt used
cross-user catalogue coverage and returned 0.17 for every candidate. That is not a
tie: zero-history learners are indistinguishable, so every deterministic ranker
gives all of them the same list, pinning coverage at K/60 by construction. The
instrument could not vary. It was replaced with within-list category spread, and
the replacement is recorded (D-042) rather than quietly substituted.

---

## 7. Official requirements — including those not retained

Every official requirement remains satisfied. Nine were **investigated and not
promoted to the primary mechanism**; each is accounted for in
`ARCHITECTURE_FREEZE.md` §"Official requirements evaluated but not retained" with
how it was investigated, why it was not retained, and **how it is still addressed**.

| Requirement | Not retained as | Still addressed by |
| --- | --- | --- |
| Age, Gender (B1–B2) | clustering features | implemented in the feature builder; **evaluation strata**; shown in the learner profile |
| Average spending (B9) | independent behaviour signal | **retained** in the schema and profiles, with the `Amount ≡ CoursePrice` redundancy documented |
| Similar learner profiles (E2) | production scorer | both arms implemented, evaluated and reported; a hybrid component |
| Rating-weighted relevance (E4) | standalone scorer | largest hybrid weight after cluster popularity; drives `DiversifiedFallback` |
| Content-based (E1) | flat production scorer | **the minimal-tier route** — half the learner base |
| Hybrid / personalised ranking (E5) | production scorer | fully searched, ablated and reported; its decomposition is what makes explanations faithful |
| Elbow method (D3) | decision rule | **produced and reported** as a mandated figure alongside five other diagnostics |
| Hierarchical clustering (D2) | production method | run as validation; **negative result reported in full** |
| Teachers sheet (§11) | any model | three experiments, all documented; joins-layer support retained behind a flag |

---

## 8. Artifacts created

| Artifact | Lines / contents |
| --- | --- |
| `research/ARCHITECTURE_FREEZE.md` | 18 required sections, 2 decision matrices, 12 decisions, freeze conditions |
| `docs/technical_architecture.md` | module map, data flow, interfaces, leakage controls, artifact versioning, extension points |
| `research/architecture_diagram.md` | 7 Mermaid diagrams |
| `research/PHASE_4_COMPLETE.md` | this report |
| `scripts/validate_final_architecture.py` | EXP-028 + EXP-029 |
| `artifacts/architecture/architecture_validation.json` | measured results + provenance |
| `src/edupro/recommendation/baselines.py` | `DiversifiedFallback` added |
| `tests/test_recommendation.py` | 3 fallback-diversity tests (56 → 59) |
| Updated | `decision_log.md` (+D-040…D-044), `experiment_log.md` (+EXP-028, EXP-029), `REQUIREMENTS_TRACEABILITY.md`, `README.md` |

---

## 9. Validation checks

| Check | Result |
| --- | --- |
| Full test suite | ✅ **163 passed**, 1 warning, 87.7s |
| Raw workbook SHA-256 | ✅ `ed555e46…8cc0` — unchanged, matches the Phase 0 constant |
| Raw data modified? | ✅ No — `git status` shows no change under `data/` |
| Docker artifacts | ✅ None (asserted by test) |
| PII in any frame | ✅ Absent (asserted by test) |
| Test budget | ✅ Not re-opened — Phase 4 ran on validation only |
| Every metric quoted traced to an artifact | ✅ All from the three experiment JSONs |
| Decision matrices built from JSON, not prose | ✅ |
| Official requirements traced | ✅ A–F complete; G–H correctly not started |
| Segment names use only model features | ✅ Asserted by test |
| Explanations cannot name unused signals | ✅ Asserted by test |
| Cold-start fallback diversity | ✅ Asserted by 3 tests |

---

## 10. Important findings

1. **The assembled architecture needed measuring, and the measurement changed the
   answer.** Ratifying Phase 3B's method selection alone would have frozen
   Architecture A at coverage 0.78. The tiered assembly reaches 1.00 at the same
   accuracy.
2. **The tiered design's value is concentrated in one tier.** The minimal tier —
   50.5% of learners, one interaction each — is where routing to content-based
   filtering buys full catalogue coverage. This is a direct consequence of the
   Phase 2 finding that 54% of learners have a single interaction.
3. **§15's fallback cannot be satisfied by blending its first two terms.**
   Popularity and rating concentrate on the same courses; diversity has to be
   engineered explicitly. This was found by measurement, not by reading.
4. **A metric that cannot vary reads exactly like a metric showing no difference.**
   The discarded cross-user coverage measurement returned an identical number for
   every candidate, which is a wrong instrument, not a null result.
5. **Nothing in this phase changes the headline.** All three architectures remain
   statistically indistinguishable from random.

---

## 11. PASS / FAIL

### ✅ **PASS**

| Acceptance criterion | Evidence |
| --- | --- |
| Every prior artifact reviewed | §3 — 11 areas, 4 corrections made |
| Formal decision matrices from actual metrics | `ARCHITECTURE_FREEZE.md`, built from the experiment JSONs |
| No method selected for looking sophisticated | The hybrid *led* and was rejected; the highest silhouette was rejected |
| Twelve decisions settled | §5, each with evidence |
| Official requirements all satisfied | §7 + `REQUIREMENTS_TRACEABILITY.md` |
| Not-retained requirements accounted for | §7 — nine, each with investigation, reason and where still addressed |
| All four documents produced | §8 |
| Mermaid diagrams | `architecture_diagram.md` — 7 |
| Tests pass | 163 passed |
| No production UI code written | ✅ `app/` untouched |
| Methodology frozen | D-044; four conditions to reopen |

### CLAUDE.md compliance

| § | Requirement | Status |
| --- | --- | --- |
| 6 | No fabricated metrics | ✅ Every number traced to a JSON artifact produced by an executed script |
| 6 | Failed experiments not hidden | ✅ The discarded coverage metric and the failed naive fallback are both reported |
| 7 | No novel algorithm | ✅ Established methods throughout |
| 8 | Raw data immutable | ✅ Checksum verified |
| 9 | Leakage addressed | ✅ L1–L6; test budget not re-opened |
| 10 | Variant A vs B decided on evidence | ✅ ARI 1.000 |
| 11 | Teachers sheet as explicit experiment | ✅ Three experiments, rejected |
| 14 | Hybrid weights not hardcoded arbitrarily | ✅ Searched, ablated — and the hybrid still rejected |
| 15 | Sparse-user tiers | ✅ Four tiers, boundaries from the data |
| 16 | Explanations match scoring logic | ✅ Model-intrinsic decomposition |
| 17 | Privacy | ✅ PII dropped at ingestion |
| 20 | No Docker | ✅ |
| 22 | Artifacts version-consistent | ✅ Manifest design specified |
| 25 | Decisions documented | ✅ D-040…D-044 |
| 27 | Phase report with evidence | ✅ This document |

---

## 12. Unresolved issues

1. **Nothing beats random.** Unchanged and unfixable on this data. The research
   paper and executive summary must lead with it (§6).
2. **The dashboard must show the random reference** wherever it reports
   recommendation quality. Carried to Phase 5 as a hard requirement.
3. **Gender gap requires monitoring** on real data — nominally significant,
   uncorrected for four strata tests, in a system using no demographic feature.
4. **P-2: `models/` is git-ignored.** Streamlit Community Cloud deploys from the
   repository and cannot run the training pipeline, so the final artifact set must
   be committed. The `.gitignore` rule is relaxed in Phase 5.
5. **Phase 0's two open items remain open**: the empty `claude.md.txt`, and the
   git-identity/authorship question (`Kartik <kartikshreekumar2006@gmail.com>` in the
   global git config vs the session account; `pyproject.toml` records *Anushree
   Menon*, inferred). Both need confirmation before publication.
6. **The segmentation is a course-level split** (D-031) and must be described as
   one in the paper and the dashboard, not as a psychological typology.

---

## 13. Stop

Per CLAUDE.md §28 and the Phase 4 brief, work **stops here**. Phase 5 will not begin
automatically.

🔒 **The methodology is frozen.** Phase 5 implements exactly what
`ARCHITECTURE_FREEZE.md` specifies — persisted artifacts, the production pipeline,
the Streamlit application — and does not revisit the ML design. Any change requires
the four conditions in D-044.
