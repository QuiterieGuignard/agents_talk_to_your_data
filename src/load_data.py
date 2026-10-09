"""Charge les CSV Olist dans une base DuckDB."""
from pathlib import Path
import duckdb

RAW_DIR = Path("data/raw")
DB_PATH = Path("data/olist.duckdb")

# nom de la table dans la base  →  fichier CSV d'origine
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

for table, fichier in TABLES.items():
    chemin = (RAW_DIR / fichier).as_posix()
    con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv_auto('{chemin}')")
    nb_lignes = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table:22} {nb_lignes:>9,} lignes")

con.close()
print(f"\nBase créée : {DB_PATH}")