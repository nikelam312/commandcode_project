"""Bounded retry/backoff HTTP fetch, stdlib-only, proxied by default.

This is the shared replacement for the many ad-hoc retry loops scattered
across the collectors (event_collector ``get()``, jetso ``http_get()`` /
``fetch_article_html``). It honours the crawler_common.proxy settings, so the
bridge is applied automatically.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request

from . import proxy


def get_with_retry(
    url: str,
    retries: int = 2,
    retry_wait_s: float = 5.0,
    timeout: float = 30.0,
    headers: dict | None = None,
) -> bytes:
    """Fetch ``url`` with exponential backoff on connect/timeout/5xx/429."""
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "crawler-common/0.1 (+personal use)"})
    opener = proxy.urllib_opener() or urllib.request.build_opener()
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with opener.open(req, timeout=timeout) as resp:  # type: ignore[arg-type]
                return resp.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in (429,) and not (exc.code >= 500):
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
        if attempt >= retries:
            break
        time.sleep(retry_wait_s * (2 ** attempt))
    raise last or RuntimeError("unreachable")


def get_text(*args, **kwargs) -> str:
    return get_with_retry(*args, **kwargs).decode("utf-8", errors="replace")