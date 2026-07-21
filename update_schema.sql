-- Run this in pgAdmin Query Tool to upgrade your schema to V2

ALTER TABLE raw_prices ADD COLUMN IF NOT EXISTS data_status VARCHAR(50) DEFAULT 'ACTUAL';
ALTER TABLE analytics_summary ADD COLUMN IF NOT EXISTS data_status VARCHAR(50) DEFAULT 'ACTUAL';
