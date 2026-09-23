import io
import os

os.environ.setdefault("TESTING", "1")

import pytest
from fastapi.testclient import TestClient

from app import database as db
from app.main import app

VALID_CSV = (
    "order_id,customer_name,email,product,category,quantity,price,order_date,city\n"
    "1,Jane Doe,jane@example.com,Wireless Mouse,Electronics,2,599,2024-05-01,Chennai\n"
    "2,John Smith,john@example.com,Desk Lamp,Furniture,1,899,2024-05-15,Bangalore\n"
    "3,Jane Doe,jane@example.com,Yoga Mat,Fitness,3,799,2024-06-02,Chennai\n"
    "4,bad-row,not-an-email,Backpack,Accessories,1,1299,2024-06-10,Mumbai\n"
    "5,Neg Qty,neg@example.com,Water Bottle,Fitness,-1,299,2024-06-11,Delhi\n"
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_db = tmp_path / "test_orders.db"
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db(test_db)
    with TestClient(app) as c:
        yield c


def upload(client, content=VALID_CSV, filename="orders.csv"):
    return client.post(
        "/upload",
        files={"file": (filename, io.BytesIO(content.encode("utf-8")), "text/csv")},
    )


def test_upload_valid_csv_returns_summary(client):
    resp = upload(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["rows_accepted"] == 3
    assert body["rows_rejected"] == 2


def test_upload_rejects_non_csv_file(client):
    resp = client.post(
        "/upload",
        files={"file": ("orders.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_rejects_empty_file(client):
    resp = client.post(
        "/upload",
        files={"file": ("orders.csv", io.BytesIO(b""), "text/csv")},
    )
    assert resp.status_code == 400


def test_upload_rejects_missing_columns(client):
    bad_csv = "order_id,customer_name\n1,Jane\n"
    resp = upload(client, content=bad_csv)
    assert resp.status_code == 400
    assert "missing required columns" in resp.json()["detail"]


def test_customer_summary_after_upload(client):
    upload(client)
    resp = client.get("/customers/Jane Doe/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_orders"] == 2
    assert body["total_spend"] == pytest.approx(2 * 599 + 3 * 799)
    assert body["most_purchased_category"] in ("Electronics", "Fitness")


def test_customer_summary_not_found(client):
    resp = client.get("/customers/Nobody/summary")
    assert resp.status_code == 404


def test_top_products_report(client):
    upload(client)
    resp = client.get("/reports/top-products?limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["products"]) <= 2
    assert body["total"] >= len(body["products"])


def test_top_products_supports_pagination_and_filters(client):
    upload(client)
    resp = client.get(
        "/reports/top-products?limit=1&offset=1&city=Chennai&category=electronics"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["offset"] == 1
    assert body["city"] == "Chennai"
    assert body["category"] == "electronics"
    assert body["total"] == 1
    assert len(body["products"]) == 0


def test_monthly_revenue_report(client):
    upload(client)
    resp = client.get("/reports/monthly-revenue")
    assert resp.status_code == 200
    months = resp.json()["months"]
    assert any(m["month"] == "2024-05" for m in months)


def test_city_wise_report(client):
    upload(client)
    resp = client.get("/reports/city-wise")
    assert resp.status_code == 200
    cities = {c["city"] for c in resp.json()["cities"]}
    assert "Chennai" in cities
