# CLAUDE.md
# EduPro Student Segmentation & Personalized Course Recommendation System

## 1. PROJECT MISSION

Build an industry-grade, research-grade machine learning project for:

"Student Segmentation and Personalized Course Recommendation System for EduPro"

The project must be:
- scientifically defensible
- reproducible
- explainable
- modular
- maintainable
- deployable
- professionally documented
- suitable for internship submission
- suitable for future industry implementation

This is NOT a toy ML notebook.

The official Unified Mentor project documentation is the authoritative source for mandatory project requirements.

The original dataset is the authoritative source for data facts.

Do not invent requirements, data properties, metrics, findings, or results.

---

# 2. HARD DEADLINE

External hard deadline:

20 September 2026, 11:59 PM IST

Internal engineering freeze:

20 September 2026, 7:00 PM IST

The goal is to have the entire core system complete before the internal freeze so that the remaining time is reserved for:
- debugging
- deployment
- documentation
- validation
- packaging
- emergency fixes

Never sacrifice scientific validity merely to produce more UI features.

---

# 3. OFFICIAL REQUIREMENTS

The implementation must address all mandatory requirements in the official documentation.

Mandatory project components include:

## Learner analysis
- learner-level aggregation
- learner profiles
- demographic information
- behavioral information
- engagement-related features
- preference features

## Feature engineering
At minimum investigate:
- Age
- Gender
- Total courses enrolled
- Average courses per category
- Enrollment frequency
- Preferred course category
- Preferred course level
- Average rating of enrolled courses
- Average spending
- Diversity score
- Learning depth index

## Segmentation
- K-Means as primary clustering method
- Hierarchical clustering as validation/comparison
- Elbow method
- Silhouette analysis
- cluster profiling
- interpretable segment descriptions

## Recommendation
Investigate and evaluate:
- content-based filtering
- similar learner profiles
- course popularity within cluster
- rating-weighted relevance
- personalized ranking
- cold-start/fallback logic

## Evaluation
Investigate:
- Silhouette Score
- Intra-cluster similarity/behavioral consistency
- Recommendation Precision
- Engagement/impact proxy

Where scientifically appropriate, also evaluate:
- Recall@K
- Hit Rate@K
- NDCG@K
- coverage

## Application
Streamlit must provide:
- learner profile explorer
- cluster visualization dashboard
- personalized recommendations
- segment comparison
- learner selection
- assigned segment
- recommended learning paths
- filtering by category and level

## Deliverables
Must produce:
1. Research paper
2. Streamlit dashboard
3. Executive summary

Additional engineering deliverables:
- GitHub-ready repository
- README
- technical architecture
- experiment logs
- trained artifacts
- tests
- reproducible environment
- deployment-ready application
- final validation report

---

# 4. RESEARCH-FIRST POLICY

Do NOT immediately build the final product.

Use the following gated sequence:

PHASE 0
Project initialization

PHASE 1
Dense research and methodology investigation

PHASE 2
Dataset audit and EDA

PHASE 3
ML experimentation

PHASE 4
Model selection and architecture freeze

PHASE 5
Production implementation

PHASE 6
Validation, documentation, deployment, and submission

Do not proceed to the next phase until the current phase passes its acceptance criteria.

---

# 5. AUTONOMY POLICY

Operate autonomously.

Do not ask the user unnecessary questions.

Only stop and ask the user when:
- a required file is genuinely missing
- a required credential/action requires explicit user intervention
- a destructive operation requires confirmation
- the next step cannot logically proceed without external information

Otherwise diagnose problems and continue autonomously.

---

# 6. SCIENTIFIC INTEGRITY

NEVER:
- fabricate metrics
- fabricate research papers
- fabricate citations
- fabricate dataset statistics
- fabricate screenshots
- fabricate recommendation quality
- fabricate business impact
- claim causal impact from observational data
- claim real engagement improvement when only a proxy is available
- hide failed experiments
- selectively report only favorable results

If a model performs poorly:
- document it
- analyze why
- use the evidence to select or reject the method

---

# 7. NO NOVEL ALGORITHM REQUIREMENT

Do NOT attempt to invent a new ML algorithm.

This project is research-grade engineering, not novel algorithmic research.

Focus on:
- sound methodology
- strong baselines
- rigorous experimentation
- reproducibility
- validation
- explainability
- practical deployment

Use established algorithms and justify the final choice experimentally.

---

# 8. DATA INTEGRITY

The raw dataset must remain immutable.

Never overwrite original source files.

Create processed copies.

Always maintain:

data/raw/
data/processed/

Never silently alter:
- IDs
- original values
- transaction amounts
- original dates
- original categorical labels

All cleaning transformations must be explicit and reproducible.

---

# 9. DATA LEAKAGE

Leakage detection is mandatory.

Especially for recommendation evaluation.

When creating temporal evaluation:
- historical interactions may be used for features
- held-out future interactions must NOT influence historical features
- test interactions must not appear in training candidate data
- future information must not leak into user profile features

Document the exact temporal split methodology.

---

# 10. DEMOGRAPHIC FEATURES

Evaluate two segmentation variants:

Variant A:
Behavior + demographics

Variant B:
Behavior only

Do not assume in advance which produces the better representation.

Measure:
- cluster quality
- cluster stability
- behavioral consistency
- interpretability
- feature dominance

Use evidence to determine the production configuration.

Demographic features must not dominate the learner segmentation without justification.

---

# 11. TEACHERS SHEET

Treat the Teachers sheet as an explicit experiment.

Do NOT automatically include it in the final model.

Test:

Core model

versus

Core model + validated teacher-derived information

