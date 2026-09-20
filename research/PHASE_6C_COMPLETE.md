# Phase 6C — Executive Summary — COMPLETE

**Phase:** 6C — executive summary
**Date:** 20 September 2026
**Decision:** ✅ **PASS**
**Deliverable:** `docs/executive_summary.md` (3,945 words)
**Next phase:** Phase 6D — public deployment and final packaging (**not started; awaiting go-ahead**)

---

## 1. Objective

Write an executive-level document for non-technical stakeholders — government
stakeholders, education administrators, EduPro management and programme reviewers —
covering thirteen specified topics in simple language, without overclaiming business
impact, using only actual project findings, and labelling every proxy metric.

Explicitly **not** a condensed copy of the research paper.

---

## 2. The writing problem this phase had to solve

The central finding is negative: on EduPro's data, no recommendation method beats
random selection. For a technical reader that is a clean, interesting result. For an
executive audience it is a document that could easily fail in one of two opposite
ways:

- **Burying it** — leading with segments and dashboards, mentioning the limitation
  on page nine. Technically honest, practically deceptive.
- **Overcorrecting** — presenting the project as a failure, which is also untrue and
  would waste a working segmentation and a tested system.

**The framing adopted:** the study tested whether EduPro's data can support
personalisation, found that it cannot *yet*, and identified exactly what is missing.
That is a genuine, valuable and actionable result — it saves EduPro from launching
something that looks impressive and performs at chance — and it is stated in the
first 200 words rather than the last.

| | |
| --- | --- |
| Segmentation | ✅ Works, usable today |
| Recommendations | ⚠️ Built and tested; not better than random on current data |

---

## 3. Coverage of the thirteen required topics

| # | Required topic | Section | Substance |
| --- | --- | --- | --- |
| 1 | Executive problem | §1 | Two business questions plus the one that is usually skipped: does the data support them |
| 2 | Why generic recommendation is insufficient | §2 | Four concrete reasons: 60-course catalogue, flat popularity, half the base with one course, no explanations |
| 3 | What data was analysed | §3 | Scale, quality, three shaping facts, and the synthetic-data caveat |
| 4 | Learner types discovered | §4 | Four types with plain-language figures; the one actionable group; an explicit statement of what the other three are *not* |
| 5 | How personalisation works | §5 | The four-tier routing table framed as "how much do we know about this learner" |
| 6 | What the system provides | §6 | Outputs, five verified guarantees, the dashboard |
| 7 | What evidence supports it | §7 | The honest comparison, plus a confidence table separating what can and cannot be claimed |
| 8 | How learners receive recommendations | §8 | Current state, integration path, and what *not* to say to learners |
| 9 | Supporting platform decisions | §9 | Four capabilities usable now, including catalogue diagnostics |
| 10 | Privacy | §10 | Design, adversarial verification, the demographic position |
| 11 | Limitations | §11 | Eight, ordered by importance, unsoftened |
| 12 | Implementation roadmap | §12 | Four phases with a recommendation *against* premature rollout |
| 13 | Future expansion | §13 | Four directions |

---

## 4. Honesty controls

### 4.1 The impact claim, refused explicitly

The document does not merely avoid claiming engagement improvement — it states that
the claim cannot be made:

> **We cannot tell you that this system increases engagement, completion or
> retention. No such measurement exists in EduPro's data.**

The official brief requires an impact metric, so one is reported and labelled:

| **Engagement Lift — a PROXY measure, not a business outcome** | |
| --- | --- |
| Our system | 1.084 |
| Picking at random | 1.046 |

Both values always appear together, with an explanation of what the proxy does and
does not measure.

### 4.2 The comparison that makes the result honest *and* useful

The evidence table compares three columns rather than two:

| Measure | Our system | Random | A popular-courses list |
| --- | --- | --- | --- |
| Next course in the top ten | 36 in 100 | 35 in 100 | 33 in 100 |
| Share of catalogue reachable | **100%** | 100% | **32%** |

**[Design decision]** The third column was added after reviewing a two-column draft.
Against random, the system has no accuracy advantage — that is the honest headline.
But a "most popular courses" list is the realistic alternative EduPro would otherwise
build, and against *that* the system has a real and explicable advantage: it can
surface all 60 courses where a popularity list reaches only 19. Omitting that column
would have understated a genuine benefit as badly as omitting the random column
would have overstated one.

### 4.3 A confidence table rather than prose hedging

§7 ends with an explicit five-row table separating claims by confidence, including
two rows reading "Not demonstrated" and "Cannot be measured with current data". A
stakeholder skimming for what they may repeat in a board paper finds it in one place.

### 4.4 Guarding against an overstated segmentation

