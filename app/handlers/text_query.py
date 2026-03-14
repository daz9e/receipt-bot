import logging
import os
import time

from aiogram import F, Router
from aiogram.types import FSInputFile, Message

from ..ai.query_agent import QueryAgent
from ..db.user_settings import get_user_language
from ..i18n.strings import t

logger = logging.getLogger(__name__)

text_router = Router()
query_agent = QueryAgent()


@text_router.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id
    question = message.text.strip()
    lang = await get_user_language(user_id) or "ru"
    status = await message.answer(t("thinking", lang))

    last_edit = [0.0]

    async def on_chunk(text: str):
        now = time.monotonic()
        if now - last_edit[0] >= 0.8:
            try:
                await status.edit_text(text or "...", parse_mode="Markdown")
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
        logger.exception("QueryAgent failed")
        await status.edit_text(t("query_error", lang, error=str(e)))
        return
    await status.edit_text(answer, parse_mode="Markdown")
