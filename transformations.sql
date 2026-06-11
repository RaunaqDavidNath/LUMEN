-- transformations.sql
-- ----------------------------------------------------------------------
-- These are "transformation models" — the kind of layered SQL views you'd
-- find in a real warehouse (think dbt staging -> intermediate -> mart
-- layers). Each one builds on base tables and/or earlier views, which is
-- exactly what creates the multi-hop "lineage graph" we want to extract.
--
-- Layers:
--   staging     : stg_*           -> light cleanup of raw tables
--   facts/dims  : fct_*, dim_*     -> joined, business-friendly tables
--   marts       : everything else  -> aggregated, analysis-ready tables
-- ----------------------------------------------------------------------

-- ===================== STAGING LAYER =====================

-- 1. Clean orders: drop cancelled orders, normalize date
CREATE VIEW stg_orders AS
SELECT order_id, customer_id, order_date, status
FROM orders
WHERE status != 'cancelled';

-- 2. Clean order items: precompute line-level revenue
CREATE VIEW stg_order_items AS
SELECT order_item_id, order_id, product_id, quantity, unit_price,
       quantity * unit_price AS line_total
FROM order_items;

-- 3. Customer dimension: add a derived "segment" based on signup date
CREATE VIEW dim_customers AS
SELECT customer_id, name, email, country, signup_date,
       CASE WHEN signup_date < '2023-01-01' THEN 'legacy' ELSE 'new' END AS customer_segment
FROM customers;

-- 4. Product dimension: denormalize category + supplier info
CREATE VIEW dim_products AS
SELECT p.product_id, p.name AS product_name, p.price,
       c.name AS category_name,
       s.name AS supplier_name, s.country AS supplier_country
FROM products p
JOIN categories c ON p.category_id = c.category_id
JOIN suppliers s ON p.supplier_id = s.supplier_id;

-- ===================== FACT LAYER =====================

-- 5. Order-level revenue: join cleaned orders with cleaned line items
CREATE VIEW fct_order_revenue AS
SELECT o.order_id, o.customer_id, o.order_date,
       SUM(oi.line_total) AS order_revenue
FROM stg_orders o
JOIN stg_order_items oi ON o.order_id = oi.order_id
GROUP BY o.order_id, o.customer_id, o.order_date;

-- 6. Product sales summary: combine cleaned line items with product dimension
CREATE VIEW product_sales_summary AS
SELECT oi.product_id, dp.product_name, dp.category_name, dp.supplier_name,
       SUM(oi.quantity) AS units_sold,
       SUM(oi.line_total) AS total_revenue
FROM stg_order_items oi
JOIN dim_products dp ON oi.product_id = dp.product_id
GROUP BY oi.product_id, dp.product_name, dp.category_name, dp.supplier_name;

-- ===================== MART LAYER =====================

-- 7. Customer lifetime value: combine order revenue with customer dimension
CREATE VIEW customer_lifetime_value AS
SELECT f.customer_id, d.name, d.country, d.customer_segment,
       SUM(f.order_revenue) AS lifetime_value,
       COUNT(f.order_id) AS total_orders
FROM fct_order_revenue f
JOIN dim_customers d ON f.customer_id = d.customer_id
GROUP BY f.customer_id, d.name, d.country, d.customer_segment;

-- 8. Revenue by category
CREATE VIEW category_revenue AS
SELECT category_name,
       SUM(total_revenue) AS category_revenue,
       SUM(units_sold) AS category_units
FROM product_sales_summary
GROUP BY category_name;

-- 9. Supplier performance
CREATE VIEW supplier_performance AS
SELECT supplier_name,
       COUNT(DISTINCT product_id) AS product_count,
       SUM(total_revenue) AS supplier_revenue
FROM product_sales_summary
GROUP BY supplier_name;

-- 10. Monthly revenue trend
CREATE VIEW monthly_revenue AS
SELECT strftime('%Y-%m', order_date) AS month,
       SUM(order_revenue) AS monthly_revenue,
       COUNT(order_id) AS order_count
FROM fct_order_revenue
GROUP BY month;

-- 11. Revenue by customer country
CREATE VIEW customer_country_revenue AS
SELECT country,
       SUM(lifetime_value) AS country_revenue,
       COUNT(customer_id) AS customer_count
FROM customer_lifetime_value
GROUP BY country;

-- 12. Top customers by lifetime value
CREATE VIEW top_customers AS
SELECT customer_id, name, country, lifetime_value, total_orders
FROM customer_lifetime_value
WHERE lifetime_value > 100
ORDER BY lifetime_value DESC;

-- 13. Repeat customers (more than one order)
CREATE VIEW repeat_customers AS
SELECT customer_id, name, total_orders
FROM customer_lifetime_value
WHERE total_orders > 1;

-- 14. Average order value by customer segment
CREATE VIEW avg_order_value_by_segment AS
SELECT customer_segment,
       AVG(lifetime_value * 1.0 / total_orders) AS avg_order_value
FROM customer_lifetime_value
GROUP BY customer_segment;

-- 15. Category x supplier matrix
CREATE VIEW category_supplier_matrix AS
SELECT category_name, supplier_name,
       COUNT(*) AS product_count
FROM dim_products
GROUP BY category_name, supplier_name;
