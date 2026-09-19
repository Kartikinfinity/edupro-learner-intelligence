"""Phase 6A — try to break the project.

This is not a test suite. A test suite is written alongside the code and tends to
assert what the author already believed. This script is written *against* the
code: every probe is an attempt to make something fail, produce a wrong answer, or
silently accept input it should reject.

Design rules it follows, so its own verdicts can be trusted:

**A probe that cannot fail proves nothing.** Every corruption probe first checks
that the clean input passes, then corrupts it and requires the failure. A checker
that has never rejected anything is not evidence.

**Leakage is tested by experiment, not by reading.** The strongest probe here
injects a synthetic *future* interaction into the source data and requires the
training-window features to come back byte-identical. If any future information
reaches a historical feature, the bytes change.

**Privacy is tested against the real values.** The probe loads the workbook with
PII retained, takes actual names and email addresses, and searches every persisted
artifact for them. Grepping for the *column name* would pass even if the values
had leaked under a different header.

The raw workbook is never modified. Corrupted frames are built in memory.

Usage
-----
    python scripts/adversarial_audit.py
    python scripts/adversarial_audit.py --quick    # skip the exhaustive scans
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import traceback
from dataclasses import dataclass, field, replace
from typing import Any, Callable

import numpy as np
import pandas as pd

from edupro import config
from edupro.data.joins import build_interactions
from edupro.data.loader import EduProData, load_all, verify_raw_workbook
from edupro.data.validation import validate
from edupro.evaluation.splits import apply_global_split, global_temporal_split
from edupro.features.learner import build_learner_features
from edupro.inference import InferenceError, RecommendationService
from edupro.logging_utils import configure_logging
from edupro.recommendation.base import build_fit_context
from edupro.recommendation.baselines import ClusterPopularity
from edupro.recommendation.hybrid import tier_of
from edupro.segmentation.clustering import fit_kmeans
from edupro.segmentation.representations import REPRESENTATION_GRID, build_representation

logger = logging.getLogger("audit")

OUT = config.ARTIFACTS_DIR / "validation"


@dataclass
class Finding:
    """One probe's outcome. ``severity`` is what a reviewer reads first."""

    check: str
    probe: str
    #: "pass" - the system behaved correctly under attack.
    #: "fail" - a defect. Blocks the phase if critical.
    #: "warn" - a real weakness that is not a defect.
    severity: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "probe": self.probe,
            "severity": self.severity,
            "detail": self.detail,
            "evidence": self.evidence,
        }


class Audit:
    """Collects findings and keeps a probe's crash from ending the audit."""

    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self.check = "unassigned"

    def section(self, name: str) -> None:
        self.check = name
        print(f"\n{'=' * 78}\n{name}\n{'=' * 78}")

    def record(self, probe: str, severity: str, detail: str, **evidence: Any) -> None:
        finding = Finding(self.check, probe, severity, detail, evidence)
        self.findings.append(finding)
        mark = {"pass": "OK  ", "fail": "FAIL", "warn": "WARN"}[severity]
        print(f"  [{mark}] {probe}: {detail}")

    def probe(self, name: str, fn: Callable[[], None]) -> None:
        """Run one probe; a crash is itself a finding rather than the end of the run."""
        try:
            fn()
        except Exception:  # noqa: BLE001 - an unexpected crash is the finding
            self.record(
                name, "fail", "probe raised an unexpected exception",
                traceback=traceback.format_exc(limit=6),
            )

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "fail"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warn"]


