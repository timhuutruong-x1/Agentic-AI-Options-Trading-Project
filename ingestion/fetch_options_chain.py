"""
ingestion/fetch_options_chain.py

Fetches options chain data from Polygon.io and stores it in PostgreSQL.
Run this daily (or on demand) to keep your database fresh.

Learning note: this is a simple ETL script —
  Extract  → pull data from API
  Transform → clean and reshape it
  Load      → insert into PostgreSQL
"""

import os
import requests
import psycopg2
from datetime import date
from dotenv import load_dotenv

load_dotenv()  # reads your .env file


# ── Database connection ───────────────────────────────────────────
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


# ── Fetch from Polygon.io ─────────────────────────────────────────
def fetch_options_chain(ticker: str) -> list[dict]:
    """
    Pulls the full options chain for a ticker from Polygon.io.
    Free tier returns delayed data — fine for learning.
    """
    api_key = os.getenv("POLYGON_API_KEY")
    url = f"https://api.polygon.io/v3/snapshot/options/{ticker}"
    params = {
        "apiKey": api_key,
        "limit": 250,
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    return data.get("results", [])


# ── Insert into PostgreSQL ────────────────────────────────────────
def save_options_chain(ticker: str, contracts: list[dict]):
    """
    Inserts each option contract into the options_chain table.
    ON CONFLICT DO NOTHING skips duplicates if you run it twice.
    """
    today = date.today()
    conn = get_db_connection()
    cursor = conn.cursor()

    inserted = 0
    for c in contracts:
        details = c.get("details", {})
        greeks  = c.get("greeks", {})
        day     = c.get("day", {})

        cursor.execute("""
            INSERT INTO options_chain (
                ticker, snapshot_date, expiration_date, strike_price,
                option_type, bid, ask, last_price, volume, open_interest,
                implied_volatility, delta, gamma, theta, vega
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT DO NOTHING
        """, (
            ticker,
            today,
            details.get("expiration_date"),
            details.get("strike_price"),
            details.get("contract_type", "C")[0].upper(),  # 'call' → 'C'
            c.get("last_quote", {}).get("bid"),
            c.get("last_quote", {}).get("ask"),
            day.get("close"),
            day.get("volume"),
            c.get("open_interest"),
            c.get("implied_volatility"),
            greeks.get("delta"),
            greeks.get("gamma"),
            greeks.get("theta"),
            greeks.get("vega"),
        ))
        inserted += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"✓ Saved {inserted} contracts for {ticker}")


# ── Main ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Start with liquid ETFs — great for learning Silver Bullet
    tickers = ["SPY", "QQQ", "IWM"]

    for ticker in tickers:
        print(f"Fetching {ticker}...")
        contracts = fetch_options_chain(ticker)
        save_options_chain(ticker, contracts)
