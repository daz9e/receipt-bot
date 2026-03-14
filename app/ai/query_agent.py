"""Natural language query agent. Single execute_sql tool, read-only connection, streaming output."""
import json
import logging
import os
import re
from collections.abc import Callable, Coroutine
from datetime import UTC, date, datetime, timedelta
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import text

from ..db.database import SessionReadOnly
from ..i18n.strings import t

logger = logging.getLogger(__name__)

_SCHEMA = """
-- receipts: id, created_at, merchant_id->merchants, merchant (legacy text), purchase_date (YYYY-MM-DD), purchase_time, total_amount, currency, tax_amount, discount_amount, payment_method, address, receipt_number, description, confidence, telegram_user_id
-- merchants: id, name (unique), address
-- receipt_items: id, receipt_id->receipts, product_id->products, name (raw from receipt), quantity, unit_price, total_price, category (legacy text), category_id->categories
-- products: id, name (canonical, unique), category_id->categories
-- categories: id, name (unique), display_name_ru, display_name_en
-- receipt_photos: id, receipt_id->receipts, file_path, sort_order
""".strip()

_BLOCKED_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma)\b",
    re.IGNORECASE,
)

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "Execute a read-only SELECT query against the receipts SQLite database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "A valid SQLite SELECT statement."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_receipt_photos",
            "description": "Send the original receipt photo(s) to the user. Use this when the user asks to see a receipt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "receipt_id": {"type": "integer", "description": "The receipt ID to send photos for."}
                },
                "required": ["receipt_id"],
            },
        },
    },
]

_CONTEXT_TTL = timedelta(minutes=10)
# user_id -> {"messages": [...], "last_at": datetime}
_user_contexts: dict[int, dict] = {}


def _get_history(user_id: int) -> list:
    ctx = _user_contexts.get(user_id)
    if ctx and datetime.now(UTC) - ctx["last_at"] < _CONTEXT_TTL:
        return list(ctx["messages"])
    return []


def _save_history(user_id: int, messages: list):
    _user_contexts[user_id] = {"messages": messages, "last_at": datetime.now(UTC)}


def clear_history(user_id: int):
    _user_contexts.pop(user_id, None)


async def _execute_sql(query: str) -> dict:
    stripped = query.strip().lower()
    if not stripped.startswith("select"):
        return {"error": "Only SELECT queries are allowed."}
    if _BLOCKED_RE.search(stripped):
        return {"error": "Blocked keywords detected."}
    try:
        async with SessionReadOnly() as session:
            result = await session.execute(text(query))
            keys = list(result.keys())
            rows = [dict(zip(keys, row)) for row in result.fetchmany(200)]
            response: dict[str, Any] = {"columns": keys, "rows": rows, "count": len(rows)}
            if len(rows) == 200:
                response["truncated"] = True
            return response
    except Exception as e:
        return {"error": str(e)}


async def _get_receipt_photo_paths(receipt_id: int) -> list[str]:
    async with SessionReadOnly() as session:
        result = await session.execute(
            text(
                "SELECT file_path FROM receipt_photos "
                "WHERE receipt_id = :rid ORDER BY sort_order"
            ),
            {"rid": receipt_id},
        )
        paths = [row[0] for row in result.fetchall()]
        if paths:
            return paths

    # Fallback to legacy file_path column
    from ..db.database import SessionLocal
    from ..db.models import Receipt
    from sqlalchemy import select as sa_select
    async with SessionLocal() as session:
        result = await session.execute(sa_select(Receipt.file_path).where(Receipt.id == receipt_id))
        row = result.scalar_one_or_none()
        if not row:
            return []
        return [p.strip() for p in row.split(",") if p.strip()]


OnChunk = Callable[[str], Coroutine[Any, Any, None]]
OnPhotos = Callable[[list[str]], Coroutine[Any, Any, None]]


class QueryAgent:
    MAX_ITERATIONS = 8

    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
        )
        self._model = os.getenv("OPENROUTER_TEXT_MODEL", os.getenv("OPENROUTER_MODEL", "openai/gpt-5-nano"))

    async def ask(self, question: str, user_id: int, lang: str = "ru", on_chunk: OnChunk | None = None, on_photos: OnPhotos | None = None) -> str:
        today = date.today().isoformat()
        lang_name = "Russian" if lang == "ru" else "English"
        system = {
            "role": "system",
            "content": (
                f"You are a personal finance assistant. Today is {today}.\n"
                f"Database schema:\n\n{_SCHEMA}\n\n"
                "Use execute_sql to query the database. You may call it multiple times. "
                "If the user's request is ambiguous or missing key details (e.g. time period, product, store), "
                "ask a short clarifying question and always suggest 2-3 concrete options the user can pick from. "
                "Do not call any tools until you have enough information. "
                "You can also send receipt photos using send_receipt_photos when the user wants to see a receipt. "
                f"ALWAYS respond in {lang_name}, regardless of what language the user writes in.\n"
                "Use Markdown formatting: **bold**, _italic_, `code`, numbered lists. Never use HTML tags.\n"
                "Product name rules:\n"
                f"- Detect the source language (Serbian, Russian, English, etc.) and semantically translate to {lang_name}.\n"
                "- Do NOT transliterate — find the actual meaning. Example: 'SOK' (Serbian) = juice, 'HLEB' = bread, 'KES' = bag.\n"
                "- Keep brand names as-is (Coca-Cola, Nike, etc.).\n"
                "- Never modify numbers, amounts, currencies, dates, or receipt IDs.\n"
                "- Never convert currencies — always show original amount and currency from the database."
            ),
        }
        history = _get_history(user_id)
        messages = [system] + history + [{"role": "user", "content": question}]

        for _ in range(self.MAX_ITERATIONS):
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=_TOOLS,
                tool_choice="auto",
                stream=True,
            )

            full_text = ""
            tool_calls_acc: dict[int, dict] = {}

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                if delta.content:
                    full_text += delta.content
                    if on_chunk:
                        await on_chunk(full_text)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc.id:
                            tool_calls_acc[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_acc[idx]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_calls_acc[idx]["arguments"] += tc.function.arguments

            if not tool_calls_acc:
                # Final answer — save context (only user+assistant text, no tool noise)
                new_history = history + [
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": full_text},
                ]
                _save_history(user_id, new_history)
                return full_text or t("max_steps_exceeded", lang)

            # Append assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": full_text or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                    for tc in tool_calls_acc.values()
                ],
            })

            # Execute each tool call and append results
            for tc in tool_calls_acc.values():
                try:
                    args = json.loads(tc["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}

                if tc["name"] == "send_receipt_photos":
                    receipt_id = args.get("receipt_id")
                    paths = await _get_receipt_photo_paths(receipt_id)
                    if paths and on_photos:
                        await on_photos(paths)
                    result = {"sent": len(paths)}
                else:
                    query = args.get("query", "")
                    logger.info("SQL: %s", query)
                    result = await _execute_sql(query)
                    logger.info("SQL result: %s", result.get("count", result.get("error")))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

        return t("max_steps_exceeded", lang)
