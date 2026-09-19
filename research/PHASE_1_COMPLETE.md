# Phase 1 — Dense Research — COMPLETE

**Phase:** 1 of 6 — dense research and methodology investigation
**Date:** 19 September 2026
**Decision:** ✅ **PASS**
**Next phase:** Phase 2 — dataset audit and EDA (**not started; awaiting go-ahead**)

---

## 1. Research completed

All eight required areas were researched against the actual constraints of the
EduPro dataset, and six documents were produced.

| Document | Lines | Contents |
| --- | --- | --- |
| `research/literature_review.md` | 831 | All eight areas; 40 verified references; evidence separated from inference |
| `research/methodology_comparison.md` | 740 | 40 methods compared on the 11 required fields |
| `research/recommendation_evaluation_plan.md` | 354 | Pre-registered evaluation protocol, metrics, selection rules |
| `research/segmentation_research.md` | 391 | Feature design, encoding, k-selection, stability, interpretability |
| `research/production_research.md` | 258 | Artifacts, CACE, Streamlit, testing, reproducibility |
| `research/experiment_plan.md` | 482 | 8 research questions, 28 experiments, acceptance criteria |

**Area coverage:**

| # | Required area | Where |
| --- | --- | --- |
| 1 | Learner segmentation | `literature_review.md` §1; `segmentation_research.md` (whole) |
| 2 | Recommender systems | `literature_review.md` §2; `methodology_comparison.md` §E |
| 3 | Course recommendation evaluation | `literature_review.md` §3; `recommendation_evaluation_plan.md` |
| 4 | Explainability | `literature_review.md` §4; `methodology_comparison.md` §G |
| 5 | Demographic features | `literature_review.md` §5; `segmentation_research.md` §7 |
| 6 | Sparse interaction data | `literature_review.md` §6; evaluation plan §4 |
| 7 | Production ML | `literature_review.md` §7; `production_research.md` |
| 8 | Teacher-sheet experiment | `literature_review.md` §8; experiment plan EXP-005/EXP-014 |

**Supporting artifact produced:** `scripts/analytical_baselines.py` →
`artifacts/phase1_analytical_baselines.json`. Closed-form reference values derived
from the catalogue size alone — no data content inspected, so Phase 2's audit is
not pre-empted.

---

## 2. Major findings

### 2.1 A random recommender scores HR@10 ≈ 0.175 on this catalogue

With 60 courses and one held-out item, a uniformly random top-10 has a hit rate of
roughly 0.175, and **Precision@10 is mathematically capped at 0.10**
(`scripts/analytical_baselines.py`).

This changes how every accuracy number in this project must be reported. A
headline "Hit Rate@10 = 0.22" would imply a useful system when the improvement
over guessing is marginal; a headline "Precision@10 = 0.08" would imply failure
when it is 80% of the achievable ceiling. **Every accuracy figure is therefore
reported against the random baseline and, where relevant, its analytical
ceiling**, and NDCG@10 becomes the primary accuracy metric because it is
rank-sensitive and not ceiling-limited in the same way [R23]. (D-012)

Most published recommender work never needs to state this — on a 10,000-item
catalogue random HR@10 is ~0.001. Here it is not, and omitting it would be
misleading.

### 2.2 The standard evaluation protocol leaks, and the leak can reorder methods

Per-user leave-one-out gives every learner a *different calendar split date*, so
training legitimately contains interactions occurring after some learners' test
points. Ji et al. studied exactly this and found relative method orderings become
unpredictable with differing amounts of leaked future data [R25]; Meng et al.
independently showed the splitting strategy alone can markedly alter system
rankings [R24].

This matters beyond metric inflation: **a leaky protocol could cause this project
to select the wrong production recommender.** Resolution: a dual protocol with a
pre-registered primary (global temporal split), the leave-one-out result reported
as explicitly leakage-bearing, and a pre-registered fallback threshold so the
choice cannot be made by looking at which gives nicer numbers. (D-011)

A subtler leak was also identified and is guarded separately: **tier assignment
must use training-window history only**. A learner with 1 training and 1 test
interaction has 2 in total; routing on total history lets the test item's
existence inform the routing decision. This hides in the routing logic, not the
feature matrix, so a global-timeline audit of features would not catch it.

### 2.3 One-hot encoding would let a single variable dominate the segmentation

Encoding `PreferredCategory` as 12 indicator columns against roughly 8 behavioural
columns spends **more than half the Euclidean distance budget on one conceptual
variable**. K-Means would then substantially be clustering learners by modal
category — reproducing the course taxonomy EduPro already has, presented as a
discovered segmentation.

