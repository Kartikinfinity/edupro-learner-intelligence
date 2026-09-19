"""Learner feature representations for segmentation.

A *representation* is a complete, reproducible recipe for turning the learner
feature table into a numeric matrix: which feature blocks are included, how the
12-level category preference is encoded, how blocks are weighted, and how columns
are scaled.

Why this is a first-class object
    Phase 1 identified encoding as the project's largest methodological risk
    (`research/segmentation_research.md` §3): one-hot encoding `preferred_category`
    adds 12 columns against ~8 behavioural ones, so more than half the Euclidean
    distance budget would be spent on a single conceptual variable and K-Means
    would largely rediscover the course taxonomy. Making the representation
    explicit lets the alternatives be compared rather than assumed.

Every representation carries a **block map** so the Phase 3A dominance diagnostic
(eta-squared per block) can attribute cluster variance to the feature groups that
produced it — the measurement CLAUDE.md §10 requires.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler, StandardScaler

from edupro.features.learner import CATEGORY_SHARE_COLUMNS
from edupro.data.schema import COURSE_LEVELS

CategoryEncoding = Literal["one_hot", "proportion", "facets", "none"]
ScalerName = Literal["standard", "robust"]

#: The seven mandated numeric learner features (official brief, pp.3-4), minus
#: the two demographics and the two categorical preferences which are handled
#: separately. Every representation includes these, so the brief's feature
#: requirement is satisfied by construction.
MANDATED_NUMERIC: tuple[str, ...] = (
    "total_courses",
    "avg_courses_per_category",
    "enrollment_frequency",
    "avg_course_rating",
    "avg_spend",
    "diversity_score",
    "learning_depth_index",
)

#: Additional numeric features justified in `research/dataset_audit.md` §8.
EXTRA_NUMERIC: tuple[str, ...] = (
    "free_ratio",
    "diversity_ratio",
    "activity_span_days",
)

#: Category-preference facets used by the "facets" encoding: breadth and
#: concentration without category identity.
CATEGORY_FACETS: tuple[str, ...] = ("category_entropy", "top_category_share", "diversity_ratio")

TEACHER_BLOCK: tuple[str, ...] = ("n_teachers", "teacher_loyalty", "avg_teacher_rating")


@dataclass(frozen=True)
class RepresentationSpec:
    """A complete, reproducible recipe for building a segmentation matrix."""

    name: str
    description: str
    category_encoding: CategoryEncoding = "proportion"
    include_extra_numeric: bool = True
    include_level_preference: bool = True
    include_demographics: bool = False
    include_teacher: bool = False
    #: Drop features that are near-duplicates of `total_courses` (EXP-011e).
    drop_correlated: bool = False
    #: Divide each block by sqrt(number of its columns) so a block's influence on
    #: Euclidean distance does not depend on how many columns it happens to have
    #: (EXP-011b). Without this, weighting is still happening — just accidentally.
    block_weighting: bool = False
    scaler: ScalerName = "standard"

    def variant(self) -> str:
        """CLAUDE.md §10 labels: A = behaviour + demographics, B = behaviour only."""
        return "A" if self.include_demographics else "B"


@dataclass
class Representation:
    """A built representation: the matrix, its columns, and its block map."""

    spec: RepresentationSpec
    matrix: np.ndarray
    columns: list[str]
    blocks: dict[str, list[str]]
    index: pd.Index
    raw: pd.DataFrame = field(repr=False)

    @property
    def n_features(self) -> int:
        return self.matrix.shape[1]

    @property
    def n_learners(self) -> int:
        return self.matrix.shape[0]

    def block_of(self, column: str) -> str:
        for block, members in self.blocks.items():
            if column in members:
                return block
        return "other"

    def summary(self) -> dict[str, object]:
        return {
            "name": self.spec.name,
            "variant": self.spec.variant(),
            "description": self.spec.description,
            "n_learners": self.n_learners,
            "n_features": self.n_features,
            "category_encoding": self.spec.category_encoding,
            "block_weighting": self.spec.block_weighting,
            "scaler": self.spec.scaler,
            "blocks": {block: len(members) for block, members in self.blocks.items()},
            "columns": self.columns,
        }


#: Features whose correlation with `total_courses` exceeded 0.9 in the Phase 2
#: audit. Dropped by the `drop_correlated` ablation (EXP-011e) to test whether
#: the segmentation is merely re-measuring activity volume several times over.
CORRELATED_WITH_VOLUME: tuple[str, ...] = (
    "diversity_score",
    "avg_courses_per_category",
    "category_entropy",
)


def _one_hot(series: pd.Series, prefix: str, categories: tuple[str, ...]) -> pd.DataFrame:
    frame = pd.get_dummies(series.astype("string"), prefix=prefix, dtype=float)
    expected = [f"{prefix}_{value}" for value in categories]
    return frame.reindex(columns=expected, fill_value=0.0)


def build_representation(
    features: pd.DataFrame, spec: RepresentationSpec
) -> Representation:
    """Assemble, weight and scale a representation from the learner feature table.

    Missingness
        The Phase 2 audit found **zero missing values** in the source data, and the
        feature builder produces a value for every active learner. Any NaN reaching
        this function therefore indicates a bug, not sparse data — so it is filled
        with 0.0 and the count is asserted to be zero by the test suite rather than
        silently imputed.
    """
    blocks: dict[str, list[str]] = {}
    parts: list[pd.DataFrame] = []

    numeric = list(MANDATED_NUMERIC)
    if spec.include_extra_numeric:
        numeric += [c for c in EXTRA_NUMERIC if c not in numeric]
    if spec.drop_correlated:
        numeric = [c for c in numeric if c not in CORRELATED_WITH_VOLUME]

    engagement = [c for c in numeric if c in {
        "total_courses", "avg_courses_per_category", "enrollment_frequency",
        "activity_span_days",
    }]
    behavioural = [c for c in numeric if c not in engagement]
    blocks["engagement"] = engagement
    blocks["behavioural"] = behavioural
    parts.append(features[numeric].astype(float))

    # --- category preference -------------------------------------------------
    if spec.category_encoding == "proportion":
        category = features[list(CATEGORY_SHARE_COLUMNS)].astype(float)
    elif spec.category_encoding == "one_hot":
        from edupro.data.schema import COURSE_CATEGORIES

        category = _one_hot(features["preferred_category"], "prefcat", COURSE_CATEGORIES)
        category.index = features.index
    elif spec.category_encoding == "facets":
        facets = [c for c in CATEGORY_FACETS if c not in numeric]
        category = features[facets].astype(float)
    else:
        category = pd.DataFrame(index=features.index)
    blocks["category"] = list(category.columns)
    if not category.empty:
        parts.append(category)

    # --- level preference ----------------------------------------------------
    if spec.include_level_preference:
        level = _one_hot(features["preferred_level"], "preflevel", COURSE_LEVELS)
        level.index = features.index
        blocks["level"] = list(level.columns)
        parts.append(level)

    # --- demographics (Variant A only) --------------------------------------
    if spec.include_demographics:
        demographic = pd.DataFrame(index=features.index)
        demographic["age"] = features["age"].astype(float)
        demographic["gender_female"] = (features["gender"] == "Female").astype(float)
        blocks["demographic"] = list(demographic.columns)
        parts.append(demographic)

    # --- teacher block (opt-in experiment only) -----------------------------
    if spec.include_teacher:
        teacher = features[list(TEACHER_BLOCK)].astype(float)
        blocks["teacher"] = list(teacher.columns)
        parts.append(teacher)

    frame = pd.concat(parts, axis=1)
    if frame.isna().any().any():
        frame = frame.fillna(0.0)

    scaler = StandardScaler() if spec.scaler == "standard" else RobustScaler()
    matrix = scaler.fit_transform(frame.to_numpy(dtype=float))

    if spec.block_weighting:
        for members in blocks.values():
            if not members:
                continue
            positions = [frame.columns.get_loc(c) for c in members]
            matrix[:, positions] /= np.sqrt(len(members))

    blocks = {name: members for name, members in blocks.items() if members}
    return Representation(
        spec=spec,
        matrix=matrix,
        columns=list(frame.columns),
        blocks=blocks,
        index=features.index,
        raw=frame,
    )


# ---------------------------------------------------------------------------
# The experiment grid
# ---------------------------------------------------------------------------
#: Representations compared in Phase 3A. `B_proportion` is the reference against
#: which every other arm is read; it is not assumed to win.
REPRESENTATION_GRID: tuple[RepresentationSpec, ...] = (
    RepresentationSpec(
        name="B_proportion",
        description="Variant B (behaviour only), category as a 12-dim share vector (E-B)",
        category_encoding="proportion",
    ),
    RepresentationSpec(
        name="B_one_hot",
        description="Variant B, category one-hot on the modal category (E-A, the control arm)",
        category_encoding="one_hot",
    ),
    RepresentationSpec(
        name="B_facets",
        description="Variant B, category as breadth/concentration facets only (E-C)",
        category_encoding="facets",
    ),
    RepresentationSpec(
        name="B_no_category",
        description="Variant B with no category representation at all (lower bound)",
        category_encoding="none",
    ),
    RepresentationSpec(
        name="A_proportion",
        description="Variant A (behaviour + demographics), category share vector",
        category_encoding="proportion",
        include_demographics=True,
    ),
    RepresentationSpec(
        name="B_proportion_weighted",
        description="Variant B, share vector, blocks weighted by 1/sqrt(columns) (EXP-011b)",
        category_encoding="proportion",
        block_weighting=True,
    ),
    RepresentationSpec(
        name="B_decorrelated",
        description="Variant B, share vector, volume-redundant features dropped (EXP-011e)",
        category_encoding="proportion",
        drop_correlated=True,
    ),
    RepresentationSpec(
        name="B_robust_scaled",
        description="Variant B, share vector, RobustScaler instead of StandardScaler",
        category_encoding="proportion",
        scaler="robust",
    ),
    RepresentationSpec(
        name="B_teacher",
        description="Variant B + teacher-derived block (EXP-014 arm)",
        category_encoding="proportion",
        include_teacher=True,
    ),
    RepresentationSpec(
        name="B_no_level",
        description=(
            "Variant B, share vector, preferred_level one-hot removed. Added after "
            "the first run showed the k=4 partition was almost purely a level split: "
            "this arm tests whether any structure survives without it."
        ),
        category_encoding="proportion",
        include_level_preference=False,
    ),
)
