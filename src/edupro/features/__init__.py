"""Learner-level aggregation and feature engineering.

Responsibilities: turn transaction-level records into one row per learner,
carrying the engagement, preference and behavioural features required by the
official documentation. Feature construction must be leakage-free with respect
to the temporal evaluation split (CLAUDE.md section 9).
"""
