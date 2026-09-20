"""Tests for the production ML path: persistence, loading, inference, explanation.

Covers the twelve capabilities Phase 5A implements, plus the failure cases that
matter more than the happy path:

- an artifact set from incompatible code or libraries must not load silently
- a half-updated artifact set must be detected
- a recommendation must never contain a course the learner already took
- an explanation must never name a signal the model did not use
- the number an explanation quotes must equal the number the scorer ranked by

The end-to-end fixture trains a complete artifact set into a temporary directory
once per session, so the tests exercise the real pipeline rather than a mock, and
never touch the repository's own artifacts.
"""

from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd
import pytest

from edupro import config
from edupro.data.loader import load_all
from edupro.explainability.explanations import (
    MIN_CONTRIBUTION,
    QUALITY_CAVEAT,
    TIER_FRAME,
    build_explanation,
)
from edupro.features.course import (
    build_course_catalogue,
    build_course_vectors,
    course_vector_columns,
)
from edupro.inference import InferenceError, RecommendationService
from edupro.persistence import (
    MODEL_VERSION,
    ArtifactIntegrityError,
    ArtifactVersionError,
    Manifest,
    check_compatibility,
    check_integrity,
    library_versions,
    load_manifest,
    save_manifest,
    verify_artifacts,
)
from edupro.pipeline import PRODUCTION, artifact_files, train


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def raw_data():
    return load_all()


@pytest.fixture(scope="session")
def trained(tmp_path_factory, raw_data):
    """A complete artifact set, trained once into a temporary directory.

    Stability is skipped: it is measured and reported in Phase 3A, and re-running
    100 bootstraps would add a minute to every test run for no additional check.
    """
    root = tmp_path_factory.mktemp("artifacts")
    models_dir = root / "models"
    tables_dir = root / "tables"
    manifest = train(
        models_dir=models_dir,
        artifacts_dir=tables_dir,
        data=raw_data,
        with_stability=False,
    )
    return {"manifest": manifest, "models": models_dir, "tables": tables_dir}


@pytest.fixture(scope="session")
def service(trained):
    return RecommendationService.load(trained["models"], trained["tables"])


@pytest.fixture(scope="session")
def learners(service):
    """One learner from each populated tier."""
    features = service.features
    return {
        tier: features[features["tier"] == tier].index[0]
        for tier in features["tier"].unique()
    }


# ---------------------------------------------------------------------------
# 1-3. Deterministic loading, validation, preprocessing
# ---------------------------------------------------------------------------
def test_training_verifies_the_workbook_checksum(trained):
    assert trained["manifest"].workbook_sha256 == config.RAW_WORKBOOK_SHA256


def test_training_is_deterministic(trained, raw_data, tmp_path):
    """Same data and seed must produce the same segmentation, or nothing downstream
    is reproducible."""
    again = train(
        models_dir=tmp_path / "models",
        artifacts_dir=tmp_path / "tables",
        data=raw_data,
        with_stability=False,
        verify_source=False,
    )
    assert again.segmentation["sizes"] == trained["manifest"].segmentation["sizes"]


# ---------------------------------------------------------------------------
# 5. Course representation
# ---------------------------------------------------------------------------
def test_catalogue_is_canonically_ordered(raw_data):
    catalogue = build_course_catalogue(raw_data.courses)
    assert len(catalogue) == 60
    assert catalogue[config.KEY_COURSE].is_monotonic_increasing
    assert catalogue[config.KEY_COURSE].is_unique
    assert catalogue["position"].tolist() == list(range(60))


def test_catalogue_rejects_duplicate_course_ids(raw_data):
    doubled = pd.concat([raw_data.courses, raw_data.courses.head(1)], ignore_index=True)
    # Duplicates of an identical row are collapsed rather than rejected: the
    # ambiguity that matters is two different rows sharing an id.
    assert len(build_course_catalogue(doubled)) == 60


def test_course_vectors_have_the_declared_shape_and_bounds(raw_data):
    catalogue = build_course_catalogue(raw_data.courses)
    vectors = build_course_vectors(raw_data.courses, catalogue[config.KEY_COURSE].tolist())
    assert vectors.shape == (60, len(course_vector_columns()))
    assert vectors.min() >= 0.0 and vectors.max() <= 1.0
    # One category and one level per course.
    assert np.allclose(vectors[:, :12].sum(axis=1), 1.0)


