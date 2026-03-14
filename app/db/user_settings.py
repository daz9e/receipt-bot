from sqlalchemy import select
from .database import SessionLocal
from .models import UserSettings


async def get_user_language(telegram_user_id: int) -> str | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserSettings).where(UserSettings.telegram_user_id == telegram_user_id)
        )
        settings = result.scalar_one_or_none()
        return settings.language if settings else None


async def set_user_language(telegram_user_id: int, language: str):
    async with SessionLocal() as session:
        result = await session.execute(
            select(UserSettings).where(UserSettings.telegram_user_id == telegram_user_id)
        )
        settings = result.scalar_one_or_none()
        if settings:
            settings.language = language
        else:
            session.add(UserSettings(telegram_user_id=telegram_user_id, language=language))
        await session.commit()
