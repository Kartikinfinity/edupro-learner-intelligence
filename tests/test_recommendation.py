"""Phase 3B tests: metrics, recommenders, the hybrid, and the evaluation protocol.

Metric tests use hand-built rankings with known answers, so a metric bug cannot
hide behind a plausible-looking aggregate. Protocol tests assert the leakage
controls as executable checks — leakage produces believable numbers, so it cannot
be caught by inspection.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from edupro import config
from edupro.data.joins import build_interactions
from edupro.data.loader import load_all
from edupro.evaluation.metrics import (
    engagement_lift_proxy,
    gini,
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    precision_ceiling,
    recall_at_k,
    reciprocal_rank,
)
from edupro.evaluation.protocol import (
    build_evaluation_set,
    evaluate,
    paired_bootstrap,
    per_user_ndcg,
    verify_leakage_controls,
)
from edupro.evaluation.splits import apply_global_split, global_temporal_split
from edupro.features.learner import build_learner_features
from edupro.recommendation.base import Scores, build_fit_context, minmax
from edupro.recommendation.baselines import (
    ClusterPopularity,
    ContentBased,
    GlobalPopularity,
    ItemItemCF,
    PreferenceMatch,
    RandomRecommender,
    RatingRecommender,
    TeacherAffinity,
    UserUserHistory,
    UserUserProfile,
)
from edupro.recommendation.hybrid import (
    TIER_BOUNDARIES,
    TieredRecommender,
    WeightedHybrid,
    random_simplex_weights,
    tier_of,
)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def test_precision_counts_hits_in_the_top_k():
    ranked = np.array([3, 7, 1, 9, 2])
    assert precision_at_k(ranked, {7, 2}, 5) == pytest.approx(0.4)
    assert precision_at_k(ranked, {7, 2}, 2) == pytest.approx(0.5)


def test_precision_ceiling_bounds_what_is_achievable():
    """The constraint that makes raw Precision@10 misleading on a 60-item catalogue."""
    assert precision_ceiling(1, 10) == pytest.approx(0.10)
    assert precision_ceiling(3, 10) == pytest.approx(0.30)
    assert precision_ceiling(20, 10) == pytest.approx(1.0)


def test_recall_and_hit_rate():
    ranked = np.array([3, 7, 1])
    assert recall_at_k(ranked, {7, 9}, 3) == pytest.approx(0.5)
    assert hit_rate_at_k(ranked, {7, 9}, 3) == 1.0
    assert hit_rate_at_k(ranked, {9}, 3) == 0.0


def test_ndcg_is_one_for_a_perfect_ranking():
    ranked = np.array([1, 2, 3, 4])
    assert ndcg_at_k(ranked, {1, 2}, 4) == pytest.approx(1.0)


def test_ndcg_rewards_higher_placement():
    """The property that makes NDCG worth using where Precision is ceiling-limited."""
    early = ndcg_at_k(np.array([5, 1, 2, 3]), {5}, 4)
    late = ndcg_at_k(np.array([1, 2, 3, 5]), {5}, 4)
    assert early > late
    assert early == pytest.approx(1.0)


def test_ndcg_is_zero_when_nothing_relevant_is_retrieved():
    assert ndcg_at_k(np.array([1, 2, 3]), {9}, 3) == 0.0


def test_reciprocal_rank():
    assert reciprocal_rank(np.array([4, 7, 1]), {7}) == pytest.approx(0.5)
    assert reciprocal_rank(np.array([4, 7, 1]), {99}) == 0.0


def test_gini_is_zero_for_uniform_exposure_and_one_for_concentrated():
    assert gini(np.ones(10)) == pytest.approx(0.0, abs=1e-9)
    concentrated = np.zeros(10)
    concentrated[0] = 100
    assert gini(concentrated) > 0.85


def test_engagement_lift_proxy_is_a_ratio():
    assert engagement_lift_proxy(0.4, 0.2) == pytest.approx(2.0)
    assert np.isnan(engagement_lift_proxy(0.4, 0.0))


# ---------------------------------------------------------------------------
# Scores and ranking
# ---------------------------------------------------------------------------
def test_ranking_is_descending_and_deterministic_under_ties():
    """Ties are common on a near-uniform catalogue, so their order must be fixed."""
    scores = Scores(
        candidates=np.array([5, 2, 9, 1]),
        total=np.array([0.5, 0.5, 0.9, 0.1]),
    )
    first = scores.ranked()
    second = scores.ranked()
    assert first[0] == 9
    assert list(first[1:3]) == [2, 5]  # tie broken by candidate index
    assert (first == second).all()


def test_minmax_maps_a_constant_vector_to_zeros():
    """A signal that cannot discriminate must contribute nothing, not a constant."""
    assert (minmax(np.array([3.0, 3.0, 3.0])) == 0).all()
    assert minmax(np.array([0.0, 5.0, 10.0])).tolist() == [0.0, 0.5, 1.0]


def test_contribution_at_returns_the_decomposition():
    """D-015: explanations are generated from the score decomposition itself."""
    scores = Scores(
        candidates=np.array([1, 2]),
        total=np.array([0.7, 0.3]),
        components={"content": np.array([0.4, 0.1]), "rating": np.array([0.3, 0.2])},
    )
    assert scores.contribution_at(1) == {"content": 0.4, "rating": 0.3}


# ---------------------------------------------------------------------------
# Tiers
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "history,expected",
    [(0, "insufficient"), (1, "minimal"), (2, "moderate"), (4, "moderate"),
     (8, "moderate"), (9, "rich"), (16, "rich")],
)
def test_tier_boundaries(history, expected):
    assert tier_of(history) == expected


def test_tier_boundaries_are_contiguous_and_cover_everything():
    for (_, _, high), (_, low, _) in zip(TIER_BOUNDARIES, TIER_BOUNDARIES[1:]):
        assert low == high + 1


# ---------------------------------------------------------------------------
# Fixtures on the real data
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def pieces():
    data = load_all()
    interactions = build_interactions(data, with_user_demographics=True, with_teacher=True)
    split = global_temporal_split(interactions)
    frames = apply_global_split(interactions, split)
    catalogue = (
        interactions.drop_duplicates(subset=[config.KEY_COURSE])
        .set_index(config.KEY_COURSE)
        .loc[sorted(interactions[config.KEY_COURSE].unique())]
        .reset_index()
    )
    features = build_learner_features(frames["fit"], users=data.users)
    clusters = pd.Series(
        np.resize([0, 1, 2, 3], len(features)), index=features.index, name="cluster"
    )
    context = build_fit_context(frames["fit"], catalogue, features, clusters)
    evaluation_set = build_evaluation_set(frames["fit"], frames["test"], context, "A_test")
    return context, evaluation_set, frames, split


ALL_RECOMMENDERS = [
    RandomRecommender, GlobalPopularity, RatingRecommender, ContentBased,
    PreferenceMatch, UserUserHistory, UserUserProfile, ItemItemCF,
    ClusterPopularity, TeacherAffinity,
]


@pytest.mark.parametrize("factory", ALL_RECOMMENDERS, ids=lambda f: f.name)
def test_every_recommender_scores_every_candidate(factory, pieces):
    context, evaluation_set, _, _ = pieces
    recommender = factory().fit(context)
    user = evaluation_set.users[0]
    candidates = context.candidates_for(user)
    scores = recommender.score(user, candidates)
    assert len(scores.total) == len(candidates)
    assert np.isfinite(scores.total).all()
    assert set(scores.ranked().tolist()) == set(candidates.tolist())


@pytest.mark.parametrize("factory", ALL_RECOMMENDERS, ids=lambda f: f.name)
def test_no_recommender_returns_an_already_enrolled_course(factory, pieces):
    """CLAUDE.md §23, and leakage control L2: exclusion uses training history only."""
    context, evaluation_set, _, _ = pieces
    recommender = factory().fit(context)
    for user in evaluation_set.users[:50]:
        seen = context.seen.get(user, set())
        assert not set(recommender.recommend(user, k=10).tolist()) & seen


def test_recommendations_are_deterministic(pieces):
    context, evaluation_set, _, _ = pieces
    recommender = GlobalPopularity().fit(context)
    user = evaluation_set.users[0]
    assert (recommender.recommend(user, 10) == recommender.recommend(user, 10)).all()


def test_unknown_user_still_receives_recommendations(pieces):
    """Cold start must degrade gracefully, not raise."""
    context, _, _, _ = pieces
    for factory in (GlobalPopularity, ContentBased, ClusterPopularity, ItemItemCF):
        recommender = factory().fit(context)
        candidates = np.arange(context.n_items)
        scores = recommender.score("U99999", candidates)
        assert len(scores.total) == len(candidates)
        assert np.isfinite(scores.total).all()


def test_popularity_reflects_only_the_training_window(pieces):
    """Leakage control L5, as an executable check."""
    context, _, frames, _ = pieces
    recommender = GlobalPopularity().fit(context)
    assert recommender.popularity.sum() == pytest.approx(len(frames["fit"]))


# ---------------------------------------------------------------------------
# Hybrid
# ---------------------------------------------------------------------------
def test_hybrid_returns_per_component_contributions(pieces):
    """The interface requirement fixed in Phase 1 (D-015) before implementation."""
    context, evaluation_set, _, _ = pieces
    components = {
        "content_based": ContentBased().fit(context),
        "rating": RatingRecommender().fit(context),
    }
    hybrid = WeightedHybrid(components, {"content_based": 0.7, "rating": 0.3}).fit(context)
    user = evaluation_set.users[0]
    scores = hybrid.score(user, context.candidates_for(user))
    assert set(scores.components) == {"content_based", "rating"}
    top = scores.ranked(1)[0]
    contributions = scores.contribution_at(int(top))
    assert sum(contributions.values()) == pytest.approx(
        float(scores.total[np.flatnonzero(scores.candidates == top)[0]])
    )


def test_hybrid_components_never_claim_a_zero_weighted_signal(pieces):
    """An explanation must not name a component the scorer gave zero weight."""
    context, evaluation_set, _, _ = pieces
    components = {
        "content_based": ContentBased().fit(context),
        "rating": RatingRecommender().fit(context),
    }
    hybrid = WeightedHybrid(components, {"content_based": 1.0, "rating": 0.0}).fit(context)
    user = evaluation_set.users[0]
    scores = hybrid.score(user, context.candidates_for(user))
    assert "rating" not in scores.components


def test_hybrid_with_one_component_matches_that_component_ranking(pieces):
    context, evaluation_set, _, _ = pieces
    content = ContentBased().fit(context)
    hybrid = WeightedHybrid({"content_based": content}, {"content_based": 1.0}).fit(context)
    user = evaluation_set.users[0]
    candidates = context.candidates_for(user)
    assert (hybrid.score(user, candidates).ranked() == content.score(user, candidates).ranked()).all()


def test_with_weights_does_not_refit_components(pieces):
    context, _, _, _ = pieces
    content = ContentBased().fit(context)
    hybrid = WeightedHybrid({"content_based": content}, {"content_based": 1.0}).fit(context)
    clone = hybrid.with_weights({"content_based": 0.5})
    assert clone.components["content_based"] is content
    assert clone.context is hybrid.context


def test_weight_samples_lie_on_the_simplex():
    samples = random_simplex_weights(["a", "b", "c"], 50, seed=42)
    assert len(samples) == 50
    for weights in samples:
        assert sum(weights.values()) == pytest.approx(1.0)
        assert all(v >= 0 for v in weights.values())
    assert any(any(v == 0 for v in w.values()) for w in samples), "search must explore subsets"


def test_tiered_routes_by_training_history_only(pieces):
    """Leakage control L3: a learner's tier must not depend on the held-out item."""
    context, evaluation_set, _, _ = pieces
    popularity = GlobalPopularity().fit(context)
    content = ContentBased().fit(context)
    tiered = TieredRecommender(routes={
        "insufficient": popularity, "minimal": content,
        "moderate": content, "rich": popularity,
    }).fit(context)
    for user in evaluation_set.users[:40]:
        tier, _ = tiered.route_for(user)
        assert tier == tier_of(len(context.seen.get(user, set())))


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------
def test_evaluation_set_excludes_learners_without_training_history(pieces):
    """CLAUDE.md §12: they must not be scored as personalised users."""
    context, evaluation_set, _, _ = pieces
    for user in evaluation_set.users:
        assert len(context.seen.get(user, set())) >= 1


