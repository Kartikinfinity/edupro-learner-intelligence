"""The production training pipeline: raw workbook in, persisted artifacts out.

This is the only place the frozen configuration is *fitted*. It runs offline,
writes a versioned artifact set, and is never invoked by the application — the
serving path in :mod:`edupro.inference` loads what this produced (CLAUDE.md §21).

What it fits, and on what
    Model *selection* used a temporal split so that every reported metric is
    out-of-sample. The *deployed* model is then fitted on the full interaction
    history, which is standard practice after selection and is what a platform
    serving live learners would do: there is nothing to hold out at serving time,
    and withholding the most recent two months of behaviour would make the
    recommendations worse for no benefit.

    The distinction matters enough to be explicit: **the metrics in
    `research/` describe the temporal-split fit; the artifacts here describe the
    full-history fit.** The manifest records which window it used so the two can
    never be confused.

Configuration is frozen
    :data:`PRODUCTION` mirrors `research/ARCHITECTURE_FREEZE.md` exactly. Changing
    a value here is a change to the frozen ML design and requires the four
    conditions in decision log D-044.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from edupro import config
from edupro.data.joins import build_interactions
from edupro.data.loader import EduProData, load_all, sha256, verify_raw_workbook
from edupro.data.validation import validate
from edupro.features.course import build_course_catalogue, build_course_vectors, course_vector_columns
from edupro.features.learner import build_learner_features
from edupro.persistence import (
    MODEL_VERSION,
    Manifest,
    library_versions,
    new_artifact_set_version,
    save_manifest,
    utc_timestamp,
)
from edupro.recommendation.base import build_fit_context
from edupro.recommendation.baselines import ClusterPopularity, ContentBased, DiversifiedFallback
from edupro.recommendation.hybrid import TIER_BOUNDARIES, TieredRecommender, tier_of
from edupro.segmentation.clustering import fit_kmeans
from edupro.segmentation.profiling import (
    compose_segment_names,
    label_clusters,
    profile_clusters,
)
from edupro.segmentation.representations import REPRESENTATION_GRID, build_representation
from edupro.segmentation.stability import assess_stability

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProductionConfig:
    """The frozen configuration. Mirrors `research/ARCHITECTURE_FREEZE.md`."""

    #: Segmentation representation: Variant B, 12-dim category share vector.
    representation: str = "B_proportion"
    #: Cluster count, selected by the pre-registered size + stability rule.
    n_clusters: int = 4
    #: Single seed for every stochastic operation.
    seed: int = config.RANDOM_SEED
    #: Default recommendation list length.
    top_k: int = 10
    #: Teacher signals are excluded: rejected in three separate experiments.
    include_teacher: bool = False
    #: Tier -> recommender class name, for the manifest and for verification.
    routes: dict[str, str] = field(
        default_factory=lambda: {
            "insufficient": "DiversifiedFallback",
            "minimal": "ContentBased",
            "moderate": "ClusterPopularity",
            "rich": "ClusterPopularity",
        }
    )


PRODUCTION = ProductionConfig()

#: Directory holding the persisted data tables, relative to the project root.
PRODUCTION_ARTIFACTS: Path = config.ARTIFACTS_DIR / "production"

#: Filenames of the artifact set, split by which directory they live in.
MODEL_FILES: tuple[tuple[str, str], ...] = (
    ("scaler", "scaler.joblib"),
    ("clusterer", "clusterer.joblib"),
    ("feature_schema", "feature_schema.json"),
    ("model_config", "model_config.json"),
)
TABLE_FILES: tuple[tuple[str, str], ...] = (
    ("learner_features", "learner_features.parquet"),
    ("cluster_profiles", "cluster_profiles.parquet"),
    ("segments", "segments.json"),
    ("course_catalogue", "course_catalogue.parquet"),
    ("course_vectors", "course_vectors.npy"),
    ("interactions", "interactions.parquet"),
    ("popularity", "popularity.parquet"),
)


def artifact_files(
    models_dir: Path | None = None, artifacts_dir: Path | None = None
) -> dict[str, Path]:
    """Resolve every artifact path. Taking the directories as arguments is what
    lets a test write a complete set somewhere disposable without touching the
    repository's own artifacts."""
    models_dir = models_dir or config.MODELS_DIR
    artifacts_dir = artifacts_dir or PRODUCTION_ARTIFACTS
    return {
        **{name: models_dir / filename for name, filename in MODEL_FILES},
        **{name: artifacts_dir / filename for name, filename in TABLE_FILES},
    }


