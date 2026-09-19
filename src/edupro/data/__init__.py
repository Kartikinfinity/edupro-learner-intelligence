"""Ingestion and validation of the authoritative EduPro workbook.

Responsibilities: load the raw Excel sheets, validate them against an explicit
schema, and emit reproducible processed copies. This layer never mutates
``data/raw/`` (CLAUDE.md section 8).
"""
