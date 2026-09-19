# Methodology Comparison

**Phase:** 1 — dense research and methodology investigation
**Date:** 19 September 2026
**Companion documents:** `literature_review.md` (evidence + reference keys `[Rxx]`),
`experiment_plan.md` (the experiments that decide the open entries).

---

## Decision-status vocabulary

| Status | Meaning |
| --- | --- |
| **ADOPT** | Required by the official brief or CLAUDE.md, or a non-contentious engineering default. Adopting it does not pre-judge any modelling outcome. |
| **CANDIDATE** | In the experimental comparison. **Not selected.** The named experiment decides. |
| **REJECT** | Ruled out in Phase 1, with the reason recorded. Reversible if Phase 2 contradicts the premise. |
| **DEFER** | Cannot be assessed until a Phase 2 fact is known. The blocking fact is named. |

> **No entry in this document is marked as the final production choice.** CLAUDE.md
> §4 and the Phase 1 pass criteria require that the architecture not be locked
> from literature. `ADOPT` here means "this is in scope and uncontroversial", never
> "this won the comparison".

**Cost scale.** Relative to this dataset (3,000 learners × 60 courses × 10,000
interactions), which is small enough that *everything* below runs in seconds to
low minutes on a laptop. Cost is therefore a near-negligible criterion for this
project and is recorded for completeness and for future scale-up, not as a
tiebreaker. Stated as: **Trivial** (<1s) · **Low** (seconds) · **Moderate**
(seconds–minutes) · **High** (minutes+).

---

# A. Segmentation algorithms

### A1. K-Means (k-means++ init)

| Field | Assessment |
| --- | --- |
| **Purpose** | Partition learners into k behavioural segments by minimising within-cluster variance. |
| **Data requirement** | Fully numeric, scaled feature matrix. No missing values. Assumes roughly isotropic, comparably-sized clusters. |
| **Advantages** | Fast, deterministic under a fixed seed, universally understood; k-means++ gives an O(log k) expected approximation guarantee [R09]; centroids are directly readable as segment profiles. |
| **Limitations** | Requires k in advance; assumes spherical clusters of similar size; sensitive to feature scaling and to encoding choices; Euclidean distance is poorly defined over one-hot categoricals. |
| **Fit to EduPro** | Good on the behavioural features. The risk is not the algorithm but its **input encoding** — see D1/D2. |
| **Cost** | Trivial. 3,000×~15 matrix. |
| **Interpretability** | High. Centroid per segment maps to a plain-language profile. |
| **Implementation** | Trivial — `sklearn.cluster.KMeans`. |
| **Decision status** | **ADOPT** as primary — mandated by the official brief. Its *configuration* (features, encoding, k) remains open. |
| **Evidence** | Official brief p.4; [R09] |

### A2. Hierarchical clustering — Ward linkage

| Field | Assessment |
| --- | --- |
| **Purpose** | Independent structural validation of the K-Means partition. |
| **Data requirement** | Numeric matrix or distance matrix; Ward requires Euclidean. |
| **Advantages** | No k needed up front; dendrogram exposes nested structure; agreement with K-Means is corroborating evidence [R08]. |
| **Limitations** | O(n²) memory; greedy merges are never revisited; **Ward minimises within-cluster variance, the same objective family as K-Means**, so agreement is partly a shared inductive bias rather than independent confirmation. |
| **Fit to EduPro** | Good — n=3,000 makes the 3,000² distance matrix trivially affordable. |
| **Cost** | Low. |
| **Interpretability** | High — the dendrogram is a strong figure for the research paper. |
| **Implementation** | Low — `scipy.cluster.hierarchy`. |
| **Decision status** | **ADOPT** as validation — mandated by the brief. |
| **Evidence** | Official brief p.4; [R08] |

### A3. Hierarchical clustering — average linkage

| Field | Assessment |
| --- | --- |
| **Purpose** | A *genuinely* independent validation, correcting A2's shared-bias weakness. |
| **Data requirement** | Any distance matrix — including non-Euclidean (Gower). |
| **Advantages** | Optimises a different objective from K-Means, so agreement is stronger evidence; works with mixed-type distances. |
| **Limitations** | Prone to chaining; can produce very unbalanced clusters. |
| **Fit to EduPro** | Useful precisely *because* it may disagree with K-Means. |
| **Cost** | Low. |
| **Interpretability** | High. |
| **Implementation** | Trivial once A2 exists. |
| **Decision status** | **CANDIDATE** — added beyond the brief's minimum. EXP-012. |
| **Evidence** | Engineering inference from [R08]; see `literature_review.md` §1.1. |

### A4. k-prototypes (mixed numeric + categorical)

| Field | Assessment |
| --- | --- |
| **Purpose** | Cluster mixed-type learner profiles without one-hot encoding. |
| **Data requirement** | Numeric and categorical columns kept native. |
| **Advantages** | Avoids the one-hot dimensionality inflation that lets a 12-level categorical dominate Euclidean distance [R10]. |
| **Limitations** | Needs a γ parameter balancing numeric and categorical dissimilarity — an *extra* arbitrary weight, which §14's spirit disfavours; not in scikit-learn, so it adds a dependency (`kmodes`); less familiar to reviewers. |
| **Fit to EduPro** | Addresses a real problem (D1), but the proportion-vector encoding (D2) may solve the same problem with no new dependency and no new hyperparameter. |
| **Cost** | Low. |
| **Interpretability** | Moderate — modes are readable, but γ is not. |
| **Implementation** | Moderate — new dependency, not in the validated environment. |
| **Decision status** | **CANDIDATE**, lower priority than D2. EXP-011a. Adopted only if D2 demonstrably fails. |
| **Evidence** | [R10] |

