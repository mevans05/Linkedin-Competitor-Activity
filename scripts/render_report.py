#!/usr/bin/env python3
"""Render the quantitative sections of the weekly report from analyze_wow.py
and diff_new_posts.py output, leaving clearly marked placeholders for the
qualitative analysis to be written afterward (see the weekly-linkedin-audit
skill).

Usage:
    python scripts/render_report.py --week 2026-09-04
"""
import argparse
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c

METRIC_LABELS = {
    "new_followers": "New followers",
    "reactions_total": "Reactions",
    "comments_total": "Comments",
    "posts_count": "Posts published",
}


def fmt_num(val, pct=False, signed=False):
    if val is None:
        return "—"
    if pct:
        return f"{val:+.1f}%" if signed else f"{val:.1f}%"
    if isinstance(val, float) and val.is_integer():
        val = int(val)
    if signed and isinstance(val, (int, float)):
        return f"{val:+,.0f}" if not isinstance(val, int) else f"{val:+,d}"
    return f"{val:,}" if isinstance(val, int) else f"{val:,.1f}"


def _clean(val):
    """DataFrames built from heterogeneous dicts (e.g. the docx post parser,
    where not every post has every field) fill absent fields with NaN rather
    than None — normalize those back to None so downstream checks don't have
    to special-case float('nan')."""
    if isinstance(val, float) and math.isnan(val):
        return None
    return val


def excerpt(text, length=220):
    if not text:
        return "_(no caption text captured)_"
    text = str(text).replace("\n", " ").strip()
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def fmt_cell(current, pct_change=None, abs_change=None):
    if current is None:
        return "—"
    base = fmt_num(current)
    if pct_change is not None:
        return f"{base} ({fmt_num(pct_change, pct=True, signed=True)})"
    if abs_change is not None:
        return f"{base} ({fmt_num(abs_change, signed=True)})"
    return base


def build_company_rows(companies, competitors):
    rows = []
    order = [e["key"] for e in competitors["company_pages"]]
    for key in order:
        comp = companies.get(key)
        name = c.company_display_name(competitors, key)
        if comp is None:
            rows.append({"name": name, "new_followers": "—", "reactions": "—", "comments": "—", "posts_count": "—"})
            continue
        m = comp["metrics"]
        rows.append({
            "name": name,
            "new_followers": fmt_cell(m["new_followers"]["current"], pct_change=m["new_followers"]["pct_change"]),
            "reactions": fmt_cell(m["reactions_total"]["current"], pct_change=m["reactions_total"]["pct_change"]),
            "comments": fmt_cell(m["comments_total"]["current"], pct_change=m["comments_total"]["pct_change"]),
            "posts_count": fmt_cell(m["posts_count"]["current"], abs_change=m["posts_count"]["abs_change"]),
        })
    return rows


def build_flagged(flagged_changes):
    out = []
    for f in flagged_changes:
        metric = f["metric"]
        prior_fmt = fmt_num(f["prior"])
        current_fmt = fmt_num(f["current"])
        if metric != "posts_count" and f["pct_change"] is not None:
            change_fmt = fmt_num(f["pct_change"], pct=True, signed=True) + " WoW"
        else:
            change_fmt = fmt_num(f["abs_change"], signed=True) + " WoW"
        out.append({
            "company_name": f["company_name"],
            "metric_label": METRIC_LABELS.get(metric, metric),
            "prior_fmt": prior_fmt,
            "current_fmt": current_fmt,
            "change_fmt": change_fmt,
        })
    return out


def build_post_groups(bucket_posts, entries, name_field, key_field="key", company_field=None, competitors=None):
    groups = []
    for entry in entries:
        key = entry[key_field]
        posts = bucket_posts.get(key, [])
        posts_sorted = sorted(posts, key=lambda p: _clean(p.get("date_posted")) or "", reverse=True)
        formatted = []
        for p in posts_sorted:
            p = {k: _clean(v) for k, v in p.items()}
            likes, comments, shares = p.get("likes"), p.get("comments"), p.get("shares")
            has_engagement = any(v not in (None, "") for v in (likes, comments, shares))
            cta = (p.get("cta") or "").strip() or None
            formatted.append({
                "date": p.get("date_posted") or None,
                "type": (p.get("post_type") or "unknown").title(),
                "excerpt": excerpt(p.get("content_text")),
                "has_engagement": has_engagement,
                "likes": int(likes) if likes not in (None, "") else 0,
                "comments": int(comments) if comments not in (None, "") else 0,
                "shares": int(shares) if shares not in (None, "") else 0,
                "cta": cta,
                "url": p.get("url"),
            })
        group = {"name": entry[name_field], "count": len(formatted), "posts": formatted}
        if company_field and entry.get(company_field) and competitors:
            group["company"] = c.company_display_name(competitors, entry[company_field])
        groups.append(group)
    return groups


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", required=True, help="Week-ending date, YYYY-MM-DD")
    args = parser.parse_args()
    week = args.week

    competitors = c.load_competitors()

    wow_path = c.PROCESSED_DIR / f"wow_analysis_{week}.json"
    posts_path = c.PROCESSED_DIR / f"new_posts_{week}.json"
    wow = c.load_json(wow_path, None)
    posts = c.load_json(posts_path, {"new_posts": {"company_pages": {}, "leadership_profiles": {}}, "total_new_posts": 0})

    if wow is None:
        print(f"No WoW analysis found at {wow_path}. Run analyze_wow.py --week {week} first.")
        return

    company_rows = build_company_rows(wow["companies"], competitors)
    flagged_changes = build_flagged(wow["flagged_changes"])

    company_post_groups = build_post_groups(
        posts["new_posts"]["company_pages"], competitors["company_pages"], "linkedin_name",
    )
    leader_post_groups = build_post_groups(
        posts["new_posts"]["leadership_profiles"], competitors["leadership_profiles"], "full_name",
        company_field="company_key", competitors=competitors,
    )

    env = Environment(loader=FileSystemLoader(str(c.ROOT / "templates")), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template("report.md.j2")
    rendered = template.render(
        week_ending=week,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        n_companies=len(competitors["company_pages"]),
        n_leaders=len(competitors["leadership_profiles"]),
        total_new_posts=posts.get("total_new_posts", 0),
        company_rows=company_rows,
        flagged_changes=flagged_changes,
        company_post_groups=company_post_groups,
        leader_post_groups=leader_post_groups,
    )

    c.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = c.REPORTS_DIR / f"{week}.md"
    out_path.write_text(rendered)
    print(f"Rendered report skeleton to {out_path}. Fill in the <!-- QUALITATIVE:* --> sections next.")


if __name__ == "__main__":
    main()
