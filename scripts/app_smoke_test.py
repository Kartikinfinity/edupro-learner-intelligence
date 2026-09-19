"""Phase 6A CHECK 9 — drive the dashboard the way a user would, then break it.

`tests/test_app.py` proves each page *renders*. This goes further: it operates the
widgets, and then removes the artifact set to confirm that the failure a deployed
app is most likely to hit — no model on disk — produces an instruction rather than
a stack trace.

The artifact-removal probe renames the manifest and restores it in a ``finally``
block. It never deletes anything.

Usage
-----
    python scripts/app_smoke_test.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

from streamlit.testing.v1 import AppTest

from edupro import config
from edupro.persistence import MANIFEST_NAME

APP = config.PROJECT_ROOT / "app"
PAGES = sorted((APP / "pages").glob("*.py"))
TIMEOUT = 180

results: list[dict[str, Any]] = []


def record(probe: str, ok: bool, detail: str, **evidence: Any) -> None:
    results.append({"probe": probe, "severity": "pass" if ok else "fail",
                    "detail": detail, "evidence": evidence})
    print(f"  [{'OK  ' if ok else 'FAIL'}] {probe}: {detail}")


def run(path: Path) -> AppTest:
    app = AppTest.from_file(str(path), default_timeout=TIMEOUT)
    app.run()
    return app


def widget(collection, label: str):
    """Find a widget by its label rather than its position.

    Positional indexing silently points at a different control the moment a page
    gains a widget, which makes a smoke test quietly stop testing what it claims.
    """
    for element in collection:
        if element.label == label:
            return element
    raise AssertionError(f"no widget labelled {label!r}; found "
                         f"{[e.label for e in collection]}")


def main() -> int:
    print("=" * 78)
    print("CHECK 9 - STREAMLIT SMOKE TEST")
    print("=" * 78)

    # --- every page renders -------------------------------------------------
    for page in PAGES:
        started = time.perf_counter()
        app = run(page)
        elapsed = time.perf_counter() - started
        errors = [str(e) for e in app.exception]
        record(
            f"page renders: {page.stem}",
            not errors,
            f"{len(app.title)} title, {len(app.subheader)} sections, "
            f"{len(app.metric)} metrics, {len(app.dataframe)} tables, {elapsed:.1f}s"
            if not errors else errors[0][:160],
        )

    # --- learner selection --------------------------------------------------
    profile = run(APP / "pages" / "2_Learner_Profile.py")
    selector = next(s for s in profile.sidebar.selectbox if s.label.startswith("Learner"))
    first = selector.value
    other = selector.options[5]
    selector.set_value(other).run()
    record(
        "learner selection changes the page",
        not profile.exception and other in " ".join(h.value for h in profile.subheader),
        f"selected {other} (from {first}); the profile header follows the selection",
    )

    # --- segment filter narrows the pool ------------------------------------
    profile = run(APP / "pages" / "2_Learner_Profile.py")
    segments = widget(profile.sidebar.selectbox, "Filter by segment")
    a_segment = segments.options[1]
    segments.set_value(a_segment).run()
    label = next(
        s for s in profile.sidebar.selectbox if s.label.startswith("Learner")
    ).label
    record(
        "segment filter narrows the learner pool",
        not profile.exception and "available" in label,
        f"filtering to {a_segment!r} leaves '{label}'",
    )

    # --- recommendations, filters and cold start ----------------------------
    recs = run(APP / "pages" / "3_Recommendations.py")
    baseline_ids = [m.value for m in recs.metric]
    record("recommendations render", not recs.exception,
           f"metrics: {dict(zip([m.label for m in recs.metric], baseline_ids))}")

    widget(recs.sidebar.selectbox, "Category").set_value("Data Science").run()
    # The category is rendered in a caption, so reading only markdown would miss it
    # and report a false failure.
    rendered = " ".join(
        e.value for group in (recs.markdown, recs.caption, recs.info) for e in group
    )
    other_categories = [
        c for c in ("Cybersecurity", "Web Development", "Marketing", "Programming")
        if f"{c} ·" in rendered
    ]
    record(
        "category filter applies",
        not recs.exception and "Data Science ·" in rendered and not other_categories,
        "every rendered recommendation is in Data Science"
        if not other_categories
        else f"list also contained {other_categories}",
    )

    recs = run(APP / "pages" / "3_Recommendations.py")
    widget(recs.sidebar.radio, "Learner").set_value("New learner (cold start)").run()
    tier = next((m.value for m in recs.metric if m.label == "Route"), None)
    record(
        "cold-start mode reaches the fallback route",
        not recs.exception and tier == "insufficient",
        f"route metric reads {tier!r}, so the diversified fallback is reachable from the UI",
    )

    recs = run(APP / "pages" / "3_Recommendations.py")
    widget(recs.sidebar.slider, "Number of recommendations").set_value(3).run()
    record("list length control works", not recs.exception,
           "k slider re-ran the page without error")

    # --- cluster visualisation controls -------------------------------------
    clusters = run(APP / "pages" / "5_Cluster_Visualization.py")
    record("segment visualization renders", not clusters.exception,
           f"{len(clusters.warning)} caveat block(s) shown before the chart")

    segments_widget = widget(clusters.sidebar.multiselect, "Segments")
    only_one = segments_widget.options[:1]
    segments_widget.set_value(only_one).run()
    record("visualisation filter works", not clusters.exception,
           f"restricted to {only_one[0]!r} without error")

    clusters = run(APP / "pages" / "5_Cluster_Visualization.py")
    widget(clusters.sidebar.multiselect, "Segments").set_value([]).run()
    info = " ".join(i.value for i in clusters.info)
    record(
        "empty selection shows an empty state",
        not clusters.exception and "No segments selected" in info,
        "deselecting every segment gives guidance, not a crash",
    )

    # --- metrics render ------------------------------------------------------
    analytics = run(APP / "pages" / "7_Model_Analytics.py")
    record(
        "measured metrics render",
        not analytics.exception and len(analytics.dataframe) >= 4,
        f"{len(analytics.dataframe)} evidence tables, {len(analytics.metric)} metrics",
    )

    comparison = run(APP / "pages" / "6_Segment_Comparison.py")
    widget(comparison.sidebar.multiselect, "Characteristics").set_value([]).run()
    info = " ".join(i.value for i in comparison.info)
    record(
        "comparison handles an empty selection",
        not comparison.exception and "Nothing selected" in info,
        "clearing every characteristic gives guidance, not a crash",
    )

    # --- the failure a deployment actually hits -----------------------------
    manifest = config.MODELS_DIR / MANIFEST_NAME
    hidden = manifest.with_suffix(".json.smoke-test-backup")
    probe = textwrap.dedent(
        """
        import json, sys
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(sys.argv[1], default_timeout=180)
        app.run()
        print(json.dumps({
            "exceptions": [str(e)[:200] for e in app.exception],
            "info": [i.value for i in app.info],
            "title": [t.value for t in app.title],
            "code": [c.value for c in app.code],
        }))
        """
    )
    try:
        manifest.rename(hidden)
        # A fresh interpreter, because st.cache_resource would otherwise hand this
        # probe the model loaded earlier in this process - it would pass while
        # testing nothing. A cold process is also what a deployment actually does.
        completed = subprocess.run(
            [sys.executable, "-c", probe,
             str(APP / "pages" / "1_Executive_Overview.py")],
            capture_output=True, text=True, cwd=config.PROJECT_ROOT, timeout=300,
        )
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        body = " ".join(payload["info"] + payload["title"])
        code = " ".join(payload["code"])
        graceful = (
            not payload["exceptions"]
            and "artifacts not found" in body.lower()
            and "train_production_model" in code
        )
        record(
            "missing artifacts produce an instruction, not a stack trace",
            graceful,
            "a cold process with no model shows the page that names the fixing command"
            if graceful
            else f"exceptions={payload['exceptions']} body={body[:160]!r}",
        )
    finally:
        if hidden.exists():
            hidden.rename(manifest)
        assert manifest.exists(), "the manifest was not restored"
    record("artifact set restored", manifest.exists(),
           "the manifest is back in place after the failure probe")

    failures = [r for r in results if r["severity"] == "fail"]
    print("\n" + "=" * 78)
    print(f"{len(results)} probes: {len(results) - len(failures)} pass, {len(failures)} FAIL")
    for failure in failures:
        print(f"  FAIL {failure['probe']}: {failure['detail']}")

    destination = config.ARTIFACTS_DIR / "validation" / "app_smoke_test.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            {
                "summary": {"n_probes": len(results), "n_fail": len(failures)},
                "findings": results,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nWritten to {destination.relative_to(config.PROJECT_ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
