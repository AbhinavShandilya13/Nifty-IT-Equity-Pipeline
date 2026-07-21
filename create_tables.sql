-- Phase 1: PostgreSQL Schema Setup for Equity Research Pipeline

CREATE TABLE IF NOT EXISTS raw_prices (
    date DATE,
    ticker VARCHAR(50),
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume BIGINT,
    PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS raw_financials (
    fetch_date DATE,
    ticker VARCHAR(50),
    trailing_pe NUMERIC,
    total_revenue NUMERIC,
    net_income NUMERIC,
    PRIMARY KEY (fetch_date, ticker)
);

CREATE TABLE IF NOT EXISTS analytics_summary (
    date DATE,
    ticker VARCHAR(50),
    close_price NUMERIC,
    rolling_7d_avg NUMERIC,
    net_profit_margin_pct NUMERIC,
    pe_ratio NUMERIC,
    PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS pipeline_logs (
    run_id SERIAL PRIMARY KEY,
    execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    task_name VARCHAR(100),
    status VARCHAR(50),
    records_processed INT,
    error_message TEXT
);
