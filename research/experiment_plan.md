# Experiment Plan

**Phase:** 1 — research and methodology investigation
**Date:** 19 September 2026
**Status:** Pre-registered. **No experiment has been run.**
**Reference keys `[Rxx]`** resolve in `literature_review.md` §10.

---

## 0. Purpose and standing rules

Phase 1 read the literature to **constrain the search space and design the
tests**. It did not select a model, and CLAUDE.md §4 forbids doing so from
literature. This document specifies the experiments that will.

**Standing rules for every experiment below:**

1. **Hypotheses are stated before the run.** A hypothesis written after seeing
   results is a description, not a test.
2. **A hypothesis being wrong is a result.** It is recorded in
   `experiment_log.md` with the same prominence as a confirmation (§6).
3. **Seed:** `edupro.config.RANDOM_SEED = 42` unless the experiment is explicitly
   about seed sensitivity.
4. **One split, shared.** Train/validation/test are computed once (EXP-004) and
   persisted; no experiment re-derives them.
5. **The test window is touched once**, at the end of Phase 3, for the selected
   method only.
6. **Provenance:** every result records method, parameters, split protocol, seed
   and the producing script.

---

## 1. Research questions

Eight questions, each traced to what makes it necessary.

| RQ | Question | Driver |
| --- | --- | --- |
| **RQ1** | Does the EduPro learner population contain **any** meaningful behavioural cluster structure, or is apparent structure an artefact of short histories? | §4, §6; [R02][R04] |
| **RQ2** | How should mixed-type learner features be encoded so that no single variable dominates the distance metric? | §10; [R10][R11] |
| **RQ3** | Do demographic features improve or degrade learner segmentation? | §10; [R30][R38] |
| **RQ4** | How many segments, and are they stable and interpretable? | Brief p.4; [R01][R02][R03] |
| **RQ5** | Which recommendation method performs best under leakage-free temporal evaluation? | §13; [R24][R25][R26] |
| **RQ6** | Does segmentation improve recommendation at all, relative to non-cluster baselines? | §10, ADR-0005 |
| **RQ7** | Where do sparse-history tier boundaries fall, and does personalisation pay off above them? | §12, §15; [R19] |
| **RQ8** | Do teacher-derived signals contribute defensible value, or are they redundant with course attributes? | §11 |

---

## 2. Phase 2 — dataset audit

Prerequisites. Several later experiments are blocked on these.

### EXP-001 — Referential integrity and key uniqueness
**Question:** Do the four sheets join cleanly?
**Hypothesis:** All `Transactions.UserID` ∈ `Users`, all `CourseID` ∈ `Courses`,
all `TeacherID` ∈ `Teachers`; all primary keys unique.
**Method:** Set membership and uniqueness checks across all four sheets.
**Metrics:** Orphan counts; duplicate key counts.
**Output:** `artifacts/phase2_integrity_report.json`; schema validation tests.
**Acceptance:** All checks run and are reported. **Orphans are a finding, not a
failure** — if present, the handling policy is documented before any row is
dropped, and no row is dropped silently.

### EXP-002 — Is `Amount` identical to `CoursePrice`? *(Q-1)*
**Question:** Is "average spending" a distinct feature from "average course
price"?
**Hypothesis:** `Amount` equals the joined `CoursePrice` for every transaction —
both have exactly 23 distinct values (Phase 0).
**Method:** Join transactions to courses; compare row-wise; report exact-match
rate and any discrepancy pattern (discounts? time-varying prices?).
**Metrics:** Exact-match proportion; distribution of any differences.
**Output:** Decision on feature B9.
**Acceptance:** If identical, **B9 (average spending) and average course price are
one feature**; only one enters the model and the redundancy is documented. If they
differ, the difference is characterised (a discount signal would be genuinely
interesting) before B9 is retained.

### EXP-003 — Per-learner interaction distribution *(Q-4)*
**Question:** How is history length distributed, and where do tier boundaries
fall?
**Hypothesis:** Right-skewed with a substantial mass at 1–2 interactions (mean is
3.333, but the mean is not the distribution).
**Method:** Full distribution of interactions per learner; percentiles; counts at
1, 2, 3, ≥5, ≥10.
**Metrics:** Histogram; percentiles; proportion evaluable under each protocol.
**Output:** Tier boundary candidates; `reports/figures/history_distribution.png`.
**Acceptance:** Distribution reported. Tier boundaries proposed **as candidates**;
final *t* is set by the EXP-025 rule, not by this distribution alone.

