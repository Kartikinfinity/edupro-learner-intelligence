"""Hybrid recommenders: weighted combination and history-tier switching.

Burke's taxonomy [R17] separates two strategies this project needs, and keeping
them separate is what makes each evaluable:

**Weighted hybrid** (:class:`WeightedHybrid`) — combine content relevance, learner
similarity, cluster popularity, rating relevance and preference match into one
score. CLAUDE.md §14 forbids arbitrary weights, so they are found by search on the
**validation** split and reported with an ablation and a sensitivity surface.

**Switching hybrid** (:class:`TieredRecommender`) — route each learner to a
different method by how much history they have. CLAUDE.md §15 requires this, and
Phase 2 made it unavoidable: 54% of learners have exactly one interaction.

Both return per-component contributions, so explanations are generated from the
score decomposition itself rather than written afterwards (D-015, §16).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from edupro.recommendation.base import BaseRecommender, FitContext, Scores, minmax


class WeightedHybrid(BaseRecommender):
    """Weighted linear combination of component recommenders.

    Each component's raw scores are min-max scaled across the candidate set before
    weighting, so a weight means the same thing across signals with different
    natural ranges (counts, cosines, ratings). Components that cannot discriminate
    on a given candidate set scale to all-zeros and contribute nothing — rather
    than contributing a constant offset that would silently shift the ranking.
    """

    name = "hybrid"

    def __init__(self, components: dict[str, BaseRecommender], weights: dict[str, float]) -> None:
        super().__init__()
        self.components = components
        self.weights = weights

    def _fit(self, context: FitContext) -> None:
        for recommender in self.components.values():
            if recommender.context is None:
                recommender.fit(context)

    def score(self, user: str, candidates: np.ndarray) -> Scores:
        contributions: dict[str, np.ndarray] = {}
        total = np.zeros(len(candidates), dtype=float)
        for name, recommender in self.components.items():
            weight = float(self.weights.get(name, 0.0))
            if weight == 0.0:
                continue
            scaled = minmax(np.asarray(recommender._raw_scores(user, candidates), dtype=float))
            weighted = weight * scaled
            contributions[name] = weighted
            total += weighted
        return Scores(candidates=candidates, total=total, components=contributions)

    def _raw_scores(self, user: str, candidates: np.ndarray) -> np.ndarray:
        return self.score(user, candidates).total

    def with_weights(self, weights: dict[str, float]) -> "WeightedHybrid":
        """A copy sharing the fitted components but using different weights.

        Weight search refits nothing: the components are fitted once and only the
        combination changes, so a search over hundreds of weight vectors costs
        almost nothing and cannot accidentally refit on different data.
        """
        clone = WeightedHybrid(self.components, weights)
        clone.context = self.context
        return clone


#: Tier boundaries, handed over by the Phase 2 distribution rather than tuned:
#: the interaction-count histogram has a hard empty band at 5-8, so the
#: moderate/rich boundary is drawn through a region containing no learners
#: (decision log D-021).
TIER_BOUNDARIES: tuple[tuple[str, int, int], ...] = (
    ("insufficient", 0, 0),
    ("minimal", 1, 1),
    ("moderate", 2, 8),
    ("rich", 9, 10**9),
)


def tier_of(history_length: int) -> str:
    """Name the tier for a training-window history length.

    **Must be called with training-window history only** (leakage control L3). A
    learner with 1 training and 1 held-out interaction has 2 in total; routing on
    total history would let the held-out interaction's existence influence the
    routing decision. That leak hides in the routing logic rather than the feature
    matrix, so a global-timeline audit of features would not catch it.
    """
    for name, low, high in TIER_BOUNDARIES:
        if low <= history_length <= high:
            return name
    return "rich"


@dataclass
class TieredRecommender:
    """Switching hybrid: a different recommender per history tier.

    Also the honest option. A learner with no history cannot be personalised, and
    saying so is better than dressing a popularity list as personalisation
    (CLAUDE.md §16, and [R32]'s transparency aim).
    """

    routes: dict[str, BaseRecommender]
    name: str = "tiered"
    context: FitContext | None = field(default=None, repr=False)

    def fit(self, context: FitContext) -> "TieredRecommender":
        self.context = context
        for recommender in self.routes.values():
            if recommender.context is None:
                recommender.fit(context)
        return self

    def route_for(self, user: str) -> tuple[str, BaseRecommender]:
        assert self.context is not None
        history = len(self.context.seen.get(user, set()))
        tier = tier_of(history)
        return tier, self.routes.get(tier, self.routes["insufficient"])

    def score(self, user: str, candidates: np.ndarray) -> Scores:
        _, recommender = self.route_for(user)
        return recommender.score(user, candidates)

    def recommend(self, user: str, k: int = 10) -> np.ndarray:
        assert self.context is not None
        candidates = self.context.candidates_for(user)
        if len(candidates) == 0:
            return np.array([], dtype=int)
        return self.score(user, candidates).ranked(k)


def random_simplex_weights(
    names: list[str], n_samples: int, seed: int, allow_zero: bool = True
) -> list[dict[str, float]]:
    """Sample weight vectors from the simplex for the hybrid weight search.

    A Dirichlet(1) sample is uniform over the simplex, so the search covers the
    space evenly rather than concentrating near the centre. Half the samples have a
    randomly chosen component zeroed, so the search naturally explores subsets
    instead of only full combinations — which matters when the honest answer may be
    that most components contribute nothing.
    """
    rng = np.random.default_rng(seed)
    samples: list[dict[str, float]] = []
    for i in range(n_samples):
        weights = rng.dirichlet(np.ones(len(names)))
        if allow_zero and i % 2 == 1:
            keep = rng.integers(1, len(names) + 1)
            drop = rng.permutation(len(names))[keep:]
            weights[drop] = 0.0
            if weights.sum() > 0:
                weights = weights / weights.sum()
        samples.append({name: float(w) for name, w in zip(names, weights)})
    return samples
