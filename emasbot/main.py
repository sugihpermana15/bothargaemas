from __future__ import annotations

import logging
import os
import sys
import time
from threading import Thread
from pathlib import Path

from config import load_config, setup_logging
from database import (
    get_last_vendor_price,
    init_db,
    insert_vendor_history,
    upsert_last_vendor_price,
)
from notifier import (
    build_full_message,
    build_full_realtime_message,
    build_vendor_realtime_message,
    get_telegram_updates,
    send_telegram_message,
)
from scraper import FullGoldPrices, fetch_full_prices

logger = logging.getLogger(__name__)


def _acquire_single_instance_lock(lock_path: str = "emasbot.lock") -> object:
    """Prevent running multiple instances on the same machine.

    This helps avoid Telegram getUpdates 409 conflicts caused by double-running.
    Returns a handle that must be kept alive for the duration of the process.
    """
    lock_file = Path(lock_path)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_file, "a+", encoding="utf-8")

    try:
        if os.name == "nt":
            import msvcrt  # type: ignore

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError(
                    "Another instance is already running (lock busy)."
                ) from exc
        else:
            import fcntl  # type: ignore

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError(
                    "Another instance is already running (lock busy)."
                ) from exc

        handle.seek(0)
        handle.truncate(0)
        handle.write(str(os.getpid()))
        handle.flush()
        return handle
    except Exception:
        try:
            handle.close()
        except Exception:
            pass
        raise


def _prices_changed(last: dict | None, sell_price: int, buyback_price: int) -> bool:
    if not last:
        return True
    return (last.get("sell_price") != sell_price) or (last.get("buyback_price") != buyback_price)


def _try_parse_weight_grams(weight_text: str) -> float | None:
    text = (weight_text or "").strip().lower().replace("g", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _full_prices_changed(db_path: str, prices: FullGoldPrices) -> bool:
    for table in prices.tables:
        for row in table.rows:
            last = get_last_vendor_price(db_path, vendor_id=table.vendor_id, weight_text=row.weight_text)
            if _prices_changed(last, row.sell_price, row.buyback_price):
                return True
    return False


def _persist_full_prices(db_path: str, prices: FullGoldPrices) -> None:
    for table in prices.tables:
        for row in table.rows:
            weight_grams = _try_parse_weight_grams(row.weight_text)
            upsert_last_vendor_price(
                db_path,
                vendor_id=table.vendor_id,
                weight_text=row.weight_text,
                weight_grams=weight_grams,
                sell_price=row.sell_price,
                buyback_price=row.buyback_price,
                updated_at=prices.observed_at,
            )
            insert_vendor_history(
                db_path,
                vendor_id=table.vendor_id,
                weight_text=row.weight_text,
                weight_grams=weight_grams,
                sell_price=row.sell_price,
                buyback_price=row.buyback_price,
                observed_at=prices.observed_at,
            )


def main() -> None:
    setup_logging()
    config = load_config()

    try:
        _lock_handle = _acquire_single_instance_lock()
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)

    init_db(config.db_path)

    logger.info(
        "Bot started. Poll interval=%ss url=%s db=%s",
        config.poll_interval_seconds,
        config.source_url,
        config.db_path,
    )

    def command_listener() -> None:
        logger.info("Command listener started (/cekharga)")
        offset: int | None = None

        allowed_chat_ids = {str(cid) for cid in config.telegram_chat_ids}

        # Use long polling to avoid tight loops.
        long_poll_seconds = min(25, max(1, config.request_timeout_seconds))
        while True:
            try:
                updates = get_telegram_updates(
                    token=config.telegram_token,
                    offset=offset,
                    long_poll_timeout_seconds=long_poll_seconds,
                    request_timeout_seconds=max(5, config.request_timeout_seconds + 5),
                    max_retries=config.max_retries,
                    backoff_base_seconds=config.retry_backoff_base_seconds,
                )

                for upd in updates:
                    try:
                        update_id = upd.get("update_id")
                        if isinstance(update_id, int):
                            offset = update_id + 1

                        msg = upd.get("message") or {}
                        text = (msg.get("text") or "").strip()
                        chat = msg.get("chat") or {}
                        chat_id = chat.get("id")
                        message_thread_id = msg.get("message_thread_id")

                        # Security: only respond to allowed chat ids
                        if str(chat_id) not in allowed_chat_ids:
                            continue

                        # In groups, commands can be like /cekharga@BotName
                        first_token = (text.split() or [""])[0]
                        command = first_token.split("@")[0].lower()

                        if command not in {"/cekharga", "/antam", "/ubs", "/galeri24"}:
                            continue

                        logger.info("Received command %s", command)

                        prices = fetch_full_prices(
                            url=config.source_url,
                            timeout_seconds=config.request_timeout_seconds,
                            max_retries=config.max_retries,
                            backoff_base_seconds=config.retry_backoff_base_seconds,
                        )

                        if command == "/cekharga":
                            reply = build_full_realtime_message(prices)
                        elif command == "/antam":
                            reply = build_vendor_realtime_message(
                                prices, vendor_id="ANTAM", command="/antam"
                            )
                        elif command == "/ubs":
                            reply = build_vendor_realtime_message(
                                prices, vendor_id="UBS", command="/ubs"
                            )
                        else:  # /galeri24
                            reply = build_vendor_realtime_message(
                                prices, vendor_id="GALERI 24", command="/galeri24"
                            )

                        send_telegram_message(
                            token=config.telegram_token,
                            chat_id=str(chat_id),
                            text=reply,
                            timeout_seconds=config.request_timeout_seconds,
                            max_retries=config.max_retries,
                            backoff_base_seconds=config.retry_backoff_base_seconds,
                            message_thread_id=message_thread_id
                            if isinstance(message_thread_id, int)
                            else None,
                        )

                    except Exception:
                        logger.exception("Failed handling Telegram update")

            except Exception:
                # Telegram returns 409 if another getUpdates request is active.
                # This happens when multiple bot instances run with the same token.
                msg = str(__import__("sys").exc_info()[1] or "")
                if "status=409" in msg or "Conflict: terminated by other getUpdates request" in msg:
                    logger.warning(
                        "Command listener conflict (409). Ensure only ONE instance is running for this token. Retrying..."
                    )
                    time.sleep(10)
                else:
                    logger.exception("Command listener cycle failed")
                    time.sleep(2)

    Thread(target=command_listener, name="telegram-command-listener", daemon=True).start()

    while True:
        try:
            prices = fetch_full_prices(
                url=config.source_url,
                timeout_seconds=config.request_timeout_seconds,
                max_retries=config.max_retries,
                backoff_base_seconds=config.retry_backoff_base_seconds,
            )

            if _full_prices_changed(config.db_path, prices):
                _persist_full_prices(config.db_path, prices)

                text = build_full_message(prices)

                # Broadcast notification to all configured chats
                for chat_id in config.telegram_chat_ids:
                    send_telegram_message(
                        token=config.telegram_token,
                        chat_id=str(chat_id),
                        text=text,
                        timeout_seconds=config.request_timeout_seconds,
                        max_retries=config.max_retries,
                        backoff_base_seconds=config.retry_backoff_base_seconds,
                    )

                logger.info(
                    "Notified change (method=%s) vendors=%s",
                    prices.method,
                    ",".join(t.vendor_id for t in prices.tables),
                )
            else:
                logger.info("No change across vendors")

        except Exception:
            logger.exception("Polling cycle failed")

        time.sleep(config.poll_interval_seconds)


if __name__ == "__main__":
    main()
