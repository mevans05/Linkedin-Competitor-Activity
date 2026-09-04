#!/usr/bin/env python3
"""Index net-new LinkedIn posts for tracked Company Pages and leaders.

Reads every not-yet-ingested file in data/raw/posts/, normalizes columns via
config/column_mappings.yaml, resolves each row's author to a company or
leader key from config/competitors.yaml, and diffs post ids against
data/state/seen_posts.json to find posts we haven't reported before.

Writes:
  - data/processed/new_posts_<week>.json  (this run's net-new posts, grouped
    by company_pages / leadership_profiles)
  - data/processed/posts_history.csv      (full running log of every post
    ever ingested, for later reference)
  - data/state/seen_posts.json            (updated with this run's post ids)

Usage:
    python scripts/diff_new_posts.py --week 2026-09-04
    (--week defaults to today's date if omitted)
"""
import argparse
import hashlib
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c

POST_FIELDS = (
    "post_id", "url", "date_posted", "post_type", "content_text",
    "likes", "comments", "shares", "reactions_total", "hashtags",
)


def make_post_id(row):
    if row.get("post_id"):
        return str(row["post_id"])
    if row.get("url"):
        return str(row["url"])
    basis = f"{row.get('date_posted')}|{row.get('content_text', '')[:200]}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def resolve_author(row, company_lookup, leader_lookup):
    """Return (bucket, key) where bucket is 'company_pages' or
    'leadership_profiles', or (None, None) if unresolved."""
    name = str(row.get("author_name", "")).strip().lower()
    author_type = str(row.get("author_type", "")).strip().lower()

    if author_type in ("leader", "leadership", "profile", "person"):
        return "leadership_profiles", leader_lookup.get(name)
    if author_type in ("company", "page", "organization"):
        return "company_pages", company_lookup.get(name)

    # No explicit type column — try both lookups.
    if name in company_lookup:
        return "company_pages", company_lookup[name]
    if name in leader_lookup:
        return "leadership_profiles", leader_lookup[name]
    return None, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", default=date.today().isoformat(), help="Week-ending date, YYYY-MM-DD")
    args = parser.parse_args()

    competitors = c.load_competitors()
    mappings = c.load_column_mappings()["posts"]
    company_lookup = c.build_company_lookup(competitors)
    leader_lookup = c.build_leader_lookup(competitors)

    manifest_path = c.STATE_DIR / "ingested_posts_files.json"
    ingested_files = set(c.load_json(manifest_path, []))
    seen_path = c.STATE_DIR / "seen_posts.json"
    seen = c.load_json(seen_path, {})  # {"company:accenture": ["id1", ...], "leader:brad-jackson": [...]}

    raw_dir = c.RAW_DIR / "posts"
    raw_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in raw_dir.glob("*") if p.suffix.lower() in (".csv", ".xlsx", ".xls"))
    new_files = [p for p in files if p.name not in ingested_files]

    if not new_files:
        print("No new post export files to ingest.")
        return

    history_path = c.PROCESSED_DIR / "posts_history.csv"
    if history_path.exists():
        history = pd.read_csv(history_path)
    else:
        history = pd.DataFrame(columns=["state_key", "bucket", "entity_key", *POST_FIELDS])

    new_posts = {"company_pages": {}, "leadership_profiles": {}}
    all_rows_for_history = []
    unresolved = set()

    for path in new_files:
        df = c.normalize_columns(c.read_table(path), mappings)
        for _, row in df.iterrows():
            row = row.to_dict()
            bucket, key = resolve_author(row, company_lookup, leader_lookup)
            if key is None:
                unresolved.add(str(row.get("author_name")))
                continue

            post_id = make_post_id(row)
            state_key = f"{'company' if bucket == 'company_pages' else 'leader'}:{key}"
            record = {field: row.get(field) for field in POST_FIELDS}
            record["post_id"] = post_id

            all_rows_for_history.append({"state_key": state_key, "bucket": bucket, "entity_key": key, **record})

            seen_ids = set(seen.get(state_key, []))
            if post_id not in seen_ids:
                new_posts[bucket].setdefault(key, []).append(record)
                seen_ids.add(post_id)
                seen[state_key] = sorted(seen_ids)

        ingested_files.add(path.name)

    if unresolved:
        print(
            f"WARNING: {len(unresolved)} post row(s) had an author not found in "
            f"config/competitors.yaml: {sorted(unresolved)}. Add them to competitors.yaml "
            f"or fix the export."
        )

    if all_rows_for_history:
        new_hist_df = pd.DataFrame(all_rows_for_history)
        combined = pd.concat([history, new_hist_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["state_key", "post_id"], keep="last")
        c.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        combined.to_csv(history_path, index=False)

    total_new = sum(len(v) for v in new_posts["company_pages"].values()) + \
        sum(len(v) for v in new_posts["leadership_profiles"].values())

    output_path = c.PROCESSED_DIR / f"new_posts_{args.week}.json"
    c.save_json(output_path, {"week_ending": args.week, "new_posts": new_posts, "total_new_posts": total_new})

    c.save_json(seen_path, seen)
    c.save_json(manifest_path, sorted(ingested_files))

    print(f"Found {total_new} net-new post(s) across {len(new_files)} file(s). Wrote {output_path}")


if __name__ == "__main__":
    main()
