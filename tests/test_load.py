import pytest
from unittest.mock import patch, MagicMock

from src.load import run_pipeline


def test_run_pipeline_success():
    with patch("src.load.extract_all") as mock_extract, \
         patch("src.load.get_db_connection") as mock_conn_fn, \
         patch("src.load.transform_all") as mock_transform:

        mock_extract.return_value = {"records_loaded": 100, "symbols_processed": 8, "errors": []}
        mock_transform.return_value = {"symbols": 8, "facts": 800}
        mock_conn_fn.return_value = MagicMock()

        result = run_pipeline()

        assert result["extract"]["records_loaded"] == 100
        assert result["transform"]["facts"] == 800


def test_run_pipeline_with_symbols():
    with patch("src.load.extract_all") as mock_extract, \
         patch("src.load.get_db_connection") as mock_conn_fn, \
         patch("src.load.transform_all") as mock_transform:

        mock_extract.return_value = {"records_loaded": 10, "symbols_processed": 1, "errors": []}
        mock_transform.return_value = {"symbols": 1, "facts": 10}
        mock_conn_fn.return_value = MagicMock()

        result = run_pipeline(symbols=["AAPL"])
        mock_extract.assert_called_once_with(["AAPL"])
