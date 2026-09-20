# Phase 3B — Recommendation System Experiments — COMPLETE

**Phase:** 3B — recommendation system experiments
**Date:** 19 September 2026
**Decision:** ✅ **PASS**
**Next phase:** Phase 4 — model selection and architecture freeze (**not started; awaiting go-ahead**)

---

## 1. Headline

> **No recommendation method beats random ranking on this dataset.**
>
> Eleven methods, evaluated on a leakage-free temporal split of 791 learners.
> Every 95% confidence interval on the paired per-learner NDCG@10 difference
> against random **contains zero** — in aggregate and within every history tier.
> Global popularity is *worse* than random on the test window (0.1072 vs 0.1102).

This is what Phase 2 predicted. Course choice in this dataset is statistically
indistinguishable from popularity-weighted chance, course popularity is
near-uniform (Gini 0.042), and demographics are independent of choice. A
recommender cannot find structure that is not there.

**It is the headline rather than a footnote**, per CLAUDE.md §6. The evaluation
design that makes it visible — a random baseline in every table, coverage as a
co-primary metric, pre-registered selection rules, a paired significance test —
was fixed in Phase 1 precisely so this outcome could be stated plainly.

**What it does not mean.** The methods are not wrong, the pipeline is not broken,
and personalisation is not impossible in education. Every component is tested and
transfers unchanged to real data. The limitation is the dataset, which Phase 2
assessed as almost certainly synthetic (D-025).

---

## 2. Protocol (Step 1)

Pre-registered in Phase 1, confirmed viable in Phase 2 (EXP-004).

| Window | Range | Interactions | Role |
| --- | --- | --- | --- |
| Training | < 2025-09-12 | 6,992 | features, popularity, similarity |
| Validation | 2025-09-12 → 2025-10-18 | 1,000 | **all model selection** |
| Fit | < 2025-10-18 | 7,992 | final training |
| Test | ≥ 2025-10-18 | 2,008 | **used exactly once** |

Evaluable learners: **511** (validation), **791** (test). Learners without training
history are excluded from personalised evaluation and reported separately — 350 of
them, 11.7% (§12).

### Leakage controls — all passed at both stages

| Control | Result |
| --- | --- |
| L1 — no held-out row in training | 0 overlapping IDs |
| L1b — nothing in training at or after the cut | latest training date < cut |
| L2 — exclusion from training history only | 0 mismatches |
| L3 — tier assignment from training history only | 0 mismatches |
| L5 — popularity from training window only | sums exactly to the training frame |
| L6 — held-out items present in the candidate pool | 0 learners with missing targets |

A test verifies the checker **can fail**: injecting five held-out rows into
training makes L1 fail. A check that cannot fail proves nothing.

---

## 3. Baselines (Steps 2–6)

Validation, 511 learners, sorted by NDCG@10. Precision ceiling **0.1542**.

| Method | NDCG@10 | HR@10 | P@10 | Coverage | Gini |
| --- | --- | --- | --- | --- | --- |
| hybrid | **0.1148** | 0.3366 | 0.0356 | 0.80 | 0.657 |
| tiered | 0.1135 | 0.3327 | 0.0352 | 1.00 | 0.608 |
| **cluster_popularity** | 0.1098 | 0.3033 | 0.0323 | 0.78 | 0.606 |
| item_item_cf | 0.1067 | 0.2975 | 0.0323 | 1.00 | 0.468 |
| user_user_history | 0.1065 | 0.2779 | 0.0294 | 1.00 | 0.142 |
| global_popularity | 0.1054 | 0.2877 | 0.0313 | **0.30** | **0.807** |
| teacher_affinity | 0.1043 | 0.2779 | 0.0299 | 1.00 | 0.666 |
| content_based | 0.1035 | 0.2877 | 0.0307 | 1.00 | 0.530 |
| **random** | **0.0973** | 0.2603 | 0.0284 | 1.00 | 0.055 |
| rating | 0.0956 | 0.2603 | 0.0288 | **0.30** | **0.811** |
| user_user_profile | 0.0944 | 0.2603 | 0.0288 | 1.00 | 0.233 |
| preference_match | 0.0924 | 0.2779 | 0.0297 | 1.00 | 0.483 |

