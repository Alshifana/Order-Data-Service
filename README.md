# Order Data Service

A small backend service that ingests messy order CSV files, cleans and validates the data, stores accepted records in SQLite, and exposes customer and business reports through a REST API built with FastAPI.

This project was built as an engineering exercise focused on **real-world data ingestion, data-quality handling, API design, testing, and clear technical decisions**.

## Features

* CSV upload and validation
* Data cleaning and normalization
* Detailed rejection reasons for invalid rows
* SQLite persistence
* Idempotent uploads using `order_id`
* Customer spending summaries
* Top-product reports by quantity or revenue
* Monthly revenue reports
* City-wise revenue and order-count reports
* Meaningful API error responses
* Unit tests for cleaning logic
* Integration tests for API endpoints
* Simple HTML dashboard
* Dockerfile for containerized deployment

---

## Project Structure

```text
order-data-service/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── cleaning.py
│   └── database.py
│
├── tests/
│   ├── test_cleaning.py
│   └── test_api.py
│
├── static/
│   └── dashboard.html
│
├── data/
│   └── sample_orders.csv
│
├── scripts_generate_sample_csv.py
├── requirements.txt
├── Dockerfile
├── .gitignore
└── README.md
```

### Module responsibilities

* `main.py` — FastAPI application and REST API routes
* `cleaning.py` — CSV validation, normalization, and rejection logic
* `database.py` — SQLite database initialization and SQL queries
* `test_cleaning.py` — Unit tests for data-cleaning rules
* `test_api.py` — Integration tests for API endpoints
* `dashboard.html` — Simple dashboard for viewing reports
* `scripts_generate_sample_csv.py` — Generates the reproducible sample dataset

---

## Requirements

* Python 3.10+
* pip

SQLite is included with Python, so no separate database installation is required.

Docker is optional.

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Alshifana/Order-Data-Service.git
cd Order-Data-Service
```

### 2. Create a virtual environment

#### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

#### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Sample Dataset

A deliberately messy sample CSV containing **60 rows** is included at:

```text
data/sample_orders.csv
```

The dataset contains examples of:

* Duplicate rows
* Duplicate `order_id` values
* Missing values
* Invalid email addresses
* Negative and zero quantities
* Invalid/non-numeric prices
* Multiple date formats
* Inconsistent casing
* Extra whitespace

The sample data can be regenerated using:

```bash
python scripts_generate_sample_csv.py
```

The generator uses a fixed random seed so the resulting dataset is reproducible.

---

## Running the Application

Start the FastAPI development server:

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

### Interactive API Documentation

FastAPI provides Swagger UI automatically:

```text
http://127.0.0.1:8000/docs
```

### Dashboard

A simple report dashboard is available at:

```text
http://127.0.0.1:8000/
```

The SQLite database is automatically created at:

```text
data/orders.db
```

when the application initializes.

---

# API Endpoints

## 1. Upload CSV

```http
POST /upload
```

Upload a CSV file, validate and clean its rows, and store accepted records in SQLite.

Example:

```bash
curl -X POST \
  -F "file=@data/sample_orders.csv" \
  http://127.0.0.1:8000/upload
