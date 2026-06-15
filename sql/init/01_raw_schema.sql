-- MarketFlow: Raw schema for ingested stock price data
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.stock_prices (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(10)    NOT NULL,
    trade_date  DATE           NOT NULL,
    open_price  NUMERIC(12, 4),
    high_price  NUMERIC(12, 4),
    low_price   NUMERIC(12, 4),
    close_price NUMERIC(12, 4),
    volume      BIGINT,
    loaded_at   TIMESTAMP      DEFAULT NOW(),
    UNIQUE (symbol, trade_date)
);

COMMENT ON TABLE raw.stock_prices IS 'Landing table for raw OHLCV data extracted from Alpha Vantage API.';
