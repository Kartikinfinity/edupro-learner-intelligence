"""Phase 0 - read-only inventory of the official source materials.

Purpose
-------
Confirm that the authoritative dataset is present, readable and structurally
sound, and record its shape for the project manifest. This script is
deliberately *structural only*: it reports sheet names, row/column counts,
column headers and inferred dtypes. It computes no distributions, no summary
statistics and no derived findings -- that is Phase 2 (dataset audit / EDA).

Immutability guarantee
----------------------
The workbook is opened read-only and its SHA-256 is verified before and after
the inspection, so this script can never be the cause of a change to the raw
data (CLAUDE.md section 8).

Usage
-----
    python scripts/inspect_sources.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_WORKBOOK = ROOT / "data" / "raw" / "EduPro Online Platform.xlsx"
OFFICIAL_PDF = ROOT / "references" / "official" / "project offical detail.pdf"
OUTPUT = ROOT / "artifacts" / "phase0_source_inventory.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_workbook(path: Path) -> dict:
    """Return the structural inventory of every sheet in the workbook."""
    checksum_before = sha256(path)

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet_names = list(workbook.sheetnames)
    dimensions = {
        name: {
            "openpyxl_max_row": workbook[name].max_row,
            "openpyxl_max_column": workbook[name].max_column,
        }
        for name in sheet_names
    }
    workbook.close()

    sheets = []
    for name in sheet_names:
        frame = pd.read_excel(path, sheet_name=name, engine="openpyxl")
        sheets.append(
            {
                "sheet_name": name,
                "n_rows": int(frame.shape[0]),
                "n_columns": int(frame.shape[1]),
                "columns": [
                    {
                        "name": str(column),
                        "pandas_dtype": str(frame[column].dtype),
                        "n_missing": int(frame[column].isna().sum()),
                        "n_unique": int(frame[column].nunique(dropna=True)),
                    }
                    for column in frame.columns
                ],
                **dimensions[name],
            }
        )

    checksum_after = sha256(path)
    if checksum_before != checksum_after:
        raise RuntimeError(
            "Raw workbook checksum changed during inspection - immutability violated."
        )

    return {
        "file": path.name,
        "sha256": checksum_after,
        "size_bytes": path.stat().st_size,
        "n_sheets": len(sheet_names),
        "sheet_names": sheet_names,
        "sheets": sheets,
    }


def main() -> None:
    missing = [p for p in (RAW_WORKBOOK, OFFICIAL_PDF) if not p.exists()]
    if missing:
        raise SystemExit(
            "Missing required source material(s):\n"
            + "\n".join(f"  - {p}" for p in missing)
        )

    inventory = {
        "official_documentation": {
            "file": OFFICIAL_PDF.name,
            "sha256": sha256(OFFICIAL_PDF),
            "size_bytes": OFFICIAL_PDF.stat().st_size,
        },
        "dataset": inspect_workbook(RAW_WORKBOOK),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(inventory, indent=2), encoding="utf-8")

    dataset = inventory["dataset"]
    print(f"Workbook : {dataset['file']}")
    print(f"SHA-256  : {dataset['sha256']}")
    print(f"Sheets   : {dataset['n_sheets']} -> {dataset['sheet_names']}")
    for sheet in dataset["sheets"]:
        print(f"\n[{sheet['sheet_name']}]  rows={sheet['n_rows']}  cols={sheet['n_columns']}")
        for column in sheet["columns"]:
            print(
                f"    {column['name']:<28} {column['pandas_dtype']:<16}"
                f" missing={column['n_missing']:<6} unique={column['n_unique']}"
            )
    print(f"\nInventory written to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
