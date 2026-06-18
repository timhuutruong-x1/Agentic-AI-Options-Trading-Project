"""
agent/trading_agent.py

AI-powered trading assistant using Claude.
Ask it anything about your positions, the market, or the Silver Bullet strategy.

Example questions:
  - "Which of my open positions have the most theta decay this week?"
  - "Find me SPY calls expiring in 7–14 days with IV above 20%"
  - "Explain how the Silver Bullet setup works for today's session"
"""

import os
import psycopg2
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ── Database helpers ──────────────────────────────────────────────
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def run_query(sql: str) -> list[dict]:
    """Run a SQL query and return results as a list of dicts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return rows


def get_portfolio_summary() -> str:
    """Pull open positions to give the AI context."""
    rows = run_query("""
        SELECT ticker, strategy_name, option_type, strike_price,
               expiration_date, contracts, entry_price,
               current_price, unrealized_pnl,
               (expiration_date - CURRENT_DATE) AS days_to_expiry
        FROM positions
        WHERE status = 'open'
        ORDER BY expiration_date
    """)
    if not rows:
        return "No open positions."
    lines = ["Open Positions:"]
    for r in rows:
        pnl = r["unrealized_pnl"] or 0
        lines.append(
            f"  {r['ticker']} {r['option_type']} ${r['strike_price']} "
            f"exp {r['expiration_date']} ({r['days_to_expiry']}d) "
            f"× {r['contracts']} contracts | P&L: ${pnl:+.2f}"
        )
    return "\n".join(lines)


def get_recent_options(ticker: str = "SPY", days_to_expiry_max: int = 21) -> str:
    """Pull recent options chain data for a ticker."""
    rows = run_query(f"""
        SELECT option_type, strike_price, expiration_date, days_to_expiry,
               bid, ask, mid_price, implied_volatility, delta, theta, volume
        FROM options_chain
        WHERE ticker = '{ticker}'
          AND snapshot_date = (SELECT MAX(snapshot_date) FROM options_chain WHERE ticker = '{ticker}')
          AND days_to_expiry BETWEEN 1 AND {days_to_expiry_max}
          AND volume > 100
        ORDER BY days_to_expiry, option_type, strike_price
        LIMIT 30
    """)
    if not rows:
        return f"No options data found for {ticker}."
    lines = [f"Recent {ticker} options chain (up to {days_to_expiry_max} DTE):"]
    for r in rows:
        lines.append(
            f"  {r['option_type']} ${r['strike_price']} exp {r['expiration_date']} "
            f"({r['days_to_expiry']}d) | mid ${r['mid_price']} "
            f"IV {r['implied_volatility']:.1%} Δ {r['delta']:.2f} θ {r['theta']:.4f}"
        )
    return "\n".join(lines)


# ── AI Agent ──────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are a knowledgeable options trading assistant helping a beginner learn
options trading through a real project. You have access to their live database
of positions and market data.

Your role:
1. Answer questions about their open positions clearly and simply
2. Explain options concepts (Greeks, IV, strategies) in plain English
3. Help them understand the Silver Bullet ICT strategy
4. Suggest trade ideas based on their options chain data
5. Never give direct financial advice — frame everything as educational

Silver Bullet ICT Strategy basics you know:
- Targets Fair Value Gaps (FVGs) formed after liquidity sweeps
- Primary entry window: 10:00–11:00 AM EST
- Secondary window: 2:00–3:00 PM EST
- Works best on liquid instruments: SPY, QQQ, NQ futures
- Entry: when price returns to fill the FVG after a liquidity sweep
- Stop: below/above the FVG
- Target: next liquidity level

Always explain your reasoning. When referencing numbers from the data,
explain what those numbers mean for a beginner.
"""


def ask_agent(question: str, ticker: str = "SPY") -> str:
    """Send a question to the AI agent with live portfolio context."""

    portfolio = get_portfolio_summary()
    options_data = get_recent_options(ticker)

    context = f"""
Current portfolio snapshot:
{portfolio}

{options_data}

User question: {question}
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}],
    )

    return response.content[0].text


# ── Interactive loop ──────────────────────────────────────────────
if __name__ == "__main__":
    print("Options Trading AI Agent")
    print("Type your question or 'quit' to exit\n")

    while True:
        question = input("You: ").strip()
        if question.lower() in ("quit", "exit", "q"):
            break
        if not question:
            continue
        print("\nAgent:", ask_agent(question), "\n")