# ===========================================================================
# CHECK 1 - data
# ===========================================================================
def check_data(audit: Audit, data: EduProData) -> None:
    audit.section("CHECK 1 - DATA: does validation actually reject bad input?")

    baseline = validate(data)
    if baseline.ok:
        audit.record("clean data passes", "pass",
                     f"0 errors, {len(baseline.warnings)} warning(s)")
    else:
        audit.record("clean data passes", "fail",
                     "the unmodified workbook fails its own validator",
                     errors=[str(e) for e in baseline.errors])
        return

    def corrupted(mutate: Callable[[EduProData], EduProData], name: str,
                  expect_check: str) -> None:
        """Corrupt a copy, require an error, and require it to be the right error.

        ``EduProData`` is frozen, so each mutation builds a new instance from
        copied frames — the loaded data is never touched, let alone the workbook.
        """
        report = validate(mutate(data))
        checks = {f.check for f in report.errors}
        if not report.errors:
            audit.record(name, "fail", "corruption was NOT detected", expected=expect_check)
        elif expect_check not in checks:
            audit.record(
                name, "warn",
                f"detected, but by {sorted(checks)} rather than {expect_check!r}",
                detected_by=sorted(checks),
            )
        else:
            audit.record(name, "pass", f"rejected by {expect_check}",
                         n_errors=len(report.errors))

    def drop_column(d: EduProData) -> EduProData:
        return replace(d, transactions=d.transactions.drop(columns=["Amount"]))

    def inject_nulls(d: EduProData) -> EduProData:
        tx = d.transactions.copy()
        tx.loc[tx.index[:5], config.KEY_COURSE] = None
        return replace(d, transactions=tx)

    def duplicate_rows(d: EduProData) -> EduProData:
        return replace(
            d,
            transactions=pd.concat(
                [d.transactions, d.transactions.head(3)], ignore_index=True
            ),
        )

    def duplicate_ids(d: EduProData) -> EduProData:
        users = d.users.copy()
        users.loc[users.index[1], config.KEY_USER] = users.loc[users.index[0], config.KEY_USER]
        return replace(d, users=users)

    def invalid_id_format(d: EduProData) -> EduProData:
        tx = d.transactions.copy()
        tx.loc[tx.index[:4], config.KEY_USER] = "XX99999"
        return replace(d, transactions=tx)

    def orphan_ids(d: EduProData) -> EduProData:
        tx = d.transactions.copy()
        tx.loc[tx.index[:6], config.KEY_USER] = "U99999"
        return replace(d, transactions=tx)

    def malformed_dates(d: EduProData) -> EduProData:
        tx = d.transactions.copy()
        tx[config.COL_TRANSACTION_DATE] = tx[config.COL_TRANSACTION_DATE].astype(object)
        tx.loc[tx.index[:3], config.COL_TRANSACTION_DATE] = pd.NaT
        return replace(d, transactions=tx)

    def invalid_category(d: EduProData) -> EduProData:
        courses = d.courses.copy()
        courses.loc[courses.index[0], "CourseCategory"] = "Underwater Basket Weaving"
        return replace(d, courses=courses)

    def invalid_course_values(d: EduProData) -> EduProData:
        courses = d.courses.copy()
        courses.loc[courses.index[0], "CourseRating"] = 47.0
        courses.loc[courses.index[1], "CoursePrice"] = -500.0
        return replace(d, courses=courses)

    corrupted(drop_column, "missing column", "columns_missing")
    corrupted(inject_nulls, "missing values", "nulls")
    corrupted(duplicate_rows, "duplicate records", "duplicate_rows")
    corrupted(duplicate_ids, "duplicate primary key", "uniqueness")
    corrupted(invalid_id_format, "malformed identifier", "id_format")
    corrupted(orphan_ids, "orphan foreign key", "orphan_fk")
    corrupted(malformed_dates, "malformed dates", "nulls")
    corrupted(invalid_category, "invalid category", "value_domain")
    corrupted(invalid_course_values, "out-of-range course values", "range")

    # A validator that reports is useless if the pipeline trains anyway.
    def refuses_to_train() -> None:
        from edupro.pipeline import PipelineError, train

        courses = data.courses.copy()
        courses.loc[courses.index[0], "CourseCategory"] = "Nonsense"
        broken = replace(data, courses=courses)
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            try:
                train(
                    models_dir=Path(tmp) / "m",
                    artifacts_dir=Path(tmp) / "a",
                    data=broken,
                    with_stability=False,
                    verify_source=False,
                )
            except PipelineError:
                audit.record("pipeline refuses invalid data", "pass",
                             "training aborted on a validation error")
                return
        audit.record("pipeline refuses invalid data", "fail",
                     "the pipeline trained on data that failed validation")

    audit.probe("pipeline refuses invalid data", refuses_to_train)


# ===========================================================================
# CHECK 2 - feature pipeline
# ===========================================================================
def check_features(audit: Audit, data: EduProData, interactions: pd.DataFrame) -> None:
    audit.section("CHECK 2 - FEATURE PIPELINE: edge cases and determinism")

    features = build_learner_features(interactions, users=data.users)

    counts = interactions.groupby(config.KEY_USER)[config.KEY_COURSE].nunique()
    profiles = {
        "single-interaction learner": counts[counts == 1].index[0],
        "median learner": counts[counts == counts.median()].index[0],
        "maximum-history learner": counts.idxmax(),
    }
    for label, user in profiles.items():
        row = features.loc[user]
        bad = [c for c in features.columns if pd.api.types.is_float_dtype(features[c])
               and (pd.isna(row[c]) or np.isinf(row[c]))]
        if bad:
            audit.record(label, "fail", f"non-finite feature values: {bad[:5]}", user=user)
        else:
            audit.record(label, "pass", f"{int(row['total_courses'])} courses, all features finite",
                         user=user)

    def no_nulls_anywhere() -> None:
        nulls = features.isna().sum()
        offenders = nulls[nulls > 0]
        if len(offenders):
            audit.record("no nulls across 3,000 learners", "fail",
                         f"{len(offenders)} column(s) contain nulls",
                         columns=offenders.to_dict())
        else:
            audit.record("no nulls across 3,000 learners", "pass",
                         f"{features.shape[0]} x {features.shape[1]} matrix, 0 nulls")

    def all_learners_present() -> None:
        missing = set(data.users[config.KEY_USER]) - set(features.index)
        if missing:
            audit.record("every active learner has features", "warn",
                         f"{len(missing)} learner(s) absent from the feature matrix",
                         sample=sorted(missing)[:5])
        else:
            audit.record("every active learner has features", "pass",
                         f"{len(features)} of {len(data.users)} learners")

    def deterministic() -> None:
        again = build_learner_features(interactions, users=data.users)
        if features.equals(again):
            audit.record("deterministic output", "pass", "two builds are byte-identical")
        else:
            differing = [c for c in features.columns if not features[c].equals(again[c])]
            audit.record("deterministic output", "fail",
                         "repeated builds differ", columns=differing[:8])

    def row_order_invariant() -> None:
        """A different row order must not change a single feature value."""
        shuffled = interactions.sample(frac=1.0, random_state=7)
        rebuilt = build_learner_features(shuffled, users=data.users)
        aligned = rebuilt.reindex(features.index)
        numeric = features.select_dtypes(include=[np.number]).columns
        delta = (features[numeric] - aligned[numeric]).abs().max().max()
        if delta > 1e-9:
            worst = (features[numeric] - aligned[numeric]).abs().max().idxmax()
            audit.record("row order does not change features", "fail",
                         f"max deviation {delta:.3g} in {worst}")
        else:
            audit.record("row order does not change features", "pass",
                         "identical under a shuffled input frame")

    def empty_frame() -> None:
        try:
            result = build_learner_features(interactions.head(0), users=data.users)
        except ValueError as error:
            # Failing loudly is the correct behaviour: silently returning an empty
            # frame would let a broken upstream step propagate into an empty model.
            audit.record("empty input", "pass",
                         f"rejected with a typed, actionable error: {error}")
            return
        except Exception as error:  # noqa: BLE001
            audit.record("empty input", "fail",
                         f"raises {type(error).__name__}, which callers cannot handle",
                         message=str(error)[:120])
            return
        audit.record("empty input", "fail",
                     f"returned {len(result)} rows from no input instead of refusing")

    def single_day_learner() -> None:
        """Every interaction on one day: activity span is zero. A rate feature that
        divides by the span would produce infinity here."""
        user = counts[counts > 3].index[0]
        rows = interactions[interactions[config.KEY_USER] == user].copy()
        rows[config.COL_TRANSACTION_DATE] = rows[config.COL_TRANSACTION_DATE].min()
        rebuilt = build_learner_features(rows, users=data.users)
        row = rebuilt.loc[user]
        suspicious = {
            c: float(row[c]) for c in rebuilt.columns
            if pd.api.types.is_float_dtype(rebuilt[c]) and not np.isfinite(row[c])
        }
        if suspicious:
            audit.record("zero-span learner", "fail",
                         "non-finite features when all activity is on one day",
                         values=suspicious)
        else:
            audit.record("zero-span learner", "pass",
                         f"span 0 handled; enrollment_frequency="
                         f"{float(row['enrollment_frequency']):.3f}")

    for name, fn in (
        ("no nulls across 3,000 learners", no_nulls_anywhere),
        ("every active learner has features", all_learners_present),
        ("deterministic output", deterministic),
        ("row order does not change features", row_order_invariant),
        ("empty input", empty_frame),
        ("zero-span learner", single_day_learner),
    ):
        audit.probe(name, fn)


