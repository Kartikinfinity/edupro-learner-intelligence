"""Generate recommendations from the command line — no notebook required.

Loads the persisted artifact set and prints an explained top-K for one learner.
An identifier that is not in the artifact set is served the cold-start route and
labelled as such, which is how a genuinely new learner is handled.

Usage
-----
    python scripts/recommend.py --user U00001
    python scripts/recommend.py --user U00001 --k 5 --category "Data Science"
    python scripts/recommend.py --user NEW-LEARNER            # cold-start route
    python scripts/recommend.py --user U00001 --json           # machine-readable
    python scripts/recommend.py --describe                    # artifact set summary
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from edupro.inference import InferenceError, RecommendationService
from edupro.logging_utils import configure_logging
from edupro.persistence import ArtifactIntegrityError, ArtifactVersionError


def _courses(count: int) -> str:
    return f"{count} course" if count == 1 else f"{count} courses"


def _print_human(result, service) -> None:
    profile = None
    if result.is_known_learner:
        profile = service.learner_profile(result.user_id)

    print()
    print(f"Learner {result.user_id}")
    if profile:
        print(
            f"  segment   {result.segment} - {result.segment_name}\n"
            f"  tier      {result.tier} ({_courses(result.history_size)} in history)\n"
            f"  prefers   {profile['preferred_category']}, {profile['preferred_level']}"
        )
    else:
        print(f"  not in the artifact set - served the cold-start route ({result.tier})")
    filters = {k: v for k, v in result.filters.items() if v}
    if filters:
        print(f"  filters   {filters}")
    print(f"  candidates {result.n_candidates} unseen courses")
    if result.recommendations:
        # The tier frame is identical for every item, so it is stated once.
        print()
        print(f"  {result.recommendations[0].explanation.tier_frame}.")
    print()

    for item in result.recommendations:
        free = "free" if item.is_free else f"{item.price:.0f}"
        print(f"{item.rank:>2}. {item.course_name}  [{item.course_id}]")
        print(f"    {item.category} | {item.level} | rated {item.rating:.1f} | {free}")
        print(f"    {item.explanation.sentence}")
        print()

    print(f"Note: {result.caveat}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", help="learner identifier, e.g. U0001")
    parser.add_argument("--k", type=int, default=10, help="number of recommendations")
    parser.add_argument("--category", help="restrict to one course category")
    parser.add_argument("--level", help="restrict to one course level")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument("--describe", action="store_true", help="summarise the artifact set")
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="load despite version or integrity problems (diagnostics only)",
    )
    parser.add_argument("--verbose", action="store_true", help="log at INFO level")
    args = parser.parse_args(argv)

    configure_logging(logging.INFO if args.verbose else logging.WARNING)

    if not args.describe and not args.user:
        parser.error("either --user or --describe is required")

    try:
        service = RecommendationService.load(strict=not args.no_strict)
    except (ArtifactIntegrityError, ArtifactVersionError) as error:
        print(f"Could not load artifacts: {error}", file=sys.stderr)
        print(
            "Train the production model first: python scripts/train_production_model.py",
            file=sys.stderr,
        )
        return 1

    if args.describe:
        print(json.dumps(service.describe(), indent=2, default=str))
        return 0

    try:
        result = service.recommend(
            args.user, k=args.k, category=args.category, level=args.level
        )
    except InferenceError as error:
        print(f"Could not generate recommendations: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        _print_human(result, service)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
