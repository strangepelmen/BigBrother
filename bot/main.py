import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo

import config
import database as db
import watcher
from handlers import router
from kufar import scraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")


async def setup_bot_ui(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="search", description="Разовый поиск"),
        BotCommand(command="track", description="Следить за товаром"),
        BotCommand(command="untrack", description="Перестать следить"),
        BotCommand(command="list", description="Активные запросы"),
        BotCommand(command="test", description="Тест по всем запросам"),
        BotCommand(command="stop", description="Остановить мониторинг"),
    ])
    if config.WEBAPP_URL:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Big Brother", web_app=WebAppInfo(url=config.WEBAPP_URL))
        )


async def main() -> None:
    config.validate()
    await db.init_db()
    await scraper.start()

    bot = Bot(token=config.BOT_TOKEN, session=AiohttpSession(timeout=60.0))
    dp = Dispatcher()
    dp.include_router(router)

    watcher_task = None
    try:
        await bot.delete_webhook()  # polling does not work while a webhook is set
        await setup_bot_ui(bot)
        watcher_task = asyncio.create_task(watcher.run(bot))
        log.info("Big Brother started")
        await dp.start_polling(bot)
    finally:
        if watcher_task:
            watcher_task.cancel()
        await scraper.stop()
        await db.close_db()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
