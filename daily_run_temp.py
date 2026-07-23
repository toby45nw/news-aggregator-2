"""One-shot morning run: ingest → enrich → cluster → score → post.

For manual use before the server + ofelia setup is in place.
Uses weekly mode on Mondays, daily otherwise (matches the eventual schedule).
Writes the selected digest to digest_YYYY-MM-DD.txt with URLs for reading.
"""

import subprocess
import sys
from datetime import date

from db import conn_ctx


def run(stage, *args):
    print(f"\n=== {stage} {' '.join(args)} ===")
    result = subprocess.run(
        [sys.executable, f"{stage}.py", *args],
        check=False,
    )
    if result.returncode != 0:
        print(f"!! {stage} failed with exit code {result.returncode}")
        sys.exit(result.returncode)


def write_digest_file(digest_date_str):
    """Read the day's selected items from the DB and write them to a text file."""
    with conn_ctx() as conn:
        rows = conn.execute("""
            SELECT source_name, title, url, cluster_id, cluster_headline, score
            FROM items
            WHERE digest_date = ?
            ORDER BY score DESC, cluster_id, id
        """, (digest_date_str,)).fetchall()

    # group by cluster (or singleton = own row)
    from collections import defaultdict
    by_cluster = defaultdict(list)
    for r in rows:
        by_cluster[r["cluster_id"]].append(r)

    # sort clusters by score, largest cluster first for stories tied
    ordered = sorted(
        by_cluster.items(),
        key=lambda kv: (kv[1][0]["score"], len(kv[1])),
        reverse=True,
    )

    path = f"digest_{digest_date_str}.txt"
    with open(path, "w") as f:
        f.write(f"Digest — {digest_date_str}\n")
        f.write(f"{len(ordered)} stories, {len(rows)} items\n")
        f.write("=" * 60 + "\n\n")

        for i, (_, members) in enumerate(ordered, 1):
            headline = members[0]["cluster_headline"] or members[0]["title"]
            score = members[0]["score"]

            if len(members) > 1:
                distinct = len({m["source_name"] for m in members})
                f.write(f"{i}. [{len(members)} items · {distinct} sources · score {score:.2f}]\n")
                f.write(f"   → {headline}\n")
                for m in members:
                    f.write(f"     [{m['source_name']}] {m['title']}\n")
                    f.write(f"     {m['url']}\n")
            else:
                m = members[0]
                f.write(f"{i}. [score {score:.2f}] [{m['source_name']}]\n")
                f.write(f"   {headline}\n")
                f.write(f"   {m['url']}\n")
            f.write("\n")

    print(f"\nwrote {path}")


def main():
    is_monday = date.today().weekday() == 0
    mode = "weekly" if is_monday else "daily"

    run("ingest")
    run("enrich")
    run("cluster", "--window", mode)
    run("score", "--mode", mode)
    run("post", "--mode", mode)

    write_digest_file(date.today().isoformat())


if __name__ == "__main__":
    main()