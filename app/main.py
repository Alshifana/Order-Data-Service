"""
app.main
--------
FastAPI service exposing order ingestion + reporting endpoints.

Run with:  uvicorn app.main:app --reload
Docs at:   http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import csv
import io
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import database as db
from app.cleaning import clean_rows, REQUIRED_FIELDS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="Ondravan Orders Service",
    description="Ingests messy order CSVs, cleans them, stores them in SQLite, "
                "and exposes customer/product/revenue reports.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Static dashboard (bonus)
# ---------------------------------------------------------------------------
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    # 'static' dir may not exist in some execution contexts (e.g. tests) — non-fatal.
    pass


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse("static/dashboard.html")


# ---------------------------------------------------------------------------
# 1. Upload
# ---------------------------------------------------------------------------
@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    raw_bytes = await file.read()
    if not raw_bytes.strip():
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not valid UTF-8 text.")

    try:
        reader = csv.DictReader(io.StringIO(text))
        fieldnames = reader.fieldnames or []
    except csv.Error as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    missing_cols = [c for c in REQUIRED_FIELDS if c not in fieldnames]
    if missing_cols:
        raise HTTPException(
            status_code=400,
            detail=f"CSV is missing required columns: {missing_cols}",
        )

    try:
        rows = list(reader)
    except csv.Error as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV rows: {e}")

    if not rows:
        raise HTTPException(status_code=400, detail="CSV has a header but no data rows.")

    result = clean_rows(rows)

    inserted = 0
    if result.accepted:
        inserted = db.upsert_orders(result.accepted)

    logger.info("Upload: %d accepted, %d rejected", len(result.accepted), len(result.rejected))

    return JSONResponse(
        status_code=201 if inserted else 200,
        content={
            "filename": file.filename,
            "rows_read": len(rows),
            **result.summary,
        },
    )


# ---------------------------------------------------------------------------
# 2. Customer summary
# ---------------------------------------------------------------------------
@app.get("/customers/{name}/summary")
def customer_summary(name: str):
    summary = db.customer_summary(name)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"No orders found for customer '{name}'.")
    return summary


# ---------------------------------------------------------------------------
# 3. Top products
# ---------------------------------------------------------------------------
@app.get("/reports/top-products")
def report_top_products(
    limit: int = Query(5, ge=1, le=100),
    offset: int = Query(0, ge=0),
    by: str = Query("revenue", pattern="^(revenue|quantity)$"),
    city: str | None = Query(None, min_length=1),
    category: str | None = Query(None, min_length=1),
):
    report = db.top_products(
        limit=limit,
        by=by,
        offset=offset,
        city=city,
        category=category,
    )
    return {
        "by": by,
        "limit": limit,
        "offset": offset,
        "city": city,
        "category": category,
        "total": report["total"],
        "products": report["items"],
    }


# ---------------------------------------------------------------------------
# 4. Monthly revenue
# ---------------------------------------------------------------------------
@app.get("/reports/monthly-revenue")
def report_monthly_revenue():
    return {"months": db.monthly_revenue()}


# ---------------------------------------------------------------------------
# 5. City-wise
# ---------------------------------------------------------------------------
@app.get("/reports/city-wise")
def report_city_wise():
    return {"cities": db.city_wise()}
