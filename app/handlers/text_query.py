import asyncio
import logging
import os
import time

from aiogram import Bot, F, Router
from aiogram.types import FSInputFile, Message

from ..ai.query_agent import QueryAgent
from ..db.user_settings import get_user_language
from ..i18n.strings import t

logger = logging.getLogger(__name__)

text_router = Router()
query_agent = QueryAgent()

TYPING_INTERVAL = 4.5


async def _send_typing_loop(bot: Bot, chat_id: int, interval: float = TYPING_INTERVAL):
    while True:
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(interval)


@text_router.message(F.text)
async def handle_text(message: Message, bot: Bot):
    user_id = message.from_user.id
    question = message.text.strip()
    lang = await get_user_language(user_id) or "ru"

    typing_task = asyncio.create_task(_send_typing_loop(bot, message.chat.id))

    last_edit = [0.0]
    status: Message | None = None

    async def on_chunk(text: str):
        nonlocal status
        now = time.monotonic()
        if now - last_edit[0] >= 0.8:
            try:
                if status is None:
                    status = await message.answer(text or "...")
                else:
                    await status.edit_text(text)
                last_edit[0] = now
            except Exception:
                pass

    async def on_photos(paths: list[str]):
        for path in paths:
            if os.path.exists(path):
                await message.answer_photo(FSInputFile(path))

    try:
        answer = await query_agent.ask(question, user_id, lang=lang, on_chunk=on_chunk, on_photos=on_photos)
    except Exception as e:
        typing_task.cancel()
        logger.exception("QueryAgent failed")
        if status:
            await status.edit_text(t("query_error", lang, error=str(e)))
        else:
            await message.answer(t("query_error", lang, error=str(e)))
        return
    typing_task.cancel()
    if status:
        await status.edit_text(answer, parse_mode="Markdown")
    else:
        await message.answer(answer, parse_mode="Markdown")