```

Example response:

```json
{
  "filename": "sample_orders.csv",
  "rows_read": 60,
  "rows_accepted": 43,
  "rows_rejected": 17,
  "rejection_reasons": [
    {
      "row_number": 1,
      "order_id": "1008",
      "reason": "missing order_date"
    },
    {
      "row_number": 3,
      "order_id": "1055",
      "reason": "missing customer_name"
    },
    {
      "row_number": 34,
      "order_id": "1009",
      "reason": "invalid email: 'not-an-email'"
    }
  ]
}
```

Each rejected row contains:

* CSV row number
* `order_id`, when available
* Specific rejection reason

---

## 2. Customer Summary

```http
GET /customers/{name}/summary
```

Returns the customer's:

* Total number of orders
* Total spending
* Most purchased category

Example:

```bash
curl "http://127.0.0.1:8000/customers/Karthik%20S/summary"
```

Example response:

```json
{
  "customer_name": "Karthik S",
  "total_orders": 3,
  "total_spend": 6392.0,
  "most_purchased_category": "Fitness"
}
```

Customer name lookup is case-insensitive.

---

## 3. Top Products

```http
GET /reports/top-products
```

Returns the top products based on quantity or revenue.

Parameters:

* `limit` — Number of products to return
* `by` — `revenue` or `quantity`

Example:

```bash
curl "http://127.0.0.1:8000/reports/top-products?limit=3&by=revenue"
```

The default ranking is by revenue.

---

## 4. Monthly Revenue

```http
GET /reports/monthly-revenue
```

Returns revenue grouped by month.

Example:

```bash
curl "http://127.0.0.1:8000/reports/monthly-revenue"
```

Example result:

```json
[
  {
    "month": "2026-01",
    "revenue": 12500.0
  },
  {
    "month": "2026-02",
    "revenue": 14320.5
  }
]
```

---

## 5. City-wise Report

```http
GET /reports/city-wise
```

Returns revenue and order count grouped by city.

Example:

```bash
curl "http://127.0.0.1:8000/reports/city-wise"
```

Example result:

```json
[
  {
    "city": "Chennai",
    "order_count": 15,
    "revenue": 23450.0
  }
]
```

---

# Data Cleaning Rules

The cleaning module follows an important principle:

> **Fix data when the correction is unambiguous; reject data when fixing it would require guessing the client's intent.**

## Rows are rejected when:

* A required field is missing or empty
* `order_id` is duplicated within the same upload
* `order_id` conflicts with an already accepted row in the same upload
* Email does not match the expected basic email format
* Quantity is not a positive integer
* Price is not a positive number
* Order date cannot be parsed using the supported date formats

Invalid rows are **not silently inserted into the database**.

## Cosmetic problems are normalized

The following fields are cleaned:

* `customer_name`
* `product`
* `category`
* `city`

Leading/trailing whitespace is removed, repeated whitespace is collapsed, and text is normalized to title case.

For example:

```text
"  JOHN   smith  "
```

becomes:

```text
"John Smith"
```

Emails are normalized to lowercase:

```text
"JOHN@EXAMPLE.COM"
```

becomes:

```text
"john@example.com"
```

Dates are normalized to:

```text
YYYY-MM-DD
```

The cleaning module supports the following input formats:

```text
YYYY-MM-DD
DD/MM/YYYY
MM-DD-YYYY
DD Mon YYYY
DD-MM-YYYY
YYYY/MM/DD
```

---

# Duplicate Handling and Idempotency

`order_id` is used as the primary key.

The service distinguishes between duplicates **within the same upload** and records that already exist in the database.

### Duplicate within the same CSV

If the same `order_id` appears multiple times in one uploaded file:

* The first valid occurrence is accepted.
* Later occurrences are rejected and logged.

This is treated as a data-quality issue because two rows in the same file claiming to represent the same order are ambiguous.

### Existing order from a previous upload

If an uploaded `order_id` already exists in the database, the existing record is updated rather than creating a duplicate.

This makes uploads effectively idempotent and supports a workflow where a client may resend previously submitted orders with corrected information.

---

# Error Handling

The API explicitly handles common input errors.

Examples include:

* Non-CSV file
* Empty file
* Header-only CSV
* Missing required columns
* Invalid CSV structure
* Invalid row data

These return meaningful `400 Bad Request` responses instead of generic server errors.

---

# Testing

The project uses `pytest`.

Run all tests with:

```bash
python -m pytest -v
```

The test suite covers:

### Cleaning tests

* Missing required values
* Invalid emails
* Negative quantities
* Zero quantities
* Invalid prices
* Invalid dates
* Date normalization
* Text normalization
* Duplicate order IDs

### API tests

* CSV upload
* Customer summary
* Top-products report
* Monthly revenue
* City-wise report
* Invalid file formats
* Missing columns
* Empty files
* Invalid upload data

---

# Docker

A `Dockerfile` is included as an optional deployment setup.

Build the image:

```bash
docker build -t order-data-service .
```

Run the container:

```bash
docker run -p 8000:8000 order-data-service
```

Docker execution was not part of the primary local development workflow. The application was developed and tested using a Python virtual environment.

## CI/CD

The GitHub Actions workflow at `.github/workflows/ci-cd.yml` runs for pull requests and pushes to `main` or `master`.

It:

* Runs the test suite on Python 3.10 through 3.13
* Builds the Docker image as a container validation step
* Publishes the image to GitHub Container Registry on pushes to `main`

The published image is available as:

```text
ghcr.io/<github-owner>/<repository>:latest
```

---

# Design Decisions

## 1. SQLite instead of a larger database

SQLite was selected because this assignment is a small, self-contained service and does not require a separate database server.

It also keeps setup simple for evaluation.

The database access is isolated inside `database.py`, making it easier to migrate to PostgreSQL or another database later.

## 2. Plain `sqlite3` instead of an ORM

The service uses Python's built-in `sqlite3` module rather than an ORM.

This keeps the dependency surface small and makes the SQL queries explicit.

For a larger production system, SQLAlchemy or another database abstraction could be introduced.

## 3. Reject ambiguous data instead of silently correcting it

For example, a quantity of:

```text
-5
```

is rejected rather than converted to:

```text
5
```

Changing the sign could hide an actual business event such as a return or correction.

Since the CSV does not contain an `order_type` field, the safest decision is to reject the ambiguous value.

## 4. Most purchased category

`most_purchased_category` is calculated using the **total quantity purchased** within each category.

This is preferred over counting distinct orders because the requirement refers to the category purchased in the greatest quantity.

## 5. Top products

The top-products endpoint supports both:

```text
by=revenue
```

and:

```text
by=quantity
```

This avoids assuming that "top product" has only one business definition.

## 6. Case-insensitive customer lookup

Customer names are normalized during ingestion and queried case-insensitively so that differences such as:

```text
Karthik S
karthik s
KARTHIK S
```

do not prevent a customer from being found.

---

# What I Would Do Next for Production

If this service needed to move beyond the scope of this assignment, I would consider:

* PostgreSQL instead of SQLite
* SQLAlchemy and database migrations
* Authentication and authorization
* Rate limiting
* Pagination and filtering on report endpoints
* Date-range filters
* Persistent storage of rejected rows
* Background processing for large CSV uploads
* Structured logging and centralized monitoring
* Request IDs for tracing
* Automated CI/CD
* Property-based testing with Hypothesis
* Data validation using stronger schemas and constraints

For very large CSV files, I would also avoid loading the entire dataset into memory at once and process the file in batches or streams.

---

# Assumptions

* `order_id` uniquely identifies an order.
* Quantity must be a positive integer.
* Price must be a positive number.
* Revenue is calculated as:

```text
quantity × price
```

* The provided date formats are the supported input formats.
* Customer names are used for lookup because the input specification does not provide a separate customer ID.
* Invalid or ambiguous records are rejected rather than silently modified.
* SQLite is sufficient for the scope of this assignment.

---

## License

This project was created as a technical assignment and demonstration project.
