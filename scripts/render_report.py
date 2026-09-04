#!/usr/bin/env python3
"""Render the quantitative sections of the weekly report from analyze_wow.py
and diff_new_posts.py output, leaving clearly marked placeholders for the
qualitative analysis to be written afterward (see the weekly-linkedin-audit
skill).

Usage:
    python scripts/render_report.py --week 2026-09-04
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c

METRIC_LABELS = {
    "followers_total": "Total followers",
    "followers_new": "New followers",
    "engagement_total": "Total engagement",
    "engagement_rate": "Engagement rate",
    "posts_count": "Posts published",
}


def fmt_num(val, pct=False, pp=False, signed=False):
    if val is None:
        return "—"
    if pct:
        return f"{val:+.1f}%" if signed else f"{val:.1f}%"
    if pp:
        return f"{val:+.1f}pp" if signed else f"{val:.1f}pp"
    if isinstance(val, float) and val.is_integer():
        val = int(val)
    if signed and isinstance(val, (int, float)):
        return f"{val:+,.0f}" if not isinstance(val, int) else f"{val:+,d}"
    return f"{val:,}" if isinstance(val, int) else f"{val:,.1f}"


def excerpt(text, length=180):
    if not text:
        return "_(no caption text captured)_"
    text = str(text).replace("\n", " ").strip()
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def build_company_rows(companies, competitors):
    rows = []
    order = [e["key"] for e in competitors["company_pages"]]
    for key in order:
        comp = companies.get(key)
        name = c.company_display_name(competitors, key)
        if comp is None:
            rows.append({
                "name": name, "followers": "—", "followers_abs": "—", "followers_pct": "—",
                "engagement_rate": "—", "engagement_rate_abs": "—", "posts_count": "—",
            })
            continue
        m = comp["metrics"]
        rows.append({
            "name": name,
            "followers": fmt_num(m["followers_total"]["current"]),
            "followers_abs": fmt_num(m["followers_total"]["abs_change"], signed=True) if m["followers_total"]["abs_change"] is not None else "—",
            "followers_pct": fmt_num(m["followers_total"]["pct_change"], pct=True, signed=True) if m["followers_total"]["pct_change"] is not None else "—",
            "engagement_rate": fmt_num(m["engagement_rate"]["current"], pct=True) if m["engagement_rate"]["current"] is not None else "—",
            "engagement_rate_abs": fmt_num(m["engagement_rate"]["abs_change"], pp=True, signed=True) if m["engagement_rate"]["abs_change"] is not None else "—",
            "posts_count": fmt_num(m["posts_count"]["current"]) if m["posts_count"]["current"] is not None else "—",
        })
    return rows


def build_flagged(flagged_changes):
    out = []
    for f in flagged_changes:
        metric = f["metric"]
        is_pct_metric = metric != "posts_count"
        prior_fmt = fmt_num(f["prior"], pct=(metric == "engagement_rate"))
        current_fmt = fmt_num(f["current"], pct=(metric == "engagement_rate"))
        if is_pct_metric and f["pct_change"] is not None:
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
        posts_sorted = sorted(posts, key=lambda p: p.get("date_posted") or "", reverse=True)
        formatted = [{
            "date": p.get("date_posted") or "—",
            "type": (p.get("post_type") or "unknown").title(),
            "excerpt": excerpt(p.get("content_text")),
            "likes": int(p["likes"]) if p.get("likes") not in (None, "") else 0,
            "comments": int(p["comments"]) if p.get("comments") not in (None, "") else 0,
            "shares": int(p["shares"]) if p.get("shares") not in (None, "") else 0,
            "url": p.get("url"),
        } for p in posts_sorted]
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
