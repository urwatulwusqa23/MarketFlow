"""Thin wrapper that wires extract → transform in sequence."""
import logging
from src.extract import get_db_connection, extract_all
from src.transform import transform_all

logger = logging.getLogger(__name__)


def run_pipeline(symbols=None):
    """Full extract → transform pipeline. Returns summary."""
    logger.info("=== MarketFlow Pipeline Starting ===")
    extract_summary = extract_all(symbols)
    logger.info(f"Extract complete: {extract_summary}")

    conn = get_db_connection()
    try:
        transform_summary = transform_all(conn)
    finally:
        conn.close()

    logger.info(f"Transform complete: {transform_summary}")
    return {"extract": extract_summary, "transform": transform_summary}