### A5. DBSCAN / density-based clustering

| Field | Assessment |
| --- | --- |
| **Purpose** | Discover arbitrarily-shaped clusters; identify outliers. |
| **Data requirement** | Meaningful density contrast in the feature space. |
| **Advantages** | No k required; labels noise points explicitly. |
| **Limitations** | ε and `min_samples` are hard to set in ~15 dimensions; degrades badly with dimensionality; frequently returns one giant cluster plus noise. |
| **Fit to EduPro** | Poor. Learner features derived from ~3.3 interactions produce a space with many tied/near-duplicate points and little density contrast. It also produces no centroid, so it cannot deliver the interpretable segment profiles the brief requires. |
| **Cost** | Low. |
| **Interpretability** | Low — no centroid, variable cluster count. |
| **Implementation** | Low. |
| **Decision status** | **REJECT** — poor fit to the deliverable, not mandated, and it would consume schedule with low expected value. Reversible if Phase 2 shows strong density structure. |
| **Evidence** | Engineering inference. |

### A6. Gaussian Mixture Models

| Field | Assessment |
| --- | --- |
| **Purpose** | Soft (probabilistic) segment assignment. |
| **Data requirement** | Numeric; assumes Gaussian components. |
| **Advantages** | Soft assignment honestly expresses that a learner may sit between segments; BIC/AIC give a principled model-selection route to k. |
| **Limitations** | Gaussian assumption is poor for counts and heavily-skewed spend; more parameters to estimate; a soft assignment complicates the "assigned segment" the brief's UI requires. |
| **Fit to EduPro** | Moderate. Attractive for k-selection via BIC, but the brief explicitly asks the dashboard to show *the* assigned segment. |
| **Cost** | Low. |
| **Interpretability** | Moderate. |
| **Implementation** | Low — `sklearn.mixture`. |
| **Decision status** | **CANDIDATE**, low priority — as a BIC-based cross-check on k only, not as the production segmenter. EXP-010c. |
| **Evidence** | Engineering inference; cf. [R06] on competing k-selection rules. |

---

# B. Cluster-count selection

### B1. Elbow method (inertia vs k)

| Field | Assessment |
| --- | --- |
| **Purpose** | Identify diminishing returns in within-cluster sum of squares as k increases. |
| **Data requirement** | A K-Means sweep over a range of k. |
| **Advantages** | Mandated by the brief; visually intuitive; cheap; familiar to every stakeholder. |
| **Limitations** | **Inertia decreases monotonically by construction**, so the "elbow" is a subjective reading of a curve that always slopes one way; frequently ambiguous; methodological critiques of casual cluster analysis apply directly [R07]. |
| **Fit to EduPro** | Required, and will be produced — but insufficient alone. |
| **Cost** | Trivial. |
| **Interpretability** | High visually; low as evidence. |
| **Implementation** | Trivial. |
| **Decision status** | **ADOPT** as a required, reported input — **not** as the sole arbiter of k. |
| **Evidence** | Official brief p.4; [R07] |

### B2. Silhouette analysis

| Field | Assessment |
| --- | --- |
| **Purpose** | Score cluster cohesion vs separation, per point and in aggregate. |
| **Data requirement** | Cluster labels + the distance metric used for clustering. |
| **Advantages** | Mandated by the brief; gives an absolute (not merely relative) quality reading; per-point silhouettes expose *which* clusters are weak, not just the average [R01]. |
| **Limitations** | Biased toward convex, well-separated clusters — it structurally favours what K-Means produces; degrades in high dimensions; O(n²) in the naive form (trivial at n=3,000). |
| **Fit to EduPro** | Strong. The per-cluster silhouette plot is a key research-paper figure. |
| **Cost** | Low. |
| **Interpretability** | High. |
| **Implementation** | Trivial — `sklearn.metrics.silhouette_score` / `silhouette_samples`. |
| **Decision status** | **ADOPT** — mandated, and the primary quantitative k-criterion. |
| **Evidence** | Official brief p.5; [R01] |

### B3. Gap statistic

| Field | Assessment |
| --- | --- |
| **Purpose** | Compare observed within-cluster dispersion against a null reference distribution. |
| **Data requirement** | Repeated clustering of reference datasets sampled from a null. |
| **Advantages** | Principled; **can indicate k=1, i.e. no cluster structure at all** — a verdict neither elbow nor silhouette can deliver [R02]. |
| **Limitations** | Sensitive to the choice of null reference; higher variance; not in scikit-learn (needs implementing, ~30 lines). |
| **Fit to EduPro** | Valuable specifically because of the k=1 capability. With features derived from ~3.3 interactions, "there are no real segments" is a live possibility that must be testable. |
| **Cost** | Moderate — B reference datasets × k values. Still seconds here. |
| **Interpretability** | Moderate. |
| **Implementation** | Moderate — small custom implementation, unit-testable against a synthetic case with known k. |
| **Decision status** | **CANDIDATE**, high priority — beyond the brief's minimum, added because no mandated method can falsify the existence of structure. EXP-010b. |
| **Evidence** | [R02]; [R06] |

### B4. Calinski–Harabasz and Davies–Bouldin indices

