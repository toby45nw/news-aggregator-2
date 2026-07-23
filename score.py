"""Score every cluster in the window and write the score back to items.

Selection (top N, caps, headlines) happens at posting time, not here.

Usage:
    python score.py --mode daily
    python score.py --mode weekly
"""

import argparse
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from config import SOURCE_WEIGHTS
from db import conn_ctx

WINDOW_DAYS = {"daily": 1, "weekly": 7}


def load_clustered_items(conn, window):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS[window])).isoformat()
    return conn.execute(
        """
        SELECT id, source_name, cluster_id
        FROM items
        WHERE cluster_id IS NOT NULL
          AND fetched_at >= ?
        """,
        (cutoff,),
    ).fetchall()


def load_tag_signal(conn):
    rows = conn.execute("""
        SELECT it.item_id, MAX(t.weight * it.fit_score / 3.0) AS signal
        FROM item_tags it
        JOIN tags t ON t.id = it.tag_id
        GROUP BY it.item_id
    """).fetchall()
    return {r["item_id"]: r["signal"] for r in rows}


def score_clusters(items, tag_signal):
    by_cluster = defaultdict(list)
    for item in items:
        by_cluster[item["cluster_id"]].append(item)

    scores = {}
    for cid, members in by_cluster.items():
        distinct = len({m["source_name"] for m in members})
        corroboration = math.log(1 + distinct)
        tag_term = max((tag_signal.get(m["id"], 0.0) for m in members), default=0.0)
        source_term = max(
            (SOURCE_WEIGHTS.get(m["source_name"], 1.0) for m in members),
            default=1.0,
        )
        scores[cid] = corroboration + tag_term + source_term
    return scores


def write_scores(conn, items, cluster_scores):
    """Write cluster score onto every member."""
    updates = [(cluster_scores[i["cluster_id"]], i["id"]) for i in items]
    conn.executemany("UPDATE items SET score = ? WHERE id = ?", updates)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=WINDOW_DAYS.keys(), required=True)
    args = parser.parse_args()

    with conn_ctx() as conn:
        items = load_clustered_items(conn, args.mode)
        tag_signal = load_tag_signal(conn)
        cluster_scores = score_clusters(items, tag_signal)
        write_scores(conn, items, cluster_scores)

    print(f"scored {len(cluster_scores)} clusters over {len(items)} items")


if __name__ == "__main__":
    main()