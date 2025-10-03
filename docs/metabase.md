# Metabase Guide

## Table of Contents
- [Initial Setup](#initial-setup)
- [Database Connection](#database-connection)
- [Dashboard Creation](#dashboard-creation)
- [Common Queries](#common-queries)
- [Best Practices](#best-practices)

## Initial Setup

### Access Metabase

1. Open browser: `http://localhost:3000`
2. Complete initial setup wizard:
   - Language: English
   - Account: Create admin account
   - Database: Add PostgreSQL connection (see below)

### Create Admin Account

**Required fields:**
- Email: `admin@example.com`
- Password: Strong password (min 8 characters)
- Company name: Your organization
- Analytics usage: Optional

## Database Connection

### Connect to PostgreSQL Analytics Database

**Connection details:**

| Field | Value |
|-------|-------|
| **Database type** | PostgreSQL |
| **Name** | Sales Analytics |
| **Host** | `postgres-analytics` |
| **Port** | `5432` |
| **Database name** | `shadowpostgresdb` |
| **Username** | `metabase_reader` |
| **Password** | `metabase_read_secret` |
| **SSL Mode** | Required |

**Read-Only User Creation:**

```sql
-- Create read-only role
CREATE ROLE metabase_reader WITH LOGIN PASSWORD 'metabase_read_secret';

-- Grant connection
GRANT CONNECT ON DATABASE shadowpostgresdb TO metabase_reader;

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO metabase_reader;

-- Grant SELECT on all tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO metabase_reader;

-- Grant SELECT on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO metabase_reader;

-- Revoke write permissions (security)
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM metabase_reader;
```

### Test Connection

Click **Test Connection** button in Metabase.

**Expected:** "Successfully connected to Sales Analytics"

## Dashboard Creation

### Dashboard 1: Sales Overview

**Purpose:** High-level sales metrics

**Metrics:**
1. **Total Revenue** (Number)
   ```sql
   SELECT SUM(discounted_price * quantity) AS total_revenue
   FROM fact_sales;
   ```

2. **Total Orders** (Number)
   ```sql
   SELECT COUNT(DISTINCT order_id) AS total_orders
   FROM fact_sales;
   ```

3. **Average Order Value** (Number)
   ```sql
   SELECT AVG(discounted_price * quantity) AS avg_order_value
   FROM fact_sales;
   ```

4. **Revenue Trend** (Line Chart)
   ```sql
   SELECT
       d.date,
       SUM(f.discounted_price * f.quantity) AS revenue
   FROM fact_sales f
   JOIN dim_date d ON f.order_date_id = d.date_id
   GROUP BY d.date
   ORDER BY d.date;
   ```

### Dashboard 2: Product Performance

**Charts:**

1. **Top 10 Products by Revenue** (Bar Chart)
   ```sql
   SELECT
       p.product_title,
       SUM(f.discounted_price * f.quantity) AS revenue
   FROM fact_sales f
   JOIN dim_product p ON f.product_id = p.product_id
   GROUP BY p.product_title
   ORDER BY revenue DESC
   LIMIT 10;
   ```

2. **Revenue by Category** (Pie Chart)
   ```sql
   SELECT
       p.product_category,
       SUM(f.discounted_price * f.quantity) AS revenue
   FROM fact_sales f
   JOIN dim_product p ON f.product_id = p.product_id
   GROUP BY p.product_category
   ORDER BY revenue DESC;
   ```

3. **Best Seller Performance** (Comparison)
   ```sql
   SELECT
       p.is_best_seller,
       COUNT(*) AS sales_count,
       SUM(f.discounted_price * f.quantity) AS revenue
   FROM fact_sales f
   JOIN dim_product p ON f.product_id = p.product_id
   GROUP BY p.is_best_seller;
   ```

### Dashboard 3: Customer Insights

**Charts:**

1. **Top 10 Customers by Total Spend** (Bar Chart)
   ```sql
   SELECT
       c.customer_id,
       c.name,
       COUNT(DISTINCT f.order_id) AS total_orders,
       SUM(f.discounted_price * f.quantity) AS total_spent
   FROM fact_sales f
   JOIN dim_customer c ON f.customer_id = c.customer_id
   GROUP BY c.customer_id, c.name
   ORDER BY total_spent DESC
   LIMIT 10;
   ```

2. **Customer Purchase Frequency** (Histogram)
   ```sql
   SELECT
       customer_id,
       COUNT(DISTINCT order_id) AS purchase_count
   FROM fact_sales
   GROUP BY customer_id;
   ```

### Dashboard 4: Time-Based Analysis

**Charts:**

1. **Monthly Revenue** (Bar Chart)
   ```sql
   SELECT
       d.year,
       d.month,
       SUM(f.discounted_price * f.quantity) AS revenue
   FROM fact_sales f
   JOIN dim_date d ON f.order_date_id = d.date_id
   GROUP BY d.year, d.month
   ORDER BY d.year, d.month;
   ```

2. **Day of Week Analysis** (Bar Chart)
   ```sql
   SELECT
       d.day_of_week,
       COUNT(DISTINCT f.order_id) AS order_count,
       SUM(f.discounted_price * f.quantity) AS revenue
   FROM fact_sales f
   JOIN dim_date d ON f.order_date_id = d.date_id
   GROUP BY d.day_of_week
   ORDER BY d.day_of_week;
   ```

3. **Quarterly Performance** (Line Chart)
   ```sql
   SELECT
       d.year,
       d.quarter,
       SUM(f.profit) AS total_profit
   FROM fact_sales f
   JOIN dim_date d ON f.order_date_id = d.date_id
   GROUP BY d.year, d.quarter
   ORDER BY d.year, d.quarter;
   ```

## Common Queries

### Profit Analysis

```sql
SELECT
    SUM(f.profit) AS total_profit,
    AVG(f.profit) AS avg_profit_per_sale,
    SUM(f.profit) / SUM(f.discounted_price * f.quantity) * 100 AS profit_margin_pct
FROM fact_sales f;
```

### Product Rating Analysis

```sql
SELECT
    ROUND(p.product_rating, 1) AS rating,
    COUNT(*) AS product_count,
    SUM(f.quantity) AS total_sold
FROM fact_sales f
JOIN dim_product p ON f.product_id = p.product_id
GROUP BY ROUND(p.product_rating, 1)
ORDER BY rating DESC;
```

### Delivery Time Analysis

```sql
SELECT
    AVG(f.delivery_date::date - f.order_date::date) AS avg_delivery_days,
    MIN(f.delivery_date::date - f.order_date::date) AS min_delivery_days,
    MAX(f.delivery_date::date - f.order_date::date) AS max_delivery_days
FROM fact_sales f
WHERE f.delivery_date IS NOT NULL;
```

## Best Practices

### Dashboard Design

1. **Keep it Simple:** Max 6 charts per dashboard
2. **Use Filters:** Add date range and category filters
3. **Clear Titles:** Descriptive chart names
4. **Consistent Colors:** Use color palette consistently
5. **Responsive Layout:** Test on different screen sizes

### Query Optimization

1. **Use Indexes:** Ensure foreign keys are indexed
2. **Limit Results:** Use `LIMIT` for large datasets
3. **Aggregate First:** Pre-aggregate in queries when possible
4. **Cache Results:** Enable caching for frequently accessed dashboards

### Security

1. **Read-Only Access:** Never grant write permissions
2. **Row-Level Security:** Implement if needed
3. **Audit Access:** Monitor dashboard access logs
4. **Secure Connection:** Always use SSL for database connection

### Maintenance

1. **Update Queries:** Review queries monthly for optimization
2. **Archive Old Dashboards:** Remove unused dashboards
3. **Monitor Performance:** Check query execution times
4. **Backup Metabase:** Regular backups of Metabase metadata database

## Next Steps

- [Deployment Guide](deployment.md) - Production deployment
- [Troubleshooting](troubleshooting.md) - Debug dashboard issues
- [API Reference](api-reference.md) - SQL query reference
