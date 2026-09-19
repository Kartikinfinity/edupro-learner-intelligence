"""Regression tests for the defects the Phase 6A adversarial audit found.

Each test names the defect, states why it mattered, and fails if it returns. A fix
without a test is a fix with a shelf life — these three were all invisible to the
existing suite, because the existing suite tests what the code is *for* and these
were failures of what the code does when attacked.

The audit script (`scripts/adversarial_audit.py`) remains the broader instrument;
these are the specific findings promoted to permanent checks.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from edupro import config
from edupro.data.loader import load_all
from edupro.data.validation import validate
from edupro.inference import InferenceError, RecommendationService
from edupro.pipeline import CLUSTER_DTYPE


@pytest.fixture(scope="module")
def data():
    return load_all()


@pytest.fixture(scope="module")
def service():
    return RecommendationService.load()


# ---------------------------------------------------------------------------
# Finding 1 (critical) — the validator crashed on the corruption it exists to report
# ---------------------------------------------------------------------------
# Four cross-sheet checks indexed columns without checking they were present, so a
# missing column raised KeyError from inside the validator. The caller got an
# opaque crash instead of a report naming the missing column, and the pipeline's
# "refuse to train on invalid data" path never ran.


@pytest.mark.parametrize(
    "sheet, column",
    [
        ("transactions", "Amount"),
        ("transactions", config.COL_TRANSACTION_DATE),
        ("transactions", config.KEY_COURSE),
        ("courses", "CoursePrice"),
        ("courses", "CourseType"),
        ("courses", "CourseName"),
    ],
)
def test_validation_reports_a_missing_column_instead_of_crashing(data, sheet, column):
    frame = getattr(data, sheet)
    broken = replace(data, **{sheet: frame.drop(columns=[column])})

    report = validate(broken)  # must not raise

    assert not report.ok, f"dropping {column} should be an error"
    assert "columns_missing" in {f.check for f in report.errors}
    assert any(column in f.message for f in report.errors)


def test_validation_survives_losing_several_columns_at_once(data):
    broken = replace(
        data,
        transactions=data.transactions.drop(columns=["Amount", config.COL_TRANSACTION_DATE]),
        courses=data.courses.drop(columns=["CourseName", "CoursePrice"]),
    )
    report = validate(broken)
    assert not report.ok
    assert len(report.errors) >= 2


def test_the_pipeline_refuses_to_train_on_data_that_fails_validation(data, tmp_path):
    """A report nobody acts on is decoration; the refusal is the point."""
    from edupro.pipeline import PipelineError, train

    courses = data.courses.copy()
    courses.loc[courses.index[0], "CourseCategory"] = "Not A Real Category"

    with pytest.raises(PipelineError, match="failed validation"):
        train(
            models_dir=tmp_path / "models",
            artifacts_dir=tmp_path / "tables",
            data=replace(data, courses=courses),
            with_stability=False,
            verify_source=False,
        )


# ---------------------------------------------------------------------------
# Finding 2 — the "no candidates" error blamed filters that were never applied
# ---------------------------------------------------------------------------
# A learner with nothing left to recommend was told the cause was filtering, with
# a count of already-enrolled courses read from the wrong structure ("0" for a
# learner who had taken all 60). An error that misdiagnoses itself sends whoever
# reads it looking in the wrong place.


def test_exhausted_learner_error_names_the_real_cause(service):
    victim = "REGRESSION-EXHAUSTED"
    service.context.seen[victim] = set(range(len(service.catalogue)))
    try:
        with pytest.raises(InferenceError) as raised:
            service.recommend(victim, k=5)
    finally:
        service.context.seen.pop(victim, None)

    message = str(raised.value)
    assert "already taken all" in message
    assert str(len(service.catalogue)) in message
    assert "category=None" not in message, "must not blame a filter that was not applied"


def test_impossible_filter_error_names_the_filter(service):
    user = service.features.index[0]
    with pytest.raises(InferenceError) as raised:
        service.recommend(user, category="Data Science", level="NOT-A-LEVEL")
    message = str(raised.value)
    assert "Data Science" in message and "NOT-A-LEVEL" in message


# ---------------------------------------------------------------------------
# Finding 3 — cluster labels had two dtypes, so identical answers compared unequal
# ---------------------------------------------------------------------------
# The pipeline persisted scikit-learn's native label dtype (int32 on this
# platform) while inference returned platform int. The labels always agreed, but
# a dtype-strict comparison of two identical answers failed — which makes "does
# inference reproduce training?" unanswerable by the obvious check.


def test_cluster_labels_have_one_declared_dtype(service):
    assigned = service.assign_segment(service.features)
    persisted = service.features["cluster"]

    assert str(assigned.dtype) == CLUSTER_DTYPE
    assert str(persisted.dtype) == CLUSTER_DTYPE
    assert assigned.equals(persisted), "the strict comparison must hold, not just =="


def test_assignment_is_independent_of_input_column_order(service):
    """The representation builder selects columns by name. If it ever selected by
    position, input order would decide which statistics scale which feature — a
    corruption that changes every number and raises nothing."""
    import numpy as np

    from edupro.segmentation.representations import build_representation

    reversed_columns = service.features[list(reversed(service.features.columns))]
    normal = build_representation(service.features, service.spec, scaler=service.scaler)
    shuffled = build_representation(reversed_columns, service.spec, scaler=service.scaler)

    assert normal.columns == shuffled.columns
    assert np.abs(normal.matrix - shuffled.matrix).max() == 0.0
    assert service.assign_segment(reversed_columns).equals(service.features["cluster"])
