import os, psycopg2
from datetime import date

def get_db():
    return psycopg2.connect(host="localhost",port="5432",dbname="options_trading",user="timtruong",password="")

def q(cursor,sql):
    cursor.execute(sql)
    cols=[d[0] for d in cursor.description]
    return [dict(zip(cols,r)) for r in cursor.fetchall()]

def header(t):
    print("\n"+"="*55+f"\n  {t}\n"+"="*55)

today=date.today()
conn=get_db()
cur=conn.cursor()

print(f"\nSPY SILVER BULLET BRIEFING - {today.strftime('%A %B %d %Y')}")
print("Entry window: 10:00am-11:00am EST")

rows=q(cur,"SELECT MAX(snapshot_date) as d,COUNT(*) as n FROM options_chain WHERE ticker='SPY'")
if rows[0]['d']!=today:
    print(f"\nWARNING: Data from {rows[0]['d']} - run fetch script first!")
else:
    print(f"\nData fresh - {rows[0]['n']} contracts loaded")

header("KEY LEVELS")
calls=q(cur,f"SELECT strike_price,volume,bid,ask,implied_volatility FROM options_chain WHERE ticker='SPY' AND option_type='C' AND snapshot_date='{today}' AND volume>0 ORDER BY volume DESC LIMIT 5")
puts=q(cur,f"SELECT strike_price,volume,bid,ask,implied_volatility FROM options_chain WHERE ticker='SPY' AND option_type='P' AND snapshot_date='{today}' AND volume>0 ORDER BY volume DESC LIMIT 5")

print("\nTOP CALLS (resistance):")
for r in calls:
    print(f"  ${r['strike_price']} | vol:{r['volume']:,} | ${r['bid']}/{r['ask']} | IV:{float(r['implied_volatility'])*100:.1f}%")
print("\nTOP PUTS (support):")
for r in puts:
    print(f"  ${r['strike_price']} | vol:{r['volume']:,} | ${r['bid']}/{r['ask']} | IV:{float(r['implied_volatility'])*100:.1f}%")

if calls and puts:
    c=float(calls[0]['strike_price'])
    p=float(puts[0]['strike_price'])
    header("SILVER BULLET SETUP")
    print(f"\n  BATTLEGROUND: ${(c+p)/2:.2f}")
    print(f"  Resistance: ${c} | Support: ${p}")
    print(f"\n  LONG setup: SPY sweeps below ${p} then reverses -> target ${c}")
    print(f"  SHORT setup: SPY sweeps above ${c} then reverses -> target ${p}")

header("REMINDERS")
print("  1. PAPER TRADE ONLY - 20+ setups before real money")
print("  2. 10-11am EST window only")
print("  3. Wait for liquidity sweep THEN FVG entry")
print("  4. No setup = no trade\n")

cur.close()
conn.close()
