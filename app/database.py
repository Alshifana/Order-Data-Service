"""
app.database
------------
Thin SQLite access layer. Uses plain sqlite3 (no ORM) to keep the
dependency surface small; each function opens its own connection so the
module is safe to use from FastAPI's threaded request handlers.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "orders.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    order_id      TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    email         TEXT NOT NULL,
    product       TEXT NOT NULL,
    category      TEXT NOT NULL,
    quantity      INTEGER NOT NULL,
    price         REAL NOT NULL,
    order_date    TEXT NOT NULL,   -- ISO format YYYY-MM-DD
    city          TEXT NOT NULL
);
"""


@contextmanager
def get_conn(db_path: Path | str | None = None):
    # Resolved at call time (not at import/def time) so tests can monkeypatch
    # module-level DB_PATH and have every function pick up the override.
    path = db_path if db_path is not None else DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path | str | None = None) -> None:
    with get_conn(db_path) as conn:
        conn.execute(SCHEMA)
        conn.commit()


def upsert_orders(records, db_path: Path | str | None = None) -> int:
    """Insert cleaned OrderRecord objects. Existing order_ids are replaced,
    so re-uploading the same (or an overlapping) file is idempotent."""
    with get_conn(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO orders (order_id, customer_name, email, product, category,
                                 quantity, price, order_date, city)
            VALUES (:order_id, :customer_name, :email, :product, :category,
                    :quantity, :price, :order_date, :city)
            ON CONFLICT(order_id) DO UPDATE SET
                customer_name=excluded.customer_name,
                email=excluded.email,
                product=excluded.product,
                category=excluded.category,
                quantity=excluded.quantity,
                price=excluded.price,
                order_date=excluded.order_date,
                city=excluded.city
            """,
            [r.__dict__ for r in records],
        )
        conn.commit()
        return len(records)


def customer_summary(name: str, db_path: Path | str | None = None):
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE customer_name = ? COLLATE NOCASE",
            (name,),
        ).fetchall()
        if not rows:
            return None

        total_orders = len(rows)
        total_spend = sum(r["quantity"] * r["price"] for r in rows)

        category_counts: dict[str, int] = {}
        for r in rows:
            category_counts[r["category"]] = category_counts.get(r["category"], 0) + r["quantity"]
        most_purchased_category = max(category_counts, key=category_counts.get)

        return {
            "customer_name": rows[0]["customer_name"],
            "total_orders": total_orders,
            "total_spend": round(total_spend, 2),
            "most_purchased_category": most_purchased_category,
        }


def top_products(
    limit: int = 5,
    by: str = "revenue",
    offset: int = 0,
    city: str | None = None,
    category: str | None = None,
    db_path: Path | str | None = None,
):
    metric = "SUM(quantity * price)" if by == "revenue" else "SUM(quantity)"
    filters = []
    parameters: list = []
    if city:
        filters.append("city = ? COLLATE NOCASE")
        parameters.append(city)
    if category:
        filters.append("category = ? COLLATE NOCASE")
        parameters.append(category)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    with get_conn(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT product,
                   SUM(quantity) AS total_quantity,
                   ROUND(SUM(quantity * price), 2) AS total_revenue
            FROM orders
            {where_clause}
            GROUP BY product
            ORDER BY {metric} DESC
            LIMIT ? OFFSET ?
            """,
            (*parameters, limit, offset),
        ).fetchall()
        total = conn.execute(
            f"SELECT COUNT(DISTINCT product) FROM orders {where_clause}",
            parameters,
        ).fetchone()[0]
        return {"items": [dict(r) for r in rows], "total": total}


def monthly_revenue(db_path: Path | str | None = None):
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT strftime('%Y-%m', order_date) AS month,
                   ROUND(SUM(quantity * price), 2) AS revenue,
                   COUNT(*) AS order_count
            FROM orders
            GROUP BY month
            ORDER BY month
            """
        ).fetchall()
        return [dict(r) for r in rows]


def city_wise(db_path: Path | str | None = None):
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT city,
                   ROUND(SUM(quantity * price), 2) AS revenue,
                   COUNT(*) AS order_count
            FROM orders
            GROUP BY city
            ORDER BY revenue DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
