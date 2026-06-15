# MarketFlow

A production-quality daily incremental ETL pipeline that extracts OHLCV stock data from the Alpha Vantage API, validates and transforms it into a PostgreSQL star schema, and exposes analytical SQL views for downstream BI or data science use.

---

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐
│  Alpha Vantage  │───▶│  extract.py     │───▶│  raw.stock_prices       │
│  Free API       │    │  (incremental)  │    │  (PostgreSQL)           │
└─────────────────┘    └─────────────────┘    └────────────┬────────────┘
                                                            │
                                                            ▼
                                               ┌─────────────────────────┐
                                               │  transform.py           │
                                               │  (star schema builder)  │
                                               └────────────┬────────────┘
                                                            │
                              ┌─────────────────────────────┼────────────────────────┐
                              ▼                             ▼                        ▼
                   ┌──────────────────┐      ┌──────────────────────┐   ┌──────────────────┐
                   │  dim_company     │      │  fact_stock_prices   │   │  dim_date        │
                   │                  │◀─────│                      │──▶│                  │
                   └──────────────────┘      └──────────────────────┘   └──────────────────┘
                                                            │
                                                            ▼
                                               ┌─────────────────────────┐
                                               │  SQL Analytical Views   │
                                               │  v_daily_returns        │
                                               │  v_moving_averages      │
                                               │  v_volume_analysis      │
                                               └─────────────────────────┘
```

---

## Star Schema

```
                        ┌──────────────────────┐
                        │   dim_company        │
                        │──────────────────────│
                        │ company_id (PK)      │
                        │ symbol               │
                        │ company_name         │
                        │ sector               │
                        │ created_at           │
                        │ updated_at           │
                        └──────────┬───────────┘
                                   │
                                   │ FK: company_id
                                   ▼
┌──────────────────────┐   ┌───────────────────────────┐   ┌──────────────────────┐
│   dim_date           │   │   fact_stock_prices       │   │                      │
│──────────────────────│   │───────────────────────────│   │                      │
│ date_id (PK)         │◀──│ fact_id (PK)              │   │                      │
│ full_date            │   │ company_id (FK)           │   │                      │
│ year                 │   │ date_id (FK)              │──▶│                      │
│ quarter              │   │ open_price                │   │                      │
│ month                │   │ high_price                │   │                      │
│ month_name           │   │ low_price                 │   │                      │
│ week_of_year         │   │ close_price               │   │                      │
│ day_of_week          │   │ volume                    │   │                      │
│ day_name             │   │ price_range (computed)    │   │                      │
│ is_weekend           │   │ daily_return_pct          │   │                      │
└──────────────────────┘   │ loaded_at                 │   └──────────────────────┘
                           └───────────────────────────┘
```

---

## Prerequisites

- Docker and Docker Compose (v2+)
- An Alpha Vantage API key — free tier at https://www.alphavantage.co/support/#api-key
- Python 3.11+ (only needed if running outside Docker)

---

## Quick Start

Five commands to get MarketFlow running end-to-end:

```bash
# 1. Clone the repo
git clone <repo-url> && cd MarketFlow

# 2. Create your .env file from the example
cp .env.example .env
# Edit .env and set your real ALPHA_VANTAGE_API_KEY

# 3. Start PostgreSQL (will auto-initialise raw + warehouse schemas)
docker compose up postgres -d

# 4. Run the full pipeline once
docker compose up pipeline

# 5. Connect to the database and query the views
docker compose exec postgres psql -U marketflow_user -d marketflow \
  -c "SELECT * FROM warehouse.v_daily_returns LIMIT 20;"
