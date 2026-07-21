import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# Database connection
db_url = URL.create(
    drivername="postgresql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    database=os.getenv("DB_NAME")
)
engine = create_engine(db_url)

def log_to_db(task_name, status, records_processed, error_message=""):
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

def run_transformations():
    logging.info("Starting Transformation Pipeline...")
    has_errors = False
    total_records = 0
    
    try:
        # 1. Read Data
        # We now pull data_status along with our prices
        prices_query = "SELECT date, ticker, close as close_price, data_status FROM raw_prices ORDER BY ticker, date"
        
        # We pull the latest financial record per ticker, and calculate the margin in SQL!
        fin_query = """
            SELECT ticker, trailing_pe as pe_ratio, 
                   (net_income / NULLIF(total_revenue, 0)) * 100 as net_profit_margin_pct
            FROM (
                SELECT *, ROW_NUMBER() OVER(PARTITION BY ticker ORDER BY fetch_date DESC) as rn 
                FROM raw_financials
            ) sub WHERE rn = 1
        """
        
        df_prices = pd.read_sql(prices_query, con=engine)
        df_fin = pd.read_sql(fin_query, con=engine)
        
        if df_prices.empty or df_fin.empty:
            msg = "Transformation skipped: Source tables are empty."
            logging.warning(msg)
            log_to_db("transform_analytics", "WARNING", 0, msg)
            return
            
        # 2. Calculate Rolling Averages (Business Logic in Pandas)
        df_prices.sort_values(by=['ticker', 'date'], inplace=True)
        # Calculate 7-day rolling average (min_periods=1 ensures we get averages even for the first few days)
        df_prices['rolling_7d_avg'] = df_prices.groupby('ticker')['close_price'].transform(lambda x: x.rolling(window=7, min_periods=1).mean())
        
        # 3. Join Prices with Financials
        df_analytics = pd.merge(df_prices, df_fin, on='ticker', how='left')
        
        # 4. Upsert into analytics_summary (Idempotency)
        # We convert the dataframe to a list of dictionaries for SQLAlchemy bulk insert
        records_to_insert = df_analytics.to_dict('records')
        
        with engine.begin() as conn:
            upsert_query = text("""
                INSERT INTO analytics_summary (date, ticker, close_price, rolling_7d_avg, net_profit_margin_pct, pe_ratio, data_status)
                VALUES (:date, :ticker, :close_price, :rolling_7d_avg, :net_profit_margin_pct, :pe_ratio, :data_status)
                ON CONFLICT (date, ticker) DO UPDATE 
                SET close_price = EXCLUDED.close_price,
                    rolling_7d_avg = EXCLUDED.rolling_7d_avg,
                    net_profit_margin_pct = EXCLUDED.net_profit_margin_pct,
                    pe_ratio = EXCLUDED.pe_ratio,
                    data_status = EXCLUDED.data_status;
            """)
            conn.execute(upsert_query, records_to_insert)
            
        total_records = len(records_to_insert)
        logging.info(f"Successfully transformed and upserted {total_records} rows into analytics_summary.")
        
    except Exception as e:
        error_msg = f"Transformation failed: {e}"
        logging.error(error_msg)
        log_to_db("transform_analytics", "FAILED", 0, error_msg)
        has_errors = True

    final_status = "WARNING" if has_errors else "SUCCESS"
    log_to_db("transformation_pipeline", final_status, total_records, "Completed transformations.")

if __name__ == "__main__":
    run_transformations()