The whole field spans 0.092–0.115. Two mandated baselines score **below random**.

**Step 6 — the rating signal.** Alone it is below random (0.0956) with 30%
coverage. But in the hybrid it took the **second-largest weight (0.249)** and
removing it cost the largest single ablation loss (−0.0102). Rating is a useful
tie-break on top of another signal and useless on its own — which is exactly what
isolating it was for.

---

## 4. Hybrid (Step 7)

Weights **searched, never chosen** (§14): 400 simplex samples, seed 42, on
validation NDCG@10. Half the samples zero a random subset so the search explores
subsets, not only full combinations.

| Component | Weight | Ablation Δ |
| --- | --- | --- |
| cluster_popularity | **0.557** | −0.0088 |
| rating | **0.249** | **−0.0102** |
| item_item_cf | 0.173 | −0.0036 |
| preference_match | 0.021 | +0.0002 |
| content_based | **0.000** | 0.0000 |
| user_user_profile | **0.000** | 0.0000 |

NDCG across all 400 samples: 0.0832–0.1148, **σ = 0.0057**. The weight choice moves
the metric by about one standard deviation of the search itself — the hybrid is not
delicately tuned, because there is little to tune against.

---

## 5. Selection — the pre-registered rule, applied as written

| Step | Rule | Outcome |
| --- | --- | --- |
| 1 | Beat **both** random and popularity on validation NDCG@10 | 5 eligible |
| 2 | Coverage@10 ≥ 25% | all 5 pass |
| 3 | Rank by validation NDCG@10 | hybrid leads (0.1148) |
| 4 | **Parsimony tiebreak** if margin < 0.01 | hybrid beat `cluster_popularity` by **0.0051** → **tiebreak applies** |
| 5 | Confirm once on test | done |

**Selected: `cluster_popularity`.** The rule — written in Phase 1 before any
number existed — rejects a six-signal hybrid that adds 0.005 NDCG.

Phase 1's pre-registered expectation **P-3** ("the hybrid will win by a small
margin and may lose the parsimony tiebreak") was **confirmed exactly**.

---

## 6. Test window — evaluated once

791 learners. Precision ceiling **0.2054**.

| Method | NDCG@10 | HR@10 | P@10 (% of ceiling) | Coverage | Lift (proxy) |
| --- | --- | --- | --- | --- | --- |
| hybrid | **0.1206** | 0.3578 | 0.0435 (21%) | 0.92 | 1.080 |
| content_based | 0.1191 | 0.3666 | 0.0439 (21%) | 1.00 | 1.107 |
| preference_match | 0.1165 | 0.3654 | 0.0416 (20%) | 1.00 | 1.103 |
| **cluster_popularity** *(selected)* | 0.1138 | 0.3590 | 0.0424 (21%) | 0.75 | 1.084 |
| tiered | 0.1117 | 0.3451 | 0.0425 (21%) | 1.00 | 1.042 |
| user_user_profile | 0.1105 | 0.3477 | 0.0411 (20%) | 1.00 | 1.050 |
| **random** | **0.1102** | 0.3464 | 0.0422 (21%) | 1.00 | **1.046** |
| teacher_affinity | 0.1076 | 0.3527 | 0.0410 (20%) | 1.00 | 1.065 |
| global_popularity | 0.1072 | 0.3312 | 0.0389 (19%) | 0.32 | 1.000 |
| item_item_cf | 0.1047 | 0.3515 | 0.0420 (20%) | 1.00 | 1.061 |
| rating | 0.1034 | 0.3325 | 0.0397 (19%) | 0.30 | 1.004 |
| user_user_history | 0.0947 | 0.3097 | 0.0362 (18%) | 1.00 | 0.935 |

**Random ranks 7th of 12.** Five methods score below it.

### The decisive test

Paired bootstrap, 2,000 resamples, per-learner NDCG@10 differences vs random:

