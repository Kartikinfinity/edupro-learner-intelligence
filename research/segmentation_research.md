# Segmentation Research

**Phase:** 1 — research and methodology investigation
**Date:** 19 September 2026
**Reference keys `[Rxx]`** resolve in `literature_review.md` §10.
**Companion:** `methodology_comparison.md` §A–D for the per-method comparison
tables.

---

## 1. The problem, stated in EduPro's terms

Aggregate 10,000 transactions into 3,000 learner profiles, then partition those
profiles into a small number of segments that are:

- **behaviourally distinct** — members differ measurably from other segments;
- **internally consistent** — members resemble each other (the brief's
  "intra-cluster similarity");
- **stable** — the segment reappears when the data is resampled [R03];
- **interpretable** — describable in a sentence a non-technical stakeholder can
  act on;
- **actionable** — the description implies something EduPro could actually do.

The last two are not softer requirements than the first three. A statistically
excellent partition that no one can describe or act on fails the brief, whose
deliverables include an executive summary and a segment-comparison dashboard.

---

## 2. Feature design

### 2.1 The mandated feature set

The official brief names eleven learner-level features across four groups
(transcript §Feature Engineering). Each is listed below with its construction and
the specific risk it carries.

| # | Feature | Group | Construction | Risk |
| --- | --- | --- | --- | --- |
| B1 | Age | Demographic | `Users.Age` | Scale dominance; low actionability — §10 |
| B2 | Gender | Demographic | `Users.Gender` | Binary split K-Means will exploit; proxy risk [R38] |
| B3 | Total courses enrolled | Engagement | count of transactions | **Skewed; correlated with B4, B5, B9, B10** |
| B4 | Average courses per category | Engagement | B3 / distinct categories | Deterministic function of B3 and B10 |
| B5 | Enrollment frequency | Engagement | B3 / active time span | Undefined for 1-interaction learners |
| B6 | Preferred course category | Preference | modal category | **12 levels — the dominance problem** |
| B7 | Preferred course level | Preference | modal level | 3 levels; ties common at short histories |
| B8 | Average course rating enrolled | Preference | mean `CourseRating` | Low variance if ratings are narrow |
| B9 | Average spending | Behavioural | mean `Amount` | **May be identical to average price — Q-1** |
| B10 | Diversity score | Behavioural | distinct categories explored | **Bounded by B3** — see §2.3 |
| B11 | Learning depth index | Behavioural | beginner vs advanced ratio | Undefined/degenerate at short histories |

### 2.2 The correlation problem

> **[INFERENCE]** Several mandated features are not independent, and K-Means
> weights correlated features effectively multiple times because each contributes
> its own term to the Euclidean distance.
>
> The clearest case: **B4 = B3 / B10** exactly. Including all three gives the
> "how much and how broadly did this learner enrol" concept *three* votes in the
> distance metric while "what did they pay" (B9) gets one. Nothing in K-Means
> corrects for this.
>
> **This does not mean dropping mandated features** — the brief requires them and
> the traceability matrix tracks each one. The mitigations, to be decided by
> experiment (EXP-011e), are: report the full correlation matrix in the EDA so
> the redundancy is visible; test a de-correlated variant as an ablation; and
> report the feature-dominance diagnostic (§4) so the reader can see which
> concepts actually drove the partition. The brief mandates *investigating* these
> features, which is what an ablation does.

### 2.3 The short-history problem

> **[INFERENCE]** This is the most serious threat to the whole segmentation, and
> it follows arithmetically from the mean of 3.333 courses per learner.
>
> **B10 (diversity score) is bounded by B3 (total courses).** A learner with 2
> enrollments can have a diversity score of at most 2, out of 12 possible
> categories. So the measured "diversity" of low-activity learners is largely a
> measure of their activity, not of their breadth of interest. K-Means cannot
> distinguish "this learner is focused" from "this learner has barely started".
>
> **B5 (enrollment frequency)** is undefined for a learner with one interaction —
> there is no span to divide by.
>
> **B11 (learning depth index)** at 3 enrollments takes only a handful of
> discrete values, so it behaves as a coarse categorical, not a continuous index.
>
> **Consequence:** without care, the dominant axis of variation will be
> *history length*, and the segments will be "heavy users / medium users / light
> users" — a finding that is real but nearly content-free, since it restates the
> activity distribution the EDA already shows.
>
> **Candidate mitigations, to be tested (EXP-011f), not assumed:**
> 1. **Normalise breadth by opportunity** — use diversity/B3 (a breadth *ratio*)
>    alongside or instead of the raw count, so a 2-of-2 learner and a 6-of-6
>    learner both read as maximally broad.
> 2. **Segment within activity strata** — cluster separately within history-length
>    bands so that within-band variation is about preference, not volume.
> 3. **Accept and report it** — if activity level genuinely is the dominant
>    structure, say so plainly rather than engineering it away. That is a
>    legitimate finding, and §6 requires it be reportable.
>
> These are alternatives, and the experiment decides. Option 3 is included
> deliberately so the experiment is not rigged toward finding richer structure
> than exists.

