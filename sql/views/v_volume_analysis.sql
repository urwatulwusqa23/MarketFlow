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
