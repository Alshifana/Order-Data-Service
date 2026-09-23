from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger("cleaning")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

REQUIRED_FIELDS = [
    "order_id", "customer_name", "email", "product",
    "category", "quantity", "price", "order_date", "city",
]

# Formats we know how to parse, tried in order.
KNOWN_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%d %b %Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
]


@dataclass
class OrderRecord:
    order_id: str
    customer_name: str
    email: str
    product: str
    category: str
    quantity: int
    price: float
    order_date: str  # normalized to YYYY-MM-DD
    city: str


@dataclass
class RejectedRow:
    row_number: int
    order_id: Optional[str]
    reason: str
    raw: dict


@dataclass
class CleaningResult:
    accepted: list
    rejected: list

    @property
    def summary(self) -> dict:
        return {
            "rows_accepted": len(self.accepted),
            "rows_rejected": len(self.rejected),
            "rejection_reasons": [
                {"row_number": r.row_number, "order_id": r.order_id, "reason": r.reason}
                for r in self.rejected
            ],
        }


def _parse_date(raw: str) -> Optional[str]:
    raw = raw.strip()
    for fmt in KNOWN_DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _normalize_text(value: str) -> str:
    """Title-case a free-text field and collapse whitespace."""
    return " ".join(value.strip().split()).title()


def clean_row(row: dict, row_number: int, seen_order_ids: set) -> tuple[Optional[OrderRecord], Optional[RejectedRow]]:
    """Validate + normalize a single raw row. Returns (record, None) on
    success or (None, RejectedRow) on failure."""

    # 0. Missing columns entirely (defensive; ingest layer should catch this)
    missing_cols = [f for f in REQUIRED_FIELDS if f not in row]
    if missing_cols:
        return None, RejectedRow(row_number, row.get("order_id"), f"missing columns: {missing_cols}", row)

    order_id = str(row.get("order_id") or "").strip()
    customer_name = str(row.get("customer_name") or "").strip()
    email = str(row.get("email") or "").strip()
    product = str(row.get("product") or "").strip()
    category = str(row.get("category") or "").strip()
    quantity_raw = str(row.get("quantity") or "").strip()
    price_raw = str(row.get("price") or "").strip()
    order_date_raw = str(row.get("order_date") or "").strip()
    city = str(row.get("city") or "").strip()

    # 1. Required-field presence
    if not order_id:
        return None, RejectedRow(row_number, None, "missing order_id", row)
    if not customer_name:
        return None, RejectedRow(row_number, order_id, "missing customer_name", row)
    if not email:
        return None, RejectedRow(row_number, order_id, "missing email", row)
    if not product:
        return None, RejectedRow(row_number, order_id, "missing product", row)
    if not category:
        return None, RejectedRow(row_number, order_id, "missing category", row)
    if not quantity_raw:
        return None, RejectedRow(row_number, order_id, "missing quantity", row)
    if not price_raw:
        return None, RejectedRow(row_number, order_id, "missing price", row)
    if not order_date_raw:
        return None, RejectedRow(row_number, order_id, "missing order_date", row)
    if not city:
        return None, RejectedRow(row_number, order_id, "missing city", row)

    # 2. Duplicate order_id (keep first occurrence, reject the rest)
    if order_id in seen_order_ids:
        return None, RejectedRow(row_number, order_id, "duplicate order_id", row)

    # 3. Email validity
    if not EMAIL_RE.match(email):
        return None, RejectedRow(row_number, order_id, f"invalid email: '{email}'", row)

    # 4. Quantity: must be a positive integer
    try:
        quantity = int(float(quantity_raw))
    except ValueError:
        return None, RejectedRow(row_number, order_id, f"non-numeric quantity: '{quantity_raw}'", row)
    if quantity <= 0:
        return None, RejectedRow(row_number, order_id, f"non-positive quantity: {quantity}", row)

    # 5. Price: must be a positive number
    try:
        price = float(price_raw)
    except ValueError:
        return None, RejectedRow(row_number, order_id, f"non-numeric price: '{price_raw}'", row)
    if price <= 0:
        return None, RejectedRow(row_number, order_id, f"non-positive price: {price}", row)

    # 6. Date: try known formats; reject if unparseable
    order_date = _parse_date(order_date_raw)
    if order_date is None:
        return None, RejectedRow(row_number, order_id, f"unparseable order_date: '{order_date_raw}'", row)

    # 7. Cosmetic fixes: normalize casing on text fields
    customer_name = _normalize_text(customer_name)
    product = _normalize_text(product)
    category = _normalize_text(category)
    city = _normalize_text(city)
    email = email.lower()

    record = OrderRecord(
        order_id=order_id,
        customer_name=customer_name,
        email=email,
        product=product,
        category=category,
        quantity=quantity,
        price=price,
        order_date=order_date,
        city=city,
    )
    return record, None


def clean_rows(rows: list[dict]) -> CleaningResult:
    """Clean a list of raw dict rows (as produced by csv.DictReader)."""
    accepted: list[OrderRecord] = []
    rejected: list[RejectedRow] = []
    seen_order_ids: set = set()

    for i, row in enumerate(rows, start=1):
        record, rejection = clean_row(row, i, seen_order_ids)
        if record is not None:
            accepted.append(record)
            seen_order_ids.add(record.order_id)
        else:
            logger.info("Row %d rejected: %s", i, rejection.reason)
            rejected.append(rejection)

    return CleaningResult(accepted=accepted, rejected=rejected)