This is the obvious implementation and it is a trap. Four encodings will be
compared (EXP-011a), with a category-proportion vector as the expected
front-runner, and a **feature-dominance diagnostic** (η² per feature block)
measuring the effect rather than assuming it. That diagnostic also operationalises
CLAUDE.md §10's requirement that demographics not dominate — the same measurement
serves both. (`segmentation_research.md` §3–4)

### 2.4 Item-based CF is better-conditioned here than the mandated user-similarity method

Each course has ~167 interactions; each learner has ~3.3. User-user similarity is
therefore estimated from roughly **50× less evidence per entity** than item-item
similarity, and the item-item matrix is 60×60 — trivially computable and fully
cacheable.

The brief mandates "similar learner profiles", so that is implemented. But item-
based CF [R15][R16] is added as a candidate, and the user-similarity method is
split into two variants — over raw interaction history (EXP-022a) and over the
engineered profile features (EXP-022b) — because the profile aggregation is what
makes sparse history usable. [R26] found tuned item-kNN beating most reproducible
neural methods, which is direct evidence that this addition is worth its cost.

### 2.5 Implicit-feedback matrix factorisation does not apply, for a specific reason

Hu, Koren and Volinsky's method derives confidence from *repeated* observations
[R13]. EduPro has **zero repeat `(user, course)` pairs** (Phase 0, verified), so
every observation has identical multiplicity, the confidence function is constant,
and the method degenerates to weighted binary matrix factorisation. Implementing
it and describing it as [R13] would misrepresent what the model does.

Together with BPR's sample-size problem and the §16 interpretability requirement,
this produced a documented rejection of the latent-factor family **with reversal
conditions**, rather than a silent omission. (D-010)

### 2.6 Explainability is an architecture decision, not a UI decision

§16 requires explanations to correspond to signals the recommender actually used.
[R31]'s distinction between model-intrinsic and post-hoc explanation makes the
failure mode precise: a post-hoc explainer can generate a fluent sentence
unrelated to why an item ranked where it did.

Since the planned hybrid is a weighted combination of named components, the
explanation can be generated from the **score decomposition itself** — true by
construction. This imposes a concrete interface requirement decided now rather
than in Phase 5: **the scorer must return per-component contributions, not just a
scalar.** Retrofitting that later would be expensive, and it is also the reason
the uninterpretable methods were rejected rather than merely deprioritised.
(D-015)

### 2.7 The teacher experiment may be vacuous, and that is checkable first

With exactly 60 teachers and 60 courses, `TeacherID` may be a deterministic
function of `CourseID`. If so, every teacher-derived feature is an alias for a
course-derived feature — adding no information while appearing to.

**EXP-005 therefore runs before EXP-014 as a go/no-go gate.** If the mapping is a
bijection, the teacher experiment is cancelled and the reason recorded: a clean
negative result and a direct answer to §11, obtained at a fraction of the cost.
Separately, teacher `Age` and `Gender` are **excluded before experimentation** —
third-party demographics with no legitimate role in allocating recommendations
[R38]. (D-016)

### 2.8 The dataset may be synthetic — flagged as a first-class threat

Phase 0's cardinalities are suggestive: zero missing values across 4 sheets and 27
columns; 21 distinct ages in *both* Users and Teachers; 23 distinct values in
*both* Amount and CoursePrice.

If the data is generated, learned cluster structure may be a generator artefact
rather than real learner behaviour. This is registered as threat **V8** in the
evaluation plan and as open question **Q-8**, and it is a principal reason the
**gap statistic** [R02] was added — elbow, silhouette, CH and DB all *assume*
structure exists and merely locate the best k. **None can return "there is no
cluster structure."** A project unable to detect that outcome would be
structurally incapable of reporting it, which §6 would not permit. (D-017)

### 2.9 Diversity may be a proxy for activity, not for breadth

At a mean of 3.333 courses per learner, the diversity score is **bounded by**
total courses: a learner with 2 enrollments can explore at most 2 of 12
categories. So measured "diversity" of low-activity learners largely measures
their activity. Without care, the dominant axis of the segmentation will be
history length, and the segments will restate the activity distribution.

Three mitigations will be tested (EXP-011f), and the third is deliberately
"accept and report it" — if activity level genuinely is the dominant structure,
saying so plainly is a legitimate finding, and including that option keeps the
experiment from being rigged toward richer structure than exists.

### 2.10 A Phase 0 claim was found to be unverified, and was corrected