### EXP-004 — Temporal coverage and split viability
**Question:** Is a leakage-free global temporal split viable?
**Hypothesis:** `TransactionDate` spans roughly one year (358 distinct dates); a
cut at the 80th percentile leaves enough learners with both pre- and post-cut
interactions to evaluate.
**Method:** Date range and density over time; compute *V* (70th pct) and *T* (80th
pct); count learners evaluable under Protocol A and Protocol B.
**Metrics:** Evaluable-learner counts per protocol and per tier.
**Output:** Persisted split artifact in `data/processed/`; the **single** split all
later experiments load.
**Acceptance:** **This experiment triggers the pre-registered protocol decision.**
If Protocol A yields <300 evaluable learners, the primary protocol switches to
Protocol B and every figure is labelled leakage-bearing
(`recommendation_evaluation_plan.md` §2.3). The threshold was fixed in Phase 1 and
is not revisable here.

### EXP-005 — Is `TeacherID` an alias for `CourseID`? *(blocks EXP-014)*
**Question:** Is the teacher→course mapping a bijection?
**Hypothesis:** With exactly 60 teachers and 60 courses, plausibly one-to-one.
**Method:** Cross-tabulate `TeacherID` × `CourseID` in transactions; count
distinct teachers per course and courses per teacher.
**Metrics:** Mapping cardinality; entropy of teacher given course.
**Output:** A go/no-go decision on the entire teacher experiment.
**Acceptance:** **If the mapping is one-to-one, EXP-014 is cancelled** and the
reason recorded: every teacher-derived feature would be an alias for a
course-derived feature, adding no information while appearing to. That is a clean
negative result and a direct answer to §11. If many-to-many or one-to-many,
EXP-014 proceeds.

### EXP-006 — Feature distributions and the synthetic-data question
**Question:** What are the distributions, and is there evidence the data is
generated rather than observed?
**Hypothesis:** Some features are skewed (spend, history length). **Additionally,
the Phase 0 cardinalities are suggestive of synthetic data** — zero missing values
across 27 columns, 21 distinct ages in *both* Users and Teachers, 23 distinct
values in *both* Amount and CoursePrice.
**Method:** Univariate distributions for all candidate features; skewness and
kurtosis; correlation matrix; uniformity tests on Age, Gender, category
assignment; check whether IDs encode structure.
**Metrics:** Distribution summaries; correlation matrix; uniformity test results.
**Output:** EDA figures; scaler decision (D5); the correlation evidence for
EXP-011e.
**Acceptance:** Reported honestly. **If the data appears synthetic and
near-uniform, that is recorded as a material threat to validity (V8)** and every
downstream segmentation finding is qualified accordingly. §6 forbids presenting
generator artefacts as behavioural insight.

---

## 3. Phase 3 — segmentation experiments

### EXP-010 — Cluster-count selection sweep
**RQ:** RQ4
**Hypothesis:** A modest k (3–6) optimises silhouette; the elbow is ambiguous
[R07].
**Method:** K-Means (k-means++, `n_init=10`) for k ∈ {2..10}; record inertia,
silhouette (global and per-cluster), Calinski–Harabasz, Davies–Bouldin.
**Metrics:** All four indices vs k; per-cluster silhouette plots.
**Output:** Criterion table for every k; elbow and silhouette figures (both
brief-mandated).
**Acceptance:** All k values reported, including losers. **Elbow reported but not
decisive.** CH and DB explicitly flagged as correlated with silhouette, not
independent confirmation.

### EXP-010b — Gap statistic *(the falsification test)*
**RQ:** RQ1
**Hypothesis:** The gap statistic indicates k ≥ 2 — i.e. structure exists.
**Method:** Gap statistic [R02] over k ∈ {1..10}, B=50 uniform reference datasets
over the feature bounding box.
**Metrics:** Gap(k) with standard error; the smallest k satisfying the standard
gap criterion.
**Output:** Gap curve; a verdict on whether structure exists.
**Acceptance:** **If gap indicates k=1, that is the headline finding of the
segmentation work** and is reported prominently. The brief-mandated K-Means is
still produced for the deliverable, but every segment interpretation is marked
provisional. This is the only experiment that can falsify the project's central
premise, which is precisely why it is included.

