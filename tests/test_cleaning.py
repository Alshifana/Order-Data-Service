import pytest
from app.cleaning import clean_row, clean_rows, OrderRecord


def base_row(**overrides):
    row = {
        "order_id": "1001",
        "customer_name": "jane doe",
        "email": "jane.doe@example.com",
        "product": "wireless mouse",
        "category": "electronics",
        "quantity": "2",
        "price": "599",
        "order_date": "2024-05-01",
        "city": "chennai",
    }
    row.update(overrides)
    return row


def test_valid_row_is_accepted_and_normalized():
    record, rejection = clean_row(base_row(), 1, set())
    assert rejection is None
    assert isinstance(record, OrderRecord)
    assert record.customer_name == "Jane Doe"
    assert record.category == "Electronics"
    assert record.email == "jane.doe@example.com"
    assert record.quantity == 2
    assert record.price == 599.0
    assert record.order_date == "2024-05-01"


@pytest.mark.parametrize(
    "date_str,expected",
    [
        ("2024-05-01", "2024-05-01"),
        ("01/05/2024", "2024-05-01"),
        ("05-01-2024", "2024-05-01"),
        ("01 May 2024", "2024-05-01"),
    ],
)
def test_various_date_formats_are_normalized(date_str, expected):
    record, rejection = clean_row(base_row(order_date=date_str), 1, set())
    assert rejection is None
    assert record.order_date == expected


def test_unparseable_date_is_rejected():
    record, rejection = clean_row(base_row(order_date="not-a-date"), 1, set())
    assert record is None
    assert "order_date" in rejection.reason


@pytest.mark.parametrize("bad_email", ["not-an-email", "missing@domain", "@nodomain.com", ""])
def test_invalid_email_is_rejected(bad_email):
    record, rejection = clean_row(base_row(email=bad_email), 1, set())
    assert record is None
    assert rejection is not None


def test_missing_customer_name_is_rejected():
    record, rejection = clean_row(base_row(customer_name=""), 1, set())
    assert record is None
    assert "customer_name" in rejection.reason


@pytest.mark.parametrize("bad_qty", ["-2", "0", "two", ""])
def test_bad_quantity_is_rejected(bad_qty):
    record, rejection = clean_row(base_row(quantity=bad_qty), 1, set())
    assert record is None


@pytest.mark.parametrize("bad_price", ["-500", "0", "N/A", ""])
def test_bad_price_is_rejected(bad_price):
    record, rejection = clean_row(base_row(price=bad_price), 1, set())
    assert record is None


def test_duplicate_order_id_is_rejected():
    seen = {"1001"}
    record, rejection = clean_row(base_row(), 2, seen)
    assert record is None
    assert "duplicate" in rejection.reason


def test_inconsistent_casing_is_normalized():
    record, _ = clean_row(
        base_row(customer_name="JOHN   smith", category="FURNITURE", city="bangalore"),
        1,
        set(),
    )
    assert record.customer_name == "John Smith"
    assert record.category == "Furniture"
    assert record.city == "Bangalore"


def test_clean_rows_deduplicates_across_batch():
    rows = [base_row(order_id="2001"), base_row(order_id="2001")]
    result = clean_rows(rows)
    assert len(result.accepted) == 1
    assert len(result.rejected) == 1
    assert "duplicate" in result.rejected[0].reason


def test_clean_rows_summary_counts():
    rows = [
        base_row(order_id="3001"),
        base_row(order_id="3002", email="bad-email"),
        base_row(order_id="3003", quantity="-1"),
    ]
    result = clean_rows(rows)
    summary = result.summary
    assert summary["rows_accepted"] == 1
    assert summary["rows_rejected"] == 2
    assert len(summary["rejection_reasons"]) == 2


def test_missing_required_column_in_row_dict():
    row = base_row()
    del row["email"]
    record, rejection = clean_row(row, 1, set())
    assert record is None
    assert "missing columns" in rejection.reason
