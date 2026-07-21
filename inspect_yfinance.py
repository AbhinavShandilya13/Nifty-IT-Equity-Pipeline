import yfinance as yf
import pandas as pd

tickers = ['INFY.NS', 'HCLTECH.NS', 'TECHM.NS', 'WIPRO.NS']

for ticker_symbol in tickers:
    print(f"\n{'='*40}")
    print(f"Inspecting: {ticker_symbol}")
    print(f"{'='*40}")
    
    ticker = yf.Ticker(ticker_symbol)
    
    # 1. Check History Columns
    print("--- History Data (Last 5 days) ---")
    try:
        hist = ticker.history(period="5d")
        print(f"Columns: {list(hist.columns)}")
    except Exception as e:
        print(f"Error fetching history: {e}")

    # 2. Check Info Keys (These are notoriously inconsistent)
    print("\n--- Info Data (Checking our target metrics) ---")
    try:
        info = ticker.info
        # We need PE ratio, Revenue, and Net Income to calculate margins
        target_keys = ['trailingPE', 'totalRevenue', 'netIncomeToCommon']
        for key in target_keys:
            val = info.get(key, "MISSING")
            print(f"{key}: {val}")
    except Exception as e:
        print(f"Error fetching info: {e}")
    
    # 3. Check Financials DataFrame
    print("\n--- Financials Data ---")
    try:
        fin = ticker.financials
        if not fin.empty:
            if 'Total Revenue' in fin.index and 'Net Income' in fin.index:
                print("SUCCESS: Found 'Total Revenue' and 'Net Income' in financials table.")
            else:
                print("WARNING: Missing target financial rows in financials table!")
        else:
            print("WARNING: Financials dataframe is entirely empty!")
    except Exception as e:
        print(f"Error fetching financials: {e}")

print("\nDone inspecting.")
