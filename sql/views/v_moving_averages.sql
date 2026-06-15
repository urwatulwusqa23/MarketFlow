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
