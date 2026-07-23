"""Select up to 25 stories from scored items and write the digest to the DB.

Caps:
- At most 5 clusters (multi-item stories).
- At most 6 items per primary tag; each cluster counts as 1.
- At most 3 singletons per source (cluster memberships don't count).
- `other`-only items excluded.

Cluster's tag for cap purposes is the weighted majority across members'
primary tags — sum tag.weight per tag, highest wins. Ties broken by highest
single-item weight × fit_score within the tag.

For each winning cluster, an LLM call picks the most representative headline
from the cluster's own titles. Singletons use their own title. Winners get
digest_date and cluster_headline written back to items.

Actual Discord posting is the bot's job — this script prepares the DB and
prints the digest for review.

Usage:
    python post.py --mode daily
    python post.py --mode weekly
"""

import argparse
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import ollama

from config import SOURCE_WEIGHTS
from db import conn_ctx

WINDOW_DAYS = {"daily": 1, "weekly": 7}
TOTAL_STORIES = 25
MAX_CLUSTERS = 5
MAX_PER_TAG = 6
MAX_SINGLETONS_PER_SOURCE = 3
HEADLINE_MODEL = "gemma3:4b"


# --- load ---

def load_scored_items(conn, window):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS[window])).isoformat()
    return conn.execute("""
        SELECT id, source_name, title, cluster_id, score, digest_date
        FROM items
        WHERE score IS NOT NULL
          AND cluster_id IS NOT NULL
          AND fetched_at >= ?
    """, (cutoff,)).fetchall()


def load_item_tag_signals(conn):
    """Return {item_id: [(tag_name, weight*fit_score), ...]}.
    Sorted per item so the first entry is the primary tag.
    """
    rows = conn.execute("""
        SELECT it.item_id, t.name, t.weight * it.fit_score AS signal
        FROM item_tags it
        JOIN tags t ON t.id = it.tag_id
    """).fetchall()

    by_item = defaultdict(list)
    for r in rows:
        by_item[r["item_id"]].append((r["name"], r["signal"]))
    for iid in by_item:
        by_item[iid].sort(key=lambda x: x[1], reverse=True)
    return by_item


def load_tag_weights(conn):
    return {r["name"]: r["weight"] for r in conn.execute("SELECT name, weight FROM tags")}


# --- helpers ---

def primary_tag(item_id, item_signals):
    """Primary tag = highest weight × fit_score for that item."""
    sigs = item_signals.get(item_id)
    return sigs[0][0] if sigs else "other"


def all_tags(item_id, item_signals):
    return {name for name, _ in item_signals.get(item_id, [])}


def is_other_only(item_id, item_signals):
    return all_tags(item_id, item_signals) == {"other"}


def cluster_tag(members, item_signals, tag_weights):
    """Weighted-majority primary tag for a cluster.

    Sum tag.weight per tag across members' primary tags. Highest sum wins.
    Ties broken by highest single-item weight × fit_score within that tag.
    """
    sum_weight = defaultdict(float)
    best_signal = defaultdict(float)

    for m in members:
        sigs = item_signals.get(m["id"])
        if not sigs:
            continue
        tag, signal = sigs[0]
        sum_weight[tag] += tag_weights.get(tag, 1.0)
        if signal > best_signal[tag]:
            best_signal[tag] = signal

    if not sum_weight:
        return "other"

    return max(sum_weight, key=lambda t: (sum_weight[t], best_signal[t]))


def eligible_cluster(members):
    """Weekly rule: at least one member must be unposted."""
    return any(m["digest_date"] is None for m in members)


# --- selection ---

