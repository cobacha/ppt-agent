"""SQLite-based history storage for PPT Agent generations."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "data" / "history.db"


@contextmanager
def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generations (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                content TEXT NOT NULL,
                style TEXT NOT NULL,
                slide_count INTEGER NOT NULL,
                slides_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                title TEXT NOT NULL DEFAULT ''
            )
        """)
        # Migration: add columns if missing (for existing DBs)
        try:
            conn.execute("ALTER TABLE generations ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE generations ADD COLUMN title TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        conn.commit()


def create_generation(content: str, style: str, title: str, slides: list[dict[str, Any]], status: str = "generating") -> str:
    gen_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO generations (id, created_at, content, style, slide_count, slides_json, status, title) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (gen_id, now, content, style, len(slides), json.dumps(slides, ensure_ascii=False), status, title),
        )
        conn.commit()
    return gen_id


def update_generation_slides(gen_id: str, slides: list[dict[str, Any]], title: str = ""):
    with _get_conn() as conn:
        if title:
            conn.execute(
                "UPDATE generations SET slides_json = ?, slide_count = ?, title = ? WHERE id = ?",
                (json.dumps(slides, ensure_ascii=False), len(slides), title, gen_id),
            )
        else:
            conn.execute(
                "UPDATE generations SET slides_json = ?, slide_count = ? WHERE id = ?",
                (json.dumps(slides, ensure_ascii=False), len(slides), gen_id),
            )
        conn.commit()


def complete_generation(gen_id: str, status: str = "completed"):
    with _get_conn() as conn:
        conn.execute("UPDATE generations SET status = ? WHERE id = ?", (status, gen_id))
        conn.commit()


def get_active_generation() -> dict[str, Any] | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id, created_at, content, style, slide_count, slides_json, status, title FROM generations WHERE status = 'generating' ORDER BY created_at DESC LIMIT 1",
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["slides"] = json.loads(result.pop("slides_json"))
    return result


def save_generation(content: str, style: str, slides: list[dict[str, Any]]) -> str:
    """Legacy: create a completed generation."""
    title = slides[0].get("title", "") if slides else ""
    return create_generation(content, style, title, slides, status="completed")


def list_generations(limit: int = 20) -> list[dict[str, Any]]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, created_at, content, style, slide_count, slides_json, status, title FROM generations ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    results = []
    for r in rows:
        item = dict(r)
        slides_json = item.pop("slides_json", "[]")
        try:
            slides = json.loads(slides_json)
            if not item.get("title"):
                item["title"] = slides[0].get("title", "") if slides else ""
            item["first_slide_html"] = slides[0].get("html", "") if slides else ""
        except (json.JSONDecodeError, IndexError):
            item["first_slide_html"] = ""
        results.append(item)
    return results


def get_generation(gen_id: str) -> dict[str, Any] | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id, created_at, content, style, slide_count, slides_json, status, title FROM generations WHERE id = ?",
            (gen_id,),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["slides"] = json.loads(result.pop("slides_json"))
    return result


def delete_generation(gen_id: str) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute("DELETE FROM generations WHERE id = ?", (gen_id,))
        conn.commit()
    return cursor.rowcount > 0


def cleanup_stale_generations(max_age_hours: int = 2):
    """Mark generations stuck in 'generating' status as failed after max_age_hours."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
    with _get_conn() as conn:
        conn.execute(
            "UPDATE generations SET status = 'failed' WHERE status = 'generating' AND created_at < ?",
            (cutoff,),
        )
        conn.commit()
