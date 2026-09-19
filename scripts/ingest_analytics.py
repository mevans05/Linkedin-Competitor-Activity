#!/usr/bin/env python3
"""Ingest weekly LinkedIn competitor analytics snapshots.

Reads every not-yet-ingested file in data/raw/analytics/, normalizes columns
via config/column_mappings.yaml, resolves each row's company name to the
canonical `key` in config/competitors.yaml, and appends the rows to
data/processed/analytics_history.csv (deduped on company_key + date).

Usage:
    python scripts/ingest_analytics.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c

METRIC_FIELDS = (
    "new_followers",
    "posts_count",
    "comments_total",
    "comments_per_day",
    "reactions_total",
)


def main():
    competitors = c.load_competitors()
    mappings = c.load_column_mappings()["analytics"]
    lookup = c.build_company_lookup(competitors)

    manifest_path = c.STATE_DIR / "ingested_analytics_files.json"
    ingested = set(c.load_json(manifest_path, []))

    raw_dir = c.RAW_DIR / "analytics"
    raw_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in raw_dir.glob("*") if p.suffix.lower() in (".csv", ".xlsx", ".xls"))
    new_files = [p for p in files if p.name not in ingested]

    if not new_files:
        print("No new analytics files to ingest.")
        return

    history_path = c.PROCESSED_DIR / "analytics_history.csv"
    if history_path.exists():
        history = pd.read_csv(history_path, parse_dates=["date"])
    else:
        history = pd.DataFrame(columns=["date", "company_key", *METRIC_FIELDS])

    all_new_rows = []
    unmatched = set()
    for path in new_files:
        df = c.normalize_columns(c.read_table(path), mappings)

        if "date" not in df.columns:
            # The real Coefficient competitor table gives one period date for
            # the whole export, not a per-row column — fall back to the
            # filename (e.g. data/raw/analytics/2026-08-28.csv).
            filename_date = pd.to_datetime(path.stem, errors="coerce")
            if pd.isna(filename_date):
                filename_date = None
            if filename_date is not None:
                df["date"] = filename_date

        missing = [col for col in ("company", "date") if col not in df.columns]
        if missing:
            print(
                f"WARNING: {path.name} is missing required column(s) {missing} after mapping "
                f"(and no date could be parsed from the filename) — skipping file. "
                f"Found columns: {list(df.columns)}"
            )
            continue

        for _, row in df.iterrows():
            company_raw = str(row["company"]).strip()
            key = lookup.get(company_raw.lower())
            if key is None:
                unmatched.add(company_raw)
                continue
            record = {"date": pd.to_datetime(row["date"]).normalize(), "company_key": key}
            for field in METRIC_FIELDS:
                record[field] = row[field] if field in df.columns else None
            all_new_rows.append(record)
        ingested.add(path.name)

    if unmatched:
        print(
            f"WARNING: {len(unmatched)} row(s) had a company name not found in "
            f"config/competitors.yaml: {sorted(unmatched)}. Add them to competitors.yaml "
            f"or fix the export."
        )

    if all_new_rows:
        new_df = pd.DataFrame(all_new_rows)
        combined = pd.concat([history, new_df], ignore_index=True)
        combined["date"] = pd.to_datetime(combined["date"])
        combined = combined.drop_duplicates(subset=["company_key", "date"], keep="last")
        combined = combined.sort_values(["company_key", "date"])
        c.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        combined.to_csv(history_path, index=False)
        print(f"Ingested {len(all_new_rows)} row(s) from {len(new_files)} file(s) into {history_path}")
    else:
        print("No valid rows found in new files.")

    c.save_json(manifest_path, sorted(ingested))


if __name__ == "__main__":
    main()
