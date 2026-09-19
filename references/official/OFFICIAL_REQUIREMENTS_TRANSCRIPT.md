# Official Requirements — Verbatim Transcript

**Source:** `references/official/project offical detail.pdf`
**SHA-256:** `e794444490c19f85b8bef6534d844a629150971189eaf71448122ed402c4e8cf`
**Origin (printed in the page footer):** `https://projects.unifiedmentor.com/project_instructions?id=18743`
**Portal header:** Unified Mentor | Project Allotment Portal — dated 15/08/2026, 19:54
**Pages:** 6

> **Why this file exists.** The official PDF has **no embedded text layer** — every
> page is a raster image, so it cannot be searched, quoted or diffed
> programmatically. This file is a transcription of that PDF, produced by
> rendering each page (`scripts/render_official_pdf.py`) and reading it.
>
> **The PDF remains the authoritative source.** This transcript is a convenience
> for traceability. Where the two ever disagree, the PDF wins. Nothing here has
> been added, interpreted, summarised or reworded; the structure below mirrors
> the document's own headings.

---

## Page 1 — Title and background

**TECHNICAL DOCUMENTATION**

# Student Segmentation and Personalized Course Recommendation System for EduPro

Detailed guide and project requirements for the Student Segmentation and
Personalized Course Recommendation System for EduPro analysis.

### Background and Context

**Online learners are not homogeneous:**
- Some explore beginner courses across domains
- Some specialize deeply in one subject
- Others focus on career-oriented certifications

**Generic course recommendations fail to:**
- Maximize learner engagement
- Improve course completion
- Build long-term platform loyalty

**EduPro needs a data-driven personalization engine to:**
- Understand different learner types
- Recommend relevant courses
- Support personalized learning journeys

---

## Page 2 — Problem statement and dataset fields

### Problem Statement

**EduPro currently faces:**
- One-size-fits-all course recommendations
- Limited understanding of learner behavior patterns
- No structured learner segmentation framework

**As a result:**
- Learners struggle to discover relevant content
- Engagement and retention opportunities are lost

### Dataset Fields Utilized (High-Dimensional)

**Users Sheet**
- UserID
- Age
- Gender

*(continues on page 3)*

---

## Page 3 — Dataset fields (continued) and feature engineering

**Courses Sheet**
- CourseID
- CourseCategory
- CourseType
- CourseLevel
- CourseRating

**Transactions Sheet**
- UserID
- CourseID
- TransactionDate
- Amount

### Feature Engineering

Key engineered learner-level features include:

**Engagement Features**
- Total courses enrolled
- Average courses per category
- Enrollment frequency

**Preference Features**
- Preferred course category
- Preferred course level
- Average course rating enrolled

*(continues on page 4)*

---

## Page 4 — Behavioral features and methodology

**Behavioral Features**
- Average spending per learner
- Diversity score (number of categories explored)
- Learning depth index (beginner vs advanced ratio)

### Data Science Methodology (Step-by-Step)

**Learner-Level Aggregation**
- Aggregate transaction data at UserID level
- Create learner profiles combining demographics and behavior

**Data Preprocessing**
- Normalize numerical features
- Encode categorical variables
- Reduce noise from sparse enrollments

**Learner Segmentation (Clustering)**

Apply unsupervised algorithms:
- K-Means Clustering
- Hierarchical Clustering (validation)
- Elbow & Silhouette methods for cluster selection

**Personalized Recommendation Logic**

Build cluster-aware recommendations using:
- Content-based filtering

*(continues on page 5)*

---

## Page 5 — Recommendation logic (continued), evaluation, application

- Similar learner profiles
- Course popularity within cluster
- Rating-weighted relevance

### Evaluation & Validation

| METRIC | PURPOSE |
| --- | --- |
| Silhouette Score | Cluster quality |
| Intra-Cluster Similarity | Behavioral consistency |
| Recommendation Precision | Relevance |
| Engagement Lift (Proxy) | Impact estimate |

### Streamlit Web Application Requirements

**Core Modules**
- Learner profile explorer
- Cluster visualization dashboard
- Personalized course recommendations
- Segment comparison panels

**User Capabilities**

*(continues on page 6)*

---

## Page 6 — User capabilities, deliverables, conclusion

- Select a learner profile
- View assigned segment
- See recommended learning paths
- Filter recommendations by level or category

### Deliverables and Submission

- Research paper (EDA, insights, recommendations)
- Streamlit dashboard (live analytics)
- Executive summary for government stakeholders

### Conclusion

This project introduces student-centric intelligence to the EduPro platform. By
shifting focus from predicting course demand to understanding and personalizing
the learner journey, it enables EduPro to deliver meaningful, adaptive, and
engaging learning experiences, making it completely different in purpose and
methodology

*(The sentence ends without a full stop in the source document.)*

A button labelled **"Access Dataset"** appears at the end of page 6.

---

## Observations recorded at transcription time

These are *observations about the source documents*, not requirements. They are
recorded here because they materially affect scope, and are carried into
`research/decision_log.md` as open questions for later phases.

1. **The Teachers sheet is not in the official field list.** "Dataset Fields
   Utilized" names only the Users, Courses and Transactions sheets. The workbook
   physically contains a fourth sheet, `Teachers` (60 rows). This corroborates
   CLAUDE.md §11: teacher-derived signals are an explicit, opt-in experiment
   rather than a core input.

2. **Some workbook columns are not in the official field list.** The workbook's
   `Courses` sheet also carries `CoursePrice` and `CourseDuration`, and `Users`
   also carries `UserName` and `Email`, none of which the official document
   lists. `UserName`/`Email` are PII and are excluded from modelling by
   CLAUDE.md §17 regardless. Whether `CoursePrice`/`CourseDuration` are used is
   a Phase 2/3 decision that must be justified, not assumed.

3. **`Amount` and `CoursePrice` overlap.** Both are listed with 23 distinct
   values in the workbook inventory. Whether `Amount` is simply the course price
   at purchase time is a data-audit question for Phase 2 — it is not assumed here.

4. **"Executive summary for government stakeholders."** The deliverable is
   phrased this way in the source, and page 2 of the PDF carries an unrelated
   link chip reading "Toronto Government Parks, Forestry & Recreation". The
   latter appears to be portal template furniture rather than part of this
   project's brief. The deliverable is therefore treated as *an executive summary
   for non-technical decision-makers*; no claim about a government client is made
   anywhere in the project.

5. **No target cluster count, no metric thresholds.** The official document
   mandates *methods* (K-Means, hierarchical, elbow, silhouette) and *metrics*,
   but specifies no required k and no pass/fail metric values. All such values in
   this project must therefore come from experiment, not from assertion.
