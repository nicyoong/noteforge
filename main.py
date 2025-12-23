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

        # Autosave debounce
        self.save_timer = QTimer(self)
        self.save_timer.setInterval(600)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._commit_note)

        # Live preview debounce (separate so preview feels instant-ish without blocking)
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(150)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self._render_preview)

        self._wire()
        self._restore_state()

        # Load initial list + select last note or create one
        self.model.reload()
        self._select_initial_note()
        