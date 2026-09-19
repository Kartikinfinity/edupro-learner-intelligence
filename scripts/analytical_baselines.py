"""Phase 1 - analytical reference values implied by the dataset's dimensions.

These are closed-form consequences of the catalogue size and interaction counts
recorded in the Phase 0 inventory. They involve no inspection of data content,
so they do not pre-empt the Phase 2 audit; they exist because the experiment
design in research/experiment_plan.md must be calibrated against what a random
recommender would score on a catalogue this small.

Why this matters: with only 60 courses, a random ranker is a surprisingly strong
baseline. Reporting Hit Rate@10 without stating the random reference would be
misleading.

Usage
-----
    python scripts/analytical_baselines.py
"""

from __future__ import annotations

import json
from math import comb

from edupro import config

N_USERS = 3_000
N_COURSES = 60
N_INTERACTIONS = 10_000


def random_hit_rate(n_candidates: int, n_relevant: int, k: int) -> float:
    """P(at least one relevant item in a uniformly random top-k).

    Complement of drawing k items entirely from the irrelevant pool.
    """
    if k >= n_candidates:
        return 1.0
    misses = n_candidates - n_relevant
    if k > misses:
        return 1.0
    return 1.0 - comb(misses, k) / comb(n_candidates, k)


def main() -> None:
    mean_history = N_INTERACTIONS / N_USERS
    density = N_INTERACTIONS / (N_USERS * N_COURSES)

    # Under leave-one-out, a user with h total interactions holds out 1 and
    # keeps h-1 for training; candidates exclude the h-1 already-seen courses.
    summary: dict[str, object] = {
        "catalogue_size": N_COURSES,
        "n_users": N_USERS,
        "n_interactions": N_INTERACTIONS,
        "mean_interactions_per_user": round(mean_history, 4),
        "matrix_density_pct": round(density * 100, 4),
        "random_baseline_leave_one_out": {},
        "max_precision_at_k_single_holdout": {},
    }

    print(f"catalogue                 : {N_COURSES} courses")
    print(f"mean interactions/user    : {mean_history:.3f}")
    print(f"matrix density            : {density * 100:.2f}%")
    print()
    print("Random-ranker Hit Rate@K under leave-one-out (1 held-out course):")
    print(f"  {'train history':<16}{'candidates':<13}" + "".join(f"HR@{k:<8}" for k in (5, 10, 20)))
    for train_history in (1, 2, 3, 5, 10):
        candidates = N_COURSES - train_history
        row = {}
        cells = ""
        for k in (5, 10, 20):
            value = random_hit_rate(candidates, 1, k)
            row[f"k{k}"] = round(value, 4)
            cells += f"{value:<11.3f}"
        summary["random_baseline_leave_one_out"][f"train_history_{train_history}"] = row
        print(f"  {train_history:<16}{candidates:<13}{cells}")

    print()
    print("Ceiling on Precision@K when exactly 1 course is held out:")
    for k in (5, 10, 20):
        ceiling = 1.0 / k
        summary["max_precision_at_k_single_holdout"][f"k{k}"] = round(ceiling, 4)
        print(f"  Precision@{k:<4}<= {ceiling:.3f}")

    destination = config.ARTIFACTS_DIR / "phase1_analytical_baselines.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nWritten to {destination.relative_to(config.PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