| Method | Δ | 95% CI | Significant? |
| --- | --- | --- | --- |
| hybrid | +0.0162 | [−0.0033, +0.0355] | no |
| content_based | +0.0147 | [−0.0040, +0.0340] | no |
| cluster_popularity | +0.0093 | [−0.0092, +0.0271] | no |
| global_popularity | +0.0028 | [−0.0155, +0.0205] | no |
| user_user_history | −0.0098 | [−0.0269, +0.0067] | no |

**0 of 11 methods significantly better than random.** Per tier: minimal +0.0307
[−0.0076, +0.0687], moderate −0.0112 [−0.0463, +0.0229], rich +0.0079
[−0.0165, +0.0342] — the same answer everywhere.

### Engagement Lift (Proxy) — with its caveat

The selected method scores **1.084**. Defined in Phase 1 (D-014) before any
result: the ratio of a method's HR@10 to global popularity's.

> **Not measured causal impact, and never to be presented as such.** No
> impressions, no control group, no counterfactual. It is an offline agreement
> ratio. **Random scores 1.046 on the same measure** — the clearest possible
> illustration of why it must not be read as impact. No statement of the form
> "this would increase engagement by X%" appears anywhere in this project.

---

## 7. Sparse users (Step 8) and coverage (Step 9)

| Tier | Learners (all 3,000) | Evaluable | HR@10 | vs random |
| --- | --- | --- | --- | --- |
| insufficient (0) | 350 (11.7%) | — | fallback | n/a |
| minimal (1) | 1,514 (50.5%) | 213 | 0.244 | not significant |
| moderate (2–8) | 731 (24.4%) | 193 | 0.326 | not significant |
| rich (≥9) | 405 (13.5%) | 385 | 0.439 | not significant |

**The rising hit rate is arithmetic, not skill.** Grouped by held-out count
instead: 1 target → 0.207, 2 → 0.381, 3 → 0.573, 6 → 0.846. A learner with six
targets has six chances in ten slots. Rich-tier learners average 2.56 targets
against minimal's 1.11.

**Coverage, both senses:**

| Measure | Value |
| --- | --- |
| Learners receiving a recommendation | **3,000 (100%)** |
| Receiving a *personalised* recommendation | 2,650 (88.3%) |
| On the popularity fallback | 350 (11.7%) |
| Learners with an empty candidate pool | **0** |
| Mean candidate pool | 53.5 of 60 (range 45–59) |
| Catalogue coverage — selected method | **0.75** (15 courses never recommended) |
| Catalogue coverage — global popularity | **0.32** |

---

## 8. Teacher signal (Step 10)

`teacher_affinity` scores a course by how often the learner's prior instructors
teach it. Phase 2 measured the effect: learners reuse instructors far more than
chance (0.688 distinct teachers per interaction vs a 0.944 null), but next-course
lift was only 1.10× because each teacher covers ~15 of ~55 unseen courses.

| Split | NDCG@10 | Rank | vs random |
| --- | --- | --- | --- |
| Validation | 0.1043 | 7th of 12 | +0.0070 |
| Test | 0.1076 | 8th of 12 | +0.0032, CI [−0.0150, +0.0209] |

**Not retained.** Phase 1's expectation **P-6** is now confirmed for recommendation
as well as segmentation — with a specific reason: the signal is real but too
low-resolution to narrow a 55-course pool.

---

## 9. Error analysis (Step 11)

Full detail in `research/recommendation_error_analysis.md`.

**Present:**
- **Popularity bias.** Recommends courses at mean popularity rank 16.8 while
  learners' actual next courses sit at 28.6 (midpoint 30). Hits have targets at
  rank 23.3; misses at 31.5. All the cost of popularity bias, none of the usual
  accuracy compensation — because popularity here is near-uniform.
- **Level-based segments predicting a near-random dimension.** The Phase 3A
  segmentation is essentially a course-level split, and Phase 2 measured level
  choice as near-random with no progression over time (p = 0.664).
