"""Phase 3A tests: representations, clustering, metrics, stability, profiling.

Most tests run on small synthetic matrices with known structure, so they assert
that the *machinery* is correct independently of what the EduPro data happens to
contain. A handful of tests pin documented properties of the real data, so a
change in the dataset or the pipeline that invalidates a Phase 3A conclusion
fails loudly instead of silently.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from edupro import config
from edupro.data.joins import build_interactions
from edupro.data.loader import load_all
from edupro.evaluation.splits import apply_global_split, global_temporal_split
from edupro.features.learner import build_learner_features
from edupro.segmentation.clustering import (
    compare_partitions,
    fit_hierarchical,
    fit_kmeans,
    kmeans_sweep,
    seed_stability,
)
from edupro.segmentation.metrics import (
    block_dominance,
    cluster_sizes,
    eta_squared,
    gap_statistic,
    intra_cluster_similarity,
    internal_metrics,
    per_cluster_silhouette,
)
from edupro.segmentation.profiling import (
    LEVEL_PURITY_THRESHOLD,
    MIN_DEVIATION,
    centroid_deviations,
    compose_segment_names,
    derive_label,
    label_clusters,
    profile_clusters,
)
from edupro.segmentation.representations import (
    REPRESENTATION_GRID,
    RepresentationSpec,
    build_representation,
)
from edupro.segmentation.stability import assess_stability, bootstrap_jaccard


@pytest.fixture(scope="module")
def blobs() -> np.ndarray:
    """Three well-separated blobs: structure the machinery must be able to find."""
    rng = np.random.default_rng(config.RANDOM_SEED)
    return np.vstack([
        rng.normal(loc=loc, scale=0.30, size=(120, 4)) for loc in (-6.0, 0.0, 6.0)
    ])


@pytest.fixture(scope="module")
def noise() -> np.ndarray:
    """Structureless data: the machinery must not claim to find clusters here."""
    rng = np.random.default_rng(config.RANDOM_SEED)
    return rng.normal(size=(300, 4))


@pytest.fixture(scope="module")
def learner_features() -> pd.DataFrame:
    data = load_all()
    interactions = build_interactions(data, with_user_demographics=True, with_teacher=True)
    fit_frame = apply_global_split(interactions, global_temporal_split(interactions))["fit"]
    return build_learner_features(fit_frame, users=data.users)


# ---------------------------------------------------------------------------
# Representations
# ---------------------------------------------------------------------------
def test_every_representation_in_the_grid_builds(learner_features: pd.DataFrame):
    for spec in REPRESENTATION_GRID:
        representation = build_representation(learner_features, spec)
        assert representation.n_learners == len(learner_features)
        assert representation.n_features == representation.matrix.shape[1]
        assert len(representation.columns) == representation.n_features


def test_no_representation_contains_nan(learner_features: pd.DataFrame):
    for spec in REPRESENTATION_GRID:
        matrix = build_representation(learner_features, spec).matrix
        assert not np.isnan(matrix).any(), f"{spec.name} produced NaN"


def test_every_representation_contains_all_mandated_numeric_features(
    learner_features: pd.DataFrame,
):
    """The brief's feature requirement must hold for every arm except the ablations
    that exist precisely to remove a feature."""
    from edupro.segmentation.representations import MANDATED_NUMERIC

    for spec in REPRESENTATION_GRID:
        if spec.drop_correlated:
            continue  # this arm exists to remove redundant features
        representation = build_representation(learner_features, spec)
        missing = set(MANDATED_NUMERIC) - set(representation.columns)
        assert not missing, f"{spec.name} missing mandated features: {missing}"


def test_variant_b_never_contains_demographics(learner_features: pd.DataFrame):
    for spec in REPRESENTATION_GRID:
        if spec.include_demographics:
            continue
        representation = build_representation(learner_features, spec)
        assert "age" not in representation.columns
        assert "gender_female" not in representation.columns
        assert representation.spec.variant() == "B"


def test_teacher_block_is_opt_in(learner_features: pd.DataFrame):
    core = build_representation(
        learner_features, RepresentationSpec(name="core", description="")
    )
    with_teacher = build_representation(
        learner_features, RepresentationSpec(name="t", description="", include_teacher=True)
    )
    assert "teacher_loyalty" not in core.columns
    assert "teacher_loyalty" in with_teacher.columns


def test_category_encodings_differ_in_dimensionality(learner_features: pd.DataFrame):
    one_hot = build_representation(
        learner_features,
        RepresentationSpec(name="a", description="", category_encoding="one_hot"),
    )
    facets = build_representation(
        learner_features,
        RepresentationSpec(name="c", description="", category_encoding="facets"),
    )
    none = build_representation(
        learner_features,
        RepresentationSpec(name="n", description="", category_encoding="none"),
    )
    assert len(one_hot.blocks["category"]) == 12
    assert len(facets.blocks.get("category", [])) < 12
    assert "category" not in none.blocks


def test_block_weighting_changes_the_matrix(learner_features: pd.DataFrame):
    plain = build_representation(
        learner_features, RepresentationSpec(name="p", description="")
    )
    weighted = build_representation(
        learner_features, RepresentationSpec(name="w", description="", block_weighting=True)
    )
    assert plain.columns == weighted.columns
    assert not np.allclose(plain.matrix, weighted.matrix)


def test_representations_are_deterministic(learner_features: pd.DataFrame):
    spec = REPRESENTATION_GRID[0]
    first = build_representation(learner_features, spec).matrix
    second = build_representation(learner_features, spec).matrix
    assert np.allclose(first, second)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def test_internal_metrics_recover_known_structure(blobs: np.ndarray):
    labels = fit_kmeans(blobs, 3).labels_
    metrics = internal_metrics(blobs, labels)
    assert metrics["silhouette"] > 0.8
    assert metrics["davies_bouldin"] < 0.5


def test_internal_metrics_are_nan_for_a_single_cluster(blobs: np.ndarray):
    metrics = internal_metrics(blobs, np.zeros(len(blobs), dtype=int))
    assert np.isnan(metrics["silhouette"])


def test_cluster_sizes_sum_to_the_population(blobs: np.ndarray):
    labels = fit_kmeans(blobs, 3).labels_
    assert sum(cluster_sizes(labels).values()) == len(blobs)


def test_per_cluster_silhouette_covers_every_cluster(blobs: np.ndarray):
    labels = fit_kmeans(blobs, 3).labels_
    assert set(per_cluster_silhouette(blobs, labels)) == set(np.unique(labels))


def test_eta_squared_is_one_for_a_perfectly_separating_feature():
    labels = np.array([0] * 50 + [1] * 50)
    matrix = np.column_stack([labels.astype(float), np.zeros(100)])
    scores = eta_squared(matrix, labels, ["separating", "constant"])
    assert scores["separating"] == pytest.approx(1.0)
    assert scores["constant"] == 0.0


def test_eta_squared_is_near_zero_for_an_unrelated_feature():
    rng = np.random.default_rng(config.RANDOM_SEED)
    labels = np.array([0] * 250 + [1] * 250)
    matrix = rng.normal(size=(500, 1))
    assert eta_squared(matrix, labels, ["noise"])["noise"] < 0.05


def test_block_dominance_shares_sum_to_one(blobs: np.ndarray):
    labels = fit_kmeans(blobs, 3).labels_
    columns = [f"f{i}" for i in range(blobs.shape[1])]
    blocks = {"first": columns[:2], "second": columns[2:]}
    result = block_dominance(blobs, labels, columns, blocks)
    assert sum(result["explained_share_per_block"].values()) == pytest.approx(1.0)
    assert result["demographic_share"] == 0.0


def test_intra_cluster_similarity_is_higher_for_tight_clusters(blobs: np.ndarray, noise):
    positions = list(range(blobs.shape[1]))
    tight = intra_cluster_similarity(blobs, fit_kmeans(blobs, 3).labels_, positions)
    loose = intra_cluster_similarity(noise, fit_kmeans(noise, 3).labels_, positions)
    assert tight["weighted_mean"] > loose["weighted_mean"]


def test_gap_statistic_finds_the_true_k_on_well_separated_blobs(blobs: np.ndarray):
    result = gap_statistic(blobs, k_values=range(1, 7), n_references=20)
    assert result.optimal_k == 3
    assert not result.indicates_no_structure


def test_gap_statistic_can_report_no_structure():
    """The property the statistic was added for: it must be able to say k=1."""
    rng = np.random.default_rng(config.RANDOM_SEED)
    uniform = rng.uniform(size=(300, 3))
    result = gap_statistic(uniform, k_values=range(1, 6), n_references=20)
    assert result.optimal_k == 1
    assert result.indicates_no_structure


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------
def test_kmeans_is_deterministic_under_the_project_seed(blobs: np.ndarray):
    assert (fit_kmeans(blobs, 3).labels_ == fit_kmeans(blobs, 3).labels_).all()


def test_seed_stability_is_one_on_separable_data(blobs: np.ndarray):
    assert seed_stability(blobs, 3, [42, 7, 123]) == pytest.approx(1.0)


def test_sweep_covers_the_requested_range(blobs: np.ndarray):
    sweep = kmeans_sweep(blobs, behavioural_positions=[0, 1], k_range=(2, 3, 4))
    assert [row.k for row in sweep.rows] == [2, 3, 4]
    assert sweep.best_by_silhouette().k == 3


def test_sweep_inertia_decreases_monotonically(blobs: np.ndarray):
    """Inertia falls with k by construction, which is exactly why the elbow alone
    cannot select k."""
    sweep = kmeans_sweep(blobs, behavioural_positions=[0, 1], k_range=(2, 3, 4, 5))
    inertias = [row.inertia for row in sweep.rows]
    assert inertias == sorted(inertias, reverse=True)


def test_hierarchical_returns_zero_based_labels(blobs: np.ndarray):
    for method in ("ward", "average"):
        labels = fit_hierarchical(blobs, 3, method=method)
        assert set(labels) == {0, 1, 2}


def test_hierarchical_agrees_with_kmeans_on_separable_data(blobs: np.ndarray):
    agreement = compare_partitions(
        fit_kmeans(blobs, 3).labels_, fit_hierarchical(blobs, 3, "ward")
    )
    assert agreement > 0.95


# ---------------------------------------------------------------------------
# Stability
# ---------------------------------------------------------------------------
def test_bootstrap_jaccard_is_high_on_separable_data(blobs: np.ndarray):
    scores = bootstrap_jaccard(blobs, 3, n_bootstrap=15)
    assert len(scores) == 3
    assert min(scores.values()) > 0.8


def test_bootstrap_jaccard_is_low_on_structureless_data(noise: np.ndarray):
    scores = bootstrap_jaccard(noise, 6, n_bootstrap=15)
    assert min(scores.values()) < 0.8


def test_assess_stability_flags_unstable_clusters(noise: np.ndarray, blobs: np.ndarray):
    good = assess_stability(blobs, 3, n_bootstrap=15, n_subsample_pairs=6)
    bad = assess_stability(noise, 8, n_bootstrap=15, n_subsample_pairs=6)
    assert good.n_unstable == 0
    assert bad.n_unstable > 0
    assert good.mean_jaccard > bad.mean_jaccard


# ---------------------------------------------------------------------------
# Profiling and naming
# ---------------------------------------------------------------------------
def test_profile_has_one_row_per_cluster(learner_features: pd.DataFrame):
    labels = np.resize([0, 1, 2, 3], len(learner_features))
    profiles = profile_clusters(learner_features, labels)
    assert len(profiles) == 4
    assert profiles["n_learners"].sum() == len(learner_features)


def test_centroid_deviations_are_zero_when_all_clusters_are_alike(
    learner_features: pd.DataFrame,
):
    """Interleaved labels give statistically identical clusters, so every deviation
    should be near zero — the condition under which naming must stay neutral."""
    labels = np.resize([0, 1], len(learner_features))
    deviations = centroid_deviations(learner_features, labels)
    assert deviations.abs().to_numpy().max() < 0.2


def test_a_shapeless_cluster_gets_a_neutral_name():
    deviations = pd.Series({"total_courses": 0.01, "learning_depth_index": -0.02})
    result = derive_label(deviations, cluster=3)
    assert result["is_neutral"]
    assert "mixed profile" in result["label"]
    assert result["evidence"] == []


def test_a_distinctive_cluster_is_named_from_its_own_deviations():
    deviations = pd.Series({"total_courses": 2.1, "learning_depth_index": -1.4})
    result = derive_label(deviations, cluster=0)
    assert not result["is_neutral"]
    assert "High-volume" in result["label"]
    assert all(abs(e["deviation"]) >= MIN_DEVIATION for e in result["evidence"])


def test_naming_can_be_restricted_to_features_the_model_used():
    """A segment must never be named for a dimension the clustering never saw."""
    deviations = pd.Series({"total_courses": 0.1, "teacher_loyalty": 2.5})
    unrestricted = derive_label(deviations, cluster=0)
    restricted = derive_label(deviations, cluster=0, allowed_features={"total_courses"})
    assert "Instructor-loyal" in unrestricted["label"]
    assert "Instructor-loyal" not in restricted["label"]


def test_mooc_labels_are_absent_from_the_vocabulary():
    """[R12]'s MOOC learner types require completion data this dataset lacks.

    Guarding the vocabulary is the mechanical form of the rule in
    `research/segmentation_research.md` §8.
    """
    from edupro.segmentation.profiling import NAMING_VOCABULARY

    forbidden = {"auditing", "completing", "sampling", "disengaging", "dropout", "churn"}
    phrases = {p.lower() for pair in NAMING_VOCABULARY.values() for p in pair}
    assert not (phrases & forbidden)


def test_level_purity_is_folded_into_the_name_when_a_cluster_is_pure():
    derived = {
        0: {"label": "Single-course learners", "evidence": [
            {"feature": "total_courses", "deviation": -0.5, "phrase": "Single-course"}
        ], "is_neutral": False, "note": ""},
    }
    composition = pd.DataFrame({"Beginner": [0.97], "Intermediate": [0.02], "Advanced": [0.01]})
    named = compose_segment_names(derived, composition)
    assert named[0]["label"].startswith("Beginner-level")
    assert named[0]["level_purity"] >= LEVEL_PURITY_THRESHOLD


def test_level_is_not_named_when_the_cluster_is_mixed():
    derived = {
        1: {"label": "High-volume learners", "evidence": [], "is_neutral": False, "note": ""},
    }
    composition = pd.DataFrame(
        {"Beginner": [0.39], "Intermediate": [0.16], "Advanced": [0.45]}, index=[1]
    )
    named = compose_segment_names(derived, composition)
    assert named[1]["label"] == "High-volume learners"
    assert named[1]["level_purity"] < LEVEL_PURITY_THRESHOLD


def test_depth_phrase_is_dropped_when_the_level_prefix_says_it():
    derived = {
        0: {"label": "Beginner-leaning Single-course learners", "evidence": [
            {"feature": "learning_depth_index", "deviation": -1.3, "phrase": "Beginner-leaning"},
            {"feature": "total_courses", "deviation": -0.5, "phrase": "Single-course"},
        ], "is_neutral": False, "note": ""},
    }
    composition = pd.DataFrame({"Beginner": [1.0], "Intermediate": [0.0], "Advanced": [0.0]})
    label = compose_segment_names(derived, composition)[0]["label"]
    assert label == "Beginner-level Single-course learners"
    assert label.count("Beginner") == 1


def test_labels_are_produced_for_every_cluster(learner_features: pd.DataFrame):
    labels = np.resize([0, 1, 2], len(learner_features))
    derived = label_clusters(learner_features, labels)
    assert set(derived) == {0, 1, 2}
    assert all("label" in info for info in derived.values())
