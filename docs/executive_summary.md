# EduPro — Learner Segmentation and Course Recommendation

## Executive Summary

**Prepared for:** EduPro management, education administrators, government stakeholders and programme reviewers
**Date:** 20 September 2026
**Technical detail:** `docs/research_paper.md` · **Live dashboard:** `app/streamlit_app.py`

---

## The short version

We were asked to build two things for EduPro: a way to group learners into useful
types, and a way to recommend the right next course to each learner.

**We built both, tested them properly, and found one works and one does not — yet.**

| | Verdict |
| --- | --- |
| **Learner segmentation** | ✅ **Works and is usable today.** Four learner types, each stable and clearly different from the others. |
| **Course recommendations** | ⚠️ **Built, tested, and honest about its limits.** On EduPro's current data it does **not** perform better than picking courses at random. |

That second line is the most important sentence in this document, so we have put it
near the top rather than in a footnote.

**This is not a failure of the software.** It is a finding about the data. EduPro
currently records *which course a learner signed up for* and nothing about what
happened next — no completion, no progress, no time spent, no rating given by the
learner. There is not enough information in "she signed up for three courses" to
predict what she will want fourth.

**Knowing this now is worth money.** Launching a recommendation engine that looks
impressive and quietly performs no better than chance would cost EduPro engineering
time, learner trust, and the opportunity to fix the real problem. The system is
built, tested and ready. What it needs is better data, and we can say exactly which
data (§13).

---

## 1. The Executive Problem

EduPro has 3,000 learners and 60 courses. Two business questions follow:

1. **Who are our learners?** Not as individuals, but as *types* — groups that
   behave alike and can be served, supported or marketed to as a group.
2. **What should each learner see next?** A catalogue of 60 courses is small enough
   to browse but large enough that a well-chosen shortlist saves a learner time.

Underneath both sits a question that is easy to skip and expensive to skip:
**does EduPro's data actually contain the information needed to answer them?**
Most recommendation projects assume the answer is yes and find out otherwise after
launch. We tested it first.

---

## 2. Why a generic recommendation engine is not enough

Off-the-shelf recommendation tools work well in situations that do not match
EduPro's.

**They assume a big catalogue.** Netflix has tens of thousands of titles; Amazon
has millions. EduPro has 60 courses. With 60 courses, a system that picks ten at
complete random will include the learner's actual next course roughly a third of
the time, purely by luck. **Any recommendation system for EduPro must be measured
against that luck**, or its results will look far better than they are. This single
point is why our results in §7 look modest: we are reporting the truth rather than
the flattering number.

**They assume popular items are much more popular.** Normally a handful of items
dominate, and recommending popular things works. At EduPro, the least popular
course has 140 enrollments and the most popular has 196 — almost flat. Popularity
therefore tells us very little about what any individual wants.

**They assume learners have history.** Most recommendation methods learn from a
learner's past behaviour. **More than half of EduPro's learners have taken exactly
one course.** There is almost nothing to learn from.

**They cannot explain themselves.** Many modern systems produce a ranked list with
no reason attached. For an education platform answerable to learners, administrators
and possibly regulators, "the algorithm decided" is not an acceptable answer. Our
system gives a plain-language reason for every course it suggests.

---

## 3. What data was analysed

We analysed EduPro's complete enrollment record.

| What | Amount |
| --- | --- |
| Learners | 3,000 |
| Courses | 60 (twelve subject areas, five courses each) |
| Enrollments | 10,000 |
| Time covered | January to December 2025 |
| Instructors | 60 |

**The data is clean.** We ran twelve families of quality checks and found **zero
errors** — no missing values, no broken links between records, no invalid entries.
This is unusually good, and it means none of our findings are explained by messy
data.

**Three facts about the data shaped everything we built:**

| Fact | Why it matters |
| --- | --- |
| **54% of learners took exactly one course** (1,620 of 3,000) | For most learners there is no pattern to personalise from |
| **15% of learners account for 61% of enrollments** | A small, highly active group drives most activity |
| **No course is much more popular than any other** (140–196 enrollments each) | "Popular courses" is a weak recommendation strategy here |

**One important caveat about the data itself.** Several patterns suggest this
dataset may have been generated for testing rather than collected from real
learners: there are no missing values anywhere, exactly five courses in every
subject area, and learner ages spread perfectly evenly. We flag this because it
affects how much the findings should be treated as facts about real EduPro learners
as opposed to facts about this particular file.

---

## 4. What learner types were discovered

The system found **four learner types**. Each one is stable — meaning if we re-run
the analysis on a different sample of learners, the same four groups reappear. That
reliability was a requirement, not an afterthought: a "learner type" that changes
every time you look at it is not something a business can act on.

