-- =============================================================
-- 02_options_chain.sql
-- One row per option contract per day
-- Learning note: this is the heart of the whole project
-- =============================================================

CREATE TABLE IF NOT EXISTS options_chain (
    id                  SERIAL PRIMARY KEY,
    ticker              VARCHAR(10)  NOT NULL,       -- underlying stock e.g. 'SPY'
    snapshot_date       DATE         NOT NULL,       -- date this data was captured
    expiration_date     DATE         NOT NULL,       -- when the contract expires
    strike_price        NUMERIC(10,2) NOT NULL,      -- the strike price
    option_type         CHAR(1)      NOT NULL        -- 'C' for call, 'P' for put
                        CHECK (option_type IN ('C','P')),
    bid                 NUMERIC(10,4),               -- highest buyer price
    ask                 NUMERIC(10,4),               -- lowest seller price
    last_price          NUMERIC(10,4),               -- last traded price
    volume              INTEGER,                     -- contracts traded today
    open_interest       INTEGER,                     -- total open contracts
    implied_volatility  NUMERIC(8,4),                -- IV (key for options pricing)
    -- THE GREEKS (how the option price changes)
    delta               NUMERIC(8,6),                -- sensitivity to price move
    gamma               NUMERIC(8,6),                -- rate of delta change
    theta               NUMERIC(8,6),                -- daily time decay (usually negative)
    vega                NUMERIC(8,6),                -- sensitivity to IV change
    rho                 NUMERIC(8,6),                -- sensitivity to interest rates
    -- Calculated fields
    days_to_expiry      INTEGER GENERATED ALWAYS AS
                            (expiration_date - snapshot_date) STORED,
    mid_price           NUMERIC(10,4) GENERATED ALWAYS AS
                            ((bid + ask) / 2) STORED,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_options_ticker_date
    ON options_chain (ticker, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_options_expiry
    ON options_chain (expiration_date);

CREATE INDEX IF NOT EXISTS idx_options_type_strike
    ON options_chain (option_type, strike_price);

-- =============================================================
-- SQL LESSON: CHECK constraint
-- CHECK (option_type IN ('C','P')) means the database will
-- REJECT any insert that isn't 'C' or 'P'. This is data quality
-- enforcement at the database level — better than checking in code.
--
-- GENERATED ALWAYS AS: a computed column. days_to_expiry and
-- mid_price are calculated automatically — you never store them
-- manually, the DB keeps them in sync.
-- =============================================================