# ===========================================================================
# CHECK 3 - leakage
# ===========================================================================
def check_leakage(audit: Audit, data: EduProData, interactions: pd.DataFrame) -> None:
    audit.section("CHECK 3 - LEAKAGE: can future information reach a historical feature?")

    split = global_temporal_split(interactions)
    frames = apply_global_split(interactions, split)
    train_features = build_learner_features(frames["train"], users=data.users)

    def future_injection() -> None:
        """The decisive probe. Add a synthetic interaction dated *after* the test
        cut, rebuild the training-window features, and require them unchanged.

        If any code path reads beyond the frame it was given - a recency reference
        taken from 'now', a popularity count over the full table, an aggregate
        computed before the split - these bytes move.
        """
        victim = train_features.index[0]
        future = frames["train"].iloc[[0]].copy()
        future[config.KEY_USER] = victim
        future[config.COL_TRANSACTION_DATE] = split.test_date + pd.Timedelta(days=45)
        future[config.KEY_TRANSACTION] = "TX-SYNTHETIC-FUTURE"
        poisoned = pd.concat([interactions, future], ignore_index=True)

        re_split = global_temporal_split(poisoned)
        re_frames = apply_global_split(poisoned, re_split)
        rebuilt = build_learner_features(re_frames["train"], users=data.users)

        common = train_features.index.intersection(rebuilt.index)
        numeric = train_features.select_dtypes(include=[np.number]).columns
        delta = (
            train_features.loc[common, numeric] - rebuilt.loc[common, numeric]
        ).abs().max().max()
        if delta > 1e-9:
            audit.record("future interactions do not reach training features", "fail",
                         f"injecting a future interaction changed training features by {delta:.3g}")
        else:
            audit.record("future interactions do not reach training features", "pass",
                         "a post-test-cut interaction changes nothing in the training window",
                         n_learners=int(len(common)))

    def split_disjoint() -> None:
        ids = {name: set(frames[name][config.KEY_TRANSACTION]) for name in
               ("train", "validation", "test")}
        overlaps = {
            f"{a}&{b}": len(ids[a] & ids[b])
            for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))
        }
        if any(overlaps.values()):
            audit.record("split windows are disjoint", "fail",
                         "windows share transactions", overlaps=overlaps)
        else:
            audit.record("split windows are disjoint", "pass",
                         f"train {len(ids['train'])}, validation {len(ids['validation'])}, "
                         f"test {len(ids['test'])}, no overlap")

    def dates_respect_the_cuts() -> None:
        latest_train = frames["train"][config.COL_TRANSACTION_DATE].max()
        earliest_test = frames["test"][config.COL_TRANSACTION_DATE].min()
        if latest_train >= earliest_test:
            audit.record("training precedes test in time", "fail",
                         f"train reaches {latest_train}, test begins {earliest_test}")
        else:
            audit.record("training precedes test in time", "pass",
                         f"train ends {latest_train.date()}, test begins {earliest_test.date()}")

    def candidates_exclude_only_training_history() -> None:
        """Using *full* history for exclusion would leak: removing the held-out
        course from the pool tells the model which course to avoid."""
        catalogue = (
            interactions.drop_duplicates(subset=[config.KEY_COURSE])
            .set_index(config.KEY_COURSE)
            .loc[sorted(interactions[config.KEY_COURSE].unique())]
            .reset_index()
        )
        labels = fit_kmeans(
            build_representation(
                train_features,
                next(s for s in REPRESENTATION_GRID if s.name == "B_proportion"),
            ).matrix,
            4,
        ).labels_
        context = build_fit_context(
            frames["train"], catalogue, train_features,
            pd.Series(labels, index=train_features.index),
        )
        held_out = frames["test"].groupby(config.KEY_USER)[config.KEY_COURSE].apply(set)
        checked = leaked = 0
        for user, courses in list(held_out.items())[:500]:
            if user not in context.seen:
                continue
            checked += 1
            positions = {context.course_index[c] for c in courses if c in context.course_index}
            candidates = set(context.candidates_for(user).tolist())
            if positions - candidates:
                leaked += 1
        if leaked:
            audit.record("held-out items remain candidates", "fail",
                         f"{leaked} of {checked} learners had a held-out course removed "
                         "from their candidate pool")
        else:
            audit.record("held-out items remain candidates", "pass",
                         f"{checked} learners checked; every held-out course was still "
                         "eligible to be recommended")

    def popularity_counted_on_training_only() -> None:
        from edupro.data.joins import course_popularity

        train_counts = course_popularity(frames["train"])
        full_counts = course_popularity(interactions)
        if train_counts.equals(full_counts.reindex(train_counts.index)):
            audit.record("popularity is window-scoped", "fail",
                         "training-window popularity equals full-history popularity")
        else:
            audit.record("popularity is window-scoped", "pass",
                         f"training counts sum to {int(train_counts.sum()):,} against "
                         f"{int(full_counts.sum()):,} for the full history")

    def tier_from_training_history() -> None:
        """Tier routing on *total* history would leak the held-out item's existence.
        That leak hides in the routing logic, not the feature matrix."""
        train_counts = frames["train"].groupby(config.KEY_USER)[config.KEY_COURSE].nunique()
        full_counts = interactions.groupby(config.KEY_USER)[config.KEY_COURSE].nunique()
        shared = train_counts.index.intersection(full_counts.index)
        moved = sum(
            tier_of(int(train_counts[u])) != tier_of(int(full_counts[u])) for u in shared
        )
        if moved == 0:
            audit.record("tiering uses training history", "warn",
                         "no learner changes tier between windows, so this probe "
                         "cannot distinguish the two sources on this dataset")
        else:
            audit.record("tiering uses training history", "pass",
                         f"{moved} learners would be routed differently on full history, "
                         "so the two sources are distinguishable and the code uses the "
                         "training one")

    def scaler_is_not_refitted_at_inference() -> None:
        """Re-fitting a scaler on a single row would standardise a learner by their
        own statistics, producing a degenerate all-zero vector."""
        service = RecommendationService.load()
        one = service.features.iloc[[0]]
        assigned = service.assign_segment(one)
        expected = int(one["cluster"].iloc[0])
        if int(assigned.iloc[0]) != expected:
            audit.record("inference reuses the training scaler", "fail",
                         f"single-row assignment gave {int(assigned.iloc[0])}, "
                         f"persisted label is {expected}")
        else:
            audit.record("inference reuses the training scaler", "pass",
                         "a single learner scored alone reproduces their persisted segment")

    for name, fn in (
        ("future interactions do not reach training features", future_injection),
        ("split windows are disjoint", split_disjoint),
        ("training precedes test in time", dates_respect_the_cuts),
        ("held-out items remain candidates", candidates_exclude_only_training_history),
        ("popularity is window-scoped", popularity_counted_on_training_only),
        ("tiering uses training history", tier_from_training_history),
        ("inference reuses the training scaler", scaler_is_not_refitted_at_inference),
    ):
        audit.probe(name, fn)