| Learner type | How many | Courses taken | Subject areas | Active period |
| --- | --- | --- | --- | --- |
| **Advanced-level browsers** | 1,030 (34%) | 1.6 | 1.6 | 62 days |
| **Beginner-level starters** | 841 (28%) | 1.5 | 1.5 | 46 days |
| **Intermediate one-session learners** | 607 (20%) | 1.4 | 1.3 | 29 days |
| **Committed multi-course learners** | **522 (17%)** | **12.0** | **7.8** | **296 days** |

**The names were not chosen by us.** They are generated automatically from what
actually distinguishes each group, using only the information the model was given.
This prevents the common failure where a group gets an appealing label — "the
ambitious learners" — that the data does not support.

### The one group worth acting on today

**Committed multi-course learners** — 522 people, 17% of the base — are genuinely
different from everyone else and not by a small margin:

- They take **12 courses** on average against roughly 1.5 for everyone else.
- They stay active for **nearly ten months**, against one to two months.
- They explore **8 of the 12 subject areas**.

This group is identifiable, durable, and behaviourally distinct. **They are a
sensible target for retention work, advanced-catalogue development, or a loyalty
programme.**

### Being straight about the other three

The other three groups are real and stable, but they are mostly separated by **the
level of the single course their members happened to take** — beginner,
intermediate or advanced. They are not personality types or learning styles. They
tell you *what level of material a learner started at*, which is useful but
narrower than the label "learner type" might suggest.

We say this explicitly because it is the kind of thing that gets overstated. A
slide claiming EduPro has discovered "four learner personas" would be going beyond
the evidence.

*(A technical note for reviewers: the research paper reports slightly different
group sizes because it measures on the historical period used for testing, while
these figures use all available data — which is what the live system uses.)*

---

## 5. How personalisation works

The system asks one question first: **how much do we actually know about this
learner?** The answer determines how it responds.

| What we know | What the learner gets | Why |
| --- | --- | --- |
| **Nothing** (brand new) | A broad, well-rated selection spanning 10 of the 12 subject areas | There is no preference to match, so we offer breadth |
| **One course** | Courses similar to that one | One course is enough for a similarity match, not for a behaviour profile |
| **Two to eight courses** | What others in their learner type are choosing | Enough history to place them in a group |
| **Nine or more** | The same, with more confidence | The most informative learners |

**This is deliberate honesty built into the product.** When the system does not know
enough to personalise, it says so in plain words rather than dressing a popular-items
list up as a personal recommendation. A learner with no history is told: *"You are
new here, so these are broad, well-rated and widely taken courses rather than
personalised picks."*

Half of EduPro's learners fall into that honest-degradation category today. A system
that pretended otherwise would be misleading them.

---

## 6. What the recommendation system provides

For any learner, the system produces a ranked shortlist with a reason attached to
each course.

**Every recommendation includes:**

- The course, its subject area, level, rating and price
- **A plain-language reason** — for example: *"127 learners in your segment enrolled
  in this course"*, or *"Matches your learning profile: same category as 1 of your 1
  course (Cybersecurity) and at the Intermediate level you usually choose."*
- Confirmation that the learner has not already taken it

**Guaranteed behaviours:**

| Guarantee | Verified how |
| --- | --- |
| Every learner receives a recommendation | Checked for all 3,000 learners |
| No learner is ever shown a course they already took | Checked for all 3,000 learners — zero failures |
| Every course in the catalogue can be recommended to someone | Coverage measured at 100% |
| Reasons always match what the system actually did | Checked across 30,000 generated explanations |
| Results are fast | 8 milliseconds per learner |

**Administrators also get a dashboard** with seven views: an overview, individual
learner profiles, recommendations, learner-type analysis, a visual map of the
learner base, side-by-side group comparison, and a page showing all the underlying
evidence.

---

## 7. What evidence supports the system — and what it does not

This section is where we ask you to read carefully, because it is where most
project summaries overclaim.

### How we tested

We used only enrollments from before **12 September 2025** to build the system, then
checked whether it could predict what **791 learners** actually enrolled in
afterwards. The system never saw the later data while it was being built. This
mirrors real use: predicting the future from the past.

We compared eleven different recommendation methods — and, critically, we also
measured **what happens if you just pick courses at random.**

### What we found

| Measure | Our system | Picking at random | A popular-courses list |
| --- | --- | --- | --- |
| Learner's actual next course appeared in our top ten | **36 in 100** | **35 in 100** | 33 in 100 |
| Ranking quality score | 0.114 | 0.110 | 0.107 |
| Share of catalogue it can ever recommend | **100%** | 100% | **32%** |

**None of the eleven methods performed better than random selection by an amount we
can distinguish from chance.** Five of them performed *worse* than random.

The third column matters, because a "most popular courses" list is the realistic
alternative EduPro would otherwise build. It is no better at predicting what a
learner takes next — and it can only ever surface **19 of the 60 courses**. Our
system reaches all 60. **That is a real difference, and it is about catalogue
exposure rather than accuracy.**

