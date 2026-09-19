"""Fit the frozen architecture and write the production artifact set.

Run this once after checking out the repository, or whenever the source data
changes. The application never calls it.

Usage
-----
    python scripts/train_production_model.py
    python scripts/train_production_model.py --no-stability   # faster, skips bootstrap
"""

from __future__ import annotations

import argparse
import logging
import sys

from edupro.logging_utils import configure_logging
from edupro.pipeline import PipelineError, train


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-stability",
        action="store_true",
        help="skip the bootstrap stability assessment (about a minute faster)",
    )
    parser.add_argument("--quiet", action="store_true", help="log warnings and errors only")
    args = parser.parse_args(argv)

    configure_logging(logging.WARNING if args.quiet else logging.INFO)

    try:
        manifest = train(with_stability=not args.no_stability)
    except PipelineError as error:
        print(f"Training failed: {error}", file=sys.stderr)
        return 1

    print()
    print(f"Artifact set {manifest.artifact_set_version} written ({manifest.model_version})")
    print(f"  learners     {manifest.training['n_learners']:,}")
    print(f"  interactions {manifest.training['n_interactions']:,}")
    print(f"  courses      {manifest.training['n_courses']:,}")
    print(f"  segments     {manifest.segmentation['sizes']}")
    print(f"  tiers        {manifest.recommendation['tiers']}")
    print(f"  files        {len(manifest.files)}")
    print()
    print("Generate recommendations with:  python scripts/recommend.py --user <UserID>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
