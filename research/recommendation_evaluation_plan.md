# Recommendation Evaluation Plan

**Phase:** 1 — research and methodology investigation
**Date:** 19 September 2026
**Status:** Pre-registered. Written **before any recommender is built or any
result is seen.**
**Reference keys `[Rxx]`** resolve in `literature_review.md` §10.

---

## 0. Why this document is pre-registered

CLAUDE.md §6 prohibits selectively reporting favourable results, and §9 makes
leakage detection mandatory. The most reliable defence against both is to fix the
protocol, the metrics and the decision rules **before** seeing any numbers. If
the evaluation design were chosen after the results, every choice would be
contaminated by knowledge of which choice flatters which method.

Everything in this document is therefore committed in advance. Any later change
must be recorded in `decision_log.md` with its reason and the date, so that
post-hoc modifications are visible rather than silent.

---

## 1. What is being evaluated

**Task.** Top-K course recommendation from implicit feedback. Given a learner's
history up to a point in time, rank the courses they have not yet enrolled in,
and measure whether the course they actually enrolled in next appears near the
top.

**Signal.** Purely implicit and purely binary. Phase 0 verified that all 10,000
transactions are distinct `(UserID, CourseID)` pairs — **zero repeat
enrollments** — so there is no frequency or repeat-purchase signal to weight by.
An enrollment is a 1; everything else is unobserved, **not** a 0.

**Candidate set.** All 60 courses minus the courses the learner has already
enrolled in *within the training window*. Excluding already-enrolled courses is
required by CLAUDE.md §23; excluding them by *training-window* history rather
than full history is required to avoid leaking the test item's existence.

---

## 2. The leakage problem, stated precisely

This is the part of the plan that most needs to be right, so the mechanism is
spelled out rather than assumed.

### 2.1 Why the conventional protocol leaks

The standard leave-one-out protocol holds out each user's own most recent
interaction. Each user's split point is therefore a **different calendar date**.

Consider user A whose held-out enrollment is dated 3 March, and user B whose
enrollments include one dated 14 June. Under per-user leave-one-out, B's June
interaction sits in the training set while the model predicts A's March
interaction. The model has been informed by events that had not happened at the
moment being predicted.

Ji, Sun, Zhang and Li studied exactly this and found that it affects accuracy and
that **the relative ordering of methods becomes unpredictable** as the amount of
leaked future data changes [R25]. Meng et al. independently showed that the
splitting strategy is a confounding variable capable of altering system rankings,
rendering much published work non-comparable [R24].

This matters more than a small metric inflation: if the leak can reorder methods,
then a leaky protocol could cause this project to select the wrong production
recommender.

### 2.2 Why not simply use the global split and stop

A global temporal cut at a single date *T* is leakage-free by construction — it
is exactly [R25]'s recommendation. But EduPro's data resists it: at a mean of
3.333 interactions per learner, a cut at *T* leaves many learners with no
training history, no post-*T* interaction, or neither. The evaluable population
may be small enough to make the estimate noisy.

### 2.3 Resolution: dual protocol, pre-registered primary

**Both protocols are run. Both are reported. The primary is fixed in advance.**

| | **Protocol A — Global temporal split** | **Protocol B — Per-user leave-one-out** |
| --- | --- | --- |
| Split rule | Single calendar date *T* for all learners | Each learner's most recent interaction |
| Leakage | **None** — respects the global timeline [R25] | **Present, by [R25]'s definition** |
| Evaluable users | Only those with ≥1 interaction before *T* **and** ≥1 after | All with ≥2 interactions |
| Role | **PRIMARY** — the headline result | **SECONDARY** — comparability with published work |
| Reported as | "Recommendation performance" | "Leave-one-out (leakage-bearing)" |

**Pre-registered fallback.** If EXP-004 shows Protocol A leaves fewer than **300
evaluable learners** (10% of the user base), Protocol A's estimates are too noisy
to carry the headline. In that case the primary switches to Protocol B, the
switch and its trigger are recorded in `decision_log.md`, and **every** reported
figure is labelled as leakage-bearing. The threshold is fixed now so the decision
cannot be made by looking at which protocol gives nicer numbers.

**If A and B disagree on method ranking, that disagreement is a headline
finding**, not an inconvenience — it would be [R24]'s result reproduced on EduPro
and belongs in the research paper.