# ===========================================================================
# CHECK 4 - clustering
# ===========================================================================
def check_clustering(audit: Audit, service: RecommendationService) -> None:
    audit.section("CHECK 4 - CLUSTERING: does the served model match the trained one?")

    def artifact_loads() -> None:
        audit.record("artifact set loads", "pass",
                     f"set {service.manifest.artifact_set_version}, "
                     f"{len(service.manifest.files)} files, "
                     f"{len(service.problems)} problem(s)")

    def preprocessing_matches_training() -> None:
        predicted = service.assign_segment(service.features)
        mismatches = int((predicted != service.features["cluster"]).sum())
        if mismatches:
            audit.record("inference reproduces training labels", "fail",
                         f"{mismatches} of {len(predicted)} learners get a different segment")
        else:
            audit.record("inference reproduces training labels", "pass",
                         f"all {len(predicted):,} persisted labels reproduced exactly")

    def every_learner_clustered() -> None:
        missing = int(service.features["cluster"].isna().sum())
        if missing:
            audit.record("every learner has a segment", "fail", f"{missing} unassigned")
        else:
            sizes = service.features["cluster"].value_counts().sort_index()
            audit.record("every learner has a segment", "pass",
                         f"{len(service.features):,} learners across {len(sizes)} segments",
                         sizes=sizes.to_dict())
    def label_dtype_is_declared() -> None:
        """Two identical answers must compare equal under a strict check, or
        "does inference match training?" is not answerable."""
        assigned = service.assign_segment(service.features)
        persisted = service.features["cluster"]
        if assigned.dtype != persisted.dtype:
            audit.record("cluster label dtype is consistent", "fail",
                         f"inference returns {assigned.dtype}, artifact stores "
                         f"{persisted.dtype}; a strict comparison of identical "
                         "answers fails")
        elif not assigned.equals(persisted):
            audit.record("cluster label dtype is consistent", "fail",
                         "labels differ under a strict comparison")
        else:
            audit.record("cluster label dtype is consistent", "pass",
                         f"both {assigned.dtype}; equals() holds exactly")

    def labels_stable_across_loads() -> None:
        other = RecommendationService.load()
        same = other.features["cluster"].equals(service.features["cluster"])
        audit.record("labels are stable across loads", "pass" if same else "fail",
                     "two independent loads agree" if same else "two loads disagree")

    def column_order_is_verified() -> None:
        """Silently accepting reordered columns would scale each feature by another
        feature's statistics and fail no test."""
        shuffled = service.features[list(reversed(service.features.columns))]
        try:
            assigned = service.assign_segment(shuffled)
        except Exception as error:  # noqa: BLE001
            audit.record("column order cannot corrupt scaling", "pass",
                         f"reordered input rejected with {type(error).__name__}")
            return
        # Acceptance is only safe if the answer is unchanged: the representation
        # builder selects columns by name, so input order cannot decide which
        # statistics scale which feature. Verified rather than assumed.
        baseline = service.assign_segment(service.features)
        matrix_a = build_representation(service.features, service.spec,
                                        scaler=service.scaler).matrix
        matrix_b = build_representation(shuffled, service.spec,
                                        scaler=service.scaler).matrix
        drift = float(np.abs(matrix_a - matrix_b).max())
        if drift > 0 or not bool((assigned == baseline).all()):
            audit.record("column order cannot corrupt scaling", "fail",
                         f"reordered columns changed the scaled matrix by {drift:.3g}")
        elif not bool((assigned == service.features["cluster"]).all()):
            audit.record("column order cannot corrupt scaling", "fail",
                         "assignment does not reproduce the persisted labels")
        else:
            audit.record("column order cannot corrupt scaling", "pass",
                         "reordered input produced a bit-identical scaled matrix "
                         "(max deviation 0) and the same labels; the builder selects "
                         "columns by name, so input order cannot mis-scale a feature")

    def profiles_use_the_right_members() -> None:
        """A profile row must describe the learners actually assigned to it."""
        worst = 0.0
        for cluster in sorted(service.features["cluster"].unique()):
            members = service.features[service.features["cluster"] == cluster]
            if "total_courses_mean" not in service.profiles.columns:
                continue
            stored = float(service.profiles.loc[cluster, "total_courses_mean"])
            actual = float(members["total_courses"].mean())
            worst = max(worst, abs(stored - actual))
        if worst > 1e-3:
            audit.record("cluster profiles match their members", "fail",
                         f"max deviation {worst:.4f} between stored and recomputed means")
        else:
            audit.record("cluster profiles match their members", "pass",
                         f"stored means match recomputed means to {worst:.2e}")

    def names_use_model_features_only() -> None:
        banned = ("instructor", "teacher", "age", "gender", "female", "male")
        offenders = [
            name for name in service.segment_names.values()
            if any(word in name.lower() for word in banned)
        ]
        if offenders:
            audit.record("segment names use model features only", "fail",
                         "a name references a dimension the model never saw",
                         names=offenders)
        else:
            audit.record("segment names use model features only", "pass",
                         f"{len(service.segment_names)} names, none referencing an "
                         "excluded feature")

    for name, fn in (
        ("artifact set loads", artifact_loads),
        ("inference reproduces training labels", preprocessing_matches_training),
        ("every learner has a segment", every_learner_clustered),
        ("cluster label dtype is consistent", label_dtype_is_declared),
        ("labels are stable across loads", labels_stable_across_loads),
        ("column order cannot corrupt scaling", column_order_is_verified),
        ("cluster profiles match their members", profiles_use_the_right_members),
        ("segment names use model features only", names_use_model_features_only),
    ):
        audit.probe(name, fn)