### 2.4 Features available but not mandated

| Field | Status | Note |
| --- | --- | --- |
| `CoursePrice`, `CourseDuration` | **Open — Q-3** | In the workbook, absent from the official field list. Duration could support a genuine "time commitment" feature, which is behaviourally distinct from spend. Decide in Phase 2 with justification either way. |
| `PaymentMethod` (3 values) | **Likely exclude** | No plausible link to learning preference. Would need a positive argument to include. |
| `CourseType` (2 values) | **Candidate** | A course-side attribute; as a learner-side preference ratio it may be informative. |
| `UserName`, `Email` | **Excluded** | PII, §17, ADR-0006. Not a modelling decision — a hard rule. |
| Teacher-derived | **Deferred to EXP-005/EXP-014** | See §7. |

---

## 3. Encoding: the central technical decision

Restating the core risk from `literature_review.md` §1.2, because it determines
whether the segmentation means anything:

> One-hot encoding `PreferredCategory` adds **12 binary columns** against roughly
> **8 behavioural columns**. More than half the Euclidean distance budget is then
> spent on a single conceptual variable, and K-Means would substantially be
> clustering learners by their modal category — reproducing the course taxonomy
> EduPro already has, dressed up as a discovered segmentation.

### 3.1 The four candidate encodings (EXP-011a)

| Encoding | Mechanism | Expected behaviour | Status |
| --- | --- | --- | --- |
| **E-A: One-hot** | 12 indicator columns | Category dominance | **Control arm** — retained so dominance is demonstrated, not asserted |
| **E-B: Category-proportion vector** | 12 columns, row-normalised to the learner's distribution | Same dimensionality, full preference shape, naturally bounded [0,1] | **Expected front-runner** |
| **E-C: Reduced facets** | Replace category identity with diversity ratio + entropy + top-category share | ~3 columns instead of 12; dominance eliminated | **Candidate** — loses category identity |
| **E-D: Gower distance** | Explicit per-variable weights, mixed types native [R11] | Weighting becomes a visible choice | **Candidate** — requires non-K-Means clustering |

> **[INFERENCE] Why E-B is expected to lead, without being selected here.** It
> preserves all the information of E-A at the same dimensionality while adding
> preference *shape*: a learner split evenly between two categories is
> represented as such rather than collapsed to one modal label. It is also
> conceptually coherent with the brief's own "average courses per category" and
> "diversity score", both of which are already summarising the same underlying
> distribution. And it is bounded in [0,1], so it needs no separate scaling
> decision.
>
> E-B is nonetheless **not selected in Phase 1**. EXP-011a runs all four and
> decides on the evidence — including the possibility that E-C, by removing
> category identity entirely, produces segments that are more about *behaviour*
> and therefore more actionable.

### 3.2 Feature-block weighting

> **[INFERENCE]** Even with E-B, three feature blocks compete: engagement (~5
> columns), preference (~14 columns), behavioural (~3 columns). Unweighted
> Euclidean distance gives the preference block roughly three times the influence
> of engagement, purely because of column counts — an accident of representation,
> not a modelling decision.
>
> **Block weighting will be tested as an ablation** (EXP-011b): weight each block
> so that blocks contribute comparably regardless of column count (e.g. scale each
> block by 1/√(columns in block)). This makes the weighting explicit and
> defensible, which is what §14's prohibition on arbitrary weights is really
> about — the alternative is not "no weighting" but "accidental weighting".

---

## 4. Feature dominance diagnostic

CLAUDE.md §10 requires that demographic features must not dominate the
segmentation without justification. That requires a *measurement*, and none is
specified, so one is defined here.

> **[INFERENCE] Definition.** For each feature *f* and partition *C*, compute the
> **eta-squared** (η²) — the proportion of *f*'s total variance explained by
> cluster membership, i.e. between-cluster sum of squares over total sum of
> squares, from a one-way ANOVA of *f* on the cluster labels.
>
> Aggregate to blocks by averaging η² across the block's features. Report:
> - η² per feature, ranked;
> - mean η² per block (demographic / engagement / preference / behavioural);
> - **the demographic block's share of total explained variance** — the single
>   number that answers §10.

**Pre-registered interpretation rule**, fixed before results are seen:

| Demographic share of explained variance | Reading |
| --- | --- |
| < 20% | Demographics are secondary. Variant A is acceptable if it also wins on quality. |
| 20–40% | Demographics are material. Requires explicit justification to retain. |
| > 40% | **Demographics dominate.** Variant A rejected unless an exceptional, documented argument applies. |