**What this means in plain terms:** on EduPro's current data, the system's ranking
is not demonstrably better than luck. We are not able to claim it helps learners
find courses faster.

**What it does not mean:** it does not mean the software is broken or badly built.
We predicted this outcome *before* building the recommender, from the data itself —
we measured that learners' course choices are statistically indistinguishable from
random picking weighted by popularity. The system is correctly built; the data does
not yet contain the signal.

### About impact figures

We want to be explicit here, because this is where education-technology claims most
often go wrong.

> **We cannot tell you that this system increases engagement, completion or
> retention. No such measurement exists in EduPro's data.**

EduPro records that a learner signed up for a course. It does not record whether
they opened it, progressed through it, finished it, or liked it. Any claim of the
form "engagement improved by X%" would be invented.

The official project brief asks for an impact measure, so we report one and label it
honestly:

| **Engagement Lift — a PROXY measure, not a business outcome** | |
| --- | --- |
| Our system | 1.084 |
| Picking at random | 1.046 |

This proxy measures whether recommended courses tend to be well-rated ones. It is
**not** a measure of whether any learner enrolled, engaged, completed or benefited.
The gap between 1.084 and 1.046 is small, and we show both numbers together so the
first cannot be quoted without the second.

### What we can say with confidence

| Claim | Confidence |
| --- | --- |
| The four learner types are real and reliably reproducible | **High** — verified by repeated resampling |
| Committed multi-course learners are genuinely distinct | **High** |
| Every learner gets a sensible, explained, non-repeating shortlist | **High** — verified exhaustively |
| The system reaches the entire catalogue rather than pushing the same few courses | **High** |
| The recommendations help learners find better courses | **Not demonstrated** |
| The system improves engagement or completion | **Cannot be measured with current data** |

---

## 8. How learners receive recommendations

Today the system runs as an internal dashboard. An administrator selects a learner
and sees their profile, their assigned type, and their recommended shortlist with
reasons.

**To reach learners directly**, the recommendations would be placed where learners
already are — a "Recommended for you" panel on the EduPro homepage or course
catalogue. The technical work for this is small: the system already produces a
result in 8 milliseconds and can be called by EduPro's website.

**What we would advise showing learners:**

- The shortlist, with the plain-language reason for each course
- The ability to filter by subject area and level
- Clear labelling when the list is a general selection rather than a personal one

**What we would advise against**, at least until the evidence supports it: presenting
these as confident personal predictions ("courses you'll love"). On current evidence
that language would overstate what the system does.

---

## 9. How the system supports platform decisions

Even with the recommendation limitation, three capabilities are usable now.

**9.1 Understanding the learner base.** EduPro can see, at any time, how many
learners fall into each type and how they differ across a dozen behaviours. This
supports capacity planning, communication targeting and catalogue decisions.

**9.2 Identifying the committed minority.** 522 learners take 12 courses each and
stay active for ten months. Retaining them is worth more than acquiring several
times that number of one-course learners. The system identifies them by name — or
rather, by anonymous ID — automatically.

**9.3 Diagnosing the catalogue.** The analysis surfaced findings EduPro can act on
independently of any recommender:

| Finding | What EduPro might consider |
| --- | --- |
| No course is much more popular than any other | Either the catalogue is well balanced, or learners are not discovering differences between courses |
| Learners do not progress from beginner to advanced over time | There may be no clear pathway between levels — a curriculum question, not a technology one |
| Learners strongly prefer instructors they have used before | Instructor continuity may matter more than the catalogue currently reflects |
| The system is almost blind to learners moving between levels | Level transitions are the moment learners most need guidance, and neither the data nor the model supports them today |

**9.4 A reusable measurement capability.** The testing approach built here — measuring
against random selection, checking for hidden data leaks, verifying explanations —
can be reapplied to any future EduPro model. This is arguably the most durable
deliverable: EduPro now has a way to tell whether its next model works.

---

## 10. Privacy

Privacy was designed in rather than added afterwards.

**Names and email addresses are removed at the moment the data is read.** They are
not filtered out later, not hidden in the interface — they are simply never loaded.
Nothing downstream can accidentally expose them, because nothing downstream has
them.

| Measure | Status |
| --- | --- |
| Learner names and emails used anywhere in the model | **Never** — removed at the point of loading |
| Learner identification in the dashboard | Anonymous IDs only (e.g. `U00001`) |
| Age and gender used to decide recommendations | **No** |
| Age and gender visible to administrators | Yes — as part of the normal learner record |

**We verified this by trying to break it.** We deliberately loaded the personal data,
took 119 real names and email addresses, and searched every file the system produces
— 97 files in total. **Zero occurrences.** Searching for the column heading would
have been easy to pass; searching for the actual values is the real test.