Phase 0 asserted in six places that Streamlit Community Cloud "supports Python
3.9–3.13". Attempting to cite it revealed the documentation says something
different: it supports all Python versions still receiving security updates and
**defaults to 3.12** [R37b] — so 3.14 would in fact have been permitted.

The claim was withdrawn everywhere and ADR-0002 rewritten. **The decision (target
3.13) stands on corrected reasoning**, but the original ADR reached a sound
conclusion through a false premise, and it survived Phase 0 precisely because the
conclusion looked right. It was caught only because Phase 1 required a citation
for every claim. (D-009)

---

## 3. References

**40 references, every one verified by retrieval during Phase 1.** Verification
means title, authors, venue, year and DOI/URL were confirmed against a publisher
page, DBLP, PMLR, or the canonical proceedings listing — not written from memory.
Full list with identifiers in `literature_review.md` §10.

| Area | Keys | Count |
| --- | --- | --- |
| Clustering and segmentation | R01–R12 | 12 |
| Recommender systems | R13–R19 | 7 |
| Evaluation | R20–R30 | 11 |
| Explainability and fairness | R31, R32, R38 | 3 |
| Production ML and engineering docs | R33–R37b | 6 |
| Education-specific | R39 | 1 |

**Load-bearing sources** — those whose removal would change a project decision:
[R01] silhouette · [R02] gap statistic · [R03] per-cluster stability · [R13]
implicit feedback · [R15][R16] item-based CF · [R17] hybrid taxonomy · [R23] NDCG
· [R24] splitting strategy · [R25] leakage · [R26] baseline rigour · [R27][R29]
coverage and popularity bias · [R30] demographic evaluation · [R31] explainable
recommendation · [R33][R34][R36][R37] production engineering · [R38] fairness.

**Fabrication controls applied:**
- No citation written from memory; every one retrieved and checked.
- Published evidence carries a citation key; my own reasoning is confined to
  marked `[INFERENCE]` blocks — 45 of them across the corpus.
- §11 of `literature_review.md` records that a search for a peer-reviewed *course*
  recommender survey returned candidates whose venue or peer-review status could
  not be established; **they are not cited**, and no claim rests on them.
- [R12]'s MOOC learner labels ("auditing", "completing", "sampling") are
  explicitly barred from reuse as EduPro segment names — EduPro has no completion
  or engagement-trace data, so applying them would assert behaviour the data
  cannot evidence. Recorded as the most tempting available fabrication in the
  project (`segmentation_research.md` §8).

---

## 4. Proposed experiment matrix

**28 experiments across Phases 2–3**, each with a pre-recorded hypothesis, method,
metrics and acceptance criterion. Full specifications in `experiment_plan.md`.

### Phase 2 — dataset audit (6)

| ID | Title | Gates |
| --- | --- | --- |
| EXP-001 | Referential integrity and key uniqueness | everything |
| EXP-002 | Is `Amount` identical to `CoursePrice`? | feature B9 (Q-1) |
| EXP-003 | Per-learner interaction distribution | tier candidates (Q-4) |
| EXP-004 | Temporal coverage and split viability | **the split protocol; the persisted split** |
| EXP-005 | Is `TeacherID` an alias for `CourseID`? | **go/no-go on EXP-014** (Q-9) |
| EXP-006 | Feature distributions; synthetic-data assessment | scaler choice; Q-8 |

### Phase 3 — segmentation (14)

EXP-010 (k sweep: elbow, silhouette, CH, DB) · **EXP-010b (gap statistic — can
falsify structure)** · EXP-010c (GMM/BIC) · **EXP-011 (Variant A vs B)** ·
EXP-011a (encoding) · EXP-011b (block weighting) · EXP-011c (feature dominance) ·
EXP-011d (PCA) · EXP-011e (correlated features) · EXP-011f (history-length
dominance) · EXP-012/012b (hierarchical validation: Ward, then average linkage) ·
EXP-013/013b (per-cluster stability) · EXP-014 (teacher signals, gated on EXP-005)

### Phase 3 — recommendation (8)

EXP-019 (random floor) · EXP-020 (global popularity) · EXP-021 (content-based) ·
EXP-022a/b/c (user-user over history; user-user over profiles; item-based CF) ·
**EXP-023 (cluster popularity — does segmentation help?)** · EXP-024 (hybrid +
ablation, determines weights) · EXP-025 (tier boundary) · EXP-026 (leakage
quantification) · EXP-027 (demographic-stratified audit)