- **Category jumps.** 46% of evaluable learners move to a category they have never
  touched; hit rate falls from 0.443 to 0.260. A property of the learner, not a
  lever the model has — that information is part of the answer, not the input.

**Ruled out:**
- **Sparse history** — no tier beats random; the method is equally chance-level at
  1 and at 11 interactions.
- **Limited candidate pool** — every learner has ≥45 candidates.
- **Cold start as a cause of the aggregate** — the 350 zero-history learners are
  excluded from personalised evaluation entirely.
- **Leakage** — all six controls pass, and the checker is verified able to fail.
- **A metrics bug** — metrics are unit-tested against hand-computed rankings.

**Root cause:** no signal in the data, established independently in Phase 2 before
any recommender existed.

---

## 10. EXP-026 — the protocol reorders the methods

Protocol B (leave-one-out) leaks by the global-timeline definition [R25]. Its
*level* is lower across the board, but **that is not evidence of leakage
deflation**: Protocol B holds out one course per learner against Protocol A's
2.05, so its ceiling is lower. Reporting the level gap as a leakage effect would
be wrong.

**The reordering is the finding:**

| Method | Rank under A | Rank under B | Move |
| --- | --- | --- | --- |
| item_item_cf | 9th | **3rd** | +6 |
| global_popularity | 8th | 4th | +4 |
| **random** | **6th** | **11th** | **−5** |
| cluster_popularity | 4th | 7th | −3 |

Five methods move three or more places purely by changing the split. **Meng et
al. [R24] reproduced on EduPro** — and the concrete justification for having
pre-registered Protocol A as primary. A project using leave-one-out alone would
have concluded item-based CF was top-three and random bottom-ranked. Neither holds
under the leakage-free protocol.

---

## 11. EXP-027 — demographic strata

Run although the recommender uses **no demographic feature** [R30].

| Stratum | n | NDCG@10 |
| --- | --- | --- |
| Female | 412 | 0.1002 |
| Male | 379 | **0.1285** |
| Age 15–24 | 374 | 0.1198 |
| Age 25–35 | 417 | 0.1084 |

The gender gap is **nominally significant**: −0.0283, CI [−0.0543, −0.0010], and
consistent in direction across all three tiers.

**Reported, not dismissed — and bounded.** The recommender uses no gender feature;
Phase 2 found gender independent of course choice (p = 0.643); the interval barely
excludes zero and is uncorrected for four strata tests; and no method beats random
at all, so this is a disparity in chance-level performance. Recorded as requiring
**monitoring on real data**, not as a finding of discrimination.

---

## 12. Pre-registered expectations — final status

| # | Expectation | Outcome |
| --- | --- | --- |
| P-1 | Popularity hard to beat | **Refuted as stated, confirmed as revised** — worse than random; hard to beat because weak |
| P-2 | Item-based CF strongest single personalised method | **Refuted** — 8th of 12 on test |
| P-3 | Hybrid wins by a small margin, may lose the parsimony tiebreak | **Confirmed exactly** — won by 0.0051, lost the tiebreak |
| P-6 | Teacher signals add nothing | **Confirmed** for recommendation too |
| P-7 | Coverage separates methods more than accuracy | **Confirmed** — accuracy 1.3× spread, coverage 3.3× |

Two further Phase 1 inferences were wrong and are recorded: user-user similarity
over profile features was expected to beat the raw-history arm (it did not), and
item-based CF was expected to be better-conditioned than user-based (it was not).

---

## 13. PASS / FAIL

### ✅ **PASS**

| Pass criterion | Evidence | Verdict |
| --- | --- | --- |
| **All primary baselines evaluated** | 10 baselines — the brief's five plus random, item-item CF, a second similar-learner arm, preference match and teacher affinity — each on both splits with identical treatment [R26] | ✅ |
| **Temporal evaluation completed** | Pre-registered three-window protocol; 511 validation and 791 test learners; test used exactly once | ✅ |
| **Leakage checks passed** | All six controls at both stages, plus a test proving the checker can fail | ✅ |
| **Hybrid candidates tested** | Weighted hybrid (400-sample weight search + 6-component ablation + sensitivity spread) and tiered switching hybrid | ✅ |
| **Sparse-user behaviour analysed** | Four tiers; per-tier metrics; per-tier paired significance; the arithmetic confound identified and separated | ✅ |
| **Final candidate evidence-backed** | Selected by the pre-registered rule including the parsimony tiebreak; every competing method reported; the selection's non-significance against random stated plainly | ✅ |

