# NIFTY IT Automated Equity Research Pipeline

## 1. Project Overview

This project is a production-grade **Data Engineering ETL (Extract, Transform, Load) Pipeline** designed to track the financial health and market performance of India's top NIFTY IT sector companies (Infosys, Tech Mahindra, Wipro, and HCLTech). 

Initially conceived as a standalone Python analytics script, it was refactored into a full-scale ETL architecture to solve critical business problems:
- **Resiliency & Automation:** Scripts running in Jupyter Notebooks or triggered manually are fragile. By moving to a dedicated ETL flow designed for orchestration (e.g., Apache Airflow), the pipeline can run reliably on a schedule, decoupling data fetching from data consumption.
- **Performance:** Directly querying a live API (like Yahoo Finance) every time a user opens a dashboard introduces massive latency and risks rate-limiting. This pipeline introduces a persistent PostgreSQL Data Warehouse layer. Heavy calculations are computed once during the nightly batch job, allowing the frontend dashboard to serve data instantly to end-users.
- **Data Integrity:** Financial APIs frequently drop data or suffer outages. This pipeline introduces robust Data Quality checks, explicitly tracking and imputing missing data rather than silently failing or misleading traders.

## 2. Architecture

The architecture strictly separates concerns across three layers: Extraction, Transformation, and Serving.

### Data Flow
1. **Extraction (`ingest.py`):** Connects to the `yfinance` API to pull daily OHLCV prices and fundamental metrics. It performs data quality checks (e.g., handling missing days, identifying market halts vs. API outages) and loads the raw data into PostgreSQL using idempotent UPSERTs.
2. **Transformation (`transform.py`):** Reads the raw data from PostgreSQL, applies business logic (calculating 7-day rolling averages and net profit margins), joins price data with financial metrics, and writes the finalized, clean dataset into an analytics data mart.
3. **Serving (`app.py`):** A Streamlit dashboard that connects directly to the PostgreSQL analytics table. It visualizes the pre-calculated metrics, trends, and pipeline metadata without ever touching the external internet.

### Database Schema (PostgreSQL)

The database (`equity_db`) contains four explicit tables:

**1. `raw_prices` (Extraction Layer)**
- `date` (DATE) - *Primary Key*
- `ticker` (VARCHAR) - *Primary Key*
- `open`, `high`, `low`, `close` (NUMERIC)
- `volume` (BIGINT)
- `data_status` (VARCHAR) - Added via migration. Tracks data provenance (`ACTUAL`, `MARKET_HALT`, or `IMPUTED_API_OUTAGE`).

**2. `raw_financials` (Extraction Layer)**
- `fetch_date` (DATE) - *Primary Key*
- `ticker` (VARCHAR) - *Primary Key*
- `trailing_pe` (NUMERIC)
- `total_revenue` (NUMERIC)
- `net_income` (NUMERIC)

**3. `analytics_summary` (Transformation / Serving Layer)**
- `date` (DATE) - *Primary Key*
- `ticker` (VARCHAR) - *Primary Key*
- `close_price` (NUMERIC)
- `rolling_7d_avg` (NUMERIC)
- `net_profit_margin_pct` (NUMERIC)
- `pe_ratio` (NUMERIC)
- `data_status` (VARCHAR)

**4. `pipeline_logs` (Metadata Layer)**
- `run_id` (SERIAL) - *Primary Key*
- `execution_time` (TIMESTAMP)
- `task_name` (VARCHAR)
- `status` (VARCHAR)
- `records_processed` (INT)
- `error_message` (TEXT)

