# Business Glossary — Olist

Official definitions of the business metrics. All amounts are in Brazilian reais (BRL).

## General rules

- All amounts are in Brazilian reais (BRL).
- The reference date for any time-based analysis is orders.order_purchase_timestamp.
- Never join order_items and payments in the same query without aggregating one of them first: each item would be multiplied by each payment (join fan-out) and sums would be wrong.
- To display a product category, use the English name (category_translation.product_category_name_english) with a LEFT JOIN.

## Revenue

Definition: sum of the prices of items in delivered orders, excluding shipping.
Rules:
- Only orders with order_status = 'delivered'.
- Use order_items.price. Do not include freight_value.
- Do not use payments.payment_value for revenue.
- The reference date is orders.order_purchase_timestamp.

Reference SQL (revenue per month):
```sql
SELECT DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
       SUM(i.price) AS revenue
FROM orders o
JOIN order_items i ON o.order_id = i.order_id
WHERE o.order_status = 'delivered'
GROUP BY month
ORDER BY month
```

## Number of customers

Definition: number of distinct people who placed at least one order.
Rules:
- One customer = one customer_unique_id (customers table).
- NEVER count customer_id: a new customer_id is created for every order, so COUNT(DISTINCT customer_id) gives the number of orders, not customers.

Reference SQL:
```sql
SELECT COUNT(DISTINCT c.customer_unique_id) AS nb_customers
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
```

## Number of orders

Definition: number of orders placed, excluding canceled or unavailable orders.
Rules:
- Exclude order_status IN ('canceled', 'unavailable').
- Orders in progress (shipped, invoiced, processing, created, approved) are counted: they represent real demand.
- Exception: for average order value, use delivered orders only, for consistency with revenue.

Reference SQL:
```sql
SELECT COUNT(DISTINCT order_id) AS nb_orders
FROM orders
WHERE order_status NOT IN ('canceled', 'unavailable')
```

## Average order value (AOV)

Definition: average revenue per delivered order, excluding shipping.
Rules:
- Average order value = revenue / number of delivered orders.
- Compute per order, not per item: divide by COUNT(DISTINCT order_id), not COUNT(*).
- Only orders with order_status = 'delivered'.

Reference SQL:
```sql
SELECT SUM(i.price) / COUNT(DISTINCT o.order_id) AS average_order_value
FROM orders o
JOIN order_items i ON o.order_id = i.order_id
WHERE o.order_status = 'delivered'
```

## Repeat purchase rate (loyal customers)

Definition: share of customers who placed at least two orders.
Rules:
- One customer = one customer_unique_id.
- A loyal customer = a customer with at least 2 non-canceled orders.
- The repeat purchase rate is very low at Olist (about 3%): most customers buy only once.

Reference SQL:
```sql
WITH orders_per_customer AS (
    SELECT c.customer_unique_id,
           COUNT(DISTINCT o.order_id) AS nb_orders
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY c.customer_unique_id
)
SELECT AVG(CASE WHEN nb_orders >= 2 THEN 1.0 ELSE 0.0 END) AS repeat_purchase_rate
FROM orders_per_customer
```

## Late delivery

Definition: an order is late if it was delivered after the date promised to the customer, comparing dates at day level.
Rules:
- Only consider delivered orders: order_status = 'delivered' AND order_delivered_customer_date not empty.
- Late if CAST(order_delivered_customer_date AS DATE) > CAST(order_estimated_delivery_date AS DATE).
- Late delivery rate = late orders / delivered orders.

Reference SQL (late delivery rate):
```sql
SELECT AVG(CASE WHEN CAST(order_delivered_customer_date AS DATE)
                   > CAST(order_estimated_delivery_date AS DATE)
                THEN 1.0 ELSE 0.0 END) AS late_delivery_rate
FROM orders
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NOT NULL
```

## Delivery time

Definition: number of days between purchase and delivery to the customer.
Rules:
- Only consider delivered orders with a delivery date.
- Delivery time = DATE_DIFF('day', order_purchase_timestamp, order_delivered_customer_date).
- For a "typical" delivery time, the median is often more representative than the mean (a few very long deliveries pull the mean up).

Reference SQL:
```sql
SELECT AVG(DATE_DIFF('day', order_purchase_timestamp, order_delivered_customer_date)) AS avg_delivery_days,
       MEDIAN(DATE_DIFF('day', order_purchase_timestamp, order_delivered_customer_date)) AS median_delivery_days
FROM orders
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NOT NULL
```

## Customer satisfaction and negative reviews

Definition: satisfaction is measured with reviews.review_score (from 1 to 5).
Rules:
- Average score = AVG(review_score).
- A negative review = a score of 1 or 2. A positive review = a score of 4 or 5. A score of 3 is neutral.
- Negative review rate = negative reviews / total reviews.
- Scores are very polarized: about 57% are 5/5, but there is a spike at 1/5 (about 11%).

Reference SQL (negative review rate per category):
```sql
SELECT COALESCE(t.product_category_name_english, p.product_category_name) AS category,
       AVG(CASE WHEN r.review_score <= 2 THEN 1.0 ELSE 0.0 END) AS negative_review_rate,
       COUNT(*) AS nb_reviews
FROM reviews r
JOIN order_items i ON r.order_id = i.order_id
JOIN products p ON i.product_id = p.product_id
LEFT JOIN category_translation t ON p.product_category_name = t.product_category_name
GROUP BY category
ORDER BY negative_review_rate DESC
```

## Regions of Brazil

Users talk about regions, but the database only contains state codes (customers.customer_state, sellers.seller_state).
Mapping:
- South: PR, SC, RS
- Southeast: SP, RJ, MG, ES
- Center-West: MT, MS, GO, DF
- Northeast: MA, PI, CE, RN, PB, PE, AL, SE, BA
- North: AM, RR, AP, PA, TO, RO, AC

Reference SQL (filter "in the South"):
```sql
WHERE c.customer_state IN ('PR', 'SC', 'RS')
```

## Data period and time expressions

The data covers orders from 2016 to 2018. The first and last months contain very few orders.
Rules:
- "Recently", "last month", "this month" = the month of the latest available purchase date, computed with MAX(order_purchase_timestamp). Never use today's date (CURRENT_DATE): the data stops in 2018.
- "This year" = the year of the latest available purchase date.
- The latest available month may be incomplete. When an answer is about this month or compares it with previous months, point this out to the user.

Reference SQL (latest available month):
```sql
WITH latest_month AS (
    SELECT DATE_TRUNC('month', MAX(order_purchase_timestamp)) AS month FROM orders
)
SELECT COUNT(DISTINCT o.order_id) AS nb_orders
FROM orders o, latest_month m
WHERE DATE_TRUNC('month', o.order_purchase_timestamp) = m.month
  AND o.order_status NOT IN ('canceled', 'unavailable')
```
