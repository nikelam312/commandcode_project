"""Command-line entry point for one-shot JD website checks."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from jd_stock_monitor.config import ConfigError, load_config
from jd_stock_monitor.website import fetch_web_observation


def _default_config() -> Path:
    return Path(__file__).resolve().parents[2] / "config.toml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check one JD HK product page without shopping actions")
    parser.add_argument("--config", type=Path, default=_default_config())
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"configuration_error: {exc}", file=sys.stderr)
        return 2

    observation = fetch_web_observation(
        url=config.url,
        product_id=config.product_id,
        variant=config.variant,
        district=config.district,
        proxy_url=config.proxy_url,
        timeout_ms=config.timeout_ms,
        wait_ms=config.wait_ms,
    )
    payload = {
        **asdict(observation),
        "state": observation.state.value,
        "region": config.region,
        "variant": config.variant,
        "proxy_enabled": bool(config.proxy_url),
    }
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return 0
