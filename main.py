from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QItemSelection, QItemSelectionModel, QSettings, QSignalBlocker, QThreadPool, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
)

from database import NoteDB, default_data_dir
from models import NotesTableModel
from ui import MainWindowUI

class MainWindow(QMainWindow):
    def __init__(self, db: NoteDB):
        super().__init__()
        self.db = db
        self.ui = MainWindowUI()
        self.ui.setup(self)

        self.thread_pool = QThreadPool.globalInstance()
        self.settings = QSettings("noteforge", "Noteforge")

        self.model = NotesTableModel(db)
        self.ui.table.setModel(self.model)

        self.current_note_id: int | None = None
        self._dirty = False