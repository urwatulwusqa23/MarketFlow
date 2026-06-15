"""Orchestration: run extract → transform → quality checks and report."""
import logging
import sys
from datetime import datetime
from src.extract import get_db_connection, extract_all
from src.transform import transform_all
from src.quality_checks import run_quality_checks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def run(symbols=None):
    start = datetime.now()
    logger.info("=" * 60)
    logger.info("MarketFlow Pipeline Run Started")
    logger.info("=" * 60)

    # Phase 1: Extract
    logger.info("[1/3] Extracting data from Alpha Vantage...")
    extract_summary = extract_all(symbols)
    logger.info(f"Extract: {extract_summary['records_loaded']} new records, {len(extract_summary['errors'])} errors")

    # Phase 2: Transform
    logger.info("[2/3] Transforming into star schema...")
    conn = get_db_connection()
    try:
        transform_summary = transform_all(conn)
    finally:
        conn.close()
    logger.info(f"Transform: {transform_summary['facts']} fact rows loaded")

    # Phase 3: Quality checks
    logger.info("[3/3] Running data quality checks...")
    conn = get_db_connection()
    try:
        qc_results = run_quality_checks(conn)
    finally:
        conn.close()

    elapsed = (datetime.now() - start).total_seconds()

    logger.info("=" * 60)
    logger.info(f"Pipeline Complete in {elapsed:.1f}s")
    logger.info(f"QC: {len(qc_results['passed'])}/{qc_results['total']} checks passed")
    if qc_results['failed']:
        logger.error(f"FAILED CHECKS: {[c['name'] for c in qc_results['failed']]}")
        sys.exit(1)
    logger.info("=" * 60)

    return {
        "extract": extract_summary,
        "transform": transform_summary,
        "quality": qc_results,
        "elapsed_seconds": elapsed
    }


if __name__ == "__main__":
    import sys
    symbols = sys.argv[1:] or None
    run(symbols)
