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
    