### Design Decisions Evident in Code
- **Idempotency & Conflict Resolution:** Both `ingest.py` and `transform.py` utilize PostgreSQL's `ON CONFLICT` constraints. `ingest.py` uses `ON CONFLICT DO NOTHING` to prevent duplicate raw records if re-run. `transform.py` uses `ON CONFLICT DO UPDATE` to safely overwrite existing analytics data with fresh calculations.
- **Data Quality Imputation:** In `ingest.py`, if the market was open but `volume == 0`, it flags the `data_status` as `MARKET_HALT`. If a row is entirely missing, it forward-fills the last known close price and flags it as `IMPUTED_API_OUTAGE`. This prevents the UI from drawing misleading flat lines.
- **Anomaly Tracking:** `ingest.py` tracks if a stock's price jumps or drops by >20% in a single day and logs a `WARNING` to `pipeline_logs` without failing the pipeline, accommodating legitimate events like stock splits.

## 3. Setup & How to Run It

### Prerequisites
- Python 3.9+
- PostgreSQL installed and running locally on port 5432.

### 1. Environment Configuration
Create a `.env` file in the root directory (alongside the Python scripts) with the following keys. Update `DB_PASSWORD` to match your local Postgres instance:
```env
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=equity_db
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Database Initialization
Connect to your PostgreSQL server (e.g., via pgAdmin or `psql`) and create an empty database named `equity_db`.
Then, execute the schema files in this exact order:
1. Run `create_tables.sql`
2. Run `update_schema.sql` (Applies the V2 data status columns)

### 4. Pipeline Execution Order
To manually trigger the ETL process:
1. **Extract & Load:** Run `python ingest.py`
2. **Transform:** Run `python transform.py`
3. **Serve:** Run `streamlit run app.py`

## 4. Current Functionality

The codebase currently successfully implements:
- **Multi-Ticker Ingestion:** Iterates through `["INFY.NS", "TECHM.NS", "WIPRO.NS", "HCLTECH.NS"]` and pulls the last 30 days of market data via `yfinance`.
- **SQL-Based Math:** `transform.py` executes complex mathematical derivations (like `(net_income / NULLIF(total_revenue, 0)) * 100 as net_profit_margin_pct`) directly in the PostgreSQL warehouse rather than in memory.
- **UI Data Quality Alerts:** The Streamlit dashboard (`app.py`) dynamically reads the `data_status` column and renders a visual warning banner if the trader is viewing imputed or halted data.
- **Sector Benchmarking:** The dashboard dynamically groups and averages the 4 tickers into a "Sector Index", plotting it as a dashed baseline against individual stock performance.
- **Live Sync Status:** The dashboard queries `pipeline_logs` to display exactly how long ago the pipeline succeeded (e.g., "Synced 2 hours ago"), utilizing a glowing CSS status dot.
- **Sparklines & Deltas:** The UI dynamically calculates day-over-day `%` change for the Close Price and plots static Plotly sparklines inside custom CSS metric cards.

## 5. Known Limitations / Future Enhancements

Based on the current codebase, the following limitations exist:
- **No Automated Schema Drift Detection:** The pipeline implicitly trusts the JSON structure returned by `yfinance`. There is no contract validation (like Pydantic or Great Expectations) to fail gracefully if the API suddenly renames a key like `trailingPE`.
- **Manual Execution (Pending Docker/Airflow):** The pipeline currently requires manual execution of the Python scripts. While an `airflow_execution_guide.md` exists outlining the DAG code (`equity_pipeline_dag.py`) and Docker requirements, it is not yet fully integrated into a running container environment in this repository.
- **Secrets Management:** The Streamlit UI utilizes standard `os.getenv` via `.env` rather than Streamlit's native `st.secrets` manager, which would need refactoring before deploying to Streamlit Community Cloud.

## 6. Tech Stack

Derived directly from `requirements.txt` and import statements:
- **Core Language:** Python
- **Orchestration / Architecture:** Apache Airflow (DAG designed in `airflow_execution_guide.md`)
- **Data Warehouse:** PostgreSQL (connected via `psycopg2-binary` and `SQLAlchemy`)
- **Data Manipulation:** `pandas`
- **External API:** `yfinance`
- **Frontend / Serving:** `streamlit`
- **Visualization:** `plotly` (`plotly.graph_objects`)
- **Configuration:** `python-dotenv`