**On age and gender.** We tested whether including them improved the learner
grouping. It made **no difference whatsoever** — the groups came out identical. They
are therefore excluded from the model entirely. We keep them for one purpose: checking
whether the system treats different groups of learners differently. That check
currently shows a small difference between female and male learners in ranking
quality (0.100 against 0.129). We report it rather than hide it. It is small, it is
measured on a system that performs at chance level anyway, and it uses no
demographic information — but it is the kind of thing that should be watched once
real data is available.

---

## 11. Limitations

Stated plainly, in order of importance.

1. **The recommendations are not demonstrably better than random selection.** This
   is the central limitation and we have not softened it anywhere in this document.
2. **We cannot measure engagement, completion or learning outcomes.** EduPro does
   not record them. Any such claim would be fabricated.
3. **The dataset may not be real.** Several patterns suggest it was generated for
   testing. Findings should be treated as provisional until confirmed on live data.
4. **Three of the four learner types are mainly course-level groupings**, not rich
   behavioural personas (§4).
5. **The system cannot help learners move between levels.** When a learner's next
   course is at a level they have not tried before, the system almost never predicts
   it correctly.
6. **The system slightly favours popular courses** over the less popular ones
   learners actually choose.
7. **A small gender difference in ranking quality is under observation** (§10).
8. **No live trial has been run.** Everything here is measured on historical records.
   Only a real trial with real learners can establish real impact.

---

## 12. Implementation roadmap

The system is built and tested. This roadmap is about deployment and about fixing
the data problem — not about further model development, which would be premature.

### Phase 1 — Deploy internally (ready now)

| Step | Effort |
| --- | --- |
| Publish the dashboard for EduPro administrators | Small — it runs today |
| Train staff on reading learner types and recommendations | Half a day |
| Begin using the committed-learner group for retention work | Business decision |

**Cost:** minimal. No new infrastructure, no ongoing licence.

### Phase 2 — Start collecting the missing data (the critical step)

This is the step that determines whether EduPro ever gets useful recommendations.

| Data to capture | Why it matters |
| --- | --- |
| **Course completion and progress** | Distinguishes a course someone finished from one they abandoned |
| **Time spent** | The clearest signal of genuine engagement |
| **Learner ratings and reviews** | Direct preference information — currently absent |
| **What learners were shown but did not choose** | Lets us learn from rejections, not just selections |
| **Repeat or continued activity** | Enables methods that are currently impossible |

**Estimated effort:** platform instrumentation work, measured in weeks rather than
months. **This is the highest-value item in this document.**

### Phase 3 — Re-measure (three to six months after Phase 2)

Re-run the same analysis on the richer data. The entire testing framework already
exists and is automated. If the signal has appeared, the recommendation system
becomes genuinely useful with no redesign.

### Phase 4 — Learner-facing rollout (only if Phase 3 succeeds)

Place recommendations in front of learners, with a controlled trial — some learners
see recommendations, some do not — so that impact can be *measured* rather than
assumed.

**We recommend against Phase 4 before Phase 3 passes.** Rolling out recommendations
that perform at chance level risks learner trust for no gain.

---

## 13. Future expansion

Beyond the roadmap, four directions are worth considering once the data supports
them.

**Learning pathways.** The analysis found learners do not naturally progress from
beginner to advanced. Designing explicit pathways — and recommending the *next step*
rather than the *next course* — would address the system's clearest weakness (§11.5)
and is as much a curriculum question as a technical one.

**Instructor-aware recommendations.** Learners return to instructors they have used
before far more than chance would predict. This is the strongest genuine behavioural
signal in the data. It is not precise enough to predict a specific course today, but
with richer data it may become useful.

**Real-time recommendations.** The system is fast enough to respond live as a learner
browses. This requires only integration work.

**Wider application.** The measurement framework — testing against random, checking
for data leaks, verifying explanations — applies to any model EduPro builds. It is
not specific to recommendations.

---

## In summary

**What EduPro gets today:** a reliable, explainable way to understand its learner
base, a clearly identified group of committed learners worth investing in, a tested
and deployable recommendation system, and an honest measurement of what that system
can and cannot do.

**What EduPro does not get today:** a recommendation engine proven to help learners.
That requires data EduPro does not yet collect.

**What we would do next, if it were our decision:** deploy the dashboard internally
this month, start recording course completion and time spent immediately, and
re-measure in six months. The system is ready and waiting for the data.

---

### About this summary

Every figure in this document comes from an automated analysis of EduPro's data and
can be traced to a specific result file. Nothing is estimated, projected or
illustrative. The technical detail sits in `docs/research_paper.md`; the complete
validation record is in `research/final_validation_report.md`.

Where a number is a **proxy** — a stand-in for something we cannot measure directly
— it is labelled as such in the text above.