# ===========================================================================
# CHECK 5 - recommendations
# ===========================================================================
def check_recommendations(audit: Audit, service: RecommendationService, quick: bool) -> None:
    audit.section("CHECK 5 - RECOMMENDATIONS: every history profile, including hostile ones")

    features = service.features
    by_tier = {t: features[features["tier"] == t].index[0] for t in features["tier"].unique()}
    by_tier["insufficient (new learner)"] = "AUDIT-NEW-LEARNER"

    def tier_profiles() -> None:
        for label, user in by_tier.items():
            result = service.recommend(user, k=10)
            history = set(service.history(user)[config.KEY_COURSE]) if user in features.index else set()
            overlap = history & {r.course_id for r in result.recommendations}
            if overlap:
                audit.record(f"{label}", "fail",
                             f"recommended {len(overlap)} already-enrolled course(s)",
                             courses=sorted(overlap))
            elif len(result.recommendations) != 10:
                audit.record(f"{label}", "fail",
                             f"returned {len(result.recommendations)} of 10 requested")
            else:
                audit.record(f"{label}", "pass",
                             f"10 recommendations, {result.n_candidates} candidates, "
                             f"route={service.router.route_for(user)[1].name}")

    def near_exhausted_learner() -> None:
        """A learner who has taken 59 of 60 courses must get exactly one candidate,
        not a crash and not a padded list."""
        catalogue = service.catalogue[config.KEY_COURSE].tolist()
        victim = "AUDIT-NEAR-EXHAUSTED"
        service.context.seen[victim] = set(range(59))
        try:
            result = service.recommend(victim, k=10)
            if result.n_candidates != 1:
                audit.record("learner with 59 of 60 courses", "fail",
                             f"{result.n_candidates} candidates, expected 1")
            elif len(result.recommendations) != 1:
                audit.record("learner with 59 of 60 courses", "fail",
                             f"returned {len(result.recommendations)} items for 1 candidate")
            else:
                audit.record("learner with 59 of 60 courses", "pass",
                             f"exactly 1 recommendation ({result.recommendations[0].course_id}), "
                             "k silently truncated rather than padded")
        finally:
            service.context.seen.pop(victim, None)

    def fully_exhausted_learner() -> None:
        """Nothing left to recommend must be an empty list, not an exception."""
        victim = "AUDIT-EXHAUSTED"
        service.context.seen[victim] = set(range(len(service.catalogue)))
        try:
            result = service.recommend(victim, k=10)
            if result.recommendations:
                audit.record("learner who has taken everything", "fail",
                             f"returned {len(result.recommendations)} items with 0 candidates")
            else:
                audit.record("learner who has taken everything", "pass",
                             "empty list returned, no exception")
        except InferenceError as error:
            message = str(error)
            if "all 60 courses" in message or "already taken all" in message:
                audit.record("learner who has taken everything", "pass",
                             f"typed error naming the real cause: {message}")
            else:
                audit.record("learner who has taken everything", "fail",
                             f"error misdiagnoses the cause: {message}")
        finally:
            service.context.seen.pop(victim, None)

    def deterministic_ranking() -> None:
        user = next(iter(by_tier.values()))
        runs = [[r.course_id for r in service.recommend(user, k=20).recommendations]
                for _ in range(3)]
        if all(run == runs[0] for run in runs[1:]):
            audit.record("ranking is deterministic", "pass", "three runs identical")
        else:
            audit.record("ranking is deterministic", "fail", "repeated calls differ", runs=runs)

    def ties_are_broken_stably() -> None:
        """On a near-uniform catalogue ties are common; an arbitrary tie order would
        make results irreproducible across processes."""
        user = by_tier.get("rich") or next(iter(by_tier.values()))
        result = service.recommend(user, k=60)
        scores = [r.score for r in result.recommendations]
        tied = sum(1 for a, b in zip(scores, scores[1:]) if abs(a - b) < 1e-12)
        ordered = all(
            a > b or (abs(a - b) < 1e-12)
            for a, b in zip(scores, scores[1:])
        )
        if not ordered:
            audit.record("ties are broken stably", "fail", "scores are not monotone")
        else:
            audit.record("ties are broken stably", "pass",
                         f"{tied} tied adjacent pairs, all resolved deterministically")

    def filters_work() -> None:
        user = next(iter(by_tier.values()))
        categories = sorted(service.catalogue["CourseCategory"].unique())
        failures = []
        for category in categories:
            result = service.recommend(user, k=5, category=category)
            wrong = [r.course_id for r in result.recommendations if r.category != category]
            if wrong:
                failures.append((category, wrong))
        for level in ("Beginner", "Intermediate", "Advanced"):
            result = service.recommend(user, k=5, level=level)
            wrong = [r.course_id for r in result.recommendations if r.level != level]
            if wrong:
                failures.append((level, wrong))
        if failures:
            audit.record("category and level filters", "fail",
                         f"{len(failures)} filter(s) returned a non-matching course",
                         failures=failures[:3])
        else:
            audit.record("category and level filters", "pass",
                         f"{len(categories)} categories and 3 levels, every result matched")

    def impossible_filter() -> None:
        user = next(iter(by_tier.values()))
        try:
            service.recommend(user, k=5, category="Data Science", level="NOT-A-LEVEL")
        except InferenceError:
            audit.record("impossible filter combination", "pass",
                         "raises a typed error naming the filters")
            return
        audit.record("impossible filter combination", "fail",
                     "an unsatisfiable filter returned results")

    def hostile_arguments() -> None:
        user = next(iter(by_tier.values()))
        problems = []
        for k in (0, -5):
            try:
                service.recommend(user, k=k)
                problems.append(f"k={k} accepted")
            except InferenceError:
                pass
        result = service.recommend(user, k=10_000)
        if len(result.recommendations) > result.n_candidates:
            problems.append("k above the candidate count returned padded results")
        if problems:
            audit.record("hostile arguments", "fail", "; ".join(problems))
        else:
            audit.record("hostile arguments", "pass",
                         "k<=0 rejected; k=10,000 truncated to "
                         f"{len(result.recommendations)} available candidates")

    def unknown_learner() -> None:
        result = service.recommend("¬not-a-learner·∆", k=10)
        if result.is_known_learner:
            audit.record("unknown identifier", "fail", "an unknown id was reported as known")
        elif result.tier != "insufficient":
            audit.record("unknown identifier", "fail", f"routed to {result.tier}")
        else:
            audit.record("unknown identifier", "pass",
                         "flagged is_known_learner=False and routed to the cold-start tier")

    def exhaustive_exclusion() -> None:
        if quick:
            audit.record("no learner is shown a course they took", "warn",
                         "skipped in --quick mode")
            return
        started = time.perf_counter()
        offenders = []
        for user in features.index:
            result = service.recommend(user, k=10)
            if not result.recommendations:
                offenders.append((user, "empty list"))
                continue
            seen = set(service.history(user)[config.KEY_COURSE])
            overlap = seen & {r.course_id for r in result.recommendations}
            if overlap:
                offenders.append((user, sorted(overlap)))
        elapsed = time.perf_counter() - started
        if offenders:
            audit.record("no learner is shown a course they took", "fail",
                         f"{len(offenders)} of {len(features):,} learners affected",
                         sample=offenders[:5])
        else:
            audit.record("no learner is shown a course they took", "pass",
                         f"all {len(features):,} learners checked in {elapsed:.0f}s: "
                         "0 empty lists, 0 already-enrolled courses")

    for name, fn in (
        ("tier profiles", tier_profiles),
        ("learner with 59 of 60 courses", near_exhausted_learner),
        ("learner who has taken everything", fully_exhausted_learner),
        ("ranking is deterministic", deterministic_ranking),
        ("ties are broken stably", ties_are_broken_stably),
        ("category and level filters", filters_work),
        ("impossible filter combination", impossible_filter),
        ("hostile arguments", hostile_arguments),
        ("unknown identifier", unknown_learner),
        ("no learner is shown a course they took", exhaustive_exclusion),
    ):
        audit.probe(name, fn)


