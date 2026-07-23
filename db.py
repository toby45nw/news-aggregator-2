"""Database connection and schema.

`get_conn()` / `conn_ctx()` — connection helpers. Every module uses these
rather than opening its own connection, so pragmas are applied consistently.

`init_schema()` — creates tables and indexes. Idempotent, safe to re-run.
"""
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path("newsagg.sqlite")

log = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name         TEXT NOT NULL,
    external_id         TEXT,
    url                 TEXT NOT NULL UNIQUE,
    title               TEXT,
    summary             TEXT,
    author              TEXT,
    thumbnail_url       TEXT,
    published_at        TIMESTAMP,
    fetched_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    discord_message_id  TEXT,
    score               REAL,
    cluster_headline    TEXT,
    digest_date         DATE,
    embedding           BLOB,
    embedding_model     TEXT,
    needs_retag         INTEGER NOT NULL DEFAULT 0,
    cluster_id          INTEGER,
    upvotes    INTEGER NOT NULL DEFAULT 0,
    downvotes  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_items_published_at ON items(published_at);
CREATE INDEX IF NOT EXISTS idx_items_digest_date  ON items(digest_date);
CREATE INDEX IF NOT EXISTS idx_items_source_name  ON items(source_name);
CREATE INDEX IF NOT EXISTS idx_items_needs_retag  ON items(needs_retag) WHERE needs_retag = 1;

CREATE TABLE IF NOT EXISTS tags (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE,
    weight         REAL NOT NULL DEFAULT 1.0,
    is_seed        INTEGER NOT NULL DEFAULT 0,
    article_count  INTEGER NOT NULL DEFAULT 0,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS item_tags (
    item_id     INTEGER NOT NULL,
    tag_id      INTEGER NOT NULL,
    fit_score   INTEGER NOT NULL,
    PRIMARY KEY (item_id, tag_id),
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id)  REFERENCES tags(id)  ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_item_tags_item_id ON item_tags(item_id);
CREATE INDEX IF NOT EXISTS idx_item_tags_tag_id  ON item_tags(tag_id);

CREATE TABLE IF NOT EXISTS errors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stage       TEXT NOT NULL,
    message     TEXT NOT NULL,
    traceback   TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    posted      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_errors_unposted ON errors(created_at) WHERE posted = 0;
"""


def _configure(conn):
    """Apply pragmas that need to run on every connection."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = sqlite3.Row


def get_conn():
    """Return a configured SQLite connection. Caller closes it."""
    conn = sqlite3.connect(DB_PATH)
    _configure(conn)
    return conn


@contextmanager
def conn_ctx():
    """Connection as a context manager. Commits on success, rolls back on error."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema():
    """Create tables and indexes. Idempotent."""
    with conn_ctx() as conn:
        conn.executescript(SCHEMA)
    log.info("schema initialised")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_schema()
    print("done")