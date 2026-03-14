"""
Receipt analyzer via OpenRouter (google/gemini-2.0-flash-exp:free).
OpenAI-compatible API with vision support.
"""
import base64
import json
import logging
import os
from pathlib import Path

from openai import AsyncOpenAI

from .schemas import ReceiptData

logger = logging.getLogger(__name__)

MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")

SYSTEM_PROMPT = """You are a receipt OCR and data extraction assistant.
When given an image of a receipt, extract ALL available information and return ONLY valid JSON.
Be thorough — extract every line item, tax, discount, and fee you can find.
If a field is not present, use null."""

EXTRACTION_PROMPT = """Analyze this receipt image and extract all information.

Return ONLY a valid JSON object with this exact structure:
{
  "merchant": "store/restaurant name",
  "purchase_date": "YYYY-MM-DD or original format if unclear",
  "purchase_time": "HH:MM or null",
  "total_amount": 0.00,
  "currency": "USD/EUR/RUB/etc (ISO 4217)",
  "tax_amount": 0.00,
  "discount_amount": 0.00,
  "payment_method": "cash/card/null",
  "items": [
    {
      "name": "full product name as on receipt",
      "quantity": 1,
      "unit_price": 0.00,
      "total_price": 0.00,
      "category": "food/hygiene/alcohol/electronics/clothing/other or null"
    }
  ],
  "description": "brief human-readable summary of the purchase",
  "address": "merchant address if visible",
  "receipt_number": "receipt/invoice number if visible",
  "confidence": 0.95
}

Return ONLY the JSON, no markdown, no explanation."""


class ReceiptAnalyzer:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url="https://openrouter.ai/api/v1",
        )

    async def analyze(self, image_paths: list[str]) -> dict:
        """Analyze one or more receipt images as a single receipt."""
        content = []
        for path in image_paths:
            ext = Path(path).suffix.lower().lstrip(".")
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
            b64 = self._encode_image(path)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            })

        prompt = EXTRACTION_PROMPT
        if len(image_paths) > 1:
            prompt = (
                f"These {len(image_paths)} images are parts of the SAME receipt (e.g. top and bottom). "
                "Combine all parts into one complete result.\n\n" + EXTRACTION_PROMPT
            )
        content.append({"type": "text", "text": prompt})

        try:
            logger.info(f"Sending {len(image_paths)} image(s) to model: {MODEL}")
            response = await self.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
                max_tokens=16000,
            )
            logger.info(f"Response: finish_reason={response.choices[0].finish_reason} "
                        f"usage={response.usage}")
            raw = response.choices[0].message.content
            if not raw:
                logger.error(f"Empty content. Full response: {response.model_dump_json()}")
                return {"error": "Model returned empty response (no vision support or rate limit)."}
            logger.info(f"Raw response ({len(raw)} chars): {raw[:300]}")
            return self._parse(raw)
        except Exception as e:
            logger.error(f"Analysis failed [{type(e).__name__}]: {e}", exc_info=True)
            return {"error": str(e)}

    def _encode_image(self, path: str) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _parse(self, raw: str) -> dict:
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse JSON: {raw[:200]}")
            return {"error": "Failed to parse AI response as JSON", "confidence": 0.0}

        # Validate with Pydantic
        try:
            validated = ReceiptData.model_validate(parsed)
            data = validated.model_dump()
        except Exception as e:
            logger.warning(f"Pydantic validation failed: {e}")
            return {"error": f"Invalid receipt structure: {e}", "confidence": 0.0}

        data["raw_text"] = raw
        return data
