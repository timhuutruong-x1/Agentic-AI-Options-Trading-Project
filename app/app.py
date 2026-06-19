import os, psycopg2, yfinance as yf, json as jlib
from datetime import date
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)

def get_db():
    return psycopg2.connect(host="localhost",port="5432",dbname="options_trading",user="timtruong",password="")

def query(sql, params=None):
    conn=get_db(); cur=conn.cursor(); cur.execute(sql,params or ())
    cols=[d[0] for d in cur.description]
    rows=[dict(zip(cols,r)) for r in cur.fetchall()]
    cur.close(); conn.close(); return rows

def execute(sql, params=None):
    conn=get_db(); cur=conn.cursor(); cur.execute(sql,params or ())
    conn.commit(); cur.close(); conn.close()

@app.route("/")
def dashboard():
    today=date.today()
    top_calls=query(f"SELECT strike_price,volume,bid,ask FROM options_chain WHERE ticker='SPY' AND option_type='C' AND snapshot_date='{today}' AND volume>0 ORDER BY volume DESC LIMIT 5")
    top_puts=query(f"SELECT strike_price,volume,bid,ask FROM options_chain WHERE ticker='SPY' AND option_type='P' AND snapshot_date='{today}' AND volume>0 ORDER BY volume DESC LIMIT 5")
    battleground=round((float(top_calls[0]["strike_price"])+float(top_puts[0]["strike_price"]))/2,2) if top_calls and top_puts else None
    info=query("SELECT MAX(snapshot_date) as last,COUNT(*) as n FROM options_chain WHERE ticker='SPY'")
    has_j=query("SELECT to_regclass('trade_journal') as t")[0]["t"]
    jstats=query("SELECT COUNT(*) as total,SUM(CASE WHEN sweep_occurred THEN 1 ELSE 0 END) as sweeps,SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) as wins,SUM(CASE WHEN result IN ('win','loss','breakeven') THEN 1 ELSE 0 END) as trades,COALESCE(SUM(pnl_points),0) as total_pnl FROM trade_journal") if has_j else [{}]
    recent=query("SELECT journal_date,sweep_occurred,fvg_formed,result,pnl_points,notes FROM trade_journal ORDER BY journal_date DESC LIMIT 5") if has_j else []
    return render_template("dashboard.html",today=today,top_calls=top_calls,top_puts=top_puts,battleground=battleground,last_fetch=info[0]["last"],contract_count=info[0]["n"],stats=jstats[0] if jstats else {},recent_journal=recent)

@app.route("/briefing")
def briefing():
    today=date.today()
    top_calls=query(f"SELECT strike_price,volume,bid,ask,implied_volatility FROM options_chain WHERE ticker='SPY' AND option_type='C' AND snapshot_date='{today}' AND volume>0 ORDER BY volume DESC LIMIT 8")
    top_puts=query(f"SELECT strike_price,volume,bid,ask,implied_volatility FROM options_chain WHERE ticker='SPY' AND option_type='P' AND snapshot_date='{today}' AND volume>0 ORDER BY volume DESC LIMIT 8")
    battleground=round((float(top_calls[0]["strike_price"])+float(top_puts[0]["strike_price"]))/2,2) if top_calls and top_puts else None
    iv_row=query(f"SELECT ROUND(AVG(implied_volatility)*100,1) as avg_iv FROM options_chain WHERE ticker='SPY' AND snapshot_date='{today}' AND implied_volatility>0 AND implied_volatility<2")
    iv=float(iv_row[0]["avg_iv"]) if iv_row and iv_row[0]["avg_iv"] else None
    mood=("Calm","Smaller moves — tighter stops","success") if iv and iv<15 else ("Moderate","Normal conditions","info") if iv and iv<25 else ("Elevated","Bigger moves — reduce size","warning") if iv and iv<40 else ("High IV","Very volatile","danger") if iv else None
    return render_template("briefing.html",today=today,top_calls=top_calls,top_puts=top_puts,battleground=battleground,iv=iv,mood=mood)

