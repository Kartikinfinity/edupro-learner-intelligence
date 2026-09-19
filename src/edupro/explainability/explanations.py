"""Explanations generated from the scorer's own decomposition.

CLAUDE.md §16 requires that every displayed recommendation carry a human-readable
explanation, and that explanations never contradict the actual scoring logic.
[R31] distinguishes *model-intrinsic* explanation, where the model's own mechanism
is interpretable, from *post-hoc* explanation, which can assert reasons the model
never used. Only the first can be faithful, so this module is deliberately not a
narrator: it has no access to the recommender and cannot invent a rationale.

Its inputs are the two things that are true by construction:

1. ``contributions`` — the per-component values the scorer itself returned via
   :meth:`edupro.recommendation.base.Scores.contribution_at`. A component the
   model did not use is **absent from this dict**, so it cannot be mentioned.
2. ``facts`` — quantities the caller verified against the same persisted data the
   scorer was fitted from. A phrase whose fact is missing degrades to its generic
   form rather than being asserted.

Three rules are enforced here and asserted by the test suite:

**No zero-weight component is ever named.** A contribution at or below
:data:`MIN_CONTRIBUTION` is dropped before any phrase is built.

**The tier frames the claim.** A learner with no history is told the list is broad
and popular, not that it is personalised. Dressing a popularity list as
personalisation is the failure §16 exists to prevent.

**No accuracy claim.** The list-level :data:`QUALITY_CAVEAT` states what Phase 3B
measured — that on this dataset no method ranks better than chance. It belongs
beside the list, once, not repeated per item.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

#: Contributions at or below this are treated as "the model did not use this".
#: Components are min-max scaled before weighting, so an exact zero is the normal
#: value for a signal that could not discriminate across the candidate set.
MIN_CONTRIBUTION: float = 1e-9

#: How each tier's recommendation is framed. The routing decision is a fact about
#: the learner, so stating it is both honest and useful.
TIER_FRAME: dict[str, str] = {
    "insufficient": (
        "You are new here, so these are broad, well-rated and widely taken courses "
        "across the catalogue rather than personalised picks"
    ),
    "minimal": (
        "You have one course in your history, so this is a similarity match to it "
        "rather than a behavioural profile"
    ),
    "moderate": "Based on the courses learners in your segment choose",
    "rich": "Based on the courses learners in your segment choose",
}

#: Stated once beside a list, never per item. Phase 3B, test window, 791 learners:
#: every 95% CI on the paired NDCG@10 difference against random contained zero.
QUALITY_CAVEAT: str = (
    "Measured on held-out data, no ranking method beat random selection on this "
    "dataset, so treat the ordering as a reasonable default rather than a "
    "prediction of what you will choose."
)


@dataclass(frozen=True)
class Explanation:
    """Why one course appears, and on what basis."""

    course_id: str
    tier: str
    #: Component name -> contribution, exactly as the scorer reported it.
    contributions: dict[str, float] = field(default_factory=dict)
    #: Evidence-backed phrases, most influential component first.
    reasons: list[str] = field(default_factory=list)
    #: The per-course sentence: the reasons only.
    sentence: str = ""
    #: How the tier frames every recommendation in this list. Kept separate from
    #: ``sentence`` because it is identical for every item — repeating it beside
    #: each course would be noise, and dropping it would remove the honesty the
    #: tier provides. Callers show it once beside the list.
    tier_frame: str = ""

    @property
    def full_sentence(self) -> str:
        """Frame and reasons together, for showing one explanation on its own."""
        if not self.tier_frame:
            return self.sentence
        return f"{self.tier_frame}. {self.sentence}"

    @property
    def components_used(self) -> list[str]:
        """Components that actually contributed, strongest first."""
        return [
            name
            for name, value in sorted(
                self.contributions.items(), key=lambda kv: -kv[1]
            )
            if value > MIN_CONTRIBUTION
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "course_id": self.course_id,
            "tier": self.tier,
            "contributions": self.contributions,
            "reasons": self.reasons,
            "sentence": self.sentence,
            "tier_frame": self.tier_frame,
        }


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or singular + "s")


def _cluster_popularity_reason(facts: Mapping[str, Any]) -> str:
    """Phrase for the within-segment enrollment count the scorer ranked by."""
    count = facts.get("segment_enrollments")
    segment = facts.get("segment_name")
    if count is None:
        return "Popular among learners in your segment"
    count = int(count)
    if segment:
        return (
            f"{count} {_plural(count, 'learner')} in your segment "
            f"({segment}) enrolled in this course"
        )
    return f"{count} {_plural(count, 'learner')} in your segment enrolled in this course"


def _content_reason(facts: Mapping[str, Any]) -> str:
    """Phrase for the cosine similarity between learner profile and course content.

    The optional clauses are only added when the caller verified them, because the
    similarity is computed over category, level, price type, rating and duration
    together — a high score does not by itself mean the category matched.
    """
    clauses: list[str] = []
    shared = facts.get("shared_category_count")
    category = facts.get("course_category")
    history = facts.get("history_size")
    if shared is not None and int(shared) > 0 and category:
        shared = int(shared)
        of_total = f" of your {int(history)}" if history else ""
        clauses.append(
            f"same category as {shared}{of_total} {_plural(shared, 'course')} ({category})"
        )
    if facts.get("level_match") and facts.get("course_level"):
        clauses.append(f"at the {facts['course_level']} level you usually choose")
    if not clauses:
        return "Content profile similar to the courses you have taken"
    return "Matches your learning profile: " + " and ".join(clauses)


def _fallback_reason(facts: Mapping[str, Any]) -> str:
    """Phrase for the diversified cold-start blend.

    The scorer ranks by within-category rank first and a popularity/rating blend
    second, so the honest statement names both — and says *why* the list spans
    categories, which is the property that route was chosen for.
    """
    category = facts.get("course_category")
    rank = facts.get("category_rank")
    rating = facts.get("course_rating")
    parts: list[str] = []
    if category and rank is not None and int(rank) == 0:
        parts.append(f"the strongest course in {category} by enrollments and rating")
    elif category:
        parts.append(f"a well-regarded course in {category}")
    if rating is not None:
        parts.append(f"rated {float(rating):.1f}")
    if not parts:
        return "Widely taken and well rated, shown to give you a broad first look"
    return (
        "Shown for breadth across categories: " + ", ".join(parts)
    )


def _popularity_reason(facts: Mapping[str, Any]) -> str:
    count = facts.get("global_enrollments")
    if count is None:
        return "One of the most widely taken courses on the platform"
    return f"Taken by {int(count)} learners across the platform"


def _rating_reason(facts: Mapping[str, Any]) -> str:
    rating = facts.get("course_rating")
    if rating is None:
        return "Highly rated by learners"
    return f"Rated {float(rating):.1f} out of 5"


def _preference_reason(facts: Mapping[str, Any]) -> str:
    category = facts.get("course_category")
    share = facts.get("category_share")
    if category and share is not None:
        return f"{category} accounts for {float(share) * 100:.0f}% of your enrollments"
    return "Matches your category and level preferences"


def _teacher_reason(facts: Mapping[str, Any]) -> str:
    count = facts.get("shared_teacher_count")
    if count is None:
        return "Taught by an instructor you have learned from before"
    count = int(count)
    return f"Taught by {count} {_plural(count, 'instructor')} you have learned from before"


def _item_similarity_reason(facts: Mapping[str, Any]) -> str:
    return "Frequently taken alongside the courses already in your history"


#: Component name -> phrase builder. Keys are the ``component`` attribute of the
#: recommenders in :mod:`edupro.recommendation.baselines`, so a component can only
#: get a phrase if a scorer actually emits it.
COMPONENT_PHRASES: dict[str, Any] = {
    "cluster_popularity": _cluster_popularity_reason,
    "content": _content_reason,
    "popularity_rating_diversity": _fallback_reason,
    "popularity": _popularity_reason,
    "rating": _rating_reason,
    "preference_match": _preference_reason,
    "teacher_affinity": _teacher_reason,
    "item_similarity": _item_similarity_reason,
}


def build_explanation(
    course_id: str,
    tier: str,
    contributions: Mapping[str, float],
    facts: Mapping[str, Any] | None = None,
) -> Explanation:
    """Render an explanation from a score decomposition and verified facts.

    Args:
        course_id: the recommended course.
        tier: the history tier the learner was routed to; frames the claim.
        contributions: per-component contributions from the scorer. Components at
            or below :data:`MIN_CONTRIBUTION` are dropped and never mentioned.
        facts: quantities the caller verified against the persisted data. Missing
            facts degrade a phrase to its generic form; they never invent one.

    Returns:
        An :class:`Explanation` whose ``reasons`` name only components the scorer
        used, ordered by contribution.

    Raises:
        ValueError: if ``tier`` is not a known routing tier, which would mean the
            caller and the router disagree about how the learner was served.
    """
    if tier not in TIER_FRAME:
        raise ValueError(f"Unknown tier {tier!r}; expected one of {sorted(TIER_FRAME)}.")
    facts = dict(facts or {})

    used = {
        name: float(value)
        for name, value in contributions.items()
        if float(value) > MIN_CONTRIBUTION
    }
    ordered = sorted(used.items(), key=lambda kv: -kv[1])

    reasons: list[str] = []
    for name, _ in ordered:
        builder = COMPONENT_PHRASES.get(name)
        if builder is None:
            # A scorer emitted a component this vocabulary does not know. Naming it
            # neutrally is honest; inventing a rationale for it would not be.
            reasons.append(f"Contributes to the score through the {name.replace('_', ' ')} signal")
            continue
        reasons.append(builder(facts))

    if reasons:
        sentence = ". ".join(reasons) + "."
    else:
        # Everything scaled to zero: the scorer could not discriminate at all, which
        # happens when every candidate has identical popularity. Saying so is the
        # only faithful option.
        sentence = (
            "No signal separated this course from the others, so its position "
            "reflects the catalogue order rather than a preference match."
        )

    return Explanation(
        course_id=course_id,
        tier=tier,
        contributions=dict(contributions),
        reasons=reasons,
        sentence=sentence,
        tier_frame=TIER_FRAME[tier],
    )
