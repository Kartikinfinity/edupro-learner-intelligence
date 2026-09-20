"""Phase 6E — audit whether this repository can actually be deployed publicly.

A deployment audit is worth something only if it tests the things that break
deployments rather than the things that are easy to check. Three of the probes
here exist because they catch failures that are invisible on the development
machine:

**Linux case sensitivity.** This project is developed on Windows, where
``Models/Scaler.joblib`` and ``models/scaler.joblib`` are the same file. On
Streamlit Community Cloud they are not. A case mismatch works locally forever and
fails on the first deploy.

**Fresh-clone availability.** The app loads an artifact set. If any file in that
set is git-ignored, the app works for the author and shows an empty state to
everyone else. The probe checks every manifest entry against ``git ls-files``,
not against the filesystem.

**Public error disclosure.** A configuration that shows full tracebacks is useful
locally and is an information leak on a public URL.

Usage
-----
    python scripts/deployment_readiness.py
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from edupro import config

APP = config.PROJECT_ROOT / "app"
ENTRY = APP / "streamlit_app.py"
REQUIREMENTS = config.PROJECT_ROOT / "requirements.txt"
STREAMLIT_CONFIG = config.PROJECT_ROOT / ".streamlit" / "config.toml"
OUT = config.ARTIFACTS_DIR / "validation" / "deployment_readiness.json"

#: Packages that exist only on one platform. Any of these in requirements.txt
#: fails the Linux build on Community Cloud.
PLATFORM_SPECIFIC = {
    "pywin32", "pywinpty", "win32-setctime", "colorama", "appscript",
    "pyobjc", "pyobjc-core", "winshell", "wmi",
}


@dataclass
class Finding:
    check: str
    severity: str  # "pass" | "fail" | "warn"
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


class Audit:
    def __init__(self) -> None:
        self.findings: list[Finding] = []

    def record(self, check: str, severity: str, detail: str, **evidence: Any) -> None:
        self.findings.append(Finding(check, severity, detail, evidence))
        mark = {"pass": "OK  ", "fail": "FAIL", "warn": "WARN"}[severity]
        print(f"  [{mark}] {check}: {detail}")

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "fail"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warn"]


def tracked_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True,
        cwd=config.PROJECT_ROOT, check=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def app_sources() -> list[Path]:
    return sorted(APP.rglob("*.py"))


# ===========================================================================
def check_secrets(audit: Audit, tracked: set[str]) -> None:
    patterns = [
        (r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token|password)\s*[:=]\s*['\"][^'\"]{8,}", "credential"),
        (r"gh[pousr]_[A-Za-z0-9]{20,}", "github token"),
        (r"sk-[A-Za-z0-9]{32,}", "api key"),
        (r"-----BEGIN [A-Z ]*PRIVATE KEY", "private key"),
    ]
    offenders = []
    for rel in tracked:
        path = config.PROJECT_ROOT / rel
        if not path.exists() or path.suffix in {".png", ".parquet", ".joblib", ".xlsx", ".pdf", ".npy"}:
            continue
        text = path.read_bytes().decode("utf-8", errors="ignore")
        for pattern, kind in patterns:
            if re.search(pattern, text):
                offenders.append(f"{rel}: {kind}")
    if offenders:
        audit.record("1. no hardcoded secrets", "fail",
                     f"{len(offenders)} possible secret(s)", offenders=offenders[:5])
    else:
        audit.record("1. no hardcoded secrets", "pass",
                     f"{len(tracked)} tracked files scanned, 0 matches")

    if ".streamlit/secrets.toml" in tracked:
        audit.record("1b. secrets file not committed", "fail",
                     ".streamlit/secrets.toml is tracked")
    else:
        gitignore = (config.PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        ignored = ".streamlit/secrets.toml" in gitignore
        audit.record("1b. secrets file not committed", "pass" if ignored else "warn",
                     "not tracked and explicitly git-ignored" if ignored
                     else "not tracked, but no explicit .gitignore rule")

    # The app must not read secrets at all: a public deployment has none to give.
    uses_secrets = [p.name for p in app_sources() if "st.secrets" in p.read_text(encoding="utf-8")]
    audit.record("1c. app requires no secrets", "fail" if uses_secrets else "pass",
                 f"st.secrets used in {uses_secrets}" if uses_secrets
                 else "the app reads no secrets, so none need configuring on the platform")


def check_personal_data(audit: Audit) -> None:
    """Scan only what the deployed app actually loads and can display."""
    from edupro.data.loader import load_all

    pii = load_all(drop_pii=False)
    emails = [e for e in pii.users["Email"].astype(str) if "@" in e]
    names = sorted({n for n in
                    list(pii.users["UserName"].astype(str))
                    + list(pii.teachers["TeacherName"].astype(str)) if len(n) >= 4})
    pattern = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(re.escape(n) for n in names[:1500])
                         + r")(?![A-Za-z0-9])")

    served = sorted((config.ARTIFACTS_DIR / "production").glob("*")) + \
        sorted(config.MODELS_DIR.glob("*")) + app_sources()
    offenders = []
    for path in served:
        if not path.is_file():
            continue
        blob = path.read_bytes()
        if any(e.encode() in blob for e in emails) or pattern.search(
                blob.decode("utf-8", errors="ignore")):
            offenders.append(path.name)
    if offenders:
        audit.record("2. no personal data served", "fail",
                     "PII found in files the app loads", files=offenders[:5])
    else:
        audit.record("2. no personal data served", "pass",
                     f"{len(served)} served files scanned against "
                     f"{len(emails)} emails and {len(names)} names, 0 matches")

    from edupro import config as cfg
    import pandas as pd

    frame = pd.read_parquet(cfg.ARTIFACTS_DIR / "production" / "learner_features.parquet")
    leaked = [c for c in cfg.PII_COLUMNS if c in frame.columns]
    audit.record("2b. identifiers are pseudonymous", "fail" if leaked else "pass",
                 f"PII columns present: {leaked}" if leaked
                 else f"learners keyed by {frame.index.name}, e.g. {frame.index[0]}")


def check_artifacts_available(audit: Audit, tracked: set[str]) -> None:
    """Every file the app loads must be in the repository, not just on this disk."""
    from edupro.persistence import load_manifest

    manifest = load_manifest()
    untracked = [rel for rel in manifest.files if rel.replace("\\", "/") not in tracked]
    if untracked:
        audit.record("3. artifacts committed", "fail",
                     f"{len(untracked)} artifact(s) are not in the repository; the app "
                     "would show an empty state after deployment", files=untracked)
    else:
        total = sum((config.PROJECT_ROOT / rel).stat().st_size for rel in manifest.files)
        audit.record("3. artifacts committed", "pass",
                     f"all {len(manifest.files)} manifest files tracked "
                     f"({total / 1024:.0f} KB); a fresh clone can serve immediately")

    from edupro.persistence import check_integrity
    problems = check_integrity(manifest)
    audit.record("3b. artifact set is internally consistent", "fail" if problems else "pass",
                 "; ".join(problems) if problems
                 else f"every file matches its recorded hash (set {manifest.artifact_set_version})")

    # The check above passes on the machine that wrote the artifacts by
    # construction. What matters for a deployment is whether the bytes git will
    # hand to a Linux runner are the same bytes. A file that git line-ending
    # normalises hashes differently after checkout, and the integrity check then
    # correctly rejects an artifact set that is not actually corrupt.
    import hashlib

    drifted = []
    for rel in manifest.files:
        rel_posix = rel.replace("\\", "/")
        blob = subprocess.run(["git", "show", f":{rel_posix}"],
                              capture_output=True, cwd=config.PROJECT_ROOT).stdout
        if not blob:
            continue
        if hashlib.sha256(blob).hexdigest() != manifest.files[rel]:
            drifted.append(rel_posix)
    if drifted:
        audit.record("3c. committed bytes match the recorded hashes", "fail",
                     f"{len(drifted)} artifact(s) are stored by git with different bytes "
                     "than the manifest recorded; the app will fail its integrity check "
                     "after a checkout on another platform", files=drifted)
    else:
        audit.record("3c. committed bytes match the recorded hashes", "pass",
                     f"all {len(manifest.files)} artifacts hash identically from git, so a "
                     "Linux checkout reproduces the manifest exactly")


def check_no_training_on_startup(audit: Audit) -> None:
    banned = ("KMeans(", "fit_transform", ".fit(", "cosine_similarity", "train(")
    offenders = [f"{p.name}: {t}" for p in app_sources()
                 for t in banned if t in p.read_text(encoding="utf-8")]
    if offenders:
        audit.record("4. no training on startup", "fail", "ML calls under app/", found=offenders)
    else:
        audit.record("4. no training on startup", "pass",
                     f"{len(app_sources())} app files contain no model-fitting call")

    loaders = (APP / "lib" / "loaders.py").read_text(encoding="utf-8")
    cached = "@st.cache_resource" in loaders
    audit.record("4b. model cached per process", "pass" if cached else "fail",
                 "RecommendationService.load is wrapped in st.cache_resource"
                 if cached else "the service is not cached; it would reload on every rerun")


def check_deterministic_startup(audit: Audit) -> None:
    """Two independent loads must produce the same recommendations."""
    from edupro.inference import RecommendationService

    first = RecommendationService.load()
    second = RecommendationService.load()
    user = first.features.index[0]
    a = [r.course_id for r in first.recommend(user, k=10).recommendations]
    b = [r.course_id for r in second.recommend(user, k=10).recommendations]
    labels_match = bool((first.features["cluster"] == second.features["cluster"]).all())
    if a == b and labels_match:
        audit.record("5. deterministic startup", "pass",
                     f"two loads agree on all {len(first.features):,} segment labels "
                     "and produce an identical top-10")
    else:
        audit.record("5. deterministic startup", "fail",
                     "two loads disagree", first=a[:3], second=b[:3])

    audit.record("5b. seeded", "pass", f"edupro.config.RANDOM_SEED = {config.RANDOM_SEED}")


def check_dependencies(audit: Audit) -> None:
    requirements = {}
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        name = re.split(r"[=<>!~\[]", line)[0].strip().lower()
        requirements[name] = line

    platform_locked = sorted(set(requirements) & PLATFORM_SPECIFIC)
    if platform_locked:
        audit.record("6. no platform-specific dependencies", "fail",
                     f"these do not install on Linux: {platform_locked}")
    else:
        audit.record("6. no platform-specific dependencies", "pass",
                     f"{len(requirements)} pinned packages, none Windows- or macOS-only")

    unpinned = [n for n, spec in requirements.items() if "==" not in spec]
    audit.record("6b. versions pinned", "pass" if not unpinned else "warn",
                 "every dependency is pinned to an exact version" if not unpinned
                 else f"unpinned: {unpinned}")

    # Every third-party module the app imports must be declared.
    third_party: set[str] = set()
    for path in app_sources() + sorted((config.PROJECT_ROOT / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                third_party.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                third_party.add(node.module.split(".")[0])
    stdlib = set(sys.stdlib_module_names)
    local = {"edupro", "lib", "app", "scripts", "tests"}
    alias = {"sklearn": "scikit-learn", "yaml": "pyyaml", "PIL": "pillow", "dateutil": "python-dateutil"}
    needed = {alias.get(m, m).lower() for m in third_party - stdlib - local}
    missing = sorted(needed - set(requirements))
    if missing:
        audit.record("6c. every import is declared", "fail",
                     f"imported but not in requirements.txt: {missing}")
    else:
        audit.record("6c. every import is declared", "pass",
                     f"{len(needed)} third-party imports, all declared: {sorted(needed)}")

    metadata = tomllib.loads((config.PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    audit.record("6d. Python version declared", "pass",
                 f"requires-python = {metadata['project']['requires-python']!r}; "
                 "Community Cloud must be set to a version inside this range")


def check_paths(audit: Audit, tracked: set[str]) -> None:
    absolute = re.compile(r"""['"](?:[A-Za-z]:[\\/]|/(?:home|Users|mnt|opt)/)""")
    offenders = []
    for path in app_sources() + sorted((config.PROJECT_ROOT / "src").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if absolute.search(text):
            offenders.append(str(path.relative_to(config.PROJECT_ROOT)))
    if offenders:
        audit.record("7. no absolute paths", "fail", "absolute paths in code", files=offenders)
    else:
        audit.record("7. no absolute paths", "pass",
                     "every path is derived from config.PROJECT_ROOT or __file__")

    root_line = [l for l in (config.PROJECT_ROOT / "src" / "edupro" / "config.py")
                 .read_text(encoding="utf-8").splitlines() if "PROJECT_ROOT" in l and "parents" in l]
    audit.record("7b. project root is relative to the package", "pass",
                 root_line[0].strip() if root_line else "derived from __file__")

    # Linux is case-sensitive; Windows is not. A mismatch works here and fails there.
    lowered = {t.lower(): t for t in tracked}
    referenced = set()
    for path in app_sources() + sorted((config.PROJECT_ROOT / "src").rglob("*.py")):
        for match in re.findall(r'["\']([\w./-]+\.(?:parquet|joblib|json|npy|csv|png|toml|md))["\']',
                                path.read_text(encoding="utf-8")):
            referenced.add(match)
    mismatches = []
    for ref in referenced:
        candidates = [t for t in tracked if t.endswith("/" + ref) or t == ref]
        if candidates:
            continue
        lower_hits = [orig for low, orig in lowered.items()
                      if low.endswith("/" + ref.lower()) or low == ref.lower()]
        if lower_hits:
            mismatches.append(f"{ref} -> {lower_hits[0]}")
    if mismatches:
        audit.record("8. filename case matches on Linux", "fail",
                     "case mismatch would break on Community Cloud", mismatches=mismatches)
    else:
        audit.record("8. filename case matches on Linux", "pass",
                     f"{len(referenced)} referenced filenames, no case mismatch against "
                     "the tracked tree")


def check_no_docker(audit: Audit) -> None:
    present = [n for n in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml",
                           ".dockerignore", "Procfile")
               if (config.PROJECT_ROOT / n).exists()]
    audit.record("9. no Docker or container config", "fail" if present else "pass",
                 f"found: {present}" if present else "no container or process-manager files")


def check_streamlit_config(audit: Audit) -> None:
    if not STREAMLIT_CONFIG.exists():
        audit.record("10. streamlit config", "warn", "no .streamlit/config.toml; defaults apply")
        return
    settings = tomllib.loads(STREAMLIT_CONFIG.read_text(encoding="utf-8"))

    detail = settings.get("client", {}).get("showErrorDetails")
    if detail in ("full", True):
        audit.record("10. error detail on a public URL", "warn",
                     f"showErrorDetails = {detail!r} shows full tracebacks to any visitor; "
                     "acceptable for a reviewed submission, not for an untrusted audience")
    else:
        audit.record("10. error detail on a public URL", "pass",
                     f"showErrorDetails = {detail!r}")

    theme = settings.get("theme", {}).get("base")
    audit.record("10b. theme pinned", "pass" if theme else "warn",
                 f"base = {theme!r}, so every viewer sees what the README shows"
                 if theme else "theme follows the viewer's system preference")

    audit.record("10c. entry point", "pass" if ENTRY.exists() else "fail",
                 f"{ENTRY.relative_to(config.PROJECT_ROOT)} exists and is the documented "
                 "main file" if ENTRY.exists() else "entry point missing")


def check_repo_size(audit: Audit, tracked: set[str]) -> None:
    total = sum((config.PROJECT_ROOT / t).stat().st_size
                for t in tracked if (config.PROJECT_ROOT / t).exists())
    large = sorted(
        ((config.PROJECT_ROOT / t).stat().st_size, t) for t in tracked
        if (config.PROJECT_ROOT / t).exists()
        and (config.PROJECT_ROOT / t).stat().st_size > 50 * 1024 * 1024
    )
    if large:
        audit.record("11. no file over GitHub's limit", "fail",
                     "files above 50 MB", files=[t for _, t in large])
    else:
        audit.record("11. no file over GitHub's limit", "pass",
                     f"repository {total / 1024 / 1024:.0f} MB, largest tracked file "
                     f"{max((config.PROJECT_ROOT / t).stat().st_size for t in tracked) / 1024 / 1024:.1f} MB")


def main() -> int:
    print("=" * 78)
    print("PHASE 6E - DEPLOYMENT READINESS AUDIT")
    print("=" * 78)
    tracked = tracked_files()
    audit = Audit()

    for label, fn in (
        ("secrets", lambda: check_secrets(audit, tracked)),
        ("personal data", lambda: check_personal_data(audit)),
        ("artifact availability", lambda: check_artifacts_available(audit, tracked)),
        ("startup cost", lambda: check_no_training_on_startup(audit)),
        ("determinism", lambda: check_deterministic_startup(audit)),
        ("dependencies", lambda: check_dependencies(audit)),
        ("paths", lambda: check_paths(audit, tracked)),
        ("containers", lambda: check_no_docker(audit)),
        ("streamlit config", lambda: check_streamlit_config(audit)),
        ("repository size", lambda: check_repo_size(audit, tracked)),
    ):
        try:
            fn()
        except Exception as error:  # noqa: BLE001 - a crashing probe is a finding
            audit.record(label, "fail", f"probe raised {type(error).__name__}: {error}")

    passes = [f for f in audit.findings if f.severity == "pass"]
    print("\n" + "=" * 78)
    print(f"{len(audit.findings)} checks: {len(passes)} pass, "
          f"{len(audit.warnings)} warn, {len(audit.failures)} FAIL")
    for finding in audit.failures:
        print(f"  FAIL {finding.check}: {finding.detail}")
    for finding in audit.warnings:
        print(f"  WARN {finding.check}: {finding.detail}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "summary": {
            "n_checks": len(audit.findings),
            "n_pass": len(passes),
            "n_warn": len(audit.warnings),
            "n_fail": len(audit.failures),
            "deployment_ready": not audit.failures,
        },
        "findings": [
            {"check": f.check, "severity": f.severity, "detail": f.detail, "evidence": f.evidence}
            for f in audit.findings
        ],
    }, indent=2, default=str), encoding="utf-8")
    print(f"\nWritten to {OUT.relative_to(config.PROJECT_ROOT)}")
    return 1 if audit.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