def test_held_out_items_are_never_already_seen(pieces):
    context, evaluation_set, _, _ = pieces
    for user, relevant in evaluation_set.relevant.items():
        assert not relevant & context.seen.get(user, set())


def test_all_leakage_controls_pass_on_the_real_split(pieces):
    context, evaluation_set, frames, split = pieces
    checks = verify_leakage_controls(
        context, frames["fit"], frames["test"], evaluation_set, split.test_date
    )
    assert checks["all_passed"], checks


def test_leakage_check_detects_an_injected_violation(pieces):
    """The check must be able to fail, or it proves nothing."""
    context, evaluation_set, frames, split = pieces
    contaminated = pd.concat([frames["fit"], frames["test"].head(5)], ignore_index=True)
    checks = verify_leakage_controls(
        context, contaminated, frames["test"], evaluation_set, split.test_date
    )
    assert not checks["L1_no_heldout_rows_in_training"]["passed"]
    assert not checks["all_passed"]


def test_evaluate_reports_per_tier_as_well_as_overall(pieces):
    context, evaluation_set, _, _ = pieces
    result = evaluate(GlobalPopularity().fit(context), context, evaluation_set, ks=(10,))
    assert result.overall[10].n_users > 0
    assert set(result.by_tier) <= {"insufficient", "minimal", "moderate", "rich"}
    assert sum(t[10].n_users for t in result.by_tier.values()) == result.overall[10].n_users


