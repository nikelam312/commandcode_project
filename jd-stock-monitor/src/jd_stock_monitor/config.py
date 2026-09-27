"""Validated configuration for the single-product JD stock monitor."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class ConfigError(ValueError):
    """Raised when the monitor configuration is incomplete or unsafe."""


@dataclass(frozen=True)
class MonitorConfig:
    product_id: str
    url: str
    variant: str
    region: str
    district: str
    proxy_url: str | None
    timeout_ms: int = 45000
    wait_ms: int = 2500


def load_config(path: str | Path) -> MonitorConfig:
    config_path = Path(path)
    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read TOML config: {exc}") from exc

    try:
        product = raw["product"]
        location = raw["location"]
        fetch = raw.get("fetch", {})
        product_id = str(product["id"]).strip()
        url = str(product["url"]).strip()
        variant = str(product["variant"]).strip()
        region = str(location["region"]).strip().upper()
        district = str(location["district"]).strip()
        proxy_value = fetch.get("proxy_url")
        proxy_url = str(proxy_value).strip() if proxy_value else None
        timeout_ms = int(fetch.get("timeout_ms", 45000))
        wait_ms = int(fetch.get("wait_ms", 2500))
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"missing or invalid required setting: {exc}") from exc

    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "mitem.jd.hk":
        raise ConfigError("product URL must be an HTTPS mitem.jd.hk URL")
    page_product_id = parsed.path.rstrip("/").rsplit("/", 1)[-1].split(".", 1)[0]
    if product_id != page_product_id:
        raise ConfigError("product ID does not match the product URL")
    if not variant or any(not term.strip() for term in variant.split("|")):
        raise ConfigError("variant must contain one or more non-empty terms")
    if region != "HK":
        raise ConfigError("region must be HK")
    if district.casefold() not in {"wan chai", "wan chai district", "灣仔", "湾仔"}:
        raise ConfigError("district must be Wan Chai")
    if not proxy_url:
        raise ConfigError("proxy_url is required; direct connections are disabled")
    if proxy_url:
        proxy = urlsplit(proxy_url)
        if proxy.scheme not in {"http", "https"} or not proxy.hostname or proxy.username or proxy.password:
            raise ConfigError("proxy_url must be an unauthenticated HTTP(S) proxy URL")
    if timeout_ms < 5000 or wait_ms < 0:
        raise ConfigError("fetch timeouts are outside the safe range")

    return MonitorConfig(
        product_id=product_id,
        url=url,
        variant=variant,
        region=region,
        district="Wan Chai",
        proxy_url=proxy_url,
        timeout_ms=timeout_ms,
        wait_ms=wait_ms,
    )
