from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

APP_NAME = "Noteforge"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_data_dir() -> Path:
    # Cross-platform-ish without extra deps.
    home = Path.home()
    # Windows: use %APPDATA% if present
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_NAME
    # macOS/Linux fallback
    return home / f".{APP_NAME.lower()}"


SCHEMA_VERSION = 1


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS meta(
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Full-text search virtual table (requires SQLite built with FTS5; most Python builds include it)
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts
USING fts5(
    title,
    body,
    tags,
    content='notes',
    content_rowid='id',
    tokenize='unicode61'
);

-- Triggers to keep notes_fts in sync with notes
CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, body, tags) VALUES (new.id, new.title, new.body, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, body, tags) VALUES('delete', old.id, old.title, old.body, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, body, tags) VALUES('delete', old.id, old.title, old.body, old.tags);
    INSERT INTO notes_fts(rowid, title, body, tags) VALUES (new.id, new.title, new.body, new.tags);
END;
"""

@dataclass(frozen=True)
class Note:
    id: int
    title: str
    body: str
    tags: str
    created_at: str
    updated_at: str


class NoteDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(self.db_path))
        self.con.row_factory = sqlite3.Row
        self._init_db()
    
    def close(self) -> None:
        try:
            self.con.close()
        except Exception:
            pass
    
    def _init_db(self) -> None:
        cur = self.con.cursor()
        cur.executescript(SCHEMA_SQL)
        cur.execute("SELECT value FROM meta WHERE key='schema_version'")
        row = cur.fetchone()
        if row is None:
            cur.execute("INSERT INTO meta(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
        self.con.commit()

        # Validate FTS5 availability early for clearer error messages.
        try:
            cur.execute("SELECT notes_fts('test')")
        except sqlite3.OperationalError as e:
            # notes_fts('test') returns error normally; better check by running a match query
            try:
                cur.execute("SELECT rowid FROM notes_fts WHERE notes_fts MATCH 'test' LIMIT 1")
            except sqlite3.OperationalError as e2:
                raise RuntimeError(
                    "SQLite FTS5 is not available in this Python/SQLite build. "
                    "Try a different Python distribution or rebuild SQLite with FTS5."
                ) from e2
    
    def _row_to_note(self, r: sqlite3.Row) -> Note:
        return Note(
            id=int(r["id"]),
            title=str(r["title"]),
            body=str(r["body"]),
            tags=str(r["tags"]),
            created_at=str(r["created_at"]),
            updated_at=str(r["updated_at"]),
        )
    
    def create_note(self, title: str = "Untitled", body: str = "", tags: str = "") -> int:
        now = utc_now_iso()
        cur = self.con.cursor()
        cur.execute(
            "INSERT INTO notes(title, body, tags, created_at, updated_at) VALUES(?,?,?,?,?)",
            (title.strip() or "Untitled", body, tags, now, now),
        )
        self.con.commit()
        return int(cur.lastrowid)
    
    def get_note(self, note_id: int) -> Note | None:
        cur = self.con.cursor()
        cur.execute("SELECT * FROM notes WHERE id=?", (note_id,))
        row = cur.fetchone()
        return self._row_to_note(row) if row else None

    def update_note(self, note_id: int, title: str, body: str, tags: str) -> None:
        now = utc_now_iso()
        self.con.execute(
            "UPDATE notes SET title=?, body=?, tags=?, updated_at=? WHERE id=?",
            (title.strip() or "Untitled", body, tags, now, note_id),
        )
        self.con.commit()

    def delete_note(self, note_id: int) -> None:
        self.con.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.con.commit()
    
    def list_notes(self, search: str = "", tag_filter: str = "") -> list[Note]:
        """
        - search: full-text query. We use a simple strategy:
          - if empty -> list all notes ordered by updated desc
          - else -> FTS MATCH across title/body/tags
        - tag_filter: substring filter on tags (comma-separated), for quick narrowing.
        """
        search = (search or "").strip()
        tag_filter = (tag_filter or "").strip().lower()

        cur = self.con.cursor()

        if not search:
            if tag_filter:
                cur.execute(
                    """
                    SELECT * FROM notes
                    WHERE LOWER(tags) LIKE ?
                    ORDER BY updated_at DESC
                    """,
                    (f"%{tag_filter}%",),
                )
            else:
                cur.execute("SELECT * FROM notes ORDER BY updated_at DESC")
            return [self._row_to_note(r) for r in cur.fetchall()]

        # Basic FTS query sanitization:
        # - Wrap in quotes to treat as a phrase by default
        # - Allow advanced users to type FTS operators (AND/OR/NEAR/*) if they want
        fts_query = search
        if any(tok in search for tok in ('"', " AND ", " OR ", " NOT ", " NEAR ", "*", ":", "(", ")")):
            # assume user knows what they're doing
            pass
        else:
            fts_query = f'"{search}"'

        if tag_filter:
            cur.execute(
                """
                SELECT n.*
                FROM notes_fts f
                JOIN notes n ON n.id = f.rowid
                WHERE f MATCH ?
                  AND LOWER(n.tags) LIKE ?
                ORDER BY n.updated_at DESC
                """,
                (fts_query, f"%{tag_filter}%"),
            )
        else:
            cur.execute(
                """
                SELECT n.*
                FROM notes_fts f
                JOIN notes n ON n.id = f.rowid
                WHERE f MATCH ?
                ORDER BY n.updated_at DESC
                """,
                (fts_query,),
            )
        return [self._row_to_note(r) for r in cur.fetchall()]
    def all_notes_as_dicts(self) -> list[dict[str, Any]]:
        cur = self.con.cursor()
        cur.execute("SELECT * FROM notes ORDER BY updated_at DESC")
        return [dict(r) for r in cur.fetchall()]
    