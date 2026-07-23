"""Enrichment: embed and tag new items.

Two passes over the items table:
  1. Embed — items where embedding IS NULL. Batch-encoded with all-MiniLM-L6-v2.
  2. Tag — items with an embedding but no item_tags rows (or needs_retag = 1).
     One Ollama call per item to gemma3:4b. On failure, needs_retag is set.

Run after each ingest pass.
"""

import re

import numpy as np
import ollama
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer

from db import conn_ctx

# --- embedding ---

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64

# --- tagging ---

TAG_MODEL = "gemma3:4b"
VALID_TAGS = [
    "politics", "world affairs", "business", "technology", "science",
    "health", "environment", "culture", "sports", "society",
    "history", "lifestyle", "other",
]
WORD_TO_SCORE = {"CENTRAL": 3, "MAJOR": 2, "MINOR": 1}


# --- embed pass ---

def clean_summary(summary):
    if not summary:
        return ""
    return BeautifulSoup(summary, "html.parser").get_text(" ", strip=True)


def build_text(title, summary):
    title = title or ""
    summary = clean_summary(summary)
    return f"{title}. {title}. {summary}".strip()


def embed_pass():
    with conn_ctx() as conn:
        rows = conn.execute(
            "SELECT id, title, summary FROM items WHERE embedding IS NULL"
        ).fetchall()

    print(f"embed: {len(rows)} items")
    if not rows:
        return

    model = SentenceTransformer(EMBED_MODEL_NAME)

    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        texts = [build_text(r["title"], r["summary"]) for r in batch]

        vecs = model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=BATCH_SIZE,
            show_progress_bar=False,
        ).astype(np.float32)

        with conn_ctx() as conn:
            conn.executemany(
                "UPDATE items SET embedding = ?, embedding_model = ? WHERE id = ?",
                [(v.tobytes(), EMBED_MODEL_NAME, r["id"]) for v, r in zip(vecs, batch)],
            )
        print(f"  {start + len(batch)}/{len(rows)}")


# --- tag pass ---

def tag_article(title, summary):
    """Return list of (tag_name, fit_score) tuples. Empty list on failure."""
    text = f"{title or ''}. {summary or ''}"[:1500]

    prompt = f"""Choose up to 3 tags from this list that describe this article, and rate each one.

Valid tags: {', '.join(VALID_TAGS)}

Ratings:
- CENTRAL: article is fundamentally about this topic
- MAJOR: one of several genuine themes
- MINOR: only touched on briefly

Rules:
- Most articles need only 1 tag.
- Never add tags that only tangentially apply.
- You MUST include a rating for every tag you pick.
- If nothing on the list fits, return only: tag: other / rating: MINOR

Article: {text}

Respond in this exact format, alternating tag and rating on separate lines:
tag: <tag name>
rating: <CENTRAL, MAJOR, or MINOR>"""

    raw = ollama.chat(
        model=TAG_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.0, "num_predict": 120},
        keep_alive="30m",
    )["message"]["content"].strip()

    scored = []
    current_tag = None
    for line in raw.splitlines():
        line = line.strip().strip("*").strip("-").strip()
        m_tag = re.match(r"^tag\s*:\s*(.+)$", line, re.IGNORECASE)
        m_rating = re.match(r"^rating\s*:\s*(.+)$", line, re.IGNORECASE)

        if m_tag:
            candidate = m_tag.group(1).strip().lower().strip('"').strip("'")
            current_tag = candidate if candidate in VALID_TAGS else None
        elif m_rating and current_tag:
            rating_text = m_rating.group(1).strip().upper()
            for word, val in WORD_TO_SCORE.items():
                if word in rating_text:
                    scored.append((current_tag, val))
                    break
            current_tag = None

        if len(scored) >= 3:
            break

    return scored


def tag_pass():
    with conn_ctx() as conn:
        rows = conn.execute("""
            SELECT id, title, summary FROM items
            WHERE embedding IS NOT NULL
              AND (needs_retag = 1
                   OR id NOT IN (SELECT DISTINCT item_id FROM item_tags))
        """).fetchall()

        tag_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM tags")}

    print(f"tag: {len(rows)} items")
    if not rows:
        return

    for i, row in enumerate(rows, 1):
        try:
            scored = tag_article(row["title"], row["summary"])
        except Exception as e:
            print(f"  [{row['id']}] ollama error: {e}")
            scored = []

        with conn_ctx() as conn:
            # clear existing tags (retag case) then insert fresh
            conn.execute("DELETE FROM item_tags WHERE item_id = ?", (row["id"],))

            if not scored:
                conn.execute("UPDATE items SET needs_retag = 1 WHERE id = ?", (row["id"],))
                print(f"  [{row['id']}] no valid tags → needs_retag")
                continue

            for name, score in scored:
                tid = tag_ids.get(name)
                if tid is None:
                    continue  # shouldn't happen — VALID_TAGS should all be seeded
                conn.execute(
                    "INSERT INTO item_tags (item_id, tag_id, fit_score) VALUES (?, ?, ?)",
                    (row["id"], tid, score),
                )
                conn.execute(
                    """UPDATE tags SET article_count = article_count + 1,
                                       last_seen_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (tid,),
                )

            conn.execute("UPDATE items SET needs_retag = 0 WHERE id = ?", (row["id"],))
            tag_str = ", ".join(f"{t}({s})" for t, s in scored)
            print(f"  [{row['id']}] {tag_str}")


def main():
    embed_pass()
    tag_pass()


if __name__ == "__main__":
    main()