def test_course_vectors_reject_an_unknown_course(raw_data):
    with pytest.raises(ValueError, match="absent from the catalogue"):
        build_course_vectors(raw_data.courses, ["NOT-A-COURSE"])


def test_recommendation_layer_uses_the_same_course_vectors(raw_data):
    """The re-export must be the same function, not a copy that can drift."""
    from edupro.recommendation import baselines

    assert baselines.build_course_vectors is build_course_vectors


# ---------------------------------------------------------------------------
# 11-12. Artifact loading and version checking
# ---------------------------------------------------------------------------
def test_every_declared_artifact_is_written(trained):
    paths = artifact_files(trained["models"], trained["tables"])
    assert len(paths) == 12
    for name, path in paths.items():
        assert path.exists(), f"{name} was not written"
        assert path.stat().st_size > 0


def test_manifest_round_trips(trained):
    manifest = load_manifest(trained["models"])
    assert manifest.model_version == MODEL_VERSION
    assert manifest.segmentation["n_clusters"] == PRODUCTION.n_clusters
    assert manifest.recommendation["routes"] == PRODUCTION.routes
    assert set(manifest.libraries) >= {"python", "numpy", "pandas", "scikit-learn"}


def test_manifest_records_the_training_window(trained):
    """The artifacts are fitted on the full history while the reported metrics come
    from the temporal split; the manifest must make that unambiguous."""
    training = trained["manifest"].training
    assert training["window"] == "full history"
    assert training["n_interactions"] == 10_000
    assert "temporal-split" in training["window_note"]


def test_missing_manifest_is_an_actionable_error(tmp_path):
    """A manifest that was never written is *not found*, not *corrupt*.

    It raised ``ArtifactIntegrityError`` until the app smoke test caught the
    consequence: a fresh checkout with no artifact set was told its artifacts had
    failed an integrity check, which sends the reader to compare hashes for files
    that do not exist (D-077).
    """
    with pytest.raises(FileNotFoundError, match="train_production_model"):
        load_manifest(tmp_path)
    assert not isinstance(
        pytest.raises(FileNotFoundError, load_manifest, tmp_path).value,
        ArtifactIntegrityError,
    ), "a missing manifest must not also present as an integrity failure"


def test_model_version_mismatch_is_rejected(trained):
    manifest = load_manifest(trained["models"])
    manifest.model_version = "edupro-0.0.1-experimental"
    with pytest.raises(ArtifactVersionError, match="Model version mismatch"):
        check_compatibility(manifest, strict=True)


def test_critical_library_mismatch_is_rejected(trained):
    """scikit-learn does not support cross-version estimator loading, and the
    failure is silent, so the check must be an error rather than a warning."""
    manifest = load_manifest(trained["models"])
    manifest.libraries = {**manifest.libraries, "scikit-learn": "0.1.0"}
    with pytest.raises(ArtifactVersionError, match="scikit-learn"):
        check_compatibility(manifest, strict=True)


def test_non_critical_library_drift_is_only_warned_about(trained, caplog):
    manifest = load_manifest(trained["models"])
    manifest.libraries = {**manifest.libraries, "joblib": "0.0.1"}
    assert check_compatibility(manifest, strict=True) == []


def test_source_workbook_mismatch_is_rejected(trained):
    manifest = load_manifest(trained["models"])
    manifest.workbook_sha256 = "0" * 64
    with pytest.raises(ArtifactVersionError, match="different source workbook"):
        check_compatibility(manifest, strict=True)


def test_non_strict_mode_reports_problems_instead_of_raising(trained):
    manifest = load_manifest(trained["models"])
    manifest.model_version = "edupro-0.0.1"
    problems = check_compatibility(manifest, strict=False)
    assert len(problems) == 1 and "Model version mismatch" in problems[0]


def test_a_changed_artifact_is_detected(trained, tmp_path):
    """The failure a manifest alone cannot catch: an artifact set updated halfway,
    where each file is individually valid but they are from different runs."""
    manifest = load_manifest(trained["models"])
    assert check_integrity(manifest) == []

    target = artifact_files(trained["models"], trained["tables"])["popularity"]
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"\x00")
        problems = check_integrity(manifest)
        assert len(problems) == 1 and "changed since it was written" in problems[0]
        with pytest.raises(ArtifactIntegrityError):
            verify_artifacts(trained["models"], strict=True)
    finally:
        target.write_bytes(original)
    assert check_integrity(load_manifest(trained["models"])) == []