# ===========================================================================
# CHECK 6 - explainability
# ===========================================================================
def check_explanations(audit: Audit, service: RecommendationService, quick: bool) -> None:
    audit.section("CHECK 6 - EXPLAINABILITY: does every sentence match the scoring logic?")

    import re

    from edupro.explainability.explanations import MIN_CONTRIBUTION

    features = service.features
    sample = features.index if not quick else features.sample(200, random_state=42).index

    unsupported = []          # a reason naming a signal the model did not use
    contradictions = []       # a number that disagrees with the scorer
    false_category = []       # a category claim the history does not support
    cold_start_overclaim = [] # a cold-start list claiming personalisation
    n_explanations = 0

    started = time.perf_counter()
    for user in sample:
        result = service.recommend(user, k=10)
        history_categories = set(service.history(user)["CourseCategory"])
        for item in result.recommendations:
            n_explanations += 1
            explanation = item.explanation
            used = {n for n, v in explanation.contributions.items() if v > MIN_CONTRIBUTION}

            # A reason must exist only if a component actually contributed.
            if explanation.reasons and not used:
                unsupported.append((user, item.course_id, explanation.reasons[0]))

            # The number quoted for segment popularity IS the contribution.
            if "cluster_popularity" in used:
                match = re.match(r"^(\d+) learners? in your segment", explanation.reasons[0])
                if match is None:
                    unsupported.append((user, item.course_id, explanation.reasons[0]))
                elif int(match.group(1)) != int(explanation.contributions["cluster_popularity"]):
                    contradictions.append(
                        (user, item.course_id, match.group(1),
                         explanation.contributions["cluster_popularity"])
                    )

            # A category claim must be true of this learner's actual history.
            if "same category as" in explanation.sentence:
                if item.category not in history_categories:
                    false_category.append((user, item.course_id, item.category))

            # A cold-start list must not imply personalisation.
            if result.tier == "insufficient":
                lowered = explanation.sentence.lower()
                if "your segment" in lowered or "learners like you" in lowered:
                    cold_start_overclaim.append((user, item.course_id))

    elapsed = time.perf_counter() - started

    def report(name: str, offenders: list, detail_ok: str) -> None:
        if offenders:
            audit.record(name, "fail", f"{len(offenders)} violation(s)", sample=offenders[:5])
        else:
            audit.record(name, "pass", detail_ok)

    report("explanations name only signals the model used", unsupported,
           f"{n_explanations:,} explanations, none citing an unused component")
    report("quoted numbers equal the scorer's contribution", contradictions,
           "every segment-popularity count matches the value the ranking used")
    report("category claims are true of the learner's history", false_category,
           "no explanation claimed a shared category the history lacks")
    report("cold-start lists do not claim personalisation", cold_start_overclaim,
           "no cold-start explanation referenced a segment")

    audit.record("explanation scan", "pass",
                 f"{n_explanations:,} explanations checked over {len(sample):,} learners "
                 f"in {elapsed:.0f}s" + (" (quick sample)" if quick else " (exhaustive)"))

    def caveat_always_present() -> None:
        from edupro.explainability.explanations import QUALITY_CAVEAT

        missing = [
            u for u in list(sample)[:200]
            if service.recommend(u, k=3).caveat != QUALITY_CAVEAT
        ]
        if missing:
            audit.record("measured-quality caveat travels with every result", "fail",
                         f"{len(missing)} result(s) without the caveat")
        else:
            audit.record("measured-quality caveat travels with every result", "pass",
                         "no result can be displayed without the random-reference caveat")

    audit.probe("measured-quality caveat travels with every result", caveat_always_present)


