"""Export clean tables for the Power BI dashboard, applying the business glossary rules."""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "olist.duckdb"
BI_DIR = ROOT / "data" / "bi"
BI_DIR.mkdir(parents=True, exist_ok=True)

ORDERS_SQL = """
WITH order_reviews AS (
    SELECT order_id, AVG(review_score) AS review_score
    FROM reviews
    GROUP BY order_id
)
SELECT
    o.order_id,
    c.customer_unique_id,
    c.customer_state,
    CASE
        WHEN c.customer_state IN ('PR', 'SC', 'RS') THEN 'South'
        WHEN c.customer_state IN ('SP', 'RJ', 'MG', 'ES') THEN 'Southeast'
        WHEN c.customer_state IN ('MT', 'MS', 'GO', 'DF') THEN 'Center-West'
        WHEN c.customer_state IN ('MA', 'PI', 'CE', 'RN', 'PB', 'PE', 'AL', 'SE', 'BA') THEN 'Northeast'
        ELSE 'North'
    END AS customer_region,
    o.order_status,
    CAST(o.order_purchase_timestamp AS DATE) AS purchase_date,
    CAST(o.order_status = 'delivered' AS INTEGER) AS is_delivered,
    CAST(o.order_status NOT IN ('canceled', 'unavailable') AS INTEGER) AS is_valid_order,
    CASE WHEN o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
         THEN CAST(CAST(o.order_delivered_customer_date AS DATE) > CAST(o.order_estimated_delivery_date AS DATE) AS INTEGER)
    END AS is_late,
    CASE WHEN o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
         THEN DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_customer_date)
    END AS delivery_days,
    r.review_score
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
LEFT JOIN order_reviews r ON o.order_id = r.order_id
"""

ITEMS_SQL = """
SELECT
    i.order_id,
    i.order_item_id,
    i.product_id,
    COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
    i.seller_id,
    s.seller_state,
    i.price,
    i.freight_value
FROM order_items i
LEFT JOIN products p ON i.product_id = p.product_id
LEFT JOIN category_translation t ON p.product_category_name = t.product_category_name
LEFT JOIN sellers s ON i.seller_id = s.seller_id
"""

con = duckdb.connect(str(DB_PATH), read_only=True)
for name, sql in [("orders", ORDERS_SQL), ("items", ITEMS_SQL)]:
    path = (BI_DIR / f"{name}.csv").as_posix()
    con.execute(f"COPY ({sql}) TO '{path}' (HEADER, DELIMITER ',')")
    nb_rows = con.execute(f"SELECT COUNT(*) FROM ({sql})").fetchone()[0]
    print(f"{name:7} {nb_rows:>8,} rows -> {path}")
con.close()