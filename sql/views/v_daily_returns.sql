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
