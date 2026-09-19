# Recommendation Error Analysis

**Phase:** 3B, Step 11 · **Date:** 19 September 2026
**Method analysed:** `cluster_popularity` (the method selected by the pre-registered rule)
**Population:** 791 evaluable learners, test window (≥ 2025-10-18)
**Source:** `artifacts/recommendation/error_analysis.csv` · `artifacts/recommendation/recommendation_results.json`

---

## 0. What this analysis can and cannot establish

The selected method achieves **Hit Rate@10 = 0.359** — it places at least one of a
learner's next courses in the top ten for 36% of learners. Random achieves 0.346
on the same population.

So this is not an analysis of *why a good model fails on hard cases*. It is an
analysis of **what distinguishes the learners it happens to get right from the
ones it does not**, on a dataset where no method beats chance. Read that way it is
still useful: it identifies which of the usual failure modes are actually present,
which are absent, and which are arithmetic rather than modelling problems.

Every claim below is a property of the *evaluation*, not a demonstrated causal
mechanism.

---

## 1. Sparse history

| Tier | n | Mean history | Mean targets | Hit Rate@10 |
| --- | --- | --- | --- | --- |
| minimal (1 interaction) | 213 | 1.00 | 1.11 | **0.244** |
| moderate (2–8) | 193 | 3.66 | 2.09 | 0.326 |
| rich (≥9) | 385 | 11.01 | 2.56 | **0.439** |

Hit rate rises monotonically with history, which looks like the expected
"personalisation needs data" story.

**It is not.** The confound is visible once the same learners are grouped by how
many courses were held out rather than by how many they had seen:

| Held-out courses | Learners | Hit Rate@10 |
| --- | --- | --- |
| 1 | 405 | **0.207** |
| 2 | 155 | 0.381 |
| 3 | 103 | 0.573 |
| 4 | 65 | 0.569 |
| 5 | 44 | 0.659 |
| 6 | 13 | **0.846** |

A learner with six held-out courses has six chances to be hit in ten slots; a
learner with one has one. Rich-tier learners average 2.56 targets against the
minimal tier's 1.11, which accounts for most of the apparent gap.

**The controlled comparison removes it entirely.** Paired against random *within*
each tier:

| Tier | Δ NDCG@10 vs random | 95% CI | Significant? |
| --- | --- | --- | --- |
| minimal | +0.0307 | [−0.0076, +0.0687] | no |
| moderate | −0.0112 | [−0.0463, +0.0229] | no |
| rich | +0.0079 | [−0.0165, +0.0342] | no |

**Sparse history is not the reason recommendations miss.** The method is no better
than chance for learners with eleven interactions than for learners with one.

> This is worth stating precisely because "the cold-start problem" is the ready
> explanation for weak recommender results, and here it is the wrong one. The
> method does not underperform on sparse learners; it underperforms everywhere,
> equally.

---

## 2. Popular-course bias

Courses ranked 0 (most enrolled) to 59 (least):

| Measure | Mean popularity rank |
| --- | --- |
| Courses the method **recommends** | **16.8** |
| Courses learners **actually took** | **28.6** |
| Catalogue midpoint | 30.0 |
| Targets of learners it **hit** | 23.3 |
| Targets of learners it **missed** | 31.5 |

The method recommends courses roughly in the **top quartile** of popularity, while
learners' actual next courses sit essentially at the **catalogue median**. This is
the popularity-bias failure mode [R29] in its clearest form.

It also explains the hit/miss split: the method succeeds when a learner's next
course happens to be popular (mean rank 23.3) and fails when it is not (31.5). The
model is not discriminating between learners — it is discriminating between
courses, and only in one direction.

**Coverage confirms it.** `cluster_popularity` ever recommends only **75%** of the
catalogue (Gini 0.606); global popularity reaches **32%** (Gini 0.807). Fifteen of
sixty courses are never recommended to anyone by the selected method.

**Why this bias buys nothing here.** Phase 2 established that course popularity is
near-uniform: enrollments range 140–196, Gini 0.042, and a chi-square test against
uniform does not reject (p = 0.60). Concentrating on "popular" courses therefore
concentrates on a distinction that barely exists — all the cost of popularity bias,
none of the usual accuracy compensation.

---

## 3. Category mismatch

| Condition | Learners | Hit Rate@10 |
| --- | --- | --- |
| Learner's history category overlaps a target category | 429 | **0.443** |
| It does not | 362 | **0.260** |

Learners who return to a category they have already taken are **70% more likely**
to be hit.

**This is a property of the learner, not a lever for the model.** Whether a
learner's next course shares a category with their history is unknown at
prediction time — it is part of the answer, not part of the input. The method
cannot use it, and a content-based recommender that assumed category persistence
would be betting on a coin-flip: Phase 2's permutation test found category
concentration statistically indistinguishable from popularity-weighted chance
(mean distinct categories 2.577 observed vs 2.587 null, z = −1.17).

It does explain the shape of the errors: roughly 46% of evaluable learners jump to
a category they have never touched, and no content or preference signal can
anticipate that.

---

## 4. Level mismatch

Phase 3A found the segmentation to be essentially a **course-level split** — three
of four clusters are 100% one level. Since `cluster_popularity` recommends within
segment, it effectively recommends within a level.

That is a liability rather than an asset here. Phase 2 measured level choice as
near-random: the permutation test gave z = −2.65, at the Bonferroni boundary across
eight tests and amounting to 0.03 levels out of 2.2 — and there is **no level
progression** over time (within-learner slope +0.0053, p = 0.664).