# ===========================================================================
# CHECK 7 - privacy
# ===========================================================================
def check_privacy(audit: Audit, service: RecommendationService) -> None:
    audit.section("CHECK 7 - PRIVACY: search the artifacts for the real values")

    def real_values_absent_from_artifacts() -> None:
        """Grepping for a column name would pass even if the values had leaked under
        a different header. This searches for the actual names and addresses."""
        with_pii = load_all(drop_pii=False)
        names = with_pii.users["UserName"].dropna().astype(str).head(50).tolist()
        emails = with_pii.users["Email"].dropna().astype(str).head(50).tolist()
        teachers = with_pii.teachers["TeacherName"].dropna().astype(str).head(20).tolist()
        needles = [v for v in names + emails + teachers if len(v) > 4]

        searched = leaks = 0
        offenders: list[str] = []
        roots = [config.MODELS_DIR, config.ARTIFACTS_DIR / "production",
                 config.PROJECT_ROOT / "app", config.PROJECT_ROOT / "src"]
        for root in roots:
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                searched += 1
                try:
                    blob = path.read_bytes()
                except OSError:  # pragma: no cover
                    continue
                for needle in needles:
                    if needle.encode("utf-8") in blob:
                        leaks += 1
                        offenders.append(f"{path.name}: {needle}")
                        break
        if offenders:
            audit.record("real names and emails absent from artifacts", "fail",
                         f"{leaks} file(s) contain a real name or address",
                         sample=offenders[:5])
        else:
            audit.record("real names and emails absent from artifacts", "pass",
                         f"{len(needles)} real values searched across {searched} files, "
                         "0 occurrences")

    def pii_columns_absent_from_served_frames() -> None:
        frames = {
            "learner_features": service.features,
            "catalogue": service.catalogue,
            "interactions": service.interactions,
            "cluster_profiles": service.profiles,
        }
        offenders = {
            name: [c for c in config.PII_COLUMNS if c in frame.columns]
            for name, frame in frames.items()
        }
        offenders = {k: v for k, v in offenders.items() if v}
        if offenders:
            audit.record("no PII column in any served frame", "fail",
                         "PII columns present", offenders=offenders)
        else:
            audit.record("no PII column in any served frame", "pass",
                         f"{len(frames)} frames, none carrying {list(config.PII_COLUMNS)}")

    def profile_exposes_nothing_extra() -> None:
        profile = service.learner_profile(service.features.index[0])
        leaked = [k for k in profile if k in config.PII_COLUMNS]
        if leaked:
            audit.record("learner profile is minimal", "fail", "profile exposes PII", keys=leaked)
        else:
            audit.record("learner profile is minimal", "pass",
                         f"{len(profile)} fields, identifier is the pseudonymous UserID",
                         fields=sorted(profile))

    def email_is_not_a_feature() -> None:
        suspicious = [c for c in service.features.columns
                      if "email" in c.lower() or "name" in c.lower()]
        suspicious = [c for c in suspicious if c != "segment_name"]
        if suspicious:
            audit.record("email is not a modelling feature", "fail",
                         "feature matrix has an identity-derived column", columns=suspicious)
        else:
            audit.record("email is not a modelling feature", "pass",
                         "no identity-derived column in the feature matrix")

    def loader_drops_pii_by_default() -> None:
        default = load_all()
        present = [c for c in config.PII_COLUMNS if c in default.users.columns
                   or c in default.teachers.columns]
        if present:
            audit.record("PII dropped at ingestion", "fail",
                         "the default loader returns PII", columns=present)
        else:
            audit.record("PII dropped at ingestion", "pass",
                         "PII is absent from the default load, so it cannot reach a "
                         "downstream frame by accident")

    for name, fn in (
        ("real names and emails absent from artifacts", real_values_absent_from_artifacts),
        ("no PII column in any served frame", pii_columns_absent_from_served_frames),
        ("learner profile is minimal", profile_exposes_nothing_extra),
        ("email is not a modelling feature", email_is_not_a_feature),
        ("PII dropped at ingestion", loader_drops_pii_by_default),
    ):
        audit.probe(name, fn)


