"""Read-only availability checks for a JD mobile-web product page."""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo


class StockState(str, Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    UNAVAILABLE_IN_REGION = "unavailable_in_region"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StockResult:
    state: StockState
    reason: str


@dataclass(frozen=True)
class WebObservation:
    product_id: str
    url: str
    district: str
    destination: str
    state: StockState
    reason: str
    page_title: str
    checked_at: str
    http_status: int | None


_OUT_OF_STOCK = (
    "暂时无货",
    "暫時無貨",
    "无货",
    "無貨",
    "暂时缺货",
    "暫時缺貨",
    "缺货",
    "缺貨",
    "已售罄",
    "售罄",
    "out of stock",
    "sold out",
)
_REGION_UNAVAILABLE = (
    "此商品在所选区域不支持销售",
    "此商品在所选区域暂不支持销售",
    "抱歉，此商品在所选区域暂不支持销售",
    "抱歉，此商品在所选区域不支持销售",
)
_IN_STOCK = (
    "现货",
    "現貨",
    "有货",
    "有貨",
    "in stock",
    "available now",
)
_CHALLENGE = (
    "security check",
    "captcha",
    "验证码",
    "驗證碼",
    "访问过于频繁",
    "訪問過於頻繁",
    "请登录",
    "請登入",
    "请先登录",
    "請先登入",
)
_DISTRICT_ALIASES = {
    "wan chai": ("wan chai", "wanchai", "灣仔", "湾仔"),
    "灣仔": ("wan chai", "wanchai", "灣仔", "湾仔"),
    "湾仔": ("wan chai", "wanchai", "灣仔", "湾仔"),
}


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"\s+", " ", value).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = _normalize(text)
    normalized_phrase = _normalize(phrase)
    pattern = re.escape(normalized_phrase).replace(r"\ ", r"\s*")
    return re.search(pattern, normalized_text) is not None


def _district_aliases(district: str) -> tuple[str, ...]:
    return _DISTRICT_ALIASES.get(_normalize(district), (district,))


def classify_stock(text: str, *, variant: str, district: str) -> StockResult:
    """Classify only explicit stock text for the exact variant and HK district.

    Unrecognized, conflicting, location-mismatched, variant-mismatched, login,
    and anti-bot pages remain UNKNOWN. This intentionally avoids inferring stock
    from a successful page load or enabled-looking purchase controls.
    """
    if not text.strip():
        return StockResult(StockState.UNKNOWN, "empty_page")

    if any(_contains_phrase(text, marker) for marker in _CHALLENGE):
        return StockResult(StockState.UNKNOWN, "login_or_challenge")

    variant_terms = [part.strip() for part in variant.split("|") if part.strip()]
    if not variant_terms or any(not _contains_phrase(text, term) for term in variant_terms):
        return StockResult(StockState.UNKNOWN, "exact_variant_not_visible")

    has_hk = _contains_phrase(text, "Hong Kong") or _contains_phrase(text, "香港") or _contains_phrase(text, "HK")
    has_district = any(_contains_phrase(text, alias) for alias in _district_aliases(district))
    if not has_hk or not has_district:
        return StockResult(StockState.UNKNOWN, "requested_hk_district_not_visible")

    out_markers = [marker for marker in _OUT_OF_STOCK if _contains_phrase(text, marker)]
    in_markers = [marker for marker in _IN_STOCK if _contains_phrase(text, marker)]
    region_unavailable = any(_contains_phrase(text, marker) for marker in _REGION_UNAVAILABLE)
    if region_unavailable and (out_markers or in_markers):
        return StockResult(StockState.UNKNOWN, "conflicting_availability_markers")
    if region_unavailable:
        return StockResult(StockState.UNAVAILABLE_IN_REGION, "not_available_in_selected_region")
    if out_markers and in_markers:
        return StockResult(StockState.UNKNOWN, "conflicting_stock_markers")
    if out_markers:
        return StockResult(StockState.OUT_OF_STOCK, "explicit_out_of_stock_text")
    if in_markers:
        return StockResult(StockState.IN_STOCK, "explicit_in_stock_text")
    return StockResult(StockState.UNKNOWN, "no_explicit_stock_text")


def _click_unique_label(
    page: Any,
    parent: Any,
    selector: str,
    labels: set[str],
    timeout_ms: int = 8000,
) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    while True:
        matches = [
            element
            for element in parent.locator(selector).all()
            if element.inner_text().strip() in labels
        ]
        if len(matches) > 1:
            return False
        if len(matches) == 1:
            matches[0].click(timeout=min(5000, timeout_ms))
            return True
        if time.monotonic() >= deadline:
            return False
        page.wait_for_timeout(100)


