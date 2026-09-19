# Weekly LinkedIn Competitor Audit — Runbook

## What this is

A weekly pipeline combining two data sources into one report:
- **Analytics** (follower growth, reactions, comments, posts) synced via
  Coefficient from LinkedIn's Analytics → Competitors comparison table.
- **Post content** (captions, format, CTA) for tracked Company Pages and
  leadership profiles, gathered manually each week — LinkedIn's Competitors
  analytics only exposes aggregate counts for pages you don't administer,
  and doesn't cover individual profiles at all, so there's no automated feed
  for this half.

The output is a report with:
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

1. **Export analytics from Coefficient**: the LinkedIn Pages Import
   competitor comparison table (Page / New Followers / Posts / Comments /
   Comments per day / Reactions). Save as `data/raw/analytics/<date>.csv`,
   where `<date>` is that week's period-end date — the filename *is* the
   date for every row in the file (the real Coefficient table gives one
   period for the whole export, not a per-row date column).

   **Set the underlying LinkedIn Analytics comparison window to 7 days**
   before each sync. Coefficient just pulls whatever period the report is
   configured for (a 30-day pull, refreshed weekly, will look like a
   rolling-window trend, not a clean week-over-week signal — most of two
   consecutive 30-day pulls overlap).

2. **Gather post content manually**: visit each tracked Company Page's Posts
   tab and each leader's profile Activity, and record what's new since last
   week. Save it as `data/raw/posts/<date>.docx` (or `.txt`) following the
   block format below — one file can contain multiple competitors/leaders
   back to back. It's fine to paste more than just the new posts (last
   week's + this week's) — the pipeline dedups automatically against
   `data/state/seen_posts.json`, so nothing gets double-reported.

3. **Run the skill**: invoke `/weekly-linkedin-audit` (or ask Claude to
   "run the weekly LinkedIn audit"). It runs the pipeline, writes the
   qualitative analysis, commits the report, and publishes an HTML version.

4. **Review** `reports/weekly/<date>.md` (and the published artifact link)
   before sharing externally — treat the qualitative sections as a strong
   first draft, not final copy.

## Automated Monday Slack digest

A Routine ("Weekly LinkedIn Competitor Audit Digest", `trig_01MfejKiTZnnum3er2KbAgZu`)
fires every Monday at 8:00am America/New_York, bound to this project's
Claude Code session (same pattern as the account's other weekly digests —
Slack access here comes from the session itself, not a per-Routine
connector grant). Each Monday it:

- Checks `data/raw/analytics/` and `data/raw/posts/` for that week's inputs.
- **If both are ready**: runs the full pipeline above, writes the
  qualitative sections, **commits and pushes the report to
  `claude/linkedin-competitor-audit-lqtkdy` automatically**, publishes/updates
  the HTML artifact, and sends a Slack DM digest (executive summary +
  significant movements + links to the full report) to the account owner.
- **If either input is missing**: sends a Slack DM reminder naming exactly
  what's needed, instead of fabricating a report or committing anything.

This means the weekly inputs (the Coefficient export and the pasted post
digest) need to land in the repo *before* Monday morning to get a real
digest that week — otherwise Monday's message is just a reminder. Manage
the Routine (pause, change schedule, view run history) via
`mcp__Claude_Code_Remote__list_triggers` / `update_trigger` /
`delete_trigger`, or the claude.ai Routines UI.

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
insensitive, several common aliases per field already included) — if a real
export uses different headers than what's listed there, either rename the
columns or add the real header text as a new alias in that file.

### Analytics export — one row per company, matching the Coefficient competitor table