### Tests

```
160 passed
```
31 environment + 36 pipeline + 37 segmentation + 56 recommendation.

### CLAUDE.md compliance

| § | Rule | How Phase 3B complied |
| --- | --- | --- |
| 6 | Scientific integrity | The headline is a **negative result**. Four Phase 1 predictions reported as wrong. The Engagement Lift proxy is reported with random's own lift (1.046) beside it |
| 9 | Leakage | Six controls verified in-run at both stages; the checker is itself tested |
| 12 | Sparse users | 350 zero-history learners excluded from personalised evaluation and counted separately; per-tier reporting throughout |
| 13 | Five baselines from evidence | All five plus five more; selection by pre-registered rule |
| 14 | Hybrid weights justified | 400-sample search on validation + full ablation + sensitivity spread. No weight chosen by hand |
| 15 | Sparse-history tiers | Four tiers, boundaries from the Phase 2 distribution, routed on training-window history (L3) |
| 16 | Explainability | The scorer returns per-component contributions (D-015), enforced by test; zero-weighted components never appear in a decomposition |
| 17 | Privacy | No demographic feature in any model; demographics used only as evaluation strata |
| 23 | Testing | 56 new tests including metric correctness against hand-computed answers and an injected leakage violation |
| 27 | Phase report with evidence | This document; every number traces to `recommendation_results.json` |
| 28 | Stop condition | Phase 3B evaluated; PASS; **stopping here** |

---

## 14. Recommendation carried to Phase 4

The pre-registered selection is `cluster_popularity` and it stands. But for
**deployment**, the tiered recommender is the better choice, and the reason is not
accuracy:

| | cluster_popularity | tiered |
| --- | --- | --- |
| Test NDCG@10 | 0.1138 | 0.1117 |
| Catalogue coverage | 0.75 | **1.00** |
| Zero-history handling | global fallback | **explicit tier, labelled** |
| Explanation faithfulness | popularity only | **routes by the signal actually used** |

The 0.0021 accuracy difference is far inside the noise band established in §6.
Where accuracy cannot distinguish two options, coverage, transparency and honest
cold-start handling should — and those are what §15 and §16 actually require. This
is a **documented recommendation to Phase 4**, not a reversal of the selection.

---

## 15. Unresolved issues

None blocking. Four carried forward:

1. **Nothing beats random.** The honest description of what EduPro would deploy is
   a segment-aware popularity recommender whose ranking quality on this dataset is
   indistinguishable from chance. The research paper and executive summary must
   say so.
2. **The dashboard must show the random reference.** "Hit Rate 36%" without
   "random achieves 35%" would mislead a stakeholder (§6).
3. **Gender gap requires monitoring** on real data — nominally significant,
   uncorrected, in a system using no demographic feature.
4. **Phase 0's two open items remain open**: the empty `claude.md.txt`, and the
   git-identity/authorship question (`Kartik <kartikshreekumar2006@gmail.com>` in
   the global git config vs the session account; `pyproject.toml` recorded a name
   inferred from that account). Both still need confirmation before publication.

   **RESOLVED 20 September 2026: the author is Kartik (`kartikshreekumar2006@gmail.com`), confirmed by the project owner. `pyproject.toml`, the paper byline and the rendered paper now all say so.**

---

## 16. Stop

Per CLAUDE.md §28 and the Phase 3B brief, work **stops here**. Phase 4 will not
begin automatically.

**Phase 4 will, on instruction,** freeze the architecture: confirm the deployment
choice between `cluster_popularity` and the tiered recommender, define the
artifact schema and version manifest (ADR/H1–H2), and record the frozen
configuration that Phase 5 implements.
