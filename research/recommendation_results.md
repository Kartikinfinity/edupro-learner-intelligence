# Recommendation Results

**Phase:** 3B — recommendation system experiments
**Date:** 19 September 2026
**Reproduce:** `python scripts/run_recommendation_experiments.py` → `artifacts/recommendation/recommendation_results.json`
**Figures:** `python scripts/generate_recommendation_figures.py`
**Reference keys `[Rxx]`** resolve in `research/literature_review.md` §10.

---

## 0. Headline

> **No recommendation method beats random ranking on this dataset.**
>
> Across eleven methods evaluated on a leakage-free temporal split of 791
> learners, every 95% confidence interval on the paired per-learner NDCG@10
> difference against random **contains zero** — in aggregate and within every
> history tier. Global popularity is in fact *worse* than random on the test
> window (0.1072 vs 0.1102).

This is the outcome Phase 2's signal detection predicted: course choice in this
dataset is statistically indistinguishable from popularity-weighted chance, and
course popularity itself is near-uniform (Gini 0.042). A recommender cannot find
structure that is not there.

It is reported as the headline rather than buried, per CLAUDE.md §6, and the
evaluation design that makes it visible — a random baseline in every table,
coverage as a co-primary metric, pre-registered selection rules — was fixed in
Phase 1 precisely so this result could be stated clearly.

**What this does not mean.** It does not mean the methods are wrong, the pipeline
is broken, or personalisation is impossible in education. Every component is
tested and would transfer unchanged to real EduPro data. The limitation is the
dataset, which Phase 2 assessed as almost certainly synthetic (D-025).

---

## 1. Protocol

Pre-registered in Phase 1, confirmed viable in Phase 2 (EXP-004).

| Window | Range | Interactions | Role |
| --- | --- | --- | --- |
| Training | < 2025-09-12 | 6,992 | features, popularity, similarity |
| Validation | 2025-09-12 → 2025-10-18 | 1,000 | **all model selection** |
| Fit | < 2025-10-18 | 7,992 | final training |
| Test | ≥ 2025-10-18 | 2,008 | **used exactly once** |

| | Validation stage | Test stage |
| --- | --- | --- |
| Evaluable learners | **511** | **791** |
| Held-out interactions | 632 | 1,625 |
| Mean held-out per learner | 1.24 | 2.05 |
| Tier mix | minimal 197 · moderate 202 · rich 112 | minimal 213 · moderate 193 · rich 385 |

A learner is evaluable only with at least one interaction in **both** windows:
training history to build from, and a held-out interaction to predict. Learners
without training history are excluded from personalised evaluation and counted
separately (§12) rather than scored as if personalisation had applied.

### 1.1 Leakage controls — all passed, at both stages

| Control | Check | Result |
| --- | --- | --- |
| **L1** | No held-out row appears in training | 0 overlapping transaction IDs |
| **L1b** | Nothing in training occurs at or after the cut | latest training date < cut |
| **L2** | Already-enrolled exclusion uses training history only | 0 mismatched learners |
| **L3** | Tier assignment uses training history only | 0 mismatched learners |
| **L5** | Popularity counts come from the training window only | sums to the training frame exactly |
| **L6** | Every held-out item is present in the candidate pool | 0 learners with missing targets |

These run as part of the experiment, not as a review step. A test also verifies
the checker **can fail**: injecting five held-out rows into training makes L1 fail
(`test_leakage_check_detects_an_injected_violation`). A check that cannot fail
proves nothing.

---

## 2. Validation results — where selection happened

511 learners. Sorted by NDCG@10.