### EXP-010c — GMM/BIC cross-check on k
**RQ:** RQ4
**Hypothesis:** BIC-optimal component count is within ±1 of the silhouette-optimal
k.
**Method:** Gaussian mixtures over k ∈ {2..10}; BIC and AIC.
**Metrics:** BIC/AIC vs k.
**Output:** Independent k evidence from a different model family.
**Acceptance:** Reported. **Divergence from EXP-010 is informative, not a
problem** — [R06] found k-selection rules frequently disagree.

### EXP-011 — Variant A vs Variant B *(§10)*
**RQ:** RQ3
**Hypothesis:** Variant B (behaviour only) produces segments that are more
actionable and no worse on downstream recommendation; demographics risk
dominating.
**Method:** Full segmentation pipeline under both feature sets at the EXP-010 k.
**Metrics:** Silhouette; per-cluster bootstrap Jaccard; intra-cluster similarity;
**demographic share of explained variance (η², §4 of `segmentation_research.md`)**;
interpretability; **downstream cluster-popularity NDCG@10**.
**Output:** Side-by-side comparison; the Variant decision.
**Acceptance:** Decided by the **pre-registered rule** in
`segmentation_research.md` §7 — not by inspection. Reject A if demographic share
>40%; prefer B on ties within 0.01 downstream NDCG@10.

### EXP-011a — Encoding comparison
**RQ:** RQ2
**Hypothesis:** One-hot (E-A) lets `PreferredCategory` dominate; the
category-proportion vector (E-B) gives better-balanced, more behavioural
segments.
**Method:** Segment under E-A, E-B, E-C (reduced facets), E-D (Gower + average
linkage); hold k and all else fixed.
**Metrics:** Silhouette; **η² attributable to the category block**; stability;
interpretability; downstream NDCG@10.
**Output:** The encoding decision (S-1).
**Acceptance:** The dominance effect is **measured, not asserted**. If E-A does
*not* in fact dominate, the Phase 1 inference is recorded as wrong in
`experiment_log.md` and E-A remains viable.

