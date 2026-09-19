# Literature Review

**Phase:** 1 — dense research and methodology investigation
**Date:** 19 September 2026
**Scope:** the eight areas required by the Phase 1 brief, read against the actual
constraints of the EduPro dataset.

---

## How to read this document

Two kinds of statement appear here, and they are never mixed:

**Published evidence** is written as ordinary prose and **always carries a
citation key** — `[R13]`, `[R24]`, and so on, resolving in §10. Every such
statement is a summary, in my own words, of something a cited source establishes.
No long passages are reproduced from any source.

**Engineering inference** is always set in a marked block:

> **[INFERENCE]** — my own reasoning about how the cited evidence applies to
> EduPro, or a deduction from EduPro's own structure. **This is not published
> evidence.** No citation supports the EduPro-specific conclusion, because none
> exists for this dataset. Every such statement must be confirmed or refuted by
> experiment, and `experiment_plan.md` names the experiment that will do so.

So the rule when reading: **a claim with a citation key is published evidence; a
claim inside an `[INFERENCE]` block is mine and is unproven.** Anything with
neither is a statement about this project's own artifacts (file paths, counts from
the Phase 0 inventory) and is verifiable in the repository.

Every reference in §10 was **verified by retrieval during Phase 1** — title,
authors, venue, year and DOI/URL checked against the publisher, DBLP, or the
canonical proceedings. No citation was written from memory alone.

---

## 0. The constraints that make this dataset unusual

Everything below is conditioned on four structural facts established in Phase 0
(`artifacts/phase0_source_inventory.json`). They are stated first because they
disqualify a large part of the recommender-systems literature before it is read.

| Fact | Value | Consequence |
| --- | --- | --- |
| Catalogue size | **60 courses** | Tiny. Most published recsys results assume 10³–10⁶ items. |
| Learners | 3,000 | Users outnumber items 50:1 — the opposite of the usual ratio. |
| Interactions | 10,000, all distinct `(user, course)` pairs | Purely implicit, purely binary. No frequency signal. |
| Mean history | 3.333 courses/learner | Extremely short. |
| Density | 5.56% | Dense *by recsys standards* — MovieLens-20M is ~0.5%. |

> **[INFERENCE] The single most important consequence: a random ranker is a
> strong baseline here.** With 60 items and one held-out course, a uniformly
> random top-10 has a hit rate of ≈0.175 (`scripts/analytical_baselines.py`).
> Any reported Hit Rate@10 below ~0.20 is *worse than guessing*. Published
> recsys papers rarely need to state this because on a 10,000-item catalogue
> random HR@10 is ~0.001 and the comparison is trivial. Here it is not, and
> omitting the random reference from any reported result would be actively
> misleading. This shapes the entire evaluation plan.

> **[INFERENCE] Precision@K is a near-useless headline metric on this data.**
> Under leave-one-out with exactly one held-out course, Precision@10 is
> mathematically capped at 0.10 and Precision@20 at 0.05. The official brief
> requires "Recommendation Precision", so it will be computed and reported — but
> it must be reported against its ceiling, or a perfectly good model will look
> like a failure. Hit Rate@K and NDCG@K carry far more information at this scale.

---

## 1. Learner segmentation

### 1.1 What the clustering literature actually establishes

**K-Means and its initialisation.** Arthur and Vassilvitskii's k-means++ seeding
gives an O(log k) approximation guarantee to the optimal clustering and improves
both speed and solution quality over random initialisation [R09]. This is the
default in scikit-learn, so the project inherits it without extra work — but the
guarantee is *in expectation*, which is why multiple restarts (`n_init`) and a
fixed seed both matter for reproducible results.

**Choosing k is not a solved problem.** Milligan and Cooper's Monte Carlo study
compared 30 stopping rules on synthetic data with known cluster counts and found
they differ substantially in accuracy — no single rule dominates [R06]. The gap
statistic compares within-cluster dispersion against a null reference
distribution, giving a principled alternative to eyeballing a curve [R02]. The
silhouette coefficient scores each point by how much closer it is to its own
cluster than to the nearest other cluster, and averages to a global validity
index [R01].

**The elbow method is the weakest of the standard tools.** Ketchen and Shook, in
a critique of 45 published strategy studies using cluster analysis, found the
methodological choices around cluster analysis were frequently handled poorly and
that this undermined the knowledge those studies produced [R07]. The elbow's
specific weakness is that within-cluster sum of squares decreases monotonically
with k by construction, so the "elbow" is a subjective reading of a curve that
always slopes the same way.

> **[INFERENCE]** The official EduPro brief mandates the elbow method, so it will
> be produced. But it will be reported as *one* input alongside silhouette
> [R01], gap statistic [R02] and stability [R03][R05], and the final k will not
> be justified by the elbow alone. Mandating a method is not the same as
> mandating that it be the sole arbiter, and §6 of CLAUDE.md forbids presenting a
> subjective curve reading as though it were decisive evidence.

**Stability is the check that catches clustering on noise.** Ben-Hur, Elisseeff
and Guyon assess structure by perturbing the dataset and measuring how similar
the resulting partitions are; crucially, the method can detect the *absence* of
structure, not only find an optimum [R04]. Hennig's refinement scores stability
**per cluster** using the bootstrap distribution of the Jaccard coefficient, so
that a partition containing three solid clusters and two artefacts is diagnosed
as such rather than receiving a single averaged verdict [R03]. Von Luxburg's
overview surveys the theory and is explicit that stability-based k-selection is a
heuristic with known failure modes rather than a guaranteed procedure [R05].

