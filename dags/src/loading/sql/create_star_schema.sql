-- Star Schema for Sales Data Analytics
-- Mini Data Platform - PostgreSQL Analytics Database

-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- DIMENSION TABLES
-- ============================================================================

-- Dimension: Customer
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id SERIAL PRIMARY KEY,
    customer_name VARCHAR(255) NOT NULL,
    email_hash VARCHAR(64) NOT NULL,
    phone_redacted VARCHAR(50),
    address_redacted VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(email_hash)
);

-- Index on email_hash for lookups
CREATE INDEX IF NOT EXISTS idx_dim_customer_email_hash ON dim_customer(email_hash);

COMMENT ON TABLE dim_customer IS 'Customer dimension table with anonymized PII';
COMMENT ON COLUMN dim_customer.email_hash IS 'SHA-256 hash of customer email';
COMMENT ON COLUMN dim_customer.phone_redacted IS 'Redacted phone number (last 4 digits only)';
COMMENT ON COLUMN dim_customer.address_redacted IS 'Redacted customer address';


-- Dimension: Product
CREATE TABLE IF NOT EXISTS dim_product (
    product_id SERIAL PRIMARY KEY,
    product_title VARCHAR(500) NOT NULL,
    product_rating DECIMAL(2, 1) CHECK (product_rating >= 1.0 AND product_rating <= 5.0),
    product_category VARCHAR(100) NOT NULL,
    is_best_seller BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_title, product_category)
);

-- Index on category for filtering
CREATE INDEX IF NOT EXISTS idx_dim_product_category ON dim_product(product_category);
CREATE INDEX IF NOT EXISTS idx_dim_product_best_seller ON dim_product(is_best_seller);

COMMENT ON TABLE dim_product IS 'Product dimension table';
COMMENT ON COLUMN dim_product.product_rating IS 'Product rating from 1.0 to 5.0';
COMMENT ON COLUMN dim_product.is_best_seller IS 'Flag indicating if product is a best seller';


-- Dimension: Date
CREATE TABLE IF NOT EXISTS dim_date (
    date_id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    year INT NOT NULL,
    month INT NOT NULL CHECK (month >= 1 AND month <= 12),
    day INT NOT NULL CHECK (day >= 1 AND day <= 31),
    quarter INT NOT NULL CHECK (quarter >= 1 AND quarter <= 4),
    day_of_week INT NOT NULL CHECK (day_of_week >= 0 AND day_of_week <= 6),
    week_of_year INT NOT NULL CHECK (week_of_year >= 1 AND week_of_year <= 53),
    is_weekend BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for date filtering
CREATE INDEX IF NOT EXISTS idx_dim_date_date ON dim_date(date);
CREATE INDEX IF NOT EXISTS idx_dim_date_year_month ON dim_date(year, month);

COMMENT ON TABLE dim_date IS 'Date dimension table for time-based analytics';
COMMENT ON COLUMN dim_date.quarter IS 'Quarter of the year (1-4)';
COMMENT ON COLUMN dim_date.day_of_week IS 'Day of week (0=Monday, 6=Sunday)';


-- ============================================================================
-- FACT TABLE
-- ============================================================================

-- Fact: Sales
CREATE TABLE IF NOT EXISTS fact_sales (
    sales_id SERIAL PRIMARY KEY,
    order_id VARCHAR(10) NOT NULL,
    customer_id INT NOT NULL REFERENCES dim_customer(customer_id) ON DELETE CASCADE,
    product_id INT NOT NULL REFERENCES dim_product(product_id) ON DELETE CASCADE,
    order_date_id INT NOT NULL REFERENCES dim_date(date_id) ON DELETE CASCADE,
    delivery_date_id INT REFERENCES dim_date(date_id) ON DELETE CASCADE,
    quantity INT NOT NULL CHECK (quantity > 0),
    discounted_price DECIMAL(10, 2) NOT NULL CHECK (discounted_price > 0),
    original_price DECIMAL(10, 2) NOT NULL CHECK (original_price > 0),
    discount_percentage INT CHECK (discount_percentage >= 0 AND discount_percentage <= 100),
    profit DECIMAL(10, 2),
    data_collected_at DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(order_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_fact_sales_customer ON fact_sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_product ON fact_sales(product_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_order_date ON fact_sales(order_date_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_delivery_date ON fact_sales(delivery_date_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_order_id ON fact_sales(order_id);

COMMENT ON TABLE fact_sales IS 'Sales fact table containing transaction metrics';
COMMENT ON COLUMN fact_sales.order_id IS 'Unique order identifier from source system';
COMMENT ON COLUMN fact_sales.profit IS 'Calculated profit (discounted_price - COGS)';
COMMENT ON COLUMN fact_sales.data_collected_at IS 'Date when data was collected from source';


-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to auto-update updated_at
CREATE TRIGGER update_dim_customer_updated_at
    BEFORE UPDATE ON dim_customer
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_dim_product_updated_at
    BEFORE UPDATE ON dim_product
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_fact_sales_updated_at
    BEFORE UPDATE ON fact_sales
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- GRANTS (for Metabase read-only user)
-- ============================================================================

-- Create read-only role if it doesn't exist
-- Note: METABASE_PASSWORD must be passed as psql variable
-- Example: psql -v METABASE_PASSWORD="'$PASSWORD'" -f create_star_schema.sql
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'metabase_reader') THEN
        CREATE ROLE metabase_reader WITH LOGIN PASSWORD :'METABASE_PASSWORD';
    END IF;
END
$$;

-- Grant read access to tables
GRANT CONNECT ON DATABASE shadowpostgresdb TO metabase_reader;
GRANT USAGE ON SCHEMA public TO metabase_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO metabase_reader;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO metabase_reader;

-- Ensure future tables are also readable
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO metabase_reader;
