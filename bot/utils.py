import html
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup

log = logging.getLogger("utils")
LINE = "<code>━━━━━━━━━━━━━━━━━━━━</code>"


def esc(value) -> str:
    return html.escape(str(value), quote=False)


def format_card(ad: dict, header: str | None = None) -> str:
    parts = [header] if header else []
    parts += [
        f"📦 <b>{esc(ad['title'][:200])}</b>",
        LINE,
        f"▫️ <b>Цена:</b> <code>{esc(ad['price'])}</code>",
        f"▫️ <b>Локация:</b> {esc(ad['location'][:100])}",
        LINE,
    ]
    return "\n".join(parts)


async def send_card(
    bot: Bot, chat_id: int, ad: dict, caption: str, kb: InlineKeyboardMarkup
) -> None:
    """Photo if possible; falls back to plain text if Telegram rejects the image."""
    if ad.get("image"):
        try:
            await bot.send_photo(chat_id, ad["image"], caption=caption, parse_mode="HTML", reply_markup=kb)
            return
        except (TelegramForbiddenError, TelegramRetryAfter):
            raise
        except Exception as e:
            log.info("photo failed (%s), sending text", e)
    await bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=kb)
