"""Load the FreshCart warehouse (the SQLite file the Databricks labs used) into the Azure SQL database freshcart_lab7.

Run once, as the trainer, signed in with az login:
  DYLD_LIBRARY_PATH=/opt/homebrew/opt/openssl@3/lib python load_warehouse.py ../../ai-engineer-data-labs/data/freshcart.db
It drops and re-creates the 8 tables, so running it again gives the same database.
"""
import sqlite3, sys, mssql_python

SERVER = "freshcart-mini-sql.database.windows.net"
DATABASE = "freshcart_lab7"

# SQLite keeps dates as text and money as floats; Azure SQL gets proper dates and two-decimal money.
TABLES = {
    "dim_customer": ("customer_id INT PRIMARY KEY, name VARCHAR(60), city VARCHAR(30), region VARCHAR(10), "
                     "signup_date DATE, status VARCHAR(10), is_internal BIT NOT NULL"),
    "dim_restaurant": ("restaurant_id INT PRIMARY KEY, name VARCHAR(60), city VARCHAR(30), cuisine VARCHAR(30), "
                       "partner_since DATE"),
    "dim_date": "date_key DATE PRIMARY KEY, year INT, month INT, day INT, is_weekend BIT",
    "orders": "order_id INT PRIMARY KEY, customer_id INT, restaurant_id INT, order_date DATE, amount DECIMAL(10,2)",
    "orders_v2": ("order_id INT PRIMARY KEY, customer_id INT, restaurant_id INT, order_date DATE, "
                  "order_value DECIMAL(10,2), delivery_minutes INT, status VARCHAR(12)"),
    "order_items": "item_id INT PRIMARY KEY, order_id INT, item_name VARCHAR(60), quantity INT, item_price DECIMAL(10,2)",
    "fact_refund_claim": ("claim_id INT PRIMARY KEY, order_id INT, customer_id INT, claim_date DATE, "
                          "reason VARCHAR(30), amount DECIMAL(10,2), status VARCHAR(14)"),
    "daily_customer_snapshot": ("snapshot_date DATE, customer_id INT, lifetime_orders INT, "
                                "lifetime_value DECIMAL(12,2), PRIMARY KEY (snapshot_date, customer_id)"),
}


def main(path):
    src = sqlite3.connect(path)
    con = mssql_python.connect(f"Server=tcp:{SERVER},1433;Database={DATABASE};"
                               "Authentication=ActiveDirectoryDefault;Encrypt=yes;TrustServerCertificate=no")
    cur = con.cursor()
    for table, columns in TABLES.items():
        cur.execute(f"DROP TABLE IF EXISTS {table}")
        cur.execute(f"CREATE TABLE {table} ({columns})")
        names = [r[1] for r in src.execute(f'PRAGMA table_info("{table}")')]
        rows = src.execute(f'SELECT {", ".join(names)} FROM "{table}"').fetchall()
        marks = ", ".join("?" for _ in names)
        for start in range(0, len(rows), 500):
            cur.executemany(f"INSERT INTO {table} ({', '.join(names)}) VALUES ({marks})", rows[start:start + 500])
        con.commit()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"{table}: {len(rows)} in the file, {cur.fetchone()[0]} in Azure SQL")
    con.close()


if __name__ == "__main__":
    main(sys.argv[1])
