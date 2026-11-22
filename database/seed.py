"""Create a small reproducible commerce database for natural-language SQL demos.

Running this script DROPS and recreates customers, orders, and sales.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from sqlalchemy import create_engine, text
from app.config import database_path

SCHEMA = """
PRAGMA foreign_keys = ON;
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL,
    city TEXT NOT NULL,
    region TEXT NOT NULL,
    segment TEXT NOT NULL
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('Delivered','Shipped','Processing','Cancelled')),
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE sales (
    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price >= 0),
    unit_cost REAL NOT NULL CHECK(unit_cost >= 0),
    discount_pct REAL NOT NULL DEFAULT 0 CHECK(discount_pct >= 0 AND discount_pct <= 1),
    FOREIGN KEY(order_id) REFERENCES orders(order_id)
);

CREATE INDEX idx_orders_order_date ON orders(order_date);
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_sales_order_id ON sales(order_id);
CREATE INDEX idx_sales_category ON sales(category);
"""

CUSTOMERS = [
    (1, "Aarav Sharma", "Chennai", "South", "Consumer"),
    (2, "Diya Patel", "Mumbai", "West", "Small Business"),
    (3, "Ishaan Reddy", "Hyderabad", "South", "Consumer"),
    (4, "Ananya Iyer", "Bengaluru", "South", "Enterprise"),
    (5, "Vivaan Gupta", "Delhi", "North", "Small Business"),
    (6, "Meera Nair", "Kochi", "South", "Consumer"),
]
ORDERS = [
    ("ORD-1001", 1, "2026-01-05", "Delivered"),
    ("ORD-1002", 2, "2026-01-18", "Delivered"),
    ("ORD-1003", 3, "2026-02-11", "Shipped"),
    ("ORD-1004", 4, "2026-02-26", "Delivered"),
    ("ORD-1005", 5, "2026-03-09", "Delivered"),
    ("ORD-1006", 1, "2026-03-21", "Processing"),
    ("ORD-1007", 6, "2026-04-02", "Delivered"),
    ("ORD-1008", 2, "2026-04-16", "Cancelled"),
    ("ORD-1009", 3, "2026-05-04", "Shipped"),
    ("ORD-1010", 4, "2026-05-19", "Delivered"),
]
SALES = [
    ("ORD-1001", "Wireless Mouse", "Accessories", 2, 899.0, 420.0, 0.05),
    ("ORD-1001", "Mechanical Keyboard", "Accessories", 1, 3499.0, 1900.0, 0.0),
    ("ORD-1002", "27-inch Monitor", "Displays", 1, 16999.0, 11800.0, 0.10),
    ("ORD-1002", "USB-C Hub", "Accessories", 2, 2199.0, 1100.0, 0.0),
    ("ORD-1003", "Noise-Cancelling Headphones", "Audio", 1, 5999.0, 3600.0, 0.05),
    ("ORD-1003", "Wireless Mouse", "Accessories", 1, 899.0, 420.0, 0.0),
    ("ORD-1004", "Laptop Stand", "Accessories", 2, 1499.0, 650.0, 0.0),
    ("ORD-1004", "Portable SSD 1TB", "Storage", 1, 7499.0, 5200.0, 0.08),
    ("ORD-1005", "Bluetooth Speaker", "Audio", 2, 2799.0, 1450.0, 0.05),
    ("ORD-1005", "Webcam HD", "Accessories", 1, 3299.0, 1850.0, 0.0),
    ("ORD-1006", "Ergonomic Chair", "Furniture", 1, 12999.0, 9100.0, 0.0),
    ("ORD-1006", "Desk Lamp", "Furniture", 2, 1699.0, 780.0, 0.05),
    ("ORD-1007", "Tablet 10-inch", "Devices", 1, 18999.0, 14200.0, 0.0),
    ("ORD-1007", "USB Flash Drive 128GB", "Storage", 3, 799.0, 360.0, 0.0),
    ("ORD-1008", "Wi-Fi Router", "Networking", 1, 2599.0, 1550.0, 0.0),
    ("ORD-1008", "Mesh Wi-Fi Node", "Networking", 1, 4999.0, 3150.0, 0.0),
    ("ORD-1009", "24-inch Monitor", "Displays", 2, 11999.0, 8100.0, 0.05),
    ("ORD-1009", "Laptop Backpack", "Bags", 1, 1899.0, 850.0, 0.0),
    ("ORD-1010", "Wireless Mouse", "Accessories", 3, 899.0, 420.0, 0.10),
    ("ORD-1010", "Mechanical Keyboard", "Accessories", 1, 3499.0, 1900.0, 0.05),
]


def seed_database(path: str | Path | None = None) -> Path:
    target = Path(path) if path else database_path()
    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{target}")
    try:
        raw = engine.raw_connection()
        try:
            cursor = raw.cursor()
            cursor.executescript(SCHEMA)
            cursor.executemany(
                "INSERT INTO customers(customer_id,customer_name,city,region,segment) VALUES(?,?,?,?,?)",
                CUSTOMERS,
            )
            cursor.executemany(
                "INSERT INTO orders(order_id,customer_id,order_date,status) VALUES(?,?,?,?)",
                ORDERS,
            )
            cursor.executemany(
                "INSERT INTO sales(order_id,product_name,category,quantity,unit_price,unit_cost,discount_pct) VALUES(?,?,?,?,?,?,?)",
                SALES,
            )
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()
    finally:
        engine.dispose()
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Recreate the sample analytics database.")
    parser.add_argument("--db", type=Path, default=None, help="Optional database file path.")
    args = parser.parse_args()
    result = seed_database(args.db)
    print(f"Sample database recreated: {result}")


if __name__ == "__main__":
    main()