So the method's dominant structuring principle predicts a dimension learners do not
follow. It is the clearest single explanation for why segment-aware recommendation
gains nothing over random: the segments are defined by an attribute that does not
govern the next choice.

---

## 5. Cold start

| Population | Learners | Handling |
| --- | --- | --- |
| Zero training-window history | **350 (11.7%)** | Popularity fallback; excluded from personalised evaluation (§12) |
| One interaction | 1,514 (50.5%) | Content anchor + cluster popularity |
| Evaluable but minimal-tier | 213 | Hit Rate 0.244 |

Cold start is **handled, not solved**. No learner is left without a
recommendation, and the 350 with no history are routed to a fallback that is
labelled as such rather than presented as personalisation.

The system degrades gracefully: `test_unknown_user_still_receives_recommendations`
asserts that an unseen learner ID produces finite scores across the full catalogue
rather than raising.

---

## 6. Limited candidate pool

| Measure | Value |
| --- | --- |
| Mean candidate pool | 53.5 of 60 |
| Minimum | 45 |
| Maximum | 59 |
| Learners with a pool smaller than K=10 | **0** |
| Learners with an empty pool | **0** |

**Not a failure mode here** — but it was a live risk worth checking. With a
60-course catalogue, a learner who had taken 51+ courses could not be given a full
top-10. The most active learner in the test window has taken 15, leaving 45
candidates, so the pool never binds.

This is, however, the reason a headline accuracy number is misleading on this
dataset: recommending 10 of ~53 candidates means a random ranker hits roughly
10/53 ≈ 19% of the time per target. The random baseline is doing most of the work
any method appears to do.

---

## 7. Unusual learner behaviour

| Pattern | Prevalence | Effect |
| --- | --- | --- |
| Jumps to an entirely new category | ~46% of evaluable learners | Hit rate falls from 0.443 to 0.260 |
| Targets in the unpopular half of the catalogue | miss group mean rank 31.5 | Systematically missed by a popularity-biased ranker |
| Single-target learners | 405 of 791 (51%) | Hit rate 0.207 — one chance in ten slots |
| Six-target learners | 13 | Hit rate 0.846 — six chances in ten slots |

The last two rows are the same phenomenon as §1 and are listed again because they
are easy to misread as a behavioural finding. They are arithmetic.

---

## 8. What the analysis rules out

As valuable as what it finds:

| Candidate explanation | Verdict |
| --- | --- |
| Sparse history | **Ruled out** — no tier beats random; the method is equally chance-level at 1 and 11 interactions |
| Limited candidate pool | **Ruled out** — every learner has ≥45 candidates |
| Cold start | **Ruled out as a cause of the aggregate result** — the 350 zero-history learners are excluded from personalised evaluation entirely |
| Leakage inflating or deflating results | **Ruled out** — all six controls pass at both stages, and the checker is verified able to fail |
| A bug in the metrics | **Ruled out** — metrics are unit-tested against hand-computed rankings with known answers |
| Popularity bias | **Present**, and costly without compensation |
| Level-based segmentation predicting a near-random dimension | **Present**, and the most likely single explanation |
| **No signal in the data to find** | **The root cause** — established independently in Phase 2 before any recommender existed |

---

## 9. What would change these conclusions

| Change | Expected effect |
| --- | --- |
| **Real (non-synthetic) EduPro data** | The only change that could plausibly alter the headline. Every component here is tested and would transfer unchanged |
| A larger catalogue | Would make the random baseline weak again and give ranking metrics room to discriminate |
| Repeat enrollments, or completion/progress data | Would supply the confidence weighting and outcome signal this dataset lacks entirely |
| Impression logs | Would remove the missing-not-at-random problem (threat V1) — currently a non-enrollment cannot be distinguished from a course never shown |
| More history per learner | Would help only if the extra interactions carried preference signal; Phase 2 found the rich cohort's choices no less random than the light cohort's |

---

## 10. Recommendations carried into Phase 4 and 5

1. **Ship the tiered recommender rather than bare `cluster_popularity`**, despite
   ranking 0.0021 NDCG lower — a difference far inside the noise band. It reaches
   **100% catalogue coverage** against 75%, routes zero-history learners to an
   explicitly labelled fallback, and explains itself by the signal it actually
   used. Where accuracy cannot distinguish two options, coverage and honesty
   should. Recorded as a Phase 4 decision, not a reversal of the pre-registered
   selection.
2. **Display the random reference in the dashboard's evaluation panel.** A
   stakeholder reading "Hit Rate 36%" without "random achieves 35%" would be
   misled, and §6 does not permit that.
3. **Label the minimal and insufficient tiers in the UI.** A learner with one
   interaction should be told the recommendation is content- or popularity-based,
   not given a personalisation narrative the model cannot support (§16, [R32]).
4. **Cap the popularity weighting or add an explicit diversity term** if coverage
   matters to EduPro. The selected method leaves 15 courses permanently
   unrecommended for no accuracy gain.
5. **Monitor the gender gap on real data.** Nominally significant here
   (−0.0283, CI [−0.0543, −0.0010]) and consistent in direction across tiers,
   but uncorrected for multiple comparisons, in a system that uses no demographic
   feature, on a dataset where nothing beats chance. It warrants monitoring, not a
   finding of discrimination.
