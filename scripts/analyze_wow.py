#!/usr/bin/env python3
"""Compute week-over-week analytics deltas for tracked competitor Company Pages.

Loads data/processed/analytics_history.csv, compares the target week's
snapshot against each company's immediately preceding snapshot, computes
absolute and percent change per metric, and flags moves that clear the
thresholds in config/thresholds.yaml.

Usage:
    python scripts/analyze_wow.py --week 2026-09-04
    (--week defaults to the most recent date present in the history file)
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c

PCT_METRICS = ("followers_total", "engagement_total", "engagement_rate")
ABS_METRICS = ("posts_count",)


def pct_change(prior, current):
    if prior in (None, 0) or pd.isna(prior):
        return None
    return (current - prior) / abs(prior) * 100


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", default=None, help="Week-ending date, YYYY-MM-DD. Defaults to latest date in history.")
    args = parser.parse_args()

    history_path = c.PROCESSED_DIR / "analytics_history.csv"
    if not history_path.exists():
        print(f"No analytics history found at {history_path}. Run ingest_analytics.py first.")
        return

    history = pd.read_csv(history_path, parse_dates=["date"])
    if history.empty:
        print("Analytics history is empty.")
        return

    target_date = pd.to_datetime(args.week) if args.week else history["date"].max()
    competitors = c.load_competitors()
    thresholds = c.load_thresholds()

    companies = {}
    flagged_changes = []

    for entry in competitors["company_pages"]:
        key = entry["key"]
        rows = history[history["company_key"] == key].sort_values("date")
        current_rows = rows[rows["date"] == target_date]
        if current_rows.empty:
            continue
        current = current_rows.iloc[-1]

        prior_rows = rows[rows["date"] < target_date]
        prior = prior_rows.iloc[-1] if not prior_rows.empty else None

        metrics = {}
        for metric in (*PCT_METRICS, *ABS_METRICS):
            cur_val = current.get(metric)
            prior_val = prior.get(metric) if prior is not None else None
            if pd.isna(cur_val):
                cur_val = None
            if prior_val is not None and pd.isna(prior_val):
                prior_val = None

            abs_change = None
            pct = None
            flagged = False
            if cur_val is not None and prior_val is not None:
                abs_change = cur_val - prior_val
                if metric in PCT_METRICS:
                    pct = pct_change(prior_val, cur_val)
                    threshold = thresholds.get(metric, {}).get("pct_change_flag")
                    if threshold is not None and pct is not None and abs(pct) >= threshold:
                        flagged = True
                else:
                    threshold = thresholds.get(metric, {}).get("abs_change_flag")
                    if threshold is not None and abs(abs_change) >= threshold:
                        flagged = True

            metrics[metric] = {
                "prior": prior_val,
                "current": cur_val,
                "abs_change": abs_change,
                "pct_change": pct,
                "flagged": flagged,
            }
            if flagged:
                flagged_changes.append({
                    "company_key": key,
                    "company_name": entry["linkedin_name"],
                    "metric": metric,
                    "prior": prior_val,
                    "current": cur_val,
                    "abs_change": abs_change,
                    "pct_change": pct,
                })

        companies[key] = {
            "company_name": entry["linkedin_name"],
            "prior_date": prior["date"].date().isoformat() if prior is not None else None,
            "metrics": metrics,
        }

    flagged_changes.sort(
        key=lambda x: abs(x["pct_change"]) if x["pct_change"] is not None else abs(x["abs_change"] or 0),
        reverse=True,
    )

    output = {
        "week_ending": target_date.date().isoformat(),
        "companies": companies,
        "flagged_changes": flagged_changes,
    }

    output_path = c.PROCESSED_DIR / f"wow_analysis_{target_date.date().isoformat()}.json"
    c.save_json(output_path, output)
    print(f"Analyzed {len(companies)} compan(ies), flagged {len(flagged_changes)} significant change(s). Wrote {output_path}")


if __name__ == "__main__":
    main()
