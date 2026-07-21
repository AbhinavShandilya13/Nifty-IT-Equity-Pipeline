import os
import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv
import logging
from datetime import datetime

# Configure standard python logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# Database connection (using URL.create to handle special characters in passwords)
db_url = URL.create(
    drivername="postgresql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME
)
engine = create_engine(db_url)

TICKERS = ['INFY.NS', 'HCLTECH.NS', 'TECHM.NS', 'WIPRO.NS']

def log_to_db(task_name, status, records_processed, error_message=""):
    """Writes a log entry to the pipeline_logs table in Postgres."""
    try:
        with engine.begin() as conn:
            query = text("""
                INSERT INTO pipeline_logs (task_name, status, records_processed, error_message)
                VALUES (:task_name, :status, :records_processed, :error_message)
            """)
            conn.execute(query, {
                "task_name": task_name,
                "status": status,
                "records_processed": records_processed,
                "error_message": error_message
            })
    except Exception as e:
        logging.error(f"Failed to write log to DB: {e}")

def fetch_and_ingest_prices():
    total_records = 0
    has_errors = False
    
    for ticker_symbol in TICKERS:
        logging.info(f"Fetching history for {ticker_symbol}...")
        ticker = yf.Ticker(ticker_symbol)
        
        try:
            # Fetch 1 month of data to get a good baseline
            df = ticker.history(period="1mo")
            
            # DQ Check 1: Zero Rows
            if df.empty:
                msg = f"WARNING: {ticker_symbol} returned 0 rows."
                logging.warning(msg)
                log_to_db(f"ingest_{ticker_symbol}", "WARNING", 0, msg)
                continue
                
            df.reset_index(inplace=True)
            
            # Standardize column names
            df.rename(columns={
                'Date': 'date', 'Open': 'open', 'High': 'high', 
                'Low': 'low', 'Close': 'close', 'Volume': 'volume'
            }, inplace=True)
            
            df['ticker'] = ticker_symbol
            
            # We only need the date part, not timezone info
            df['date'] = pd.to_datetime(df['date']).dt.date
            
            # --- V2 DATA QUALITY: IMPUTATION & STATUS ---
            # Create a complete date range to catch silently dropped days
            idx = pd.date_range(df['date'].min(), df['date'].max())
            df_reindexed = df.set_index('date').reindex(idx.date)
            
            # Track what was missing before we fill it
            df_reindexed['is_missing_close'] = df_reindexed['close'].isna()
            
            # Forward fill the missing close prices
            df_reindexed['close'] = df_reindexed['close'].ffill()
            
            # Fill other numerical columns (like volume) with 0 for missing days
            df_reindexed['volume'] = df_reindexed['volume'].fillna(0)
            
            # Assign data_status based on context
            df_reindexed['data_status'] = 'ACTUAL'
            # If the market was open but volume was exactly 0, it's a trading halt
            df_reindexed.loc[df_reindexed['volume'] == 0, 'data_status'] = 'MARKET_HALT'
            # If the row was completely missing from the API, it's an outage
            df_reindexed.loc[df_reindexed['is_missing_close'], 'data_status'] = 'IMPUTED_API_OUTAGE'
            
            df_reindexed['ticker'] = ticker_symbol
            df_reindexed.reset_index(names='date', inplace=True)
            df = df_reindexed.drop(columns=['is_missing_close'])
            # --------------------------------------------

            # DQ Check 3: Flag Anomalies (>20% jump)
            df['prev_close'] = df['close'].shift(1)
            df['pct_change'] = abs((df['close'] - df['prev_close']) / df['prev_close']) * 100
            
            anomalies = df[df['pct_change'] > 20.0]
            if not anomalies.empty:
                for _, row in anomalies.iterrows():
                    anomaly_msg = f"ANOMALY DETECTED: {ticker_symbol} moved {row['pct_change']:.2f}% on {row['date']} (Possible split/bonus)."
                    logging.warning(anomaly_msg)
                    # We log it, but do NOT block the insert (as per the Notion Plan Rule)
                    log_to_db(f"dq_anomaly_{ticker_symbol}", "WARNING", 1, anomaly_msg)

            # Prepare for DB insert
            df_to_insert = df[['date', 'ticker', 'open', 'high', 'low', 'close', 'volume', 'data_status']]
            
            # Insert into Postgres using a temporary table for UPSERT logic
            with engine.begin() as conn:
                # 1. Write to a temp table
                df_to_insert.to_sql('temp_prices', con=conn, if_exists='replace', index=False)
                
                # 2. Insert on conflict do nothing
                insert_query = text("""
                    INSERT INTO raw_prices (date, ticker, open, high, low, close, volume, data_status)
                    SELECT date, ticker, open, high, low, close, volume, data_status FROM temp_prices
                    ON CONFLICT (date, ticker) DO NOTHING;
                """)
                conn.execute(insert_query)
                
            records_added = len(df_to_insert)
            total_records += records_added
            logging.info(f"Successfully ingested {records_added} price records for {ticker_symbol}")
            
        except Exception as e:
            error_msg = f"Error processing prices for {ticker_symbol}: {e}"
            logging.error(error_msg)
            log_to_db(f"ingest_prices_{ticker_symbol}", "FAILED", 0, error_msg)
            has_errors = True
            
    # Final logging
    final_status = "WARNING" if has_errors else "SUCCESS"
    log_to_db("ingestion_pipeline_prices", final_status, total_records, "Completed price ingestion.")

