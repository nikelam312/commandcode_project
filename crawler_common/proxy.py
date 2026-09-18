"""Proxy configuration and NordVPN helpers — single source for the workspace.

Two layers:

1. ``PROXY_URL`` / ``PROXY_DISABLED`` — how the collectors route through the
   local HTTP bridge (crawler_common.proxy is the bridge client contract).
2. NordVPN SOCKS5 upstream config + rotation — what the bridge itself (and the
   Apple delivery watcher) uses to reach NordVPN.

Semantics are identical to the helpers the projects used to duplicate:
``request_proxies()`` for requests, ``browser_kwargs()`` for Playwright,
``install_urllib_proxy()`` for urllib-default openers (jetso/notion).
"""

from __future__ import annotations

import os
import threading
import urllib.request

from . import config

DEFAULT_PROXY_URL = "http://127.0.0.1:1181"
DEFAULT_UPSTREAM_PORT = 1080

# Rotating upstream list (mirrors the Apple delivery watcher's historical list).
NORDVPN_HOSTS = [
    "nl.socks.nordhold.net",
    "se.socks.nordhold.net",
    "us.socks.nordhold.net",
    "amsterdam.nl.socks.nordhold.net",
    "stockholm.se.socks.nordhold.net",
    "atlanta.us.socks.nordhold.net",
    "chicago.us.socks.nordhold.net",
    "dallas.us.socks.nordhold.net",
    "los-angeles.us.socks.nordhold.net",
    "new-york.us.socks.nordhold.net",
    "phoenix.us.socks.nordhold.net",
    "san-francisco.us.socks.nordhold.net",
]

_rotation_lock = threading.Lock()
_rotation_index = 0

# --- client-side proxy semantics -------------------------------------------


def proxy_url() -> str:
    return os.environ.get("PROXY_URL", DEFAULT_PROXY_URL)


def enabled() -> bool:
    return os.environ.get("PROXY_DISABLED", "0") == "0" and bool(proxy_url())


def request_proxies() -> dict | None:
    """Proxies dict for the ``requests`` library (``None`` when disabled)."""
    url = proxy_url() if enabled() else None
    return {"http": url, "https": url} if url else None


def browser_kwargs() -> dict:
    """Playwright launch kwargs; includes ``proxy`` only when enabled."""
    url = proxy_url() if enabled() else None
    return {"proxy": {"server": url}} if url else {}


def urllib_opener() -> urllib.request.OpenerDirector | None:
    """A urllib opener through the bridge, or ``None`` when disabled."""
    if not enabled():
        return None
    url = proxy_url()
    no_proxy = os.environ.get("NO_PROXY", "127.0.0.1,localhost")
    os.environ.setdefault("HTTP_PROXY", url)
    os.environ.setdefault("HTTPS_PROXY", url)
    os.environ.setdefault("NO_PROXY", no_proxy)
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": url, "https": url, "no": no_proxy})
    )


def install_urllib_proxy() -> None:
    """Install the bridge as urllib's default opener (no-op when disabled)."""
    opener = urllib_opener()
    if opener is not None:
        urllib.request.install_opener(opener)


# --- NordVPN upstream (bridge + stock checker) -----------------------------


def nvpn_credentials() -> tuple[str, str]:
    return os.environ.get("NORDVPN_USER", ""), os.environ.get("NORDVPN_PASS", "")


def nvpn_upstream_port() -> int:
    try:
        return int(os.environ.get("NORDVPN_PROXY_PORT", DEFAULT_UPSTREAM_PORT))
    except ValueError:
        return DEFAULT_UPSTREAM_PORT


def nvpn_hosts() -> list[str]:
    csv = os.environ.get("NORDVPN_PROXY_HOSTS", "") or os.environ.get("NORDVPN_PROXY_HOST", "")
    hosts = [h.strip() for h in csv.split(",") if h.strip()]
    return hosts or NORDVPN_HOSTS


def next_upstream() -> tuple[str, int]:
    """Next NordVPN (host, port) to use — round-robin, thread-safe."""
    global _rotation_index
    hosts = nvpn_hosts()
    with _rotation_lock:
        host = hosts[_rotation_index % len(hosts)]
        _rotation_index += 1
    return host, nvpn_upstream_port()