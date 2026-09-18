"""Console/log alert helpers shared by watchers and crawlers.

Unifies the two alert styles the projects had: the Apple watcher's boxed
banner + beep + log line, and the crawlers' ``CRAWLER SOURCE FAILED`` line.
Cron runs deliver stdout verbatim, so these functions print only, never write
to a UI.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

try:
    import winsound
except ImportError:  # not Windows / not installed
    winsound = None


def crawler_alert(source: str, detail: str) -> None:
    """Alert that a crawler source failed; no-agent cron echoes stdout."""
    print(f"🚨 CRAWLER SOURCE FAILED: {source} — {detail}")


def append_log(path: str | Path, line: str) -> None:
    """Append ``<timestamp> | line`` to an append-only log file."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} | {line}\n")


def banner(lines: list[str], width: int = 74) -> None:
    """Print a boxed console banner (used for watcher/crawler alerts)."""
    print()
    print("*" * width)
    for line in lines:
        print(line)
    print("*" * width)
    print()


def beep(freq: int = 1200, duration: int = 700, times: int = 1) -> None:
    """Windows beep (silent no-op elsewhere)."""
    if winsound is None:
        return
    try:
        for _ in range(times):
            winsound.Beep(freq, duration)
    except RuntimeError:
        pass