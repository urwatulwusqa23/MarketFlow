import pytest
from unittest.mock import MagicMock, patch, call
from datetime import date

from src.transform import (
    populate_dim_date,
    upsert_dim_company,
    transform_and_load_facts,
    transform_all,
)


def test_populate_dim_date_range():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    count = populate_dim_date(mock_conn, date(2024, 1, 1), date(2024, 1, 3))
    assert count == 3
    mock_cursor.executemany.assert_called_once()


def test_populate_dim_date_single_day():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    count = populate_dim_date(mock_conn, date(2024, 1, 15), date(2024, 1, 15))
    assert count == 1


def test_upsert_dim_company_known_symbol():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = ("AAPL", 1)

    result = upsert_dim_company(mock_conn, ["AAPL"])
    assert result == {"AAPL": 1}


def test_upsert_dim_company_unknown_symbol():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = ("XYZ", 99)

    result = upsert_dim_company(mock_conn, ["XYZ"])
    assert "XYZ" in result


def test_transform_all_no_data():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchall.return_value = []
    mock_cursor.fetchone.return_value = (None, None)

    result = transform_all(mock_conn)
    assert result == {"symbols": 0, "facts": 0}
