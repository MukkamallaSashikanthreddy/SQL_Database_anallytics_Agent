"""Deterministic example-question planner for no-API demonstrations."""

from __future__ import annotations


def demo_sql(question: str) -> str:
    """Map common demonstration prompts to safe, prewritten analytics SQL.

    This is intentionally a limited fallback. Use Gemini mode for open-ended
    natural-language questions.
    """
    q = question.lower()
    if any(word in q for word in ("top customer", "top customers", "top five customers", "best customers", "highest spending customer")):
        return """SELECT c.customer_name, c.region,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct)), 2) AS revenue
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status != 'Cancelled'
GROUP BY c.customer_id, c.customer_name, c.region
ORDER BY revenue DESC
LIMIT 10"""
    if any(word in q for word in ("category", "categories")) and any(word in q for word in ("revenue", "sales", "generate", "generated")):
        return """SELECT p.category,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct)), 2) AS revenue
FROM products p
JOIN order_items oi ON oi.product_id = p.product_id
JOIN orders o ON o.order_id = oi.order_id
WHERE o.status != 'Cancelled'
GROUP BY p.category
ORDER BY revenue DESC
LIMIT 100"""
    if any(word in q for word in ("monthly", "month by month", "by month")) and any(word in q for word in ("revenue", "sales", "order")):
        return """SELECT strftime('%Y-%m', o.order_date) AS month,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct)), 2) AS revenue,
       COUNT(DISTINCT o.order_id) AS order_count
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status != 'Cancelled'
GROUP BY month
ORDER BY month
LIMIT 100"""
    if "how many orders" in q or "number of orders" in q or "order count" in q:
        return """SELECT COUNT(*) AS order_count
FROM orders
WHERE status != 'Cancelled'
LIMIT 1"""
    if "region" in q and any(word in q for word in ("revenue", "sales", "performance")):
        return """SELECT c.region,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct)), 2) AS revenue,
       COUNT(DISTINCT o.order_id) AS order_count
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status != 'Cancelled'
GROUP BY c.region
ORDER BY revenue DESC
LIMIT 100"""
    if any(word in q for word in ("product", "products")) and any(word in q for word in ("revenue", "sales", "popular", "top")):
        return """SELECT p.product_name, p.category,
       SUM(oi.quantity) AS units_sold,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct)), 2) AS revenue
FROM products p
JOIN order_items oi ON oi.product_id = p.product_id
JOIN orders o ON o.order_id = oi.order_id
WHERE o.status != 'Cancelled'
GROUP BY p.product_id, p.product_name, p.category
ORDER BY revenue DESC
LIMIT 10"""
    if "status" in q or "payment" in q:
        group_column = "payment_method" if "payment" in q else "status"
        return f"""SELECT {group_column}, COUNT(*) AS order_count
FROM orders
GROUP BY {group_column}
ORDER BY order_count DESC
LIMIT 100"""
    return """SELECT c.region,
       COUNT(DISTINCT o.order_id) AS order_count,
       ROUND(SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct)), 2) AS revenue
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status != 'Cancelled'
GROUP BY c.region
ORDER BY revenue DESC
LIMIT 100"""