**Critical path:** EXP-001 → EXP-004 (split) → EXP-006 → EXP-010/010b → EXP-011 →
EXP-023 → EXP-024 → EXP-025 → selection → **one** test evaluation.

**A circularity was identified and resolved in the design:** EXP-011 (Variant
choice) uses downstream NDCG@10, which requires EXP-023, which requires a
segmentation. Resolution: EXP-023 runs first against a provisional segmentation,
and the recommender is **not** re-tuned per variant — otherwise the comparison
would confound segmentation quality with recommender tuning.

---

## 5. Unresolved methodological questions

**Deliberately unresolved.** CLAUDE.md §4 forbids deciding the architecture from
literature; these are what the experiments are for.

### 5.1 Open project questions (`decision_log.md`)

Q-1 `Amount` vs `CoursePrice` · Q-2 duplicate course names · Q-3 use of
`CoursePrice`/`CourseDuration` · Q-4 tier boundaries · Q-5 Variant A vs B · Q-6
temporal hold-out viability · **Q-8 is the data synthetic** · **Q-9 is `TeacherID`
an alias** · **Q-10 does segmentation improve recommendation at all**

*(Q-7, the Engagement Lift definition, was resolved by D-014; its magnitude is a
Phase 3 result.)*

### 5.2 Segmentation questions (S-1…S-10)

Encoding · block weighting · Variant · k · **whether structure exists at all** ·
history-length dominance · diversity separability · teacher signal validity ·
scaler · **whether segmentation improves recommendation**.

### 5.3 Production questions (P-1…P-5)

Artifact schema · **whether `models/` must be committed for deployment** (a
conflict between ADR-0003's gitignore rules and Community Cloud's
deploy-from-repo model, flagged now rather than on deployment day) · Streamlit
page structure · Git LFS · coverage targets.

### 5.4 Methodological questions the literature does not settle

`literature_review.md` §9 records seven, including: which encoding produces the
better segmentation; the right k (competing criteria frequently disagree [R06]);
whether demographics help or harm on *this* data; and **whether cluster-aware
recommendation beats item-based CF on a 60-item catalogue** — for which no cited
source provides an answer.

---

## 6. PASS / FAIL decision

### ✅ **PASS**

| Pass criterion | Evidence | Verdict |
| --- | --- | --- |
| **Research documents exist** | All six created: 3,056 lines total. All eight required areas covered; mapping in §1. | ✅ |
| **References are traceable** | 40 references, each with a DOI or canonical URL, **each verified by retrieval** during Phase 1. Sources that could not be verified are named as excluded (`literature_review.md` §11). | ✅ |
| **Experiments are clearly specified** | 28 experiments, each with hypothesis, method, metrics, output, acceptance criterion and dependencies. Matrix, critical path and a resolved circularity in `experiment_plan.md` §5. | ✅ |
| **No fabricated evidence** | No citation from memory. Published evidence carries a citation key; 45 marked `[INFERENCE]` blocks carry my own reasoning. A Phase 0 claim found to be unverified was **withdrawn and corrected in six files** (D-009). [R12]'s labels explicitly barred from reuse. | ✅ |
| **Final algorithm NOT prematurely locked** | **Every recommendation method that could win is CANDIDATE.** No k, no encoding, no Variant, no recommender selected. The five rejections are argued from this dataset's structure or a direct CLAUDE.md conflict, each with a stated reversal condition. | ✅ |

### The "not prematurely locked" criterion, in detail

This is the criterion most at risk from a dense research phase, so it is
evidenced rather than asserted:

| | Count | Note |
| --- | --- | --- |
| **CANDIDATE** (undecided, experiment named) | 16 | Includes all 5 brief-mandated recommendation baselines + the hybrid |
| **ADOPT** (mandated or uncontroversial engineering default) | 17 | Adopting K-Means as *primary* is a brief requirement, **not** a result — its configuration, k, encoding and feature set are all open |
| **REJECT** (with reason + reversal condition) | 5 | DBSCAN, iALS, BPR, neural, random split (+ post-hoc explanation) |
| **DEFER** (blocked on a named Phase 2 fact) | 2 | Scaler choice; Protocol A viability |

**Seven pre-registered expectations are recorded in `experiment_log.md`** —
including the prediction that the hybrid may lose the parsimony tiebreak and that
cluster structure may be weak enough for the gap statistic to indicate k=1. These
are logged as predictions so that hindsight cannot later be presented as
foresight, and so that being wrong is visible and costless.

### CLAUDE.md compliance