| Method | NDCG@10 | HR@10 | P@10 | Recall@10 | MRR | Coverage | Gini |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **hybrid** | **0.1148** | 0.3366 | 0.0356 | 0.2366 | 0.1200 | 0.80 | 0.657 |
| tiered | 0.1135 | 0.3327 | 0.0352 | 0.2347 | 0.1189 | 1.00 | 0.608 |
| **cluster_popularity** | **0.1098** | 0.3033 | 0.0323 | 0.2138 | 0.1234 | 0.78 | 0.606 |
| item_item_cf | 0.1067 | 0.2975 | 0.0323 | 0.2121 | 0.1186 | 1.00 | 0.468 |
| user_user_history | 0.1065 | 0.2779 | 0.0294 | 0.2005 | 0.1237 | 1.00 | 0.142 |
| global_popularity | 0.1054 | 0.2877 | 0.0313 | 0.2139 | 0.1165 | **0.30** | **0.807** |
| teacher_affinity | 0.1043 | 0.2779 | 0.0299 | 0.1949 | 0.1217 | 1.00 | 0.666 |
| content_based | 0.1035 | 0.2877 | 0.0307 | 0.2106 | 0.1168 | 1.00 | 0.530 |
| **random** | **0.0973** | 0.2603 | 0.0284 | 0.1891 | 0.1138 | 1.00 | 0.055 |
| rating | 0.0956 | 0.2603 | 0.0288 | 0.1853 | 0.1141 | **0.30** | **0.811** |
| user_user_profile | 0.0944 | 0.2603 | 0.0288 | 0.1944 | 0.1071 | 1.00 | 0.233 |
| preference_match | 0.0924 | 0.2779 | 0.0297 | 0.1957 | 0.1046 | 1.00 | 0.483 |

Precision@10 ceiling on this split: **0.1542** (mean 1.24 held-out courses in ten
slots). Every precision figure must be read against it — the best method achieves
23% of what was achievable, not 3.6% of a notional 1.0.

**Three observations.**

1. **The entire field spans 0.092 to 0.115 NDCG.** Random sits at 0.097, near the
   middle.
2. **Popularity and rating concentrate on 30% of the catalogue** (Gini 0.81) and
   gain nothing for it — the popularity-bias failure mode [R29] with none of the
   usual accuracy compensation, because popularity here is near-uniform.
3. **Two mandated baselines score below random**: `preference_match` and
   `user_user_profile`. Phase 1 predicted user-user similarity would be weak at
   ~3.3 interactions per learner; it was weaker than predicted.

---

## 3. Steps 2–6 — What each baseline contributed

### Baseline A — Global popularity (EXP-020)
Validation NDCG 0.1054, coverage **0.30**, Gini **0.807**. Beats random on
validation but **loses to random on the test window** (0.1072 vs 0.1102).

Phase 1's pre-registered expectation **P-1** said popularity would be hard to
beat. Phase 2 revised that: popularity is near-uniform, so it is hard to beat
because it is *weak*, not strong. The test result confirms the revision.

### Baseline B — Content-based (EXP-021)
Validation NDCG 0.1035, full coverage. Uses category, level, type, rating and
duration; the learner profile is the mean content vector of their training
courses, so it works from a single interaction.

`CourseName` was deliberately excluded: 58 distinct names across 60 courses with
no descriptive text, so TF-IDF over titles would be near-degenerate (Phase 1).

**On the test window it is the best single baseline** (NDCG 0.1191) — though not
significantly better than random.

### Baseline C — Similar learner (EXP-022)
Split into two arms because the brief's "similar learner profiles" does not
specify the similarity space:

| Arm | Similarity over | Validation NDCG |
| --- | --- | --- |
| `user_user_history` | raw interaction vectors | 0.1065 |
| `user_user_profile` | engineered feature vectors | 0.0944 |

Phase 1 expected the profile arm to be better-conditioned, since the aggregation
is what makes a 3-interaction history usable. **It was worse** — on both splits.
Recorded as a wrong prediction.

`item_item_cf` was added beyond the brief on the reasoning that items have ~167
interactions each against users' ~3.3 [R15][R16]. It scored 0.1067 on validation
(4th) but 0.1047 on test (8th) — no better than the user-based arms.

### Baseline D — Cluster popularity (EXP-023) — **the answer to Q-10**
Validation NDCG **0.1098** (3rd), test **0.1138** (3rd), coverage 0.75–0.78.

**This is the experiment that tests whether the Phase 3A segmentation has
practical value.** ADR-0005 made the cluster signal ablatable so the question
could be answered rather than assumed.

| Comparison | Validation | Test |
| --- | --- | --- |
| cluster_popularity vs global_popularity | +0.0044 | **+0.0066** |
| cluster_popularity vs random | +0.0125 | **+0.0036** |
| Paired CI vs random (test) | — | **[−0.0092, +0.0271] — contains zero** |

