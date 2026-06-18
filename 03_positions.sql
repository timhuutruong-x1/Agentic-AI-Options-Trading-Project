-- =============================================================
-- 03_positions.sql
-- Your open options positions (active trades)
-- =============================================================

CREATE TABLE IF NOT EXISTS positions (
    id                  SERIAL PRIMARY KEY,
    ticker              VARCHAR(10)  NOT NULL,
    strategy_name       VARCHAR(50),                 -- e.g. 'Silver Bullet', 'Covered Call'
    option_type         CHAR(1)      NOT NULL
                        CHECK (option_type IN ('C','P')),
    strike_price        NUMERIC(10,2) NOT NULL,
    expiration_date     DATE         NOT NULL,
    contracts           INTEGER      NOT NULL,        -- number of contracts (each = 100 shares)
    entry_price         NUMERIC(10,4) NOT NULL,       -- what you paid per contract
    entry_date          DATE         NOT NULL,
    current_price       NUMERIC(10,4),                -- updated by tracker
    status              VARCHAR(10)  DEFAULT 'open'
                        CHECK (status IN ('open','closed','expired')),
    notes               TEXT,                         -- your trade journal notes
    closed_at           TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    -- Calculated P&L (positive = profit)
    unrealized_pnl      NUMERIC(12,4) GENERATED ALWAYS AS (
                            (current_price - entry_price) * contracts * 100
                        ) STORED
);

CREATE INDEX IF NOT EXISTS idx_positions_status
    ON positions (status, expiration_date);

-- =============================================================
-- SQL LESSON: Why contracts * 100?
-- Each options contract controls 100 shares. So if you buy
-- 2 contracts at $3.50, you paid $3.50 × 2 × 100 = $700.
-- This multiplier is baked into the P&L calculation above.
-- =============================================================
