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


def export_notes_to_json(path: Path, notes: list[dict[str, Any]]) -> ExportResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "app": "Noteforge",
        "version": 1,
        "notes": notes,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return ExportResult(path=str(path), count=len(notes))


def import_notes_from_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    notes = data.get("notes")
    if not isinstance(notes, list):
        raise ValueError("Invalid file: expected top-level key 'notes' as a list.")
    cleaned: list[dict[str, Any]] = []
    for n in notes:
        if isinstance(n, dict):
            cleaned.append(n)
    return cleaned
