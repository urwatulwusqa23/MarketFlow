import pytest
from unittest.mock import MagicMock

from src.quality_checks import run_quality_checks, QC_CHECKS


def make_mock_conn(return_values):
    """Helper: mock conn where each cursor.fetchone() returns next value in list."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.side_effect = [(v,) for v in return_values]
    return mock_conn


def test_all_checks_pass():
    # Values that pass all checks: row counts > 0, null% = 0, dups = 0, stale = 0, neg = 0, zero_vol = 0
    passing_values = [100, 800, 8, 0, 0, 0, 0, 0, 0]
    conn = make_mock_conn(passing_values)
    results = run_quality_checks(conn)
    assert results["total"] == len(QC_CHECKS)
    assert len(results["failed"]) == 0
    assert len(results["passed"]) == len(QC_CHECKS)


def test_zero_row_count_fails():
    values = [0, 800, 8, 0, 0, 0, 0, 0, 0]
    conn = make_mock_conn(values)
    results = run_quality_checks(conn)
    failed_names = [c["name"] for c in results["failed"]]
    assert "raw_row_count" in failed_names


def test_null_close_price_fails():
    values = [100, 800, 8, 5.0, 0, 0, 0, 0, 0]  # 5% null close price
    conn = make_mock_conn(values)
    results = run_quality_checks(conn)
    failed_names = [c["name"] for c in results["failed"]]
    assert "null_close_price_pct" in failed_names


def test_duplicate_keys_fails():
    values = [100, 800, 8, 0, 0, 3, 0, 0, 0]  # 3 duplicates
    conn = make_mock_conn(values)
    results = run_quality_checks(conn)
    failed_names = [c["name"] for c in results["failed"]]
    assert "duplicate_fact_keys" in failed_names


def test_negative_prices_fails():
    values = [100, 800, 8, 0, 0, 0, 0, 5, 0]
    conn = make_mock_conn(values)
    results = run_quality_checks(conn)
    failed_names = [c["name"] for c in results["failed"]]
    assert "negative_prices" in failed_names
