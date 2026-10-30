"""
scripts/create_relationship_test_data.py
========================================
Creates a dedicated synthetic multi-table dataset designed specifically to test
and demonstrate the AI Relationship Explorer:

1. customers.csv     - Customer accounts (PK: customer_id) with duplicate names & PII
2. orders.csv        - Customer orders (PK: order_id, FK: customer_id)
3. payments.csv      - Order payment transactions (PK: payment_id, FK: order_id, customer_id)
4. employees.csv     - Staff records (PK: employee_id, FK: department_id)
5. departments.csv   - Departments (PK: department_id)
6. relational_demo.db - SQLite database mirroring schemas with explicit PK & FK constraints!

Includes:
  - 1:1, 1:N, and N:M patterns
  - Intentional duplicate names to prove people are NOT falsely linked by name
  - Unrelated records (e.g. guest checkouts with null customer_id, orphan IDs)
  - Maskable personal-data fields
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_DIR = PROJECT_ROOT / "data" / "csv"
SQL_DIR = PROJECT_ROOT / "data" / "sql"

CSV_DIR.mkdir(parents=True, exist_ok=True)
SQL_DIR.mkdir(parents=True, exist_ok=True)


# 1. Customers
CUSTOMERS_DATA = [
    {
        "customer_id": "C001",
        "full_name": "Eleanor Vance",
        "email": "eleanor.vance@hillhouse.example",
        "phone": "+1-555-019-2831",
        "city": "Boston",
        "country": "USA",
        "tier": "VIP Platinum",
    },
    {
        "customer_id": "C002",
        "full_name": "Theodora Crain",
        "email": "theo.crain@designstudio.example",
        "phone": "+1-555-014-9923",
        "city": "Chicago",
        "country": "USA",
        "tier": "Gold",
    },
    {
        "customer_id": "C003",
        "full_name": "Luke Sanderson",
        "email": "luke.sanderson@sanderson-holdings.example",
        "phone": "+44-20-7946-0192",
        "city": "London",
        "country": "UK",
        "tier": "Silver",
    },
    {
        "customer_id": "C004",
        "full_name": "Eleanor Vance",  # DUPLICATE NAME with C001, distinct customer!
        "email": "eleanor.vance.arch@citynet.example",
        "phone": "+1-555-018-7711",
        "city": "Seattle",
        "country": "USA",
        "tier": "Bronze",
    },
    {
        "customer_id": "C005",
        "full_name": "Arthur Pendelton",
        "email": "arthur.pendelton@medicare-sample.org",
        "phone": "+1-555-342-1100",
        "city": "Boston",
        "country": "USA",
        "tier": "VIP Platinum",
    },
    {
        "customer_id": "C006",
        "full_name": "Elena Rostova",
        "email": "elena.rostova@globalcorp.example",
        "phone": "+1-555-014-8844",
        "city": "Berlin",
        "country": "Germany",
        "tier": "Gold",
    },
    {
        "customer_id": "C007",
        "full_name": "Klaus Weber",
        "email": "klaus.weber@techfirm.example",
        "phone": "+49-30-1234-5678",
        "city": "Munich",
        "country": "Germany",
        "tier": "Silver",
    },
]

# 2. Orders (FK -> customer_id)
ORDERS_DATA = [
    {"order_id": "ORD-101", "customer_id": "C001", "order_date": "2024-01-15", "amount": 249.99, "status": "COMPLETED", "currency": "USD"},
    {"order_id": "ORD-102", "customer_id": "C001", "order_date": "2024-02-10", "amount": 89.50, "status": "COMPLETED", "currency": "USD"},
    {"order_id": "ORD-103", "customer_id": "C001", "order_date": "2024-03-01", "amount": 410.00, "status": "PROCESSING", "currency": "USD"},
    {"order_id": "ORD-104", "customer_id": "C002", "order_date": "2024-02-18", "amount": 1250.00, "status": "COMPLETED", "currency": "USD"},
    {"order_id": "ORD-105", "customer_id": "C003", "order_date": "2024-02-25", "amount": 75.20, "status": "COMPLETED", "currency": "GBP"},
    {"order_id": "ORD-106", "customer_id": "C004", "order_date": "2024-03-05", "amount": 320.00, "status": "DELIVERED", "currency": "USD"},
    {"order_id": "ORD-107", "customer_id": "C005", "order_date": "2024-03-12", "amount": 890.00, "status": "SHIPPED", "currency": "USD"},
    {"order_id": "ORD-108", "customer_id": "C006", "order_date": "2024-03-14", "amount": 150.00, "status": "COMPLETED", "currency": "EUR"},
    {"order_id": "ORD-109", "customer_id": "C999", "order_date": "2024-03-15", "amount": 99.00, "status": "FAILED", "currency": "USD"},  # Orphan FK
    {"order_id": "ORD-110", "customer_id": "", "order_date": "2024-03-16", "amount": 45.00, "status": "DRAFT", "currency": "USD"},        # Null FK guest
]

# 3. Payments (FK -> order_id, customer_id)
PAYMENTS_DATA = [
    {"payment_id": "PAY-501", "order_id": "ORD-101", "customer_id": "C001", "method": "CREDIT_CARD", "amount": 249.99, "status": "SETTLED", "card_last_four": "4242"},
    {"payment_id": "PAY-502", "order_id": "ORD-102", "customer_id": "C001", "method": "PAYPAL", "amount": 89.50, "status": "SETTLED", "card_last_four": ""},
    {"payment_id": "PAY-503", "order_id": "ORD-103", "customer_id": "C001", "method": "CREDIT_CARD", "amount": 410.00, "status": "AUTHORIZED", "card_last_four": "1111"},
    {"payment_id": "PAY-504", "order_id": "ORD-104", "customer_id": "C002", "method": "WIRE_TRANSFER", "amount": 1250.00, "status": "SETTLED", "card_last_four": ""},
    {"payment_id": "PAY-505", "order_id": "ORD-105", "customer_id": "C003", "method": "DEBIT_CARD", "amount": 75.20, "status": "SETTLED", "card_last_four": "8821"},
    {"payment_id": "PAY-506", "order_id": "ORD-106", "customer_id": "C004", "method": "CREDIT_CARD", "amount": 320.00, "status": "SETTLED", "card_last_four": "5544"},
    {"payment_id": "PAY-507", "order_id": "ORD-107", "customer_id": "C005", "method": "CREDIT_CARD", "amount": 890.00, "status": "SETTLED", "card_last_four": "9900"},
    {"payment_id": "PAY-508", "order_id": "ORD-108", "customer_id": "C006", "method": "CREDIT_CARD", "amount": 150.00, "status": "SETTLED", "card_last_four": "3131"},
    {"payment_id": "PAY-509", "order_id": "ORD-109", "customer_id": "C999", "method": "CREDIT_CARD", "amount": 99.00, "status": "DECLINED", "card_last_four": "0000"},
    {"payment_id": "PAY-510", "order_id": "ORD-101", "customer_id": "C001", "method": "GIFT_CARD", "amount": 25.00, "status": "REFUNDED", "card_last_four": ""}, # Multiple payments per order
]

# 4. Departments
DEPARTMENTS_DATA = [
    {"department_id": "D01", "department_name": "Engineering & Technology", "location_code": "Bldg-A-Fl3", "budget": 1200000.00, "head_of_department": "Alex Mercer"},
    {"department_id": "D02", "department_name": "Human Resources & People", "location_code": "Bldg-A-Fl1", "budget": 450000.00, "head_of_department": "Sarah Connor"},
    {"department_id": "D03", "department_name": "Finance & Accounting", "location_code": "Bldg-B-Fl2", "budget": 850000.00, "head_of_department": "Marcus Wright"},
    {"department_id": "D04", "department_name": "Advanced Research", "location_code": "Lab-C", "budget": 950000.00, "head_of_department": "Dr. Emmett Brown"},
]

# 5. Employees (FK -> department_id)
EMPLOYEES_DATA = [
    {"employee_id": "E101", "employee_name": "Alex Mercer", "email": "alex.mercer@enterprise.example", "phone": "+1-555-011-2233", "department_id": "D01", "job_title": "VP of Engineering", "salary": 185000.00},
    {"employee_id": "E102", "employee_name": "Sarah Connor", "email": "sarah.connor@enterprise.example", "phone": "+1-555-012-4455", "department_id": "D02", "job_title": "HR Director", "salary": 140000.00},
    {"employee_id": "E103", "employee_name": "Marcus Wright", "email": "marcus.wright@enterprise.example", "phone": "+1-555-013-6677", "department_id": "D03", "job_title": "Chief Financial Officer", "salary": 195000.00},
    {"employee_id": "E104", "employee_name": "Elena Fisher", "email": "elena.fisher@enterprise.example", "phone": "+1-555-014-8899", "department_id": "D01", "job_title": "Staff Security Engineer", "salary": 160000.00},
    {"employee_id": "E105", "employee_name": "Nathan Drake", "email": "nathan.drake@enterprise.example", "phone": "+1-555-015-1122", "department_id": "D01", "job_title": "DevOps Architect", "salary": 155000.00},
    {"employee_id": "E106", "employee_name": "Victor Sullivan", "email": "victor.sullivan@enterprise.example", "phone": "+1-555-016-3344", "department_id": "D03", "job_title": "Internal Auditor", "salary": 125000.00},
    {"employee_id": "E107", "employee_name": "Dr. Emmett Brown", "email": "emmett.brown@enterprise.example", "phone": "+1-555-017-5566", "department_id": "D04", "job_title": "Lead Scientist", "salary": 175000.00},
    {"employee_id": "E108", "employee_name": "Marty McFly", "email": "marty.mcfly@enterprise.example", "phone": "+1-555-018-7788", "department_id": "D04", "job_title": "Research Assistant", "salary": 65000.00},
    {"employee_id": "E109", "employee_name": "Unassigned Contractor", "email": "contractor.unassigned@enterprise.example", "phone": "+1-555-019-0011", "department_id": "", "job_title": "Independent Specialist", "salary": 80000.00},
]


def write_csv(filename: str, fieldnames: list[str], rows: list[dict]) -> None:
    path = CSV_DIR / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated CSV: {path} ({len(rows)} records)")


def build_sqlite_database() -> None:
    db_path = SQL_DIR / "relational_demo.db"
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Create tables with explicit FOREIGN KEY definitions in DDL for schema reflection,
    # but do not enforce abort on invalid test data inserts so we can test orphaned references.
    cur.execute("PRAGMA foreign_keys = OFF;")

    # Customers table
    cur.execute("""
    CREATE TABLE customers (
        customer_id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        city TEXT,
        country TEXT,
        tier TEXT
    );
    """)

    # Orders table
    cur.execute("""
    CREATE TABLE orders (
        order_id TEXT PRIMARY KEY,
        customer_id TEXT,
        order_date TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT NOT NULL,
        currency TEXT DEFAULT 'USD',
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE SET NULL
    );
    """)

    # Payments table
    cur.execute("""
    CREATE TABLE payments (
        payment_id TEXT PRIMARY KEY,
        order_id TEXT,
        customer_id TEXT,
        method TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT NOT NULL,
        card_last_four TEXT,
        FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE SET NULL
    );
    """)

    # Departments table
    cur.execute("""
    CREATE TABLE departments (
        department_id TEXT PRIMARY KEY,
        department_name TEXT NOT NULL,
        location_code TEXT,
        budget REAL,
        head_of_department TEXT
    );
    """)

    # Employees table
    cur.execute("""
    CREATE TABLE employees (
        employee_id TEXT PRIMARY KEY,
        employee_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        department_id TEXT,
        job_title TEXT NOT NULL,
        salary REAL,
        FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE SET NULL
    );
    """)

    # Populate SQLite tables
    for c in CUSTOMERS_DATA:
        cur.execute("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (c["customer_id"], c["full_name"], c["email"], c["phone"], c["city"], c["country"], c["tier"]))

    for o in ORDERS_DATA:
        cur.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)",
                    (o["order_id"], o["customer_id"] or None, o["order_date"], o["amount"], o["status"], o["currency"]))

    for p in PAYMENTS_DATA:
        cur.execute("INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (p["payment_id"], p["order_id"] or None, p["customer_id"] or None, p["method"], p["amount"], p["status"], p["card_last_four"] or None))

    for d in DEPARTMENTS_DATA:
        cur.execute("INSERT INTO departments VALUES (?, ?, ?, ?, ?)",
                    (d["department_id"], d["department_name"], d["location_code"], d["budget"], d["head_of_department"]))

    for e in EMPLOYEES_DATA:
        cur.execute("INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (e["employee_id"], e["employee_name"], e["email"], e["phone"], e["department_id"] or None, e["job_title"], e["salary"]))

    conn.commit()
    conn.close()
    print(f"Generated SQLite Database: {db_path}")


def main() -> None:
    print("Generating AI Relationship Explorer synthetic test datasets...")
    write_csv("customers.csv", list(CUSTOMERS_DATA[0].keys()), CUSTOMERS_DATA)
    write_csv("orders.csv", list(ORDERS_DATA[0].keys()), ORDERS_DATA)
    write_csv("payments.csv", list(PAYMENTS_DATA[0].keys()), PAYMENTS_DATA)
    write_csv("departments.csv", list(DEPARTMENTS_DATA[0].keys()), DEPARTMENTS_DATA)
    write_csv("employees.csv", list(EMPLOYEES_DATA[0].keys()), EMPLOYEES_DATA)
    build_sqlite_database()
    print("AI Relationship Explorer synthetic datasets generated successfully!")


if __name__ == "__main__":
    main()
