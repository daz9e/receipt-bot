import logging
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "/data/receipts.db")
engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Read-only connection for the query agent
engine_ro = create_async_engine(
    f"sqlite+aiosqlite:///file:{DB_PATH}?mode=ro&uri=true", echo=False
)
SessionReadOnly = async_sessionmaker(engine_ro, expire_on_commit=False)

_SEED_CATEGORIES = [
    ("food", "Продукты", "Food"),
    ("beverage", "Напитки", "Beverages"),
    ("bakery", "Выпечка", "Bakery"),
    ("hygiene", "Гигиена", "Hygiene"),
    ("alcohol", "Алкоголь", "Alcohol"),
    ("electronics", "Электроника", "Electronics"),
    ("clothing", "Одежда", "Clothing"),
    ("other", "Другое", "Other"),
]

_MIGRATIONS = [
    # --- legacy migrations (safe to re-run) ---
    "ALTER TABLE receipts ADD COLUMN purchase_time TEXT",
    "ALTER TABLE receipts ADD COLUMN discount_amount REAL",
    "ALTER TABLE receipts ADD COLUMN payment_method TEXT",
    "ALTER TABLE receipts ADD COLUMN address TEXT",
    "ALTER TABLE receipts ADD COLUMN receipt_number TEXT",
    "ALTER TABLE receipts ADD COLUMN image_hash TEXT",
    "ALTER TABLE receipts ADD COLUMN purchase_fingerprint TEXT",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_receipts_image_hash ON receipts (image_hash)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_receipts_purchase_fp ON receipts (purchase_fingerprint)",
    # --- new normalized tables (create_all handles these, but migrations handle columns) ---
    "ALTER TABLE receipts ADD COLUMN merchant_id INTEGER REFERENCES merchants(id)",
    "ALTER TABLE receipt_items ADD COLUMN product_id INTEGER REFERENCES products(id)",
    "ALTER TABLE receipt_items ADD COLUMN category_id INTEGER REFERENCES categories(id)",
    # --- indexes ---
    "CREATE INDEX IF NOT EXISTS ix_receipts_purchase_date ON receipts (purchase_date)",
    "CREATE INDEX IF NOT EXISTS ix_receipts_merchant_id ON receipts (merchant_id)",
    "CREATE INDEX IF NOT EXISTS ix_receipts_telegram_user_id ON receipts (telegram_user_id)",
    "CREATE INDEX IF NOT EXISTS ix_receipt_items_product_id ON receipt_items (product_id)",
    "CREATE INDEX IF NOT EXISTS ix_receipt_items_category_id ON receipt_items (category_id)",
]


async def _seed_categories(conn):
    """Insert seed categories if table is empty."""
    result = await conn.execute(text("SELECT COUNT(*) FROM categories"))
    count = result.scalar()
    if count == 0:
        for name, ru, en in _SEED_CATEGORIES:
            await conn.execute(
                text(
                    "INSERT OR IGNORE INTO categories (name, display_name_ru, display_name_en) "
                    "VALUES (:name, :ru, :en)"
                ),
                {"name": name, "ru": ru, "en": en},
            )


async def _migrate_existing_data(conn):
    """Migrate data from denormalized columns to new tables."""
    # Migrate merchants from receipts
    await conn.execute(
        text(
            "INSERT OR IGNORE INTO merchants (name) "
            "SELECT DISTINCT merchant FROM receipts WHERE merchant IS NOT NULL"
        )
    )
    # Set merchant_id on receipts that don't have it yet
    await conn.execute(
        text(
            "UPDATE receipts SET merchant_id = ("
            "  SELECT m.id FROM merchants m WHERE m.name = receipts.merchant"
            ") WHERE merchant IS NOT NULL AND merchant_id IS NULL"
        )
    )

    # Migrate products from receipt_items
    await conn.execute(
        text(
            "INSERT OR IGNORE INTO products (name) "
            "SELECT DISTINCT name FROM receipt_items WHERE name IS NOT NULL"
        )
    )
    # Set product_id on receipt_items
    await conn.execute(
        text(
            "UPDATE receipt_items SET product_id = ("
            "  SELECT p.id FROM products p WHERE p.name = receipt_items.name"
            ") WHERE name IS NOT NULL AND product_id IS NULL"
        )
    )

    # Set category_id on receipt_items from matching categories
    await conn.execute(
        text(
            "UPDATE receipt_items SET category_id = ("
            "  SELECT c.id FROM categories c WHERE c.name = receipt_items.category"
            ") WHERE category IS NOT NULL AND category_id IS NULL"
        )
    )

    # Set category_id on products from their most common receipt_item category
    await conn.execute(
        text(
            "UPDATE products SET category_id = ("
            "  SELECT ri.category_id FROM receipt_items ri "
            "  WHERE ri.product_id = products.id AND ri.category_id IS NOT NULL "
            "  GROUP BY ri.category_id ORDER BY COUNT(*) DESC LIMIT 1"
            ") WHERE category_id IS NULL"
        )
    )

    # Migrate file_path -> receipt_photos
    # Only for receipts that have file_path but no photos yet
    result = await conn.execute(
        text(
            "SELECT r.id, r.file_path FROM receipts r "
            "WHERE r.file_path IS NOT NULL "
            "AND r.id NOT IN (SELECT DISTINCT receipt_id FROM receipt_photos)"
        )
    )
    rows = result.fetchall()
    for receipt_id, file_path in rows:
        for i, path in enumerate(p.strip() for p in file_path.split(",") if p.strip()):
            await conn.execute(
                text(
                    "INSERT INTO receipt_photos (receipt_id, file_path, sort_order) "
                    "VALUES (:rid, :fp, :so)"
                ),
                {"rid": receipt_id, "fp": path, "so": i},
            )

    # Migrate raw_text -> receipt_raw
    result = await conn.execute(
        text(
            "SELECT r.id, r.raw_text FROM receipts r "
            "WHERE r.raw_text IS NOT NULL "
            "AND r.id NOT IN (SELECT receipt_id FROM receipt_raw)"
        )
    )
    rows = result.fetchall()
    for receipt_id, raw_text in rows:
        await conn.execute(
            text(
                "INSERT INTO receipt_raw (receipt_id, raw_json) VALUES (:rid, :rj)"
            ),
            {"rid": receipt_id, "rj": raw_text},
        )


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        for sql in _MIGRATIONS:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass  # column/index already exists

        try:
            await _seed_categories(conn)
        except Exception:
            logger.warning("Failed to seed categories", exc_info=True)

        try:
            await _migrate_existing_data(conn)
        except Exception:
            logger.warning("Data migration encountered issues", exc_info=True)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