### 2.4 Choosing *T*

Fixed by rule, not by tuning: *T* is the **80th percentile of `TransactionDate`**
across all transactions, giving a roughly 80/20 train/test split by interaction
volume. The percentile is chosen in advance; the resulting date is whatever the
data says it is. `TransactionDate` has 358 distinct values, so *T* will be a
real, well-populated date.

**Validation split.** For hyperparameter and hybrid-weight selection, a second
cut *V* at the **70th percentile** creates train (< *V*), validation (*V* to *T*)
and test (> *T*) windows. **The test window is touched exactly once**, at the end
of Phase 3, after all selection is complete.

### 2.5 The leakage controls, as a checklist

Each is independently testable, and each will have a test:

| # | Control | Test |
| --- | --- | --- |
| L1 | No test-window interaction contributes to any training feature | Recompute features from the training window alone; assert equality with the features used |
| L2 | Already-enrolled exclusion uses **training-window** history only | Assert the exclusion set is derived from the train frame |
| L3 | **Tier assignment uses training-window history only** | Assert tier is a function of the train frame — see below |
| L4 | Cluster assignment is fitted on training-window features only | Assert the fitted scaler/clusterer saw no post-*T* rows |
| L5 | Item popularity counts use training-window interactions only | Assert popularity vector sums to the train interaction count |
| L6 | Test interactions never appear in the candidate pool as "seen" | Assert candidate sets contain the held-out item |

> **L3 deserves emphasis.** A learner with 1 training interaction and 1 test
> interaction has *2* total. If tier assignment uses total history, the learner is
> routed to the "moderate" tier — a routing decision informed by the existence of
> the very interaction being predicted. This leak hides in the *routing logic*,
> not in the feature matrix, so a global-timeline audit of the features would not
> catch it. It is called out here because it is the subtle one.

---

## 3. Metrics

### 3.1 The reporting constraint that shapes everything

`scripts/analytical_baselines.py` computes, from the catalogue size alone:

| Reference value | K=5 | K=10 | K=20 |
| --- | --- | --- | --- |
| **Random-ranker Hit Rate** (1 held-out item, ~3 training items) | 0.088 | **0.175** | 0.351 |
| **Precision@K ceiling** (1 held-out item) | 0.200 | **0.100** | 0.050 |

Two consequences, both binding:

1. **A random recommender achieves HR@10 ≈ 0.175 on this catalogue.** Reporting
   "Hit Rate@10 = 0.22" without that reference would imply a useful system when
   the true improvement over guessing is marginal. **Every accuracy figure in
   this project is reported alongside the random baseline**, computed empirically
   as well as analytically.
2. **Precision@10 cannot exceed 0.10.** The official brief mandates
   "Recommendation Precision", so it is computed and reported — but always as
   "Precision@10 = 0.081 (ceiling 0.100)". Reporting the bare number would make a
   strong model look like a failure.

This is why **NDCG@10 is the primary accuracy metric**: it is not ceiling-limited
in the same way and it distinguishes rank 1 from rank 10, which the Precision
family cannot [R23].

### 3.2 Metric set

**K values: 5, 10, 20.** K=10 is primary (a plausible dashboard page size); K=5
and K=20 test rank sensitivity. K=20 is one third of the catalogue and is
reported mainly to show where the measure saturates.

| Metric | Definition | Role | Source |
| --- | --- | --- | --- |
| **NDCG@K** | Discounted cumulative gain normalised by the ideal ranking | **PRIMARY accuracy** | [R23] |
| **Hit Rate@K** | Fraction of evaluable learners with ≥1 held-out item in top-K | Primary interpretability | [R21][R22] |
| **Precision@K** | Relevant∩top-K / K | Brief-mandated; reported with ceiling | Brief p.5 |
| **Recall@K** | Relevant∩top-K / relevant | Reported; equals HR@K when exactly 1 item is held out | [R21] |
| **MRR** | Mean reciprocal rank of the first relevant item | Rank sensitivity | [R21] |
| **Catalogue coverage@K** | Distinct courses appearing in any top-K / 60 | **Co-primary** | [R27][R29] |
| **Gini / popularity concentration** | Concentration of recommendation exposure across courses | Popularity-bias diagnostic | [R29] |
| **Engagement Lift (Proxy)** | §7 below | Brief-mandated | Brief p.5 |

