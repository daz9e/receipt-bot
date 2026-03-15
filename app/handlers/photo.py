import asyncio
import logging
from collections import defaultdict

from aiogram import Bot, F, Router
from aiogram.types import Message

from ..ai.analyzer import ReceiptAnalyzer
from ..db.user_settings import get_user_language
from ..i18n.strings import t
from ..services.formatting import format_reply
from ..services.receipt_service import compute_hash, check_duplicate_and_save
from ..storage import save_photo

logger = logging.getLogger(__name__)

photo_router = Router()
analyzer = ReceiptAnalyzer()

_album_buffer: dict[str, list] = defaultdict(list)
_album_tasks: dict[str, asyncio.Task] = {}
ALBUM_TIMEOUT = 1.5


async def _process_and_reply(file_paths: list[str], chat_id: int, user_id: int, username: str, bot: Bot):
    lang = await get_user_language(user_id) or "ru"
    image_hash = compute_hash(file_paths)
    n = len(file_paths)
    label = t("photo_label_multi", lang, n=n) if n > 1 else t("photo_label_single", lang)

    await bot.send_chat_action(chat_id=chat_id, action="typing")
    data = await analyzer.analyze(file_paths)

    if "error" in data:
        await bot.send_message(chat_id, t("analysis_error", lang, error=data["error"]))
        return

    receipt, is_duplicate = await check_duplicate_and_save(data, file_paths, user_id, username, image_hash)

    if is_duplicate:
        merchant = receipt.merchant or "?"
        date = receipt.purchase_date or "?"
        total = receipt.total_amount
        currency = receipt.currency or ""
        await bot.send_message(
            chat_id,
            t("duplicate_found", lang, id=receipt.id, merchant=merchant, date=date, total=total, currency=currency)
        )
        return

    await bot.send_message(chat_id, format_reply(data, receipt.id, n, lang), parse_mode="HTML")


async def _process_album(group_id: str, status: Message, bot: Bot, user_id: int, username: str):
    try:
        await asyncio.sleep(ALBUM_TIMEOUT)
        entries = _album_buffer.pop(group_id, [])
        if not entries:
            return
        file_paths = [e[0] for e in entries]
        await _process_and_reply(file_paths, status.chat.id, user_id, username, bot)
    finally:
        _album_buffer.pop(group_id, None)
        _album_tasks.pop(group_id, None)


@photo_router.message(F.photo)
async def handle_photo(message: Message, bot: Bot):
    lang = await get_user_language(message.from_user.id) or "ru"
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    file_path = await save_photo(file_bytes.read(), message.from_user.id, file_ext="jpg")

    group_id = message.media_group_id

    if group_id:
        is_first = group_id not in _album_buffer
        _album_buffer[group_id].append((file_path, message))
        if is_first:
            status = await message.answer(t("receiving_photo", lang))
            if group_id in _album_tasks:
                _album_tasks[group_id].cancel()
            _album_tasks[group_id] = asyncio.create_task(
                _process_album(group_id, status, bot, message.from_user.id, message.from_user.username)
            )
    else:
        await bot.send_chat_action(chat_id=message.chat.id, action="typing")
        await _process_and_reply([file_path], message.chat.id, message.from_user.id, message.from_user.username, bot)


@photo_router.message(F.document)
async def handle_document(message: Message, bot: Bot):
    lang = await get_user_language(message.from_user.id) or "ru"
    doc = message.document
    if not doc.mime_type or not doc.mime_type.startswith("image/"):
        await message.answer(t("send_image_file", lang))
        return

    ext = doc.mime_type.split("/")[-1]
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    file = await bot.get_file(doc.file_id)
    file_bytes = await bot.download_file(file.file_path)
    file_path = await save_photo(file_bytes.read(), message.from_user.id, file_ext=ext)

    await _process_and_reply([file_path], message.chat.id, message.from_user.id, message.from_user.username, bot)
