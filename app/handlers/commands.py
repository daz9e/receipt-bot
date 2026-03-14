from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ..ai.query_agent import clear_history
from ..db.user_settings import get_user_language, set_user_language
from ..i18n.strings import t

commands_router = Router()

_LANG_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="Русский", callback_data="lang:ru"),
    InlineKeyboardButton(text="English", callback_data="lang:en"),
]])


@commands_router.message(CommandStart())
async def cmd_start(message: Message):
    lang = await get_user_language(message.from_user.id)
    if lang:
        await message.answer(t("welcome", lang))
    else:
        await message.answer(t("choose_language", "en"), reply_markup=_LANG_KEYBOARD)


@commands_router.message(Command("lang"))
async def cmd_lang(message: Message):
    await message.answer(t("choose_language_prompt"), reply_markup=_LANG_KEYBOARD)


@commands_router.callback_query(F.data.startswith("lang:"))
async def handle_lang(callback: CallbackQuery):
    lang = callback.data.split(":")[1]
    await set_user_language(callback.from_user.id, lang)
    clear_history(callback.from_user.id)
    await callback.message.edit_text(t("lang_set", lang))
    await callback.answer()


@commands_router.message(Command("clear"))
async def cmd_clear(message: Message):
    clear_history(message.from_user.id)
    lang = await get_user_language(message.from_user.id) or "ru"
    await message.answer(t("dialog_cleared", lang))