def select(items, item_signals, tag_weights, mode):
    """Return list of (cluster_id, members) tuples in admission order."""
    by_cluster = defaultdict(list)
    for item in items:
        by_cluster[item["cluster_id"]].append(item)

    # score is identical across cluster members
    ranked = sorted(by_cluster.items(), key=lambda kv: kv[1][0]["score"], reverse=True)

    if mode == "weekly":
        ranked = [(cid, m) for cid, m in ranked if eligible_cluster(m)]

    # drop other-only members; drop clusters that empty out
    cleaned = []
    for cid, members in ranked:
        kept = [m for m in members if not is_other_only(m["id"], item_signals)]
        if kept:
            cleaned.append((cid, kept, len(members) > 1))

    tag_count = defaultdict(int)
    src_singleton_count = defaultdict(int)
    winners = []
    stories = 0
    clusters = 0

    # Pass 1: clusters
    for cid, members, is_multi in cleaned:
        if not is_multi:
            continue
        if clusters >= MAX_CLUSTERS or stories >= TOTAL_STORIES:
            break

        tag = cluster_tag(members, item_signals, tag_weights)
        if tag_count[tag] >= MAX_PER_TAG:
            continue

        tag_count[tag] += 1
        winners.append((cid, members))
        clusters += 1
        stories += 1

    # Pass 2: singletons
    for cid, members, is_multi in cleaned:
        if is_multi:
            continue
        if stories >= TOTAL_STORIES:
            break

        m = members[0]
        src = m["source_name"]
        tag = primary_tag(m["id"], item_signals)

        if src_singleton_count[src] >= MAX_SINGLETONS_PER_SOURCE:
            continue
        if tag_count[tag] >= MAX_PER_TAG:
            continue

        winners.append((cid, members))
        src_singleton_count[src] += 1
        tag_count[tag] += 1
        stories += 1

    return winners


# --- headline ---

def pick_headline(members):
    if len(members) == 1:
        return members[0]["title"]

    numbered = "\n".join(f"{i+1}. {m['title']}" for i, m in enumerate(members))
    prompt = f"""Below are {len(members)} news headlines about the same story from different sources. Pick the ONE headline that best summarises the story overall — clearest, most informative, least sensational.

{numbered}

Respond with only the number."""

    try:
        raw = ollama.chat(
            model=HEADLINE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0, "num_predict": 10},
            keep_alive="30m",
        )["message"]["content"].strip()
        m = re.search(r"\d+", raw)
        if m:
            idx = int(m.group()) - 1
            if 0 <= idx < len(members):
                return members[idx]["title"]
    except Exception as e:
        print(f"  headline pick failed: {e}")

    return max(
        members,
        key=lambda m: (SOURCE_WEIGHTS.get(m["source_name"], 1.0), -len(m["title"] or "")),
    )["title"]


# --- main ---

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=WINDOW_DAYS.keys(), required=True)
    args = parser.parse_args()

    digest_date_str = date.today().isoformat()

    with conn_ctx() as conn:
        items = load_scored_items(conn, args.mode)
        item_signals = load_item_tag_signals(conn)
        tag_weights = load_tag_weights(conn)

        winners = select(items, item_signals, tag_weights, args.mode)

        print(f"\n=== digest for {digest_date_str} ({args.mode}) ===")
        print(f"{len(winners)} stories selected\n")

        for i, (cid, members) in enumerate(winners, 1):
            headline = pick_headline(members)
            score = members[0]["score"]

            if len(members) > 1:
                distinct = len({m["source_name"] for m in members})
                tag = cluster_tag(members, item_signals, tag_weights)
                print(f"{i:2}. [cluster · {len(members)} items · {distinct} sources · tag {tag} · score {score:.2f}]")
                print(f"    → {headline}")
                for m in members:
                    print(f"      [{m['source_name']}] {m['title']}")
            else:
                m = members[0]
                tag = primary_tag(m["id"], item_signals)
                print(f"{i:2}. [single · tag {tag} · score {score:.2f}] [{m['source_name']}]")
                print(f"    {headline}")
            print()

            for m in members:
                conn.execute(
                    "UPDATE items SET digest_date = ?, cluster_headline = ? WHERE id = ?",
                    (digest_date_str, headline, m["id"]),
                )

    print(f"digest_date={digest_date_str} written to {sum(len(m) for _, m in winners)} items")


if __name__ == "__main__":
    main()