> **[INFERENCE]** Hennig's per-cluster Jaccard is the right tool for this
> project, more so than a global stability score. The deliverable is a set of
> *interpretable learner segments* that a stakeholder will act on. If one segment
> is stable at 0.85 and another at 0.45, that difference is a finding the
> executive summary must carry — recommending a strategy for a segment that
> dissolves under resampling would be exactly the kind of unsupported claim §6
> prohibits.

**Hierarchical clustering as validation.** Ward's method merges the pair of
clusters that minimises the increase in total within-cluster variance [R08].

> **[INFERENCE]** Ward and K-Means optimise closely related objectives, so
> agreement between them is weaker evidence than it appears — it partly reflects
> a shared inductive bias. The brief mandates hierarchical clustering as
> validation and it will be run, but average-linkage will be run alongside Ward
> precisely because it optimises something different, and a structure that
> survives *both* is better evidenced than one that survives Ward alone.

### 1.2 Mixed-type features: the central technical problem

The EduPro learner profile is irreducibly mixed: continuous (average spending,
average rating), count (total courses), and categorical (preferred category with
12 levels, preferred level with 3, gender with 2).

**Published approaches.** Gower's general similarity coefficient handles mixed
attribute types by computing a per-variable similarity and averaging with weights
[R11]. Huang's k-prototypes integrates k-means and k-modes with a combined
dissimilarity measure, giving a native mixed-type clustering algorithm [R10].

> **[INFERENCE] This is where the project's biggest methodological risk sits.**
> The obvious approach — one-hot encode `PreferredCategory` and run K-Means on
> everything — is quietly wrong at these cardinalities. One-hot encoding 12
> categories adds 12 binary columns against roughly 8 behavioural columns, so
> *more than half the Euclidean distance budget* is spent on a single
> conceptual variable. K-Means would then substantially be clustering on
> preferred category, and the resulting "segments" would largely recapitulate the
> category taxonomy the platform already knows.
>
> Three candidate mitigations, to be decided by experiment (EXP-011a), not by
> preference:
> 1. **Proportion vector instead of one-hot.** Represent category preference as
>    the learner's 12-dimensional distribution across categories. Same
>    dimensionality, but it carries the full preference shape rather than only
>    the argmax — and it is what "average courses per category" and "diversity
>    score" are already gesturing at.
> 2. **Gower distance [R11] with explicit weights**, clustered via a
>    distance-based method. Makes the weighting a visible, defensible choice
>    rather than an accident of encoding.
> 3. **k-prototypes [R10]**, keeping categoricals native.
>
> Whichever wins, the **feature-dominance diagnostic is mandatory**: measure how
> much of the between-cluster variance each feature block explains. CLAUDE.md §10
> demands this for demographics; the same logic applies to any block that can
> swamp the distance metric.

### 1.3 Learner segmentation in education specifically

Kizilcec, Piech and Schneider clustered longitudinal engagement trajectories
across three computer-science MOOCs and consistently recovered four prototypical
patterns — described as completing, auditing, disengaging and sampling [R12].
The finding that matters methodologically is the *consistency* across three
independent courses, which is stability evidence of the kind [R03] formalises.

> **[INFERENCE]** [R12] is the closest published analogue to this project's
> segmentation task, and it is instructive about what to expect and what not to
> import. What transfers: the finding that a small k (≈4) produced interpretable,
> recurring learner types, and the practice of validating across independent
> subsets. What does **not** transfer: their features are longitudinal
> within-course engagement traces (video views, assessment submissions over
> time), and EduPro has nothing comparable — only enrollment transactions. Their
> four labels must therefore **not** be borrowed as expected EduPro segments.
> Adopting "auditing/completing/sampling" as EduPro segment names without
> completion data would be fabricating a finding. Segment names must be derived
> from EduPro's own cluster profiles.

Urdaneta-Ponte, Mendez-Zorrilla and Oleagordia-Ruiz's systematic review of
educational recommender systems surveys the field's approaches and the elements
being recommended [R39], and is the best single entry point to the education-
specific recommender literature.

---

## 2. Recommender systems

### 2.1 Popularity is not a strawman baseline

**Published evidence.** Cremonesi, Koren and Turrin showed that algorithms tuned
to minimise RMSE do not necessarily perform well on top-N recommendation, and
that simple non-personalised baselines are more competitive on top-N tasks than
the error-metric literature implied [R20]. Cañamares and Castells analysed
probabilistically *when* popularity is an effective signal rather than merely a
bias, identifying conditions under which it genuinely predicts relevance [R28].

Ferrari Dacrema, Cremonesi and Jannach attempted to reproduce 18 neural
recommendation papers, could reproduce only 7, and found that most of those were
outperformed by properly-tuned simple baselines — nearest-neighbour and
graph-based methods [R26]. Their diagnosis includes weak baselines and the
propagation of weak methods as new baselines.

> **[INFERENCE]** [R26] is the single most important paper for this project's
> *process*, not its algorithms. It is direct published evidence that
> insufficiently-tuned baselines are how recommender research goes wrong. On a
> 60-item catalogue, popularity is likely to be a genuinely hard baseline to
> beat — a handful of courses plausibly absorb a large share of 10,000
> enrollments. CLAUDE.md §13 already requires popularity as a baseline; [R26]
> says it must be *tuned as carefully as the proposed method*, and that "the
> hybrid beat popularity" is only a finding if popularity was given a fair run.
>
> The honest possible outcome — that popularity or a simple item-kNN wins — must
> be reportable. §6 forbids hiding it, and [R26] shows it is the common case.

**The counterweight.** Popularity bias is a real harm: Abdollahpouri, Mansoury,
Burke and Mobasher analyse how it under-exposes less popular items and
disadvantages users whose tastes lie outside the mainstream [R29]. Ge,
Delgado-Battenfeld and Jannach argue for evaluating beyond accuracy, using
coverage and serendipity [R27].

