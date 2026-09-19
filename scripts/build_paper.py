"""Render the research paper to a submission-ready HTML document.

`docs/research_paper.md` is the source of truth; this script only presents it.
Keeping the content in Markdown means the paper diffs cleanly in review and cannot
drift from a separately maintained "final" copy.

The output is a single self-contained file with no external fonts, scripts or
stylesheets, so it opens identically offline and on any machine, and prints to PDF
from a browser (Ctrl/Cmd-P → Save as PDF) with sensible page breaks.

Usage
-----
    python scripts/build_paper.py
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import mistune

from edupro import config

SOURCE = config.DOCS_DIR / "research_paper.md"
OUTPUT = config.DOCS_DIR / "research_paper.html"

#: The evidence tags the paper uses, and the colour each is rendered in. Keeping
#: the mapping here rather than in the Markdown means the tags stay readable as
#: plain text in the source document.
EVIDENCE_TAGS: dict[str, str] = {
    "OBSERVED": "observed",
    "MODEL": "model",
    "EXPERIMENT": "experiment",
    "INTERPRETATION": "interpretation",
    "ENGINEERING": "engineering",
    "FUTURE": "future",
}

STYLE = """
:root {
  --ink: #16191d;
  --muted: #5b6470;
  --rule: #d8dde3;
  --accent: #1f4e79;
  --bg: #ffffff;
  --panel: #f6f8fa;
  --observed: #1f6f8b;
  --model: #6b4c9a;
  --experiment: #1f6b45;
  --interpretation: #8a5a1f;
  --engineering: #44506b;
  --future: #6b6b6b;
}
* { box-sizing: border-box; }
body {
  margin: 0 auto;
  padding: 3rem 1.5rem 6rem;
  max-width: 52rem;
  background: var(--bg);
  color: var(--ink);
  font-family: "Charter", "Bitstream Charter", "Sitka Text", Cambria, Georgia, serif;
  font-size: 16px;
  line-height: 1.62;
  text-rendering: optimizeLegibility;
}
h1, h2, h3, h4 {
  font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
  line-height: 1.25;
  color: var(--ink);
}
h1 { font-size: 1.95rem; margin: 0 0 .4rem; letter-spacing: -.01em; }
h2 {
  font-size: 1.3rem; margin: 3rem 0 .9rem;
  padding-bottom: .4rem; border-bottom: 2px solid var(--rule);
}
h3 { font-size: 1.05rem; margin: 2rem 0 .6rem; color: var(--accent); }
h4 { font-size: .97rem; margin: 1.4rem 0 .5rem; }
p { margin: 0 0 1rem; }
a { color: var(--accent); }
hr { border: 0; border-top: 1px solid var(--rule); margin: 2.5rem 0; }
code {
  font-family: "Cascadia Mono", Consolas, "SF Mono", Menlo, monospace;
  font-size: .86em; background: var(--panel);
  padding: .1em .35em; border-radius: 3px;
}
pre {
  background: var(--panel); border: 1px solid var(--rule); border-radius: 6px;
  padding: .9rem 1rem; overflow-x: auto; font-size: .82rem; line-height: 1.5;
}
pre code { background: none; padding: 0; }
blockquote {
  margin: 1.2rem 0; padding: .7rem 1.1rem;
  border-left: 4px solid var(--accent); background: var(--panel);
  color: var(--ink);
}
blockquote p:last-child { margin-bottom: 0; }
table {
  width: 100%; border-collapse: collapse; margin: 1.1rem 0 1.6rem;
  font-family: "Segoe UI", -apple-system, Arial, sans-serif;
  font-size: .82rem; line-height: 1.45;
}
thead th {
  text-align: left; border-bottom: 2px solid var(--ink);
  padding: .45rem .55rem; font-weight: 600; vertical-align: bottom;
}
tbody td { border-bottom: 1px solid var(--rule); padding: .42rem .55rem; vertical-align: top; }
tbody tr:last-child td { border-bottom: 1px solid var(--ink); }
tbody tr:hover { background: var(--panel); }
ul, ol { margin: 0 0 1rem; padding-left: 1.4rem; }
li { margin-bottom: .35rem; }
.tag {
  display: inline-block; font-family: "Segoe UI", Arial, sans-serif;
  font-size: .64rem; font-weight: 700; letter-spacing: .06em;
  padding: .1rem .4rem; border-radius: 3px; vertical-align: .08em;
  margin-right: .25rem; white-space: nowrap; color: #fff;
}
.tag-observed { background: var(--observed); }
.tag-model { background: var(--model); }
.tag-experiment { background: var(--experiment); }
.tag-interpretation { background: var(--interpretation); }
.tag-engineering { background: var(--engineering); }
.tag-future { background: var(--future); }
.titleblock {
  border-top: 4px solid var(--accent); border-bottom: 1px solid var(--rule);
  padding: 1.4rem 0 1.2rem; margin-bottom: 2rem;
}
.titleblock .subtitle {
  font-family: "Segoe UI", Arial, sans-serif; color: var(--muted);
  font-size: .98rem; margin: .5rem 0 1rem;
}
.titleblock .meta {
  font-family: "Segoe UI", Arial, sans-serif; font-size: .78rem;
  color: var(--muted); line-height: 1.8;
}
.toc {
  background: var(--panel); border: 1px solid var(--rule); border-radius: 6px;
  padding: 1.1rem 1.4rem; margin: 2rem 0 2.5rem;
  font-family: "Segoe UI", Arial, sans-serif; font-size: .84rem;
}
.toc h2 {
  font-size: .78rem; text-transform: uppercase; letter-spacing: .08em;
  margin: 0 0 .7rem; border: 0; padding: 0; color: var(--muted);
}
.toc ol { list-style: none; padding: 0; margin: 0;
          columns: 2; column-gap: 2rem; }
