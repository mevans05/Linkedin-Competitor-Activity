"""Shared helpers for the weekly LinkedIn competitor audit pipeline."""

import json
import re
from pathlib import Path

import docx
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
STATE_DIR = DATA_DIR / "state"
REPORTS_DIR = ROOT / "reports" / "weekly"


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def load_competitors():
    return load_yaml(CONFIG_DIR / "competitors.yaml")


def load_thresholds():
    return load_yaml(CONFIG_DIR / "thresholds.yaml")["metrics"]


def load_column_mappings():
    return load_yaml(CONFIG_DIR / "column_mappings.yaml")


def normalize_columns(df, mapping):
    """Rename df columns to canonical names using {canonical: [alias, ...]}.

    Matching is case-insensitive and ignores leading/trailing whitespace.
    Unrecognized columns are left as-is (and simply ignored downstream).
    """
    lower_map = {}
    for canonical, aliases in mapping.items():
        lower_map[canonical.strip().lower()] = canonical
        for alias in aliases:
            lower_map[alias.strip().lower()] = canonical

    rename = {}
    for col in df.columns:
        key = str(col).strip().lower()
        if key in lower_map:
            rename[col] = lower_map[key]
    return df.rename(columns=rename)


def read_table(path):
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path)
    if path.suffix.lower() == ".docx":
        return read_pasted_posts_docx(path)
    return pd.read_csv(path)


_ENTITY_RE = re.compile(r"^(Competitor|Leader|Profile)\s*:\s*(.+)$", re.I)
_SECTION_HEADER_RE = re.compile(r"^Top Engagement Posts\s*:?\s*$", re.I)
_NUMBER_RE = re.compile(r"^\d+$")
_FIELD_LABELS = {
    "post url": "url",
    "post text": "content_text",
    "post format": "post_type",
    "cta": "cta",
}
_FIELD_LABEL_RE = re.compile(
    r"^(" + "|".join(re.escape(lbl) for lbl in _FIELD_LABELS) + r")\s*:\s*(.*)$", re.I
)


def read_pasted_posts_docx(path):
    """Parse a manually-pasted competitor/leader post digest.

    Expected structure (one repeated block per post, grouped under an
    entity header): "Competitor: <name>" (or "Leader:"/"Profile:"),
    optionally "Top Engagement Posts:", then per post: a bare post number,
    "Post URL:", "Post Text:" (may span several paragraphs — LinkedIn
    hashtags paste as a standalone "hashtag" paragraph followed by "#Tag",
    which is dropped/rejoined here), "Post Format:", "CTA:". No engagement
    counts or dates are expected from this source.
    """
    d = docx.Document(str(path))
    lines = [p.text.strip() for p in d.paragraphs]
    lines = [ln for ln in lines if ln and ln.lower() != "hashtag"]

    rows = []
    current_entity = None
    current_post = None
    active_field = None

    def append_field(post, field, text):
        if field == "content_text" and post.get(field):
            post[field] = post[field] + " " + text
        elif field not in post or not post[field]:
            post[field] = text

    def flush():
        nonlocal current_post
        if current_post and (current_post.get("url") or current_post.get("content_text")):
            current_post["author_name"] = current_entity
            rows.append(current_post)
        current_post = None

    for line in lines:
        m = _ENTITY_RE.match(line)
        if m:
            flush()
            current_entity = m.group(2).strip()
            active_field = None
            continue
        if _SECTION_HEADER_RE.match(line):
            active_field = None
            continue
        if _NUMBER_RE.match(line):
            flush()
            current_post = {}
            active_field = None
            continue

        m = _FIELD_LABEL_RE.match(line)
        if m:
            field = _FIELD_LABELS[m.group(1).lower()]
            active_field = field
            if current_post is None:
                current_post = {}
            inline_value = m.group(2).strip()
            if inline_value:
                append_field(current_post, field, inline_value)
            continue

        if active_field and current_post is not None:
            append_field(current_post, active_field, line)
    flush()

    return pd.DataFrame(rows)


def load_json(path, default):
    path = Path(path)
    if not path.exists():
        return default
    with open(path) as f:
        return json.load(f)


def _json_default(o):
    # numpy/pandas scalars (int64, float64, Timestamp, etc.) expose .item()
    # or isoformat(); fall back to str() for anything else.
    if hasattr(o, "item"):
        return o.item()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


def save_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=_json_default)


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")


def build_company_lookup(competitors):
    """Map normalized company name/key/alias -> canonical company key."""
    lookup = {}
    for entry in competitors["company_pages"]:
        lookup[entry["key"].strip().lower()] = entry["key"]
        lookup[entry["linkedin_name"].strip().lower()] = entry["key"]
        for alias in entry.get("aliases", []):
            lookup[alias.strip().lower()] = entry["key"]
    return lookup


def build_leader_lookup(competitors):
    """Map normalized leader name/key/alias -> canonical leader key."""
    lookup = {}
    for entry in competitors["leadership_profiles"]:
        lookup[entry["key"].strip().lower()] = entry["key"]
        lookup[entry["full_name"].strip().lower()] = entry["key"]
        for alias in entry.get("aliases", []):
            lookup[alias.strip().lower()] = entry["key"]
    return lookup


def build_self_page_names(competitors):
    """Normalized set of names for Zilker Trail's own page, to skip silently
    when it shows up as a row in a self-vs-competitor comparison export."""
    return {name.strip().lower() for name in competitors.get("self_page_aliases", [])}


def company_display_name(competitors, key):
    for entry in competitors["company_pages"]:
        if entry["key"] == key:
            return entry["linkedin_name"]
    return key


def leader_display_name(competitors, key):
    for entry in competitors["leadership_profiles"]:
        if entry["key"] == key:
            return entry["full_name"]
    return key
