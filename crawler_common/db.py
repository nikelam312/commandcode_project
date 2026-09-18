"""SQLite helpers the collectors share (MySQL backend to be added for Oracle Cloud).

Standardises the repeated ``sqlite3.connect + row_factory=Row`` and the
backup-before-write pattern that every project was re-implementing. Storage
experts say keep one writer; these helpers make that easy.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def connect(path: str | Path, row_factory: bool = True) -> sqlite3.Connection:
    db = sqlite3.connect(str(path))
    if row_factory:
        db.row_factory = sqlite3.Row
    return db


def backup(path: str | Path, name: str | None = None) -> Path:
    """Copy the DB to a timestamped sibling before a write (atomic guard)."""
    src = Path(path)
    if name:
        dst = Path(name)
    else:
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        dst = src.with_name(f"{src.name}.backup-{stamp}")
    shutil.copy2(src, dst)
    return dst