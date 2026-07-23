"""Cluster items in a time window into stories.

Groups items by embedding similarity so score.py can rank stories (clusters)
rather than individual items. Writes cluster_id back to each item.

Usage:
    python cluster.py --window daily    # last 24h
    python cluster.py --window weekly   # last 7 days
"""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from db import conn_ctx

DISTANCE_THRESHOLD = 0.60  # validated in earlier tuning session

WINDOW_DAYS = {"daily": 1, "weekly": 7}


def load_items(conn, window):
    """Return list of (id, embedding_bytes) for items in the window with an embedding."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS[window])).isoformat()
    rows = conn.execute(
        """
        SELECT id, embedding FROM items
        WHERE embedding IS NOT NULL
          AND fetched_at >= ?
        """,
        (cutoff,),
    ).fetchall()
    return rows


def cluster_items(rows):
    """Return dict of {item_id: cluster_label}. Singletons get their own label."""
    if not rows:
        return {}

    ids = [r["id"] for r in rows]
    X = np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])

    clusterer = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=DISTANCE_THRESHOLD,
        metric="cosine",
        linkage="average",
    )
    labels = clusterer.fit_predict(X)

    return dict(zip(ids, (int(l) for l in labels)))


def write_clusters(conn, id_to_label):
    """Write cluster_id back to items. Wipes any previous cluster_id in this window."""
    conn.executemany(
        "UPDATE items SET cluster_id = ? WHERE id = ?",
        [(label, item_id) for item_id, label in id_to_label.items()],
    )


def summarise(id_to_label):
    """Print a small summary: cluster count, singletons, multi-item clusters."""
    if not id_to_label:
        print("no items to cluster")
        return

    clusters = defaultdict(list)
    for item_id, label in id_to_label.items():
        clusters[label].append(item_id)

    singletons = sum(1 for members in clusters.values() if len(members) == 1)
    multi = len(clusters) - singletons

    print(f"{len(id_to_label)} items → {len(clusters)} clusters "
          f"({multi} multi-item, {singletons} singletons)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", choices=WINDOW_DAYS.keys(), required=True)
    args = parser.parse_args()

    with conn_ctx() as conn:
        rows = load_items(conn, args.window)
        id_to_label = cluster_items(rows)
        write_clusters(conn, id_to_label)

    summarise(id_to_label)


if __name__ == "__main__":
    main()