def select_hk_wan_chai(page: Any) -> tuple[bool, str, str]:
    """Use JD's visible address picker to select Hong Kong, Wan Chai.

    No account address is entered or saved. The steps are repeated in each
    fresh browser context; ambiguous or missing options fail closed.
    """
    try:
        destination = page.locator("#addrName").inner_text(timeout=5000).strip()
        if "香港" in destination and any(name in destination for name in ("灣仔", "湾仔")):
            return True, destination, "already_selected"

        page.locator("#addrArea").click(timeout=5000)
        layer = page.locator(".plato-ui-addressLayer")
        layer.wait_for(state="visible", timeout=5000)
        if not _click_unique_label(page, layer, ".plato-ui-tabsItem", {"港澳台及海外"}):
            return False, destination, "overseas_tab_missing"
        if not _click_unique_label(
            page, layer, ".plato-ui-cityItem, .plato-ui-hotCityItem", {"中国香港", "中國香港"}
        ):
            return False, destination, "hong_kong_option_missing"
        if not _click_unique_label(
            page, layer, ".plato-ui-cityItem, .plato-ui-hotCityItem", {"湾仔区", "灣仔區"}
        ):
            return False, destination, "wan_chai_district_missing"
        if not _click_unique_label(
            page, layer, ".plato-ui-cityItem, .plato-ui-hotCityItem", {"湾仔", "灣仔"}
        ):
            return False, destination, "wan_chai_area_missing"

        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            destination = page.locator("#addrName").inner_text(timeout=5000).strip()
            confirmed = "香港" in destination and any(
                name in destination for name in ("灣仔", "湾仔")
            )
            if confirmed:
                return True, destination, "selected"
            page.wait_for_timeout(100)
        return False, destination, "destination_not_confirmed"
    except Exception as exc:
        return False, "", f"page_error_{type(exc).__name__}"


def fetch_web_observation(
    *,
    url: str,
    product_id: str,
    variant: str,
    district: str,
    proxy_url: str | None,
    timeout_ms: int = 30000,
    wait_ms: int = 2500,
) -> WebObservation:
    """Open the public product page in mobile emulation and read visible text.

    The configured geolocation is a coarse Wan Chai point. It does not change a
    JD account address or select a physical pickup store; if the page does not
    visibly confirm the requested district, the result stays UNKNOWN.
    """
    from playwright.sync_api import sync_playwright

    checked_at = datetime.now(ZoneInfo("Asia/Hong_Kong")).isoformat(timespec="seconds")
    status: int | None = None
    title = ""
    destination = ""
    try:
        with sync_playwright() as playwright:
            launch_options: dict[str, Any] = {"headless": True}
            if proxy_url:
                launch_options["proxy"] = {"server": proxy_url}
            browser = playwright.chromium.launch(**launch_options)
            try:
                context = browser.new_context(
                    viewport={"width": 390, "height": 844},
                    screen={"width": 390, "height": 844},
                    device_scale_factor=2,
                    is_mobile=True,
                    has_touch=True,
                    locale="zh-HK",
                    timezone_id="Asia/Hong_Kong",
                    geolocation={"latitude": 22.2770, "longitude": 114.1740},
                    permissions=["geolocation"],
                )
                page = context.new_page()

                def route_nonvisual(route: Any) -> None:
                    if route.request.resource_type in {"image", "media", "font"}:
                        route.abort()
                    else:
                        route.continue_()

                # Keep proxy use light: page text and scripts/XHR are needed, but
                # image, media, and font downloads are not needed for this check.
                page.route("**/*", route_nonvisual)
                response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                status = response.status if response else None
                page.wait_for_timeout(wait_ms)
                title = page.title()
                final_url = page.url
                if product_id not in final_url:
                    result = StockResult(StockState.UNKNOWN, "redirected_away_from_product")
                elif status is None or status >= 400:
                    result = StockResult(StockState.UNKNOWN, "http_error")
                else:
                    location_confirmed, destination, location_reason = select_hk_wan_chai(page)
                    if not location_confirmed:
                        result = StockResult(StockState.UNKNOWN, f"location_{location_reason}")
                    else:
                        body_text = page.locator("body").inner_text(timeout=5000)
                        result = classify_stock(body_text, variant=variant, district=district)
                return WebObservation(
                    product_id=product_id,
                    url=final_url,
                    district=district,
                    destination=destination,
                    state=result.state,
                    reason=result.reason,
                    page_title=title,
                    checked_at=checked_at,
                    http_status=status,
                )
            finally:
                browser.close()
    except Exception as exc:
        # Keep logs diagnostic but do not leak page contents, cookies, or headers.
        reason = f"fetch_error:{type(exc).__name__}"
        return WebObservation(
            product_id=product_id,
            url=url,
            district=district,
            destination=destination,
            state=StockState.UNKNOWN,
            reason=reason,
            page_title=title,
            checked_at=checked_at,
            http_status=status,
        )
