"""The non-hybrid recommenders: the baselines the final method must beat.

CLAUDE.md §13 requires at least five baselines and that the final method be chosen
from experimental evidence. [R26] is direct published evidence that under-tuned
baselines are how recommender research goes wrong, so each of these gets the same
treatment as the hybrid rather than being a strawman.

Included beyond the brief's five, with justification:

**Random** — the reference floor. On a 60-course catalogue a random ranker has
Hit Rate@10 of roughly 0.175 (``scripts/analytical_baselines.py``), so reporting
accuracy without it would be misleading. Published work rarely needs this because
a 10,000-item catalogue makes random ~0.001.

**Item-based collaborative filtering** [R15][R16] — each course has ~167
interactions while each learner has ~3.3, so item-item co-occurrence is estimated
from roughly 50× more evidence per entity than user-user similarity.

**Teacher affinity** — Phase 2 found instructor reuse to be the only genuine
behavioural signal in the dataset (0.688 distinct teachers per interaction against
a 0.944 null). It was rejected for *segmentation* (D-030); predicting the next
course is a different question, so it is tested here on its own merits.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from edupro import config
from edupro.data.schema import COURSE_CATEGORIES, COURSE_LEVELS, LEVEL_ORDER
from edupro.features.learner import CATEGORY_SHARE_COLUMNS
from edupro.recommendation.base import BaseRecommender, FitContext, minmax


class RandomRecommender(BaseRecommender):
    """Uniformly random ranking — the reference floor, seeded for reproducibility."""

    name = "random"
    component = "random"

    def __init__(self, seed: int = config.RANDOM_SEED) -> None:
        super().__init__()
        self.seed = seed

    def _fit(self, context: FitContext) -> None:
        self._rng = np.random.default_rng(self.seed)

    def _raw_scores(self, user: str, candidates: np.ndarray) -> np.ndarray:
        return self._rng.random(len(candidates))


class GlobalPopularity(BaseRecommender):
    """Rank by training-window enrollment count.

    Popularity counts come from the training frame only (leakage control L5).
    """

    name = "global_popularity"
    component = "popularity"

    def _fit(self, context: FitContext) -> None:
        counts = np.zeros(context.n_items, dtype=float)
        for course, n in context.interactions[config.KEY_COURSE].value_counts().items():
            if course in context.course_index:
                counts[context.course_index[course]] = n
        self.popularity = counts

    def _raw_scores(self, user: str, candidates: np.ndarray) -> np.ndarray:
        return self.popularity[candidates]


class RatingRecommender(BaseRecommender):
    """Rank by course rating alone — the rating signal in isolation.

    Isolating it answers a question the brief's "rating-weighted relevance" leaves
    open: does rating carry ranking information on its own, or only as a tie-break
    on top of another signal?
    """

    name = "rating"
    component = "rating"

    def _fit(self, context: FitContext) -> None:
        ratings = context.courses.set_index(config.KEY_COURSE)["CourseRating"]
        self.ratings = np.array(
            [float(ratings.get(course, 0.0)) for course in context.course_ids]
        )

    def _raw_scores(self, user: str, candidates: np.ndarray) -> np.ndarray:
        return self.ratings[candidates]


def build_course_vectors(courses: pd.DataFrame, course_ids: list[str]) -> np.ndarray:
    """Content feature matrix: category one-hot, level ordinal, type, rating, duration.

    ``CourseName`` is deliberately absent: 58 distinct names across 60 courses with
    no descriptive text, so TF-IDF over titles would be near-degenerate (Phase 1,
    `literature_review.md` §2.2). Numeric attributes are min-max scaled so no single
    one dominates cosine similarity through its raw range.
    """
    indexed = courses.set_index(config.KEY_COURSE).reindex(course_ids)
    category = pd.get_dummies(
        indexed["CourseCategory"].astype("string"), dtype=float
    ).reindex(columns=list(COURSE_CATEGORIES), fill_value=0.0)
    level = pd.get_dummies(
        indexed["CourseLevel"].astype("string"), dtype=float
    ).reindex(columns=list(COURSE_LEVELS), fill_value=0.0)
    numeric = pd.DataFrame(
        {
            "is_free": (indexed["CourseType"] == "Free").astype(float),
            "rating": minmax(indexed["CourseRating"].to_numpy(dtype=float)),
            "duration": minmax(indexed["CourseDuration"].to_numpy(dtype=float)),
        },
        index=indexed.index,
    )
    return pd.concat([category, level, numeric], axis=1).to_numpy(dtype=float)


class ContentBased(BaseRecommender):
    """Similarity between a learner's content profile and each unseen course.

    The learner profile is the mean of the content vectors of the courses they
    enrolled in during the training window — so it works from a single interaction,
    which matters when 54% of learners have exactly one.
    """

    name = "content_based"
    component = "content"

    def _fit(self, context: FitContext) -> None:
        self.vectors = build_course_vectors(context.courses, context.course_ids)
        self.profiles: dict[str, np.ndarray] = {}
        for user, positions in context.seen.items():
            if positions:
                self.profiles[user] = self.vectors[sorted(positions)].mean(axis=0)
        self.fallback = self.vectors.mean(axis=0)

    def _raw_scores(self, user: str, candidates: np.ndarray) -> np.ndarray:
        profile = self.profiles.get(user, self.fallback).reshape(1, -1)
        return cosine_similarity(profile, self.vectors[candidates]).ravel()


class ItemItemCF(BaseRecommender):
    """Item-based collaborative filtering [R15][R16].

    Scores a candidate by its cosine co-occurrence similarity with the courses the
    learner already took. The 60×60 similarity matrix is computed from the training
    interactions only and is small enough to hold entirely in memory.
    """

    name = "item_item_cf"
    component = "item_similarity"

    def _fit(self, context: FitContext) -> None:
        matrix = _user_item_matrix(context)
        self.similarity = cosine_similarity(matrix.T)
        np.fill_diagonal(self.similarity, 0.0)

    def _raw_scores(self, user: str, candidates: np.ndarray) -> np.ndarray:
        assert self.context is not None
        seen = sorted(self.context.seen.get(user, set()))
        if not seen:
            return np.zeros(len(candidates))
        return self.similarity[np.ix_(candidates, seen)].sum(axis=1)


class UserUserHistory(BaseRecommender):
    """Similar-learner recommendation over the raw interaction history.

    The brief's "similar learner profiles" read literally. Phase 1 predicted this
    would be weak: with ~3.3 interactions per learner the similarity is estimated
    from almost nothing.
    """

    name = "user_user_history"
    component = "learner_similarity"

    def __init__(self, n_neighbours: int = 50) -> None:
        super().__init__()
        self.n_neighbours = n_neighbours

    def _fit(self, context: FitContext) -> None:
        self.matrix = _user_item_matrix(context)
        self.users = list(context.seen.keys())
        self.user_index = {user: i for i, user in enumerate(self.users)}
        self.similarity = cosine_similarity(self.matrix)
        np.fill_diagonal(self.similarity, 0.0)

    def _raw_scores(self, user: str, candidates: np.ndarray) -> np.ndarray:
        if user not in self.user_index:
            return np.zeros(len(candidates))
        row = self.similarity[self.user_index[user]]
        neighbours = np.argpartition(-row, min(self.n_neighbours, len(row) - 1))[
            : self.n_neighbours
        ]
        weights = row[neighbours]
        if weights.sum() <= 0:
            return np.zeros(len(candidates))
        return (weights @ self.matrix[neighbours])[candidates]


class UserUserProfile(UserUserHistory):
    """Similar-learner recommendation over the engineered profile features.

    Same intent as :class:`UserUserHistory`, but similarity is computed on the
    learner feature vector rather than the sparse history vector. The aggregation
    is what makes a 3-interaction history usable, so this is expected to be
    better-conditioned — an empirical question the experiment settles.
    """

    name = "user_user_profile"

    def _fit(self, context: FitContext) -> None:
        self.matrix = _user_item_matrix(context)
        self.users = list(context.seen.keys())
        self.user_index = {user: i for i, user in enumerate(self.users)}
        profile = context.features.reindex(self.users)
        numeric = profile.select_dtypes(include=[np.number]).fillna(0.0)
        standardised = (numeric - numeric.mean()) / numeric.std().replace(0, 1.0)
        self.similarity = cosine_similarity(standardised.fillna(0.0).to_numpy())
        np.fill_diagonal(self.similarity, 0.0)


class ClusterPopularity(BaseRecommender):
    """Popularity within the learner's assigned segment.

    The brief's cluster-aware recommendation, and the experiment that answers
    whether the Phase 3A segmentation has any practical value (open question Q-10).
    ADR-0005 kept the cluster signal ablatable precisely so this can be measured.
    """

    name = "cluster_popularity"
    component = "cluster_popularity"

    def _fit(self, context: FitContext) -> None:
        frame = context.interactions[[config.KEY_USER, config.KEY_COURSE]].copy()
        frame["cluster"] = frame[config.KEY_USER].map(context.clusters)
        self.by_cluster: dict[int, np.ndarray] = {}
        for cluster, group in frame.dropna(subset=["cluster"]).groupby("cluster"):
            counts = np.zeros(context.n_items, dtype=float)
            for course, n in group[config.KEY_COURSE].value_counts().items():
                if course in context.course_index:
                    counts[context.course_index[course]] = n
            self.by_cluster[int(cluster)] = counts
        global_counts = np.zeros(context.n_items, dtype=float)
        for course, n in frame[config.KEY_COURSE].value_counts().items():
            if course in context.course_index:
                global_counts[context.course_index[course]] = n
        self.global_popularity = global_counts

    def _raw_scores(self, user: str, candidates: np.ndarray) -> np.ndarray:
        assert self.context is not None
        cluster = self.context.clusters.get(user)
        if cluster is None or int(cluster) not in self.by_cluster:
            return self.global_popularity[candidates]
        return self.by_cluster[int(cluster)][candidates]


class TeacherAffinity(BaseRecommender):
    """Score a course by how often the learner's prior instructors teach it.

    Phase 2 measured the effect this exploits: learners reuse instructors far more
    than chance (0.688 distinct teachers per interaction vs a 0.944 null), but the
    lift on next-course prediction was only 1.10× because each teacher covers ~15
    of ~55 unseen courses. Included so that expectation is tested, not assumed.
    """

    name = "teacher_affinity"
    component = "teacher_affinity"

    def _fit(self, context: FitContext) -> None:
        interactions = context.interactions
        if config.KEY_TEACHER not in interactions.columns:
            self.enabled = False
            return
        self.enabled = True
        pairs = interactions[[config.KEY_COURSE, config.KEY_TEACHER]].drop_duplicates()
        self.course_teachers: dict[int, set[str]] = {}
        for course, group in pairs.groupby(config.KEY_COURSE)[config.KEY_TEACHER]:
            if course in context.course_index:
                self.course_teachers[context.course_index[course]] = set(group)
        self.user_teachers: dict[str, dict[str, int]] = {}
        for user, group in interactions.groupby(config.KEY_USER)[config.KEY_TEACHER]:
            self.user_teachers[user] = group.value_counts().to_dict()

    def _raw_scores(self, user: str, candidates: np.ndarray) -> np.ndarray:
        if not getattr(self, "enabled", False):
            return np.zeros(len(candidates))
        history = self.user_teachers.get(user, {})
        if not history:
            return np.zeros(len(candidates))
        return np.array([
            sum(history.get(t, 0) for t in self.course_teachers.get(int(c), ()))
            for c in candidates
        ], dtype=float)


class DiversifiedFallback(BaseRecommender):
    """The cold-start fallback CLAUDE.md §15 prescribes: popularity, rating **and
    diversity**.

    A plain popularity-and-rating blend fails the diversity half. Measured on the
    validation window it reached only **17%** of the catalogue for zero-history
    learners — *worse* than global popularity alone (32%), because popularity and
    rating concentrate on the same courses and blending them compounds rather than
    offsets the concentration.

    This recommender keeps the same quality blend but re-ranks it **round-robin
    across course categories**: the best unshown course from each category, then
    the second-best from each, and so on. A top-12 therefore spans all twelve
    categories.

    That is the right behaviour for a learner the system knows nothing about.
    There is no preference to exploit, so the useful thing to offer is breadth —
    and Phase 2 showed the accuracy cost is nil, because course popularity is
    near-uniform (Gini 0.042) and nothing beats random anyway.
    """

    name = "diversified_fallback"
    component = "popularity_rating_diversity"

    def __init__(self, popularity_weight: float = 0.5) -> None:
        super().__init__()
        self.popularity_weight = popularity_weight

    def _fit(self, context: FitContext) -> None:
        self.popularity = GlobalPopularity().fit(context).popularity
        self.ratings = RatingRecommender().fit(context).ratings
        indexed = context.courses.set_index(config.KEY_COURSE).reindex(context.course_ids)
        self.categories = indexed["CourseCategory"].tolist()

        quality = (
            self.popularity_weight * minmax(self.popularity)
            + (1 - self.popularity_weight) * minmax(self.ratings)
        )
        # Rank within category: 0 for each category's best course, 1 for its
        # second-best, and so on. The round-robin ordering falls out of sorting by
        # this rank first and quality second.
        self.within_category_rank = np.zeros(context.n_items, dtype=float)
        for category in set(self.categories):
            members = [i for i, c in enumerate(self.categories) if c == category]
            for rank, position in enumerate(sorted(members, key=lambda i: -quality[i])):
                self.within_category_rank[position] = rank
        self.quality = quality

    def _raw_scores(self, user: str, candidates: np.ndarray) -> np.ndarray:
        # Higher is better: a low within-category rank dominates, and quality
        # orders the courses that share a rank.
        return -self.within_category_rank[candidates] + self.quality[candidates]


class PreferenceMatch(BaseRecommender):
    """How well a course matches the learner's category and level preferences.

    The brief's "learner preference match". Distinct from content similarity: it
    scores against the learner's *distribution* over categories and their preferred
    level, rather than against the mean content vector of their courses.
    """

    name = "preference_match"
    component = "preference_match"

    def _fit(self, context: FitContext) -> None:
        indexed = context.courses.set_index(config.KEY_COURSE).reindex(context.course_ids)
        self.course_category = indexed["CourseCategory"].tolist()
        self.course_level_ordinal = np.array(
            [LEVEL_ORDER[level] for level in indexed["CourseLevel"]], dtype=float
        )
        share_columns = [c for c in CATEGORY_SHARE_COLUMNS if c in context.features.columns]
        self.share = context.features[share_columns] if share_columns else None
        self.category_order = [
            c.replace("cat_share_", "").replace("_", " ") for c in share_columns
        ]
        self.depth = context.features["learning_depth_index"]

    def _raw_scores(self, user: str, candidates: np.ndarray) -> np.ndarray:
        if self.share is None or user not in self.share.index:
            return np.zeros(len(candidates))
        shares = self.share.loc[user]
        lookup = {name: float(shares.iloc[i]) for i, name in enumerate(self.category_order)}
        category_score = np.array(
            [lookup.get(self.course_category[int(c)].lower(), 0.0) for c in candidates]
        )
        # Level proximity: 1 when the course level matches the learner's mean depth,
        # falling linearly across the two-step ordinal scale.
        depth = float(self.depth.get(user, 1.0))
        level_score = 1.0 - np.abs(self.course_level_ordinal[candidates] - depth) / 2.0
        return minmax(category_score) + minmax(level_score)


def _user_item_matrix(context: FitContext) -> np.ndarray:
    """Binary user×item matrix from the training window.

    Binary, not weighted: Phase 2 verified there are **zero repeat
    ``(user, course)`` pairs**, so every observation has identical multiplicity and
    no confidence weighting is possible (which is also why iALS was rejected —
    decision log D-010).
    """
    users = list(context.seen.keys())
    matrix = np.zeros((len(users), context.n_items), dtype=float)
    for row, user in enumerate(users):
        for position in context.seen[user]:
            matrix[row, position] = 1.0
    return matrix
