"""Entry point for setup.

Idempotent — run on a fresh DB, after a schema change, or when new seed tags
are added. Safe to re-run.
"""
from config import SEED_TAGS
from db import conn_ctx, init_schema


def ensure_seed_tags():
    with conn_ctx() as conn:
        cur = conn.cursor()
        existing = {r["name"] for r in cur.execute("SELECT name FROM tags").fetchall()}
        missing = [name for name in SEED_TAGS if name not in existing]

        if not missing:
            print(f"seed tags already present ({len(existing)} total)")
            return

        cur.executemany(
            "INSERT INTO tags (name, is_seed) VALUES (?, 1)",
            [(name,) for name in missing],
        )
        print(f"inserted {len(missing)} seed tags: {', '.join(missing)}")


def setup():
    init_schema()
    ensure_seed_tags()


if __name__ == "__main__":
    setup()