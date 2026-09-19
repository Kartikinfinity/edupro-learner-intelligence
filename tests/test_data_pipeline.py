"""Phase 2 tests: loading, validation, joining, aggregation and splitting.

Organised along the [R34] ML-Test-Score categories that apply to this project:
data tests, model-input tests, and infrastructure tests. Monitoring tests are out
of scope — there is no live serving — which is recorded as a deliberate exclusion
in ``research/production_research.md`` §5.
"""

from __future__ import annotations

import pandas as pd
import pytest

from edupro import config
from edupro.data.joins import build_interactions, course_popularity
from edupro.data.loader import DataIntegrityError, EduProData, load_all, load_sheet, verify_raw_workbook
from edupro.data.schema import COURSE_LEVELS, SHEET_SPECS
from edupro.data.validation import validate
from edupro.evaluation.splits import (
    apply_global_split,
    global_temporal_split,
    leave_one_out_split,
)
from edupro.features.learner import build_learner_features, category_profile


@pytest.fixture(scope="module")
def data() -> EduProData:
    return load_all()


@pytest.fixture(scope="module")
def interactions(data: EduProData) -> pd.DataFrame:
    return build_interactions(data, with_user_demographics=True, with_teacher=True)


# ---------------------------------------------------------------------------
# Data: loading and immutability
# ---------------------------------------------------------------------------
def test_raw_workbook_checksum_matches():
    assert verify_raw_workbook() == config.RAW_WORKBOOK_SHA256


def test_missing_workbook_raises_clearly(tmp_path):
    with pytest.raises(DataIntegrityError, match="not found"):
        verify_raw_workbook(tmp_path / "absent.xlsx")


def test_all_sheets_load_with_expected_row_counts(data: EduProData):
    assert len(data.users) == 3_000
    assert len(data.teachers) == 60
    assert len(data.courses) == 60
    assert len(data.transactions) == 10_000


def test_pii_is_dropped_at_load_time(data: EduProData):
    """PII must be absent from the frames, not merely unused downstream (ADR-0006)."""
    for frame in (data.users, data.teachers, data.courses, data.transactions):
        leaked = set(config.PII_COLUMNS) & set(frame.columns)
        assert not leaked, f"PII present after load: {leaked}"


def test_pii_can_be_loaded_only_by_explicit_opt_in():
    """The audit path must still be able to inspect PII columns deliberately."""
    with_pii = load_sheet(config.SHEET_USERS, drop_pii=False)
    assert "Email" in with_pii.columns
    assert "Email" not in load_sheet(config.SHEET_USERS).columns


def test_transactions_are_deterministically_ordered(data: EduProData):
    expected = data.transactions.sort_values(
        [config.KEY_USER, config.COL_TRANSACTION_DATE, config.KEY_TRANSACTION]
    ).reset_index(drop=True)
    pd.testing.assert_frame_equal(data.transactions, expected)


def test_unknown_sheet_name_is_rejected():
    with pytest.raises(KeyError):
        load_sheet("NotASheet")


# ---------------------------------------------------------------------------
# Data: validation
# ---------------------------------------------------------------------------
def test_validation_reports_no_errors(data: EduProData):
    report = validate(data)
    assert report.ok, f"unexpected validation errors: {[str(f) for f in report.errors]}"


def test_validation_detects_an_injected_orphan(data: EduProData):
    broken = data.transactions.copy()
    broken.loc[0, config.KEY_COURSE] = "CR99999"
    report = validate(
        EduProData(data.users, data.teachers, data.courses, broken)
    )
    assert not report.ok
    assert any(f.check == "orphan_fk" for f in report.errors)


def test_validation_detects_an_injected_out_of_domain_value(data: EduProData):
    broken = data.courses.copy()
    broken.loc[0, "CourseLevel"] = "Expert"
    report = validate(
        EduProData(data.users, data.teachers, broken, data.transactions)
    )
    assert any(f.check == "value_domain" for f in report.errors)


def test_validation_detects_an_injected_duplicate_key(data: EduProData):
    broken = pd.concat([data.users, data.users.iloc[[0]]], ignore_index=True)
    report = validate(
        EduProData(broken, data.teachers, data.courses, data.transactions)
    )
    assert any(f.check in {"uniqueness", "duplicate_rows"} for f in report.errors)


