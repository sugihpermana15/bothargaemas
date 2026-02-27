from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv(*_args: object, **_kwargs: object) -> None:
        return None


URL_GALERI24 = "https://galeri24.co.id/harga-emas"


@dataclass(frozen=True)
class AppConfig:
    telegram_token: str
    telegram_chat_ids: tuple[str, ...]
    db_path: str

    poll_interval_seconds: int
    request_timeout_seconds: int

    max_retries: int
    retry_backoff_base_seconds: float

    source_url: str = URL_GALERI24


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid int for {name}: {raw!r}") from exc


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid float for {name}: {raw!r}") from exc


def _get_str(name: str, default: Optional[str] = None) -> Optional[str]:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    return value if value else default


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def load_config() -> AppConfig:
    """Load and validate configuration from environment variables.

    Required:
      - TELEGRAM_TOKEN
      - TELEGRAM_CHAT_ID

    Optional:
      - DB_PATH (default: emasbot.db)
      - POLL_INTERVAL_SECONDS (default: 30)
      - REQUEST_TIMEOUT_SECONDS (default: 15)
      - MAX_RETRIES (default: 3)
      - RETRY_BACKOFF_BASE_SECONDS (default: 1.5)

    Note: will load .env if present.
    """

    load_dotenv(override=False)

    telegram_token = _get_str("TELEGRAM_TOKEN")
    telegram_chat_id_raw = _get_str("TELEGRAM_CHAT_ID")

    if not telegram_token:
        raise RuntimeError("Missing required env var: TELEGRAM_TOKEN")
    if not telegram_chat_id_raw:
        raise RuntimeError("Missing required env var: TELEGRAM_CHAT_ID")

    # Support multiple chat IDs separated by comma, for example:
    #   TELEGRAM_CHAT_ID=6951917620,-1003703084240
    telegram_chat_ids = tuple(
        part.strip()
        for part in telegram_chat_id_raw.split(",")
        if part.strip()
    )
    if not telegram_chat_ids:
        raise RuntimeError("TELEGRAM_CHAT_ID must contain at least one chat id")

    db_path = _get_str("DB_PATH", "emasbot.db") or "emasbot.db"

    poll_interval_seconds = _get_int("POLL_INTERVAL_SECONDS", 30)
    request_timeout_seconds = _get_int("REQUEST_TIMEOUT_SECONDS", 15)

    max_retries = _get_int("MAX_RETRIES", 3)
    retry_backoff_base_seconds = _get_float("RETRY_BACKOFF_BASE_SECONDS", 1.5)

    if poll_interval_seconds <= 0:
        raise RuntimeError("POLL_INTERVAL_SECONDS must be > 0")
    if request_timeout_seconds <= 0:
        raise RuntimeError("REQUEST_TIMEOUT_SECONDS must be > 0")
    if max_retries < 1:
        raise RuntimeError("MAX_RETRIES must be >= 1")
    if retry_backoff_base_seconds <= 0:
        raise RuntimeError("RETRY_BACKOFF_BASE_SECONDS must be > 0")

    return AppConfig(
        telegram_token=telegram_token,
        telegram_chat_ids=telegram_chat_ids,
        db_path=db_path,
        poll_interval_seconds=poll_interval_seconds,
        request_timeout_seconds=request_timeout_seconds,
        max_retries=max_retries,
        retry_backoff_base_seconds=retry_backoff_base_seconds,
    )