**Answer to Q-10: the segmentation improves on global popularity but not on
random, and not significantly.** Segmenting learners and recommending within
segment is better than recommending globally popular courses — but since global
popularity is itself worse than random here, that is a low bar. The segmentation
has **not** demonstrated recommendation value.

### Step 6 — Rating-weighted signal
`rating` alone: validation NDCG 0.0956, **below random**, coverage 0.30, Gini
0.811. Rating carries no ranking information on its own.

But in the hybrid search, **rating received the second-largest weight (0.249)**
and removing it costs −0.0102 NDCG — the largest single ablation loss. So rating
functions as a useful *tie-break on top of another signal* while being useless
alone. That distinction is exactly what isolating it was for.

---

## 4. Step 7 — Hybrid (EXP-024)

Weights were **searched, never chosen** (§14): 400 samples from the simplex,
seed 42, evaluated on validation NDCG@10. Half the samples zero a random subset of
components, so the search explores subsets rather than only full combinations.

### Best weights

| Component | Weight |
| --- | --- |
| cluster_popularity | **0.557** |
| rating | **0.249** |
| item_item_cf | 0.173 |
| preference_match | 0.021 |
| content_based | **0.000** |
| user_user_profile | **0.000** |

Best validation NDCG@10 = **0.1148**. Across all 400 samples NDCG ranged
0.0832–0.1148 with a standard deviation of **0.0057** — the weight choice moves
the metric by about one standard deviation of the search itself, which is a
sensitivity result worth stating: the hybrid is not delicately tuned, because
there is little to tune against.

### Ablation

| Component removed | NDCG@10 | Δ vs full |
| --- | --- | --- |
| rating | 0.1047 | **−0.0102** |
| cluster_popularity | 0.1060 | **−0.0088** |
| item_item_cf | 0.1112 | −0.0036 |
| preference_match | 0.1151 | +0.0002 |
| content_based | 0.1148 | 0.0000 |
| user_user_profile | 0.1148 | 0.0000 |

Two components (`content_based`, `user_user_profile`) received zero weight, so
removing them changes nothing — the search had already discarded them. Only
`rating` and `cluster_popularity` carry material weight.

### Step 8's companion — the tiered switching hybrid (EXP-025)

Routes by **training-window** history (control L3): insufficient → global
popularity, minimal → content-based, moderate and rich → the tuned hybrid.

