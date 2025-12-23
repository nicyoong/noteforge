from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from database import Note, NoteDB

def _fmt_dt(iso_str: str) -> str:
    try:
        dt_utc = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone()
        return dt_local.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str


@dataclass
class NoteRow:
    id: int
    title: str
    tags: str
    updated_at: str

class NotesTableModel(QAbstractTableModel):
    COL_TITLE = 0
    COL_TAGS = 1
    COL_UPDATED = 2

    headers = ["Title", "Tags", "Updated"]

    def __init__(self, db: NoteDB):
        super().__init__()
        self.db = db
        self._rows: list[NoteRow] = []
        self._search = ""
        self._tag_filter = ""

    def set_filters(self, search: str, tag_filter: str) -> None:
        self._search = search
        self._tag_filter = tag_filter
        self.reload()

    def reload(self) -> None:
        self.beginResetModel()
        notes = self.db.list_notes(search=self._search, tag_filter=self._tag_filter)
        self._rows = [
            NoteRow(id=n.id, title=n.title, tags=n.tags, updated_at=n.updated_at) for n in notes
        ]
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else 3

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(self.headers):
            return self.headers[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_TITLE:
                return row.title
            if col == self.COL_TAGS:
                return row.tags
            if col == self.COL_UPDATED:
                return _fmt_dt(row.updated_at)

        if role == Qt.UserRole:
            return row.id

        return None

    def note_id_at(self, row: int) -> int | None:
        if 0 <= row < len(self._rows):
            return self._rows[row].id
        return None
