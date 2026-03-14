import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..db.database import SessionLocal
from ..db.models import (
    Category,
    Merchant,
    Product,
    Receipt,
    ReceiptItem,
    ReceiptPhoto,
    ReceiptRaw,
)

logger = logging.getLogger(__name__)


def compute_hash(file_paths: list[str]) -> str:
    """MD5 of all files together — unique fingerprint for the photo set."""
    h = hashlib.md5()
    for path in sorted(file_paths):
        with open(path, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def purchase_fingerprint(data: dict) -> str | None:
    """Fingerprint: date + time + total + currency.
    Merchant intentionally excluded — model may extract it differently from the same receipt."""
    date = (data.get("purchase_date") or "").strip()
    time_ = (data.get("purchase_time") or "").strip()
    total = data.get("total_amount")
    currency = (data.get("currency") or "").strip().upper()
    if not (date and total and currency):
        return None
    return hashlib.md5(f"{date}|{time_}|{total}|{currency}".encode()).hexdigest()


async def _get_or_create_merchant(session, name: str | None) -> int | None:
    if not name:
        return None
    result = await session.execute(select(Merchant).where(Merchant.name == name))
    merchant = result.scalar_one_or_none()
    if merchant:
        return merchant.id
    m = Merchant(name=name)
    session.add(m)
    await session.flush()
    return m.id


async def _get_or_create_category(session, name: str | None) -> int | None:
    if not name:
        return None
    result = await session.execute(select(Category).where(Category.name == name))
    cat = result.scalar_one_or_none()
    if cat:
        return cat.id
    c = Category(name=name)
    session.add(c)
    await session.flush()
    return c.id


async def _get_or_create_product(session, name: str | None, category_id: int | None) -> int | None:
    if not name:
        return None
    result = await session.execute(select(Product).where(Product.name == name))
    prod = result.scalar_one_or_none()
    if prod:
        return prod.id
    p = Product(name=name, category_id=category_id)
    session.add(p)
    await session.flush()
    return p.id


async def check_duplicate_and_save(
    data: dict,
    file_paths: list[str],
    user_id: int,
    username: str,
    image_hash: str,
) -> tuple[Receipt, bool]:
    """Check for duplicate and save in a single transaction.

    Returns (receipt, is_duplicate). If is_duplicate is True, receipt is the existing one.
    """
    fp = purchase_fingerprint(data)

    async with SessionLocal() as session:
        # 1. Check by image hash
        result = await session.execute(
            select(Receipt).where(Receipt.image_hash == image_hash)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing, True

        # 2. Check by purchase fingerprint
        if fp:
            result = await session.execute(
                select(Receipt).where(Receipt.purchase_fingerprint == fp)
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing, True

        # 3. Not a duplicate — save within the same session/transaction
        merchant_id = await _get_or_create_merchant(session, data.get("merchant"))

        receipt = Receipt(
            telegram_user_id=user_id,
            telegram_username=username,
            merchant=data.get("merchant"),
            merchant_id=merchant_id,
            purchase_date=data.get("purchase_date"),
            purchase_time=data.get("purchase_time"),
            total_amount=data.get("total_amount"),
            currency=data.get("currency"),
            tax_amount=data.get("tax_amount"),
            discount_amount=data.get("discount_amount"),
            payment_method=data.get("payment_method"),
            address=data.get("address"),
            receipt_number=data.get("receipt_number"),
            description=data.get("description"),
            confidence=data.get("confidence"),
            image_hash=image_hash,
            purchase_fingerprint=fp,
        )
        session.add(receipt)

        try:
            await session.flush()
        except IntegrityError:
            # Race condition: another request inserted between check and insert
            await session.rollback()
            result = await session.execute(
                select(Receipt).where(Receipt.image_hash == image_hash)
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing, True
            raise

        # Save photos
        for i, path in enumerate(file_paths):
            session.add(ReceiptPhoto(
                receipt_id=receipt.id,
                file_path=path,
                sort_order=i,
            ))

        # Save raw JSON
        raw_text = data.get("raw_text")
        if raw_text:
            session.add(ReceiptRaw(
                receipt_id=receipt.id,
                raw_json=raw_text,
            ))

        # Save items
        for item in data.get("items") or []:
            category_id = await _get_or_create_category(session, item.get("category"))
            product_id = await _get_or_create_product(session, item.get("name"), category_id)
            session.add(ReceiptItem(
                receipt_id=receipt.id,
                name=item.get("name"),
                quantity=item.get("quantity"),
                unit_price=item.get("unit_price"),
                total_price=item.get("total_price"),
                category=item.get("category"),
                category_id=category_id,
                product_id=product_id,
            ))

        await session.commit()
        await session.refresh(receipt)
        return receipt, False
