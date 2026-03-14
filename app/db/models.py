from datetime import UTC, datetime

from sqlalchemy import Float, DateTime, Integer, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name_ru: Mapped[str] = mapped_column(String, nullable=True)
    display_name_en: Mapped[str] = mapped_column(String, nullable=True)

    products: Mapped[list["Product"]] = relationship(back_populates="category")
    receipt_items: Mapped[list["ReceiptItem"]] = relationship(back_populates="category_rel")


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=True)

    receipts: Mapped[list["Receipt"]] = relationship(back_populates="merchant_rel")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=True)

    category: Mapped["Category"] = relationship(back_populates="products")
    receipt_items: Mapped[list["ReceiptItem"]] = relationship(back_populates="product")


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    # Legacy — kept for backward compat, not written in new code
    file_path: Mapped[str] = mapped_column(String, nullable=True)
    raw_text: Mapped[str] = mapped_column(String, nullable=True)

    telegram_user_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    telegram_username: Mapped[str] = mapped_column(String, nullable=True)

    # Normalized merchant
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=True, index=True)
    merchant: Mapped[str] = mapped_column(String, nullable=True)  # legacy backup

    purchase_date: Mapped[str] = mapped_column(String, nullable=True, index=True)
    purchase_time: Mapped[str] = mapped_column(String, nullable=True)
    total_amount: Mapped[float] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=True)
    tax_amount: Mapped[float] = mapped_column(Float, nullable=True)
    discount_amount: Mapped[float] = mapped_column(Float, nullable=True)
    payment_method: Mapped[str] = mapped_column(String, nullable=True)
    address: Mapped[str] = mapped_column(String, nullable=True)
    receipt_number: Mapped[str] = mapped_column(String, nullable=True)

    description: Mapped[str] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)
    image_hash: Mapped[str] = mapped_column(String(64), nullable=True, unique=True)
    purchase_fingerprint: Mapped[str] = mapped_column(String(64), nullable=True, unique=True)

    merchant_rel: Mapped["Merchant"] = relationship(back_populates="receipts")
    product_items: Mapped[list["ReceiptItem"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )
    photos: Mapped[list["ReceiptPhoto"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )
    raw: Mapped["ReceiptRaw"] = relationship(
        back_populates="receipt", cascade="all, delete-orphan", uselist=False
    )


class ReceiptItem(Base):
    __tablename__ = "receipt_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id"), nullable=False)

    name: Mapped[str] = mapped_column(String, nullable=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=True)
    unit_price: Mapped[float] = mapped_column(Float, nullable=True)
    total_price: Mapped[float] = mapped_column(Float, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=True)  # legacy backup

    # Normalized references
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=True, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)

    receipt: Mapped["Receipt"] = relationship(back_populates="product_items")
    product: Mapped["Product"] = relationship(back_populates="receipt_items")
    category_rel: Mapped["Category"] = relationship(back_populates="receipt_items")


class ReceiptPhoto(Base):
    __tablename__ = "receipt_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    receipt: Mapped["Receipt"] = relationship(back_populates="photos")


class ReceiptRaw(Base):
    __tablename__ = "receipt_raw"

    receipt_id: Mapped[int] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), primary_key=True
    )
    raw_json: Mapped[str] = mapped_column(Text, nullable=True)

    receipt: Mapped["Receipt"] = relationship(back_populates="raw")


class UserSettings(Base):
    __tablename__ = "user_settings"

    telegram_user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    language: Mapped[str] = mapped_column(String(10), default="ru")
