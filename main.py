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

    def _wire(self) -> None:
        # Search / tag filter
        self.ui.search.textChanged.connect(self._on_filters_changed)
        self.ui.tag_filter.textChanged.connect(self._on_filters_changed)

        # Selection changes
        sel = self.ui.table.selectionModel()
        sel.selectionChanged.connect(self._on_selection_changed)

        # Buttons / actions
        self.ui.btn_new.clicked.connect(self.new_note)
        self.ui.btn_delete.clicked.connect(self.delete_current_note)

        self.ui.act_new.triggered.connect(self.new_note)
        self.ui.act_delete.triggered.connect(self.delete_current_note)
        self.ui.act_export.triggered.connect(self.export_json)
        self.ui.act_import.triggered.connect(self.import_json)
        self.ui.act_focus_search.triggered.connect(lambda: self.ui.search.setFocus())
        self.ui.act_about.triggered.connect(self.about)

        # Editor changes -> mark dirty + debounce save
        self.ui.title.textChanged.connect(self._mark_dirty)
        self.ui.tags.textChanged.connect(self._mark_dirty)
        self.ui.body.textChanged.connect(self._mark_dirty)

        # Preview updates
        self.ui.title.textChanged.connect(lambda: self.preview_timer.start())
        self.ui.tags.textChanged.connect(lambda: self.preview_timer.start())
        self.ui.body.textChanged.connect(lambda: self.preview_timer.start())
        