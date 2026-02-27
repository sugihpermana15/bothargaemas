from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from scraper import FullGoldPrices, VendorPriceRow, VendorPriceTable

logger = logging.getLogger(__name__)


def format_rupiah(value: int) -> str:
    """Format integer as Indonesian Rupiah with thousand separators using dots.

    Example: 74536000 -> 'Rp 74.536.000'
    """
    if value < 0:
        return f"-Rp {format_rupiah(abs(value))[3:]}"
    grouped = f"{value:,}".replace(",", ".")
    return f"Rp {grouped}"


def _format_timezone_offset(dt: datetime) -> str:
    offset = dt.strftime("%z")  # e.g. +0700
    if len(offset) == 5 and (offset.startswith("+") or offset.startswith("-")):
        return f"{offset[:3]}:{offset[3:]}"  # +07:00
    return offset or ""


def _format_datetime_parts(dt: datetime) -> tuple[str, str, str]:
    # Prefer Indonesia/Jakarta timezone naming when available.
    # On Windows, the local tzname can be verbose (e.g. 'SE Asia Standard Time').
    # We normalize to WIB/WITA/WIT based on UTC offset.
    dt_local = dt.astimezone()
    try:
        from zoneinfo import ZoneInfo  # Python 3.9+

        dt_local = dt.astimezone(ZoneInfo("Asia/Jakarta"))
    except Exception:
        pass

    date_part = dt_local.date().isoformat()
    time_part = dt_local.strftime("%H:%M:%S")

    tz_offset = _format_timezone_offset(dt_local)

    # Normalize Indonesia timezones by offset.
    indo_map = {
        "+07:00": ("WIB", "Jakarta"),
        "+08:00": ("WITA", "Makassar"),
        "+09:00": ("WIT", "Jayapura"),
    }
    tz_utc = f"UTC{tz_offset}" if tz_offset else ""
    if tz_offset in indo_map:
        abbr, city = indo_map[tz_offset]
        tz_part = f"{abbr} ({city}, {tz_utc})" if tz_utc else f"{abbr} ({city})"
    else:
        tz_name = dt_local.tzname() or ""
        if tz_name and tz_utc:
            tz_part = f"{tz_name} ({tz_utc})"
        else:
            tz_part = tz_name or tz_utc

    return date_part, time_part, tz_part


def build_message(
    weight_grams: int,
    sell_price: int,
    buyback_price: int,
    observed_at: datetime,
    source_url: str,
) -> str:
    date_part, time_part, tz_part = _format_datetime_parts(observed_at)
    return (
        "GALERI24 — UPDATE HARGA EMAS\n"
        "────────────────────────\n"
        f"Berat         : {weight_grams} gram\n"
        f"Harga jual    : {format_rupiah(sell_price)}\n"
        f"Harga buyback : {format_rupiah(buyback_price)}\n"
        f"Tanggal update: {date_part}\n"
        f"Jam update    : {time_part}\n"
        f"Zona waktu    : {tz_part}\n"
        f"Sumber        : {source_url}"
    )


def _sleep_backoff(base_seconds: float, attempt: int) -> None:
    time.sleep(base_seconds * (2 ** (attempt - 1)))


def build_realtime_message(
    weight_grams: int,
    sell_price: int,
    buyback_price: int,
    observed_at: datetime,
    source_url: str,
) -> str:
    date_part, time_part, tz_part = _format_datetime_parts(observed_at)
    return (
        "GALERI24 — HARGA EMAS (REALTIME)\n"
        "Perintah      : /cekharga\n"
        "────────────────────────\n"
        f"Berat         : {weight_grams} gram\n"
        f"Harga jual    : {format_rupiah(sell_price)}\n"
        f"Harga buyback : {format_rupiah(buyback_price)}\n"
        f"Tanggal cek   : {date_part}\n"
        f"Jam cek       : {time_part}\n"
        f"Zona waktu    : {tz_part}\n"
        f"Sumber        : {source_url}"
    )


def _format_weight(weight_text: str) -> str:
    w = (weight_text or "").strip()
    if not w:
        return "-"
    if w.lower().endswith("g"):
        return w
    return f"{w} g"


def _format_vendor_table(table: VendorPriceTable) -> str:
    # Keep lines compact to stay well within Telegram message limit.
    lines: list[str] = []
    header = table.title.strip() if table.title else table.vendor_id
    lines.append(header)
    if table.updated_label:
        lines.append(table.updated_label)
    lines.append("Berat | Jual | Buyback")

    for row in table.rows:
        lines.append(
            f"{_format_weight(row.weight_text)} | {format_rupiah(row.sell_price)} | {format_rupiah(row.buyback_price)}"
        )

    return "\n".join(lines)


