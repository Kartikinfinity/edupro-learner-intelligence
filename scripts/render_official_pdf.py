"""Render the official documentation PDF to page images so it can be read.

The official Unified Mentor PDF is image-based: ``pypdf`` extracts zero
characters from all six pages because there is no embedded text layer. To read,
quote or re-verify the requirements, the pages must be rasterised.

This script exists so that the transcript in
``references/official/OFFICIAL_REQUIREMENTS_TRANSCRIPT.md`` is reproducible and
auditable rather than something a reader has to take on trust.

The PDF is opened read-only; its SHA-256 is verified before and after rendering.

Usage
-----
    python scripts/render_official_pdf.py [--dpi 140] [--out <directory>]

Requires the dev extras (``pip install -r requirements-dev.txt``).
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pymupdf

from edupro import config


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dpi", type=int, default=140, help="render resolution (default: 140)")
    parser.add_argument(
        "--out",
        type=Path,
        default=config.ARTIFACTS_DIR / "official_pdf_pages",
        help="output directory for the rendered PNG pages",
    )
    args = parser.parse_args()

    source = config.OFFICIAL_DOCUMENTATION
    if not source.is_file():
        raise SystemExit(f"Official documentation not found: {source}")

    checksum_before = sha256(source)
    if checksum_before != config.OFFICIAL_DOCUMENTATION_SHA256:
        raise SystemExit(
            "Official documentation checksum does not match the recorded value.\n"
            f"  expected {config.OFFICIAL_DOCUMENTATION_SHA256}\n"
            f"  found    {checksum_before}"
        )

    args.out.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open(source)
    try:
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(dpi=args.dpi)
            destination = args.out / f"page{index:02d}.png"
            pixmap.save(str(destination))
            print(f"{destination.name}  {pixmap.width}x{pixmap.height}px  {destination.stat().st_size:,} bytes")
    finally:
        document.close()

    if sha256(source) != checksum_before:
        raise RuntimeError("Source PDF changed during rendering - immutability violated.")

    print(f"\n{len(list(args.out.glob('page*.png')))} pages rendered to {args.out}")


if __name__ == "__main__":
    main()
