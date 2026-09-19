"""Tests that keep the research paper honest.

Numeric traceability is checked by `scripts/verify_paper_claims.py`, which compares
77 artifact values against the text. These tests cover the properties that script
cannot: that the required structure is present, that every cited reference resolves,
and — most importantly — that the paper does not contain the kinds of claim the
data cannot support.

The forbidden-phrase test is the one that matters. It is easy to write "engagement
improved by 8%" when the artifact says "impact proxy 1.084 against random's 1.046";
the first sentence is a causal business claim the dataset cannot support, and no
numeric check would catch it.
"""

from __future__ import annotations

import re

import pytest

from edupro import config

PAPER = config.DOCS_DIR / "research_paper.md"
HTML = config.DOCS_DIR / "research_paper.html"

REQUIRED_SECTIONS = [
    "Abstract", "Introduction", "Problem Statement", "Project Objectives",
    "Dataset Description", "Data Quality Assessment", "Exploratory Data Analysis",
    "Literature Review", "Feature Engineering", "Learner Segmentation Methodology",
    "Segmentation Experiments", "Recommendation System Methodology",
    "Recommendation Baselines", "Hybrid Recommendation Method",
    "Temporal Evaluation Methodology", "Experimental Results", "Error Analysis",
    "Explainability", "Privacy Considerations", "Production Architecture",
    "Limitations", "Practical and Industry Implications", "Future Work",
    "Conclusion", "References",
]

EVIDENCE_TAGS = [
    "[OBSERVED]", "[MODEL]", "[EXPERIMENT]",
    "[INTERPRETATION]", "[ENGINEERING]", "[FUTURE]",
]


@pytest.fixture(scope="module")
def paper() -> str:
    assert PAPER.exists(), f"{PAPER} is missing"
    return PAPER.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("section", REQUIRED_SECTIONS)
def test_required_section_is_present(paper: str, section: str):
    headings = re.findall(r"^## (.+)$", paper, flags=re.M)
    assert any(section.lower() in h.lower() for h in headings), f"missing section: {section}"


def test_every_evidence_class_is_used(paper: str):
    """The paper's central promise is that claim types are distinguished."""
    for tag in EVIDENCE_TAGS:
        assert f"**{tag}**" in paper, f"evidence class {tag} is never used"


def test_the_headline_finding_is_stated_in_the_abstract(paper: str):
    abstract = paper.split("## 2. Introduction")[0]
    assert "no method is significantly better than random" in abstract.lower()


# ---------------------------------------------------------------------------
# No unsupported claims
# ---------------------------------------------------------------------------
FORBIDDEN = [
    # Causal business claims the dataset cannot support.
    r"engagement (?:increased|improved|rose|grew)",
    r"increased engagement by",
    r"improved engagement by",
    r"boost(?:ed|s)? (?:engagement|retention|completion)",
    r"drove? (?:a )?\d+% ",
    r"resulted in (?:a )?\d+%",
    r"lift in revenue",
    # Claims of significance the tests did not support.
    r"significantly outperform",
    r"statistically significant improvement",
]


@pytest.mark.parametrize("pattern", FORBIDDEN)
def test_paper_makes_no_unsupported_causal_claim(paper: str, pattern: str):
    matches = re.findall(pattern, paper, flags=re.I)
    assert not matches, f"unsupported claim pattern {pattern!r} found: {matches[:3]}"


def test_the_impact_metric_is_labelled_a_proxy(paper: str):
    """The brief requires an impact metric; the data cannot support a causal one."""
    assert "impact proxy" in paper.lower() or "Engagement Lift is an **impact proxy**" in paper


def test_the_impact_proxy_never_appears_without_its_reference(paper: str):
    """1.084 means nothing without the 1.046 a random ranker scores."""
    for line in paper.splitlines():
        if "1.084" in line:
            assert "1.046" in line, f"proxy quoted without its random reference: {line.strip()}"


def test_quality_figures_are_paired_with_the_random_baseline(paper: str):
    """The deployed method's NDCG must never be quoted without random's."""
    for line in paper.splitlines():
        if "0.1138" in line and "|" not in line:  # prose, not a table row
            assert "0.1102" in line or "random" in line.lower(), (
                f"deployed NDCG quoted without its reference: {line.strip()}"
            )


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------
def test_every_cited_reference_is_listed(paper: str):
    body, _, references = paper.partition("## 25. References")
    assert references, "reference section not found"
    cited = set(re.findall(r"\[R\d+[a-z]?\]", body))
    listed = set(re.findall(r"\*\*(\[R\d+[a-z]?\])\*\*", references))
    missing = cited - listed
    assert not missing, f"cited but not listed: {sorted(missing)}"


def test_listed_references_carry_an_identifier(paper: str):
    """A reference without a DOI, arXiv id or venue cannot be checked by a reader."""
    _, _, references = paper.partition("## 25. References")
    entries = re.findall(r"\*\*\[R\d+[a-z]?\]\*\*(.+?)(?=\n\n|\Z)", references, flags=re.S)
    assert len(entries) >= 35, f"only {len(entries)} references listed"
    unidentifiable = [
        e.strip()[:60] for e in entries
        if not any(marker in e for marker in ("DOI:", "arXiv:", "*", "documentation"))
    ]
    assert not unidentifiable, f"references without an identifier: {unidentifiable}"


def test_reference_keys_are_unique(paper: str):
    _, _, references = paper.partition("## 25. References")
    listed = re.findall(r"\*\*(\[R\d+[a-z]?\])\*\*", references)
    assert len(listed) == len(set(listed)), "a reference key is listed twice"


# ---------------------------------------------------------------------------
# Artifact traceability
# ---------------------------------------------------------------------------
def test_paper_names_the_artifacts_its_tables_come_from(paper: str):
    """Each results section must point at the file a reader can open."""
    for artifact in (
        "artifacts/phase2_audit.json",
        "artifacts/segmentation/segmentation_results.json",
        "artifacts/recommendation/recommendation_results.json",
        "artifacts/architecture/architecture_validation.json",
    ):
        assert artifact in paper, f"paper never cites {artifact}"


def test_every_referenced_figure_file_exists(paper: str):
    """No figure may be cited that was not generated."""
    figures = set(re.findall(r"artifacts/(?:eda|segmentation|recommendation)/[\w\d_]+\.png", paper))
    assert figures, "the paper cites no figures"
    missing = [f for f in figures if not (config.PROJECT_ROOT / f).exists()]
    assert not missing, f"cited figures do not exist: {missing}"


def test_the_source_checksum_is_stated(paper: str):
    assert config.RAW_WORKBOOK_SHA256 in paper, "the paper does not state the data checksum"


# ---------------------------------------------------------------------------
# Submission copy
# ---------------------------------------------------------------------------
def test_the_html_submission_copy_is_built(paper: str):
    assert HTML.exists(), "run scripts/build_paper.py"
    markup = HTML.read_text(encoding="utf-8")
    assert markup.startswith("<!DOCTYPE html>")
    assert "<table>" in markup
    assert 'class="tag tag-' in markup, "evidence tags were not rendered"
    assert "**[" not in markup, "raw markdown leaked into the rendered document"


def test_the_html_copy_is_self_contained():
    """A submission copy that fetches fonts or scripts breaks offline."""
    markup = HTML.read_text(encoding="utf-8")
    external = re.findall(r'(?:src|href)="(https?://[^"]+)"', markup)
    assert not external, f"external resources referenced: {external[:3]}"
