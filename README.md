# LinkedIn Competitor Activity

A weekly LinkedIn competitor audit pipeline for Zilker Trail. Turns
Coefficient-synced LinkedIn Analytics (Competitors tab) and post data into a
report with:

- An executive summary of week-over-week analytics movement, with
  significant changes flagged and speculation on drivers.
- A full index of net-new posts for tracked Company Pages and leadership
  profiles.
- Qualitative analysis: brand/leader summaries, cross-competitor content
  themes and formats, and where Zilker Trail might agree, differentiate, or
  push back.

Run it via the `weekly-linkedin-audit` Claude Code skill, or manually with
the scripts in `scripts/`. See **[docs/RUNBOOK.md](docs/RUNBOOK.md)** for
the full weekly workflow, expected data schema, and configuration.

## Layout

```
config/                 competitor roster, thresholds, column mappings, ZT positioning
data/raw/                weekly Coefficient exports land here (analytics/, posts/)
data/processed/          computed history + per-week analysis output
data/state/               dedup/tracking state (seen posts, ingested files)
scripts/                 ingestion, WoW analysis, post diffing, report rendering
templates/               report Jinja2 template
reports/weekly/          generated weekly reports (Markdown)
.claude/skills/weekly-linkedin-audit/   orchestration skill
docs/RUNBOOK.md          full usage guide
```

## Quick start

```bash
pip install -r requirements.txt
# drop this week's Coefficient exports into data/raw/analytics/ and data/raw/posts/
python3 scripts/ingest_analytics.py
python3 scripts/diff_new_posts.py --week YYYY-MM-DD
python3 scripts/analyze_wow.py --week YYYY-MM-DD
python3 scripts/render_report.py --week YYYY-MM-DD
# then fill in the qualitative sections — see docs/RUNBOOK.md
```

Two sample weeks of demo data are included (`2026-08-28`, `2026-09-04`) so
the pipeline runs end-to-end out of the box — see
`reports/weekly/2026-09-04.md` for a full example output.
