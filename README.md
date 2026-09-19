# LinkedIn Competitor Activity

A weekly LinkedIn competitor audit pipeline for Zilker Trail. Combines a
Coefficient-synced analytics export with manually-gathered post content into
a report with:

- An executive summary of week-over-week analytics movement, with
  significant changes flagged and speculation on drivers.
- A full index of net-new posts for tracked Company Pages and leadership
  profiles.
- Qualitative analysis: brand/leader summaries, cross-competitor content
  themes and formats, and where Zilker Trail might agree, differentiate, or
  push back.

Run it via the `weekly-linkedin-audit` Claude Code skill, or manually with
the scripts in `scripts/`. See **[docs/RUNBOOK.md](docs/RUNBOOK.md)** for
the full weekly workflow, expected data formats, and configuration.

## Layout

```
config/                 competitor roster, thresholds, column mappings, ZT positioning
data/raw/                weekly inputs land here (analytics/ from Coefficient, posts/ pasted manually)
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
# drop this week's analytics CSV into data/raw/analytics/<date>.csv
# drop this week's pasted post content into data/raw/posts/<date>.docx
python3 scripts/ingest_analytics.py
python3 scripts/diff_new_posts.py --week YYYY-MM-DD
python3 scripts/analyze_wow.py --week YYYY-MM-DD
python3 scripts/render_report.py --week YYYY-MM-DD
# then fill in the qualitative sections — see docs/RUNBOOK.md
```

Two sample weeks of demo data are included (`2026-08-21`, `2026-08-28`) so
the pipeline runs end-to-end out of the box — see
`reports/weekly/2026-08-28.md` for a full example output. The analytics
figures reuse Zilker Trail's real Coefficient snapshot; the Accenture posts
in the first week are real public content from a sample export, the rest are
illustrative. Both reports are clearly marked as demo data.
