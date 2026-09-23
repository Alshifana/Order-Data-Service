"""
Generates data/sample_orders.csv — a deliberately messy dataset used to
exercise the cleaning pipeline (duplicates, missing values, bad emails,
negative quantities, inconsistent date formats/casing).

Run once with: python scripts_generate_sample_csv.py
"""
import csv
import random

random.seed(42)

customers = [
    ("Aravind K", "aravind@example.com"),
    ("Ravi Kumar", "ravi.kumar@example.com"),
    ("Priya Sharma", "priya.sharma@example.com"),
    ("John Mathew", "john.mathew@example.com"),
    ("Divya Nair", "divya.nair@example.com"),
    ("Arjun Reddy", "arjun.reddy@example.com"),
    ("Sneha Pillai", "sneha.pillai@example.com"),
    ("Vikram Rao", "vikram.rao@example.com"),
    ("Meera Iyer", "meera.iyer@example.com"),
    ("Karthik S", "karthik.s@example.com"),
]

products = [
    ("Wireless Mouse", "Electronics", 599),
    ("Bluetooth Speaker", "Electronics", 1499),
    ("Notebook Set", "Stationery", 199),
    ("Office Chair", "Furniture", 4999),
    ("Desk Lamp", "Furniture", 899),
    ("Running Shoes", "Footwear", 2499),
    ("Cotton T-Shirt", "Apparel", 399),
    ("Yoga Mat", "Fitness", 799),
    ("Water Bottle", "Fitness", 299),
    ("Backpack", "Accessories", 1299),
]

cities = ["Chennai", "chennai", "Bangalore", "BANGALORE", "Mumbai", "Delhi", "Hyderabad", "Madurai", "Coimbatore", "Kochi"]

date_formats = [
    lambda d: d.strftime("%Y-%m-%d"),
    lambda d: d.strftime("%d/%m/%Y"),
    lambda d: d.strftime("%m-%d-%Y"),
    lambda d: d.strftime("%d %b %Y"),
]

import datetime

rows = []
order_id = 1000

for i in range(55):
    cust = random.choice(customers)
    prod = random.choice(products)
    qty = random.randint(1, 6)
    price = prod[2]
    d = datetime.date(2024, random.randint(1, 12), random.randint(1, 28))
    fmt = random.choice(date_formats)
    city = random.choice(cities)

    name = cust[0]
    email = cust[1]

    # inject inconsistent casing on category/product sometimes
    category = prod[1]
    product = prod[0]
    if random.random() < 0.3:
        category = category.upper()
    if random.random() < 0.3:
        product = product.lower()

    row = {
        "order_id": order_id,
        "customer_name": name,
        "email": email,
        "product": product,
        "category": category,
        "quantity": qty,
        "price": price,
        "order_date": fmt(d),
        "city": city,
    }
    rows.append(row)
    order_id += 1

# --- inject messiness on top of the clean base rows ---

# 1. Duplicates (exact repeats of some rows)
rows.append(dict(rows[3]))
rows.append(dict(rows[10]))
rows.append(dict(rows[10]))

# 2. Missing values
rows[5] = dict(rows[5]); rows[5]["customer_name"] = ""
rows[6] = dict(rows[6]); rows[6]["email"] = ""
rows[7] = dict(rows[7]); rows[7]["price"] = ""
rows[8] = dict(rows[8]); rows[8]["order_date"] = ""

# 3. Invalid emails
rows[9] = dict(rows[9]); rows[9]["email"] = "not-an-email"
rows[11] = dict(rows[11]); rows[11]["email"] = "missing@domain"
rows[12] = dict(rows[12]); rows[12]["email"] = "@nodomain.com"

# 4. Negative / zero quantities
rows[13] = dict(rows[13]); rows[13]["quantity"] = -2
rows[14] = dict(rows[14]); rows[14]["quantity"] = 0

# 5. Negative price
rows[15] = dict(rows[15]); rows[15]["price"] = -500

# 6. Non-numeric quantity/price
rows[16] = dict(rows[16]); rows[16]["quantity"] = "two"
rows[17] = dict(rows[17]); rows[17]["price"] = "N/A"

# 7. Completely empty row (all blanks except order_id)
rows.append({
    "order_id": order_id, "customer_name": "", "email": "", "product": "",
    "category": "", "quantity": "", "price": "", "order_date": "", "city": ""
})
order_id += 1

# 8. Duplicate order_id with different data (data conflict)
dup = dict(rows[20]); dup["order_id"] = rows[19]["order_id"]
rows.append(dup)

random.shuffle(rows)

fieldnames = ["order_id", "customer_name", "email", "product", "category",
              "quantity", "price", "order_date", "city"]

with open("data/sample_orders.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)

print(f"Wrote {len(rows)} rows to data/sample_orders.csv")
