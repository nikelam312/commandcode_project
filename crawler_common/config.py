"""One .env loader + shared settings for every tool in this workspace.

Credits are never committed: they live in a git-ignored .env. The loader
searches, in order: the current directory, the workspace root, and the legacy
nordvpn_proxy/ / apple-watcher/ folders (where secrets historically lived), so
regardless of where a script is launched it finds the canonical file.
Existing environment variables always win.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _parse_line(line: str):
    line = line.strip().strip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    key, _, value = line.partition("=")
    key, value = key.strip(), value.strip().strip('"').strip("'")
    return (key, value) if key and value else None


def load_env(candidates=()) -> None:
    """Load the first existing .env into os.environ (does not override real env)."""
    search = list(candidates) or [
        Path.cwd() / ".env",
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / "nordvpn_proxy" / ".env",
        PROJECT_ROOT / "apple-watcher" / ".env",
    ]
    for path in search:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            kv = _parse_line(line)
            if kv:
                os.environ.setdefault(kv[0], kv[1])
        return  # first file wins


def get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)