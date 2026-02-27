from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, Optional, Sequence

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GoldPrice:
    weight_grams: int
    sell_price: int
    buyback_price: int
    observed_at: datetime
    source_url: str
    method: str  # 'requests' or 'playwright'


@dataclass(frozen=True)
class VendorPriceRow:
    weight_text: str  # keep original string from page (e.g. '0.5', '1', '25')
    sell_price: int
    buyback_price: int


@dataclass(frozen=True)
class VendorPriceTable:
    vendor_id: str  # matches the HTML id (e.g. 'GALERI 24', 'ANTAM', 'UBS')
    title: str  # human title (e.g. 'Harga ANTAM')
    updated_label: str | None  # e.g. 'Diperbarui Jumat, 27 Februari 2026'
    rows: tuple[VendorPriceRow, ...]


@dataclass(frozen=True)
class FullGoldPrices:
    observed_at: datetime
    source_url: str
    method: str  # 'requests' or 'playwright'
    tables: tuple[VendorPriceTable, ...]


_RP_RE = re.compile(r"Rp", re.IGNORECASE)


def parse_rupiah_to_int(text: str) -> int:
    digits = re.sub(r"\D+", "", text)
    if not digits:
        raise ValueError(f"Cannot parse Rupiah value from: {text!r}")
    return int(digits)


def parse_weight_text(text: str) -> str:
    """Normalize weight cell text.

    The page typically returns values like '0.5', '1', '25'.
    We keep it as a string to preserve fractional weights exactly.
    """
    value = (text or "").strip()
    if not value:
        raise ValueError("Empty weight text")
    return value


def _extract_vendor_table_from_soup(soup: BeautifulSoup, vendor_id: str) -> VendorPriceTable:
    root = soup.find(id=vendor_id)
    if root is None:
        raise ValueError(f"Could not find vendor section id={vendor_id!r}")

    # Title typically: 'Harga ANTAM' / 'Harga UBS' / 'Harga GALERI 24'
    title_el = root.select_one("div.bg-primary-100")
    title = title_el.get_text(" ", strip=True) if title_el else f"Harga {vendor_id}"

    updated_el = root.select_one("div.text-lg.font-semibold")
    updated_label = updated_el.get_text(" ", strip=True) if updated_el else None
    if updated_label == "":
        updated_label = None

    # Rows live under a 'min-w' container; first grid row is header.
    rows: list[VendorPriceRow] = []
    for grid in root.select("div.grid.grid-cols-5"):
        # Each row has 3 cells: weight, sell, buyback.
        # Header row contains text 'Berat', 'Harga Jual', 'Harga Buyback'.
        cells = [c.get_text(" ", strip=True) for c in grid.find_all("div", recursive=False)]
        if len(cells) < 3:
            continue
        first = (cells[0] or "").strip().lower()
        if first in {"berat", "weight"}:
            continue

        weight_text = parse_weight_text(cells[0])
        sell_price = parse_rupiah_to_int(cells[1])
        buyback_price = parse_rupiah_to_int(cells[2])
        rows.append(
            VendorPriceRow(
                weight_text=weight_text,
                sell_price=sell_price,
                buyback_price=buyback_price,
            )
        )

    if not rows:
        raise ValueError(f"Found vendor section {vendor_id!r} but no price rows parsed")

    return VendorPriceTable(
        vendor_id=vendor_id,
        title=title,
        updated_label=updated_label,
        rows=tuple(rows),
    )


def _extract_full_prices_from_html(
    html: str,
    source_url: str,
    method: str,
    vendor_ids: Sequence[str],
) -> FullGoldPrices:
    soup = BeautifulSoup(html, "html.parser")
    tables = tuple(_extract_vendor_table_from_soup(soup, vendor_id=v) for v in vendor_ids)
    observed_at = datetime.now().astimezone()
    return FullGoldPrices(
        observed_at=observed_at,
        source_url=source_url,
        method=method,
        tables=tables,
    )


def _extract_25g_from_html(html: str, source_url: str, method: str) -> GoldPrice:
    soup = BeautifulSoup(html, "html.parser")
    divs = soup.find_all("div")

    weight_index: Optional[int] = None
    for idx, div in enumerate(divs):
        if div.get_text(strip=True) == "25":
            weight_index = idx
            break

    if weight_index is None:
        raise ValueError("Could not find weight '25' element in HTML")

    prices: list[int] = []
    for div in divs[weight_index + 1 :]:
        t = div.get_text(strip=True)
        if not t:
            continue
        if _RP_RE.search(t):
            try:
                prices.append(parse_rupiah_to_int(t))
            except ValueError:
                continue
        if len(prices) >= 2:
            break

    if len(prices) < 2:
        raise ValueError("Found weight '25' but could not extract both prices")

    observed_at = datetime.now().astimezone()
    return GoldPrice(
        weight_grams=25,
        sell_price=prices[0],
        buyback_price=prices[1],
        observed_at=observed_at,
        source_url=source_url,
        method=method,
    )


