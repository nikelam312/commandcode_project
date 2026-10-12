"""Optional JS-render fallback bridge to crawl4ai (stdlib-only).

Collectors are stdlib-only and must not take a dependency on crawl4ai's heavy
Playwright/patchright stack, so this module shells out to the isolated crawl4ai
venv running ``crawl4ai_worker.py`` and reads back a single JSON object.

Contract: every public function is fail-open. When the bridge, the venv or the
browser is missing, or the crawl times out, the caller gets ``None`` and the
collector keeps its existing behaviour.

Configuration (env, all optional):
  CRAWL4AI_PYTHON   interpreter that has crawl4ai   (default ~/.venvs/crawl4ai/bin/python)
  CRAWL4AI_WORKER   worker script path              (default: next to this file)
  CRAWL4AI_DISABLED "1" turns the bridge off everywhere
  PROXY_URL         egress bridge for the browser   (default http://127.0.0.1:1181)

The browser always goes through the local proxy bridge unless the caller passes
proxy=None / "none", matching the collectors' forced-egress rule.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

DEFAULT_PYTHON = os.path.expanduser("~/.venvs/crawl4ai/bin/python")
DEFAULT_PROXY = "http://127.0.0.1:1181"
DEFAULT_TIMEOUT = 90.0

_HERE = os.path.dirname(os.path.abspath(__file__))


def _grace() -> float:
    """Extra seconds allowed on top of the crawl timeout (browser start + shutdown)."""
    try:
        return float(os.environ.get("CRAWL4AI_GRACE_SECONDS", "30"))
    except ValueError:
        return 30.0


def python_path() -> str:
    return os.environ.get("CRAWL4AI_PYTHON") or DEFAULT_PYTHON


def worker_path() -> str:
    return os.environ.get("CRAWL4AI_WORKER") or os.path.join(_HERE, "crawl4ai_worker.py")


def disabled() -> bool:
    return os.environ.get("CRAWL4AI_DISABLED", "0") == "1"


def available() -> bool:
    """True when the interpreter and worker are both present and enabled."""
    if disabled():
        return False
    py, worker = python_path(), worker_path()
    return bool(shutil.which(py) and os.path.isfile(worker))


def diagnostics() -> dict:
    return {"enabled": not disabled(), "available": available(), "python": python_path(),
            "python_exists": bool(shutil.which(python_path())), "worker": worker_path(),
            "worker_exists": os.path.isfile(worker_path()), "proxy": os.environ.get("PROXY_URL") or DEFAULT_PROXY}


def render(url: str, mode: str = "fit", schema: dict | None = None, timeout: float = DEFAULT_TIMEOUT,
           proxy: str | None = DEFAULT_PROXY, scroll: bool = False, locale: str = "zh-HK") -> dict | None:
    """Render/extract ``url``. Returns the worker payload dict, or None on failure.

    mode: "fit" (pruned markdown) | "markdown" (raw markdown) | "html" (rendered DOM)
          | "cleaned" (cleaned HTML) | "json" (CSS-schema extraction, needs ``schema``)
    """
    if not available():
        logger.debug("crawl4ai bridge unavailable; skipping render of %s", url)
        return None

    tmpdir = tempfile.mkdtemp(prefix="c4ai-")
    out_path = os.path.join(tmpdir, "result.json")
    cmd = [python_path(), worker_path(), "--url", url, "--out", out_path, "--mode", mode,
           "--timeout", str(float(timeout)), "--locale", locale]
    if schema is not None:
        cmd += ["--schema", json.dumps(schema)]
    if proxy and proxy != "none":
        cmd += ["--proxy", proxy]
    if scroll:
        cmd += ["--scroll"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + _grace())
    except subprocess.TimeoutExpired:
        logger.warning("crawl4ai bridge timed out after %.0fs: %s", timeout + _grace(), url)
        return None
    except OSError as exc:
        logger.warning("crawl4ai bridge could not run %s: %s", python_path(), exc)
        return None

    try:
        with open(out_path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        tail = (proc.stderr or "").strip().splitlines()[-1:] or [""]
        logger.warning("crawl4ai bridge returned no payload for %s (%s) rc=%s stderr=%s",
                       url, exc, proc.returncode, tail[0][:200])
        return None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if not payload.get("ok"):
        logger.warning("crawl4ai bridge crawl failed for %s: %s", url, payload.get("error"))
    return payload


def fetch_content(url: str, **kwargs) -> str | None:
    """Return rendered content as text (None when unavailable/failed)."""
    payload = render(url, **kwargs)
    if not payload or not payload.get("ok") or payload.get("blocked"):
        return None
    return payload.get("content") or None


def fetch_html(url: str, **kwargs) -> str | None:
    """Rendered DOM HTML — drop-in for collectors that parse HTML with BeautifulSoup/regex."""
    kwargs.setdefault("mode", "html")
    return fetch_content(url, **kwargs)


def fetch_markdown(url: str, fit: bool = True, **kwargs) -> str | None:
    kwargs.setdefault("mode", "fit" if fit else "markdown")
    return fetch_content(url, **kwargs)


def fetch_json(url: str, schema: dict, **kwargs) -> list | None:
    """No-LLM CSS-schema extraction; returns the row list or None."""
    kwargs.setdefault("mode", "json")
    payload = render(url, schema=schema, **kwargs)
    if not payload or not payload.get("ok"):
        return None
    try:
        return json.loads(payload.get("content") or "[]")
    except json.JSONDecodeError:
        return None
