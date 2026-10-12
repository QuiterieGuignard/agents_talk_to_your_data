# Data Dictionary — Olist

E-commerce database of the Brazilian marketplace Olist (orders from 2016 to 2018).
All amounts are in Brazilian reais (BRL).

## Table orders

Central table: one row = one order. Primary key: order_id.

Columns:
- order_id: unique identifier of the order.
- customer_id: customer identifier specific to THIS order (a new customer_id is created for every order). Only used to join the customers table. Never use it to count customers.
- order_status: status of the order. Values: delivered, shipped, canceled, unavailable, invoiced, processing, created, approved.
- order_purchase_timestamp: date and time of purchase. This is THE reference date for any time-based analysis.
- order_approved_at: date the payment was approved.
- order_delivered_carrier_date: date the order was handed to the carrier.
- order_delivered_customer_date: actual delivery date to the customer. Empty if the order was not delivered.
- order_estimated_delivery_date: delivery date promised to the customer at the time of purchase.

Joins:
- orders.order_id = order_items.order_id (an order has one or more items)
- orders.order_id = payments.order_id
- orders.order_id = reviews.order_id
- orders.customer_id = customers.customer_id

## Table order_items

One row = one item in an order. An order with 3 items has 3 rows.

Columns:
- order_id: order the item belongs to.
- order_item_id: sequence number of the item within the order (1, 2, 3...). This is NOT a quantity.
- product_id: product sold.
- seller_id: seller of this item. A single order can contain items from different sellers.
- shipping_limit_date: deadline for the seller to ship the item.
- price: price of the item in BRL, excluding shipping.
- freight_value: shipping cost of the item in BRL.

Pitfalls:
- There is no quantity column. A product bought twice appears on two rows. Number of items sold = COUNT(*) on order_items.

Joins:
- order_items.order_id = orders.order_id
- order_items.product_id = products.product_id
- order_items.seller_id = sellers.seller_id

## Table customers

One row = one customer FOR A GIVEN ORDER (not a person). Key: customer_id.

Columns:
- customer_id: customer identifier specific to one order. There is exactly one customer_id per order. Only used to join the orders table.
- customer_unique_id: identifier of the real person. The same person keeps the same customer_unique_id across all their orders. This is THE column to use to count customers or study repeat purchases.
- customer_zip_code_prefix: first 5 digits of the customer's zip code, stored as text (e.g. '01151').
- customer_city: customer's city, lowercase and without accents (e.g. sao paulo, rio de janeiro).
- customer_state: customer's state, two-letter code (e.g. SP = São Paulo, RJ = Rio de Janeiro, MG = Minas Gerais).

Pitfalls:
- Number of customers = COUNT(DISTINCT customer_unique_id), never COUNT(DISTINCT customer_id).
- For a geographic analysis of sales, use customer_state (where the customer is delivered), not seller_state.

Joins:
- customers.customer_id = orders.customer_id

## Table products

One row = one product in the catalog. Key: product_id.

Columns:
- product_id: unique identifier of the product.
- product_category_name: product category IN PORTUGUESE (e.g. beleza_saude, cama_mesa_banho). Can be empty.
- product_name_lenght: number of characters in the product name. Warning: the column name contains a typo ("lenght") and must be written exactly like this.
- product_description_lenght: number of characters in the product description. Same typo ("lenght").
- product_photos_qty: number of photos on the product page.
- product_weight_g: product weight in grams.
- product_length_cm, product_height_cm, product_width_cm: product dimensions in centimeters (here "length" is spelled correctly).

Pitfalls:
- The actual product names are not in the database: only their category is known.
- Categories are in Portuguese. To display a readable name, join category_translation to get the English name.
- 610 products have no category (empty product_category_name). A JOIN on category_translation excludes them: use LEFT JOIN for totals.

Joins:
- products.product_id = order_items.product_id
- products.product_category_name = category_translation.product_category_name

## Table sellers

One row = one seller on the marketplace. Key: seller_id.

Columns:
- seller_id: unique identifier of the seller.
- seller_zip_code_prefix: first 5 digits of the seller's zip code, stored as text.
- seller_city: seller's city, lowercase and without accents.
- seller_state: seller's state, two-letter code (e.g. SP, RJ).

Pitfalls:
- A seller is not linked to an order but to an item: go through order_items to link sellers and orders.
- A single order can contain items from several sellers.

Joins:
- sellers.seller_id = order_items.seller_id

## Table payments

One row = one payment method used for an order. An order can have several rows (e.g. credit card + voucher).

Columns:
- order_id: order being paid.
- payment_sequential: sequence number of the payment within the order (1, 2, 3...), when several payment methods are combined.
- payment_type: payment method. Values: credit_card, boleto (Brazilian bank slip, paid in cash or by bank transfer), voucher, debit_card, not_defined.
- payment_installments: number of monthly installments chosen (paying in installments is very common in Brazil). 1 = paid in full.
- payment_value: amount of this payment in BRL. It includes shipping costs.

Pitfalls:
- Total amount paid for an order = SUM(payment_value) grouped by order_id.
- 2,961 orders have several payment rows. Credit card largely dominates (about 74% of payments), followed by boleto (about 19%).
- Never join payments and order_items in the same query without aggregating one of them first: each item would be multiplied by each payment, and sums would be inflated.
- Do not use payment_value to compute revenue (see business glossary).

Joins:
- payments.order_id = orders.order_id

## Table reviews

One row = one customer review left after an order (satisfaction survey sent by email).

Columns:
- review_id: identifier of the review.
- order_id: order being reviewed.
- review_score: score from 1 (very dissatisfied) to 5 (very satisfied).
- review_comment_title: title of the comment, in Portuguese. Often empty.
- review_comment_message: text of the comment, in Portuguese. Often empty. Company names were replaced with names of Game of Thrones houses (anonymization).
- review_creation_date: date the survey was sent to the customer.
- review_answer_timestamp: date the customer answered.

Pitfalls:
- Not every order has a review, and 547 orders have several reviews. For one score per order, average by order_id.
- Scores are very polarized: about 57% are 5/5, but about 11% are 1/5.
- Review text is in Portuguese.

Joins:
- reviews.order_id = orders.order_id

## Table category_translation

Translation table for product categories, from Portuguese to English. One row = one category.

Columns:
- product_category_name: category name in Portuguese (e.g. beleza_saude).
- product_category_name_english: category name in English (e.g. health_beauty).

Pitfalls:
- Two categories in products have no translation: pc_gamer and portateis_cozinha_e_preparadores_de_alimentos. A JOIN excludes them: use LEFT JOIN and COALESCE(product_category_name_english, product_category_name) to always keep a name.

Joins:
- category_translation.product_category_name = products.product_category_name