| § | Rule | How Phase 1 complied |
| --- | --- | --- |
| 4 | Research-first; do not build | No model, recommender or app built. No data content analysed beyond the one structural fact needed for a claim already made in Phase 0. |
| 6 | Scientific integrity | Every citation verified. An unverified Phase 0 claim was found, corrected in six files, and the correction recorded rather than silently applied. Negative outcomes pre-registered as legitimate. |
| 7 | No novel algorithms | None proposed; neural/latent methods rejected partly on this ground. |
| 9 | Leakage | The leakage mechanism is analysed precisely, a dual protocol is pre-registered, and six controls (L1–L6) are specified as executable tests. |
| 10 | Demographics | Variant A/B comparison specified with a measurable dominance diagnostic (η²) and a **pre-registered decision rule**. |
| 11 | Teachers sheet | Treated as an explicit experiment, **gated on a cheap prerequisite check** that may cancel it. Third-party demographics excluded before testing. |
| 12 | Sparse users | Tiered evaluation; low-history learners never scored as personalised. |
| 13 | Baselines | All five mandated baselines are CANDIDATE with equal tuning budget [R26]; three more added with justification. |
| 14 | Hybrid weights | Determined by validation search + ablation. Hand-chosen weights are named as a Phase 3 failure condition. |
| 15 | Sparse tiers | Four tiers specified; boundary set by a pre-registered rule, not invented. |
| 16 | Explainability | Model-intrinsic explanation required; the scorer-interface consequence decided now (D-015); post-hoc explanation rejected. |
| 17 | Privacy | PII exclusion reaffirmed; demographics retained for **evaluation stratification** only [R30]. |
| 25 | Documentation | Six research documents; 10 new decision-log entries; ADR-0002 corrected. |
| 27 | Phase report with evidence | This document; every claim traced to a file, a reference, or a script output. |
| 28 | Stop condition | Phase 1 evaluated; PASS; **stopping here.** |

---

## 7. Artifacts created

| Artifact | Purpose |
| --- | --- |
| `research/literature_review.md` | Eight areas; 40 verified references; evidence/inference separated |
| `research/methodology_comparison.md` | 40 methods on the 11 required comparison fields |
| `research/recommendation_evaluation_plan.md` | Pre-registered protocol, metrics, selection rules, threats |
| `research/segmentation_research.md` | Feature design, encoding, k, stability, interpretability, naming rules |
| `research/production_research.md` | Artifacts, CACE, Streamlit, testing, reproducibility |
| `research/experiment_plan.md` | 8 RQs, 28 experiments, acceptance criteria |
| `research/PHASE_1_COMPLETE.md` | This report |
| `scripts/analytical_baselines.py` | Closed-form random-baseline and ceiling reference values |
| `artifacts/phase1_analytical_baselines.json` | Its output |
| `research/decision_log.md` | +10 entries (D-009…D-018), +3 open questions |
| `research/experiment_log.md` | Experiment programme index + 7 pre-registered expectations |
| `research/architecture_decision_record.md` | ADR-0002 corrected |

**Corrected in six files** following D-009: `architecture_decision_record.md`,
`decision_log.md`, `PROJECT_MANIFEST.md`, `README.md`, `requirements.txt`,
`tests/test_phase0_environment.py`, `PHASE_0_COMPLETE.md`.

---

## 8. Unresolved issues

None blocking. Two carried forward:

1. **`models/` gitignore vs deployment** (P-2). ADR-0003's `.gitignore` treats
   `models/` as regenerable output, but Streamlit Community Cloud deploys from the
   repository and cannot run the training pipeline. The rule will need relaxing
   for the final artifact set. Flagged now so it is a deliberate Phase 5 decision
   rather than a deployment-day surprise. Artifacts are small; committing them is
   unproblematic.
2. **Phase 0's two open items remain open**: the empty `claude.md.txt` in the
   project root, and the git-identity/authorship question
   (`Kartik <kartikshreekumar2006@gmail.com>` in the global git config vs the
   session account `menonanushree897@gmail.com`; `pyproject.toml` records
   *Anushree Menon*, inferred). Both still need the user's confirmation before the
   repository is published.

---

## 9. Stop

Per CLAUDE.md §28 and the Phase 1 brief, work **stops here**. Phase 2 will not
begin automatically.

**Phase 2 will, on instruction, run EXP-001 through EXP-006:** referential
integrity; the `Amount`/`CoursePrice` question; the per-learner interaction
distribution; temporal coverage and the split-protocol decision; the
`TeacherID`/`CourseID` alias check that gates the teacher experiment; and the
feature distributions — including an honest assessment of whether this dataset is
synthetic.