```

---

## Environment Variables

| Variable                | Default           | Description                                        |
|-------------------------|-------------------|----------------------------------------------------|
| `ALPHA_VANTAGE_API_KEY` | *(required)*      | Your Alpha Vantage API key                         |
| `POSTGRES_DB`           | `marketflow`      | PostgreSQL database name                           |
| `POSTGRES_USER`         | `marketflow_user` | PostgreSQL username                                |
| `POSTGRES_PASSWORD`     | `marketflow_pass` | PostgreSQL password                                |
| `POSTGRES_HOST`         | `postgres`        | Hostname — use `postgres` inside Docker, `localhost` outside |
| `POSTGRES_PORT`         | `5432`            | PostgreSQL port                                    |

---

## How Incremental Loading Works

Each pipeline run is designed to process only new data, not re-fetch the full history:

1. Before calling the API for a symbol, `extract.py` queries `raw.stock_prices` for the most recent `trade_date` already loaded (`get_latest_loaded_date`).
2. If no data exists (first run), `outputsize=full` is requested from Alpha Vantage, returning up to 20 years of history.
3. If data already exists, `outputsize=compact` is used (last 100 trading days), then `filter_new_records` discards everything on or before the last known date.
4. Records are upserted (INSERT … ON CONFLICT DO UPDATE), so re-runs are idempotent.
5. The transform layer similarly upserts into the warehouse tables, so partial or repeated runs never produce duplicates.

---

## Running the Pipeline Manually

### Via Docker Compose (recommended)

```bash
# Run the full pipeline
docker compose up pipeline

# Run for specific symbols only
docker compose run --rm pipeline python -m src.orchestrate AAPL MSFT

# Run just the extraction step
docker compose run --rm pipeline python -m src.extract

# Run just the transformation step
docker compose run --rm pipeline python -c "
from src.extract import get_db_connection
from src.transform import transform_all
conn = get_db_connection()
print(transform_all(conn))
conn.close()
"
```

### Locally (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export POSTGRES_HOST=localhost
export ALPHA_VANTAGE_API_KEY=your_key_here

# Run the orchestrator
PYTHONPATH=. python -m src.orchestrate

# Or run individual modules
PYTHONPATH=. python -m src.extract
```

---

## Running Tests

```bash
# Install dependencies (if not already done)
pip install -r requirements.txt

# Run all tests
PYTHONPATH=. pytest tests/ -v

# Run with coverage
PYTHONPATH=. pytest tests/ -v --tb=short --cov=src --cov-report=term-missing

# Run a specific test file
PYTHONPATH=. pytest tests/test_extract.py -v
```

All tests use mocks — no live database or API connection is needed.

---

## SQL Analytical Views

Views are defined in `sql/views/` and should be applied to the database after the warehouse schema is initialised:

```bash
docker compose exec postgres psql -U marketflow_user -d marketflow \
  -f /docker-entrypoint-initdb.d/../views/v_daily_returns.sql
```

Or apply all views at once:

```bash
for f in sql/views/*.sql; do
  docker compose exec -T postgres psql -U marketflow_user -d marketflow < "$f"
done
```

### v_daily_returns

Returns daily close price and return percentage for each non-weekend trading day, with a 5-day rolling average return computed using a window function.

Columns: `symbol`, `company_name`, `full_date`, `close_price`, `daily_return_pct`, `rolling_5d_return_avg`, `year`, `quarter`, `month`

```sql
SELECT symbol, full_date, daily_return_pct, rolling_5d_return_avg
FROM warehouse.v_daily_returns
WHERE symbol = 'AAPL'
ORDER BY full_date DESC
LIMIT 30;
```

### v_moving_averages

Computes 20-day and 50-day simple moving averages (SMA) for each stock, plus the distance of the current close price from the SMA-20 (useful for mean-reversion signals).

Columns: `symbol`, `company_name`, `full_date`, `close_price`, `sma_20`, `sma_50`, `price_vs_sma20`

```sql
-- Find stocks trading significantly above their 20-day MA
SELECT symbol, full_date, close_price, sma_20, price_vs_sma20
FROM warehouse.v_moving_averages
WHERE full_date = CURRENT_DATE - INTERVAL '1 day'
  AND price_vs_sma20 > 5
ORDER BY price_vs_sma20 DESC;
```

### v_volume_analysis

Compares each day's volume against its 30-day rolling average. Also includes intraday price range as a percentage of close price — a proxy for volatility.

Columns: `symbol`, `company_name`, `full_date`, `volume`, `avg_volume_30d`, `volume_vs_avg_pct`, `price_range`, `intraday_range_pct`

```sql
-- Find unusual volume spikes (>200% of 30-day avg)
SELECT symbol, full_date, volume, avg_volume_30d, volume_vs_avg_pct
FROM warehouse.v_volume_analysis
WHERE volume_vs_avg_pct > 200
ORDER BY full_date DESC, volume_vs_avg_pct DESC;
```

