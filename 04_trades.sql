-- =============================================================
-- 04_trades.sql
-- Complete closed trade history — the backtester reads this
-- =============================================================

CREATE TABLE IF NOT EXISTS trades (
    id                  SERIAL PRIMARY KEY,
    position_id         INTEGER REFERENCES positions(id),  -- links back to position
    ticker              VARCHAR(10)  NOT NULL,
    strategy_name       VARCHAR(50),
    option_type         CHAR(1)      NOT NULL CHECK (option_type IN ('C','P')),
    strike_price        NUMERIC(10,2) NOT NULL,
    expiration_date     DATE         NOT NULL,
    contracts           INTEGER      NOT NULL,
    entry_date          DATE         NOT NULL,
    exit_date           DATE         NOT NULL,
    entry_price         NUMERIC(10,4) NOT NULL,
    exit_price          NUMERIC(10,4) NOT NULL,
    -- Outcome
    realized_pnl        NUMERIC(12,4) GENERATED ALWAYS AS (
                            (exit_price - entry_price) * contracts * 100
                        ) STORED,
    win                 BOOLEAN GENERATED ALWAYS AS (
                            exit_price > entry_price
                        ) STORED,
    days_held           INTEGER GENERATED ALWAYS AS (
                            exit_date - entry_date
                        ) STORED,
    exit_reason         VARCHAR(50),  -- 'target hit', 'stop loss', 'expired', 'manual'
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades (strategy_name, entry_date DESC);
CREATE INDEX IF NOT EXISTS idx_trades_ticker    ON trades (ticker, entry_date DESC);

-- =============================================================
-- 05_strategies.sql (appended here for simplicity)
-- Stores Silver Bullet ICT setups and scan rules
-- =============================================================

CREATE TABLE IF NOT EXISTS strategies (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,   -- e.g. 'Silver Bullet AM Session'
    description     TEXT,
    entry_window_start  TIME,                -- e.g. '10:00' AM session
    entry_window_end    TIME,                -- e.g. '11:00'
    rules           JSONB,                   -- flexible storage for strategy rules
    active          BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Pre-load Silver Bullet strategy
INSERT INTO strategies (name, description, entry_window_start, entry_window_end, rules)
VALUES (
    'Silver Bullet ICT',
    'ICT Silver Bullet strategy using Fair Value Gaps and liquidity sweeps',
    '10:00', '11:00',
    '{
        "session": "AM",
        "concept": "Fair Value Gap",
        "requires_liquidity_sweep": true,
        "entry_on": "FVG retest",
        "notes": "Also valid 14:00-15:00 PM session"
    }'::jsonb
);

-- =============================================================
-- SQL LESSON: REFERENCES (Foreign Key)
-- position_id INTEGER REFERENCES positions(id) means every
-- trade MUST link to a valid position. The DB enforces this —
-- you can't insert a trade for a position that doesn't exist.
-- This is called "referential integrity."
--
-- JSONB: PostgreSQL's JSON column type. Great for flexible,
-- structured data that varies per strategy (rules differ per setup).
-- You can query inside it: rules->>'session' = 'AM'
-- =============================================================
