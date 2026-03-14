import asyncio
import logging
import os

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from .db.database import init_db
from .handlers import create_dispatcher

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def main():
    token = os.environ["TELEGRAM_TOKEN"]

    await init_db()
    logger.info("Database initialized")

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = create_dispatcher()

    await bot.set_my_commands([
        BotCommand(command="start", description="Start / Начало работы"),
        BotCommand(command="lang", description="Change language / Сменить язык"),
        BotCommand(command="clear", description="Reset dialog / Сбросить диалог"),
    ])

    logger.info("Starting bot...")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
