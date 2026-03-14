from pydantic import BaseModel, field_validator


class ReceiptItemData(BaseModel):
    name: str | None = None
    quantity: float | None = 1
    unit_price: float | None = None
    total_price: float | None = None
    category: str | None = None

    @field_validator("category", mode="before")
    @classmethod
    def normalize_null_category(cls, v: object) -> str | None:
        if isinstance(v, str) and v.lower() in ("null", "none", ""):
            return None
        return v


class ReceiptData(BaseModel):
    merchant: str | None = None
    purchase_date: str | None = None
    purchase_time: str | None = None
    total_amount: float | None = None
    currency: str | None = None
    tax_amount: float | None = None
    discount_amount: float | None = None
    payment_method: str | None = None
    items: list[ReceiptItemData] = []
    description: str | None = None
    address: str | None = None
    receipt_number: str | None = None
    confidence: float = 0.0