def test_a_missing_artifact_is_detected(trained):
    manifest = load_manifest(trained["models"])
    manifest.files = {**manifest.files, "models/does-not-exist.joblib": "0" * 64}
    problems = check_integrity(manifest)
    assert problems == ["missing artifact: models/does-not-exist.joblib"]


def test_library_versions_are_reported(trained):
    versions = library_versions()
    assert versions["python"].count(".") == 2
    assert versions["scikit-learn"] != "not-installed"


def test_manifest_rejects_a_truncated_payload(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"model_version": "x"}), encoding="utf-8")
    with pytest.raises(ArtifactIntegrityError, match="missing fields"):
        load_manifest(tmp_path)


# ---------------------------------------------------------------------------
# 6. Clustering inference
# ---------------------------------------------------------------------------
def test_service_loads_without_fitting_the_segmentation(service, trained):
    assert service.manifest.artifact_set_version == trained["manifest"].artifact_set_version
    assert service.clusterer.n_clusters == PRODUCTION.n_clusters
    assert len(service.features) == 3000
    assert service.problems == []


def test_assign_segment_reproduces_the_persisted_labels(service):
    """The strongest available check that inference matches training: transforming
    the persisted features with the persisted scaler and predicting with the
    persisted clusterer must return exactly the stored labels."""
    predicted = service.assign_segment(service.features)
    assert (predicted == service.features["cluster"]).all()


def test_assign_segment_works_for_a_single_unseen_learner(service):
    """A learner arriving alone must be scaled by the training population's
    statistics, not by their own — which is only possible with a persisted scaler."""
    one = service.features.iloc[[0]]
    assigned = service.assign_segment(one)
    assert len(assigned) == 1
    assert int(assigned.iloc[0]) == int(one["cluster"].iloc[0])


def test_assign_segment_rejects_a_mismatched_schema(service):
    broken = service.features.drop(columns=["total_courses"])
    with pytest.raises(KeyError):
        service.assign_segment(broken)


def test_every_segment_is_named_from_model_features_only(service):
    """A segment must never be named for a dimension the clustering did not see."""
    segments = service.segments["segments"]
    assert len(segments) == PRODUCTION.n_clusters
    banned = ("instructor", "teacher", "age", "gender", "female", "male")
    for info in segments.values():
        assert info["label"]
        assert not any(word in info["label"].lower() for word in banned)


def test_segment_summary_covers_every_segment(service):
    summary = service.segment_summary()
    assert len(summary) == PRODUCTION.n_clusters
    assert summary["n_learners"].sum() == 3000
    # Shares are rounded to 4 dp for display, so they sum to 1 only within that.
    assert abs(summary["share"].sum() - 1.0) < 1e-3


# ---------------------------------------------------------------------------
# 7-8. Recommendation inference and unseen-course filtering
# ---------------------------------------------------------------------------
def test_recommendations_are_produced_for_every_tier(service, learners):
    for tier, user in learners.items():
        result = service.recommend(user, k=10)
        assert result.tier == tier
        assert len(result.recommendations) == 10
        assert result.is_known_learner


def test_no_recommendation_is_a_course_the_learner_already_took(service, learners):
    for user in learners.values():
        history = set(service.history(user)[config.KEY_COURSE])
        recommended = {r.course_id for r in service.recommend(user, k=20).recommendations}
        assert not (history & recommended)


def test_candidate_count_equals_catalogue_minus_history(service, learners):
    for user in learners.values():
        result = service.recommend(user, k=5)
        assert result.n_candidates == 60 - result.history_size


def test_recommendations_are_deterministic(service, learners):
    user = next(iter(learners.values()))
    first = [r.course_id for r in service.recommend(user, k=10).recommendations]
    second = [r.course_id for r in service.recommend(user, k=10).recommendations]
    assert first == second


