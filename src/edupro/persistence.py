"""Artifact persistence and version checking for the frozen model.

The production system loads what was *learned* (a fitted scaler, a fitted
K-Means) rather than re-deriving it, so the serving path must be able to answer
two questions before it trusts anything on disk:

**Was this artifact set written by compatible code?**
    scikit-learn documents loading an estimator across library versions as
    unsupported. The failure mode is the dangerous kind — a pickle from a
    different version usually loads and then produces subtly different numbers,
    rather than raising. The manifest records the library versions that wrote the
    set, and :func:`check_compatibility` compares them on every load.

**Is this artifact set internally consistent?**
    The artifacts are mutually dependent: per-cluster popularity counts are
    indexed by the cluster labels the clusterer produced, so pairing a freshly
    fitted clusterer with a stale popularity table is wrong in a way no
    single-component test would catch (the CACE problem, [R33]). Every file is
    hashed at write time and re-hashed at load time, and every file carries the
    same ``artifact_set_version``.

Both checks raise by default. ``strict=False`` downgrades them to warnings, which
exists for debugging a mismatched environment — not for production.
"""

from __future__ import annotations

import json
import logging
import platform
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from edupro import config

logger = logging.getLogger(__name__)

#: The frozen model version (research/ARCHITECTURE_FREEZE.md). Bumped only when
#: the freeze is deliberately reopened under the four conditions in D-044.
MODEL_VERSION: str = "edupro-1.0.0"

#: Filename of the manifest inside the models directory.
MANIFEST_NAME: str = "manifest.json"

#: Line ending used for every JSON artifact this project writes.
#:
#: Explicit, because the default translates to the platform's native ending. The
#: manifest hashes these files and the loader re-hashes them at startup, so a set
#: written on Windows (CRLF) failed its own integrity check after a Linux checkout
#: (LF). That is what broke the first public deployment (decision log D-072).
LF: str = "\n"

#: Libraries whose version is recorded. A mismatch in scikit-learn invalidates the
#: pickled estimators; numpy and pandas affect the persisted arrays and frames.
TRACKED_LIBRARIES: tuple[str, ...] = ("numpy", "pandas", "scikit-learn", "joblib")

#: Libraries whose mismatch is treated as an error rather than a warning.
#: scikit-learn alone, because it is the one that silently changes results.
CRITICAL_LIBRARIES: frozenset[str] = frozenset({"scikit-learn"})


class ArtifactVersionError(RuntimeError):
    """Raised when artifacts on disk are incompatible with the running code."""


class ArtifactIntegrityError(RuntimeError):
    """Raised when an artifact is missing, corrupt, or from a different set."""


def library_versions() -> dict[str, str]:
    """Versions of the libraries whose behaviour the artifacts depend on."""
    from importlib.metadata import PackageNotFoundError, version

    versions: dict[str, str] = {"python": platform.python_version()}
    for package in TRACKED_LIBRARIES:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:  # pragma: no cover - environment-dependent
            versions[package] = "not-installed"
    return versions


@dataclass
class Manifest:
    """Provenance and integrity record for one artifact set.

    ``artifact_set_version`` is what ties the files together: every file written
    by one training run carries the same value, so a set assembled from two runs
    is detectable even if each individual file is valid.
    """

    model_version: str
    artifact_set_version: str
    created_at: str
    seed: int
    workbook_sha256: str
    libraries: dict[str, str]
    training: dict[str, Any]
    segmentation: dict[str, Any]
    recommendation: dict[str, Any]
    #: Relative path -> SHA-256 of the file as written.
    files: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Manifest":
        known = {f for f in cls.__dataclass_fields__}
        missing = known - set(payload)
        if missing:
            raise ArtifactIntegrityError(f"Manifest is missing fields: {sorted(missing)}")
        return cls(**{k: v for k, v in payload.items() if k in known})


def save_manifest(manifest: Manifest, directory: Path | None = None) -> Path:
    """Write the manifest as readable JSON beside the artifacts it describes.

    JSON rather than a pickle so a reviewer can see what produced a result without
    executing anything.
    """
    directory = directory or config.MODELS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / MANIFEST_NAME
    # LF on every platform: the manifest sits beside files whose hashes it
    # records, and a platform-dependent encoding of the manifest itself would be
    # the same trap one level up (D-072).
    destination.write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=False),
        encoding="utf-8",
        newline=LF,
    )
    logger.info("Wrote manifest to %s", destination)
    return destination


