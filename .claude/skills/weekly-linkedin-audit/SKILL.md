---
name: weekly-linkedin-audit
description: Generate the weekly LinkedIn competitor audit and summary report — ingests the week's Coefficient exports (analytics + posts), computes WoW deltas, indexes net-new posts for tracked Company Pages and leadership profiles, then writes the qualitative analysis (brand/leader summaries, content themes, Zilker Trail POV) and publishes the report. Use when the user asks to run, generate, or update the weekly LinkedIn competitor audit/report, or invokes /weekly-linkedin-audit.
---

# Weekly LinkedIn Competitor Audit

This skill produces the weekly LinkedIn competitor audit: a report with a
quant executive summary (WoW analytics deltas, flagged significant moves,
speculation on drivers), an index of net-new posts for tracked Company Pages
and leadership profiles, and qualitative analysis (brand/leader summaries,
cross-competitor content themes, and Zilker Trail's potential POV).

The pipeline splits work deliberately: **scripts do the arithmetic** (WoW
deltas, significance flags, new-post diffing) so the numbers are always
exactly right; **you do the synthesis** (reading actual post content and
writing the narrative) because that requires judgment a script can't apply.
Never hand-compute or eyeball a WoW percentage yourself — always read it from
the script output.

## Inputs this expects

Two files should exist for the target week before running:
- `data/raw/analytics/<week>.csv` (or `.xlsx`) — the Coefficient export of
  LinkedIn Analytics → Competitors data (follower counts, engagement).
- `data/raw/posts/<week>.csv` (or `.xlsx`) — the Coefficient export of
  Company Page and leadership profile posts for the week.

The exact filename doesn't matter (the ingest scripts scan the whole
directory for anything not yet ingested) — what matters is the file is
dropped into the right folder before this skill runs. Column headers don't
need to match exactly either; `config/column_mappings.yaml` aliases common
header variants to the canonical fields.

**If one or both files are missing**, tell the user which file(s) are needed
and where to put them (`data/raw/analytics/` and `data/raw/posts/`), point
them to `docs/RUNBOOK.md` for the expected schema, and stop — do not
fabricate data or run the pipeline on a partial week.

## Steps

1. **Check for input files.** List `data/raw/analytics/` and
   `data/raw/posts/` for files not yet recorded in
   `data/state/ingested_analytics_files.json` /
   `data/state/ingested_posts_files.json`. If nothing new, ask the user for
   this week's export or confirm the target week explicitly.

2. **Run the pipeline** (from the repo root; determine `<week>` as the
   Monday or the analytics snapshot date in the new file — ask the user if
   ambiguous):
   ```
   python3 scripts/ingest_analytics.py
   python3 scripts/diff_new_posts.py --week <week>
   python3 scripts/analyze_wow.py --week <week>
   python3 scripts/render_report.py --week <week>
   ```
   Watch stdout for `WARNING` lines about unmatched company/author names —
   if any appear, a competitor's name in the export doesn't match
   `config/competitors.yaml`; flag this to the user rather than silently
   dropping their data (a plausible fuzzy match is not good enough — ask).

3. **Read the rendered skeleton** at `reports/weekly/<week>.md`, plus
   `data/processed/wow_analysis_<week>.json` and
   `data/processed/new_posts_<week>.json` for the full structured data
   behind it, and `config/zilker_trail.md` for positioning to ground the POV
   sections.

4. **Write the qualitative sections directly into the report file** with
   Edit, replacing each `_TODO (Claude): ..._` block between its
   `<!-- QUALITATIVE:X -->` / `<!-- /QUALITATIVE:X -->` markers (leave the
   markers themselves in place so future runs and diffs stay anchored):
   - **Executive Summary**: 3-6 bullets on WoW findings. Every flagged
     movement from the Significant Movements table must be named with
     specific speculation on why (tie to a specific new post when the post
     data supports it — don't speculate generically when there's a post that
     obviously explains the number).
   - **By Brand**: one subsection per company that has new posts this week
     (skip companies with zero — no need to write "nothing happened").
     Topics/themes/format used, and how Zilker Trail might approach the
     subject or where it would disagree.
   - **By Leader**: same treatment, per leader with new posts.
   - **Cross-Competitor Patterns**: findings that span multiple
     competitors — format mix trends, recurring themes, tone shifts. Don't
     repeat single-brand observations already covered above.
   - **Zilker Trail POV & Opportunities**: concrete, specific angles ZT
     could publish this week, grounded in `config/zilker_trail.md`. Prefer
     naming an actual post/topic to react to over generic advice.

   Ground every claim in the actual post excerpts and numbers — never invent
   a theme or engagement pattern that isn't visible in `new_posts_<week>.json`
   or `wow_analysis_<week>.json`.

5. **Commit** the updated `reports/weekly/<week>.md` (and the `data/`
   changes — history/state files are checked in so the pipeline is
   reproducible and auditable across weeks) to the branch, with a clear
   commit message naming the week.

6. **Publish an HTML artifact version** of the finished report (per the
   user's stated preference for both Markdown + a shareable web version).
   Load the `artifact-design` skill first, then translate the Markdown
   report into a well-designed HTML page — keep the same structure and all
   the content, but present the quant snapshot as a proper table/stat
   layout (see the `dataviz` skill if charts would help show the WoW trend)
   rather than a literal Markdown-to-HTML dump. Give the user the link.

## Notes for recurring/scheduled use

If the user wants this to run automatically every week (e.g. via the `loop`
skill or a scheduled trigger), the input-file check in step 1 is the natural
gate — the skill should no-op with a clear message if the week's Coefficient
exports haven't landed yet, rather than erroring or fabricating a report.

If a competitor is added, removed, or renamed, update
`config/competitors.yaml` — the `key` field must stay stable even if
`linkedin_name` changes, since it's used to join historical data.
