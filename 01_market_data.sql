-- =============================================================
-- 01_market_data.sql
-- Daily price snapshots for underlying stocks/ETFs
-- Learning note: this is your "source of truth" for price history
-- =============================================================

CREATE TABLE IF NOT EXISTS market_data (
    id              SERIAL PRIMARY KEY,          -- auto-incrementing unique row ID
    ticker          VARCHAR(10)  NOT NULL,       -- e.g. 'SPY', 'AAPL', 'QQQ'
    trade_date      DATE         NOT NULL,       -- the market date
    open_price      NUMERIC(10,4),               -- opening price
    high_price      NUMERIC(10,4),               -- daily high
    low_price       NUMERIC(10,4),               -- daily low
    close_price     NUMERIC(10,4) NOT NULL,      -- closing price
    volume          BIGINT,                      -- shares traded
    vix             NUMERIC(6,2),                -- VIX on that day (fear index)
    created_at      TIMESTAMPTZ DEFAULT NOW()    -- when we inserted this row
);

-- Index for fast lookups by ticker + date (you'll query this constantly)
CREATE INDEX IF NOT EXISTS idx_market_data_ticker_date
    ON market_data (ticker, trade_date DESC);

-- Prevent duplicate entries for same ticker/date
CREATE UNIQUE INDEX IF NOT EXISTS uq_market_data_ticker_date
    ON market_data (ticker, trade_date);

-- =============================================================
-- SQL LESSON: What is an INDEX?
-- Without an index, every query scans every row (slow).
-- An index is like a book's table of contents — finds rows fast.
-- Rule of thumb: index columns you filter or ORDER BY frequently.
-- =============================================================