### EXP-011b — Feature-block weighting ablation
**RQ:** RQ2
**Hypothesis:** Weighting blocks to contribute comparably (e.g. 1/√columns)
produces more balanced η² across blocks without materially reducing silhouette.
**Method:** Segment with and without block weighting.
**Metrics:** η² per block; silhouette; downstream NDCG@10.
**Acceptance:** Reported either way. Makes weighting an explicit choice rather
than an accident of column counts (§14's principle).

### EXP-011c — Feature-dominance diagnostic
**RQ:** RQ2, RQ3
**Method:** One-way ANOVA η² per feature on cluster labels; aggregate per block.
**Metrics:** η² per feature (ranked); mean η² per block; demographic share.
**Output:** The measurement §10 requires, for every configuration tested.
**Acceptance:** Computed for **every** segmentation variant, not just the winner —
otherwise it cannot inform the choice.

### EXP-011d — PCA before clustering
**RQ:** RQ2
**Hypothesis:** PCA improves cluster separation but degrades interpretability
enough to be net-negative for this deliverable.
**Method:** Segment on the top components explaining ~90% variance; compare.
**Metrics:** Silhouette; interpretability (can centroids be described?);
downstream NDCG@10.
**Acceptance:** Reported. PCA is adopted for the **visualisation** requirement
regardless of this result.

### EXP-011e — Correlated-feature ablation
**RQ:** RQ2
**Hypothesis:** B4 (avg courses/category) is redundant given B3 and B10 — indeed
B4 = B3/B10 exactly — and its inclusion triple-weights the activity concept.
**Method:** Segment with the full mandated set vs a de-correlated subset.
**Metrics:** Correlation matrix; silhouette; η²; downstream NDCG@10.
**Acceptance:** All mandated features remain **investigated** (brief compliance)
whichever wins; the redundancy is documented and its effect on the distance metric
reported.

### EXP-011f — Does history length dominate the segmentation?
**RQ:** RQ1, RQ2
**Hypothesis:** The first axis of variation is activity volume, and diversity
score is substantially a proxy for it — because diversity is **bounded by** total
courses at a mean history of 3.333.
**Method:** Correlate cluster assignment with history length; compare raw
diversity vs diversity-normalised-by-opportunity (breadth ratio); test
within-activity-stratum clustering.
**Metrics:** η² of history length; correlation of diversity with B3; silhouette
under each treatment.
**Output:** Decision on breadth normalisation (S-6, S-7).
**Acceptance:** **If activity level genuinely is the dominant structure, that is
reported plainly** rather than engineered away. Option 3 in
`segmentation_research.md` §2.3 is a legitimate outcome.

### EXP-012 / EXP-012b — Hierarchical validation
**RQ:** RQ4
**Hypothesis:** Ward agrees substantially with K-Means (**partly due to shared
objective family**); average linkage is the more informative test.
**Method:** Ward and average linkage at the chosen k; ARI against K-Means. EXP-012b
adds average linkage over Gower distance [R11].
**Metrics:** ARI per pairing; dendrogram.
**Acceptance:** Ward–K-Means agreement is reported **with the shared-bias
caveat**. Agreement across all three methods is treated as materially stronger
evidence than Ward alone.

### EXP-013 / EXP-013b — Cluster stability
**RQ:** RQ1, RQ4
**Hypothesis:** Some clusters are stable (Jaccard ≥0.75); at least one may be
marginal (<0.6).
**Method:** EXP-013 — bootstrap per-cluster Jaccard [R03], B=100. EXP-013b —
subsample consensus stability [R04].
**Metrics:** Per-cluster Jaccard distribution; global partition similarity.
**Output:** A stability figure **per segment** for the executive summary.
**Acceptance:** Per-cluster values reported. **Clusters below 0.6 are labelled
unstable wherever they appear**, including in the dashboard — recommending a
strategy for a segment that dissolves under resampling would be an unsupported
claim (§6).

### EXP-014 — Teacher-derived signals *(blocked on EXP-005)*
**RQ:** RQ8
**Hypothesis:** Teacher signals add little beyond course attributes; `Expertise`
may be largely redundant with `CourseCategory`.
**Method:** Core model vs core + validated teacher features (`TeacherRating` as a
quality prior; `Expertise` as a second content facet; learner→teacher affinity).
**Explicitly excluded before testing: teacher `Age` and `Gender`** — third-party
demographics with no legitimate role in allocating recommendations [R38] — and
`TeacherName` (PII, §17).
**Metrics:** Association between `Expertise` and `CourseCategory`; segmentation
quality with/without; recommendation NDCG@10 with/without.
**Acceptance:** **Retained only on defensible evidence of improvement** (§11).
"No improvement" is a complete and publishable answer. **Cancelled outright if
EXP-005 shows a bijection.**

---

## 4. Phase 3 — recommendation experiments

All evaluated under the pre-registered protocol
(`recommendation_evaluation_plan.md`), on the **same** persisted split, with the
**same tuning budget** per [R26].

| ID | Method | Hypothesis |
| --- | --- | --- |
| **EXP-019** | **Random** | Reference floor. HR@10 ≈ 0.175 analytically; confirm empirically. |
| **EXP-020** | **Global popularity** | **Strong** — hard to beat on a 60-item catalogue [R20][R28]. Low coverage. |
| **EXP-021** | **Content-based** | Beats random; works from 1 interaction; **low coverage** from over-specialisation [R18]. |
| **EXP-022a** | **User-user CF over interaction history** | **Weak** — similarity from ~3.3 interactions is noisy. |
| **EXP-022b** | **User-user CF over profile features** | **Better than 022a** — features aggregate sparse history into a denser representation. |
| **EXP-022c** | **Item-based CF** | **Strong** — items have ~167 interactions each vs users' ~3.3 [R15][R16][R26]. |
| **EXP-023** | **Cluster popularity** | Beats global popularity **if** segmentation is meaningful; better coverage. |
| **EXP-024** | **Weighted hybrid + ablation** | Best accuracy, but possibly by a margin too small to justify its complexity. |
| **EXP-025** | **Tiered switching** | Personalisation beats cluster popularity only above some history threshold. |

**Metrics for every method:** NDCG@{5,10,20} (primary), HR@K, Precision@K (with
ceiling), Recall@K, MRR, catalogue coverage@K (co-primary), Gini, Engagement Lift
(Proxy) — reported **in aggregate and per tier**.

### EXP-024 — hybrid weight determination (§14)
Weights are **not** chosen by hand. Procedure: grid or coordinate search over
component weights, optimising **validation** NDCG@10; report the full ablation
(each component removed in turn) so each component's contribution is measured;
report the weight sensitivity surface. If the hybrid does not beat the best single
baseline by ≥0.01 validation NDCG@10, the **parsimony tiebreak** selects the
simpler method (`recommendation_evaluation_plan.md` §6, Step 4).

### EXP-025 — tier boundary determination (§15)
*t* = the smallest training-history length at which the personalised hybrid's
validation NDCG@10 exceeds cluster popularity's. **If no such point exists, the
finding is that personalisation never pays on this data** and the honest system is
simpler.

### EXP-026 — Leakage demonstration
**RQ:** RQ5
**Hypothesis:** A random (non-temporal) split inflates accuracy relative to the
global temporal split, and may reorder methods [R24][R25].
**Method:** Re-evaluate the top 3 methods under a random split; compare metrics
and rankings.
**Output:** A research-paper result quantifying leakage on EduPro.
**Acceptance:** Reported as a **methodological finding**, never as model
performance. This is the one and only use of the rejected random split (F3).

### EXP-027 — Demographic-stratified evaluation
**RQ:** RQ3
**Hypothesis:** Recommendation quality is comparable across gender and age bands.
**Method:** Stratify the selected method's metrics by gender and age band [R30].
**Metrics:** NDCG@10 and coverage per stratum.
**Acceptance:** **Reported whatever the result.** Runs even if Variant B excludes
demographics from the model — auditing with a protected attribute is not the same
as modelling with it. A disparity is an important finding, not a reason to omit
the analysis.

---

## 5. Experiment matrix

| ID | Phase | RQ | Blocks on | Decides |
| --- | --- | --- | --- | --- |
| EXP-001 | 2 | — | — | Data integrity policy |
| EXP-002 | 2 | — | EXP-001 | Feature B9 (Q-1) |
| EXP-003 | 2 | RQ7 | EXP-001 | Tier candidates (Q-4) |
| EXP-004 | 2 | RQ5 | EXP-001 | **Split protocol + persisted split** |
| EXP-005 | 2 | RQ8 | EXP-001 | **Go/no-go on EXP-014** |
| EXP-006 | 2 | RQ1 | EXP-001 | Scaler (D5); V8 threat; EXP-011e inputs |
| EXP-010 | 3 | RQ4 | EXP-006 | k candidates |
| EXP-010b | 3 | **RQ1** | EXP-006 | **Whether structure exists at all** |
| EXP-010c | 3 | RQ4 | EXP-006 | k cross-check |
| EXP-011 | 3 | RQ3 | EXP-010, EXP-023 | **Variant A vs B** |
| EXP-011a | 3 | RQ2 | EXP-010 | Encoding (S-1) |
| EXP-011b | 3 | RQ2 | EXP-011a | Block weighting (S-2) |
| EXP-011c | 3 | RQ2/3 | EXP-011a | Dominance measurement |
| EXP-011d | 3 | RQ2 | EXP-011a | PCA input (low priority) |
| EXP-011e | 3 | RQ2 | EXP-006 | Correlated-feature handling |
| EXP-011f | 3 | RQ1/2 | EXP-003 | Breadth normalisation (S-6/7) |
| EXP-012/b | 3 | RQ4 | EXP-010 | Hierarchical validation |
| EXP-013/b | 3 | RQ1/4 | EXP-010 | Per-cluster stability |
| EXP-014 | 3 | RQ8 | **EXP-005** | Teacher signals (§11) |
| EXP-019 | 3 | RQ5 | EXP-004 | Reference floor |
| EXP-020 | 3 | RQ5 | EXP-004 | Popularity baseline |
| EXP-021 | 3 | RQ5 | EXP-004 | Content-based |
| EXP-022a/b/c | 3 | RQ5 | EXP-004 | Similarity approaches |
| EXP-023 | 3 | **RQ6** | EXP-011 | **Does clustering help recommendation** |
| EXP-024 | 3 | RQ5 | EXP-020…023 | Hybrid + weights (§14) |
| EXP-025 | 3 | RQ7 | EXP-024 | Tier boundary *t* (§15) |
| EXP-026 | 3 | RQ5 | EXP-024 | Leakage quantification |
| EXP-027 | 3 | RQ3 | selection | Demographic parity audit |

**Critical path:** EXP-001 → EXP-004 (split) → EXP-006 → EXP-010/010b →
EXP-011 → EXP-023 → EXP-024 → EXP-025 → selection → one test evaluation.

**Circularity, and how it is resolved.** EXP-011 (Variant choice) uses downstream
NDCG@10, which requires EXP-023, which requires a segmentation. Resolution:
EXP-023 runs first against a **provisional** segmentation (the EXP-010
silhouette-optimal Variant B configuration), and the variant comparison uses that
fixed recommender. The recommender is **not** re-tuned per variant — otherwise the
comparison would confound segmentation quality with recommender tuning.

---

## 6. Expected outputs

| Output | Location |
| --- | --- |
| Per-experiment entries (incl. failures) | `research/experiment_log.md` |
| Machine-readable results | `experiments/<EXP-ID>/results.json` |

> **Where these actually went (added in Phase 6D).** The implementation consolidated every generated output under `artifacts/` — `artifacts/phase2_audit.json`, `artifacts/segmentation/`, `artifacts/recommendation/`, `artifacts/architecture/`, `artifacts/validation/` — rather than the per-experiment tree and `reports/figures/` planned here. The planned paths in this document are left as written, because it is a record of the plan; the empty directories were removed.
| Figures (elbow, silhouette, gap, stability, dendrogram, distributions) | `reports/figures/` |
| Persisted split | `data/processed/splits/` |
| Learner feature matrix | `data/processed/` |
| Full method comparison matrix | `research/experiment_log.md` + research paper |
| Decisions with evidence | `research/decision_log.md` |
| Architecture freeze | `research/architecture_decision_record.md` (Phase 4) |

---

## 7. Acceptance criteria

### 7.1 Per experiment
An experiment is complete when: the hypothesis was recorded before the run; the
result is logged with seed and script path; the interpretation states what the
result does **and does not** support; the decision is recorded; and any figures
are regenerable by re-running the script.

### 7.2 Phase 2
- [ ] EXP-001…006 complete and logged
- [ ] Split protocol decided by the **pre-registered** rule and persisted
- [ ] EXP-005 has returned a go/no-go on EXP-014
- [ ] V8 (synthetic-data) assessed and reported honestly
- [ ] Open questions Q-1…Q-4 answered or explicitly carried forward
- [ ] `data/raw/` checksums still pass

### 7.3 Phase 3
- [ ] All segmentation experiments complete, **including negative results**
- [ ] Gap statistic has returned a verdict on RQ1
- [ ] Per-cluster stability reported for the chosen partition
- [ ] Feature dominance measured for **every** variant
- [ ] Variant decided by the pre-registered rule
- [ ] All five brief-mandated recommendation baselines evaluated with equal tuning effort [R26]
- [ ] Random and popularity reference baselines in **every** results table
- [ ] Precision@K reported **with its analytical ceiling**
- [ ] Coverage reported as co-primary; the 25% gate applied
- [ ] Metrics reported **per tier**, not only in aggregate
- [ ] Hybrid weights justified by ablation, never asserted (§14)
- [ ] Test window used **exactly once**
- [ ] Engagement Lift labelled a **proxy** everywhere
- [ ] Leakage controls L1–L6 implemented as executable tests

### 7.4 What would make Phase 3 fail
Not "the hybrid lost". Phase 3 fails if: an experiment is run without a
pre-recorded hypothesis; a negative result is omitted; the test window is used
more than once; a metric is reported without its reference baseline; hybrid
weights are hand-chosen; or a causal claim is made from observational data.

**The hybrid losing to item-based CF or to popularity is a legitimate,
publishable outcome** — [R26] indicates it is the common one — and the
architecture (ADR-0005) was built so that outcome is reportable rather than
embarrassing.

---

## 8. Honest statement of expectations

Recorded so that hindsight cannot be presented as foresight. These are
**predictions**, and being wrong about them costs nothing:

1. Popularity will be **hard to beat** on raw accuracy [R20][R26][R28].
2. Item-based CF will be the **strongest single personalised method** — items have
   ~50× more interaction evidence than users here.
3. The hybrid will win on accuracy **by a small margin** and may lose the
   parsimony tiebreak.
4. Cluster structure will be **weak** — short histories and possible synthetic
   generation. The gap statistic may indicate k=1.
5. Variant B (behaviour only) will be preferred.
6. Teacher signals will add **nothing**, and EXP-005 may cancel the experiment
   outright.
7. Coverage will separate the methods more sharply than accuracy does.

**If the experiments contradict these, the experiments win.** Each is logged as a
pre-registered expectation in `experiment_log.md` so that the comparison between
prediction and outcome is itself part of the record.
