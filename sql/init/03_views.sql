-- MarketFlow: Analytical views (auto-applied on DB init)

-- Daily return % per stock with 5-day rolling avg
CREATE OR REPLACE VIEW warehouse.v_daily_returns AS
SELECT
    dc.symbol,
    dc.company_name,
    dd.full_date,
    f.close_price,
    f.daily_return_pct,
    ROUND(AVG(f.daily_return_pct) OVER (
        PARTITION BY f.company_id
        ORDER BY dd.full_date
        ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
    ), 4) AS rolling_5d_return_avg,
    dd.year,
    dd.quarter,
    dd.month
FROM warehouse.fact_stock_prices f
JOIN warehouse.dim_company dc ON f.company_id = dc.company_id
JOIN warehouse.dim_date dd ON f.date_id = dd.date_id
WHERE NOT dd.is_weekend
ORDER BY dc.symbol, dd.full_date;

-- 20-day and 50-day simple moving averages
CREATE OR REPLACE VIEW warehouse.v_moving_averages AS
SELECT
    dc.symbol,
    dc.company_name,
    dd.full_date,
    f.close_price,
    ROUND(AVG(f.close_price) OVER (
        PARTITION BY f.company_id
        ORDER BY dd.full_date
        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ), 4) AS sma_20,
    ROUND(AVG(f.close_price) OVER (
        PARTITION BY f.company_id
        ORDER BY dd.full_date
        ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
    ), 4) AS sma_50,
    ROUND(f.close_price - AVG(f.close_price) OVER (
        PARTITION BY f.company_id
        ORDER BY dd.full_date
        ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ), 4) AS price_vs_sma20
FROM warehouse.fact_stock_prices f
JOIN warehouse.dim_company dc ON f.company_id = dc.company_id
JOIN warehouse.dim_date dd ON f.date_id = dd.date_id
WHERE NOT dd.is_weekend
ORDER BY dc.symbol, dd.full_date;

-- Volume analysis: daily vs 30-day average volume
CREATE OR REPLACE VIEW warehouse.v_volume_analysis AS
SELECT
    dc.symbol,
    dc.company_name,
    dd.full_date,
    f.volume,
    ROUND(AVG(f.volume) OVER (
        PARTITION BY f.company_id
        ORDER BY dd.full_date
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    )) AS avg_volume_30d,
    ROUND(100.0 * f.volume / NULLIF(AVG(f.volume) OVER (
        PARTITION BY f.company_id
        ORDER BY dd.full_date
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ), 0), 2) AS volume_vs_avg_pct,
    f.price_range,
    ROUND(f.price_range / NULLIF(f.close_price, 0) * 100, 4) AS intraday_range_pct
FROM warehouse.fact_stock_prices f
JOIN warehouse.dim_company dc ON f.company_id = dc.company_id
JOIN warehouse.dim_date dd ON f.date_id = dd.date_id
WHERE NOT dd.is_weekend
ORDER BY dc.symbol, dd.full_date;