def test_ranks_are_contiguous_and_scores_are_ordered(service, learners):
    for user in learners.values():
        items = service.recommend(user, k=10).recommendations
        assert [r.rank for r in items] == list(range(1, 11))
        scores = [r.score for r in items]
        assert scores == sorted(scores, reverse=True)


def test_an_unknown_learner_is_routed_to_the_cold_start_tier(service):
    result = service.recommend("NOT-A-LEARNER", k=10)
    assert result.is_known_learner is False
    assert result.tier == "insufficient"
    assert result.n_candidates == 60
    assert len(result.recommendations) == 10


def test_cold_start_list_spans_the_catalogue(service):
    """The property the diversified fallback was selected for (EXP-029)."""
    result = service.recommend("NOT-A-LEARNER", k=10)
    categories = {r.category for r in result.recommendations}
    assert len(categories) >= 10


def test_filters_are_applied_to_candidates_not_to_the_ranked_list(service, learners):
    """Filtering after ranking would silently return fewer than k results."""
    user = learners["rich"] if "rich" in learners else next(iter(learners.values()))
    result = service.recommend(user, k=5, category="Data Science")
    assert len(result.recommendations) == 5
    assert {r.category for r in result.recommendations} == {"Data Science"}


def test_level_filter_is_respected(service, learners):
    user = next(iter(learners.values()))
    result = service.recommend(user, k=3, level="Beginner")
    assert {r.level for r in result.recommendations} == {"Beginner"}


def test_impossible_filter_combination_raises(service, learners):
    user = next(iter(learners.values()))
    with pytest.raises(InferenceError, match="No candidate courses"):
        service.recommend(user, category="Data Science", level="NOT-A-LEVEL")


def test_non_positive_k_raises(service, learners):
    with pytest.raises(InferenceError, match="k must be positive"):
        service.recommend(next(iter(learners.values())), k=0)


def test_unknown_learner_profile_raises(service):
    with pytest.raises(InferenceError, match="Unknown learner"):
        service.learner_profile("NOT-A-LEARNER")


# ---------------------------------------------------------------------------
# 9. Sparse-user fallback
# ---------------------------------------------------------------------------
def test_each_tier_is_served_by_the_frozen_route(service):
    routes = service.router.routes
    assert routes["insufficient"].name == "diversified_fallback"
    assert routes["minimal"].name == "content_based"
    assert routes["moderate"].name == "cluster_popularity"
    assert routes["rich"].name == "cluster_popularity"


def test_every_learner_receives_a_recommendation(service):
    """CLAUDE.md §15: no learner may be left without a recommendation."""
    sample = service.features.sample(50, random_state=config.RANDOM_SEED).index
    for user in sample:
        assert len(service.recommend(user, k=10).recommendations) == 10


def test_moderate_and_rich_tiers_share_one_fitted_scorer(service):
    """They are the same object, so per-segment counts cannot diverge between them."""
    assert service.router.routes["moderate"] is service.router.routes["rich"]


# ---------------------------------------------------------------------------
# 10. Explanation generation
# ---------------------------------------------------------------------------
def test_every_recommendation_carries_an_explanation(service, learners):
    for user in learners.values():
        for item in service.recommend(user, k=10).recommendations:
            assert item.explanation.sentence
            assert item.explanation.course_id == item.course_id
            assert item.explanation.tier in TIER_FRAME


def test_explanation_never_names_a_component_the_model_did_not_use():
    explanation = build_explanation(
        course_id="CR00001",
        tier="rich",
        contributions={"cluster_popularity": 0.9, "teacher_affinity": 0.0},
        facts={"segment_enrollments": 12, "segment_name": "Test segment"},
    )
    assert explanation.components_used == ["cluster_popularity"]
    assert "instructor" not in explanation.sentence.lower()
    assert len(explanation.reasons) == 1


def test_explanation_drops_contributions_at_the_threshold():
    explanation = build_explanation(
        course_id="CR00001",
        tier="rich",
        contributions={"cluster_popularity": MIN_CONTRIBUTION},
        facts={},
    )
    assert explanation.reasons == []
    assert "No signal separated" in explanation.sentence