def test_paired_bootstrap_detects_a_real_difference_and_ignores_noise():
    better = {f"u{i}": 0.5 for i in range(200)}
    baseline = {f"u{i}": 0.2 for i in range(200)}
    assert paired_bootstrap(better, baseline)["significant"]

    rng = np.random.default_rng(config.RANDOM_SEED)
    a = {f"u{i}": float(rng.normal()) for i in range(200)}
    b = {f"u{i}": float(rng.normal()) for i in range(200)}
    assert not paired_bootstrap(a, b)["significant"]


def test_per_user_ndcg_covers_the_evaluation_set(pieces):
    context, evaluation_set, _, _ = pieces
    scores = per_user_ndcg(GlobalPopularity().fit(context), context, evaluation_set)
    assert set(scores) == set(evaluation_set.relevant)
    assert all(0.0 <= v <= 1.0 for v in scores.values())


# ---------------------------------------------------------------------------
# Cold-start fallback (Phase 4)
# ---------------------------------------------------------------------------
def test_diversified_fallback_spans_more_categories_than_popularity(pieces):
    """§15 prescribes popularity + rating + **diversity**.

    A plain popularity-and-rating blend fails the diversity half: measured, it
    shows a cold-start learner 7 of 12 categories against the diversified
    fallback's 10, and concentrates 20% of its list in one category against 10%.
    """
    from edupro.recommendation.baselines import DiversifiedFallback

    context, _, _, _ = pieces
    categories = (
        context.courses.set_index(config.KEY_COURSE)
        .reindex(context.course_ids)["CourseCategory"]
        .tolist()
    )

    popular = GlobalPopularity().fit(context).recommend("U99999", k=10)
    diverse = DiversifiedFallback().fit(context).recommend("U99999", k=10)

    popular_categories = {categories[int(i)] for i in popular}
    diverse_categories = {categories[int(i)] for i in diverse}
    assert len(diverse_categories) > len(popular_categories)


def test_diversified_fallback_never_repeats_a_category_within_the_catalogue_width(pieces):
    """With 12 categories, a top-10 from the round-robin must be all-distinct."""
    from edupro.recommendation.baselines import DiversifiedFallback

    context, _, _, _ = pieces
    categories = (
        context.courses.set_index(config.KEY_COURSE)
        .reindex(context.course_ids)["CourseCategory"]
        .tolist()
    )
    top = DiversifiedFallback().fit(context).recommend("U99999", k=10)
    chosen = [categories[int(i)] for i in top]
    assert len(set(chosen)) == len(chosen)


def test_diversified_fallback_still_orders_by_quality_within_a_round(pieces):
    """Diversity re-ranks; it must not discard the popularity/rating signal."""
    from edupro.recommendation.baselines import DiversifiedFallback

    context, _, _, _ = pieces
    fallback = DiversifiedFallback().fit(context)
    top = fallback.recommend("U99999", k=12)
    qualities = [fallback.quality[int(i)] for i in top]
    # The first full round covers every category, ordered by quality.
    assert qualities == sorted(qualities, reverse=True)
