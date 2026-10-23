from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_card_keyboard(ad: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔗 Открыть на Kufar", url=ad["url"])]]
    )