---

## Data Quality Checks

The `quality_checks.py` module runs 9 automated checks after each pipeline run. If any check fails, `orchestrate.py` exits with code 1 (fails CI/CD).

| Check Name            | What It Verifies                                              | Threshold          |
|-----------------------|---------------------------------------------------------------|--------------------|
| `raw_row_count`       | Raw table is not empty                                        | > 0 rows           |
| `fact_row_count`      | Fact table is not empty                                       | > 0 rows           |
| `dim_company_count`   | Company dimension is populated                                | > 0 rows           |
| `null_close_price_pct`| No null close prices in fact table                            | 0%                 |
| `null_open_price_pct` | No null open prices in fact table                             | 0%                 |
| `duplicate_fact_keys` | No duplicate (company_id, date_id) combinations               | 0 duplicates       |
| `stale_data_days`     | Data was loaded recently (not stale)                          | <= 3 days ago      |
| `negative_prices`     | No negative open or close prices                              | 0 rows             |
| `zero_volume_pct`     | Zero-volume rows are rare (holidays, halts)                   | < 5%               |

---

## Project Structure

```
MarketFlow/
├── docker-compose.yml          # PostgreSQL + pipeline services
├── Dockerfile                  # Python 3.11-slim image for pipeline
├── .env.example                # Template for environment variables
├── .gitignore                  # Excludes .env, __pycache__, venvs, logs
├── README.md                   # This file
├── requirements.txt            # Python dependencies (pinned versions)
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions: test + lint on push/PR
├── sql/
│   ├── init/
│   │   ├── 01_raw_schema.sql   # Creates raw schema + raw.stock_prices table
│   │   └── 02_warehouse_schema.sql  # Creates warehouse schema + star schema tables
│   └── views/
│       ├── v_daily_returns.sql      # Daily return % with 5d rolling avg
│       ├── v_moving_averages.sql    # SMA-20, SMA-50, price vs SMA-20
│       └── v_volume_analysis.sql   # Volume vs 30d avg, intraday range %
├── src/
│   ├── __init__.py
│   ├── extract.py              # Alpha Vantage API extraction + incremental load to raw
│   ├── transform.py            # Raw → warehouse star schema transformation
│   ├── load.py                 # Thin wrapper: extract_all → transform_all
│   ├── quality_checks.py       # 9 automated data quality checks
│   └── orchestrate.py          # Main entrypoint: extract → transform → QC → report
└── tests/
    ├── __init__.py
    ├── test_extract.py         # Unit tests for extraction logic (fully mocked)
    ├── test_transform.py       # Unit tests for transform functions (fully mocked)
    ├── test_load.py            # Unit tests for pipeline orchestration (fully mocked)
    └── test_quality_checks.py  # Unit tests for all 9 QC checks (fully mocked)
```

---

## Tracked Symbols

By default, MarketFlow tracks 8 large-cap US equities:

| Symbol | Company                  | Sector              |
|--------|--------------------------|---------------------|
| AAPL   | Apple Inc.               | Technology          |
| MSFT   | Microsoft Corporation    | Technology          |
| GOOGL  | Alphabet Inc.            | Technology          |
| AMZN   | Amazon.com Inc.          | Consumer Cyclical   |
| TSLA   | Tesla Inc.               | Consumer Cyclical   |
| META   | Meta Platforms Inc.      | Technology          |
| NVDA   | NVIDIA Corporation       | Technology          |
| JPM    | JPMorgan Chase & Co.     | Financial Services  |

To add more symbols, either pass them as CLI arguments or extend `DEFAULT_SYMBOLS` in `src/extract.py` and `COMPANY_METADATA` in `src/transform.py`.

---

## Notes on Alpha Vantage Free Tier

- The free tier allows **25 API requests per day**.
- With 8 symbols, the pipeline uses 8 requests per run — well within the limit.
- If you hit the rate limit, you will see a `"Note"` key in the API response; the pipeline logs a warning and skips that symbol gracefully.
- For larger symbol lists, consider adding `time.sleep(12)` between requests to stay within the 5 requests/minute rate limit.
