import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from src.extract import (
    fetch_daily_prices,
    filter_new_records,
    load_raw_records,
    get_latest_loaded_date,
)

SAMPLE_AV_RESPONSE = {
    "Time Series (Daily)": {
        "2024-01-05": {"1. open": "185.0", "2. high": "187.0", "3. low": "184.0", "4. close": "186.0", "5. volume": "50000000"},
        "2024-01-04": {"1. open": "182.0", "2. high": "184.0", "3. low": "181.0", "4. close": "183.5", "5. volume": "45000000"},
        "2024-01-03": {"1. open": "180.0", "2. high": "182.0", "3. low": "179.0", "4. close": "181.0", "5. volume": "42000000"},
    }
}


def test_fetch_daily_prices_success():
    with patch("src.extract.requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_AV_RESPONSE
        mock_get.return_value.raise_for_status = MagicMock()
        records = fetch_daily_prices("AAPL", "test_key")
    assert len(records) == 3
    assert records[0]["symbol"] == "AAPL"
    assert records[0]["close_price"] == 186.0


def test_fetch_daily_prices_error_message():
    with patch("src.extract.requests.get") as mock_get:
        mock_get.return_value.json.return_value = {"Error Message": "Invalid API call"}
        mock_get.return_value.raise_for_status = MagicMock()
        with pytest.raises(ValueError, match="Alpha Vantage error"):
            fetch_daily_prices("INVALID", "test_key")


def test_fetch_daily_prices_rate_limit():
    with patch("src.extract.requests.get") as mock_get:
        mock_get.return_value.json.return_value = {"Note": "API rate limit reached"}
        mock_get.return_value.raise_for_status = MagicMock()
        records = fetch_daily_prices("AAPL", "test_key")
    assert records == []


def test_filter_new_records_with_latest_date():
    records = [
        {"symbol": "AAPL", "trade_date": "2024-01-05"},
        {"symbol": "AAPL", "trade_date": "2024-01-04"},
        {"symbol": "AAPL", "trade_date": "2024-01-03"},
    ]
    filtered = filter_new_records(records, date(2024, 1, 4))
    assert len(filtered) == 1
    assert filtered[0]["trade_date"] == "2024-01-05"


def test_filter_new_records_no_latest():
    records = [{"symbol": "AAPL", "trade_date": "2024-01-05"}]
    assert filter_new_records(records, None) == records


def test_filter_new_records_empty():
    assert filter_new_records([], date(2024, 1, 1)) == []


def test_get_latest_loaded_date():
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (date(2024, 1, 5),)
    result = get_latest_loaded_date(mock_conn, "AAPL")
    assert result == date(2024, 1, 5)


def test_get_latest_loaded_date_none():
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (None,)
    result = get_latest_loaded_date(mock_conn, "AAPL")
    assert result is None


def test_load_raw_records_empty():
    mock_conn = MagicMock()
    count = load_raw_records(mock_conn, [])
    assert count == 0
    mock_conn.cursor.assert_not_called()