def test_every_sheet_spec_matches_the_loaded_columns(data: EduProData):
    for sheet, frame in (
        (config.SHEET_USERS, data.users),
        (config.SHEET_TEACHERS, data.teachers),
        (config.SHEET_COURSES, data.courses),
        (config.SHEET_TRANSACTIONS, data.transactions),
    ):
        spec = SHEET_SPECS[sheet]
        expected = set(spec.column_names) - set(spec.pii_columns)
        assert set(frame.columns) == expected


# ---------------------------------------------------------------------------
# Data: documented properties of this specific dataset
# ---------------------------------------------------------------------------
def test_no_repeat_user_course_pairs(data: EduProData):
    """The interaction signal is purely binary; several design decisions rest on it."""
    assert data.transactions.duplicated([config.KEY_USER, config.KEY_COURSE]).sum() == 0


def test_amount_equals_course_price_everywhere(data: EduProData):
    """EXP-002: spending is a deterministic function of catalogue choice."""
    merged = data.transactions.merge(
        data.courses[[config.KEY_COURSE, "CoursePrice"]], on=config.KEY_COURSE
    )
    assert (merged["Amount"].round(2) == merged["CoursePrice"].round(2)).all()


def test_course_type_is_determined_by_price(data: EduProData):
    free = data.courses[data.courses["CourseType"] == "Free"]
    paid = data.courses[data.courses["CourseType"] == "Paid"]
    assert (free["CoursePrice"] == 0).all()
    assert (paid["CoursePrice"] > 0).all()


def test_teacher_course_mapping_is_not_a_bijection(data: EduProData):
    """EXP-005 gate: a bijection would make the teacher experiment vacuous."""
    per_course = data.transactions.groupby(config.KEY_COURSE)[config.KEY_TEACHER].nunique()
    assert per_course.max() > 1


# ---------------------------------------------------------------------------
# Model input: joins
# ---------------------------------------------------------------------------
def test_join_preserves_row_count(data: EduProData, interactions: pd.DataFrame):
    assert len(interactions) == len(data.transactions)


def test_join_introduces_no_nulls(interactions: pd.DataFrame):
    assert not interactions.isna().any().any()


def test_level_ordinal_matches_the_declared_order(interactions: pd.DataFrame):
    for level, expected in zip(COURSE_LEVELS, range(len(COURSE_LEVELS))):
        subset = interactions[interactions["CourseLevel"] == level]
        assert (subset["LevelOrdinal"] == expected).all()


def test_teacher_demographics_are_never_joined(data: EduProData):
    """D-016: third-party demographics have no role in allocating recommendations."""
    frame = build_interactions(data, with_teacher=True)
    assert "TeacherAge" not in frame.columns
    # Teacher Age/Gender must not arrive under the learner's column names either.
    merged_gender = frame["Gender"].isin({"Female", "Male"})
    assert merged_gender.all()
    assert len(frame) == len(data.transactions)


def test_course_popularity_reflects_only_the_frame_given(interactions: pd.DataFrame):
    """Leakage control L5: popularity must come from the window it is passed."""
    subset = interactions.head(500)
    assert course_popularity(subset).sum() == 500
    assert course_popularity(interactions).sum() == len(interactions)


# ---------------------------------------------------------------------------
# Model input: learner features
# ---------------------------------------------------------------------------
def test_features_have_one_row_per_active_learner(data: EduProData, interactions: pd.DataFrame):
    features = build_learner_features(interactions, users=data.users)
    assert len(features) == data.transactions[config.KEY_USER].nunique()
    assert features.index.is_unique


def test_official_features_are_all_present(data: EduProData, interactions: pd.DataFrame):
    features = build_learner_features(interactions, users=data.users)
    official = {
        "age", "gender", "total_courses", "avg_courses_per_category",
        "enrollment_frequency", "preferred_category", "preferred_level",
        "avg_course_rating", "avg_spend", "diversity_score", "learning_depth_index",
    }
    missing = official - set(features.columns)
    assert not missing, f"official brief features missing: {missing}"


def test_total_courses_matches_the_raw_counts(data: EduProData, interactions: pd.DataFrame):
    features = build_learner_features(interactions)
    expected = data.transactions.groupby(config.KEY_USER).size()
    pd.testing.assert_series_equal(
        features["total_courses"].sort_index(),
        expected.sort_index(),
        check_names=False,
    )


def test_category_profile_rows_sum_to_one(interactions: pd.DataFrame):
    profile = category_profile(interactions)
    assert profile.shape[1] == 12
    assert ((profile.sum(axis=1) - 1.0).abs() < 1e-9).all()


