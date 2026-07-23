"""Feed ingestion.

Fetches every feed in config.FEEDS, parses entries, and inserts new items into
the DB. Two dedupe layers:
  - URL tracking-param strip (catches ?utm_* etc. treating same article as new)
  - Near-duplicate title check within a lookback window (catches same-source
    republishes under a new URL slug)

Run: python3 ingest.py
"""

import sqlite3
import time
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import feedparser

from config import FEEDS
from db import get_conn

TITLE_SIMILARITY_THRESHOLD = 0.95
DEDUPE_LOOKBACK_DAYS = 2  # catches same-day/next-day republishes without
                          # false positives on genuinely recurring column titles

TRACKING_PARAMS = {
    "at_medium", "at_campaign", "traffic_source", "cmpid",
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
}


def normalize_url(url):
    """Strip known tracking query params so the same article isn't treated as
    two different URLs (e.g. BBC's ?at_medium=RSS)."""
    if not url:
        return url
    parts = urlsplit(url)
    clean_query = [(k, v) for k, v in parse_qsl(parts.query) if k not in TRACKING_PARAMS]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(clean_query), ""))


def is_near_duplicate_title(conn, source_name, title):
    """Check for a near-identical title from the same source recently. Catches
    same-source republishes under a new URL slug that URL dedupe can't catch."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=DEDUPE_LOOKBACK_DAYS)).isoformat()
    rows = conn.execute(
        "SELECT title FROM items WHERE source_name = ? AND fetched_at >= ?",
        (source_name, cutoff),
    ).fetchall()
    for row in rows:
        existing = row["title"]
        if existing and SequenceMatcher(None, title.lower(), existing.lower()).ratio() >= TITLE_SIMILARITY_THRESHOLD:
            return True
    return False


def parse_published(entry):
    """Best-effort extraction of a published timestamp from a feed entry."""
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            return datetime.fromtimestamp(time.mktime(value), tz=timezone.utc).isoformat()
    return None


def extract_thumbnail(entry):
    """Best-effort thumbnail URL from the various places feeds put them."""
    media = entry.get("media_thumbnail") or entry.get("media_content")
    if media and isinstance(media, list) and media[0].get("url"):
        return media[0]["url"]
    for link in entry.get("links", []):
        if link.get("rel") == "enclosure" and (link.get("type") or "").startswith("image/"):
            return link.get("href")
    return None


def ingest_feed(conn, source_name, url):
    parsed = feedparser.parse(url)

    if parsed.bozo and not parsed.entries:
        print(f"  [warn] failed to parse {source_name} ({url}): {parsed.bozo_exception}")
        return 0

    new_count = 0

    for entry in parsed.entries:
        link = normalize_url(entry.get("link"))
        if not link:
            continue  # can't dedupe without a URL

        title = entry.get("title", "(no title)")

        if is_near_duplicate_title(conn, source_name, title):
            continue

        summary = entry.get("summary", "")
        author = entry.get("author")
        external_id = entry.get("id")
        thumbnail_url = extract_thumbnail(entry)
        published_at = parse_published(entry)

        try:
            conn.execute(
                """
                INSERT INTO items (
                    source_name, external_id, url, title, summary,
                    author, thumbnail_url, published_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (source_name, external_id, link, title, summary,
                 author, thumbnail_url, published_at),
            )
            new_count += 1
        except sqlite3.IntegrityError:
            pass  # duplicate URL, skip silently

    conn.commit()
    return new_count


def main():
    conn = get_conn()
    total_new = 0

    print(f"Fetching {len(FEEDS)} feed(s)...\n")

    try:
        for feed in FEEDS:
            source_name, url = feed["source"], feed["url"]
            print(f"Fetching {source_name}...")
            count = ingest_feed(conn, source_name, url)
            print(f"  {count} new item(s)")
            total_new += count
    finally:
        conn.close()

    print(f"\nDone. {total_new} new item(s) added.")


if __name__ == "__main__":
    main()