def load_manifest(directory: Path | None = None) -> Manifest:
    """Read the manifest, with an actionable error when it is absent."""
    directory = directory or config.MODELS_DIR
    path = directory / MANIFEST_NAME
    if not path.exists():
        raise ArtifactIntegrityError(
            f"No manifest at {path}. Train the production model first: "
            "python scripts/train_production_model.py"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:  # pragma: no cover - corrupt file
        raise ArtifactIntegrityError(f"Manifest at {path} is not valid JSON: {error}") from error
    return Manifest.from_dict(payload)


def new_artifact_set_version(seed: int, workbook_sha256: str, created_at: str) -> str:
    """A short, deterministic-looking id for one training run.

    Derived from the inputs that define the run, so two sets written from the same
    data and seed at different times are still distinguishable by timestamp — which
    is what makes a half-updated directory detectable.
    """
    import hashlib

    digest = hashlib.sha256(f"{seed}|{workbook_sha256}|{created_at}".encode()).hexdigest()
    return digest[:12]


def utc_timestamp() -> str:
    """Current UTC time, ISO-8601, second resolution."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def check_compatibility(manifest: Manifest, strict: bool = True) -> list[str]:
    """Compare the running environment against the one that wrote the artifacts.

    Args:
        manifest: the loaded manifest.
        strict: raise on any problem. With ``False``, problems are logged as
            warnings and returned — for diagnosing a mismatched environment, not
            for serving from one.

    Returns:
        Human-readable problem descriptions; empty when the environment matches.

    Raises:
        ArtifactVersionError: in strict mode, if the code version differs or a
            critical library version differs.
    """
    problems: list[str] = []

    if manifest.model_version != MODEL_VERSION:
        problems.append(
            f"Model version mismatch: artifacts are {manifest.model_version!r}, "
            f"code is {MODEL_VERSION!r}. Retrain with the current code."
        )

    current = library_versions()
    for package, recorded in manifest.libraries.items():
        running = current.get(package)
        if running is None or running == recorded:
            continue
        message = f"{package}: artifacts written with {recorded}, running {running}"
        if package in CRITICAL_LIBRARIES:
            problems.append(
                message + " - scikit-learn does not support loading estimators "
                "across versions; results may differ silently."
            )
        else:
            logger.warning("Library version drift (non-critical) - %s", message)

    if manifest.workbook_sha256 != config.RAW_WORKBOOK_SHA256:
        problems.append(
            "Artifacts were trained from a different source workbook "
            f"({manifest.workbook_sha256[:12]}... vs {config.RAW_WORKBOOK_SHA256[:12]}...)."
        )

    if problems and strict:
        raise ArtifactVersionError("; ".join(problems))
    for problem in problems:
        logger.warning("Artifact compatibility: %s", problem)
    return problems


def check_integrity(manifest: Manifest, root: Path | None = None) -> list[str]:
    """Verify every file the manifest lists is present and unchanged.

    Detects the failure mode that matters most here: an artifact set updated
    halfway, where each file is individually valid but they no longer belong to
    the same training run.

    Returns:
        Problem descriptions; empty when every file matches its recorded hash.
    """
    from edupro.data.loader import sha256

    root = root or config.PROJECT_ROOT
    problems: list[str] = []
    for relative, expected in manifest.files.items():
        path = root / relative
        if not path.exists():
            problems.append(f"missing artifact: {relative}")
            continue
        actual = sha256(path)
        if actual != expected:
            problems.append(
                f"artifact changed since it was written: {relative} "
                f"({actual[:12]}... != {expected[:12]}...)"
            )
    return problems


def verify_artifacts(
    directory: Path | None = None, strict: bool = True
) -> tuple[Manifest, list[str]]:
    """Load the manifest and run both checks. The single entry point for serving.

    Args:
        directory: the models directory holding the manifest.
        strict: raise on any problem rather than returning it.

    Returns:
        The manifest and the list of problems found (empty in strict mode, since
        any problem would have raised).

    Raises:
        ArtifactIntegrityError: a file is missing or has changed.
        ArtifactVersionError: the environment or code version is incompatible.
    """
    manifest = load_manifest(directory)
    problems = check_compatibility(manifest, strict=strict)
    integrity = check_integrity(manifest)
    if integrity and strict:
        raise ArtifactIntegrityError("; ".join(integrity))
    for problem in integrity:
        logger.warning("Artifact integrity: %s", problem)
    return manifest, problems + integrity
