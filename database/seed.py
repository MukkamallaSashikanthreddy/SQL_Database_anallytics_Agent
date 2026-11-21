"""Create a reproducible sample commerce database for local analytics."""

from __future__ import annotations

import argparse
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.config import DATABASE_PATH

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL,
    city TEXT NOT NULL,
    region TEXT NOT NULL,
    segment TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    unit_cost REAL NOT NULL CHECK (unit_cost >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    status TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    discount_pct REAL NOT NULL DEFAULT 0 CHECK (discount_pct >= 0 AND discount_pct <= 1),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_order_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);
"""

CUSTOMER_NAMES = [
    "Aarav Sharma", "Diya Patel", "Ishaan Reddy", "Ananya Iyer", "Vivaan Gupta",
    "Meera Nair", "Arjun Kumar", "Saanvi Shah", "Aditya Rao", "Aadhya Singh",
    "Reyansh Das", "Kiara Mehta", "Atharv Joshi", "Myra Menon", "Kabir Verma",
    "Ira Kapoor", "Rohan Pillai", "Tara Chawla", "Dev Malhotra", "Navya Bose",
]

LOCATIONS = [
    ("Chennai", "South"), ("Bengaluru", "South"), ("Hyderabad", "South"),
    ("Kochi", "South"), ("Mumbai", "West"), ("Pune", "West"),
    ("Ahmedabad", "West"), ("Delhi", "North"), ("Jaipur", "North"),
    ("Lucknow", "North"), ("Kolkata", "East"), ("Bhubaneswar", "East"),
]

PRODUCTS = [
    ("Wireless Mouse", "Accessories", 899.0, 420.0),
    ("Mechanical Keyboard", "Accessories", 3499.0, 1900.0),
    ("USB-C Hub", "Accessories", 2199.0, 1100.0),
    ("27-inch Monitor", "Displays", 16999.0, 11800.0),
    ("24-inch Monitor", "Displays", 11999.0, 8100.0),
    ("Laptop Stand", "Accessories", 1499.0, 650.0),
    ("Noise-Cancelling Headphones", "Audio", 5999.0, 3600.0),
    ("Bluetooth Speaker", "Audio", 2799.0, 1450.0),
    ("Webcam HD", "Accessories", 3299.0, 1850.0),
    ("Portable SSD 1TB", "Storage", 7499.0, 5200.0),
    ("External HDD 2TB", "Storage", 6299.0, 4300.0),
    ("Wi-Fi Router", "Networking", 2599.0, 1550.0),
    ("Mesh Wi-Fi Node", "Networking", 4999.0, 3150.0),
    ("Laptop Backpack", "Bags", 1899.0, 850.0),
    ("USB Flash Drive 128GB", "Storage", 799.0, 360.0),
    ("Ergonomic Chair", "Furniture", 12999.0, 9100.0),
    ("Desk Lamp", "Furniture", 1699.0, 780.0),
    ("Tablet 10-inch", "Devices", 18999.0, 14200.0),
]


def _create_customers(rng: random.Random, today: date) -> list[tuple[Any, ...]]:
    rows = []
    segments = ["Consumer", "Small Business", "Enterprise"]
    for customer_id in range(1, 121):
        base = CUSTOMER_NAMES[(customer_id - 1) % len(CUSTOMER_NAMES)]
        name = f"{base} {customer_id:03d}"
        city, region = LOCATIONS[(customer_id - 1) % len(LOCATIONS)]
        created = today - timedelta(days=rng.randint(60, 900))
        rows.append((customer_id, name, city, region, rng.choices(segments, [0.62, 0.28, 0.10])[0], created.isoformat()))
    return rows


def _create_orders_and_items(
    rng: random.Random, today: date, order_count: int = 720
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    orders: list[tuple[Any, ...]] = []
    items: list[tuple[Any, ...]] = []
    statuses = ["Delivered", "Delivered", "Delivered", "Shipped", "Processing", "Cancelled"]
    payment_methods = ["UPI", "Credit Card", "Debit Card", "Net Banking", "Cash on Delivery"]
    product_weights = [1.5, 1.1, 1.4, 0.85, 0.9, 1.3, 0.8, 1.0, 1.2, 0.7, 0.65, 0.9, 0.55, 1.1, 1.25, 0.35, 0.7, 0.4]
    item_id = 1

    for order_id in range(1, order_count + 1):
        # Generate realistic history across the previous 18 months.
        days_ago = rng.randint(0, 540)
        order_day = today - timedelta(days=days_ago)
        customer_id = rng.randint(1, 120)
        orders.append((
            order_id,
            customer_id,
            order_day.isoformat(),
            rng.choice(statuses),
            rng.choice(payment_methods),
        ))

        item_count = rng.choices([1, 2, 3, 4], [0.48, 0.34, 0.14, 0.04])[0]
        chosen_products = rng.choices(range(1, len(PRODUCTS) + 1), weights=product_weights, k=item_count)
        for product_id in chosen_products:
            _, _, price, _ = PRODUCTS[product_id - 1]
            # Small seasonality and promotional variation make the dataset useful for analysis.
            seasonal_factor = 1.08 if order_day.month in (10, 11, 12) else 1.0
            quantity = max(1, int(round(rng.choices([1, 2, 3, 4], [0.60, 0.25, 0.11, 0.04])[0] * seasonal_factor)))
            discount = rng.choice([0.0, 0.0, 0.05, 0.10, 0.15])
            items.append((item_id, order_id, product_id, quantity, price, discount))
            item_id += 1

    return orders, items


def seed_database(db_path: str | Path = DATABASE_PATH, *, reset: bool = False) -> Path:
    """Create and populate the sample database. Safe to run repeatedly."""
    path = Path(db_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    if reset and path.exists():
        path.unlink()

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA_SQL)

        product_count = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if product_count == 0:
            today = date.today()
            rng = random.Random(20261121)
            customers = _create_customers(rng, today)
            products = [(idx, *row) for idx, row in enumerate(PRODUCTS, start=1)]
            orders, items = _create_orders_and_items(rng, today)

            connection.executemany(
                "INSERT INTO customers (customer_id, customer_name, city, region, segment, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                customers,
            )
            connection.executemany(
                "INSERT INTO products (product_id, product_name, category, unit_price, unit_cost) VALUES (?, ?, ?, ?, ?)",
                products,
            )
            connection.executemany(
                "INSERT INTO orders (order_id, customer_id, order_date, status, payment_method) VALUES (?, ?, ?, ?, ?)",
                orders,
            )
            connection.executemany(
                "INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price, discount_pct) VALUES (?, ?, ?, ?, ?, ?)",
                items,
            )
        connection.commit()

    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the SQL Analytics Agent sample database.")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate the sample database.")
    parser.add_argument("--db", type=Path, default=DATABASE_PATH, help="Optional database file path.")
    args = parser.parse_args()
    path = seed_database(args.db, reset=args.reset)
    with sqlite3.connect(path) as connection:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("customers", "products", "orders", "order_items")
        }
    print(f"Database ready: {path}")
    for table, count in counts.items():
        print(f"  {table}: {count:,} rows")


if __name__ == "__main__":
    main()
