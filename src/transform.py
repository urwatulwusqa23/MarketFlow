"""Transform raw stock data into warehouse star schema."""
import logging
from datetime import date, datetime
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

COMPANY_METADATA = {
    "AAPL": ("Apple Inc.", "Technology"),
    "MSFT": ("Microsoft Corporation", "Technology"),
    "GOOGL": ("Alphabet Inc.", "Technology"),
    "AMZN": ("Amazon.com Inc.", "Consumer Cyclical"),
    "TSLA": ("Tesla Inc.", "Consumer Cyclical"),
    "META": ("Meta Platforms Inc.", "Technology"),
    "NVDA": ("NVIDIA Corporation", "Technology"),
    "JPM": ("JPMorgan Chase & Co.", "Financial Services"),
}


def populate_dim_date(conn, start_date: date, end_date: date) -> int:
    """Populate dim_date for all dates in range. Returns count inserted."""
    import calendar
    from datetime import timedelta

    dates = []
    current = start_date
    while current <= end_date:
        dates.append({
            "date_id": int(current.strftime("%Y%m%d")),
            "full_date": current,
            "year": current.year,
            "quarter": (current.month - 1) // 3 + 1,
            "month": current.month,
            "month_name": current.strftime("%B"),
            "week_of_year": current.isocalendar()[1],
            "day_of_week": current.weekday(),
            "day_name": current.strftime("%A"),
            "is_weekend": current.weekday() >= 5,
        })
        current += timedelta(days=1)

    sql = """
        INSERT INTO warehouse.dim_date
            (date_id, full_date, year, quarter, month, month_name, week_of_year, day_of_week, day_name, is_weekend)
        VALUES
            (%(date_id)s, %(full_date)s, %(year)s, %(quarter)s, %(month)s, %(month_name)s,
             %(week_of_year)s, %(day_of_week)s, %(day_name)s, %(is_weekend)s)
        ON CONFLICT (date_id) DO NOTHING
    """
    with conn.cursor() as cur:
        cur.executemany(sql, dates)
    conn.commit()
    logger.info(f"Populated dim_date with {len(dates)} date records")
    return len(dates)


def upsert_dim_company(conn, symbols: list[str]) -> dict:
    """Upsert company dimension. Returns {symbol: company_id}."""
    sql = """
        INSERT INTO warehouse.dim_company (symbol, company_name, sector)
        VALUES (%(symbol)s, %(company_name)s, %(sector)s)
        ON CONFLICT (symbol) DO UPDATE SET
            company_name = EXCLUDED.company_name,
            sector = EXCLUDED.sector,
            updated_at = NOW()
        RETURNING symbol, company_id
    """
    records = []
    for symbol in symbols:
        name, sector = COMPANY_METADATA.get(symbol, (symbol, "Unknown"))
        records.append({"symbol": symbol, "company_name": name, "sector": sector})

    symbol_to_id = {}
    with conn.cursor() as cur:
        for rec in records:
            cur.execute(sql, rec)
            row = cur.fetchone()
            if row:
                symbol_to_id[row[0]] = row[1]
    conn.commit()
    logger.info(f"Upserted {len(symbol_to_id)} companies into dim_company")
    return symbol_to_id


def transform_and_load_facts(conn, symbol_to_id: dict) -> int:
    """Read from raw, compute daily_return_pct, upsert into fact_stock_prices."""
    fetch_sql = """
        SELECT symbol, trade_date, open_price, high_price, low_price, close_price, volume
        FROM raw.stock_prices
        ORDER BY symbol, trade_date
    """

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(fetch_sql)
        rows = cur.fetchall()

    prev_close = {}
    fact_records = []

    for row in rows:
        symbol = row["symbol"]
        company_id = symbol_to_id.get(symbol)
        if company_id is None:
            continue

        trade_date = row["trade_date"]
        date_id = int(trade_date.strftime("%Y%m%d"))
        close = float(row["close_price"])
        prev = prev_close.get(symbol)
        daily_return = round((close - prev) / prev * 100, 4) if prev else None
        prev_close[symbol] = close

        fact_records.append({
            "company_id": company_id,
            "date_id": date_id,
            "open_price": float(row["open_price"]),
            "high_price": float(row["high_price"]),
            "low_price": float(row["low_price"]),
            "close_price": close,
            "volume": int(row["volume"]),
            "daily_return_pct": daily_return,
        })

    upsert_sql = """
        INSERT INTO warehouse.fact_stock_prices
            (company_id, date_id, open_price, high_price, low_price, close_price, volume, daily_return_pct)
        VALUES
            (%(company_id)s, %(date_id)s, %(open_price)s, %(high_price)s, %(low_price)s,
             %(close_price)s, %(volume)s, %(daily_return_pct)s)
        ON CONFLICT (company_id, date_id) DO UPDATE SET
            open_price = EXCLUDED.open_price,
            high_price = EXCLUDED.high_price,
            low_price = EXCLUDED.low_price,
            close_price = EXCLUDED.close_price,
            volume = EXCLUDED.volume,
            daily_return_pct = EXCLUDED.daily_return_pct,
            loaded_at = NOW()
    """

    with conn.cursor() as cur:
        cur.executemany(upsert_sql, fact_records)
    conn.commit()
    logger.info(f"Upserted {len(fact_records)} fact records")
    return len(fact_records)


def transform_all(conn) -> dict:
    """Main transform entrypoint."""
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT symbol FROM raw.stock_prices")
        symbols = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT MIN(trade_date), MAX(trade_date) FROM raw.stock_prices")
        min_date, max_date = cur.fetchone()

    if not symbols or not min_date:
        logger.warning("No raw data found to transform")
        return {"symbols": 0, "facts": 0}

    populate_dim_date(conn, min_date, max_date)
    symbol_to_id = upsert_dim_company(conn, symbols)
    facts_count = transform_and_load_facts(conn, symbol_to_id)

    return {"symbols": len(symbols), "facts": facts_count}