Why η²: it is standard, cheap, and directly interpretable as "how much of this
feature's variation is accounted for by the segmentation". It is reported for
*every* block, not only demographics, because the one-hot dominance risk (§3) is
structurally the same problem applied to a different block.

---

## 5. Intra-cluster similarity — definition

The brief mandates this metric for "behavioural consistency" [transcript p.5] but
gives no formula. Defining it in advance:

> **[INFERENCE] Definition.** For cluster *c*, intra-cluster similarity is the
> **mean pairwise cosine similarity between members' feature vectors, computed on
> the behavioural and engagement feature blocks only** — demographics excluded.
>
> Reported per cluster and as a population-weighted mean.

Three deliberate choices:

1. **Behavioural features only.** The metric's stated purpose is *behavioural*
   consistency. Including age and gender would let a demographically homogeneous
   but behaviourally scattered cluster score well, which would misreport exactly
   what the metric exists to measure.
2. **Cosine rather than Euclidean.** Cosine compares *profile shape*
   independently of magnitude, so it does not simply re-measure the
   history-length axis identified in §2.3 — which is the dominant magnitude
   effect in this data.
3. **Per cluster, not only averaged.** Like silhouette [R01] and stability [R03],
   the per-cluster value is where the actionable information is: one loose
   segment among four tight ones is a finding an average would conceal.

**Note on independence.** This metric is correlated with silhouette by
construction — both measure within-cluster tightness. It is reported because the
brief mandates it and because the cosine/behavioural-only formulation differs
meaningfully from silhouette's Euclidean/all-features formulation, but it will
**not** be presented as independent confirmation of silhouette.

---

## 6. Selecting k

### 6.1 Five criteria, deliberately including one that can say "none"

| Criterion | What it contributes | Status |
| --- | --- | --- |
| **Elbow** (inertia vs k) | Mandated; visual | Reported, **not decisive** [R07] |
| **Silhouette** (global + per-cluster) | Mandated; absolute quality reading | **Primary quantitative criterion** [R01] |
| **Gap statistic** | **Can return k=1 — i.e. no structure** | Critical falsification test [R02] |
| **Calinski–Harabasz, Davies–Bouldin** | Cheap corroboration | Supporting; correlated with silhouette [R06] |
| **Stability** (per-cluster Jaccard) | Does the partition survive resampling | **Co-primary** [R03][R05] |

> **[INFERENCE] The gap statistic is the most important non-mandated addition to
> this project.** Elbow, silhouette, CH and DB all *assume* structure exists and
> merely locate the best k; none can return the verdict "there are no real
> clusters here". Given the synthetic-data risk (V8 in the evaluation plan) and
> the short-history problem (§2.3), "the learner profiles have no meaningful
> cluster structure" is a genuinely live possibility. A project that cannot
> detect that outcome would be structurally incapable of reporting it — and §6
> requires that it be reportable.

### 6.2 Search range and pre-registered decision rule

**Range: k ∈ {2, …, 10}.** Upper bound justified by the deliverable: the
dashboard must present segment comparisons a stakeholder can hold in mind, and
[R12] recovered four interpretable learner types across three independent MOOCs.
Beyond ~8 segments, interpretability collapses regardless of statistics.

**Decision rule, fixed in advance:**

1. If the **gap statistic indicates k=1**, report that the data does not support
   segmentation. Proceed with the brief-mandated K-Means for the deliverable, but
   report the finding prominently and treat all segment interpretations as
   provisional. **This outcome is not a failure — it is a result.**
2. Otherwise, take the k maximising **mean silhouette**, subject to:
   - every cluster holding **≥5% of learners** (150) — smaller clusters are not
     actionable segments;
   - every cluster achieving **bootstrap Jaccard ≥0.6** [R03] — below this the
     cluster is not reliably reproducible;
   - the partition being describable in plain language (§8).
3. If no k satisfies all constraints, take the largest k that satisfies the
   stability and size constraints, and **report the constraint that bound**.
4. Record the full criterion table for every k — including the values that lost.

---

## 7. Variant A vs Variant B (CLAUDE.md §10)

| | **Variant A** | **Variant B** |
| --- | --- | --- |
| Features | Behaviour + demographics (Age, Gender) | Behaviour only |
| Rationale | Demographics may carry real signal | Demographics risk dominating, are unactionable, and carry proxy risk |

**Measured for both** (EXP-011): silhouette; per-cluster bootstrap Jaccard;
intra-cluster similarity; **demographic share of explained variance** (§4);
interpretability (§8); and — the criterion that connects segmentation to the rest
of the project — **downstream cluster-popularity recommender NDCG@10**.

