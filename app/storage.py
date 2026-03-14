import os
from datetime import UTC, datetime
from pathlib import Path

import aiofiles
import aiofiles.os

RECEIPTS_DIR = os.getenv("RECEIPTS_DIR", "/data/receipts")


async def save_photo(file_bytes: bytes, user_id: int, file_ext: str = "jpg") -> str:
    """Save receipt photo to disk, return relative path."""
    date_prefix = datetime.now(UTC).strftime("%Y/%m/%d")
    target_dir = Path(RECEIPTS_DIR) / date_prefix
    await aiofiles.os.makedirs(str(target_dir), exist_ok=True)

    ts = datetime.now(UTC).strftime("%H%M%S%f")
    filename = f"{user_id}_{ts}.{file_ext}"
    file_path = target_dir / filename

    async with aiofiles.open(str(file_path), "wb") as f:
        await f.write(file_bytes)

    return str(file_path)