| Canonical field | Source column | Meaning |
|---|---|---|
| `company` | Page | Must match a `linkedin_name`, `key`, or `aliases` entry in `config/competitors.yaml` — including Zilker Trail's own row via `self_page` in that file, which is tracked (not skipped) so it shows up as a labeled reference row in the report. |
| `date` | *(none — derived from filename)* | Optional column; if absent, the period-end date is parsed from the filename (`2026-09-04.csv`). |
| `new_followers` | New Followers | New followers this period |
| `posts_count` | Posts | Posts published this period |
| `comments_total` | Comments | Total comments this period |
| `comments_per_day` | Comments per day | Informational only — not independently flagged (it's derived from `comments_total`) |
| `reactions_total` | Reactions | Total reactions this period |

Note there is **no cumulative follower total or engagement rate** in this
source — only period counts. Significance thresholds for these metrics
(`config/thresholds.yaml`) are set relatively high by default since
week-to-week counts are naturally noisier than a cumulative total would be.

### Posts — manually pasted, one block per entity

Paste into a `.docx` (Word) file. The parser recognizes this structure,
matching the format of a typical "top engagement posts" copy from LinkedIn:

```
Competitor: Accenture
Top Engagement Posts:
1
Post URL:
https://www.linkedin.com/feed/update/...
Post Text:
How do you build an enterprise that doesn't just run, but thinks?
Learn more in our latest report: https://accntu.re/...
Post Format:
Animated image
CTA:
Link to website research report
2
Post URL:
...
```

- The entity line accepts `Competitor:`, `Leader:`, or `Profile:` — the name
  after the colon is matched against both company and leader lists in
  `config/competitors.yaml`, so any of the three labels works for either.
- `Post Text:` can span multiple paragraphs (bracketed alt-text like
  `[VD: ...]` or `[Video Description: ...]` is kept as part of the content —
  useful context for the qualitative write-up). LinkedIn hashtags often
  paste into Word as a standalone "hashtag" paragraph followed by "#Tag" on
  its own line — the parser drops the placeholder and rejoins the tag
  automatically.
- No engagement counts (likes/comments/shares) or post dates come from this
  source — the report gracefully omits those fields when absent rather than
  showing zeroes. If a future source *does* provide them (a different tool,
  or LinkedIn adding this to an export), the same canonical fields
  (`likes`, `comments`, `shares`, `date_posted`) are already wired up — CSV
  and XLSX posts exports with those columns work too, `read_table()`
  dispatches by file extension.
- `post_id` isn't in this source either — the post URL is used as the
  dedup key instead (a content hash is the last-resort fallback if neither
  is present).

## How "net-new" is determined

Every post's `post_id` (or `url`, or a content hash as last resort) is
tracked per-author in `data/state/seen_posts.json`. Each week, only posts not
already in that file are reported as "new" — this means pasting overlapping
content two weeks in a row (e.g. LinkedIn's own "top posts" view still
showing last week's post) won't be double-counted or re-reported.

## Config files

- `config/competitors.yaml` — the tracked Company Pages and leadership
  profiles, plus `aliases` for alternate names seen in real exports (e.g.
  the Coefficient table uses "APPLY" and "Insight" rather than full page
  names) and a `self_page` entry for Zilker Trail's own page. `self_page` is
  tracked through the same WoW pipeline as any competitor — it shows up as a
  bolded "(You)" reference row in the Quantitative Snapshot table and can
  appear in Significant Movements too, so your own analytics sit right
  alongside competitors' each week. The `key` for each entry (competitor or
  self) must stay stable over time (it's the join key across all historical
  data) even if the display name changes.
- `config/thresholds.yaml` — what counts as a "significant" WoW change per
  metric. Tune these once you've seen a few weeks of normal variance for
  this competitor set.
- `config/column_mappings.yaml` — source-column aliasing for flexible
  ingestion.
- `config/zilker_trail.md` — Zilker Trail's positioning/voice, used to
  ground the POV sections of the report. Grounded in the AI Philosophy and
  Pathfinder/Digital Commerce decks as of 2026-09-04 — re-derive from source
  docs if either is materially updated.

## Adjusting the report format

Edit `templates/report.md.j2` (quant sections) — it's a Jinja2 template
rendered by `scripts/render_report.py`. Keep the
`<!-- QUALITATIVE:X --> ... <!-- /QUALITATIVE:X -->` marker pairs if you
change structure; the skill relies on them to know where to write.

## Troubleshooting

- **"WARNING: row(s) had a company/author name not found in
  competitors.yaml"** — the export used a name/spelling that doesn't match
  `linkedin_name`, `key`, or `aliases` for any tracked entry. Either fix the
  export or add the new spelling as an alias in `competitors.yaml`.
- **A file doesn't get picked up by ingest** — check
  `data/state/ingested_analytics_files.json` /
  `ingested_posts_files.json`; a file already listed there is skipped even
  if you edit it. Delete its entry from the manifest to force re-ingestion
  (rare — usually only needed to fix a bad export after the fact).
- **Analytics file skipped with "missing required column(s) ['date']"** —
  the filename couldn't be parsed as a date. Name the file after the
  period-end date (`2026-09-04.csv`), or add an explicit date column.
- **Numbers look right but the significance flags feel off** — tune
  `config/thresholds.yaml`; the defaults are a starting point, not a fixed
  standard, and were set for true 7-day counts (see the window note above).
