-- MarketFlow: Warehouse star schema
CREATE SCHEMA IF NOT EXISTS warehouse;

-- Dimension: Company
CREATE TABLE IF NOT EXISTS warehouse.dim_company (
    company_id   SERIAL PRIMARY KEY,
    symbol       VARCHAR(10)  UNIQUE NOT NULL,
    company_name VARCHAR(255),
    sector       VARCHAR(100),
    created_at   TIMESTAMP DEFAULT NOW(),
    updated_at   TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE warehouse.dim_company IS 'Company dimension: one row per tracked ticker symbol.';

-- Dimension: Date
CREATE TABLE IF NOT EXISTS warehouse.dim_date (
    date_id      INTEGER PRIMARY KEY,  -- YYYYMMDD format
    full_date    DATE UNIQUE NOT NULL,
    year         INTEGER,
    quarter      INTEGER,
    month        INTEGER,
    month_name   VARCHAR(20),
    week_of_year INTEGER,
    day_of_week  INTEGER,
    day_name     VARCHAR(20),
    is_weekend   BOOLEAN
);

COMMENT ON TABLE warehouse.dim_date IS 'Date dimension: one row per calendar day, pre-populated for all dates in the data range.';

-- Fact: Stock Prices
CREATE TABLE IF NOT EXISTS warehouse.fact_stock_prices (
    fact_id          SERIAL PRIMARY KEY,
    company_id       INTEGER REFERENCES warehouse.dim_company(company_id),
    date_id          INTEGER REFERENCES warehouse.dim_date(date_id),
    open_price       NUMERIC(12, 4),
    high_price       NUMERIC(12, 4),
    low_price        NUMERIC(12, 4),
    close_price      NUMERIC(12, 4),
    volume           BIGINT,
    price_range      NUMERIC(12, 4) GENERATED ALWAYS AS (high_price - low_price) STORED,
    daily_return_pct NUMERIC(8, 4),
    loaded_at        TIMESTAMP DEFAULT NOW(),
    UNIQUE (company_id, date_id)
);

COMMENT ON TABLE warehouse.fact_stock_prices IS 'Fact table: one row per company per trading day, with OHLCV and derived metrics.';