§4 states plainly that three of the four learner types are largely course-level
groupings, and that a slide claiming EduPro has found "four learner personas" would
go beyond the evidence. This anticipates the most likely misuse of the document.

---

## 5. Verification

### 5.1 Numeric traceability

`scripts/verify_paper_claims.py` now checks both documents:

```
Checking 77 numeric claims in research_paper.md against the artifacts
Checking 19 numeric claims in executive_summary.md

All 77 paper values and 19 summary values appear verbatim in their documents.
```

The summary's checks are formatted the way a stakeholder reads them — "36 in 100",
"19 of the 60", "54%" — and computed from the artifacts, so a rounded figure that
rounds the wrong way fails.

### 5.2 Forbidden-claim tests, refined

`tests/test_paper.py` now applies the nine forbidden claim patterns to the summary as
well as the paper — and the test itself was **improved during this phase**.

**[Finding]** The original test flagged this correct sentence in the summary:

> Any claim of the form "engagement improved by X%" would be invented.

That is the document *refusing* the claim. A test that cannot distinguish an
assertion from its disavowal forces vaguer writing — the author's only fix is to stop
naming the thing being refused, which makes the document worse.

**[Fix]** A forbidden phrase now counts as a violation only when **asserted**: the
line must not contain a negation marker ("cannot", "would be invented", "no such",
"does not", …). The marker list is deliberately narrow, because an author trying to
smuggle an overclaim past the test would have to write a negation into their own
claim, which defeats it.

**[Verified able to fail]** Re-tested against six synthetic violating sentences (all
caught) and three disavowals (all correctly allowed).

### 5.3 "Not a copy of the paper" — tested

A test asserts the summary is under half the paper's length and contains **no
unexplained technical terms**: `NDCG@10`, `silhouette`, `bootstrap Jaccard`,
`Adjusted Rand Index`, `permutation null`, `K-Means`, `confidence interval`. It is
3,945 words — **35% of the paper** — and uses none of them.

### 5.4 Full suite

| Check | Result |
| --- | --- |
| Test suite | ✅ **331 passed** (304 + 27 new) |
| Numeric claims across both documents | ✅ **96 of 96** |
| Thirteen required topics | ✅ parametrised test |
| Forbidden claims | ✅ 9 patterns, applied to both documents, verified able to fail |
| Proxy labelled and paired with its reference | ✅ |
| Summary is not a paper extract | ✅ 35% length, 0 unexplained technical terms |
| Raw workbook SHA-256 | ✅ unchanged |

---

## 6. PASS / FAIL

### ✅ **PASS**

| Criterion | Evidence |
| --- | --- |
| Executive-level document for non-technical stakeholders | 3,945 words, plain language, no unexplained technical terms |
| All thirteen topics covered | §3 |
| Not a copy of the research paper | Tested: 35% length, zero technical-term overlap |
| Simple language | No jargon without immediate explanation |
| Never overclaims business impact | The impact claim is explicitly refused; 9 patterns tested |
| Uses actual project findings | 19 figures machine-checked against artifacts |
| Proxy metrics clearly identified | Labelled in the table header, in the text, and in a closing note |

### CLAUDE.md compliance

| § | Requirement | Status |
| --- | --- | --- |
| 6 | No fabricated metrics | ✅ Every figure traced to an artifact |
| 6 | No causal claim from observational data | ✅ Refused explicitly and enforced by test |
| 17 | Privacy | ✅ §10 states the position and the adversarial verification |
| 25 | Decisions documented | ✅ D-061, D-062 |
| 27 | Phase report with evidence | ✅ This document |
| 29 | Executive summary is Priority 3 | ✅ Delivered after the paper and the application |

---

## 7. Unresolved issues

1. **The system still does not beat random.** Unchanged; now stated for a third
   audience.
2. **Not yet deployed publicly.** Phase 6D.
3. **Gender gap** is now disclosed in the executive summary (§10) but still not
   surfaced in the dashboard itself.
4. **Phase 0's two open items remain open**: the empty `claude.md.txt`, and the
   git-identity/authorship question. The summary carries no byline, so this blocks
   the paper rather than this document — but both need settling before submission.

   **RESOLVED 20 September 2026: the author is Kartik (`kartikshreekumar2006@gmail.com`), confirmed by the project owner. `pyproject.toml`, the paper byline and the rendered paper now all say so.**
5. **No PDF rendering** of the executive summary. The research paper has an HTML
   submission copy; the summary is currently Markdown only. Producing a matching
   HTML would be a small addition if a formatted copy is wanted.

---

## 8. Stop

Per CLAUDE.md §28, work **stops here**. Phase 6D will not begin automatically.

🔒 The ML design remains frozen. This phase produced one document and refined one
test; it changed no model behaviour.
