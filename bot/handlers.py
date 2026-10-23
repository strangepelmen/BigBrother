import asyncio
import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

import config
import database as db
from keyboards import get_card_keyboard
from kufar import filter_stop_words, scraper
from utils import LINE, esc, format_card, send_card

log = logging.getLogger("handlers")
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        f"{LINE}\n"
        "👁 <b>BIG BROTHER</b>\n"
        f"{LINE}\n"
        "Мониторинг новых объявлений Kufar.\n\n"
        "<b>Команды:</b>\n"
        "▫️ <code>/search &lt;товар&gt;</code> — разовый поиск\n"
        "▫️ <code>/track &lt;товар&gt;</code> — следить за товаром\n"
        "▫️ <code>/untrack &lt;товар&gt;</code> — перестать следить\n"
        "▫️ <code>/list</code> — активные запросы\n"
        "▫️ <code>/test</code> — тест по всем запросам\n"
        "▫️ <code>/stop</code> — остановить весь мониторинг\n"
        f"{LINE}",
        parse_mode="HTML",
    )


@router.message(Command("search"))
async def cmd_search(message: Message, command: CommandObject):
    query = (command.args or "").strip()[: config.MAX_QUERY_LEN]
    if not query:
        await message.answer("⚠️ <b>Укажите товар:</b> <code>/search PS5</code>", parse_mode="HTML")
        return

    status = await message.answer(f"🔍 <i>Ищу:</i> <code>{esc(query)}</code>…", parse_mode="HTML")
    cfg = await db.get_user_config(message.from_user.id)
    ads = await scraper.search(query, limit=40, max_pages=2)
    ads = filter_stop_words(ads, cfg["stop_words"])[: cfg["search_limit"]]

    try:
        await status.delete()
    except Exception:
        pass

    if not ads:
        await message.answer(
            f"❌ По запросу <code>{esc(query)}</code> ничего не найдено.", parse_mode="HTML"
        )
        return

    for ad in ads:
        kb = get_card_keyboard(ad)
        await send_card(message.bot, message.chat.id, ad, format_card(ad), kb)


@router.message(Command("track"))
async def cmd_track(message: Message, command: CommandObject):
    query = (command.args or "").strip()[: config.MAX_QUERY_LEN]
    if not query:
        await message.answer("⚠️ <b>Укажите товар:</b> <code>/track PS5</code>", parse_mode="HTML")
        return

    uid = message.from_user.id
    queries = (await db.get_user_config(uid))["queries"]
    if query.lower() in (q.lower() for q in queries):
        await message.answer("ℹ️ Этот запрос уже отслеживается.")
        return
    if len(queries) >= config.MAX_QUERIES:
        await message.answer(f"⚠️ Максимум {config.MAX_QUERIES} запросов. Удалите лишние: /untrack")
        return

    await db.set_queries(uid, queries + [query])
    await message.answer(
        f"✅ <code>{esc(query)}</code> добавлен. Первое сканирование — в течение минуты.",
        parse_mode="HTML",
    )


@router.message(Command("untrack"))
async def cmd_untrack(message: Message, command: CommandObject):
    query = (command.args or "").strip()
    uid = message.from_user.id
    queries = (await db.get_user_config(uid))["queries"]
    if not query:
        await message.answer("⚠️ Укажите товар: <code>/untrack PS5</code> (список: /list)", parse_mode="HTML")
        return
    left = [q for q in queries if q.lower() != query.lower()]
    if len(left) == len(queries):
        await message.answer("ℹ️ Такого запроса нет. Список: /list")
        return
    await db.set_queries(uid, left)
    await message.answer(f"🗑 <code>{esc(query)}</code> удалён.", parse_mode="HTML")


@router.message(Command("list"))
async def cmd_list(message: Message):
    queries = (await db.get_user_config(message.from_user.id))["queries"]
    if not queries:
        await message.answer("ℹ️ Активных запросов нет. Добавьте: <code>/track товар</code>", parse_mode="HTML")
        return
    items = "\n".join(f"▫️ <code>{esc(q)}</code>" for q in queries)
    await message.answer(
        f"📋 <b>Активные запросы:</b>\n{LINE}\n{items}\n{LINE}\n"
        "Удалить: <code>/untrack товар</code> · всё: /stop",
        parse_mode="HTML",
    )


@router.message(Command("stop"))
async def cmd_stop(message: Message):
    await db.set_queries(message.from_user.id, [])
    await message.answer("🛑 <b>Весь мониторинг остановлен.</b>", parse_mode="HTML")


@router.message(Command("test"))
async def cmd_test(message: Message):
    uid = message.from_user.id
    cfg = await db.get_user_config(uid)
    if not cfg["queries"]:
        await message.answer(
            "⚠️ Нет активных запросов. Добавьте в приложении или: <code>/track PS5</code>",
            parse_mode="HTML",
        )
        return

    status = await message.answer(f"🧪 <i>Тест по {len(cfg['queries'])} запросам…</i>", parse_mode="HTML")
    for query in cfg["queries"]:
        ads = filter_stop_words(await scraper.search(query, limit=20), cfg["stop_words"])
        if not ads:
            await message.answer(f"ℹ️ По <code>{esc(query)}</code> ничего не найдено.", parse_mode="HTML")
            continue
        ad = ads[0]
        kb = get_card_keyboard(ad)
        await send_card(
            message.bot, message.chat.id, ad,
            format_card(ad, f"🧪 <b>ТЕСТ</b> <code>[{esc(query)}]</code>\n{LINE}"), kb,
        )
        await asyncio.sleep(1)
    try:
        await status.delete()
    except Exception:
        pass