def build_full_message(prices: FullGoldPrices) -> str:
    date_part, time_part, tz_part = _format_datetime_parts(prices.observed_at)
    blocks = [
        "UPDATE HARGA EMAS\n────────────────────────",
        f"Tanggal update: {date_part}",
        f"Jam update    : {time_part}",
        f"Zona waktu    : {tz_part}",
        "",
    ]
    for table in prices.tables:
        blocks.append(_format_vendor_table(table))
        blocks.append("")
    blocks.append(f"Sumber        : {prices.source_url}")
    return "\n".join(blocks).rstrip()


def build_full_realtime_message(prices: FullGoldPrices) -> str:
    date_part, time_part, tz_part = _format_datetime_parts(prices.observed_at)
    blocks = [
        "HARGA EMAS (REALTIME)\nPerintah      : /cekharga\n────────────────────────",
        f"Tanggal cek   : {date_part}",
        f"Jam cek       : {time_part}",
        f"Zona waktu    : {tz_part}",
        "",
    ]
    for table in prices.tables:
        blocks.append(_format_vendor_table(table))
        blocks.append("")
    blocks.append(f"Sumber        : {prices.source_url}")
    return "\n".join(blocks).rstrip()


def build_vendor_realtime_message(
    prices: FullGoldPrices,
    vendor_id: str,
    command: str,
) -> str:
    date_part, time_part, tz_part = _format_datetime_parts(prices.observed_at)

    table = next((t for t in prices.tables if t.vendor_id == vendor_id), None)
    if table is None:
        return (
            "HARGA EMAS (REALTIME)\n"
            f"Perintah      : {command}\n"
            "────────────────────────\n"
            f"Vendor        : {vendor_id}\n"
            "Data tidak ditemukan di sumber saat ini.\n"
            f"Sumber        : {prices.source_url}"
        )

    blocks = [
        f"{vendor_id} — HARGA EMAS (REALTIME)\nPerintah      : {command}\n────────────────────────",
        f"Tanggal cek   : {date_part}",
        f"Jam cek       : {time_part}",
        f"Zona waktu    : {tz_part}",
        "",
        _format_vendor_table(table),
        "",
        f"Sumber        : {prices.source_url}",
    ]
    return "\n".join(blocks).rstrip()


def send_telegram_message(
    token: str,
    chat_id: str,
    text: str,
    timeout_seconds: int,
    max_retries: int,
    backoff_base_seconds: float,
    message_thread_id: int | None = None,
) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if message_thread_id is not None:
        payload["message_thread_id"] = message_thread_id

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=payload, timeout=timeout_seconds)
            if 200 <= resp.status_code < 300:
                logger.info("Telegram sent (status=%s)", resp.status_code)
                return

            body_preview = (resp.text or "").strip().replace("\n", " ")
            if len(body_preview) > 300:
                body_preview = body_preview[:300] + "…"

            raise RuntimeError(
                f"Telegram send failed status={resp.status_code} body={body_preview}"
            )
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                logger.warning(
                    "Telegram send attempt %s/%s failed: %s. Retrying...",
                    attempt,
                    max_retries,
                    exc,
                )
                _sleep_backoff(backoff_base_seconds, attempt)
                continue

            logger.error("Telegram send failed after %s attempts", max_retries)
            raise

    if last_error:
        raise last_error


def get_telegram_updates(
    token: str,
    offset: Optional[int],
    long_poll_timeout_seconds: int,
    request_timeout_seconds: int,
    max_retries: int,
    backoff_base_seconds: float,
) -> List[Dict[str, Any]]:
    """Fetch Telegram updates using getUpdates with long polling.

    Returns a list of update objects.
    """
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params: Dict[str, Any] = {
        "timeout": long_poll_timeout_seconds,
        "allowed_updates": ["message"],
    }
    if offset is not None:
        params["offset"] = offset

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=request_timeout_seconds)
            if resp.status_code == 409:
                # Another getUpdates is active somewhere (or webhook conflict).
                # This is not transient until the other consumer stops.
                body_preview = (resp.text or "").strip().replace("\n", " ")
                if len(body_preview) > 300:
                    body_preview = body_preview[:300] + "…"
                logger.warning(
                    "Telegram getUpdates conflict (409): %s. "
                    "Ensure only ONE instance uses getUpdates for this token.",
                    body_preview,
                )
                time.sleep(10)
                return []

            if not (200 <= resp.status_code < 300):
                body_preview = (resp.text or "").strip().replace("\n", " ")
                if len(body_preview) > 300:
                    body_preview = body_preview[:300] + "…"
                raise RuntimeError(
                    f"Telegram getUpdates failed status={resp.status_code} body={body_preview}"
                )

            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(f"Telegram getUpdates not ok: {data}")

            result = data.get("result")
            if not isinstance(result, list):
                raise RuntimeError(f"Telegram getUpdates invalid result type: {type(result)}")
            return result
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                logger.warning(
                    "Telegram getUpdates attempt %s/%s failed: %s. Retrying...",
                    attempt,
                    max_retries,
                    exc,
                )
                _sleep_backoff(backoff_base_seconds, attempt)
                continue
            logger.error("Telegram getUpdates failed after %s attempts", max_retries)
            raise

    if last_error:
        raise last_error

    return []
