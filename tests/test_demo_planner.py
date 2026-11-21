from app.demo_planner import demo_sql


def test_demo_planner_categories():
    query = demo_sql("Which product categories generated the most revenue?")
    assert "GROUP BY p.category" in query
    assert "FROM products" in query


def test_demo_planner_monthly_sales():
    query = demo_sql("Show monthly sales revenue")
    assert "strftime('%Y-%m'" in query
    assert "GROUP BY month" in query


def test_demo_planner_top_customers():
    query = demo_sql("Who are the top five customers by order value?")
    assert "customer_name" in query
    assert "ORDER BY revenue DESC" in query


def test_demo_planner_order_count():
    query = demo_sql("How many orders were placed?")
    assert "COUNT(*) AS order_count" in query
