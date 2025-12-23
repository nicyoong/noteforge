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