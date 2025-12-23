from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import (
    QItemSelection,
    QItemSelectionModel,
    QSettings,
    QSignalBlocker,
    QThreadPool,
    QTimer,
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
)

from database import NoteDB, default_data_dir
from models import NotesTableModel
from ui import MainWindowUI
from workers import (
    FunctionWorker,
    export_notes_to_json,
    import_notes_from_json,
    ExportResult,
    ImportResult,
)


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

    def _restore_state(self) -> None:
        geo = self.settings.value("window/geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        state = self.settings.value("window/state")
        if state is not None:
            self.restoreState(state)

        split = self.settings.value("ui/splitter")
        if split is not None:
            self.ui.splitter.restoreState(split)

        es = self.settings.value("ui/editor_split")
        if es is not None:
            self.ui.editor_split.restoreState(es)

        self.ui.search.setText(self.settings.value("filters/search", ""))
        self.ui.tag_filter.setText(self.settings.value("filters/tag", ""))

    def closeEvent(self, event) -> None:
        # Best-effort commit before closing
        self._commit_note()
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/state", self.saveState())
        self.settings.setValue("ui/splitter", self.ui.splitter.saveState())
        self.settings.setValue("ui/editor_split", self.ui.editor_split.saveState())
        self.settings.setValue("filters/search", self.ui.search.text())
        self.settings.setValue("filters/tag", self.ui.tag_filter.text())
        if self.current_note_id is not None:
            self.settings.setValue("notes/last_id", self.current_note_id)
        super().closeEvent(event)

    def _select_initial_note(self) -> None:
        last_id = self.settings.value("notes/last_id")
        if last_id is not None:
            try:
                last_id = int(last_id)
            except Exception:
                last_id = None

        # If we have any notes, select last_id if it exists, else first row.
        if self.model.rowCount() > 0:
            row_to_select = 0
            if last_id is not None:
                for r in range(self.model.rowCount()):
                    if self.model.note_id_at(r) == last_id:
                        row_to_select = r
                        break
            self._select_row(row_to_select)
            return

        # else create one
        self.new_note()

    def _select_row(self, row: int) -> None:
        if row < 0 or row >= self.model.rowCount():
            return
        idx = self.model.index(row, 0)
        self.ui.table.scrollTo(idx)
        self.ui.table.selectRow(row)

    def _on_filters_changed(self) -> None:
        # Commit current edits before reloading list, so search results include latest text.
        self.model.set_filters(
            self.ui.search.text(),
            self.ui.tag_filter.text(),
        )
        if self.model.rowCount() > 0:
            self._select_row(0)
        else:
            self._load_note(None)

    def _on_selection_changed(
        self, selected: QItemSelection, deselected: QItemSelection
    ) -> None:
        # Commit previous note before switching
        self._commit_note()

        indexes = selected.indexes()
        if not indexes:
            self._load_note(None)
            return

        note_id = self.model.data(indexes[0], role=Qt.UserRole)
        try:
            note_id = int(note_id)
        except Exception:
            note_id = None
        self._load_note(note_id)

    def _load_note(self, note_id: int | None) -> None:
        self.current_note_id = note_id
        self._dirty = False

        # Block signals to avoid triggering save/preview timers while loading
        blockers = [
            QSignalBlocker(self.ui.title),
            QSignalBlocker(self.ui.tags),
            QSignalBlocker(self.ui.body),
        ]
        _ = blockers  # keep alive in scope

        if note_id is None:
            self.ui.title.setText("")
            self.ui.tags.setText("")
            self.ui.body.setPlainText("")
            self.ui.preview.setMarkdown("")
            self.ui.status.showMessage("No note selected.", 2500)
            return

        note = self.db.get_note(note_id)
        if note is None:
            self.ui.status.showMessage(
                "Note not found (it may have been deleted).", 3000
            )
            self.model.reload()
            return

        self.ui.title.setText(note.title)
        self.ui.tags.setText(note.tags)
        self.ui.body.setPlainText(note.body)
        self._render_preview()
        self.ui.status.showMessage(f"Loaded note #{note_id}", 1500)

    def _mark_dirty(self) -> None:
        if self.current_note_id is None:
            return
        self._dirty = True
        self.save_timer.start()

    def _commit_note(self) -> None:
        if self.current_note_id is None or not self._dirty:
            return
        note_id = self.current_note_id
        title = self.ui.title.text()
        tags = self.ui.tags.text()
        body = self.ui.body.toPlainText()

        self.db.update_note(note_id, title=title, body=body, tags=tags)
        self._dirty = False

        # Refresh list (keeps ordering by updated_at)
        prev_id = self.current_note_id
        self.model.reload()

        # Try to reselect same note
        if prev_id is not None:
            for r in range(self.model.rowCount()):
                if self.model.note_id_at(r) == prev_id:
                    self._select_row(r)
                    break

        self.ui.status.showMessage("Saved.", 800)

    def _render_preview(self) -> None:
        # Render markdown from editor
        title = self.ui.title.text().strip()
        tags = self.ui.tags.text().strip()
        body = self.ui.body.toPlainText()
        prefix = ""
        if title:
            prefix += f"# {title}\n\n"
        if tags:
            prefix += f"*Tags:* `{tags}`\n\n---\n\n"
        md = prefix + body
        self.ui.preview.setMarkdown(md)

    # Actions
    def new_note(self) -> None:
        self._commit_note()
        new_id = self.db.create_note()
        self.model.reload()
        # select newly created note (should be top due to updated_at)
        for r in range(self.model.rowCount()):
            if self.model.note_id_at(r) == new_id:
                self._select_row(r)
                break
        self.ui.title.setFocus()
        self.ui.title.selectAll()
        self.ui.status.showMessage(f"Created note #{new_id}", 2000)

    def delete_current_note(self) -> None:
        if self.current_note_id is None:
            return
        note_id = self.current_note_id
        title = self.ui.title.text().strip() or "Untitled"

        resp = QMessageBox.question(
            self,
            "Delete note?",
            f"Delete note #{note_id}:\n\n{title}\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        self.db.delete_note(note_id)
        self.current_note_id = None
        self._dirty = False
        self.model.reload()
        if self.model.rowCount() > 0:
            self._select_row(0)
        else:
            self._load_note(None)
        self.ui.status.showMessage(f"Deleted note #{note_id}", 2500)

    def export_json(self) -> None:
        self._commit_note()
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Notes to JSON",
            str(Path.home() / "noteforge_export.json"),
            "JSON (*.json)",
        )
        if not path_str:
            return
        path = Path(path_str)
        notes = self.db.all_notes_as_dicts()

        worker = FunctionWorker(export_notes_to_json, path, notes)
        worker.signals.finished.connect(self._on_export_done)
        worker.signals.error.connect(
            lambda msg: QMessageBox.critical(self, "Export failed", msg)
        )
        self.thread_pool.start(worker)
        self.ui.status.showMessage("Exporting…", 2000)

    def _on_export_done(self, result: object) -> None:
        if isinstance(result, ExportResult):
            QMessageBox.information(
                self,
                "Export complete",
                f"Exported {result.count} notes to:\n{result.path}",
            )
            self.ui.status.showMessage("Export complete.", 2500)

    def import_json(self) -> None:
        self._commit_note()
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Import Notes from JSON", str(Path.home()), "JSON (*.json)"
        )
        if not path_str:
            return
        path = Path(path_str)

        # Background step 1: read/validate json
        worker = FunctionWorker(import_notes_from_json, path)
        worker.signals.finished.connect(self._on_import_data_ready)
        worker.signals.error.connect(
            lambda msg: QMessageBox.critical(self, "Import failed", msg)
        )
        self.thread_pool.start(worker)
        self.ui.status.showMessage("Reading import file…", 2000)

    def _on_import_data_ready(self, notes: object) -> None:
        if not isinstance(notes, list):
            QMessageBox.critical(self, "Import failed", "Invalid file structure.")
            return

        resp = QMessageBox.question(
            self,
            "Import notes?",
            f"File contains {len(notes)} notes.\n\n"
            "Import and merge into your database?\n"
            "(If IDs match, notes will be updated; otherwise inserted.)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if resp != QMessageBox.Yes:
            return

        # Background step 2: import into DB (fast usually, but keep UI responsive)
        def do_import():
            inserted, updated = self.db.import_notes(notes, merge=True)
            return ImportResult(inserted=inserted, updated=updated)

        try:
            inserted, updated = self.db.import_notes(notes, merge=True)
            self._on_import_done(ImportResult(inserted, updated))
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))
        self.ui.status.showMessage("Importing…", 2000)

    def _on_import_done(self, result: object) -> None:
        if isinstance(result, ImportResult):
            self.model.reload()
            if self.model.rowCount() > 0:
                self._select_row(0)
            QMessageBox.information(
                self,
                "Import complete",
                f"Inserted: {result.inserted}\nUpdated: {result.updated}",
            )
            self.ui.status.showMessage("Import complete.", 2500)

    def about(self) -> None:
        QMessageBox.information(
            self,
            "About Noteforge",
            "Noteforge is an offline Markdown note app built with PySide6.\n\n"
            "Highlights:\n"
            "- SQLite persistence + FTS5 full-text search\n"
            "- Qt Model/View architecture\n"
            "- Autosave debouncing\n"
            "- Background import/export (thread pool)\n",
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Noteforge")

    data_dir = default_data_dir()
    db_path = data_dir / "noteforge.sqlite3"
    db = NoteDB(db_path)

    win = MainWindow(db)
    win.resize(1100, 720)
    win.show()

    code = app.exec()
    db.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