.toc li { margin-bottom: .3rem; break-inside: avoid; }
.toc a { text-decoration: none; color: var(--ink); }
.toc a:hover { color: var(--accent); text-decoration: underline; }

@media (max-width: 680px) {
  body { padding: 1.5rem 1rem 3rem; font-size: 15px; }
  .toc ol { columns: 1; }
  table { font-size: .74rem; }
  table, thead, tbody, tr { display: block; }
  thead { display: none; }
  tbody td { display: block; border: 0; padding: .2rem 0; }
  tbody tr { border-bottom: 1px solid var(--rule); padding: .6rem 0; }
}

@media print {
  @page { margin: 18mm 16mm; }
  body { max-width: none; padding: 0; font-size: 10.5pt; }
  h2 { page-break-before: always; page-break-after: avoid; }
  h2:first-of-type { page-break-before: avoid; }
  h3, h4 { page-break-after: avoid; }
  table, pre, blockquote { page-break-inside: avoid; }
  tbody tr { page-break-inside: avoid; }
  .toc { page-break-after: always; }
  a { color: var(--ink); text-decoration: none; }
  a[href^="http"]::after { content: " (" attr(href) ")"; font-size: .72em; color: var(--muted); }
}
"""


def slugify(text: str) -> str:
    plain = re.sub(r"<[^>]+>", "", text)
    plain = re.sub(r"[^\w\s-]", "", plain).strip().lower()
    return re.sub(r"[\s_]+", "-", plain)


def render_tags(markup: str) -> str:
    """Turn the paper's **[TAG]** markers into styled badges.

    Applied after Markdown rendering, so the tags stay plain, greppable text in
    the source document and only become presentation here.
    """
    for tag, css in EVIDENCE_TAGS.items():
        markup = markup.replace(
            f"<strong>[{tag}]</strong>",
            f'<span class="tag tag-{css}">{tag}</span>',
        )
    return markup


def build_toc(markup: str) -> tuple[str, str]:
    """Anchor every h2 and return the table of contents built from them."""
    entries: list[tuple[str, str]] = []

    def anchor(match: re.Match[str]) -> str:
        title = match.group(1)
        slug = slugify(title)
        entries.append((slug, title))
        return f'<h2 id="{slug}">{title}</h2>'

    markup = re.sub(r"<h2>(.*?)</h2>", anchor, markup, flags=re.DOTALL)
    skip = {"note-on-evidence-classes"}
    items = "\n".join(
        f'<li><a href="#{slug}">{re.sub(r"<[^>]+>", "", title)}</a></li>'
        for slug, title in entries
        if slug not in skip
    )
    toc = f'<nav class="toc"><h2>Contents</h2><ol>{items}</ol></nav>'
    return markup, toc


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"{SOURCE} not found")

    text = SOURCE.read_text(encoding="utf-8")

    # The title block is rebuilt as structured markup; everything after the first
    # horizontal rule is rendered as ordinary prose.
    body_markdown = text.split("\n---\n", 1)[1] if "\n---\n" in text else text

    renderer = mistune.create_markdown(
        plugins=["table", "strikethrough", "footnotes"],
        escape=False,
    )
    markup = renderer(body_markdown)
    markup = render_tags(markup)
    markup, toc = build_toc(markup)

    title = "Student Segmentation and Personalized Course Recommendation System for EduPro"
    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="author" content="Anushree Menon">
<meta name="description" content="A reproducible study of learner segmentation and course recommendation on the EduPro online learning platform.">
<style>{STYLE}</style>
</head>
<body>
<header class="titleblock">
  <h1>{html.escape(title)}</h1>
  <p class="subtitle">A reproducible study of learner segmentation and course
     recommendation on the EduPro online learning platform</p>
  <div class="meta">
    <strong>Anushree Menon</strong> &middot; 19 September 2026<br>
    Model version <code>edupro-1.0.0</code> &middot; artifact set <code>b658773c9db8</code><br>
    Source data SHA-256 <code>ed555e46&hellip;8cc0</code> &middot; seed 42 &middot; Python 3.13.9<br>
    All results reproducible via <code>scripts/verify_reproducibility.py</code>
  </div>
</header>
{toc}
<main>
{markup}
</main>
</body>
</html>
"""
    OUTPUT.write_text(document, encoding="utf-8")
    size = OUTPUT.stat().st_size / 1024
    print(f"Wrote {OUTPUT.relative_to(config.PROJECT_ROOT)} ({size:.0f} KB)")
    print("Open it in a browser and print to PDF for a submission copy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
