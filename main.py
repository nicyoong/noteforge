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