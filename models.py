from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from database import Note, NoteDB

def _fmt_dt(iso_str: str) -> str:
    try:
        # Not perfect, but good enough for display
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str


@dataclass
class NoteRow:
    id: int
    title: str
    tags: str
    updated_at: str