| Field | Assessment |
| --- | --- |
| **Purpose** | Additional internal validity indices for k selection. |
| **Data requirement** | Cluster labels + feature matrix. |
| **Advantages** | Free (both in scikit-learn); cheap corroboration; disagreement between indices is itself informative [R06]. |
| **Limitations** | Same convexity bias as silhouette — **they are not independent evidence**; no absolute interpretation. |
| **Fit to EduPro** | Cheap supporting evidence; must not be presented as independent confirmation. |
| **Cost** | Trivial. |
| **Interpretability** | Low — relative-only, unfamiliar to stakeholders. |
| **Implementation** | Trivial. |
| **Decision status** | **CANDIDATE** — reported in the k-selection table, explicitly flagged as correlated with B2. EXP-010. |
| **Evidence** | [R06] |

---

# C. Cluster stability

### C1. Bootstrap per-cluster Jaccard (Hennig)

| Field | Assessment |
| --- | --- |
| **Purpose** | Measure how reliably **each individual cluster** reappears under resampling. |
| **Data requirement** | Repeated clustering of bootstrap resamples. |
| **Advantages** | Diagnoses *which* segments are solid and which are artefacts, rather than issuing one averaged verdict [R03]. |
| **Limitations** | Needs a cluster-matching rule across runs; interpretation thresholds are conventional, not theoretical. |
| **Fit to EduPro** | **Excellent, and arguably the single most valuable non-mandated method in this document.** The deliverable is segments a stakeholder will act on; a per-segment reliability figure is exactly what the executive summary needs to avoid over-claiming. |
| **Cost** | Moderate — B resamples × clustering. Seconds here. |
| **Interpretability** | High — "this segment reappeared in 87% of resamples" is directly reportable. |
| **Implementation** | Moderate — resampling loop plus Jaccard matching. |
| **Decision status** | **CANDIDATE**, high priority. EXP-013. |
| **Evidence** | [R03]; [R05] |

### C2. Subsample consensus stability (Ben-Hur)

| Field | Assessment |
| --- | --- |
| **Purpose** | Assess presence of structure, and select k, via pairwise partition similarity across perturbed subsamples. |
| **Data requirement** | Repeated clustering of subsamples. |
| **Advantages** | **Can detect the absence of structure** [R04] — same falsification property as B3, by a different route. |
| **Limitations** | Stability-based k-selection is a heuristic with documented failure modes [R05]; global rather than per-cluster. |
| **Fit to EduPro** | Good as a second opinion on both k and "is there structure at all". |
| **Cost** | Moderate. |
| **Interpretability** | Moderate. |
| **Implementation** | Moderate. |
| **Decision status** | **CANDIDATE**. EXP-013b. |
| **Evidence** | [R04]; [R05] |

### C3. Seed-restart stability

| Field | Assessment |
| --- | --- |
| **Purpose** | Confirm the K-Means solution is not an initialisation artefact. |
| **Data requirement** | Repeated fits under different seeds. |
| **Advantages** | Near-free; catches a real and common failure. |
| **Limitations** | Only tests initialisation sensitivity, not structural validity — a stable-but-meaningless partition passes. |
| **Fit to EduPro** | Cheap sanity check. |
| **Cost** | Trivial. |
| **Interpretability** | High (ARI between runs). |
| **Implementation** | Trivial. |
| **Decision status** | **ADOPT** — a baseline hygiene check, not a finding. |
| **Evidence** | Engineering inference from [R09]. |

---

# D. Feature encoding and distance

> This section carries the **highest methodological risk in the project**. See
> `literature_review.md` §1.2.

### D1. One-hot encoding + Euclidean K-Means

| Field | Assessment |
| --- | --- |
| **Purpose** | The default route to clustering categorical preferences. |
| **Data requirement** | Categorical columns expanded to indicator columns. |
| **Advantages** | Standard, trivial, works with every scikit-learn tool. |
| **Limitations** | **12 one-hot columns for `PreferredCategory` against ~8 behavioural columns means over half the distance budget is spent on one conceptual variable.** The resulting "segments" would largely restate the category taxonomy EduPro already has. |
| **Fit to EduPro** | **Poor, despite being the obvious choice.** Identified as a trap. |
| **Cost** | Trivial. |
| **Interpretability** | Moderate. |
| **Implementation** | Trivial. |
| **Decision status** | **CANDIDATE — as the control arm**, retained so the dominance problem is *demonstrated* rather than asserted. EXP-011a. |
| **Evidence** | Engineering inference; the dominance mechanism follows from the Euclidean metric and is measured by the feature-dominance diagnostic (EXP-011c). |

### D2. Category-proportion vector

| Field | Assessment |
| --- | --- |
| **Purpose** | Represent category preference as the learner's distribution across the 12 categories. |
| **Data requirement** | Per-learner category counts, row-normalised. |
| **Advantages** | Same dimensionality as one-hot but carries the full preference *shape*, not just the argmax; naturally bounded [0,1] so it does not need separate scaling; coherent with the brief's own "average courses per category" and "diversity score"; a learner split 50/50 across two categories is represented as such rather than being forced to one. |
| **Limitations** | Still 12 dimensions — dominance is reduced, not eliminated; block weighting may still be needed. |
| **Fit to EduPro** | **Strong.** Expected front-runner, but not selected here. |
| **Cost** | Trivial. |
| **Interpretability** | High — "38% Data Science, 25% Business" is directly readable. |
| **Implementation** | Low. |
| **Decision status** | **CANDIDATE**, high priority. EXP-011a. |
| **Evidence** | Engineering inference, motivated by the mixed-type problem [R10][R11]. |

### D3. Gower distance + distance-based clustering