@app.route("/refresh",methods=["POST"])
def refresh():
    stock=yf.Ticker("SPY"); today=date.today()
    conn=get_db(); cur=conn.cursor()
    for expiry in (stock.options or [])[:4]:
        chain=stock.option_chain(expiry)
        for opt_type,df in [("C",chain.calls),("P",chain.puts)]:
            for _,row in df.iterrows():
                try: vol=int(float(row.get("volume") or 0)) if str(row.get("volume"))!="nan" else 0
                except: vol=0
                try: oi=int(float(row.get("openInterest") or 0)) if str(row.get("openInterest"))!="nan" else 0
                except: oi=0
                cur.execute("INSERT INTO options_chain(ticker,snapshot_date,expiration_date,strike_price,option_type,bid,ask,last_price,volume,open_interest,implied_volatility,delta,gamma,theta,vega) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",("SPY",today,expiry,float(row.get("strike",0)),opt_type,float(row.get("bid",0) or 0),float(row.get("ask",0) or 0),float(row.get("lastPrice",0) or 0),vol,oi,float(row.get("impliedVolatility",0) or 0),None,None,None,None))
    conn.commit(); cur.close(); conn.close()
    return redirect(url_for("briefing"))

@app.route("/journal")
def journal():
    execute("""CREATE TABLE IF NOT EXISTS trade_journal(id SERIAL PRIMARY KEY,journal_date DATE DEFAULT CURRENT_DATE,ticker VARCHAR(10) DEFAULT 'SPY',call_level NUMERIC(10,2),put_level NUMERIC(10,2),battleground NUMERIC(10,2),sweep_occurred BOOLEAN DEFAULT false,sweep_direction VARCHAR(10),sweep_price NUMERIC(10,2),fvg_formed BOOLEAN DEFAULT false,fvg_low NUMERIC(10,2),fvg_high NUMERIC(10,2),would_trade BOOLEAN DEFAULT false,trade_direction VARCHAR(10),entry_price NUMERIC(10,2),target_price NUMERIC(10,2),stop_price NUMERIC(10,2),result VARCHAR(20),pnl_points NUMERIC(8,2),notes TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
    entries=query("SELECT * FROM trade_journal ORDER BY journal_date DESC")
    stats=query("SELECT COUNT(*) as total,SUM(CASE WHEN sweep_occurred THEN 1 ELSE 0 END) as sweeps,SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) as wins,SUM(CASE WHEN result IN ('win','loss','breakeven') THEN 1 ELSE 0 END) as trades,COALESCE(SUM(pnl_points),0) as total_pnl FROM trade_journal")
    return render_template("journal.html",entries=entries,stats=stats[0] if stats else {})

@app.route("/journal/add",methods=["GET"])
def journal_add():
    return render_template("journal_add.html",today=date.today())

@app.route("/journal/add",methods=["POST"])
def add_journal():
    f=request.form
    cl=float(f.get("call_level") or 0); pl=float(f.get("put_level") or 0)
    execute("INSERT INTO trade_journal(journal_date,call_level,put_level,battleground,sweep_occurred,sweep_direction,sweep_price,fvg_formed,fvg_low,fvg_high,would_trade,trade_direction,entry_price,target_price,stop_price,result,pnl_points,notes) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(f.get("journal_date") or date.today(),cl,pl,round((cl+pl)/2,2),f.get("sweep")=="yes",f.get("sweep_direction") or None,float(f.get("sweep_price")) if f.get("sweep_price") else None,f.get("fvg")=="yes",float(f.get("fvg_low")) if f.get("fvg_low") else None,float(f.get("fvg_high")) if f.get("fvg_high") else None,f.get("would_trade")=="yes",f.get("trade_direction") or None,float(f.get("entry_price")) if f.get("entry_price") else None,float(f.get("target_price")) if f.get("target_price") else None,float(f.get("stop_price")) if f.get("stop_price") else None,f.get("result") or None,float(f.get("pnl_points")) if f.get("pnl_points") else None,f.get("notes") or None))
    return redirect(url_for("journal"))

@app.route("/journal/delete/<int:id>",methods=["POST"])
def delete_journal(id):
    execute("DELETE FROM trade_journal WHERE id=%s",(id,))
    return redirect(url_for("journal"))

@app.route("/chain")
def chain():
    today=date.today()
    opt_type=request.args.get("type","C")
    expiry=request.args.get("expiry","")
    expiries=query(f"SELECT DISTINCT expiration_date FROM options_chain WHERE ticker='SPY' AND snapshot_date='{today}' ORDER BY expiration_date")
    if not expiry and expiries: expiry=str(expiries[0]["expiration_date"])
    contracts=query(f"SELECT strike_price,bid,ask,mid_price,last_price,volume,open_interest,implied_volatility,days_to_expiry FROM options_chain WHERE ticker='SPY' AND option_type='{opt_type}' AND snapshot_date='{today}' AND expiration_date='{expiry}' ORDER BY strike_price") if expiry else []
    return render_template("chain.html",today=today,expiries=expiries,selected_expiry=expiry,opt_type=opt_type,contracts=contracts)

@app.route("/confluence")
def confluence():
    tf=request.args.get("tf","5m")
    today=date.today()
    calls=query(f"SELECT strike_price FROM options_chain WHERE ticker='SPY' AND option_type='C' AND snapshot_date='{today}' AND volume>0 ORDER BY volume DESC LIMIT 1")
    puts=query(f"SELECT strike_price FROM options_chain WHERE ticker='SPY' AND option_type='P' AND snapshot_date='{today}' AND volume>0 ORDER BY volume DESC LIMIT 1")
    battleground=round((float(calls[0]["strike_price"])+float(puts[0]["strike_price"]))/2,2) if calls and puts else None
    spy=yf.Ticker("SPY")
    df=spy.history(period="1d",interval=tf)
    candles=[]
    if not df.empty:
        for ts,row in df.iterrows():
            try: t=int(ts.timestamp())
            except: continue
            candles.append({"time":t,"open":round(float(row["Open"]),2),"high":round(float(row["High"]),2),"low":round(float(row["Low"]),2),"close":round(float(row["Close"]),2)})
    fvgs,swing_highs,swing_lows,markers=[],[],[],[]
    for i in range(2,len(candles)):
        c0,c1,c2=candles[i-2],candles[i-1],candles[i]
        if c0["high"]<c2["low"] and (c2["low"]-c0["high"])>0.03:
            fvgs.append({"type":"bullish","time":c1["time"],"top":c2["low"],"bottom":c0["high"]})
        elif c0["low"]>c2["high"] and (c0["low"]-c2["high"])>0.03:
            fvgs.append({"type":"bearish","time":c1["time"],"top":c0["low"],"bottom":c2["high"]})
    for i in range(2,len(candles)-2):
        c=candles[i]
        if all(c["high"]>=candles[j]["high"] for j in [i-2,i-1,i+1,i+2]): swing_highs.append((c["time"],c["high"]))
        if all(c["low"]<=candles[j]["low"] for j in [i-2,i-1,i+1,i+2]): swing_lows.append((c["time"],c["low"]))
    for i in range(4,len(candles)):
        c=candles[i]
        for t,p in swing_highs[-5:]:
            if t<c["time"] and c["high"]>p and c["close"]<p:
                markers.append({"time":c["time"],"position":"aboveBar","color":"#D85A30","shape":"arrowDown","text":"Sweep"}); break
        for t,p in swing_lows[-5:]:
            if t<c["time"] and c["low"]<p and c["close"]>p:
                markers.append({"time":c["time"],"position":"belowBar","color":"#1D9E75","shape":"arrowUp","text":"Sweep"}); break
    last_sh=swing_highs[-1] if swing_highs else None
    last_sl=swing_lows[-1] if swing_lows else None
    for i in range(1,len(candles)):
        c=candles[i]
        if last_sh and c["time"]>last_sh[0] and c["close"]>last_sh[1]:
            markers.append({"time":c["time"],"position":"aboveBar","color":"#1D9E75","shape":"circle","text":"BOS"}); last_sh=None
        if last_sl and c["time"]>last_sl[0] and c["close"]<last_sl[1]:
            markers.append({"time":c["time"],"position":"belowBar","color":"#D85A30","shape":"circle","text":"BOS"}); last_sl=None
    markers.sort(key=lambda x:x["time"])
    bull_fvg=sum(1 for f in fvgs if f["type"]=="bullish")
    bear_fvg=sum(1 for f in fvgs if f["type"]=="bearish")
    return render_template("confluence.html",candles=jlib.dumps(candles),fvgs=jlib.dumps(fvgs[-10:]),markers=jlib.dumps(markers),battleground=battleground,tf=tf,today=today,fvg_count=len(fvgs),bull_fvg=bull_fvg,bear_fvg=bear_fvg)

if __name__=="__main__":
    print("\nSilver Bullet Dashboard -> http://localhost:8080\n")
    app.run(debug=True,host="0.0.0.0",port=8080)
