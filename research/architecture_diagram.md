# Architecture Diagrams

Visual companion to `research/ARCHITECTURE_FREEZE.md` and
`docs/technical_architecture.md`. Mermaid renders natively on GitHub.

Version `edupro-1.0.0`, frozen 19 September 2026.

---

## 1. End-to-end system

```mermaid
flowchart TD
    RAW["data/raw/EduPro Online Platform.xlsx<br/>IMMUTABLE · sha256 ed555e46…8cc0"]

    RAW --> LOAD["loader.load_all()<br/><b>PII dropped here</b>"]
    LOAD --> VAL["validation.validate_all()<br/>12 check families · 0 errors"]
    VAL --> JOIN["joins.build_interactions()<br/>10,000 interactions"]
    JOIN --> SPLIT{"global_temporal_split<br/>70th / 80th percentile dates"}

    SPLIT -->|"&lt; 2025-09-12"| TRAIN["TRAIN<br/>features · popularity · similarity"]
    SPLIT -->|"09-12 → 10-18"| VALID["VALIDATION<br/>all model selection"]
    SPLIT -->|"≥ 2025-10-18"| TEST["TEST<br/>opened exactly once"]

    TRAIN --> FEAT["build_learner_features()<br/>25 features · 4 blocks"]
    FEAT --> REP["build_representation('B_proportion')<br/>StandardScaler"]
    REP --> KM["KMeans k=4 · seed 42"]
    KM --> SEG["4 learner segments"]

    FEAT --> CTX["FitContext"]
    TRAIN --> CTX
    SEG --> CTX
    CTX --> REC["TieredRecommender"]

    REC --> EVAL["protocol.evaluate()"]
    VALID --> EVAL
    TEST --> EVAL
    EVAL --> ART["artifacts/*.json<br/>+ research/*.md"]

    SEG --> PERSIST["models/ + artifacts/<br/>joblib · parquet · json"]
    REC --> PERSIST
    PERSIST --> APP["Streamlit app<br/><b>loads only · never fits</b>"]

    classDef frozen fill:#1f4e79,stroke:#0d2c47,color:#fff
    classDef guard fill:#7a1f1f,stroke:#4a0f0f,color:#fff
    class KM,REC frozen
    class RAW,LOAD,TEST guard
```

---

## 2. Segmentation layer

```mermaid
flowchart LR
    F["learner features<br/>25 columns"]

    F --> B1["Engagement · 4<br/>total_courses<br/>avg_courses_per_category<br/>enrollment_frequency<br/>activity_span_days"]
    F --> B2["Behavioural · 6<br/>avg_course_rating · avg_spend<br/>diversity_score · learning_depth_index<br/>free_ratio · diversity_ratio"]
    F --> B3["Category · 12<br/>cat_share_* (row-normalised)"]
    F --> B4["Level · 3<br/>one-hot"]
    F -.->|"EXCLUDED<br/>ARI 1.000 · 0.04% variance"| B5["Demographics<br/>age · gender"]

    B1 --> SC["StandardScaler"]
    B2 --> SC
    B3 --> SC
    B4 --> SC

    SC --> KM["KMeans<br/>k=4 · k-means++ · n_init=10"]

    KM --> C0["C0 · 27.0%<br/>Beginner-level<br/>Single-course"]
    KM --> C1["C1 · 19.7%<br/>Category-repeating<br/>High-volume · 9.65 courses"]
    KM --> C2["C2 · 33.2%<br/>Advanced-level<br/>Non-repeating"]
    KM --> C3["C3 · 20.1%<br/>Intermediate-level<br/>Single-session"]

    B5:::rejected
    classDef rejected fill:#3a3a3a,stroke:#666,color:#bbb,stroke-dasharray: 5 5
```

**Why k=4 and not the highest-silhouette k:**

```mermaid
flowchart TD
    S["Silhouette sweep k=2…10"] --> BEST["Highest silhouette: k=10 (0.2685)"]
    BEST --> G1{"Every cluster ≥ 5%?"}
    G1 -->|"No — smallest 4.4%"| R1["REJECTED"]
    BEST --> G2{"Every cluster Jaccard ≥ 0.60?"}
    G2 -->|"No — 5 of 10 fail"| R2["REJECTED"]

    S --> PASS["Passing k: 2, 3, 4"]
    PASS --> PICK["Highest silhouette among them<br/><b>k = 4 · 0.1946</b>"]

    classDef bad fill:#7a1f1f,stroke:#4a0f0f,color:#fff
    classDef good fill:#1f4e79,stroke:#0d2c47,color:#fff
    class R1,R2 bad
    class PICK good
```

---

## 3. Recommendation routing

```mermaid
flowchart TD
    U["Learner"] --> H{"Training-window<br/>history length<br/><i>(leakage control L3)</i>"}

    H -->|"0<br/>350 learners · 11.7%"| T0["<b>insufficient</b><br/>DiversifiedFallback"]
    H -->|"1<br/>1,514 · 50.5%"| T1["<b>minimal</b><br/>ContentBased"]
    H -->|"2–8<br/>731 · 24.4%"| T2["<b>moderate</b><br/>ClusterPopularity"]
    H -->|"≥ 9<br/>405 · 13.5%"| T3["<b>rich</b><br/>ClusterPopularity"]

    T0 --> CAND
    T1 --> CAND
    T2 --> CAND
    T3 --> CAND

    CAND["Candidate generation<br/>60 courses − training enrollments<br/><i>(leakage control L2)</i>"]
    CAND --> SCORE["Score + component decomposition"]
    SCORE --> RANK["Deterministic ranking<br/>ties broken by catalogue index"]
    RANK --> TOPK["Top-K"]
    TOPK --> EXPL["Explanation from<br/>Scores.contribution_at()<br/><b>tier-honest</b>"]

    classDef fallback fill:#5a4a1f,stroke:#3a2f0f,color:#fff
    class T0 fallback
```

