from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int)


class FunctionWorker(QRunnable):
    """
    Run a Python callable in a thread pool.
    - Emits finished(result) or error(str)
    - Optional progress callback: callable(int)
    """
    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))


@dataclass(frozen=True)
class ExportResult:
    path: str
    count: int


@dataclass(frozen=True)
class ImportResult:
    inserted: int
    updated: int