Only retain teacher-related signals if they provide defensible value and are methodologically appropriate.

Document the decision.

---

# 12. RECOMMENDATION EVALUATION

Use historical implicit interaction data.

A temporal evaluation framework should be investigated.

Where enough history exists per learner:
- use historical interactions for training
- hold out the most recent interaction for evaluation
- optionally use the second-most-recent interaction for validation

Users with insufficient interaction history must be handled separately.

Do not falsely evaluate one-interaction users as personalized recommendation users.

---

# 13. RECOMMENDATION BASELINES

At minimum investigate:

1. Global popularity
2. Content-based recommendation
3. Similar learner recommendation
4. Cluster popularity recommendation
5. Hybrid recommendation

The final method must be selected from actual experimental evidence.

---

# 14. HYBRID MODEL

A hybrid recommendation architecture may combine:
- content relevance
- learner similarity
- cluster popularity
- rating relevance
- personal preference match

Do not hardcode arbitrary weights merely because they seem reasonable.

Weights/logic must be justified by experiments or defensible methodology.

---

# 15. SPARSE USER STRATEGY

The dataset may contain sparse learner histories.

Create explicit recommendation tiers.

Conceptually:

Rich history
→ personalized hybrid recommendation

Moderate history
→ content + similarity + cluster

Minimal history
→ content + cluster/popularity

Insufficient history
→ popularity/rating/diversity fallback

The exact implementation must be justified by actual data analysis.

---

# 16. EXPLAINABILITY

Every displayed personalized recommendation should have a human-readable explanation.

Example:

"This course matches your preferred category and level and is frequently selected by learners with similar behavior."

Do not generate explanations that contradict the actual scoring logic.

Explanations must be evidence-backed.

---

# 17. PRIVACY

Do not unnecessarily expose:
- names
- emails
- personally identifying data

Use anonymized learner identifiers in the dashboard.

Email must never be a modeling feature.

Only expose information required by the intended workflow.

---

# 18. PRODUCTION ENGINEERING

The final application must NOT depend on manually executing notebooks.

The production system must have modular source code.

Use clear separation between:
- data ingestion
- validation
- feature engineering
- segmentation
- recommendation
- evaluation
- explainability
- application

Persist trained artifacts.

Provide reproducible execution instructions.

---

# 19. NOTEBOOK POLICY

Notebooks are allowed for:
- exploration
- visualization
- experimentation
- research

Notebooks must NOT be the only implementation.

Final inference must work through reusable Python modules.

---

# 20. DOCKER

DO NOT introduce Docker.

Do not create:
- Dockerfile
- docker-compose
- container-specific deployment logic

Use Python environment + Streamlit deployment.

---

# 21. STREAMLIT

The final application must be public-deployment ready.

Do not retrain the model every time the app starts.

Load persisted model artifacts when possible.

Use:
- clean navigation
- professional layout
- informative empty states
- understandable terminology
- stakeholder-friendly visualizations

---

# 22. MODEL ARTIFACTS

Persist all necessary artifacts, such as:
- scaler
- encoder
- clustering model
- course representations
- recommendation metadata
- feature schema
- model configuration

Artifacts must be version-consistent with the source code.

---

# 23. TESTING

At minimum test:
- data loading
- schema validation
- feature generation
- clustering inference
- recommendation inference
- filtering
- exclusion of already-enrolled courses
- explanation generation
- artifact loading
- app startup
- critical UI workflows

Also test failure/edge cases.

---

# 24. GIT

Create meaningful commits after major phase completions.

Suggested commit pattern:

phase-0/project-bootstrap
phase-1/research-complete
phase-2/data-audit-complete
phase-3/ml-experiments-complete
phase-4/architecture-freeze
phase-5/production-system
phase-6/final-validation

Do not push externally unless explicitly instructed.

---

# 25. DOCUMENTATION

Every important decision must be documented.

Maintain:

research/
decision_log.md
experiment_log.md
architecture_decision_record.md

Do not rely on conversation history for project knowledge.

---

# 26. FINAL QUALITY STANDARD

Before declaring completion, verify:

- Official requirements covered
- Dataset validated
- EDA completed
- Features justified
- Segmentation experimentally validated
- Recommendation baselines evaluated
- Temporal leakage addressed
- Sparse-user strategy implemented
- Explainability implemented
- Privacy handled
- Tests pass
- Streamlit works
- Public deployment works
- Research paper complete
- Executive summary complete
- README complete
- Architecture documented
- GitHub repository clean
- Reproducibility instructions work

Project is NOT DONE merely because Streamlit opens.

---

# 27. PHASE REPORTING

At the end of each phase, create:

research/PHASE_X_COMPLETE.md

Containing:

- objectives
- tasks completed
- evidence
- important findings
- unresolved issues
- artifacts created
- validation checks
- PASS/FAIL decision

Do not mark PASS without evidence.

---

# 28. STOP CONDITION

After every phase:
- evaluate acceptance criteria
- if PASS, report completion
- if FAIL, diagnose and repair
- rerun affected checks
- do not continue with known critical failures

---

# 29. PRIORITY ORDER

Priority 1:
Research paper

Priority 2:
Streamlit application

Priority 3:
Executive summary

Priority 4:
GitHub repository

Priority 5:
Technical documentation

Priority 6:
Experiments and research artifacts

Priority 7:
Tests

Priority 8:
Additional polish

Never improve cosmetic UI at the expense of research validity.

---

# 30. FINAL PRINCIPLE

Build less, but build it correctly.

Every major component should answer:

WHY does it exist?
WHAT evidence supports it?
HOW is it evaluated?
HOW does it fail?
HOW is it reproduced?
HOW can a real organization use it?