def _manifest_key(path: Path) -> str:
    """Project-relative path where possible, absolute otherwise (temp dirs)."""
    try:
        return str(path.relative_to(config.PROJECT_ROOT))
    except ValueError:
        return str(path)

#: Interaction columns persisted for serving. Deliberately minimal: the scorers
#: need the pair, the dashboard needs the date to show a history in order, and
#: everything else is recoverable by joining the catalogue.
SERVING_INTERACTION_COLUMNS: tuple[str, ...] = (
    config.KEY_USER,
    config.KEY_COURSE,
    config.COL_TRANSACTION_DATE,
)


class PipelineError(RuntimeError):
    """Raised when the training pipeline cannot produce a trustworthy artifact set."""


def _level_composition(features: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    """Share of each course level within each cluster — input to segment naming."""
    frame = pd.DataFrame(
        {"cluster": labels, "preferred_level": features["preferred_level"].to_numpy()}
    )
    return (
        pd.crosstab(frame["cluster"], frame["preferred_level"], normalize="index")
        .rename_axis(index="cluster", columns=None)
    )


def _popularity_table(
    scorer: ClusterPopularity, catalogue: pd.DataFrame
) -> pd.DataFrame:
    """Global and per-segment enrollment counts, aligned to catalogue position.

    Persisted for two reasons: the dashboard reads it directly, and the test suite
    compares it against the counts the serving path recomputes. A divergence would
    mean the artifact and the live scorer disagree, which is exactly the failure a
    manifest alone cannot catch.
    """
    table = catalogue[[config.KEY_COURSE, "position"]].copy()
    table["global_enrollments"] = scorer.global_popularity.astype(int)
    for cluster in sorted(scorer.by_cluster):
        table[f"cluster_{cluster}_enrollments"] = scorer.by_cluster[cluster].astype(int)
    return table


def _feature_schema(features: pd.DataFrame, representation_columns: list[str]) -> dict[str, Any]:
    """Column names, dtypes and the model/display split, for load-time validation."""
    return {
        "model_version": MODEL_VERSION,
        "n_features_persisted": int(features.shape[1]),
        "n_features_in_model": len(representation_columns),
        "representation_columns": representation_columns,
        "persisted_columns": {
            column: str(dtype) for column, dtype in features.dtypes.items()
        },
        "note": (
            "Persisted columns include age and gender for display and evaluation "
            "strata. They are absent from representation_columns: the segmentation "
            "is Variant B, behaviour only (ARCHITECTURE_FREEZE.md, decision 4)."
        ),
    }


def _model_config() -> dict[str, Any]:
    """The frozen configuration, written in human-readable form."""
    return {
        "model_version": MODEL_VERSION,
        "seed": PRODUCTION.seed,
        "segmentation": {
            "representation": PRODUCTION.representation,
            "n_clusters": PRODUCTION.n_clusters,
            "scaler": "standard",
            "algorithm": "KMeans(init=k-means++, n_init=10)",
        },
        "recommendation": {
            "architecture": "tiered switching recommender",
            "routes": PRODUCTION.routes,
            "tier_boundaries": [
                {"tier": name, "min_history": low, "max_history": None if high > 10**6 else high}
                for name, low, high in TIER_BOUNDARIES
            ],
            "default_k": PRODUCTION.top_k,
            "teacher_signals": "excluded (ARCHITECTURE_FREEZE.md, decision 10)",
        },
        "evaluation_reference": {
            "protocol": "A - global temporal split",
            "note": (
                "Metrics in research/ come from the temporal-split fit. These "
                "artifacts are fitted on the full history, as recorded in the "
                "manifest's training block."
            ),
        },
    }


def train(
    *,
    models_dir: Path | None = None,
    artifacts_dir: Path | None = None,
    data: EduProData | None = None,
    with_stability: bool = True,
    verify_source: bool = True,
) -> Manifest:
    """Fit the frozen architecture on the full history and persist the artifact set.

    Args:
        models_dir: destination for fitted estimators and configuration.
        artifacts_dir: destination for the persisted data tables.
        data: pre-loaded workbook, for tests. Loaded from disk when omitted.
        with_stability: run the bootstrap stability assessment and persist it.
            Costs roughly a minute; skipped in fast test runs.
        verify_source: check the workbook checksum before training.

    Returns:
        The manifest describing the artifact set that was written.

    Raises:
        PipelineError: if the source data fails validation, or if the fitted
            segmentation does not match the frozen configuration.
    """
    models_dir = models_dir or config.MODELS_DIR
    artifacts_dir = artifacts_dir or PRODUCTION_ARTIFACTS
    models_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    paths = artifact_files(models_dir, artifacts_dir)

    created_at = utc_timestamp()

    # --- 1. deterministic loading -------------------------------------------
    checksum = verify_raw_workbook() if verify_source else config.RAW_WORKBOOK_SHA256
    if data is None:
        data = load_all()
    logger.info("Loaded workbook (sha256 %s...)", checksum[:12])

    # --- 2. schema validation ------------------------------------------------
    report = validate(data)
    if not report.ok:
        raise PipelineError(
            "Source data failed validation; refusing to train.\n" + report.summary()
        )
    logger.info(
        "Validation passed: 0 errors, %d warnings, %d informational findings",
        len(report.warnings),
        len(report.infos),
    )

    # --- 3. preprocessing / joining -----------------------------------------
    interactions = build_interactions(
        data, with_user_demographics=True, with_teacher=PRODUCTION.include_teacher
    )
    logger.info("Built %d interactions", len(interactions))

    # --- 4. learner features -------------------------------------------------
    # Demographics are attached for display and evaluation strata. They are
    # excluded from the model matrix by the representation, not by omission here.
    features = build_learner_features(interactions, users=data.users)
    logger.info("Built features for %d learners", len(features))

    # --- 5. course representation -------------------------------------------
    catalogue = build_course_catalogue(data.courses)
    course_ids = catalogue[config.KEY_COURSE].tolist()
    vectors = build_course_vectors(data.courses, course_ids)
    logger.info("Built %d course vectors of width %d", *vectors.shape)

    # --- 6. segmentation -----------------------------------------------------
    spec = next((s for s in REPRESENTATION_GRID if s.name == PRODUCTION.representation), None)
    if spec is None:
        raise PipelineError(
            f"Frozen representation {PRODUCTION.representation!r} is not in the grid."
        )
    representation = build_representation(features, spec)
    clusterer = fit_kmeans(representation.matrix, PRODUCTION.n_clusters, seed=PRODUCTION.seed)
    labels = clusterer.labels_
    if len(set(labels)) != PRODUCTION.n_clusters:
        raise PipelineError(
            f"K-Means produced {len(set(labels))} non-empty clusters, "
            f"expected {PRODUCTION.n_clusters}."
        )
    clusters = pd.Series(labels, index=features.index, name="cluster")
    logger.info("Fitted %d segments", PRODUCTION.n_clusters)

    # --- 7. segment profiling and naming ------------------------------------
    profiles = profile_clusters(features, labels, interactions)
    named = compose_segment_names(
        # Naming is restricted to the columns the clustering actually used, so a
        # segment can never be named for a dimension the model did not see.
        label_clusters(features, labels, allowed_features=set(representation.columns)),
        _level_composition(features, labels),
    )
    stability: dict[str, Any] = {"assessed": False}
    if with_stability:
        result = assess_stability(representation.matrix, PRODUCTION.n_clusters)
        stability = {"assessed": True, **result.to_dict()}
        logger.info("Stability: mean Jaccard %.3f", result.mean_jaccard)

    # --- 8. recommendation ---------------------------------------------------
    context = build_fit_context(interactions, catalogue, features, clusters)
    cluster_popularity = ClusterPopularity().fit(context)
    router = TieredRecommender(
        routes={
            "insufficient": DiversifiedFallback(),
            "minimal": ContentBased(),
            "moderate": cluster_popularity,
            "rich": cluster_popularity,
        }
    ).fit(context)
    tiers = pd.Series(
        {user: tier_of(len(context.seen.get(user, set()))) for user in features.index},
        name="tier",
    )
    logger.info("Tier distribution: %s", tiers.value_counts().to_dict())

    # --- 9. persist ----------------------------------------------------------
    persisted = features.copy()
    persisted["cluster"] = clusters
    persisted["tier"] = tiers
    persisted["segment_name"] = persisted["cluster"].map(
        {int(c): str(info["label"]) for c, info in named.items()}
    )

    joblib.dump(representation.scaler, paths["scaler"])
    joblib.dump(clusterer, paths["clusterer"])
    paths["feature_schema"].write_text(
        json.dumps(_feature_schema(persisted, representation.columns), indent=2),
        encoding="utf-8",
    )
    paths["model_config"].write_text(
        json.dumps(_model_config(), indent=2), encoding="utf-8"
    )
    persisted.to_parquet(paths["learner_features"])
    profiles.to_parquet(paths["cluster_profiles"])
    paths["segments"].write_text(
        json.dumps(
            {
                "segments": {
                    str(cluster): {
                        **{k: v for k, v in info.items()},
                        "n_learners": int((clusters == cluster).sum()),
                        "share": round(float((clusters == cluster).mean()), 4),
                    }
                    for cluster, info in named.items()
                },
                "stability": stability,
                "naming_method": (
                    "Deviation-ranked over the clustering's own columns, with a "
                    "level prefix where a cluster is at least 90% pure on one level."
                ),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    catalogue.to_parquet(paths["course_catalogue"])
    np.save(paths["course_vectors"], vectors)
    interactions.loc[:, list(SERVING_INTERACTION_COLUMNS)].to_parquet(
        paths["interactions"]
    )
    _popularity_table(cluster_popularity, catalogue).to_parquet(paths["popularity"])

    # --- 10. manifest --------------------------------------------------------
    manifest = Manifest(
        model_version=MODEL_VERSION,
        artifact_set_version=new_artifact_set_version(PRODUCTION.seed, checksum, created_at),
        created_at=created_at,
        seed=PRODUCTION.seed,
        workbook_sha256=checksum,
        libraries=library_versions(),
        training={
            "window": "full history",
            "window_note": (
                "Fitted on all interactions. Reported metrics come from the "
                "temporal-split fit described in research/ARCHITECTURE_FREEZE.md."
            ),
            "n_learners": int(len(features)),
            "n_interactions": int(len(interactions)),
            "n_courses": int(len(catalogue)),
            "first_interaction": str(interactions[config.COL_TRANSACTION_DATE].min().date()),
            "last_interaction": str(interactions[config.COL_TRANSACTION_DATE].max().date()),
        },
        segmentation={
            "representation": PRODUCTION.representation,
            "n_clusters": PRODUCTION.n_clusters,
            "n_model_features": len(representation.columns),
            "columns": representation.columns,
            "sizes": {str(c): int((clusters == c).sum()) for c in sorted(set(labels))},
        },
        recommendation={
            "architecture": "tiered",
            "routes": PRODUCTION.routes,
            "tiers": tiers.value_counts().to_dict(),
            "default_k": PRODUCTION.top_k,
        },
        files={_manifest_key(path): sha256(path) for path in paths.values()},
    )
    save_manifest(manifest, models_dir)
    logger.info(
        "Artifact set %s written (%d files)", manifest.artifact_set_version, len(manifest.files)
    )
    return manifest
