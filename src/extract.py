"""Extract OHLCV data from Alpha Vantage API with incremental logic."""
import os
import requests
import logging
from datetime import date, datetime
from typing import Optional
import psycopg2
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
DEFAULT_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "JPM"]


def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "marketflow"),
        user=os.getenv("POSTGRES_USER", "marketflow_user"),
        password=os.getenv("POSTGRES_PASSWORD", "marketflow_pass"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432")
    )


def get_latest_loaded_date(conn, symbol: str) -> Optional[date]:
    """Get most recent trade_date already loaded for this symbol (incremental logic)."""
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(trade_date) FROM raw.stock_prices WHERE symbol = %s", (symbol,))
        result = cur.fetchone()[0]
    return result


def fetch_daily_prices(symbol: str, api_key: str, outputsize: str = "compact") -> list[dict]:
    """Fetch TIME_SERIES_DAILY from Alpha Vantage. Returns list of OHLCV dicts."""
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": outputsize,
        "apikey": api_key
    }
    logger.info(f"Fetching {symbol} from Alpha Vantage (outputsize={outputsize})")
    resp = requests.get(ALPHA_VANTAGE_BASE, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if "Error Message" in data:
        raise ValueError(f"Alpha Vantage error for {symbol}: {data['Error Message']}")
    if "Note" in data:
        logger.warning(f"API rate limit note for {symbol}: {data['Note']}")
        return []
    if "Information" in data:
        logger.warning(f"Alpha Vantage info/premium message for {symbol}: {data['Information']}")
        return []

    time_series = data.get("Time Series (Daily)", {})
    records = []
    for date_str, ohlcv in time_series.items():
        records.append({
            "symbol": symbol,
            "trade_date": date_str,
            "open_price": float(ohlcv["1. open"]),
            "high_price": float(ohlcv["2. high"]),
            "low_price": float(ohlcv["3. low"]),
            "close_price": float(ohlcv["4. close"]),
            "volume": int(ohlcv["5. volume"]),
        })
    logger.info(f"Fetched {len(records)} records for {symbol}")
    return records


def filter_new_records(records: list[dict], latest_date) -> list[dict]:
    """Keep only records newer than latest_date (incremental load)."""
    if latest_date is None:
        return records
    return [r for r in records if r["trade_date"] > str(latest_date)]


def load_raw_records(conn, records: list[dict]) -> int:
    """Upsert records into raw.stock_prices. Returns count inserted."""
    if not records:
        return 0
    insert_sql = """
        INSERT INTO raw.stock_prices (symbol, trade_date, open_price, high_price, low_price, close_price, volume)
        VALUES (%(symbol)s, %(trade_date)s, %(open_price)s, %(high_price)s, %(low_price)s, %(close_price)s, %(volume)s)
        ON CONFLICT (symbol, trade_date) DO UPDATE SET
            open_price = EXCLUDED.open_price,
            high_price = EXCLUDED.high_price,
            low_price = EXCLUDED.low_price,
            close_price = EXCLUDED.close_price,
            volume = EXCLUDED.volume,
            loaded_at = NOW()
    """
    with conn.cursor() as cur:
        cur.executemany(insert_sql, records)
    conn.commit()
    logger.info(f"Upserted {len(records)} records into raw.stock_prices")
    return len(records)


def extract_all(symbols: list[str] = None) -> dict:
    """Main extraction entrypoint. Returns summary dict."""
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise EnvironmentError("ALPHA_VANTAGE_API_KEY not set")

    symbols = symbols or DEFAULT_SYMBOLS
    summary = {"symbols_processed": 0, "records_loaded": 0, "errors": []}

    conn = get_db_connection()
    try:
        for symbol in symbols:
            try:
                latest = get_latest_loaded_date(conn, symbol)
                # free tier only supports compact (last 100 trading days)
                records = fetch_daily_prices(symbol, api_key, outputsize="compact")
                new_records = filter_new_records(records, latest)
                count = load_raw_records(conn, new_records)
                summary["records_loaded"] += count
                summary["symbols_processed"] += 1
            except Exception as e:
                logger.error(f"Failed to extract {symbol}: {e}")
                summary["errors"].append({"symbol": symbol, "error": str(e)})
    finally:
        conn.close()

    return summary


if __name__ == "__main__":
    result = extract_all()
    logger.info(f"Extraction complete: {result}")
