"""Regression tests for the defects the Phase 6A adversarial audit found.

Each test names the defect, states why it mattered, and fails if it returns. A fix
without a test is a fix with a shelf life — these three were all invisible to the
existing suite, because the existing suite tests what the code is *for* and these
were failures of what the code does when attacked.

The audit script (`scripts/adversarial_audit.py`) remains the broader instrument;
these are the specific findings promoted to permanent checks.
"""

from __future__ import annotations

import hashlib
import subprocess
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


# ---------------------------------------------------------------------------
# Finding 4 (critical) — artifacts hashed on Windows failed on Linux
# ---------------------------------------------------------------------------
# The manifest records a SHA-256 of every artifact and the loader re-hashes them
# at startup. Three artifacts are JSON, and `.gitattributes` had `* text=auto`,
# so git stored them with LF and checked them out with CRLF on Windows. The hash
# recorded on Windows therefore did not match the bytes a Linux runner received,
# `check_integrity` correctly reported them as changed, and the first public
# deployment showed the missing-artifacts empty state.
#
# The Phase 6E readiness audit missed it because it ran `check_integrity` against
# the Windows working copy, where the hashes match by construction. The only check
# that catches it compares the manifest against what *git* stores.


def _git_blob(relative_path: str) -> bytes:
    """The bytes git holds for this path — the staged index, not HEAD.

    The index is what the next commit contains and therefore what a clone
    receives. Comparing against HEAD would make this test red whenever artifacts
    have been regenerated but not yet committed, which is a normal working state.
    """
    result = subprocess.run(
        ["git", "show", f":{relative_path}"],
        capture_output=True, cwd=config.PROJECT_ROOT,
    )
    return result.stdout


def test_committed_artifact_bytes_match_the_recorded_hashes():
    """What git hands a Linux runner must hash to what the manifest recorded."""
    from edupro.persistence import load_manifest

    manifest = load_manifest()
    drifted = []
    for relative, recorded in manifest.files.items():
        blob = _git_blob(relative.replace("\\", "/"))
        if not blob:
            continue  # not yet committed; a different test covers tracked-ness
        if hashlib.sha256(blob).hexdigest() != recorded:
            drifted.append(relative)
    assert not drifted, (
        "these artifacts are stored by git with different bytes than the manifest "
        f"recorded, so the app fails its integrity check after checkout: {drifted}"
    )


def test_json_artifacts_are_written_with_lf():
    """CRLF in a hashed artifact reintroduces the platform dependency."""
    from edupro.pipeline import artifact_files

    for name, path in artifact_files().items():
        if path.suffix != ".json" or not path.exists():
            continue
        assert b"\r\n" not in path.read_bytes(), f"{name} contains CRLF"
    manifest = config.MODELS_DIR / "manifest.json"
    assert b"\r\n" not in manifest.read_bytes(), "manifest.json contains CRLF"


def test_gitattributes_exempts_artifact_json_from_eol_conversion():
    """Writing LF is not enough on its own: git would convert it back on checkout."""
    rules = (config.PROJECT_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "models/*.json" in rules and "-text" in rules
    assert "artifacts/production/*.json" in rules


# ---------------------------------------------------------------------------
# Finding 5 — the empty state misdiagnosed the failure it was reporting
# ---------------------------------------------------------------------------
# The first failed deployment was an *integrity* failure: every artifact was
# present and readable, and three of them no longer hashed to the manifest value.
# The page announced "Model artifacts not found", which sent the reader looking
# for missing files that were sitting in the checkout. Same class as Finding 2 —
# an error that blames the wrong cause is worse than a bare exception, because it
# is confidently wrong and people believe it.


def _loaders_module():
    """Import `app/lib/loaders.py`, which is not on the package path."""
    import importlib.util

    path = config.PROJECT_ROOT / "app" / "lib" / "loaders.py"
    spec = importlib.util.spec_from_file_location("edupro_app_loaders", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_each_load_failure_has_its_own_heading():
    from edupro.persistence import ArtifactIntegrityError, ArtifactVersionError

    guide = _loaders_module()._FAILURE_GUIDE

    assert set(guide) == {ArtifactIntegrityError, ArtifactVersionError, FileNotFoundError}
    headings = [entry[0] for entry in guide.values()]
    assert len(set(headings)) == 3, f"failures share a heading: {headings}"


def test_an_integrity_failure_is_not_reported_as_a_missing_file():
    """The exact misdiagnosis the first deployment showed."""
    from edupro.persistence import ArtifactIntegrityError

    heading, cause, _ = _loaders_module()._FAILURE_GUIDE[ArtifactIntegrityError]

    assert "not found" not in heading.lower()
    assert "not found" not in cause.lower()
    assert "integrity" in heading.lower()


# ---------------------------------------------------------------------------
# Finding 6 (critical) — the manifest recorded Windows paths, and every check
# normalised them away before looking
# ---------------------------------------------------------------------------
# `_manifest_key` used `str(Path)`, which emits the *platform* separator, so the
# manifest written on Windows recorded `models\scaler.joblib`. On Linux that is
# not a path: it is one filename containing a backslash. Every artifact resolved
# to nothing, `check_integrity` reported all twelve as missing, and the public
# deployment served the empty state on every page.
#
# This is the finding the Phase 6E audit, probe 3c and the Finding 4 tests all
# missed, and they missed it the same way: each one called `.replace("\\", "/")`
# on the manifest key before using it. Three independent checks, one shared
# assumption, and the assumption was the bug. A check that repairs its input
# cannot fail on the defect it repairs.
#
# So these tests read the key exactly as stored.


def test_manifest_keys_use_forward_slashes():
    """Read verbatim: normalising here is what hid the defect for three checks."""
    from edupro.persistence import load_manifest

    offenders = [key for key in load_manifest().files if "\\" in key]
    assert not offenders, (
        "manifest keys contain Windows separators, which resolve to nothing on "
        f"Linux and report every artifact as missing: {offenders}"
    )


def test_artifacts_resolve_from_the_manifest_key_without_repair():
    """Exactly what `check_integrity` does, with no separator fix-up."""
    from edupro.persistence import load_manifest

    missing = [
        key for key in load_manifest().files if not (config.PROJECT_ROOT / key).exists()
    ]
    assert not missing, f"manifest keys do not resolve as written: {missing}"


def test_manifest_key_is_posix_even_for_a_windows_path():
    """The unit that produced the bad key."""
    from edupro.pipeline import _manifest_key

    key = _manifest_key(config.MODELS_DIR / "scaler.joblib")
    assert key == "models/scaler.joblib"
    assert "\\" not in key


def test_a_windows_style_key_still_resolves_on_a_posix_checkout(tmp_path):
    """Old artifact sets must not become unreadable; the loader reads both."""
    from edupro.persistence import resolve_manifest_key

    target = tmp_path / "models" / "scaler.joblib"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x")

    assert resolve_manifest_key("models" + chr(92) + "scaler.joblib", tmp_path) == target
    assert resolve_manifest_key("models/scaler.joblib", tmp_path) == target
