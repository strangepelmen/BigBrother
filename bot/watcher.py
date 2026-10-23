import asyncio
import logging
import time

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

import config
import database as db
from keyboards import get_card_keyboard
from kufar import filter_stop_words, scraper
from utils import esc, format_card, send_card

log = logging.getLogger("watcher")


async def _process(bot: Bot, uid: int, query: str, raw: list[dict], stop_words: list[str], seeded: bool):
    ids = [a["id"] for a in raw]

    if not seeded:
        # First scan of this query: remember what exists now, alert only about NEW ads later.
        await db.add_seen_ads(uid, ids)
        await db.mark_seeded(uid, query)
        await bot.send_message(
            uid,
            f"📡 <b>Big Brother запущен:</b> <code>{esc(query)}</code>\n<i>Слежу за новыми лотами в фоне.</i>",
            parse_mode="HTML",
        )
        return

    unseen = await db.filter_unseen(uid, ids)
    fresh = [a for a in raw if a["id"] in unseen]
    if not fresh:
        return

    wanted = filter_stop_words(fresh, stop_words)
    wanted_ids = {a["id"] for a in wanted}
    await db.add_seen_ads(uid, [a["id"] for a in fresh if a["id"] not in wanted_ids])

    # oldest first, so the chat reads chronologically
    for ad in reversed(wanted[: config.MAX_SEND_PER_CYCLE]):
        kb = get_card_keyboard(ad)
        header = f"⚡️ <b>НОВОЕ ОБЪЯВЛЕНИЕ</b> <code>[{esc(query)}]</code>"
        await send_card(bot, uid, ad, format_card(ad, header), kb)
        await db.add_seen_ads(uid, [ad["id"]])  # only after a successful send
        await asyncio.sleep(1)


async def run(bot: Bot) -> None:
    last_cleanup = 0.0
    while True:
        try:
            users = await db.get_all_users_with_queries()
            scanned: dict[str, list[dict]] = {}  # one scrape per unique query per cycle

            for u in users:
                uid, queries, stop_words = u["user_id"], u["queries"], u["stop_words"]
                await db.prune_seeded(uid, queries)
                seeded = await db.get_seeded(uid)

                for query in queries:
                    key = query.lower()
                    if key not in scanned:
                        scanned[key] = await scraper.search(query, limit=config.SCAN_LIMIT)
                    raw = scanned[key]
                    if not raw:
                        continue  # scrape failed / nothing found: try again next cycle
                    try:
                        await _process(bot, uid, query, raw, stop_words, query in seeded)
                    except TelegramForbiddenError:
                        log.info("user %s blocked the bot, stopping their queries", uid)
                        await db.set_queries(uid, [])
                        break
                    except TelegramRetryAfter as e:
                        await asyncio.sleep(e.retry_after)
                    except Exception:
                        log.exception("failed to process %s / %s", uid, query)

            if time.monotonic() - last_cleanup > 3600:
                await db.cleanup_old_seen(60)
                last_cleanup = time.monotonic()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("watcher cycle failed")
        await asyncio.sleep(config.POLL_INTERVAL)
