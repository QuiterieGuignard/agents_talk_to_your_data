"""Load the Olist CSV files into a DuckDB database."""
from pathlib import Path
 
import duckdb
 
ROOT = Path(__file__).resolve().parent.parent  # project root
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "olist.duckdb"
 
# table name in the database -> original CSV file
TABLES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}
 
con = duckdb.connect(str(DB_PATH))
 
for table, filename in TABLES.items():
    path = (RAW_DIR / filename).as_posix()
    con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv_auto('{path}')")
    nb_rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table:22} {nb_rows:>9,} rows")
 
con.close()
print(f"\nDatabase created: {DB_PATH}")