def _sleep_backoff(base_seconds: float, attempt: int) -> None:
    time.sleep(base_seconds * (2 ** (attempt - 1)))


def _fetch_html_requests(url: str, timeout_seconds: int) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=timeout_seconds)
    resp.raise_for_status()
    return resp.text


def _fetch_html_playwright(url: str, timeout_seconds: int) -> str:
    """Fetch HTML after JS rendering using Playwright.

    Note: requires `playwright install` on the machine.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Playwright not available. Install deps and run: playwright install"
        ) from exc

    timeout_ms = max(1, int(timeout_seconds * 1000))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
            html = page.content()
            return html
        finally:
            browser.close()


def fetch_price(
    url: str,
    timeout_seconds: int,
    max_retries: int,
    backoff_base_seconds: float,
) -> GoldPrice:
    """Fetch 25g gold price (sell + buyback).

    Strategy:
      1) Try requests + BS4 parse
      2) If parse fails (likely JS-rendered), fallback to Playwright then parse

    Both stages have retry/backoff so it won't crash on transient failures.
    """

    # Stage A: requests
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Fetching via requests (attempt %s/%s)", attempt, max_retries)
            html = _fetch_html_requests(url, timeout_seconds)
            price = _extract_25g_from_html(html, url, method="requests")
            logger.info(
                "Parsed via requests: sell=%s buyback=%s",
                price.sell_price,
                price.buyback_price,
            )
            return price
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                logger.warning(
                    "Requests stage failed attempt %s/%s: %s. Retrying...",
                    attempt,
                    max_retries,
                    exc,
                )
                _sleep_backoff(backoff_base_seconds, attempt)
                continue
            logger.warning("Requests stage exhausted: %s", exc)

    # Stage B: playwright fallback
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "Fetching via Playwright fallback (attempt %s/%s)", attempt, max_retries
            )
            html = _fetch_html_playwright(url, timeout_seconds)
            price = _extract_25g_from_html(html, url, method="playwright")
            logger.info(
                "Parsed via Playwright: sell=%s buyback=%s",
                price.sell_price,
                price.buyback_price,
            )
            return price
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                logger.warning(
                    "Playwright stage failed attempt %s/%s: %s. Retrying...",
                    attempt,
                    max_retries,
                    exc,
                )
                _sleep_backoff(backoff_base_seconds, attempt)
                continue
            logger.error("Playwright stage exhausted: %s", exc)

    assert last_exc is not None
    raise last_exc


def fetch_full_prices(
    url: str,
    vendor_ids: Sequence[str] = ("GALERI 24", "ANTAM", "UBS"),
    timeout_seconds: int = 15,
    max_retries: int = 3,
    backoff_base_seconds: float = 1.5,
) -> FullGoldPrices:
    """Fetch full tables for multiple vendors (GALERI 24 / ANTAM / UBS).

    Uses the same 2-stage strategy as `fetch_price`:
      - requests first
      - Playwright fallback if parsing fails
    """

    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "Fetching full prices via requests (attempt %s/%s)", attempt, max_retries
            )
            html = _fetch_html_requests(url, timeout_seconds)
            prices = _extract_full_prices_from_html(
                html=html,
                source_url=url,
                method="requests",
                vendor_ids=vendor_ids,
            )
            logger.info(
                "Parsed full prices via requests: vendors=%s", ",".join(vendor_ids)
            )
            return prices
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                logger.warning(
                    "Full requests stage failed attempt %s/%s: %s. Retrying...",
                    attempt,
                    max_retries,
                    exc,
                )
                _sleep_backoff(backoff_base_seconds, attempt)
                continue
            logger.warning("Full requests stage exhausted: %s", exc)

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "Fetching full prices via Playwright fallback (attempt %s/%s)",
                attempt,
                max_retries,
            )
            html = _fetch_html_playwright(url, timeout_seconds)
            prices = _extract_full_prices_from_html(
                html=html,
                source_url=url,
                method="playwright",
                vendor_ids=vendor_ids,
            )
            logger.info(
                "Parsed full prices via Playwright: vendors=%s", ",".join(vendor_ids)
            )
            return prices
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                logger.warning(
                    "Full Playwright stage failed attempt %s/%s: %s. Retrying...",
                    attempt,
                    max_retries,
                    exc,
                )
                _sleep_backoff(backoff_base_seconds, attempt)
                continue
            logger.error("Full Playwright stage exhausted: %s", exc)

    assert last_exc is not None
    raise last_exc
