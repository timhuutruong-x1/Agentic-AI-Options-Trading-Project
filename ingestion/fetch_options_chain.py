"""
ingestion/fetch_options_chain.py
Fetches real options chain data from Yahoo Finance (free, no API key needed)
and stores it in PostgreSQL.
"""

import os
import yfinance as yf
import psycopg2
from datetime import date
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "options_trading"),
        user=os.getenv("DB_USER", "timtruong"),
        password=os.getenv("DB_PASSWORD", ""),
    )

def fetch_and_save(ticker: str):
    print(f"Fetching {ticker}...")
    stock = yf.Ticker(ticker)
    expirations = stock.options

    if not expirations:
        print(f"  No options found for {ticker}")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    total = 0

    for expiry in expirations[:4]:  # first 4 expiry dates to start
        chain = stock.option_chain(expiry)

        for opt_type, df in [("C", chain.calls), ("P", chain.puts)]:
            for _, row in df.iterrows():
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
                    date.today(),
                    expiry,
                    float(row.get("strike", 0)),
                    opt_type,
                    float(row.get("bid", 0) or 0),
                    float(row.get("ask", 0) or 0),
                    float(row.get("lastPrice", 0) or 0),
                    int(float(row.get("volume") or 0) if str(row.get("volume")) != "nan" else 0),
                    int(float(row.get("openInterest") or 0) if str(row.get("openInterest")) != "nan" else 0),
                    float(row.get("impliedVolatility", 0) or 0),
                    None, None, None, None  # Greeks not in yfinance free tier
                ))
                total += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"  Saved {total} contracts for {ticker}")

if __name__ == "__main__":
    for ticker in ["SPY", "QQQ", "IWM"]:
        fetch_and_save(ticker)
    print("\nDone! Run: psql -d options_trading -c \"SELECT COUNT(*) FROM options_chain;\"")
