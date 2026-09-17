"""
setup_db.py
-----------
Creates a small SQLite database (lumen.db) with a simple e-commerce schema
and sample data. This is our "raw data layer", the base tables that the
transformation queries (transformations.sql) will build on top of.

Schema:
  customers(customer_id, name, email, country, signup_date)
  categories(category_id, name)
  suppliers(supplier_id, name, country)
  products(product_id, name, category_id, supplier_id, price)
  orders(order_id, customer_id, order_date, status)
  order_items(order_item_id, order_id, product_id, quantity, unit_price)
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "lumen.db")

SCHEMA = """
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    country TEXT NOT NULL,
    signup_date TEXT NOT NULL
);

CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE suppliers (
    supplier_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT NOT NULL
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    price REAL NOT NULL,
    FOREIGN KEY (category_id) REFERENCES categories(category_id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
"""

CUSTOMERS = [
    (1, "Aarav Sharma", "aarav@example.com", "India", "2022-03-14"),
    (2, "Mei Lin", "mei@example.com", "Singapore", "2023-06-01"),
    (3, "John Smith", "john@example.com", "USA", "2021-11-20"),
    (4, "Fatima Khan", "fatima@example.com", "UAE", "2023-01-10"),
    (5, "Carlos Diaz", "carlos@example.com", "Mexico", "2022-09-05"),
    (6, "Priya Nair", "priya@example.com", "India", "2024-02-18"),
    (7, "Tom Becker", "tom@example.com", "Germany", "2021-05-30"),
    (8, "Yuki Tanaka", "yuki@example.com", "Japan", "2023-08-22"),
]

CATEGORIES = [
    (1, "Electronics"),
    (2, "Home & Kitchen"),
    (3, "Books"),
    (4, "Sportswear"),
    (5, "Office Supplies"),
]

SUPPLIERS = [
    (1, "TechSource Ltd", "China"),
    (2, "HomeGoods Co", "India"),
    (3, "PageTurner Inc", "USA"),
    (4, "ActiveWear Group", "Vietnam"),
]

PRODUCTS = [
    (1, "Wireless Earbuds", 1, 1, 39.99),
    (2, "4K Monitor", 1, 1, 249.99),
    (3, "Smart Watch", 1, 1, 89.99),
    (4, "Non-stick Pan Set", 2, 2, 34.50),
    (5, "Electric Kettle", 2, 2, 22.00),
    (6, "Data Engineering Handbook", 3, 3, 28.00),
    (7, "Intro to Knowledge Graphs", 3, 3, 32.00),
    (8, "Running Shoes", 4, 4, 59.99),
    (9, "Yoga Mat", 4, 4, 19.99),
    (10, "Desk Organizer", 5, 2, 14.99),
    (11, "Notebook Set", 5, 3, 9.99),
    (12, "Bluetooth Speaker", 1, 1, 45.00),
]

ORDERS = [
    (1, 1, "2023-01-15", "completed"),
    (2, 1, "2023-04-02", "completed"),
    (3, 2, "2023-06-10", "completed"),
    (4, 3, "2022-12-01", "completed"),
    (5, 3, "2023-02-20", "completed"),
    (6, 3, "2023-07-18", "cancelled"),
    (7, 4, "2023-01-25", "completed"),
    (8, 5, "2022-10-12", "completed"),
    (9, 5, "2023-03-09", "completed"),
    (10, 6, "2024-02-25", "completed"),
    (11, 6, "2024-03-15", "completed"),
    (12, 7, "2021-06-05", "completed"),
    (13, 7, "2023-05-22", "completed"),
    (14, 8, "2023-09-01", "completed"),
    (15, 8, "2023-09-20", "completed"),
    (16, 2, "2023-08-14", "cancelled"),
    (17, 4, "2023-11-30", "completed"),
    (18, 1, "2023-12-05", "completed"),
    (19, 5, "2024-01-10", "completed"),
    (20, 6, "2024-02-28", "completed"),
]

# (order_item_id, order_id, product_id, quantity, unit_price)
ORDER_ITEMS = [
    (1, 1, 1, 2, 39.99),
    (2, 1, 4, 1, 34.50),
    (3, 2, 6, 1, 28.00),
    (4, 2, 11, 3, 9.99),
    (5, 3, 3, 1, 89.99),
    (6, 4, 2, 1, 249.99),
    (7, 4, 12, 1, 45.00),
    (8, 5, 8, 1, 59.99),
    (9, 5, 9, 2, 19.99),
    (10, 6, 1, 1, 39.99),
    (11, 7, 5, 1, 22.00),
    (12, 7, 10, 2, 14.99),
    (13, 8, 7, 1, 32.00),
    (14, 9, 8, 1, 59.99),
    (15, 9, 9, 1, 19.99),
    (16, 10, 1, 1, 39.99),
    (17, 10, 3, 1, 89.99),
    (18, 11, 12, 2, 45.00),
    (19, 12, 6, 2, 28.00),
    (20, 12, 7, 1, 32.00),
    (21, 13, 2, 1, 249.99),
    (22, 14, 4, 2, 34.50),
    (23, 14, 5, 1, 22.00),
    (24, 15, 1, 3, 39.99),
    (25, 16, 9, 1, 19.99),
    (26, 17, 10, 4, 14.99),
    (27, 17, 11, 5, 9.99),
    (28, 18, 3, 1, 89.99),
    (29, 18, 12, 1, 45.00),
    (30, 19, 8, 2, 59.99),
    (31, 20, 2, 1, 249.99),
    (32, 20, 6, 1, 28.00),
]


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(SCHEMA)

    cur.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", CUSTOMERS)
    cur.executemany("INSERT INTO categories VALUES (?,?)", CATEGORIES)
    cur.executemany("INSERT INTO suppliers VALUES (?,?,?)", SUPPLIERS)
    cur.executemany("INSERT INTO products VALUES (?,?,?,?,?)", PRODUCTS)
    cur.executemany("INSERT INTO orders VALUES (?,?,?,?)", ORDERS)
    cur.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", ORDER_ITEMS)

    conn.commit()
    conn.close()
    print(f"Created {DB_PATH} with base tables: "
          "customers, categories, suppliers, products, orders, order_items")


if __name__ == "__main__":
    main()
