"""The serving path: load persisted artifacts and produce explained recommendations.

This is the module the application and the command line both use. It never fits
the segmentation — the scaler and the K-Means model are loaded from disk — and it
never reads the raw workbook.

What is loaded versus what is recomputed
    The *learned* objects are loaded: the fitted scaler and the fitted clusterer,
    which are the only components whose fitting is expensive or stochastic. The
    *counting* structures — per-segment enrollment counts, content profiles, the
    category round-robin order — are rebuilt at load time from the persisted
    tables, in well under a second, **by calling the same recommender classes the
    experiments used**.

    That is a deliberate choice. The alternative, a second implementation that
    reads precomputed arrays, would be a serving path whose scoring logic could
    drift from the evaluated one — and an explanation generated from a drifted
    scorer would be exactly the failure CLAUDE.md §16 prohibits. Here, the code
    that produced the reported metrics is the code that serves. The persisted
    ``popularity.parquet`` is compared against the recomputed counts by test, so
    a drift would fail loudly rather than silently.

Loading is not free, but it happens once per process: the application wraps
:meth:`RecommendationService.load` in ``st.cache_resource`` (CLAUDE.md §21).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import joblib
import numpy as np
import pandas as pd

from edupro import config
from edupro.explainability.explanations import QUALITY_CAVEAT, Explanation, build_explanation
from edupro.persistence import Manifest, verify_artifacts
from edupro.pipeline import PRODUCTION, artifact_files
from edupro.recommendation.base import FitContext, build_fit_context
from edupro.recommendation.baselines import ClusterPopularity, ContentBased, DiversifiedFallback
from edupro.recommendation.hybrid import TieredRecommender, tier_of
from edupro.segmentation.representations import REPRESENTATION_GRID, build_representation

logger = logging.getLogger(__name__)


class InferenceError(RuntimeError):
    """Raised when a recommendation cannot be produced."""


@dataclass(frozen=True)
class Recommendation:
    """One recommended course, with the reason it appears."""

    rank: int
    course_id: str
    course_name: str
    category: str
    level: str
    rating: float
    price: float
    is_free: bool
    score: float
    explanation: Explanation

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "course_id": self.course_id,
            "course_name": self.course_name,
            "category": self.category,
            "level": self.level,
            "rating": self.rating,
            "price": self.price,
            "is_free": self.is_free,
            "score": round(self.score, 6),
            "explanation": self.explanation.to_dict(),
        }


@dataclass(frozen=True)
class RecommendationResult:
    """A complete, self-describing answer to one recommendation request."""

    user_id: str
    #: False when the learner is not in the persisted set — they are served the
    #: cold-start route, and saying so is part of being honest about the basis.
    is_known_learner: bool
    tier: str
    segment: int | None
    segment_name: str | None
    history_size: int
    n_candidates: int
    recommendations: list[Recommendation] = field(default_factory=list)
    filters: dict[str, str | None] = field(default_factory=dict)
    #: What Phase 3B measured about ranking quality. Shown once beside the list.
    caveat: str = QUALITY_CAVEAT

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "is_known_learner": self.is_known_learner,
            "tier": self.tier,
            "segment": self.segment,
            "segment_name": self.segment_name,
            "history_size": self.history_size,
            "n_candidates": self.n_candidates,
            "filters": self.filters,
            "caveat": self.caveat,
            "recommendations": [r.to_dict() for r in self.recommendations],
        }

    def to_frame(self) -> pd.DataFrame:
        """Tabular view for the dashboard and the command line."""
        return pd.DataFrame(
            [
                {
                    "rank": r.rank,
                    "course_id": r.course_id,
                    "course": r.course_name,
                    "category": r.category,
                    "level": r.level,
                    "rating": r.rating,
                    "why": r.explanation.sentence,
                }
                for r in self.recommendations
            ]
        )


class RecommendationService:
    """Loads one artifact set and answers recommendation and profile queries.

    Construct with :meth:`load`; the constructor is for tests that already hold
    the pieces.
    """

    def __init__(
        self,
        manifest: Manifest,
        scaler: Any,
        clusterer: Any,
        features: pd.DataFrame,
        catalogue: pd.DataFrame,
        interactions: pd.DataFrame,
        segments: dict[str, Any],
        profiles: pd.DataFrame,
        problems: list[str] | None = None,
    ) -> None:
        self.manifest = manifest
        self.scaler = scaler
        self.clusterer = clusterer
        self.features = features
        self.catalogue = catalogue
        self.interactions = interactions
        self.segments = segments
        self.profiles = profiles
        self.problems = problems or []

        self.spec = next(
            (s for s in REPRESENTATION_GRID if s.name == PRODUCTION.representation), None
        )
        if self.spec is None:  # pragma: no cover - guarded by the pipeline too
            raise InferenceError(
                f"Frozen representation {PRODUCTION.representation!r} is not in the grid."
            )

        self.clusters = features["cluster"]
        self.segment_names = {
            int(cluster): str(info["label"]) for cluster, info in segments["segments"].items()
        }

        self.context: FitContext = build_fit_context(
            interactions, catalogue, features, self.clusters
        )
        self._cluster_popularity = ClusterPopularity().fit(self.context)
        self._content = ContentBased().fit(self.context)
        self._fallback = DiversifiedFallback().fit(self.context)
        self.router = TieredRecommender(
            routes={
                "insufficient": self._fallback,
                "minimal": self._content,
                "moderate": self._cluster_popularity,
                "rich": self._cluster_popularity,
            }
        ).fit(self.context)

        self._course_row = catalogue.set_index(config.KEY_COURSE)
        self._category_of = self._course_row["CourseCategory"].to_dict()
        self._history: dict[str, list[str]] = {
            user: list(group)
            for user, group in interactions.groupby(config.KEY_USER)[config.KEY_COURSE]
        }

    # ------------------------------------------------------------------ load

    @classmethod
    def load(
        cls,
        models_dir: Path | None = None,
        artifacts_dir: Path | None = None,
        strict: bool = True,
    ) -> "RecommendationService":
        """Verify and load an artifact set.

        Args:
            models_dir: directory holding the manifest and fitted estimators.
            artifacts_dir: directory holding the persisted tables.
            strict: fail on a version or integrity problem. ``False`` loads anyway
                and records the problems on ``self.problems`` — for diagnosing a
                mismatched environment, not for serving from one.

        Raises:
            ArtifactIntegrityError: a file is missing or has changed since it was
                written.
            ArtifactVersionError: the artifacts were written by incompatible code
                or library versions.
        """
        models_dir = models_dir or config.MODELS_DIR
        manifest, problems = verify_artifacts(models_dir, strict=strict)
        paths = artifact_files(models_dir, artifacts_dir)

        features = pd.read_parquet(paths["learner_features"])
        catalogue = pd.read_parquet(paths["course_catalogue"])
        interactions = pd.read_parquet(paths["interactions"])
        profiles = pd.read_parquet(paths["cluster_profiles"])
        segments = json.loads(paths["segments"].read_text(encoding="utf-8"))

        service = cls(
            manifest=manifest,
            scaler=joblib.load(paths["scaler"]),
            clusterer=joblib.load(paths["clusterer"]),
            features=features,
            catalogue=catalogue,
            interactions=interactions,
            segments=segments,
            profiles=profiles,
            problems=problems,
        )
        logger.info(
            "Loaded artifact set %s (%s): %d learners, %d courses, %d interactions",
            manifest.artifact_set_version,
            manifest.model_version,
            len(features),
            len(catalogue),
            len(interactions),
        )
        return service

    # -------------------------------------------------------- segmentation

    def segment_of(self, user_id: str) -> int | None:
        """The persisted segment for a known learner, or ``None``."""
        if user_id not in self.clusters.index:
            return None
        return int(self.clusters.loc[user_id])

    def assign_segment(self, features: pd.DataFrame) -> pd.Series:
        """Clustering inference for learners not in the persisted set.

        Scales with the **persisted** scaler — a learner arriving alone must be
        standardised by the training population's statistics, not by their own —
        and predicts with the persisted K-Means model. Nothing is refitted.

        Args:
            features: learner feature rows in the same schema the pipeline built.

        Returns:
            Cluster label per learner, indexed as ``features``.
        """
        representation = build_representation(features, self.spec, scaler=self.scaler)
        labels = self.clusterer.predict(representation.matrix)
        return pd.Series(labels.astype(int), index=features.index, name="cluster")

    def segment_summary(self) -> pd.DataFrame:
        """One row per segment: size, share, label and headline behaviour."""
        rows = []
        for cluster, info in sorted(
            self.segments["segments"].items(), key=lambda kv: int(kv[0])
        ):
            cluster = int(cluster)
            row: dict[str, Any] = {
                "cluster": cluster,
                "segment_name": info["label"],
                "n_learners": info["n_learners"],
                "share": info["share"],
            }
            if cluster in self.profiles.index:
                profile = self.profiles.loc[cluster]
                for column in ("total_courses_mean", "diversity_score_mean",
                               "avg_course_rating_mean", "level_mix"):
                    if column in profile.index:
                        row[column] = profile[column]
            rows.append(row)
        return pd.DataFrame(rows).set_index("cluster")

    # ------------------------------------------------------------- learners

    def history(self, user_id: str) -> pd.DataFrame:
        """The learner's enrollments, most recent first, joined to the catalogue."""
        rows = self.interactions[self.interactions[config.KEY_USER] == user_id]
        if rows.empty:
            return rows.assign(**{c: [] for c in ("CourseName", "CourseCategory", "CourseLevel")})
        return (
            rows.merge(self.catalogue, on=config.KEY_COURSE, how="left")
            .sort_values(config.COL_TRANSACTION_DATE, ascending=False)
            .reset_index(drop=True)
        )

    def learner_profile(self, user_id: str) -> dict[str, Any]:
        """Profile for the dashboard: identifiers are pseudonymous by construction.

        No name or email can appear here because the loader dropped those columns
        at ingestion; there is nothing downstream to filter (ADR-0006).
        """
        if user_id not in self.features.index:
            raise InferenceError(f"Unknown learner {user_id!r}.")
        row = self.features.loc[user_id]
        cluster = int(row["cluster"])
        return {
            "user_id": user_id,
            "segment": cluster,
            "segment_name": self.segment_names.get(cluster),
            "tier": str(row["tier"]),
            "total_courses": int(row["total_courses"]),
            "diversity_score": int(row["diversity_score"]),
            "preferred_category": str(row["preferred_category"]),
            "preferred_level": str(row["preferred_level"]),
            "avg_course_rating": round(float(row["avg_course_rating"]), 3),
            "avg_spend": round(float(row["avg_spend"]), 2),
            "learning_depth_index": round(float(row["learning_depth_index"]), 3),
            "age": int(row["age"]) if "age" in row and pd.notna(row["age"]) else None,
            "gender": str(row["gender"]) if "gender" in row else None,
        }

    # ------------------------------------------------------ recommendation

    def _filtered_candidates(
        self, user_id: str, category: str | None, level: str | None
    ) -> np.ndarray:
        """Unseen courses, narrowed by the requested filters.

        Filters are applied to the **candidate set**, before scoring, rather than
        to the ranked list afterwards: a filter is a hard constraint, and filtering
        a top-10 would return fewer than ten results whenever the constraint bites.
        """
        candidates = self.context.candidates_for(user_id)
        if category is None and level is None:
            return candidates
        keep = []
        for position in candidates:
            row = self.catalogue.iloc[int(position)]
            if category is not None and row["CourseCategory"] != category:
                continue
            if level is not None and row["CourseLevel"] != level:
                continue
            keep.append(int(position))
        return np.array(keep, dtype=int)

    def _facts_for(
        self, user_id: str, position: int, cluster: int | None, history: Sequence[str]
    ) -> dict[str, Any]:
        """Quantities the explanation may cite, each read from persisted data.

        Every value here is checked rather than assumed: the category-overlap count
        is computed from the learner's actual history, and the segment enrollment
        count is read from the same array the scorer ranked by.
        """
        row = self.catalogue.iloc[int(position)]
        category = str(row["CourseCategory"])
        facts: dict[str, Any] = {
            "course_category": category,
            "course_level": str(row["CourseLevel"]),
            "course_rating": float(row["CourseRating"]),
            "history_size": len(history),
            "global_enrollments": int(self._cluster_popularity.global_popularity[position]),
        }
        if cluster is not None and cluster in self._cluster_popularity.by_cluster:
            facts["segment_enrollments"] = int(
                self._cluster_popularity.by_cluster[cluster][position]
            )
            facts["segment_name"] = self.segment_names.get(cluster)
        if history:
            facts["shared_category_count"] = sum(
                1 for course in history if self._category_of.get(course) == category
            )
            levels = [
                self._course_row.loc[course, "CourseLevel"]
                for course in history
                if course in self._course_row.index
            ]
            if levels:
                modal = pd.Series(levels).mode().iloc[0]
                facts["level_match"] = bool(modal == row["CourseLevel"])
        facts["category_rank"] = int(self._fallback.within_category_rank[position])
        share_column = f"cat_share_{category.lower().replace(' ', '_')}"
        if user_id in self.features.index and share_column in self.features.columns:
            facts["category_share"] = float(self.features.loc[user_id, share_column])
        return facts

    def recommend(
        self,
        user_id: str,
        k: int = PRODUCTION.top_k,
        category: str | None = None,
        level: str | None = None,
    ) -> RecommendationResult:
        """Produce an explained top-K for one learner.

        Args:
            user_id: learner identifier. An identifier absent from the artifact set
                is served the cold-start route and flagged as unknown rather than
                rejected — that is what a genuinely new learner is.
            k: list length.
            category: restrict to one course category.
            level: restrict to one course level.

        Returns:
            A :class:`RecommendationResult` carrying the list, the routing tier,
            the segment and the quality caveat.

        Raises:
            InferenceError: if ``k`` is not positive, or the filters leave no
                candidate courses.
        """
        if k <= 0:
            raise InferenceError(f"k must be positive, got {k}.")

        known = user_id in self.features.index
        history = self._history.get(user_id, [])
        tier = tier_of(len(self.context.seen.get(user_id, set())))
        cluster = self.segment_of(user_id)
        if not known:
            logger.info("Learner %s is not in the artifact set; serving the cold-start route.",
                        user_id)

        candidates = self._filtered_candidates(user_id, category, level)
        if len(candidates) == 0:
            raise InferenceError(
                "No candidate courses remain after filtering "
                f"(category={category!r}, level={level!r}) and excluding "
                f"{len(history)} already-enrolled courses."
            )

        _, recommender = self.router.route_for(user_id)
        scores = recommender.score(user_id, candidates)
        ranked = scores.ranked(k)

        recommendations: list[Recommendation] = []
        for rank, position in enumerate(ranked, start=1):
            position = int(position)
            row = self.catalogue.iloc[position]
            course_id = str(row[config.KEY_COURSE])
            explanation = build_explanation(
                course_id=course_id,
                tier=tier,
                contributions=scores.contribution_at(position),
                facts=self._facts_for(user_id, position, cluster, history),
            )
            index = int(np.flatnonzero(scores.candidates == position)[0])
            recommendations.append(
                Recommendation(
                    rank=rank,
                    course_id=course_id,
                    course_name=str(row["CourseName"]),
                    category=str(row["CourseCategory"]),
                    level=str(row["CourseLevel"]),
                    rating=float(row["CourseRating"]),
                    price=float(row["CoursePrice"]),
                    is_free=str(row["CourseType"]) == "Free",
                    score=float(scores.total[index]),
                    explanation=explanation,
                )
            )

        return RecommendationResult(
            user_id=user_id,
            is_known_learner=known,
            tier=tier,
            segment=cluster,
            segment_name=self.segment_names.get(cluster) if cluster is not None else None,
            history_size=len(history),
            n_candidates=len(candidates),
            recommendations=recommendations,
            filters={"category": category, "level": level},
        )

    # ------------------------------------------------------------ reporting

    def describe(self) -> dict[str, Any]:
        """Summary of the loaded artifact set, for a health check or an about page."""
        return {
            "model_version": self.manifest.model_version,
            "artifact_set_version": self.manifest.artifact_set_version,
            "created_at": self.manifest.created_at,
            "workbook_sha256": self.manifest.workbook_sha256[:12] + "...",
            "n_learners": int(len(self.features)),
            "n_courses": int(len(self.catalogue)),
            "n_interactions": int(len(self.interactions)),
            "segments": self.segment_names,
            "tiers": self.features["tier"].value_counts().to_dict(),
            "problems": self.problems,
        }
