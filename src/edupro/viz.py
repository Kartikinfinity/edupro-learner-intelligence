"""Shared plotting style for every figure this project produces.

Centralising the style means the research paper, the notebooks and the Streamlit
application cannot drift into three different visual languages.

Palette
    Categorical slots are taken **in fixed order, never cycled**, from a palette
    validated for colour-vision deficiency separation. Only the first three slots
    are used for forms where every pair of series can appear together (scatter,
    small multiples); that subset validates on the all-pairs test. Beyond three
    series the project folds the remainder into "Other" or facets rather than
    inventing a ninth hue.

    Aqua (slot 3) sits below 3:1 contrast against the light surface, so any chart
    using it carries visible direct labels or an accompanying table — the
    documented relief for a contrast warning.

Correlation matrices use a diverging blue<->red ramp through a neutral grey
midpoint, never a rainbow and never a hue at the midpoint: the midpoint must read
as "no association".
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# --- surfaces and ink ------------------------------------------------------
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
TEXT_MUTED = "#8a8985"
GRID = "#e6e5e1"

# --- categorical slots, in fixed order -------------------------------------
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")
BLUE, ORANGE, AQUA, YELLOW = SERIES

#: Reference / null / baseline marks are deliberately neutral, so they never
#: compete with a data series for identity.
REFERENCE = "#8a8985"

# --- sequential (magnitude) ------------------------------------------------
SEQUENTIAL_BLUE = (
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
    "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab",
)

# --- diverging (polarity), neutral grey midpoint ---------------------------
DIVERGING = LinearSegmentedColormap.from_list(
    "edupro_diverging", ["#1c5cab", "#2a78d6", "#f0efec", "#e34948", "#b32a29"]
)


def apply_style() -> None:
    """Install the project's matplotlib defaults: thin marks, recessive chrome."""
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "savefig.bbox": "tight",
            "savefig.dpi": 150,
            "font.size": 10,
            "font.family": "sans-serif",
            "text.color": TEXT_PRIMARY,
            "axes.labelcolor": TEXT_SECONDARY,
            "axes.edgecolor": GRID,
            "axes.linewidth": 0.8,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.titlecolor": TEXT_PRIMARY,
            "axes.titlepad": 12,
            "axes.labelsize": 10,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "xtick.color": TEXT_SECONDARY,
            "ytick.color": TEXT_SECONDARY,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "legend.labelcolor": TEXT_SECONDARY,
            "lines.linewidth": 2.0,
            "lines.markersize": 5,
            "figure.autolayout": False,
        }
    )
    for spine in ("top", "right"):
        mpl.rcParams[f"axes.spines.{spine}"] = False


def caption(fig: plt.Figure, text: str) -> None:
    """Attach a short interpretive note beneath the whole figure.

    Research figures travel into documents without their surrounding prose, so a
    figure that states what it shows is less likely to be misread.

    Placed at figure level rather than on an axes: an axes-relative offset
    collides with rotated tick labels, and ``savefig(bbox="tight")`` expands the
    canvas to include figure-level text.
    """
    fig.text(0.01, -0.01, text, fontsize=8.5, color=TEXT_MUTED, va="top", wrap=True)


def save(fig: plt.Figure, destination: Path, name: str) -> Path:
    """Write a figure to ``destination/name.png`` and close it."""
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    return path
