# Agent Guidelines for Receipt Bot

This is a Telegram bot that processes receipts using AI vision (OpenRouter/gemini-2.0-flash-exp). Users send photos of receipts, the bot analyzes them, extracts data, and stores them in a SQLite database.

## Project Structure

```
receipt-bot/
├── app/
│   ├── main.py              # Entry point, bot initialization
│   ├── ai/
│   │   ├── analyzer.py      # Receipt image analysis via OpenRouter
│   │   ├── query_agent.py   # Natural language query handling
│   │   └── schemas.py       # Pydantic models for AI responses
│   ├── db/
│   │   ├── database.py      # SQLAlchemy async setup, migrations
│   │   ├── models.py        # ORM models (Receipt, ReceiptItem, etc.)
│   │   └── user_settings.py # User language preferences
│   ├── handlers/
│   │   ├── commands.py     # /start, /lang, /clear commands
│   │   ├── photo.py         # Photo/document upload handling
│   │   ├── text_query.py   # Natural language queries
│   │   └── __init__.py      # Dispatcher setup, allowed users filter
│   ├── services/
│   │   ├── receipt_service.py  # Receipt saving, duplicate detection
│   │   ├── formatting.py        # Response formatting
│   │   └── reporting.py        # Report generation
│   ├── storage.py           # Photo file storage
│   └── i18n/strings.py     # Internationalization (en/ru)
├── requirements.txt         # Python dependencies
├── docker-compose.yml       # Docker setup
├── .env.example            # Environment variables template
└── data/                   # Receipt images and SQLite database
```

## Commands

### Running the Bot

```bash
# Local development (requires .env with TELEGRAM_TOKEN and OPENROUTER_API_KEY)
python -m app.main

# With Docker
docker-compose up --build
```

### Testing

There are currently no tests in the codebase. When adding tests:

```bash
# Run all tests with pytest
pytest

# Run a single test file
pytest tests/test_receipt_service.py

# Run a single test function
pytest tests/test_receipt_service.py::test_check_duplicate_and_save

# Run with verbose output
pytest -v

# Run with coverage (if coverage is installed)
pytest --cov=app --cov-report=term-missing
```

### Linting & Type Checking

```bash
# Install dev dependencies (if any added)
pip install -r requirements.txt

# Run ruff linter (if installed)
ruff check app/

# Run mypy type checker (if installed)
mypy app/

# Format code with ruff (if installed)
ruff format app/
```

## Code Style Guidelines

### General Principles

- **Async-first**: Use `async`/`await` for all I/O operations (database, HTTP, file I/O)
- **Type hints**: Always use type hints for function signatures and variables
- **Pydantic models**: Use Pydantic for data validation and serialization (see `app/ai/schemas.py`)
- **SQLAlchemy 2.0**: Use SQLAlchemy 2.0 style with async sessions and `Mapped` annotations

### Imports

```python
# Standard library first
import asyncio
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from collections import defaultdict

# Third-party packages (alphabetical)
from aiogram import Bot, F, Router
from aiogram.types import Message
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Local application imports
from ..db.database import SessionLocal
from ..db.models import Receipt
from ..i18n.strings import t
```

### Naming Conventions

- **Files**: `snake_case.py` (e.g., `receipt_service.py`, `query_agent.py`)
- **Classes**: `PascalCase` (e.g., `ReceiptAnalyzer`, `ReceiptData`)
- **Functions/variables**: `snake_case` (e.g., `check_duplicate_and_save`, `image_hash`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `ALBUM_TIMEOUT`, `MODEL`)
- **Private members**: Leading underscore (e.g., `_process_album`, `_encode_image`)

### Type Annotations

```python
# Use modern Python 3.10+ union syntax
def process_photos(paths: list[str], user_id: int) -> tuple[Receipt, bool]:
    ...

# For async functions
async def analyze(file_paths: list[str]) -> dict:
    ...

# Optional types (use | None, not Optional)
name: str | None = None
quantity: float | None = None
```

### Error Handling

- Use try/except with specific exception types
- Log errors with appropriate level (`logger.error`, `logger.warning`)
- Return error dicts for expected failure modes (see `analyzer.py` pattern)
- Let unexpected exceptions propagate or use `logger.exception()` for debugging

```python
# Good: handle expected errors, return structured error
try:
    validated = ReceiptData.model_validate(parsed)
except Exception as e:
    logger.warning(f"Pydantic validation failed: {e}")
    return {"error": f"Invalid receipt structure: {e}", "confidence": 0.0}

# Good: log and re-raise unexpected errors
except Exception as e:
    logger.error(f"Analysis failed [{type(e).__name__}]: {e}", exc_info=True)
    return {"error": str(e)}
```

### Database

- Use async SQLAlchemy with `aiosqlite`
- Use `async_sessionmaker` for session creation
- Always use `async with SessionLocal() as session:` context manager
- Use `select()` for queries (SQLAlchemy 2.0 style)
- Use `mapped_column()` for model definitions

```python
async with SessionLocal() as session:
    result = await session.execute(select(Receipt).where(Receipt.id == receipt_id))
    receipt = result.scalar_one_or_none()
    if receipt:
        ...
    await session.commit()
```

### AI/ML Code

- Validate AI responses with Pydantic models
- Log token usage and response metadata for debugging
- Handle empty/null responses gracefully
- Include confidence scores when available

### Telegram Bot

- Use aiogram 3.x patterns with routers
- Filter by user with `AllowedUserFilter` (see `handlers/__init__.py`)
- Support both photo and document uploads
- Handle album/media groups with buffering
- Use i18n strings via `t()` function

### Internationalization

- Use the `t()` function from `app.i18n.strings`
- Pass language code (typically from user settings, default "ru")
- Store translations in `app/i18n/strings.py`

```python
from ..i18n.strings import t

lang = await get_user_language(user_id) or "ru"
await message.answer(t("welcome", lang))
```

### Logging

- Use module-level loggers: `logger = logging.getLogger(__name__)`
- Set appropriate log levels:
  - `DEBUG`: Detailed diagnostic info
  - `INFO`: General operational events
  - `WARNING`: Unexpected but handled situations
  - `ERROR`: Failures that need attention
- Reduce noise from external libraries (httpx, openai)

```python
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
```

### Configuration

- All config via environment variables
- Use `os.getenv("VAR_NAME", default)` for optional vars
- Required vars accessed via `os.environ["VAR_NAME"]`
- Document required vars in `.env.example`

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_TOKEN` | Telegram bot token from @BotFather | Yes |
| `OPENROUTER_API_KEY` | OpenRouter API key | Yes |
| `OPENROUTER_MODEL` | Vision model (default: google/gemini-2.0-flash-exp:free) | No |
| `OPENROUTER_TEXT_MODEL` | Text model for queries | No |
| `ALLOWED_USERS` | Comma-separated Telegram user IDs | No |
| `DB_PATH` | SQLite database path (default: /data/receipts.db) | No |