**Coverage is co-primary, not supplementary.** A recommender that routes every
learner to the same 8 courses can score well on accuracy while defeating the
brief's stated purpose of helping learners discover relevant content. The
selection rule in §6 treats a coverage collapse as disqualifying.

### 3.3 Mandatory reference baselines

Reported in **every** results table, not just once:

| Baseline | Why |
| --- | --- |
| **Random** | Establishes the floor. Non-negotiable at this catalogue size. |
| **Global popularity** | Published evidence says it is hard to beat on small catalogues [R20][R28] |
| **Analytical ceiling** | Precision@K upper bound |

A method that does not beat *both* random and popularity on NDCG@10 has not
demonstrated value, regardless of its absolute numbers.

---

## 4. Tiered evaluation

CLAUDE.md §12 forbids evaluating one-interaction learners as though they were
personalised-recommendation users. [R19] independently argues cold-start
performance needs its own metrics rather than being folded into an aggregate.

**Every metric is reported per tier and in aggregate.** An aggregate-only report
would hide the thing most worth knowing: whether personalisation works where it
is supposed to.

| Tier | Training-window history | Expected strategy | Evaluation note |
| --- | --- | --- | --- |
| **Insufficient** | 0 | Popularity + rating + diversity | **Not evaluable** for personalisation. Excluded from personalised metrics and reported as a population count. |
| **Minimal** | 1 | Content similarity + cluster popularity | Evaluable, but reported separately. Personalisation claims here are weak by construction. |
| **Moderate** | 2 to *t* | Content + item-similarity + cluster | Evaluable. |
| **Rich** | > *t* | Full weighted hybrid | Evaluable. The tier where personalisation should demonstrably pay. |

**Boundary *t* is not invented here.** Pre-registered rule: *t* = the smallest
training-history length at which the personalised hybrid's **validation** NDCG@10
exceeds the cluster-popularity recommender's. That is the point where
personalisation starts earning its complexity.

**If no such point exists**, the finding is that personalisation never beats
cluster popularity on this data, the tier collapses, and the honest system is the
simpler one. That outcome is reportable and is **not** a project failure — it is
what §6 requires and what [R26] suggests is common.

---

## 5. Segmentation-specific evaluation

Covered in depth in `segmentation_research.md`; summarised here for completeness.

| Metric | Purpose | Source |
| --- | --- | --- |
| Silhouette (global + per-cluster) | Cluster quality — mandated | Brief p.5; [R01] |
| Intra-cluster similarity | Behavioural consistency — mandated | Brief p.5 |
| Gap statistic | Can falsify the existence of structure | [R02] |
| Per-cluster bootstrap Jaccard | Which segments are real | [R03] |
| Feature-block dominance | Guards §10 — no block may swamp the distance | §10 |
| Calinski–Harabasz, Davies–Bouldin | Supporting indices (correlated with silhouette) | [R06] |

---

## 6. Pre-registered model-selection rule

Committed now so the winner cannot be chosen by whichever criterion happens to
favour a preferred method.

**Step 1 — Eligibility.** A method proceeds only if, on the **validation** split,
it beats **both** random and global popularity on NDCG@10.

**Step 2 — Coverage gate.** A method with catalogue coverage@10 below **25%**
(15 of 60 courses) is **disqualified**, regardless of accuracy. Rationale: a
system recommending fewer than a quarter of the catalogue is not performing
discovery, which is the brief's stated purpose. The threshold is set now, in
advance.

**Step 3 — Primary ranking.** Among eligible methods, rank by **validation
NDCG@10**.

**Step 4 — Parsimony tiebreak.** If the best method's validation NDCG@10 exceeds
the simplest eligible method's by **less than 0.01 absolute**, **select the
simpler method.** A complex hybrid that adds a rounding error of accuracy is not
worth its maintenance and explanation cost. This rule exists to stop the project
selecting the hybrid merely because the hybrid is the interesting outcome.

**Step 5 — Confirm once on test.** The selected method is evaluated **exactly
once** on the held-out test window. **That number is reported whatever it is.**
If it is worse than the validation estimate, the gap is reported and discussed —
it is not grounds for reopening selection.