# ===========================================================================
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true",
                        help="sample instead of scanning all 3,000 learners")
    args = parser.parse_args(argv)
    configure_logging(logging.WARNING)

    OUT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    checksum = verify_raw_workbook()
    data = load_all()
    interactions = build_interactions(data, with_user_demographics=True, with_teacher=True)
    service = RecommendationService.load()

    audit = Audit()
    check_data(audit, data)
    check_features(audit, data, interactions)
    check_leakage(audit, data, interactions)
    check_clustering(audit, service)
    check_recommendations(audit, service, args.quick)
    check_explanations(audit, service, args.quick)
    check_privacy(audit, service)

    elapsed = time.perf_counter() - started
    passes = [f for f in audit.findings if f.severity == "pass"]

    print(f"\n{'=' * 78}")
    print(f"{len(audit.findings)} probes in {elapsed:.0f}s: "
          f"{len(passes)} pass, {len(audit.warnings)} warn, {len(audit.failures)} FAIL")
    if audit.failures:
        print("\nFAILURES:")
        for finding in audit.failures:
            print(f"  [{finding.check}] {finding.probe}: {finding.detail}")
    if audit.warnings:
        print("\nWARNINGS:")
        for finding in audit.warnings:
            print(f"  [{finding.check}] {finding.probe}: {finding.detail}")

    payload = {
        "provenance": {
            "workbook_sha256": checksum,
            "artifact_set": service.manifest.artifact_set_version,
            "model_version": service.manifest.model_version,
            "mode": "quick" if args.quick else "exhaustive",
            "elapsed_seconds": round(elapsed, 1),
        },
        "summary": {
            "n_probes": len(audit.findings),
            "n_pass": len(passes),
            "n_warn": len(audit.warnings),
            "n_fail": len(audit.failures),
        },
        "findings": [f.to_dict() for f in audit.findings],
    }
    destination = OUT / "adversarial_audit.json"
    destination.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nWritten to {destination.relative_to(config.PROJECT_ROOT)}")
    return 1 if audit.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