> **[INFERENCE] The downstream criterion is the one that matters most.** Cluster
> quality metrics measure whether a partition is *tight*. They do not measure
> whether it is *useful*. Since the brief's purpose for segmentation is
> cluster-aware recommendation, the segmentation that produces better
> recommendations has demonstrated practical value in a way a silhouette score
> cannot. This also guards against the failure mode where a demographically-driven
> partition scores well on internal metrics precisely because age and gender give
> clean, high-variance splits — while contributing nothing to recommendation.

**Pre-registered decision rule:**

1. If Variant A's **demographic share of explained variance exceeds 40%** (§4),
   **reject Variant A** — §10's requirement that demographics not dominate
   without justification, made operational.
2. Otherwise, if the two variants' downstream NDCG@10 differ by **less than
   0.01**, **select Variant B** — the simpler, more privacy-respecting, more
   actionable model wins ties on principle, not by preference.
3. Otherwise select the variant with higher downstream NDCG@10, and document the
   justification for demographics if Variant A wins.

**Regardless of the outcome:** age and gender are retained as **evaluation
strata** [R30]. Reporting that recommendation quality is (or is not) equivalent
across demographic groups is a stronger position than not looking. Auditing with
a protected attribute is not the same as modelling with it.

---

## 8. Interpretability and segment naming

The brief requires "interpretable segment descriptions" and a segment-comparison
dashboard.

**Profiling procedure.** For each cluster: centroid values per feature; deviation
from the population mean in standard-deviation units; the 3–5 features with the
largest absolute deviation (these become the description); size and population
share; per-cluster silhouette and stability; top course categories and levels.

> **[INFERENCE] Naming rules, adopted to prevent fabricated findings.**
> 1. **Names are derived from the cluster's own top deviating features** — never
>    chosen first and justified afterwards.
> 2. **[R12]'s labels must not be borrowed.** "Auditing", "completing",
>    "sampling" and "disengaging" were derived from longitudinal within-course
>    engagement traces (video views, assessment submissions over time). EduPro has
>    **no completion, progress or engagement-trace data at all** — only enrollment
>    transactions. Applying those labels here would assert learner behaviour the
>    data cannot evidence. This is the most tempting available fabrication in the
>    whole project, because the labels are well-known, intuitive and would look
>    authoritative in a research paper.
> 3. **Names must be defensible from the feature that earns them.** "Broad
>    Explorers" is defensible if the cluster's diversity ratio is high. "Motivated
>    Career-Changers" is not defensible from any field in this dataset.
> 4. **A cluster with no clear distinguishing feature gets a neutral name**
>    ("Segment 3 — mixed profile") and the ambiguity is reported. Inventing a
>    narrative for a diffuse cluster is exactly the fabrication §6 prohibits.

---

## 9. Validation via hierarchical clustering

The brief mandates hierarchical clustering as validation.

> **[INFERENCE] A caveat that must accompany the result.** Ward's method
> minimises the increase in within-cluster variance on merge [R08] — the same
> objective family K-Means optimises. High agreement between Ward and K-Means
> therefore partly reflects a **shared inductive bias**, not independent
> confirmation. Reporting "hierarchical clustering confirms our K-Means solution"
> without that caveat would overstate the evidence.
>
> **Mitigation:** run **average-linkage** alongside Ward (and, if E-D is used,
> over Gower distance [R11]). Average linkage optimises something different, so
> agreement across Ward *and* average linkage *and* K-Means is meaningfully
> stronger evidence than agreement between Ward and K-Means alone.

**Agreement metric:** Adjusted Rand Index between partitions at the chosen k,
reported for each pairing, with the shared-bias caveat stated in the text.

---

## 10. Open questions this research does not settle

| # | Question | Decided by |
| --- | --- | --- |
| S-1 | Which encoding (E-A…E-D)? | EXP-011a |
| S-2 | Is block weighting needed? | EXP-011b |
| S-3 | Variant A or B? | EXP-011 + §7 rule |
| S-4 | What k? | EXP-010 + §6.2 rule |
| S-5 | Does meaningful structure exist at all? | EXP-010b (gap statistic) |
| S-6 | Does history length dominate the segmentation? | EXP-011f |
| S-7 | Is diversity separable from activity level? | EXP-011f + Phase 2 distributions |
| S-8 | Do teacher signals add anything, or is TeacherID an alias for CourseID? | **EXP-005 first**, then EXP-014 |
| S-9 | StandardScaler or RobustScaler? | EXP-006 distributions |
| S-10 | Does the segmentation improve recommendation at all? | EXP-023 vs EXP-020 |

> **S-10 is the question the whole project turns on.** ADR-0005 deliberately made
> the cluster signal ablatable so this can be measured rather than assumed. If
> cluster-popularity does not beat global popularity, then the segmentation —
> however statistically sound — has not demonstrated recommendation value, and the
> research paper must say so. The segmentation would still have standalone
> analytical value for the brief's learner-analysis requirement, and that
> distinction is worth drawing carefully rather than blurring.