| Field | Assessment |
| --- | --- |
| **Purpose** | Principled mixed-type dissimilarity with explicit per-variable weights. |
| **Data requirement** | Typed columns; a weighting decision per variable. |
| **Advantages** | Makes the weighting an explicit, defensible choice rather than an artefact of encoding [R11]; works with average-linkage (A3). |
| **Limitations** | 3,000² distance matrix (manageable); rules out standard K-Means (needs k-medoids or hierarchical); weights must themselves be justified — §14's concern about arbitrary weights applies. |
| **Fit to EduPro** | Good, and the most *methodologically* defensible option — but it conflicts with the brief's mandate of K-Means as primary. |
| **Cost** | Moderate. |
| **Interpretability** | High — weights are inspectable. |
| **Implementation** | Moderate. |
| **Decision status** | **CANDIDATE**, medium priority — as a validation route via A3, not as a replacement for mandated K-Means. EXP-012b. |
| **Evidence** | [R11] |

### D4. Dimensionality reduction (PCA) before clustering

| Field | Assessment |
| --- | --- |
| **Purpose** | Decorrelate and compress features prior to clustering. |
| **Data requirement** | Scaled numeric matrix. |
| **Advantages** | Mitigates correlated-feature dominance; 2-D projection is needed anyway for the mandated cluster visualization dashboard. |
| **Limitations** | **Components are linear combinations, which destroys the interpretability the brief requires of segment profiles**; deciding how many components is another free parameter. |
| **Fit to EduPro** | Good **for visualisation**; questionable for clustering itself. |
| **Cost** | Trivial. |
| **Interpretability** | Low for modelling; high for plots. |
| **Implementation** | Trivial. |
| **Decision status** | **ADOPT for visualisation** (required by the brief's cluster dashboard). **CANDIDATE, low priority** for clustering input — interpretability cost is high. EXP-011d. |
| **Evidence** | Engineering inference. |

### D5. StandardScaler vs RobustScaler

| Field | Assessment |
| --- | --- |
| **Purpose** | Put numeric features on a comparable scale before distance computation. |
| **Data requirement** | Numeric matrix. |
| **Advantages** | Mandated ("normalize numerical features"); StandardScaler is the default and pairs naturally with Euclidean K-Means; RobustScaler resists outlier influence via median/IQR. |
| **Limitations** | StandardScaler is outlier-sensitive — a few very high-spend learners could compress everyone else into a narrow band. |
| **Fit to EduPro** | **DEFER** — depends on the Phase 2 skew of spend and history-length. |
| **Cost** | Trivial. |
| **Interpretability** | High. |
| **Implementation** | Trivial. |
| **Decision status** | **DEFER** — blocked on the EXP-003/EXP-006 distributions. Default StandardScaler; switch to Robust if skew/outliers warrant, with the evidence recorded. |
| **Evidence** | Official brief p.4; [R35] |

---

# E. Recommendation methods

> All five brief-mandated baselines are **CANDIDATE**. CLAUDE.md §13 requires the
> winner to be chosen from experimental evidence, and [R26] is direct published
> evidence that under-tuned baselines are how this goes wrong. Each baseline gets
> the same tuning budget as the hybrid.

### E1. Global popularity

| Field | Assessment |
| --- | --- |
| **Purpose** | Non-personalised baseline: rank by enrollment count. |
| **Data requirement** | Interaction counts only. |
| **Advantages** | Trivial; no cold-start problem; **genuinely hard to beat on a 60-item catalogue** [R20][R28]; the necessary reference point for every other method. |
| **Limitations** | Zero personalisation; drives popularity bias and low coverage [R29]. |
| **Fit to EduPro** | Essential — both as a baseline and as the deepest fallback tier. |
| **Cost** | Trivial. |
| **Interpretability** | High ("popular with learners like you" is honest). |
| **Implementation** | Trivial. |
| **Decision status** | **CANDIDATE** (EXP-020) **+ ADOPT** as the insufficient-history fallback. |
| **Evidence** | Brief §13; [R20][R28] |

### E2. Content-based filtering

| Field | Assessment |
| --- | --- |
| **Purpose** | Recommend courses similar to those the learner already took. |
| **Data requirement** | Course attributes (category, type, level, rating) + learner history. |
| **Advantages** | Works from a single interaction — critical for the minimal-history tier; no item cold start; **directly explainable**, satisfying §16 naturally [R18]. |
| **Limitations** | Over-specialisation and low serendipity [R18]; with 12 categories and ~3.3 courses of history, will tend to return the learner's own category repeatedly. |
| **Fit to EduPro** | Strong, especially for sparse learners. Content signal is thin but clean; **`CourseName` is not usable** (58 distinct names over 60 courses, no text to embed). |
| **Cost** | Trivial — 60×60 similarity matrix. |
| **Interpretability** | **Highest of all methods.** |
| **Implementation** | Low. |
| **Decision status** | **CANDIDATE**. EXP-021. |
| **Evidence** | Brief p.4; [R18] |

### E3a. Similar-learner (user-user) over interaction history

| Field | Assessment |
| --- | --- |
| **Purpose** | Recommend what similar learners enrolled in — the brief's "similar learner profiles". |
| **Data requirement** | User×item interaction matrix. |
| **Advantages** | Explicitly mandated; captures preferences no content attribute encodes. |
| **Limitations** | **Similarity estimated from ~3.3 interactions per learner is very noisy**; 3,000² similarity matrix; fails entirely for 1-interaction learners. |
| **Fit to EduPro** | **Weak as specified**, for a reason that is structural rather than incidental — see E3b. |
| **Cost** | Moderate (9M pairs; still fast). |
| **Interpretability** | High conceptually. |
| **Implementation** | Low. |
| **Decision status** | **CANDIDATE**. EXP-022a. |
| **Evidence** | Brief p.5; [R21] |

### E3b. Similar-learner over engineered profile features

| Field | Assessment |
| --- | --- |
| **Purpose** | Same intent as E3a, but similarity computed over the learner's engineered feature vector rather than the sparse history vector. |
| **Data requirement** | The learner feature matrix already built for segmentation. |
| **Advantages** | Features aggregate the sparse history into a **denser, better-conditioned** representation; works for 1-interaction learners; reuses the segmentation feature pipeline, so no new machinery. |
| **Limitations** | Similarity is in feature space, not taste space — two learners with identical summary statistics may have disjoint tastes. |
| **Fit to EduPro** | **Potentially much better than E3a**, precisely because the profile aggregation is what makes the sparse data usable. |
| **Cost** | Moderate. |
| **Interpretability** | High — "learners with a similar learning profile". |
| **Implementation** | Low. |
| **Decision status** | **CANDIDATE**. EXP-022b. The E3a-vs-E3b comparison is one of the more interesting questions in this project. |
| **Evidence** | Engineering inference; the brief says "similar learner profiles" without specifying the similarity space. |

### E4. Item-based collaborative filtering

| Field | Assessment |
| --- | --- |
| **Purpose** | Recommend courses that co-occur with the learner's courses. |
| **Data requirement** | User×item interaction matrix. |
| **Advantages** | **The best-conditioned CF variant for this data shape**: each item has ~167 interactions (well-estimated) while each user has ~3.3 (barely estimated); the 60×60 similarity matrix is trivial and fully cacheable [R15][R16]; [R26] found tuned item-kNN beats many neural methods. |
| **Limitations** | Not named in the brief — must be justified as an addition; still needs ≥1 interaction. |
| **Fit to EduPro** | **Excellent on structural grounds.** A strong candidate to beat the mandated methods. |
| **Cost** | Trivial. |
| **Interpretability** | High ("learners who took X often take Y"). |
| **Implementation** | Low. |
| **Decision status** | **CANDIDATE**, high priority — added beyond the brief's minimum on [R26]'s evidence that strong simple baselines are essential. EXP-022c. |
| **Evidence** | [R15][R16][R26] |

### E5. Cluster popularity

| Field | Assessment |
| --- | --- |
| **Purpose** | Recommend what is popular within the learner's segment — the brief's cluster-aware recommendation. |
| **Data requirement** | Cluster assignments + within-cluster interaction counts. |
| **Advantages** | Mandated; connects the two halves of the project; works from zero interactions once a learner is assigned a segment; naturally more diverse than global popularity. |
| **Limitations** | **Quality is entirely contingent on the segmentation being meaningful**; degenerates to E1 if clusters are not behaviourally distinct. |
| **Fit to EduPro** | Central to the brief. Its performance is the de-facto test of whether the segmentation has practical value. |
| **Cost** | Trivial. |
| **Interpretability** | High. |
| **Implementation** | Low. |
| **Decision status** | **CANDIDATE**. EXP-023. |
| **Evidence** | Brief p.5 |

### E6. Weighted hybrid

| Field | Assessment |
| --- | --- |
| **Purpose** | Combine content, learner similarity, cluster popularity and rating relevance into one ranking. |
| **Data requirement** | All component scores, on a common scale. |
| **Advantages** | Burke's *weighted* strategy [R17]; per-component contributions are directly available, which is what makes honest explanation possible [R31]; each component can be ablated to measure its contribution. |
| **Limitations** | **Weights must be justified, not chosen** (§14); more components means more overfitting risk on a small validation set; score normalisation across heterogeneous components is a real design problem. |
| **Fit to EduPro** | The brief's implied target architecture — but it must *earn* its place against E1–E5. |
| **Cost** | Low. |
| **Interpretability** | **High, and uniquely so**: the score decomposition *is* the explanation. Requires the scorer to return components, not just a total. |
| **Implementation** | Moderate. |
| **Decision status** | **CANDIDATE**. EXP-024. **If it does not beat the best single baseline, that is the reported finding** (§6) — a simpler winning system is a legitimate outcome. |
| **Evidence** | Brief §14; [R17][R31] |

### E7. Switching hybrid (sparse-history tiers)

| Field | Assessment |
| --- | --- |
| **Purpose** | Route each learner to a different recommender based on history depth. |
| **Data requirement** | Per-learner **training-window** history length. |
| **Advantages** | Burke's *switching* strategy [R17]; directly implements §15; avoids applying a personalised method to a learner with no basis for personalisation, which is both dishonest and ineffective [R19]. |
| **Limitations** | Boundaries must be derived, not invented; discontinuities at boundaries; each tier needs separate evaluation. |
| **Fit to EduPro** | **Necessary, not optional** — a mean of 3.333 interactions means a large share of learners cannot be personalised honestly. |
| **Cost** | Trivial. |
| **Interpretability** | High, and honest: a minimal-history learner is told the basis is popularity. |
| **Implementation** | Moderate. |
| **Decision status** | **ADOPT** as architecture (§15 mandates tiering); **boundaries are CANDIDATE** — EXP-003 + EXP-025. |
| **Evidence** | §15; [R17][R19] |

### E8. Matrix factorisation for implicit feedback (ALS / iALS)

| Field | Assessment |
| --- | --- |
| **Purpose** | Learn latent user and item factors from implicit signals. |
| **Data requirement** | User×item matrix; confidence weights derived from interaction frequency. |
| **Advantages** | Strong on large implicit datasets; the preference/confidence separation is conceptually valuable [R13]. |
| **Limitations** | **Its confidence mechanism does not apply here**: EduPro has zero repeat `(user, course)` pairs (Phase 0, verified), so every observation has identical multiplicity and the confidence function is constant — it degenerates to weighted binary MF. Latent factors are also **not interpretable**, conflicting with §16. |
| **Fit to EduPro** | **Poor.** 60 items and ~3.3 interactions/user do not support latent-factor estimation, and the method's distinctive contribution is inoperative. |
| **Cost** | Moderate. |
| **Interpretability** | **Low** — the main disqualifier under §16. |
| **Implementation** | Moderate–high. |
| **Decision status** | **REJECT**, with reason recorded. Revisit only if Phase 2 contradicts the zero-repeat finding. |
| **Evidence** | [R13]; Phase 0 verified zero repeat pairs; §16 |

### E9. BPR (Bayesian Personalised Ranking)

| Field | Assessment |
| --- | --- |
| **Purpose** | Pairwise ranking optimisation from implicit feedback. |
| **Data requirement** | (user, positive, sampled negative) triples. |
| **Advantages** | Directly optimises ranking rather than reconstruction [R14]; a standard strong implicit baseline in the literature. |
| **Limitations** | Latent factors are uninterpretable (§16); 10,000 positives over 60 items under-identifies a conventional factor model; [R26] found tuned simple baselines beat learned methods on small data. |
| **Fit to EduPro** | Poor on sample-size and interpretability grounds. |
| **Cost** | Moderate–high. |
| **Interpretability** | Low. |
| **Implementation** | High — new dependency, tuning budget. |
| **Decision status** | **REJECT**, with reason recorded — the tuning budget is better spent giving E1–E5 a fair run, which [R26] identifies as the higher-value use of effort. |
| **Evidence** | [R14][R26]; §16 |

### E10. Neural / deep recommenders

| Field | Assessment |
| --- | --- |
| **Purpose** | Learn non-linear user-item interactions. |
| **Data requirement** | Large interaction volumes. |
| **Advantages** | State of the art at scale. |
| **Limitations** | [R26] reproduced only 7 of 18 neural papers and found most reproducible ones beaten by tuned simple baselines; uninterpretable (§16); 10,000 interactions is far too few. |
| **Fit to EduPro** | **Very poor.** |
| **Cost** | High. |
| **Interpretability** | Very low. |
| **Implementation** | High. |
| **Decision status** | **REJECT** — also aligns with §7 (no novel algorithms; use established methods and justify by experiment). |
| **Evidence** | [R26]; §7; §16 |

---

# F. Evaluation methods

### F1. Global temporal split

| Field | Assessment |
| --- | --- |
| **Purpose** | Train on all interactions before date *T*, test on interactions after *T*. |
| **Data requirement** | Reliable timestamps (`TransactionDate`, 358 distinct values). |
| **Advantages** | **Leakage-free by construction** — respects the global timeline [R25]; mirrors how a deployed system actually operates. |
| **Limitations** | At 3.333 interactions/learner, many learners will have no training history, no test interaction, or neither; the evaluable population may be small. |
| **Fit to EduPro** | **DEFER on viability**, but it is the methodologically correct primary — subject to EXP-004 confirming enough learners remain evaluable. |
| **Cost** | Trivial. |
| **Interpretability** | High. |
| **Implementation** | Low. |
| **Decision status** | **ADOPT as primary protocol**, conditional on EXP-004. Fallback rule pre-registered in `recommendation_evaluation_plan.md`. |
| **Evidence** | [R24][R25]; §9 |

### F2. Per-user leave-one-out (most recent held out)

| Field | Assessment |
| --- | --- |
| **Purpose** | Hold out each learner's most recent interaction. |
| **Data requirement** | Per-user ordering; ≥2 interactions to be evaluable. |
| **Advantages** | Maximises evaluable users; the field's most common protocol, so results are comparable with published work; explicitly suggested by §12. |
| **Limitations** | **Leaks by [R25]'s definition**: each user's cut is a different calendar date, so training contains interactions occurring after some users' test points. |
| **Fit to EduPro** | Practical, and necessary for comparability — but not defensible as the sole protocol. |
| **Cost** | Trivial. |
| **Interpretability** | High. |
| **Implementation** | Low. |
| **Decision status** | **ADOPT as secondary**, reported **explicitly labelled as leakage-bearing**. Divergence from F1 is itself a reportable finding reproducing [R24]. |
| **Evidence** | §12; [R24][R25] |

### F3. Random split

| Field | Assessment |
| --- | --- |
| **Purpose** | Randomly partition interactions. |
| **Advantages** | Simple; maximal data use. |
| **Limitations** | Ignores time entirely — the worst leakage case in [R25]; trains on the future to predict the past. |
| **Fit to EduPro** | Poor. |
| **Cost** | Trivial. |
| **Interpretability** | Moderate. |
| **Implementation** | Trivial. |
| **Decision status** | **REJECT** for headline results. May appear **once**, in a leakage-demonstration experiment showing how much the protocol inflates scores — which is a useful research-paper result, not a reported model metric. |
| **Evidence** | [R25] |

### F4. Precision@K · F5. Recall@K · F6. Hit Rate@K

| Field | Assessment |
| --- | --- |
| **Purpose** | Top-K accuracy: proportion recommended-and-relevant; proportion of relevant retrieved; whether any relevant item appears. |
| **Data requirement** | Ranked list + held-out ground truth. |
| **Advantages** | Precision is mandated by the brief; all three are standard and understood [R21][R22]. |
| **Limitations** | **With one held-out item, Precision@10 ≤ 0.10 and Precision@20 ≤ 0.05 by construction**, and Precision@K, Recall@K and HR@K become monotone transforms of one another — they carry the *same* information. Popularity-biased [R28][R29]. |
| **Fit to EduPro** | Report all three (brief compliance + convention) but **always against the analytical ceiling and the random reference** (`scripts/analytical_baselines.py`: random HR@10 ≈ 0.175). |
| **Cost** | Trivial. |
| **Interpretability** | High, **but actively misleading if reported without the ceiling.** |
| **Implementation** | Low. |
| **Decision status** | **ADOPT**, with mandatory co-reporting of the random baseline and the ceiling. |
| **Evidence** | Brief p.5; [R21][R22]; analytical baselines |

### F7. NDCG@K

| Field | Assessment |
| --- | --- |
| **Purpose** | Rank-sensitive accuracy with logarithmic position discounting. |
| **Data requirement** | Ranked list + graded or binary relevance. |
| **Advantages** | **Distinguishes rank 1 from rank 10, which HR@K cannot** — the single most informative accuracy metric available here [R23]. |
| **Limitations** | Less intuitive for stakeholders; with one relevant item it reduces to a reciprocal-log-rank measure. |
| **Fit to EduPro** | **Strong — the recommended primary accuracy metric** precisely because the Precision family is ceiling-limited. |
| **Cost** | Trivial. |
| **Interpretability** | Moderate — needs a sentence of explanation in the dashboard. |
| **Implementation** | Low. |
| **Decision status** | **ADOPT** as primary accuracy metric, with Precision@K retained for brief compliance. |
| **Evidence** | [R23]; §3 of CLAUDE.md permits additional metrics where appropriate. |

### F8. Catalogue coverage

| Field | Assessment |
| --- | --- |
| **Purpose** | Fraction of the 60 courses that ever appear in any learner's top-K. |
| **Data requirement** | All generated recommendation lists. |
| **Advantages** | Detects the failure mode accuracy metrics reward — routing everyone to the same few courses [R27][R29]; trivially measurable on a 60-item catalogue. |
| **Limitations** | High coverage is not automatically good; must be read alongside accuracy. |
| **Fit to EduPro** | **First-class metric.** The brief's stated goal is helping learners *discover* content; a high-accuracy, low-coverage system fails that goal. |
| **Cost** | Trivial. |
| **Interpretability** | High ("the system ever recommends 44 of 60 courses"). |
| **Implementation** | Trivial. |
| **Decision status** | **ADOPT** — a coverage collapse is disqualifying in the Phase 3 selection rule, not a footnote. |
| **Evidence** | [R27][R29] |

### F9. Intra-cluster similarity (behavioural consistency)

| Field | Assessment |
| --- | --- |
| **Purpose** | Mandated metric: how behaviourally consistent members of a segment are. |
| **Data requirement** | Cluster labels + feature matrix. |
| **Advantages** | Mandated by the brief; directly interpretable as segment tightness. |
| **Limitations** | The brief defines the metric's *purpose* but not its *formula*. |
| **Fit to EduPro** | Required. |
| **Cost** | Trivial. |
| **Interpretability** | High. |
| **Implementation** | Low. |
| **Decision status** | **ADOPT**; the exact formulation (mean pairwise within-cluster cosine/Euclidean similarity on behavioural features only, excluding demographics) is defined and justified in `segmentation_research.md` §5, since no official definition exists. |
| **Evidence** | Brief p.5 |

### F10. Engagement Lift (proxy)

| Field | Assessment |
| --- | --- |
| **Purpose** | Mandated metric: an estimate of impact. |
| **Data requirement** | Offline recommendation lists vs observed behaviour. |
| **Advantages** | Mandated; gives stakeholders a business-facing figure. |
| **Limitations** | **Cannot be a causal measurement.** The data is observational with no impressions, no control group and no counterfactual. Any figure is agreement with historical behaviour under an unknown incumbent policy. |
| **Fit to EduPro** | Required, but **hazardous** — it is the single most likely place for this project to make an unsupported claim. |
| **Cost** | Trivial. |
| **Interpretability** | High — dangerously so, since it invites causal misreading. |
| **Implementation** | Low. |
| **Decision status** | **ADOPT**, under strict conditions: named "Engagement Lift (Proxy)" everywhere including axis labels; accompanied by an explicit statement that it is not measured causal impact; defined in `recommendation_evaluation_plan.md` §7 before results are seen. |
| **Evidence** | Brief p.5; §6 |

---

# G. Explainability

### G1. Score-decomposition explanation (model-intrinsic)

| Field | Assessment |
| --- | --- |
| **Purpose** | Generate the explanation from the hybrid's actual per-component contributions. |
| **Data requirement** | The scorer must **return components, not just a total**. |
| **Advantages** | Explanation is true by construction — it cannot contradict the scoring logic, which is exactly what §16 requires; model-intrinsic in [R31]'s taxonomy; free at inference time. |
| **Limitations** | Constrains the architecture to interpretable components — which is a reason E8/E9/E10 were rejected; requires threshold rules for which components to mention. |
| **Fit to EduPro** | **Ideal, and it is why the weighted-hybrid architecture is preferred over latent-factor methods.** |
| **Cost** | Trivial. |
| **Interpretability** | Maximal. |
| **Implementation** | Low — **provided the interface is designed for it from the start**. Retrofitting is expensive. |
| **Decision status** | **ADOPT.** Phase 5 interface requirement decided here in Phase 1. |
| **Evidence** | §16; [R31][R32] |

### G2. Post-hoc explanation (template/LLM-generated)

| Field | Assessment |
| --- | --- |
| **Purpose** | Generate a plausible justification after ranking. |
| **Advantages** | Flexible, fluent prose; works with any model including opaque ones. |
| **Limitations** | **Can assert reasons the model did not use** — the precise failure §16 prohibits; adds a dependency and a failure mode for no accuracy gain. |
| **Fit to EduPro** | Unnecessary — G1 is available because the architecture is interpretable. |
| **Cost** | Low–high. |
| **Interpretability** | Superficially high, **actually unfaithful**. |
| **Implementation** | Moderate. |
| **Decision status** | **REJECT** — direct conflict with §16. |
| **Evidence** | §16; [R31] |

### G3. Tier-honest explanation

| Field | Assessment |
| --- | --- |
| **Purpose** | Make the explanation state the actual basis, including when that basis is weak. |
| **Advantages** | A minimal-history learner is told the recommendation is popularity-based rather than given a fabricated personalisation story; serves [R32]'s transparency and scrutability aims rather than persuasiveness. |
| **Limitations** | Less impressive-sounding — a product stakeholder may push back. |
| **Fit to EduPro** | **Required for honesty** given that a large share of learners will sit in low tiers. |
| **Cost** | Trivial. |
| **Interpretability** | High. |
| **Implementation** | Low. |
| **Decision status** | **ADOPT.** |
| **Evidence** | §6; §16; [R32] |

---

# H. Production engineering

### H1. joblib artifact persistence + version manifest

| Field | Assessment |
| --- | --- |
| **Purpose** | Persist scaler, encoder, clustering model, course representations and config so the app never retrains. |
| **Data requirement** | Fitted objects + the environment metadata they were fitted under. |
| **Advantages** | Standard for scikit-learn objects; efficient for large numpy arrays; satisfies §21 and §22. |
| **Limitations** | **Cross-version loading is explicitly unsupported** [R36]; pickle-family formats carry documented security risks and should only be loaded from trusted sources [R36]. |
| **Fit to EduPro** | Good — artifacts are produced by this repository's own pipeline and committed with it, so the trusted-source condition holds. |
| **Cost** | Trivial. |
| **Interpretability** | N/A. |
| **Implementation** | Low. |
| **Decision status** | **ADOPT**, with a mandatory manifest recording scikit-learn, numpy and Python versions plus the artifact set's own version, **verified on load with a loud failure on mismatch**. |
| **Evidence** | §22; [R36] |

### H2. Matched artifact set (CACE mitigation)

| Field | Assessment |
| --- | --- |
| **Purpose** | Ensure the segmentation model, the recommender built on it and the feature schema are always loaded as one consistent set. |
| **Advantages** | Mitigates the entanglement/CACE problem [R33] — changing the clustering silently changes the recommender's inputs and the hybrid's optimal weights. |
| **Limitations** | Adds release ceremony; all artifacts must be regenerated together. |
| **Fit to EduPro** | **Necessary.** ADR-0005 makes the stages composable, but composable is not independently swappable. |
| **Cost** | Trivial. |
| **Interpretability** | N/A. |
| **Implementation** | Low — one manifest file, one load-time check. |
| **Decision status** | **ADOPT.** |
| **Evidence** | [R33]; §22 |

### H3. Streamlit `st.cache_resource` / `st.cache_data`

| Field | Assessment |
| --- | --- |
| **Purpose** | Load artifacts once per process rather than per interaction. |
| **Advantages** | `st.cache_resource` is documented for unserializable globals such as ML models; `st.cache_data` for serializable return values, returning a copy per call [R37]. This is the mechanism that implements §21's "never retrain on startup". |
| **Limitations** | `cache_resource` shares one instance across sessions, so the cached object must not be mutated; cache invalidation on artifact change must be handled. |
| **Fit to EduPro** | Exactly the intended use case. |
| **Cost** | Trivial. |
| **Interpretability** | N/A. |
| **Implementation** | Trivial. |
| **Decision status** | **ADOPT** — `cache_resource` for models, `cache_data` for dataframes. |
| **Evidence** | §21; [R37] |

### H4. Test strategy modelled on the ML Test Score

| Field | Assessment |
| --- | --- |
| **Purpose** | Structure testing across data, model, infrastructure and monitoring rather than only unit-testing functions. |
| **Advantages** | [R34] provides 28 concrete tests from production experience; covers the surfaces §23 enumerates; catches the ML-specific failures ordinary unit tests miss. |
| **Limitations** | The full rubric includes monitoring practices that are out of scope for a non-live deployment. |
| **Fit to EduPro** | Good as a checklist to select from, not to adopt wholesale. |
| **Cost** | Low. |
| **Interpretability** | N/A. |
| **Implementation** | Moderate — the largest single testing effort. |
| **Decision status** | **ADOPT** the applicable subset; mapping in `production_research.md` §5. |
| **Evidence** | §23; [R33][R34] |

---

# Summary

| Status | Count | Entries |
| --- | --- | --- |
| **ADOPT** | 17 | A1, A2, B1, B2, C3, D4(vis), E1(fallback), E7(architecture), F1, F2, F4–F6, F7, F8, F9, F10, G1, G3, H1–H4 |
| **CANDIDATE** | 16 | A3, A4, A6, B3, B4, C1, C2, D1, D2, D3, D4(model), E1–E7 |
| **REJECT** | 5 | A5 (DBSCAN), E8 (iALS), E9 (BPR), E10 (neural), F3 (random split), G2 (post-hoc explanation) |
| **DEFER** | 2 | D5 (scaler choice), F1 (viability, pending EXP-004) |

**Every recommendation method that could win is CANDIDATE.** No segmentation
configuration and no recommendation method has been selected. The five rejections
are argued from structural properties of this dataset (zero repeat pairs, 60
items, 10,000 interactions) or from direct conflict with a CLAUDE.md rule, each
with the reason recorded and the reversal condition stated.