> **[INFERENCE]** With 60 courses, catalogue coverage is both critical and
> cheaply measurable. A recommender that achieves a good hit rate by routing
> every learner to the same 8 courses has failed EduPro's actual business goal —
> the brief's stated aim is helping learners *discover relevant content*. Coverage
> will therefore be a **first-class reported metric**, not an afterthought, and
> the Phase 3 selection rule (see `experiment_plan.md`) treats a coverage
> collapse as disqualifying rather than as a footnote.

### 2.2 Content-based filtering

Lops, de Gemmis and Semeraro survey content-based recommenders, their
representation techniques and their characteristic limitations — notably
over-specialisation and limited serendipity [R18].

> **[INFERENCE]** EduPro's content signal is unusually thin but unusually clean:
> every course has `CourseCategory` (12), `CourseType` (2), `CourseLevel` (3),
> `CourseRating`, and — pending the Q-3 decision — `CoursePrice` and
> `CourseDuration`. There is no text to embed: `CourseName` is a short label with
> two repeats across 60 courses, so TF-IDF over names would be near-degenerate
> and is not worth attempting. A low-dimensional categorical feature vector with
> explicit similarity is the appropriate representation, and it has a real
> advantage here — it is directly explainable, which §16 requires.
>
> The over-specialisation risk in [R18] is acute at this scale: with 12
> categories and a mean history of 3.3 courses, a pure content recommender will
> tend to return the learner's own category repeatedly. This is precisely what
> the diversity/coverage metrics must catch.

### 2.3 Collaborative and learner-similarity approaches

Sarwar, Karypis, Konstan and Riedl introduced item-based collaborative filtering,
computing item-item similarity rather than user-user [R15]. Deshpande and Karypis
developed item-based top-N algorithms and reported them to be up to two orders of
magnitude faster than user-neighbourhood methods [R16].