**Step 6 — Report the full matrix.** Every method's metrics are published,
including the losers, per CLAUDE.md §6.

---

## 7. Engagement Lift (Proxy) — definition and guard rails

The brief mandates this metric and gives no formula. Defining it **before**
results are seen prevents choosing the definition that flatters the model.

### 7.1 What it cannot be

It cannot be a causal estimate. The data is observational: no impressions, no
control group, no counterfactual. Nothing computable offline measures what
learners *would have* done under a different recommendation policy.

### 7.2 Pre-registered definition

> **Engagement Lift (Proxy)** = the ratio of the recommender's Hit Rate@10 to the
> global-popularity baseline's Hit Rate@10, on the same evaluable population and
> the same split.
>
> Interpretation: *how much better this system agrees with learners' actual next
> enrollments than a non-personalised popularity list does.*

Rationale for this choice: it is directly computable, it is anchored to a
meaningful incumbent (popularity approximates a generic non-personalised
recommendation strategy), and its interpretation is honest — it is an agreement
ratio, not an effect size.

### 7.3 Mandatory guard rails

1. Named **"Engagement Lift (Proxy)"** everywhere — prose, tables, chart axes,
   dashboard labels. Never "Engagement Lift".
2. Every appearance carries the statement that it is an offline agreement ratio,
   **not measured causal impact**.
3. The research paper's limitations section states plainly that establishing real
   engagement impact requires an online controlled experiment that this project
   did not and could not run.
4. **No statement anywhere of the form "this system would increase engagement by
   X%".** That claim is not supported by any offline computation and §6 forbids
   it.

---

## 8. Reproducibility

- **Seed.** `edupro.config.RANDOM_SEED = 42` for every stochastic step.
- **Split artifacts.** *T* and *V*, and the resulting train/validation/test
  interaction ID sets, are computed once and persisted to `data/processed/`.
  Every experiment loads the same split; none re-derives it.
- **Provenance.** Each results row records method, parameters, split protocol,
  seed and the script that produced it.
- **Test-window budget.** One evaluation, at the end of Phase 3, on the selected
  method. Recorded in `experiment_log.md` when spent.

---

## 9. Threats to validity — declared in advance

To appear in the research paper's limitations section. Declared now so they are
not discovered by a reviewer.

| # | Threat | Mitigation | Residual risk |
| --- | --- | --- | --- |
| V1 | **Missing-not-at-random.** A non-enrollment is not a negative; learners cannot enroll in what they never saw. No impression data exists. | None available | **High — unavoidable** |
| V2 | **No counterfactual.** Offline evaluation measures agreement with behaviour under an unknown incumbent policy. | Proxy labelled as proxy | **High — unavoidable** |
| V3 | **Popularity-biased metrics** [R28][R29] | Coverage and Gini co-reported | Moderate |
| V4 | **Split sensitivity** [R24][R25] | Dual protocol; both reported | Moderate |
| V5 | **Small catalogue inflates all accuracy metrics** | Random baseline in every table; ceilings stated | Low, once disclosed |
| V6 | **Short histories limit personalisation headroom** | Tiered evaluation | Moderate |
| V7 | **Single dataset, single time period** — no external validity | Stated as a limitation | Moderate |
| V8 | **Synthetic-data risk.** Uniform column cardinalities (21 distinct ages in both Users and Teachers; 23 distinct values in both Amount and CoursePrice; zero missing values anywhere) are consistent with a generated dataset. If so, learned structure may be an artefact of the generator rather than of real learner behaviour. | EXP-006 characterises the distributions; findings reported with this caveat | **Potentially high — assess in Phase 2** |

> **V8 is flagged as a first-class threat, not a footnote.** Zero missing values
> across 4 sheets and 27 columns is uncommon in real transactional data. If Phase
> 2 finds uniformly-distributed features and no realistic skew, then cluster
> structure may be weak or arbitrary — and the honest report is that the
> *methodology* is sound and demonstrated while the *segments* may not describe
> real learner populations. §6 requires saying so rather than presenting
> generator artefacts as behavioural insight. The gap statistic [R02] and
> stability analysis [R03] are the tools that would detect this, which is a
> further reason both are in the plan.
