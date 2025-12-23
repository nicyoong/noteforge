from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTableView,
    QTextBrowser,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


class MainWindowUI:
    """
    Pure UI wiring: creates widgets/actions and exposes them for the controller (main.py).
    """
    def setup(self, win: QMainWindow) -> None:
        win.setWindowTitle("Noteforge — Offline Markdown Notes")

        # Central layout
        central = QWidget()
        win.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        self.splitter = QSplitter(Qt.Horizontal)
        root.addWidget(self.splitter)

        # Left: list + search/filter
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search (FTS5)…")
        left_layout.addWidget(self.search)

        self.tag_filter = QLineEdit()
        self.tag_filter.setPlaceholderText("Tag filter (substring)…")
        left_layout.addWidget(self.tag_filter)

        self.table = QTableView()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        left_layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.btn_new = QPushButton("New")
        self.btn_delete = QPushButton("Delete")
        btn_row.addWidget(self.btn_new)
        btn_row.addWidget(self.btn_delete)
        btn_row.addStretch(1)
        left_layout.addLayout(btn_row)

        # Right: editor + preview
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.title = QLineEdit()
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("comma,separated,tags")
        form.addRow(QLabel("Title:"), self.title)
        form.addRow(QLabel("Tags:"), self.tags)
        right_layout.addLayout(form)

        self.editor_split = QSplitter(Qt.Horizontal)

        self.body = QTextEdit()
        self.body.setPlaceholderText("# Markdown note\n\nStart typing…")

        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(True)

        self.editor_split.addWidget(self.body)
        self.editor_split.addWidget(self.preview)
        self.editor_split.setStretchFactor(0, 2)
        self.editor_split.setStretchFactor(1, 2)

        right_layout.addWidget(self.editor_split, 1)

        self.splitter.addWidget(left)
        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        