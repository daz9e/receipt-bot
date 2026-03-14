import os

from aiogram import Dispatcher, Router
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from .commands import commands_router
from .photo import photo_router
from .text_query import text_router

_raw = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: set[int] = {int(x.strip()) for x in _raw.split(",") if x.strip()}


class AllowedUserFilter(BaseFilter):
    async def __call__(self, message: Message | CallbackQuery) -> bool:
        if not ALLOWED_USERS:
            return True
        return message.from_user.id in ALLOWED_USERS


root_router = Router()
root_router.message.filter(AllowedUserFilter())
root_router.callback_query.filter(AllowedUserFilter())
root_router.include_router(commands_router)
root_router.include_router(photo_router)
root_router.include_router(text_router)


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(root_router)
    return dp
