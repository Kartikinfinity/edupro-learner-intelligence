"""Capture dashboard screenshots for the README, reproducibly.

Screenshots in a README are usually hand-taken and quietly go stale: the interface
moves on and the picture does not. This script regenerates all of them from a
running app in one command, so a reviewer can confirm the images match the code.

It drives headless Chrome rather than a Python browser library, because Chrome is
already present on any machine likely to review this and adding Playwright would
mean a ~130 MB dependency for six images.

Usage
-----
    streamlit run app/streamlit_app.py      # in another terminal
    python scripts/capture_screenshots.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from edupro import config

OUT = config.DOCS_DIR / "screenshots"
BASE_URL = "http://localhost:8501"
WIDTH, HEIGHT = 1440, 1400

#: Page path -> output filename. The paths are the titles Streamlit derives from
#: the navigation entries in app/streamlit_app.py.
PAGES: tuple[tuple[str, str], ...] = (
    ("", "01_executive_overview.png"),
    ("Learner_Profile", "02_learner_profile.png"),
    ("Recommendations", "03_recommendations.png"),
    ("Segment_Intelligence", "04_segment_intelligence.png"),
    ("Cluster_Visualization", "05_cluster_visualization.png"),
    ("Model_Analytics", "06_model_analytics.png"),
)

CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
)


def find_browser() -> str | None:
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


#: A rendered dashboard page is well over this; a blank one compresses far below
#: it. Used to tell "Chrome wrote a file" apart from "Chrome captured the app".
MIN_RENDERED_BYTES = 25_000


def capture(browser: str, url: str, destination: Path, budget_ms: int) -> None:
    """Take one screenshot. Streamlit renders client-side, so the virtual-time
    budget is what gives the app time to draw before the shot is taken."""
    subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--window-size={WIDTH},{HEIGHT}",
            f"--virtual-time-budget={budget_ms}",
            f"--screenshot={destination}",
            url,
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )


def app_is_running() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE_URL}/healthz", timeout=5) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def main() -> int:
    browser = find_browser()
    if browser is None:
        print("No Chrome or Edge found. Install one, or take the screenshots manually.",
              file=sys.stderr)
        return 1
    if not app_is_running():
        print(f"Nothing answering at {BASE_URL}. Start the app first:", file=sys.stderr)
        print("    streamlit run app/streamlit_app.py", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Capturing {len(PAGES)} pages with {Path(browser).name}\n")

    failures = 0
    for path, filename in PAGES:
        destination = OUT / filename
        url = f"{BASE_URL}/{path}" if path else BASE_URL
        # The first capture of a session pays Chrome's profile-creation cost and
        # can land before the app has drawn, so a short capture is retried once
        # with a longer budget rather than left as a gap in the documentation.
        for budget in (25_000, 45_000):
            capture(browser, url, destination, budget)
            if destination.exists() and destination.stat().st_size >= MIN_RENDERED_BYTES:
                break
        if not destination.exists():
            print(f"  [FAIL] {filename}: nothing written")
            failures += 1
            continue
        size = destination.stat().st_size
        if size < MIN_RENDERED_BYTES:
            print(f"  [FAIL] {filename}: {size / 1024:.0f} KB - looks blank")
            failures += 1
        else:
            print(f"  [OK  ] {filename}: {size / 1024:.0f} KB")

    print()
    if failures:
        print(f"{failures} of {len(PAGES)} captures failed")
        return 1
    total = sum((OUT / name).stat().st_size for _, name in PAGES) / 1024
    print(f"All {len(PAGES)} screenshots written to "
          f"{OUT.relative_to(config.PROJECT_ROOT)} ({total:.0f} KB total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
