# Weekly LinkedIn Competitor Audit — Runbook

## What this is

A weekly pipeline that turns Coefficient-synced LinkedIn competitor data into
a report with:
- An **executive summary** of week-over-week (WoW) analytics movement, with
  significant changes flagged and speculation on why.
- An **index of every net-new post** for tracked Company Pages and
  leadership profiles.
- **Qualitative analysis**: brand-by-brand and leader-by-leader summaries,
  cross-competitor content themes/formats, and where Zilker Trail might
  agree, differentiate, or push back.

Quant analysis is fully scripted (deterministic, always numerically
correct). Qualitative analysis is written by Claude each week via the
`weekly-linkedin-audit` skill, reading the real post content.

## Weekly workflow

1. **Export from Coefficient** the two data sets for the week:
   - LinkedIn Analytics → Competitors data (follower counts, engagement) →
     save as `data/raw/analytics/<date>.csv` (or `.xlsx`)
   - Company Page + leadership profile posts → save as
     `data/raw/posts/<date>.csv` (or `.xlsx`)

   Filenames don't matter beyond being unique — the ingest scripts scan the
   whole folder for anything not yet processed.

2. **Run the skill**: invoke `/weekly-linkedin-audit` (or ask Claude to
   "run the weekly LinkedIn audit"). It runs the pipeline, writes the
   qualitative analysis, commits the report, and publishes an HTML version.

3. **Review** `reports/weekly/<date>.md` (and the published artifact link)
   before sharing externally — treat the qualitative sections as a strong
   first draft, not final copy.

## Running the pipeline manually

```bash
pip install -r requirements.txt

python3 scripts/ingest_analytics.py                    # ingest new analytics exports
python3 scripts/diff_new_posts.py --week 2026-09-04     # index net-new posts
python3 scripts/analyze_wow.py --week 2026-09-04        # compute WoW deltas + flags
python3 scripts/render_report.py --week 2026-09-04      # render report skeleton
```

`--week` is the snapshot/week-ending date used to look up that week's row in
the analytics history and to name output files. The quant steps
(`render_report.py`'s output) still need the qualitative sections filled in
— that's the skill's job, or do it by hand by editing the
`<!-- QUALITATIVE:X --> ... <!-- /QUALITATIVE:X -->` blocks in the rendered
Markdown.

## Expected data schema

Column headers are matched flexibly via `config/column_mappings.yaml` (case-
insensitive, several common aliases per field already included) — if
Coefficient's actual export uses different headers than what's listed there,
either rename the columns in the export or add the real header text as a new
alias in that file.

### Analytics export — one row per company per week

| Canonical field | Meaning |
|---|---|
| `company` | Must match a `linkedin_name` or `key` in `config/competitors.yaml` |
| `date` | Snapshot/week-ending date |
| `followers_total` | Total followers as of this snapshot |
| `followers_new` | New followers this period (optional) |
| `engagement_total` | Total engagements this period |
| `engagement_rate` | Engagement rate (%) |
| `posts_count` | Posts published this period |

### Posts export — one row per post

| Canonical field | Meaning |
|---|---|
| `post_id` or `url` | Unique identifier — at least one is required for dedup to work correctly. Without either, a content hash is used as a fallback, which is less reliable for detecting true duplicates. |
| `author_type` | `company` or `leader` (optional — if omitted, the author name is matched against both lists) |
| `author_name` | Must match a company `linkedin_name`/`key` or leader `full_name`/`key` in `config/competitors.yaml` |
| `date_posted` | Post date |
| `post_type` | e.g. text, image, video, document, poll, article |
| `content_text` | Caption/body text |
| `likes`, `comments`, `shares` | Engagement counts |
| `hashtags` | Optional |

## How "net-new" is determined

Every post's `post_id` (or `url`, or a content hash as last resort) is
tracked per-author in `data/state/seen_posts.json`. Each week, only posts not
already in that file are reported as "new" — this means a post scraped twice
(e.g. reappearing in an export because of how Coefficient's sync window
works) won't be double-counted or re-reported.

## Config files

- `config/competitors.yaml` — the tracked Company Pages and leadership
  profiles. The `key` for each entry must stay stable over time (it's the
  join key across all historical data) even if the display name changes.
- `config/thresholds.yaml` — what counts as a "significant" WoW change per
  metric. Tune these once you've seen a few weeks of normal variance for
  this competitor set.
- `config/column_mappings.yaml` — source-column aliasing for flexible
  ingestion.
- `config/zilker_trail.md` — Zilker Trail's positioning/voice, used to
  ground the POV sections of the report. **This started as an inferred
  draft — review and correct it**; the qualitative analysis is only as good
  as this doc.

## Adjusting the report format

Edit `templates/report.md.j2` (quant sections) — it's a Jinja2 template
rendered by `scripts/render_report.py`. Keep the
`<!-- QUALITATIVE:X --> ... <!-- /QUALITATIVE:X -->` marker pairs if you
change structure; the skill relies on them to know where to write.

## Troubleshooting

- **"WARNING: row(s) had a company/author name not found in
  competitors.yaml"** — the export used a name/spelling that doesn't match
  `linkedin_name` or `key` for any tracked entry. Either fix the export or
  add the new spelling to `competitors.yaml`.
- **A file doesn't get picked up by ingest** — check
  `data/state/ingested_analytics_files.json` /
  `ingested_posts_files.json`; a file already listed there is skipped even
  if you edit it. Delete its entry from the manifest to force re-ingestion
  (rare — usually only needed to fix a bad export after the fact).
- **Numbers look right but the significance flags feel off** — tune
  `config/thresholds.yaml`; the defaults are a starting point, not a fixed
  standard.
