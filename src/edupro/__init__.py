"""EduPro - student segmentation and personalized course recommendation system.

The package is organised along the pipeline boundaries mandated by CLAUDE.md
section 18, so that each stage can be developed, tested and reasoned about
independently:

    edupro.config           project paths, sheet names and global constants
    edupro.data             ingestion and schema validation of the raw workbook
    edupro.features         learner-level aggregation and feature engineering
    edupro.segmentation     clustering, model selection and cluster profiling
    edupro.recommendation   candidate generation, scoring and ranking
    edupro.evaluation       segmentation and recommendation metrics
    edupro.explainability   human-readable justifications for recommendations

Subpackages are populated during Phase 5 (production implementation). Phase 0
establishes only the boundaries and the shared configuration.
"""

__version__ = "0.1.0"
