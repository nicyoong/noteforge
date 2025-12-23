# Noteforge

**Noteforge** is a cross-platform, offline Markdown note-taking application built with **Python** and **PySide6**.  
It demonstrates real-world desktop application patterns including Qt’s model/view architecture, SQLite persistence with full-text search, autosave debouncing, and safe UI threading.

---

## Features

- 📝 **Markdown editor with live preview**
- 💾 **SQLite persistence** (WAL mode) with automatic schema initialization
- 🔎 **Full-text search** using SQLite **FTS5**
  - Prefix search for incremental typing
  - Optional advanced FTS operators
- 🏷️ **Tag support** with quick filtering
- ⏱️ **Autosave with debounce** (prevents excessive writes)
- 🧵 **Background import/export** using Qt thread pools
- 🌍 **UTC storage with local-time display**
- 💻 **Cross-platform** (Windows, macOS, Linux)
- 🎛️ **Persistent UI state** (window geometry, splitters, last note)

---

## Screenshots

> *(Optional – add screenshots here for extra polish)*

---

## Architecture Overview

The project is organized as a small but realistic desktop application:

noteforge/
├── main.py # Application entry point & controller logic
├── ui.py # Qt widget construction (pure UI)
├── models.py # QAbstractTableModel (Qt MVC)
├── db.py # SQLite access layer + FTS5 integration
├── workers.py # Background workers (import/export)


### Key Design Decisions

- **Model/View separation** using `QAbstractTableModel`
- **UTC timestamps** in storage, converted to local time for display
- **SQLite FTS5** for fast full-text search with triggers to stay in sync
- **Debounced autosave** to improve UX and performance
- **Thread-safe design**: database writes occur on the main thread

---

## Requirements

- Python **3.10+**
- PySide6

SQLite must be built with **FTS5 support** (most Python distributions include this).

---

## Installation

```bash
git clone https://github.com/yourusername/noteforge.git
cd noteforge
pip install -r requirements.txt
```

If you don’t have a `requirements.txt`, install manually:

`pip install PySide6`

## Import / Export Format

Notes can be exported to and imported from JSON files:

```
{
  "app": "Noteforge",
  "version": 1,
  "notes": [
    {
      "id": 1,
      "title": "Example",
      "body": "Markdown content",
      "tags": "demo,example",
      "created_at": "2025-12-23T15:31:43+00:00",
      "updated_at": "2025-12-23T15:31:50+00:00"
    }
  ]
}
```

- Timestamps are stored in UTC

- Imports merge by ID when possible

## Keyboard Shortcuts

| Action      | Shortcut |
| ----------- | -------- |
| New note    | `Ctrl+N` |
| Delete note | `Delete` |
| Search      | `Ctrl+F` |
| Export      | `Ctrl+E` |
| Import      | `Ctrl+I` |

## Known Limitations

No cloud sync (offline-first by design)

Single-user local database

Markdown rendering uses Qt’s built-in support

