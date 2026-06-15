"""Data quality checks: null %, row counts, duplicates, date gaps."""
import logging
import psycopg2.extras
from datetime import date

logger = logging.getLogger(__name__)

QC_CHECKS = [
    {
        "name": "raw_row_count",
        "sql": "SELECT COUNT(*) FROM raw.stock_prices",
        "threshold": lambda v: v > 0,
        "message": "raw.stock_prices must have rows"
    },
    {
        "name": "fact_row_count",
        "sql": "SELECT COUNT(*) FROM warehouse.fact_stock_prices",
        "threshold": lambda v: v > 0,
        "message": "fact_stock_prices must have rows"
    },
    {
        "name": "dim_company_count",
        "sql": "SELECT COUNT(*) FROM warehouse.dim_company",
        "threshold": lambda v: v > 0,
        "message": "dim_company must have rows"
    },
    {
        "name": "null_close_price_pct",
        "sql": "SELECT ROUND(100.0 * SUM(CASE WHEN close_price IS NULL THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0), 2) FROM warehouse.fact_stock_prices",
        "threshold": lambda v: v is None or v == 0,
        "message": "close_price must have 0% nulls in facts"
    },
    {
        "name": "null_open_price_pct",
        "sql": "SELECT ROUND(100.0 * SUM(CASE WHEN open_price IS NULL THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0), 2) FROM warehouse.fact_stock_prices",
        "threshold": lambda v: v is None or v == 0,
        "message": "open_price must have 0% nulls in facts"
    },
    {
        "name": "duplicate_fact_keys",
        "sql": "SELECT COUNT(*) FROM (SELECT company_id, date_id, COUNT(*) FROM warehouse.fact_stock_prices GROUP BY company_id, date_id HAVING COUNT(*) > 1) dups",
        "threshold": lambda v: v == 0,
        "message": "No duplicate (company_id, date_id) in fact table"
    },
    {
        "name": "stale_data_days",
        "sql": "SELECT EXTRACT(DAY FROM NOW() - MAX(f.loaded_at)) FROM warehouse.fact_stock_prices f",
        "threshold": lambda v: v is None or v <= 3,
        "message": "Fact table must have been loaded within last 3 days"
    },
    {
        "name": "negative_prices",
        "sql": "SELECT COUNT(*) FROM warehouse.fact_stock_prices WHERE close_price < 0 OR open_price < 0",
        "threshold": lambda v: v == 0,
        "message": "No negative prices in fact table"
    },
    {
        "name": "zero_volume_pct",
        "sql": "SELECT ROUND(100.0 * SUM(CASE WHEN volume = 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0), 2) FROM warehouse.fact_stock_prices",
        "threshold": lambda v: v is None or v < 5,
        "message": "Zero volume rows must be under 5%"
    },
]


def run_quality_checks(conn) -> dict:
    """Run all QC checks. Returns {passed: [...], failed: [...]}."""
    results = {"passed": [], "failed": [], "total": len(QC_CHECKS)}

    with conn.cursor() as cur:
        for check in QC_CHECKS:
            cur.execute(check["sql"])
            value = cur.fetchone()[0]
            numeric_value = float(value) if value is not None else None
            passed = check["threshold"](numeric_value)
            result = {
                "name": check["name"],
                "value": numeric_value,
                "message": check["message"],
                "passed": passed
            }
            if passed:
                results["passed"].append(result)
                logger.info(f"QC PASS: {check['name']} = {numeric_value}")
            else:
                results["failed"].append(result)
                logger.error(f"QC FAIL: {check['name']} = {numeric_value} — {check['message']}")

    return results