def test_behaviour_only_features_exclude_demographics(interactions: pd.DataFrame):
    """Variant B must be constructible without demographics ever being present."""
    features = build_learner_features(interactions, users=None)
    assert "age" not in features.columns
    assert "gender" not in features.columns


def test_features_never_see_beyond_the_frame_they_are_given(interactions: pd.DataFrame):
    """Leakage control L1, as an executable test.

    Features built from the training window must be identical whether or not the
    full frame exists — i.e. the builder reads only its argument.
    """
    split = global_temporal_split(interactions)
    frames = apply_global_split(interactions, split)

    from_train = build_learner_features(frames["train"])
    from_train_again = build_learner_features(frames["train"].copy())
    pd.testing.assert_frame_equal(from_train, from_train_again)

    from_full = build_learner_features(interactions)
    shared = from_train.index.intersection(from_full.index)
    # If the builder leaked, training-window totals would match full-window totals.
    assert (from_train.loc[shared, "total_courses"]
            <= from_full.loc[shared, "total_courses"]).all()
    assert (from_train.loc[shared, "total_courses"]
            < from_full.loc[shared, "total_courses"]).any()


def test_recency_is_measured_inside_the_given_window(interactions: pd.DataFrame):
    split = global_temporal_split(interactions)
    train = apply_global_split(interactions, split)["train"]
    features = build_learner_features(train)
    assert features["recency_days"].min() == 0
    assert (features["recency_days"] >= 0).all()


def test_empty_interaction_frame_is_rejected(interactions: pd.DataFrame):
    with pytest.raises(ValueError):
        build_learner_features(interactions.iloc[0:0])


# ---------------------------------------------------------------------------
# Infrastructure: splits
# ---------------------------------------------------------------------------
def test_global_split_partitions_without_overlap(interactions: pd.DataFrame):
    split = global_temporal_split(interactions)
    frames = apply_global_split(interactions, split)
    train_ids = set(frames["train"][config.KEY_TRANSACTION])
    validation_ids = set(frames["validation"][config.KEY_TRANSACTION])
    test_ids = set(frames["test"][config.KEY_TRANSACTION])
    assert not train_ids & validation_ids
    assert not train_ids & test_ids
    assert not validation_ids & test_ids
    assert len(train_ids | validation_ids | test_ids) == len(interactions)


def test_global_split_respects_the_timeline(interactions: pd.DataFrame):
    """Protocol A's whole point: nothing in train happens after the test cut."""
    split = global_temporal_split(interactions)
    frames = apply_global_split(interactions, split)
    assert frames["fit"][config.COL_TRANSACTION_DATE].max() < split.test_date
    assert frames["test"][config.COL_TRANSACTION_DATE].min() >= split.test_date


def test_global_split_is_deterministic(interactions: pd.DataFrame):
    first = global_temporal_split(interactions)
    second = global_temporal_split(interactions)
    assert first == second


def test_protocol_a_is_viable_on_this_dataset(interactions: pd.DataFrame):
    """EXP-004's pre-registered decision. Documents the outcome as a regression guard."""
    split = global_temporal_split(interactions)
    assert split.protocol_a_viable
    assert split.n_evaluable_learners >= 300


def test_leave_one_out_excludes_single_interaction_learners(interactions: pd.DataFrame):
    """CLAUDE.md §12: they must not be scored as personalised-recommendation users."""
    loo = leave_one_out_split(interactions)
    counts = interactions.groupby(config.KEY_USER).size()
    singles = set(counts[counts == 1].index)
    assert not set(loo["test"][config.KEY_USER]) & singles
    assert len(loo["excluded_single_interaction"]) == len(singles)


def test_leave_one_out_holds_out_exactly_one_per_learner(interactions: pd.DataFrame):
    loo = leave_one_out_split(interactions)
    per_user = loo["test"].groupby(config.KEY_USER).size()
    assert (per_user == 1).all()


def test_leave_one_out_holds_out_the_most_recent(interactions: pd.DataFrame):
    loo = leave_one_out_split(interactions)
    held = loo["test"].set_index(config.KEY_USER)[config.COL_TRANSACTION_DATE]
    kept = loo["train"].groupby(config.KEY_USER)[config.COL_TRANSACTION_DATE].max()
    shared = held.index.intersection(kept.index)
    assert (held.loc[shared] >= kept.loc[shared]).all()
