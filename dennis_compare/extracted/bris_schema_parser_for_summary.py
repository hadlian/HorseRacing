#!/usr/bin/env python3
"""
BRIS/DRF raw CSV schema parser for the BRIS Summary Handicap System.

Purpose
-------
Converts a raw BRIS single-file/DRF comma-delimited export with many unnamed
fields into the compact CSV expected by bris_summary_handicap_system_code.py.

Default mapping is tuned to the CDX0529 raw BRIS/DRF export layout seen in this
project. You can override any field by passing a simple schema JSON file.

Expected output columns:
Race, Horse Number, Horse Name, Morning Line, Avg Speed, Distance Speed,
Best Speed, Prime Power, Avg Class, Jockey Rating, Trainer Rating, Earnings,
Early Pace, Late Pace, BRIS Top Pick

Usage examples
--------------
python bris_schema_parser_for_summary.py CDX0529.csv --output-csv CDX0529_summary_input.csv

python bris_schema_parser_for_summary.py CDX0529.DRF --output-csv CDX0529_summary_input.csv \
  --run-summary bris_summary_handicap_system_code.py --summary-output CDX0529_summary_output.txt

Schema override example JSON
----------------------------
{
  "Race": 2,
  "Horse Number": 42,
  "Horse Name": 44,
  "Morning Line": 43,
  "Trainer Rating": 28,
  "Jockey Rating": 34,
  "Earnings": 100,
  "Prime Power": 250,
  "Avg Class": 223,
  "Speed Ratings": [213, 214, 215, 216, 217],
  "Early Pace Candidates": [218, 219],
  "Late Pace Candidates": [220, 221]
}
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


# Zero-based raw CSV field numbers. These are BRIS export positions after pandas
# reads the no-header comma-delimited file.
DEFAULT_SCHEMA: Dict[str, Any] = {
    "Race": 2,
    "Program Number Fallback": 3,
    "Horse Number": 42,
    "Horse Name": 44,
    "Morning Line": 43,
    "Trainer Rating": 28,
    "Jockey Rating": 34,
    "Earnings": 100,
    "Prime Power": 250,
    "Avg Class": 223,
    # Recent speed-rating fields. The parser uses these to compute Avg Speed,
    # Distance Speed, and Best Speed when direct fields are not available.
    "Speed Ratings": [213, 214, 215, 216, 217],
    # Pace candidates. The parser takes the best available value from each set.
    "Early Pace Candidates": [218, 219],
    "Late Pace Candidates": [220, 221],
    # Race-level ordered horse-name list, used only as a fallback for top pick.
    "Entry Horse List": 16,
}

OUTPUT_COLUMNS = [
    "Race",
    "Horse Number",
    "Horse Name",
    "Morning Line",
    "Avg Speed",
    "Distance Speed",
    "Best Speed",
    "Prime Power",
    "Avg Class",
    "Jockey Rating",
    "Trainer Rating",
    "Earnings",
    "Early Pace",
    "Late Pace",
    "BRIS Top Pick",
]


def clean_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value).strip()


def clean_number(value: Any) -> Optional[float]:
    text = clean_text(value)
    if text == "":
        return None
    text = text.replace("$", "").replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def get_field(row: pd.Series, index: Any) -> Any:
    try:
        idx = int(index)
    except (TypeError, ValueError):
        return None
    if idx < 0 or idx >= len(row):
        return None
    return row.iloc[idx]


def first_number(row: pd.Series, indexes: Iterable[int]) -> Optional[float]:
    for idx in indexes:
        value = clean_number(get_field(row, idx))
        if value is not None:
            return value
    return None


def max_number(row: pd.Series, indexes: Iterable[int]) -> Optional[float]:
    values = [clean_number(get_field(row, idx)) for idx in indexes]
    values = [v for v in values if v is not None]
    return max(values) if values else None


def avg_number(row: pd.Series, indexes: Iterable[int]) -> Optional[float]:
    values = [clean_number(get_field(row, idx)) for idx in indexes]
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 2) if values else None


def format_number(value: Optional[float]) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return str(round(float(value), 2))


def load_schema(path: Optional[str]) -> Dict[str, Any]:
    schema = dict(DEFAULT_SCHEMA)
    if not path:
        return schema
    with open(path, "r", encoding="utf-8") as f:
        override = json.load(f)
    schema.update(override)
    return schema


def read_raw_file(path: str) -> pd.DataFrame:
    # BRIS raw files are comma-delimited with no header and many columns.
    return pd.read_csv(path, header=None, dtype=str, low_memory=False)


def derive_bris_top_pick(output_df: pd.DataFrame) -> pd.Series:
    """Mark the lowest morning-line horse in each race as a fallback top pick.

    BRIS Top Pick is not always directly present in the raw export. This fallback
    keeps the downstream summary script functional. If you later identify the
    exact BRIS top-pick field, add it to the schema and replace this logic.
    """
    flags = pd.Series(["" for _ in range(len(output_df))], index=output_df.index)
    for race, group in output_df.groupby("Race", sort=False):
        odds = pd.to_numeric(group["Morning Line"], errors="coerce")
        if odds.notna().any():
            flags.loc[odds.idxmin()] = "YES"
    return flags


def convert_raw_to_summary(input_file: str, output_csv: str, schema_file: Optional[str] = None) -> pd.DataFrame:
    schema = load_schema(schema_file)
    raw = read_raw_file(input_file)
    rows: List[Dict[str, Any]] = []

    for _, row in raw.iterrows():
        race = clean_text(get_field(row, schema["Race"]))
        horse_number = clean_text(get_field(row, schema.get("Horse Number")))
        if not horse_number:
            horse_number = clean_text(get_field(row, schema.get("Program Number Fallback")))
        horse_name = clean_text(get_field(row, schema["Horse Name"]))

        # Skip non-horse or malformed rows.
        if not race or not horse_number or not horse_name:
            continue

        speed_fields = schema.get("Speed Ratings", [])
        parsed = {
            "Race": race,
            "Horse Number": horse_number,
            "Horse Name": horse_name,
            "Morning Line": format_number(clean_number(get_field(row, schema["Morning Line"]))),
            "Avg Speed": format_number(avg_number(row, speed_fields)),
            "Distance Speed": format_number(first_number(row, speed_fields)),
            "Best Speed": format_number(max_number(row, speed_fields)),
            "Prime Power": format_number(clean_number(get_field(row, schema["Prime Power"]))),
            "Avg Class": format_number(clean_number(get_field(row, schema["Avg Class"]))),
            "Jockey Rating": format_number(clean_number(get_field(row, schema["Jockey Rating"]))),
            "Trainer Rating": format_number(clean_number(get_field(row, schema["Trainer Rating"]))),
            "Earnings": format_number(clean_number(get_field(row, schema["Earnings"]))),
            "Early Pace": format_number(max_number(row, schema.get("Early Pace Candidates", []))),
            "Late Pace": format_number(max_number(row, schema.get("Late Pace Candidates", []))),
            "BRIS Top Pick": "",
        }
        rows.append(parsed)

    output_df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    if output_df.empty:
        raise ValueError("No valid horse rows were parsed. Check the schema field numbers.")

    output_df["BRIS Top Pick"] = derive_bris_top_pick(output_df)
    output_df.to_csv(output_csv, index=False)
    return output_df


def run_summary_script(summary_script: str, csv_file: str, output_file: str) -> None:
    script_path = Path(summary_script)
    if not script_path.exists():
        raise FileNotFoundError(f"Summary script not found: {summary_script}")
    spec = importlib.util.spec_from_file_location("bris_summary_module", str(script_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load summary script: {summary_script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "run_bris_summary"):
        raise AttributeError("Summary script does not contain run_bris_summary(csv_file, output_file).")
    module.run_bris_summary(csv_file, output_file)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Convert raw BRIS/DRF CSV into BRIS Summary input CSV.")
    parser.add_argument("input_file", help="Raw BRIS/DRF CSV or .DRF comma-delimited file")
    parser.add_argument("--schema", help="Optional JSON schema override file", default=None)
    parser.add_argument("--output-csv", default="bris_summary_input.csv", help="Output summary input CSV")
    parser.add_argument("--run-summary", help="Path to bris_summary_handicap_system_code.py", default=None)
    parser.add_argument("--summary-output", default="bris_summary_output.txt", help="Summary text output file")
    args = parser.parse_args(argv)

    output_df = convert_raw_to_summary(args.input_file, args.output_csv, args.schema)
    print(f"Parsed {len(output_df)} horse rows into: {args.output_csv}")
    print(output_df.head(10).to_string(index=False))

    if args.run_summary:
        run_summary_script(args.run_summary, args.output_csv, args.summary_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