**Coverage of the routing:** 3,000 of 3,000 learners receive a recommendation.
Minimum candidate pool 45 of 60, so top-10 can always be filled. Zero empty pools.

---

## 4. Leakage controls

```mermaid
flowchart LR
    subgraph TRAINING["TRAINING WINDOW — everything fitted here"]
        L1["L1 features"]
        L5["L5 popularity"]
        L3["L3 tier assignment"]
        L4["L4 similarity structures"]
    end

    subgraph HELDOUT["HELD-OUT — read only at scoring time"]
        REL["relevant items"]
    end

    L2["L2 candidate exclusion<br/>uses TRAINING enrollments only"]
    L6["L6 test window opened once"]

    TRAINING --> MODEL["Fitted model"]
    MODEL --> SCORES["Ranked list"]
    L2 --> SCORES
    SCORES --> COMPARE["Compare"]
    HELDOUT --> COMPARE
    HELDOUT -.->|"NEVER"| TRAINING

    VERIFY["verify_leakage_controls()<br/>runs L1–L6 in-run<br/><i>tested able to fail</i>"] --> COMPARE

    classDef forbidden stroke:#7a1f1f,stroke-width:3px,color:#f88
```

Using **full** history for candidate exclusion would leak: removing the held-out
course from the candidate pool tells the model which course to avoid, which is
information about the answer.

---

## 5. Evidence flow — how decisions were reached

```mermaid
flowchart TD
    P1["<b>Phase 1</b> Research<br/>40 references · pre-registered<br/>metrics, rules and thresholds"]
    P2["<b>Phase 2</b> Audit<br/>permutation testing<br/><b>finds: no choice signal</b>"]
    P3A["<b>Phase 3A</b> Segmentation<br/>10 representations × 9 k values<br/>+ stability + dominance"]
    P3B["<b>Phase 3B</b> Recommendation<br/>11 methods × 2 protocols<br/>+ paired bootstrap"]
    P4["<b>Phase 4</b> Freeze<br/>decision matrices<br/>+ assembled-architecture measurement"]

    P1 --> P2 --> P3A --> P3B --> P4

    P1 -.->|"random baseline mandatory<br/>coverage co-primary"| P3B
    P2 -.->|"54% single-interaction<br/>→ tiering is required"| P3B
    P2 -.->|"popularity near-uniform<br/>→ low ranking information"| P3B
    P3A -.->|"segments"| P3B
    P3B -.->|"parsimony rule rejects hybrid"| P4

    P4 --> FREEZE["🔒 edupro-1.0.0"]

    classDef finding fill:#7a1f1f,stroke:#4a0f0f,color:#fff
    class P2 finding
```

---

## 6. The finding that governs presentation

```mermaid
flowchart LR
    subgraph RESULT["Test window · 791 learners · NDCG@10"]
        R["random<br/><b>0.1102</b>"]
        H["hybrid 0.1206"]
        C["content_based 0.1191"]
        CP["cluster_popularity 0.1138"]
        GP["global_popularity 0.1072"]
        RT["rating 0.1034"]
        UH["user_user_history 0.0947"]
    end

    RESULT --> SIG{"Paired bootstrap<br/>vs random"}
    SIG --> Z["<b>0 of 11 significant.</b><br/>Every 95% CI contains zero.<br/>Random ranks 7th of 12."]

    Z --> SELECT["Selection therefore made on<br/>robustness · interpretability<br/>coverage · honest degradation"]

    classDef ref fill:#7a1f1f,stroke:#4a0f0f,color:#fff
    class R,Z ref
```

Any dashboard or report figure quoting recommendation quality must show the random
reference beside it.

---

## 7. Artifact dependency — why the set is versioned together

```mermaid
flowchart TD
    SCALER["scaler.joblib"] --> CLUSTERER["clusterer.joblib"]
    CLUSTERER --> PROFILES["cluster_profiles.parquet"]
    CLUSTERER --> POP["popularity.parquet<br/><i>per-cluster counts</i>"]
    POP --> RECOM["ClusterPopularity scorer"]
    PROFILES --> UI["segment names in the UI"]
    SCHEMA["feature_schema.json"] --> SCALER
    MANIFEST["manifest.json<br/>artifact_set_version<br/>library versions<br/>workbook sha256"] -.->|"verified at load"| SCALER
    MANIFEST -.-> CLUSTERER
    MANIFEST -.-> POP

    NOTE["Re-fitting the clusterer invalidates<br/>popularity.parquet AND any hybrid weights<br/>tuned against it — the CACE problem"]
    CLUSTERER -.-> NOTE

    classDef warn fill:#5a4a1f,stroke:#3a2f0f,color:#fff
    class NOTE warn
```