Validation NDCG 0.1135 with **full catalogue coverage** (vs the hybrid's 0.80).
Test NDCG 0.1117.

---

## 5. The pre-registered selection

| Step | Rule | Outcome |
| --- | --- | --- |
| 1 | Beat **both** random and global popularity on validation NDCG@10 | 5 methods eligible |
| 2 | Coverage@10 ≥ 25% | all 5 pass |
| 3 | Rank by validation NDCG@10 | hybrid (0.1148) leads |
| 4 | **Parsimony tiebreak**: if the margin over the simplest eligible method is < 0.01, take the simpler one | hybrid beat `cluster_popularity` by **0.0051** → **tiebreak applies** |
| 5 | Confirm once on test | done |

**Selected: `cluster_popularity`.**

The hybrid is more accurate on validation but by less than the pre-registered
margin, so the rule — written in Phase 1 before any number existed — selects the
simpler method. A six-signal hybrid that adds 0.005 NDCG is not worth its
maintenance and explanation cost.

---

## 6. The test window — evaluated once

791 learners. Precision@10 ceiling: **0.2054**.

| Method | NDCG@10 | HR@10 | P@10 | % of ceiling | Recall@10 | MRR | Coverage | Lift (proxy) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid | **0.1206** | 0.3578 | 0.0435 | 21% | 0.2101 | 0.1511 | 0.92 | 1.080 |
| content_based | 0.1191 | 0.3666 | 0.0439 | 21% | 0.2205 | 0.1427 | 1.00 | 1.107 |
| preference_match | 0.1165 | 0.3654 | 0.0416 | 20% | 0.2112 | 0.1454 | 1.00 | 1.103 |
| **cluster_popularity** *(selected)* | **0.1138** | 0.3590 | 0.0424 | 21% | 0.2080 | 0.1412 | 0.75 | 1.084 |
| tiered | 0.1117 | 0.3451 | 0.0425 | 21% | 0.1998 | 0.1423 | 1.00 | 1.042 |
| user_user_profile | 0.1105 | 0.3477 | 0.0411 | 20% | 0.2010 | 0.1397 | 1.00 | 1.050 |
| **random** | **0.1102** | 0.3464 | 0.0422 | 21% | 0.1975 | 0.1440 | 1.00 | 1.046 |
| teacher_affinity | 0.1076 | 0.3527 | 0.0410 | 20% | 0.2018 | 0.1350 | 1.00 | 1.065 |
| global_popularity | 0.1072 | 0.3312 | 0.0389 | 19% | 0.1873 | 0.1440 | 0.32 | 1.000 |
| item_item_cf | 0.1047 | 0.3515 | 0.0420 | 20% | 0.2069 | 0.1253 | 1.00 | 1.061 |
| rating | 0.1034 | 0.3325 | 0.0397 | 19% | 0.1885 | 0.1363 | 0.30 | 1.004 |
| user_user_history | 0.0947 | 0.3097 | 0.0362 | 18% | 0.1738 | 0.1233 | 1.00 | 0.935 |

**Random ranks 7th of 12.** Five methods score below it.

### Engagement Lift (Proxy) — with its mandatory caveat

Defined in Phase 1 (D-014) before any result: the ratio of a method's HR@10 to
global popularity's. The selected method's value is **1.084**.

> **This is not measured causal impact and must never be presented as such.** The
> data is observational: no impressions, no control group, no counterfactual. The
> figure says the system agrees with learners' actual next enrollments 8.4% more
> often than a non-personalised popularity list does — an offline agreement ratio.
> Establishing real engagement impact would require an online controlled
> experiment this project did not and could not run. **No statement of the form
> "this system would increase engagement by X%" appears anywhere in this project.**
>
> Note also that random scores a lift of **1.046** on the same measure, which is
> the clearest possible illustration of why the proxy must not be read as impact.

---

## 7. Does anything beat random? The decisive test

An aggregate gap of a few thousandths of NDCG on 791 learners means nothing
without a test. Pairing by learner removes the between-learner variance that
dominates here, where one learner has five held-out courses and another has one.

**Paired bootstrap, 2,000 resamples, per-learner NDCG@10 differences vs random:**

| Method | Δ NDCG@10 | 95% CI | Significant? |
| --- | --- | --- | --- |
| hybrid | +0.0162 | [−0.0033, +0.0355] | **no** |
| content_based | +0.0147 | [−0.0040, +0.0340] | **no** |
| preference_match | +0.0121 | [−0.0068, +0.0305] | **no** |
| cluster_popularity | +0.0093 | [−0.0092, +0.0271] | **no** |
| tiered | +0.0072 | [−0.0126, +0.0245] | **no** |
| user_user_profile | +0.0061 | [−0.0113, +0.0251] | **no** |
| teacher_affinity | +0.0032 | [−0.0150, +0.0209] | **no** |
| global_popularity | +0.0028 | [−0.0155, +0.0205] | **no** |
| item_item_cf | +0.0002 | [−0.0179, +0.0174] | **no** |
| rating | −0.0010 | [−0.0193, +0.0163] | **no** |
| user_user_history | −0.0098 | [−0.0269, +0.0067] | **no** |

**Zero of eleven methods are significantly better than random.**

### Per tier — the same answer everywhere

| Tier | n | Δ NDCG vs random | 95% CI | Significant? |
| --- | --- | --- | --- | --- |
| minimal (1 interaction) | 213 | +0.0307 | [−0.0076, +0.0687] | no |
| moderate (2–8) | 193 | −0.0112 | [−0.0463, +0.0229] | no |
| rich (≥9) | 385 | +0.0079 | [−0.0165, +0.0342] | no |

The selected method's largest apparent advantage is in the **minimal** tier —
learners with one interaction — which is the opposite of what personalisation
should do, and it is not significant either.

---

## 8. Step 9 — Coverage, both senses

### Learner coverage

| Measure | Value |
| --- | --- |
| Total learners | 3,000 |
| Receiving a recommendation | **3,000 (100%)** |
| Receiving a *personalised* recommendation | 2,650 (88.3%) |
| On the popularity fallback | **350 (11.7%)** |
| With an empty candidate pool | **0** |
| Mean candidate pool | 53.5 of 60 (range 45–59) |

| Tier | Learners | Share |
| --- | --- | --- |
| insufficient (0 training interactions) | 350 | 11.7% |
| minimal (1) | 1,514 | 50.5% |
| moderate (2–8) | 731 | 24.4% |
| rich (≥9) | 405 | 13.5% |

No learner is left without a recommendation, and no learner has fewer than 45
candidates — so top-10 can always be filled.

### Catalogue coverage

| Method | Coverage@10 | Gini |
| --- | --- | --- |
| random, content_based, preference_match, item_item_cf, teacher_affinity, user_user_*, tiered | **1.00** | 0.14–0.67 |
| hybrid | 0.92 | — |
| cluster_popularity | **0.75** | 0.606 |
| global_popularity | **0.32** | 0.807 |
| rating | **0.30** | 0.811 |

All eligible methods cleared the pre-registered 25% gate, so it never bound — but
it would have disqualified nothing here only because no method both concentrated
*and* won.

---

## 9. Step 10 — Teacher signal (EXP-022 teacher arm)

`teacher_affinity` scores a course by how often the learner's prior instructors
teach it. Phase 2 measured the effect it exploits: learners reuse instructors far
more than chance (0.688 distinct teachers per interaction against a 0.944 null),
but the lift on next-course prediction was only **1.10×**, because each teacher
covers ~15 of ~55 unseen courses.

| Split | NDCG@10 | Rank | vs random |
| --- | --- | --- | --- |
| Validation | 0.1043 | 7th of 12 | +0.0070 |
| Test | 0.1076 | 8th of 12 | +0.0032, CI [−0.0150, +0.0209] |

**Not retained.** It is not significantly better than random, and it did not earn
a place in the hybrid search (it was not among the six components, having been
excluded from segmentation in D-030 and tested here as a standalone baseline).

Phase 1's expectation **P-6** ("teacher signals will add nothing") is now
**confirmed for both segmentation and recommendation** — though for recommendation
the reason is specific: the signal is real but too low-resolution to narrow a
55-course candidate pool.

---

## 10. EXP-026 — The protocol reorders the methods

Protocol B (per-user leave-one-out) **leaks** by the global-timeline definition
[R25]. It is reported only for comparability with published work.

| Method | Protocol A (leakage-free) | Protocol B (leaking) | Difference |
| --- | --- | --- | --- |
| hybrid | 0.1206 | 0.0932 | −0.0274 |
| content_based | 0.1191 | 0.0899 | −0.0292 |
| cluster_popularity | 0.1138 | 0.0850 | −0.0287 |
| **random** | **0.1102** | **0.0785** | −0.0317 |
| item_item_cf | 0.1047 | 0.0893 | −0.0153 |

**A caution about the direction.** Protocol B scores *lower* across the board, but
that is **not** evidence that leakage deflates results. Protocol B holds out
exactly one course per learner while Protocol A holds out 2.05 on average, so
Protocol B's Precision/NDCG ceiling is lower. The level difference is an artefact
of target counts, not of leakage, and it would be wrong to report it as one.

**The finding that does matter is the reordering:**

| Method | Rank under A | Rank under B | Move |
| --- | --- | --- | --- |
| item_item_cf | 9th | **3rd** | +6 |
| global_popularity | 8th | 4th | +4 |
| **random** | **6th** | **11th** | **−5** |
| cluster_popularity | 4th | 7th | −3 |
| user_user_history | 11th | 8th | +3 |

Five methods move three or more places purely by changing the split. **This is
Meng et al.'s result [R24] reproduced on EduPro**, and it is the concrete
justification for having pre-registered Protocol A as primary: a project that had
used leave-one-out alone would have concluded item-based CF was a top-three method
and random a bottom-ranked one. Under the leakage-free protocol, neither holds.

---

## 11. EXP-027 — Demographic-stratified evaluation

Run even though the recommender uses **no demographic feature** — being able to
report whether quality is equivalent across groups is a stronger position than not
looking [R30].

| Stratum | n | NDCG@10 | HR@10 |
| --- | --- | --- | --- |
| Female | 412 | 0.1002 | 0.3398 |
| Male | 379 | **0.1285** | 0.3799 |
| Age 15–24 | 374 | 0.1198 | 0.3717 |
| Age 25–35 | 417 | 0.1084 | 0.3477 |

**The gender gap is nominally significant**: −0.0283 (female − male), 95% CI
[−0.0543, −0.0010], and the direction is **consistent across all three tiers**
(minimal −0.018, moderate −0.025, rich −0.034).

### How this should and should not be read

**Reported, not dismissed.** The gap is real in this sample and consistent.

**But four things bound it:**
1. The recommender uses **no demographic feature** — neither gender nor age enters
   any model. There is no mechanism by which it could treat the groups differently
   by design.
2. Phase 2 found gender **independent of course choice** (χ² p = 0.643 for
   category, p = 0.906 for level).
3. The interval **barely excludes zero** (upper bound −0.0010) and is **not
   corrected for multiple comparisons**; with four strata tested, a Bonferroni
   adjustment would not leave it significant.
4. **No method beats random at all**, so this is a disparity in how well random-
   equivalent rankings happen to align with two groups' held-out courses.

**Conclusion:** recorded as an observed disparity requiring monitoring on real
data, not as evidence of a discriminatory system. On a dataset where nothing beats
chance, a gap in chance-level performance is most plausibly sampling variation
plus the slight tier-composition difference between the groups (female 46.4% rich
vs male 51.2%).

---

## 12. Pre-registered expectations — final status

| # | Phase 1 expectation | Outcome |
| --- | --- | --- |
| P-1 | Popularity hard to beat | **Refuted as stated, confirmed as revised.** Popularity is worse than random on test. Hard to beat because weak, not strong |
| P-2 | Item-based CF the strongest single personalised method | **Refuted.** 8th of 12 on test; content-based led |
| P-3 | Hybrid wins by a small margin, may lose the parsimony tiebreak | **Confirmed exactly.** Won validation by 0.0051, **lost the tiebreak** |
| P-6 | Teacher signals add nothing | **Confirmed** for recommendation as well as segmentation |
| P-7 | Coverage separates methods more sharply than accuracy | **Confirmed.** Accuracy spans 0.095–0.121 (1.3×); coverage spans 0.30–1.00 (3.3×) |

Two further predictions from Phase 1's literature review were also wrong and are
recorded as such: user-user similarity over *profile features* was expected to
beat the raw-history arm (it did not, on either split), and item-based CF was
expected to be better-conditioned than user-based (it was not).

---

## 13. What this means for the production system

**The selected method is `cluster_popularity`**, by the pre-registered rule. But
it is not significantly better than random, so the honest description of what
EduPro would be deploying is:

> A segment-aware popularity recommender that covers 75% of the catalogue, reaches
> every learner, degrades gracefully for the 11.7% with no history, and produces
> faithful explanations — and whose ranking quality on this dataset is
> indistinguishable from chance.

**For Phase 5, the tiered recommender is the better production choice despite
ranking below `cluster_popularity`**, and the reason is not accuracy:

| | cluster_popularity | tiered |
| --- | --- | --- |
| Test NDCG@10 | 0.1138 | 0.1117 |
| Catalogue coverage | 0.75 | **1.00** |
| Honest handling of zero-history learners | via global fallback | **explicit tier, labelled as such** |
| Explanation faithfulness | popularity only | **routes by what it actually used** |

The difference in accuracy (0.0021) is far inside the noise band established in
§7. Where accuracy cannot distinguish two options, coverage, transparency and
honest cold-start handling should — and those are the criteria CLAUDE.md §15 and
§16 actually care about. This is recorded as a **recommendation to Phase 4**, not
a reversal of the pre-registered selection: the selection stands, and the
deployment choice is a separate, documented decision.