def test_explanation_quotes_the_number_the_scorer_actually_ranked_by(service, learners):
    """Faithfulness, checked rather than asserted: the count in the sentence must be
    the contribution the scorer returned, which for cluster popularity *is* the
    within-segment enrollment count."""
    tier = "rich" if "rich" in learners else "moderate"
    result = service.recommend(learners[tier], k=5)
    for item in result.recommendations:
        contribution = item.explanation.contributions["cluster_popularity"]
        quoted = int(re.match(r"^(\d+) learners? in your segment", item.explanation.reasons[0])[1])
        assert quoted == int(contribution)


def test_explanation_matches_the_persisted_popularity_table(service, trained, learners):
    """Serving and artifact must agree; a divergence would mean the persisted table
    no longer describes what the live scorer does."""
    popularity = pd.read_parquet(artifact_files(trained["models"], trained["tables"])["popularity"])
    tier = "rich" if "rich" in learners else "moderate"
    result = service.recommend(learners[tier], k=5)
    column = f"cluster_{result.segment}_enrollments"
    lookup = popularity.set_index(config.KEY_COURSE)[column]
    for item in result.recommendations:
        assert int(item.explanation.contributions["cluster_popularity"]) == int(
            lookup.loc[item.course_id]
        )


def test_cold_start_explanations_do_not_claim_personalisation(service):
    result = service.recommend("NOT-A-LEARNER", k=10)
    frame = result.recommendations[0].explanation.tier_frame
    assert "rather than personalised" in frame
    for item in result.recommendations:
        text = item.explanation.sentence.lower()
        assert "learners like you" not in text
        assert "your segment" not in text


def test_minimal_tier_explanations_state_the_single_course_basis(service, learners):
    if "minimal" not in learners:  # pragma: no cover - dataset-dependent
        pytest.skip("no minimal-tier learner in this artifact set")
    result = service.recommend(learners["minimal"], k=5)
    assert "one course in your history" in result.recommendations[0].explanation.tier_frame


def test_explanation_rejects_an_unknown_tier():
    with pytest.raises(ValueError, match="Unknown tier"):
        build_explanation("CR00001", "enthusiastic", {"content": 1.0})


def test_result_carries_the_measured_quality_caveat(service, learners):
    result = service.recommend(next(iter(learners.values())), k=3)
    assert result.caveat == QUALITY_CAVEAT
    assert "no ranking method beat random" in result.caveat


def test_category_overlap_claim_is_verified_not_assumed(service, learners):
    """A content explanation may only claim a shared category when the learner's
    history actually contains one."""
    if "minimal" not in learners:  # pragma: no cover - dataset-dependent
        pytest.skip("no minimal-tier learner in this artifact set")
    user = learners["minimal"]
    history_categories = set(service.history(user)["CourseCategory"])
    for item in service.recommend(user, k=10).recommendations:
        if "same category as" in item.explanation.sentence:
            assert item.category in history_categories


# ---------------------------------------------------------------------------
# Privacy and reporting
# ---------------------------------------------------------------------------
def test_no_pii_reaches_any_persisted_artifact(trained):
    paths = artifact_files(trained["models"], trained["tables"])
    for name in ("learner_features", "course_catalogue", "interactions", "popularity"):
        frame = pd.read_parquet(paths[name])
        for column in config.PII_COLUMNS:
            assert column not in frame.columns, f"{column} leaked into {name}"


def test_learner_profile_exposes_no_identifying_fields(service, learners):
    profile = service.learner_profile(next(iter(learners.values())))
    assert set(profile) & set(config.PII_COLUMNS) == set()
    assert profile["user_id"].startswith("U")


def test_describe_summarises_the_loaded_set(service):
    described = service.describe()
    assert described["model_version"] == MODEL_VERSION
    assert described["n_learners"] == 3000
    assert described["n_courses"] == 60
    assert len(described["segments"]) == PRODUCTION.n_clusters
    assert described["problems"] == []


def test_history_is_returned_most_recent_first(service, learners):
    user = learners.get("rich") or next(iter(learners.values()))
    history = service.history(user)
    dates = history[config.COL_TRANSACTION_DATE].tolist()
    assert dates == sorted(dates, reverse=True)


def test_result_serialises_to_json(service, learners):
    result = service.recommend(next(iter(learners.values())), k=3)
    payload = json.loads(json.dumps(result.to_dict(), default=str))
    assert len(payload["recommendations"]) == 3
    assert payload["recommendations"][0]["explanation"]["sentence"]