def fetch_and_ingest_financials():
    total_records = 0
    has_errors = False
    fetch_date = datetime.now().date()
    
    for ticker_symbol in TICKERS:
        logging.info(f"Fetching financials for {ticker_symbol}...")
        ticker = yf.Ticker(ticker_symbol)
        
        try:
            info = ticker.info
            fin = ticker.financials
            
            trailing_pe = info.get('trailingPE', None)
            
            total_revenue = None
            net_income = None
            if not fin.empty and 'Total Revenue' in fin.index and 'Net Income' in fin.index:
                total_revenue = float(fin.loc['Total Revenue'].iloc[0])
                net_income = float(fin.loc['Net Income'].iloc[0])
            
            if trailing_pe is None or total_revenue is None or net_income is None:
                logging.warning(f"Missing financial data for {ticker_symbol}")
            
            with engine.begin() as conn:
                insert_query = text("""
                    INSERT INTO raw_financials (fetch_date, ticker, trailing_pe, total_revenue, net_income)
                    VALUES (:fetch_date, :ticker, :trailing_pe, :total_revenue, :net_income)
                    ON CONFLICT (fetch_date, ticker) DO UPDATE 
                    SET trailing_pe = EXCLUDED.trailing_pe,
                        total_revenue = EXCLUDED.total_revenue,
                        net_income = EXCLUDED.net_income;
                """)
                conn.execute(insert_query, {
                    "fetch_date": fetch_date,
                    "ticker": ticker_symbol,
                    "trailing_pe": trailing_pe,
                    "total_revenue": total_revenue,
                    "net_income": net_income
                })
            
            total_records += 1
            logging.info(f"Successfully ingested financials for {ticker_symbol}")
            
        except Exception as e:
            error_msg = f"Error processing financials for {ticker_symbol}: {e}"
            logging.error(error_msg)
            log_to_db(f"ingest_financials_{ticker_symbol}", "FAILED", 0, error_msg)
            has_errors = True

    final_status = "WARNING" if has_errors else "SUCCESS"
    log_to_db("ingestion_pipeline_financials", final_status, total_records, "Completed financials ingestion.")

if __name__ == "__main__":
    logging.info("Starting Ingestion Pipeline...")
    fetch_and_ingest_prices()
    fetch_and_ingest_financials()
    logging.info("Ingestion Pipeline Complete.")