> **[INFERENCE] Item-based CF is unusually well-suited to EduPro, for a reason
> specific to its shape.** The item-item similarity matrix is 60×60 — 3,600
> entries, computable instantly and cacheable entirely in memory. The user-user
> matrix would be 3,000×3,000 = 9M entries. More importantly, each item has on
> average 10,000/60 ≈ 167 interactions, so item-item co-occurrence statistics are
> reasonably well-estimated, whereas each *user* has only ~3.3 interactions, so
> user-user similarity is estimated from almost nothing.
>
> This is worth stating plainly because the official brief asks for "similar
> learner profiles" — a user-based framing. **Both will be implemented and
> compared** (the brief's requirement is met), but the prior expectation is that
> item-based is better-conditioned on this data, and the user-similarity variant
> may be better computed over *profile features* (the learner's engineered
> feature vector) than over the 3.3-interaction history vector. That distinction
> is itself an experiment: EXP-022a vs EXP-022b.

### 2.4 Implicit feedback

Hu, Koren and Volinsky formalised implicit-feedback CF by distinguishing
*preference* (binary: did the interaction happen) from *confidence* (how strongly
the observed signal supports that preference), typically scaling confidence with
interaction frequency [R13]. Rendle et al.'s BPR optimises a pairwise ranking
criterion derived from a Bayesian treatment, learning from (user, positive item,
sampled negative item) triples [R14].

> **[INFERENCE] The confidence half of [R13] does not apply to EduPro.** Their
> confidence weighting derives from repeated observations — play counts, repeat
> views. EduPro has **zero repeat `(user, course)` pairs** (Phase 0, verified).
> Every observation has identical multiplicity, so any confidence function is
> constant and the model degenerates to weighted binary matrix factorisation.
> The *preference/confidence distinction* remains conceptually useful — absence
> of an enrollment is not evidence of dislike — but the mechanism does not
> transfer. Implementing [R13]'s weighting scheme and reporting it as such would
> misrepresent what the model is doing.
>
> **BPR [R14] is also a poor fit, on sample-size grounds.** BPR learns latent
> factors from sampled triples; with 10,000 positives and 60 items, a
> conventionally-sized factor model has more parameters than the data can
> identify. [R26]'s finding that tuned simple baselines beat neural methods on
> small data reinforces this. BPR is therefore **not** in the Phase 3 baseline
> set — and this exclusion is recorded as a reasoned decision with its rationale,
> not a silent omission. It can be revisited if Phase 2 reveals more usable
> signal than expected.

### 2.5 Hybrid recommendation

Burke's survey taxonomises hybridisation strategies — weighted, switching,
mixed, feature combination, cascade, feature augmentation and meta-level — and
demonstrates a knowledge-based/collaborative hybrid [R17].

> **[INFERENCE]** Burke's taxonomy maps directly onto CLAUDE.md's two distinct
> requirements, and separating them clarifies the design:
> - **§14 (hybrid scoring)** is a *weighted* hybrid — combine content, similarity,
>   cluster-popularity and rating relevance into one score.
> - **§15 (sparse-history tiers)** is a *switching* hybrid — choose a different
>   recommender depending on how much history the learner has.
>
> These are independent axes and the project needs both. Recognising them as two
> named strategies rather than one bespoke mechanism means each can be evaluated
> separately: the weighted combination by ablation, the switching policy by
> per-tier evaluation. §14's prohibition on arbitrary weights is satisfied by
> tuning the weighted component on a validation split and reporting the ablation
> — never by choosing round numbers that "seem reasonable".

### 2.6 Cold start

Schein, Popescul, Ungar and Pennock combined content and collaborative signals in
a single probabilistic framework and — as important — argued that cold-start
performance requires its own metrics rather than being folded into an aggregate
[R19].

> **[INFERENCE]** EduPro has **no item cold start**: all 60 courses appear in the
> transaction data, so every item has history. The cold-start problem here is
> purely *user*-side, and it is severe: at a mean of 3.333 interactions, a
> substantial share of learners will have 1–2. [R19]'s methodological point —
> evaluate cold-start users separately — is exactly what CLAUDE.md §12
> independently requires. This convergence between the published methodology and
> the project standard is the strongest available justification for the tiered
> evaluation design in `recommendation_evaluation_plan.md`.

---

## 3. Evaluation

### 3.1 The foundational sources

Herlocker, Konstan, Terveen and Riedl's survey remains the reference treatment of
what CF evaluation decisions exist and how they interact — task, dataset, metric
and analysis choices [R21]. Shani and Gunawardana's handbook chapter covers
offline, online and user-study protocols and the conditions each supports [R22].
Järvelin and Kekäläinen introduced cumulated gain measures, including the
discounted and normalised forms (DCG/NDCG), which reward placing relevant items
higher in the ranking [R23].

### 3.2 Temporal splitting and leakage — the critical area

**Splitting strategy changes conclusions, not just numbers.** Meng, McCreadie,
Macdonald and Ounis showed empirically that the data-splitting strategy is a
confounding variable that can **markedly alter the relative ranking of
recommender systems**, making much published literature non-comparable even when
dataset and metrics match [R24].

**Ignoring the global timeline is leakage.** Ji, Sun, Zhang and Li studied
leakage caused by splits that do not respect a global timeline — where a model
trains on interactions that would not have existed at prediction time. Across
four models and four datasets they found leakage affects accuracy and that
*relative performance orderings become unpredictable* with differing amounts of
leaked future data. They propose evaluating against a global timeline [R25].

> **[INFERENCE] These two papers jointly determine this project's evaluation
> design, and the distinction they expose is subtle enough to be worth stating
> explicitly.**
>
> The conventional leave-one-out protocol holds out *each user's own* most recent
> interaction. Each user's split point is a different calendar date. So when
> predicting user A's held-out course dated March, the training set legitimately
> contains user B's interactions from June — future information relative to the
> prediction being made. This is the leakage [R25] identifies, and it is present
> in a protocol most practitioners consider standard.
>
> The alternative, a **global temporal split** at a single calendar date, is
> leakage-free by construction but costly here: with 3.333 interactions per
> learner, a global cut leaves many learners with zero training history on one
> side and nothing to evaluate on the other.
>
> **Resolution: run both, report both, pre-register the primary.** The global
> split is the primary protocol because it is the one that is defensible under
> [R25]. Per-user leave-one-out is reported as a secondary, explicitly labelled
> as leakage-bearing, precisely because it is what most comparable work does and
> omitting it would make this project incomparable. If the two disagree on method
> *ranking*, that disagreement is itself a finding worth reporting — it is [R24]'s
> result reproduced on EduPro. Full protocol in
> `research/recommendation_evaluation_plan.md`.

### 3.3 Beyond accuracy

Coverage and serendipity as evaluation dimensions are motivated in [R27];
popularity bias and its distributional harms in [R29]. Ekstrand et al.
demonstrated that aggregate effectiveness numbers hide systematic differences in
utility across demographic groups — users of different ages and genders do not
necessarily receive equally good recommendations [R30].

> **[INFERENCE]** [R30] is directly actionable for CLAUDE.md §10 and connects the
> demographics question to the recommendation half of the project. Even if the
> Variant B (behaviour-only) segmentation wins and demographics are excluded from
> the *model*, age and gender are still available as **evaluation strata**. Being
> able to report "recommendation quality is equivalent across gender and across
> age bands" — or to report honestly that it is not — is a stronger and more
> defensible privacy-respecting position than simply not looking. Using a
> protected attribute to *audit* a model is not the same as using it as a feature.

### 3.4 Limitations of offline evaluation

> **[INFERENCE — but constrained by [R21][R22][R25][R26]]** Four limitations bind
> this project, and all four must appear in the research paper's limitations
> section rather than being discovered by a reviewer:
>
> 1. **Missing-not-at-random.** A non-enrollment is not a negative. Learners
>    cannot enroll in what was never shown to them, and no impression data exists.
>    Every "false positive" may be a good recommendation the learner never saw.
> 2. **No counterfactual.** Offline evaluation measures agreement with what
>    learners *did* under EduPro's existing (unknown) recommendation policy. It
>    cannot measure what they *would have* done under ours. This is why the
>    official brief's "Engagement Lift" must stay labelled a **proxy** — §6
>    forbids presenting it as measured impact, and no offline design can fix this.
> 3. **Popularity-biased metrics** [R28][R29] — accuracy metrics reward
>    recommending what is already popular, which is why coverage is co-reported.
> 4. **Splitting sensitivity** [R24][R25] — mitigated by running both protocols,
>    not eliminated.

---

## 4. Explainability

Zhang and Chen's survey organises explainable recommendation by *what* is
explained and *how*, and distinguishes model-intrinsic explanation (the model's
own mechanism is interpretable) from post-hoc explanation (a separate process
generates a justification after the fact) [R31]. Tintarev and Masthoff enumerate
seven distinct aims an explanation can serve — including transparency,
scrutability, trust, effectiveness and persuasiveness — and note these aims can
conflict, so an explanation optimised for persuasion is not the same artifact as
one optimised for transparency [R32].

> **[INFERENCE] CLAUDE.md §16 effectively mandates model-intrinsic explanation,
> and this is a constraint on the *architecture*, not on the UI.** The rule is
> that an explanation must correspond to the signals the recommender actually
> used. A post-hoc explainer can generate a plausible sentence that has nothing to
> do with why the item was ranked where it was — [R31]'s distinction makes that
> failure mode precise. Since the planned hybrid is a *weighted linear
> combination* of named, individually-meaningful components (content match,
> learner similarity, cluster popularity, rating), the per-component
> contributions to the final score are directly available. The explanation can
> therefore be generated from the score decomposition itself.
>
> This has a concrete architectural consequence: **the scorer must return the
> component breakdown, not just the total.** If it returns only a scalar, honest
> explanation becomes impossible after the fact and §16 cannot be satisfied. That
> is a Phase 5 interface requirement, decided here in Phase 1 because retrofitting
> it later would be expensive.
>
> On [R32]'s aims: this project targets **transparency and scrutability**, not
> persuasiveness. An explanation that overstates confidence to drive enrollment
> would violate §6. Concretely, a learner in the minimal-history tier should be
> told the recommendation is popularity-based — not given a fabricated
> personalisation narrative.

---

## 5. Demographic features

Barocas, Hardt and Narayanan's textbook covers the statistical and causal
measures of fairness and the legal and philosophical background to
discrimination [R38]. Ekstrand et al. provide the recommender-specific empirical
finding that effectiveness varies across demographic groups [R30].

> **[INFERENCE] The case for Variant B (behaviour-only) is stronger than the
> symmetry of CLAUDE.md §10 implies, but it must still be decided by experiment.**
>
> Four reasons demographics may harm this segmentation:
> 1. **Scale dominance.** `Age` has 21 distinct values and wide numeric range;
>    after standardisation it competes on equal footing with behavioural features
>    that are the actual subject of the analysis. Gender adds a hard binary split
>    that K-Means will happily use as a cheap variance reduction.
> 2. **Actionability.** EduPro can act on "this learner explores broadly across
>    categories". It cannot act on "this learner is 34". A segment defined by age
>    supports no intervention.
> 3. **Proxy risk** [R38]. A segment that is substantially a gender split, then
>    used to route course recommendations, is a mechanism for differential
>    treatment by gender regardless of intent.
> 4. **The official brief lists Age and Gender as available fields, not as
>    required clustering features.** Its own feature-engineering section is
>    dominated by engagement, preference and behavioural features.
>
> Counter-consideration, stated so the experiment is not rigged: if age genuinely
> correlates with learning-depth preference, excluding it discards real signal and
> produces less useful segments. **The experiment must be able to return that
> answer.** EXP-011 therefore measures cluster quality, stability, behavioural
> consistency, interpretability and feature dominance for both variants, and the
> decision rule is written down *before* the results are seen
> (`experiment_plan.md` §6) so that the outcome cannot be rationalised after the
> fact.
>
> **Privacy.** §17 already bars email from modelling. Beyond compliance: age and
> gender are retained for *evaluation stratification* per [R30] even if excluded
> from features. Auditing with a protected attribute is not the same as modelling
> with it.

---

## 6. Sparse interaction data

There is no single published method for "users with one interaction" — the
literature treats this as the user cold-start problem [R19] and as a
hybridisation/switching problem [R17].

> **[INFERENCE] Tier design for EduPro.** Boundaries are stated as *rules*
> parameterised by the Phase 2 distribution, not as numbers invented now:
>
> | Tier | Condition | Strategy | Why |
> | --- | --- | --- | --- |
> | **Insufficient** | 0 interactions | Popularity + rating + category diversity | Nothing to personalise on. Must be labelled as such in the UI. |
> | **Minimal** | 1 interaction | Content similarity to that one course + cluster popularity | A single course gives a category/level anchor but no reliable preference distribution. |
> | **Moderate** | 2 to *t* | Content + item-similarity + cluster popularity | Enough for a preference shape; too little for stable user-user similarity. |
> | **Rich** | > *t* | Full weighted hybrid | Enough history for all components. |
>
> *t* is set from the Phase 2 percentile distribution (EXP-003), with the
> pre-registered rule: *t* = the smallest history length at which the personalised
> hybrid's validation NDCG@10 exceeds the cluster-popularity recommender's, since
> that is the point at which personalisation starts paying for itself. If no such
> point exists, that is a legitimate and reportable finding — it would mean
> personalisation never beats cluster popularity on this data, and the honest
> system is a simpler one.
>
> **Critically (§12):** tier membership is determined by **training-window history
> only**, never by total history including the held-out interaction. Using total
> history to assign tiers would leak the test interaction's existence into the
> routing decision — a subtle leak that a global-timeline check [R25] would not
> catch, because it hides in the tier assignment rather than in the feature
> matrix.

---

## 7. Production ML

Sculley et al. frame ML systems through technical debt, cataloguing ML-specific
risks: boundary erosion, entanglement, hidden feedback loops, undeclared
consumers, data dependencies and configuration debt [R33]. Breck et al. offer 28
concrete tests and monitoring practices for production readiness, scored as a
rubric [R34].

Engineering documentation: scikit-learn's API and design are described in
[R35]; its model-persistence documentation warns that pickle — and by extension
joblib and cloudpickle — has documented security vulnerabilities by design and
should only be used with artifacts from trusted, verified sources, and notes that
loading a model across scikit-learn versions is unsupported [R36]. Streamlit
documents `st.cache_data` for serializable return values (a copy is returned per
call) and `st.cache_resource` for unserializable global resources such as ML
models and database connections (the same instance is shared) [R37].

> **[INFERENCE]** Four direct consequences for this project:
> 1. **Entanglement / CACE** [R33] — changing the segmentation changes the
>    cluster-popularity recommender's inputs, which changes the hybrid's optimal
>    weights. Segmentation and recommendation artifacts must therefore be
>    versioned and loaded **as a matched set**; a manifest recording which
>    clustering produced which recommender is required, not optional. ADR-0005's
>    separation of stages makes them composable, but composable is not the same as
>    independently swappable.
> 2. **Version-consistency** [R36] — CLAUDE.md §22 requires artifacts consistent
>    with the source code. Since cross-version loading is explicitly unsupported,
>    the artifact manifest must record the scikit-learn, numpy and Python versions
>    used to fit, and loading must verify them and fail loudly on mismatch rather
>    than silently producing wrong numbers.
> 3. **`st.cache_resource` for the model, `st.cache_data` for frames** [R37] —
>    this is exactly the mechanism by which §21's "never retrain on startup" is
>    implemented.
> 4. **Trusted-source caveat** [R36] — the artifacts are built by this repository's
>    own pipeline and committed alongside it, so the trust condition is satisfied.
>    Worth stating in the deployment documentation rather than left implicit.

---

## 8. Teacher-sheet experiment

No published work was found treating instructor attributes as features in a
course recommender on data of this shape; the educational recommender survey
[R39] surveys the field broadly without establishing this specific result.

> **[INFERENCE] What could legitimately contribute, and what could not.**
>
> The `Teachers` sheet holds `TeacherID`, `TeacherName`, `Age`, `Gender`,
> `Expertise` (12 values), `YearsOfExperience`, `TeacherRating`. `Transactions`
> carries `TeacherID` per enrollment.
>
> **Structurally defensible uses:**
> - **`TeacherRating` as an additional quality prior** on a course, alongside
>   `CourseRating` — a rating-weighted relevance term already required by the
>   brief.
> - **`Expertise` as a second content facet.** It has 12 values, as does
>   `CourseCategory`. Whether it carries information *beyond* category is an
>   empirical question — if the two are near-redundant it adds nothing, and Phase
>   2 can measure their association directly before any model is built.
> - **Teacher affinity as a behavioural feature**: does a learner return to the
>   same instructor? This is a genuine personalisation signal if present.
>
> **Structurally indefensible uses:**
> - **Teacher `Age` and `Gender`.** These are demographics of a *third party* who
>   is not the subject of the recommendation. Clustering learners by their
>   instructors' gender, or routing recommendations by it, would be
>   discriminatory allocation with no legitimate rationale [R38]. **Excluded
>   before experimentation**, not tested — some hypotheses should not be run.
> - **`TeacherName`** — PII, excluded under §17 like all other name fields.
>
> **A prerequisite Phase 2 check that determines whether any of this is
> meaningful:** is the `Transactions.TeacherID` → `CourseID` mapping
> one-to-one? With exactly 60 teachers and 60 courses, teacher may be a
> deterministic function of course. **If so, every teacher-derived feature is an
> alias for a course-derived feature and the entire experiment is vacuous** — it
> would add no information while appearing to. That check (EXP-005) must run
> *before* EXP-014, and if it shows a bijection, EXP-014 is cancelled and the
> reason recorded. That would be a clean, publishable negative result and a
> direct answer to CLAUDE.md §11.

---

## 9. What the literature does *not* settle

Recorded explicitly, because CLAUDE.md §4 forbids letting literature substitute
for experiment and the Phase 1 pass criteria require that no algorithm be locked
prematurely.

1. **Which encoding of categorical preferences produces the better segmentation.**
   [R10][R11] give options, not an answer for this data.
2. **The right k.** [R01][R02][R06] give competing criteria that frequently
   disagree.
3. **Whether demographics help or harm.** [R30][R38] establish the risk, not the
   outcome on EduPro.
4. **Which recommender wins.** [R26] is explicit that this must be settled by
   properly-tuned empirical comparison.
5. **Whether clustering improves recommendation at all.** No cited source
   establishes that cluster-aware recommendation beats item-based CF on a
   60-item catalogue. This is genuinely open and is why ADR-0005 made the cluster
   signal ablatable.
6. **Where the tier boundaries fall.** Requires the Phase 2 distribution.
7. **Whether the teacher signal is even non-degenerate.** Requires EXP-005.

**No algorithm is selected in Phase 1.** This review constrains the search space
and designs the experiments; `experiment_plan.md` specifies the experiments that
will decide.

---

## 10. References

All entries verified by retrieval during Phase 1 (19 September 2026). Verification
means the title, authors, venue, year and identifier were confirmed against a
publisher page, DBLP, or the canonical proceedings listing.

### Clustering and segmentation

**[R01]** Rousseeuw, P. J. (1987). Silhouettes: a graphical aid to the
interpretation and validation of cluster analysis. *Journal of Computational and
Applied Mathematics*, 20, 53–65. DOI: [10.1016/0377-0427(87)90125-7](https://doi.org/10.1016/0377-0427(87)90125-7)

**[R02]** Tibshirani, R., Walther, G., & Hastie, T. (2001). Estimating the number
of clusters in a data set via the gap statistic. *Journal of the Royal Statistical
Society: Series B*, 63(2), 411–423. DOI: [10.1111/1467-9868.00293](https://doi.org/10.1111/1467-9868.00293)

**[R03]** Hennig, C. (2007). Cluster-wise assessment of cluster stability.
*Computational Statistics & Data Analysis*, 52(1), 258–271. DOI: [10.1016/j.csda.2006.11.025](https://doi.org/10.1016/j.csda.2006.11.025)

**[R04]** Ben-Hur, A., Elisseeff, A., & Guyon, I. (2002). A stability based method
for discovering structure in clustered data. *Pacific Symposium on Biocomputing*,
6–17. URL: https://psb.stanford.edu/psb-online/proceedings/psb02/benhur.pdf

**[R05]** von Luxburg, U. (2010). Clustering Stability: An Overview. *Foundations
and Trends in Machine Learning*, 2(3), 235–274. DOI: [10.1561/2200000008](https://doi.org/10.1561/2200000008)

**[R06]** Milligan, G. W., & Cooper, M. C. (1985). An examination of procedures
for determining the number of clusters in a data set. *Psychometrika*, 50(2),
159–179. DOI: [10.1007/BF02294245](https://doi.org/10.1007/BF02294245)

**[R07]** Ketchen, D. J., & Shook, C. L. (1996). The application of cluster
analysis in strategic management research: an analysis and critique. *Strategic
Management Journal*, 17(6), 441–458. DOI: [10.1002/(SICI)1097-0266(199606)17:6<441::AID-SMJ819>3.0.CO;2-G](https://doi.org/10.1002/(SICI)1097-0266(199606)17:6<441::AID-SMJ819>3.0.CO;2-G)

**[R08]** Ward, J. H. (1963). Hierarchical Grouping to Optimize an Objective
Function. *Journal of the American Statistical Association*, 58(301), 236–244.
DOI: [10.1080/01621459.1963.10500845](https://doi.org/10.1080/01621459.1963.10500845)

**[R09]** Arthur, D., & Vassilvitskii, S. (2007). k-means++: The Advantages of
Careful Seeding. *SODA '07*, 1027–1035. URL: https://theory.stanford.edu/~sergei/papers/kMeansPP-soda.pdf

**[R10]** Huang, Z. (1998). Extensions to the k-Means Algorithm for Clustering
Large Data Sets with Categorical Values. *Data Mining and Knowledge Discovery*,
2(3), 283–304. DOI: [10.1023/A:1009769707641](https://doi.org/10.1023/A:1009769707641)

**[R11]** Gower, J. C. (1971). A General Coefficient of Similarity and Some of Its
Properties. *Biometrics*, 27(4), 857–871. DOI: [10.2307/2528823](https://doi.org/10.2307/2528823)

**[R12]** Kizilcec, R. F., Piech, C., & Schneider, E. (2013). Deconstructing
disengagement: analyzing learner subpopulations in massive open online courses.
*LAK '13*, 170–179. DOI: [10.1145/2460296.2460330](https://doi.org/10.1145/2460296.2460330)

### Recommender systems

**[R13]** Hu, Y., Koren, Y., & Volinsky, C. (2008). Collaborative Filtering for
Implicit Feedback Datasets. *ICDM '08*, 263–272. DOI: [10.1109/ICDM.2008.22](https://doi.org/10.1109/ICDM.2008.22)

**[R14]** Rendle, S., Freudenthaler, C., Gantner, Z., & Schmidt-Thieme, L. (2009).
BPR: Bayesian Personalized Ranking from Implicit Feedback. *UAI '09*, 452–461.
URL: https://www.auai.org/uai2009/papers/UAI2009_0139_48141db02b9f0b02bc7158819ebfa2c7.pdf · arXiv: [1205.2618](https://arxiv.org/abs/1205.2618)

**[R15]** Sarwar, B., Karypis, G., Konstan, J., & Riedl, J. (2001). Item-based
collaborative filtering recommendation algorithms. *WWW '01*, 285–295. DOI: [10.1145/371920.372071](https://doi.org/10.1145/371920.372071)

**[R16]** Deshpande, M., & Karypis, G. (2004). Item-based top-N recommendation
algorithms. *ACM TOIS*, 22(1), 143–177. DOI: [10.1145/963770.963776](https://doi.org/10.1145/963770.963776)

**[R17]** Burke, R. (2002). Hybrid Recommender Systems: Survey and Experiments.
*User Modeling and User-Adapted Interaction*, 12(4), 331–370. DOI: [10.1023/A:1021240730564](https://doi.org/10.1023/A:1021240730564)

**[R18]** Lops, P., de Gemmis, M., & Semeraro, G. (2011). Content-based
Recommender Systems: State of the Art and Trends. In *Recommender Systems
Handbook*, 73–105. DOI: [10.1007/978-0-387-85820-3_3](https://doi.org/10.1007/978-0-387-85820-3_3)

**[R19]** Schein, A. I., Popescul, A., Ungar, L. H., & Pennock, D. M. (2002).
Methods and metrics for cold-start recommendations. *SIGIR '02*, 253–260. DOI: [10.1145/564376.564421](https://doi.org/10.1145/564376.564421)

### Evaluation

**[R20]** Cremonesi, P., Koren, Y., & Turrin, R. (2010). Performance of
recommender algorithms on top-N recommendation tasks. *RecSys '10*, 39–46. DOI: [10.1145/1864708.1864721](https://doi.org/10.1145/1864708.1864721)

**[R21]** Herlocker, J. L., Konstan, J. A., Terveen, L. G., & Riedl, J. T. (2004).
Evaluating collaborative filtering recommender systems. *ACM TOIS*, 22(1), 5–53.
DOI: [10.1145/963770.963772](https://doi.org/10.1145/963770.963772)

**[R22]** Shani, G., & Gunawardana, A. (2011). Evaluating Recommendation Systems.
In *Recommender Systems Handbook*, 257–297. DOI: [10.1007/978-0-387-85820-3_8](https://doi.org/10.1007/978-0-387-85820-3_8)

**[R23]** Järvelin, K., & Kekäläinen, J. (2002). Cumulated gain-based evaluation
of IR techniques. *ACM TOIS*, 20(4), 422–446. DOI: [10.1145/582415.582418](https://doi.org/10.1145/582415.582418)

**[R24]** Meng, Z., McCreadie, R., Macdonald, C., & Ounis, I. (2020). Exploring
Data Splitting Strategies for the Evaluation of Recommendation Models.
*RecSys '20*, 681–686. DOI: [10.1145/3383313.3418479](https://doi.org/10.1145/3383313.3418479) · arXiv: [2007.13237](https://arxiv.org/abs/2007.13237)

**[R25]** Ji, Y., Sun, A., Zhang, J., & Li, C. (2023). A Critical Study on Data
Leakage in Recommender System Offline Evaluation. *ACM TOIS*, 41(3), Article 75.
DOI: [10.1145/3569930](https://doi.org/10.1145/3569930) · arXiv: [2010.11060](https://arxiv.org/abs/2010.11060)

**[R26]** Ferrari Dacrema, M., Cremonesi, P., & Jannach, D. (2019). Are We Really
Making Much Progress? A Worrying Analysis of Recent Neural Recommendation
Approaches. *RecSys '19*, 101–109. DOI: [10.1145/3298689.3347058](https://doi.org/10.1145/3298689.3347058) · arXiv: [1907.06902](https://arxiv.org/abs/1907.06902)

**[R27]** Ge, M., Delgado-Battenfeld, C., & Jannach, D. (2010). Beyond accuracy:
evaluating recommender systems by coverage and serendipity. *RecSys '10*,
257–260. DOI: [10.1145/1864708.1864761](https://doi.org/10.1145/1864708.1864761)

**[R28]** Cañamares, R., & Castells, P. (2018). Should I Follow the Crowd? A
Probabilistic Analysis of the Effectiveness of Popularity in Recommender Systems.
*SIGIR '18*, 415–424. DOI: [10.1145/3209978.3210014](https://doi.org/10.1145/3209978.3210014)

**[R29]** Abdollahpouri, H., Mansoury, M., Burke, R., & Mobasher, B. (2019). The
Unfairness of Popularity Bias in Recommendation. *RecSys 2019 Workshop on
Recommendation in Multistakeholder Environments (RMSE)*. arXiv: [1907.13286](https://arxiv.org/abs/1907.13286)

**[R30]** Ekstrand, M. D., Tian, M., Madrazo Azpiazu, I., Ekstrand, J. D.,
Anuyah, O., McNeill, D., & Pera, M. S. (2018). All The Cool Kids, How Do They Fit
In? Popularity and Demographic Biases in Recommender Evaluation and
Effectiveness. *PMLR* 81 (FAT* 2018), 172–186. URL: https://proceedings.mlr.press/v81/ekstrand18b.html

### Explainability and fairness

**[R31]** Zhang, Y., & Chen, X. (2020). Explainable Recommendation: A Survey and
New Perspectives. *Foundations and Trends in Information Retrieval*, 14(1),
1–101. DOI: [10.1561/1500000066](https://doi.org/10.1561/1500000066)

**[R32]** Tintarev, N., & Masthoff, J. (2011). Designing and Evaluating
Explanations for Recommender Systems. In *Recommender Systems Handbook*, 479–510.
DOI: [10.1007/978-0-387-85820-3_15](https://doi.org/10.1007/978-0-387-85820-3_15)

**[R38]** Barocas, S., Hardt, M., & Narayanan, A. (2023). *Fairness and Machine
Learning: Limitations and Opportunities*. MIT Press. URL: https://fairmlbook.org/
· https://mitpress.mit.edu/9780262048613/fairness-and-machine-learning/

### Production ML and engineering documentation

**[R33]** Sculley, D., Holt, G., Golovin, D., Davydov, E., Phillips, T., Ebner,
D., Chaudhary, V., Young, M., Crespo, J.-F., & Dennison, D. (2015). Hidden
Technical Debt in Machine Learning Systems. *NIPS 28*. URL: https://papers.nips.cc/paper/5656-hidden-technical-debt-in-machine-learning-systems

**[R34]** Breck, E., Cai, S., Nielsen, E., Salib, M., & Sculley, D. (2017). The ML
Test Score: A Rubric for ML Production Readiness and Technical Debt Reduction.
*IEEE Big Data*. URL: https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/

**[R35]** Pedregosa, F., et al. (2011). Scikit-learn: Machine Learning in Python.
*Journal of Machine Learning Research*, 12, 2825–2830. URL: https://www.jmlr.org/papers/volume12/pedregosa11a/pedregosa11a.pdf

**[R36]** scikit-learn developers. *Model persistence* (documentation). URL: https://scikit-learn.org/stable/model_persistence.html
— retrieved 19 September 2026.

**[R37]** Streamlit. *Caching* (documentation). URL: https://docs.streamlit.io/develop/concepts/architecture/caching
— retrieved 19 September 2026.

**[R37b]** Streamlit. *Deploy your app on Community Cloud* (documentation). URL: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
— retrieved 19 September 2026. States that Community Cloud supports all released
Python versions still receiving security updates, and defaults to 3.12. **This
retrieval corrected an unverified claim made in Phase 0** — see ADR-0002.

### Education-specific

**[R39]** Urdaneta-Ponte, M. C., Mendez-Zorrilla, A., & Oleagordia-Ruiz, I.
(2021). Recommendation Systems for Education: Systematic Review. *Electronics*,
10(14), 1611. DOI: [10.3390/electronics10141611](https://doi.org/10.3390/electronics10141611)

---

## 11. Sources consulted but not relied upon

Recorded for transparency: the search for a peer-reviewed survey specifically
covering *course* recommenders returned several candidates whose venue or peer-
review status could not be established to the standard required here. Only [R39]
is cited, because only it was confirmed as a peer-reviewed journal article with a
resolvable DOI. No claim in this review rests on an unverified source.
