"""crawl4ai render/extract worker (runs under the isolated crawl4ai venv).

Never imported by the collectors: ``crawl4ai_fallback`` runs this file as a
subprocess with ``~/.venvs/crawl4ai/bin/python`` so the stdlib-only collectors
never take a dependency on crawl4ai or its Playwright/patchright stack.

Usage (called by the bridge, not by hand):

    crawl4ai-venv/bin/python crawl4ai_worker.py --url URL --out PATH \
        [--mode markdown|fit|html|cleaned|json] [--schema JSON] \
        [--proxy URL|none] [--timeout 60] [--scroll] [--threshold 0.48]

The result is written as a single JSON object to ``--out`` (never to stdout,
because crawl4ai logs to stdout and would corrupt it). Exit code is 0 whenever
a payload was written, 1 when even that failed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import traceback

BLOCK_MARKERS = ("security check", "byteplus", "cf-browser-verification", "just a moment")


def _write(out_path: str, payload: dict) -> None:
    tmp = f"{out_path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    os.replace(tmp, out_path)


def _pruner(threshold: float):
    """Return the pruning content filter available in this crawl4ai version."""
    try:
        from crawl4ai.content_filter_strategy import PruningContentFilterLXML as Pruner
    except Exception:
        from crawl4ai.content_filter_strategy import PruningContentFilter as Pruner
    return Pruner(threshold=threshold, threshold_type="fixed", min_word_threshold=0)


async def run(args: argparse.Namespace) -> dict:
    from crawl4ai import (AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig,
                          JsonCssExtractionStrategy, ProxyConfig)
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    browser_kwargs: dict = {
        "headless": True,
        "verbose": False,
        "enable_stealth": True,
        "viewport": {"width": 1366, "height": 900},
    }
    if args.proxy and args.proxy != "none":
        browser_kwargs["proxy_config"] = ProxyConfig(server=args.proxy)

    run_kwargs: dict = {
        "cache_mode": CacheMode.BYPASS,
        "page_timeout": int(args.timeout * 1000),
        "wait_until": "domcontentloaded",
        "delay_before_return_html": args.settle,
        "locale": args.locale,
        "verbose": False,
    }
    if args.scroll:
        run_kwargs.update(scan_full_page=True, scroll_delay=0.4)
    if args.mode == "fit":
        run_kwargs["markdown_generator"] = DefaultMarkdownGenerator(
            content_filter=_pruner(args.threshold))
    if args.mode == "json":
        run_kwargs["extraction_strategy"] = JsonCssExtractionStrategy(json.loads(args.schema))

    async with AsyncWebCrawler(config=BrowserConfig(**browser_kwargs)) as crawler:
        result = await crawler.arun(args.url, config=CrawlerRunConfig(**run_kwargs))

    payload: dict = {
        "ok": bool(result.success),
        "url": args.url,
        "status": result.status_code,
        "mode": args.mode,
        "blocked": False,
        "chars": 0,
        "content": None,
        "rows": None,
        "error": result.error_message or "",
    }

    if args.mode == "json":
        raw = result.extracted_content or "[]"
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError:
            rows = []
        payload.update(rows=len(rows), content=raw, chars=len(raw))
        return payload

    markdown = result.markdown
    raw_md = getattr(markdown, "raw_markdown", "") or ""
    if args.mode == "markdown":
        content = raw_md
    elif args.mode == "fit":
        content = (getattr(markdown, "fit_markdown", "") or "") or raw_md
    elif args.mode == "cleaned":
        content = result.cleaned_html or ""
    else:  # html — full rendered DOM, what the regex date-extractors expect
        content = result.html or ""

    probe = f"{content}\n{raw_md}".lower()
    payload["blocked"] = any(marker in probe for marker in BLOCK_MARKERS)
    payload["chars"] = len(content)
    payload["content"] = content
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="crawl4ai worker (JSON to file)")
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", default="fit",
                    choices=["markdown", "fit", "html", "cleaned", "json"])
    ap.add_argument("--schema", default="{}")
    ap.add_argument("--proxy", default=os.environ.get("PROXY_URL") or "http://127.0.0.1:1181")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--settle", type=float, default=2.0, help="seconds to let JS settle")
    ap.add_argument("--threshold", type=float, default=0.48)
    ap.add_argument("--locale", default="zh-HK")
    ap.add_argument("--scroll", action="store_true")
    args = ap.parse_args()

    try:
        payload = asyncio.run(run(args))
    except Exception as exc:  # always leave a parseable payload behind
        payload = {"ok": False, "url": args.url, "status": None, "mode": args.mode,
                   "blocked": False, "chars": 0, "content": None, "rows": None,
                   "error": f"{type(exc).__name__}: {exc}"}
        print(f"[worker] {payload['error']}\n{traceback.format_exc()}", file=sys.stderr)

    try:
        _write(args.out, payload)
    except Exception as exc:
        print(f"[worker] cannot write {args.out}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
