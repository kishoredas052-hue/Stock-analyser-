"""Roz market data banata hai -> data/market.json (GitHub Actions chalata hai)."""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import yfinance as yf

STOCKS = {  # symbol: sector
    "RELIANCE": "Energy", "TCS": "IT", "HDFCBANK": "Banks", "INFY": "IT", "ICICIBANK": "Banks",
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "SBIN": "Banks", "BHARTIARTL": "Telecom",
    "KOTAKBANK": "Banks", "LT": "Infra", "AXISBANK": "Banks", "ASIANPAINT": "Consumer",
    "MARUTI": "Auto", "SUNPHARMA": "Pharma", "TITAN": "Consumer", "BAJFINANCE": "Finance",
    "HCLTECH": "IT", "WIPRO": "IT", "ULTRACEMCO": "Cement", "NTPC": "Power", "ONGC": "Energy",
    "POWERGRID": "Power", "TATAMOTORS": "Auto", "TATASTEEL": "Metals", "M&M": "Auto",
    "ADANIENT": "Infra", "COALINDIA": "Metals", "TECHM": "IT", "NESTLEIND": "FMCG",
    "JSWSTEEL": "Metals", "INDUSINDBK": "Banks", "BAJAJFINSV": "Finance", "GRASIM": "Cement",
    "CIPLA": "Pharma", "DRREDDY": "Pharma", "EICHERMOT": "Auto", "HEROMOTOCO": "Auto",
    "BRITANNIA": "FMCG", "APOLLOHOSP": "Healthcare",
}
FINANCIAL = {"Banks", "Finance"}  # inme debt/equity ka check nahi lagta
INDICES = {"Nifty 50": "^NSEI", "Sensex": "^BSESN", "Bank Nifty": "^NSEBANK",
           "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "USD/INR": "INR=X",
           "Gold": "GC=F", "Crude Oil": "CL=F"}


def f(x, nd=2):
    try:
        x = float(x)
        return None if np.isnan(x) else round(x, nd)
    except Exception:
        return None


def add_indicators(df):
    df = df.copy()
    c = df["Close"]
    for n in (20, 50, 200):
        df[f"SMA{n}"] = c.rolling(n).mean()
    d = c.diff()
    g = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    df["RSI"] = 100 - 100 / (1 + g / l.replace(0, np.nan))
    e12, e26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    df["MACD"] = e12 - e26
    df["SIG"] = df["MACD"].ewm(span=9, adjust=False).mean()
    return df


def tech_score(df):
    x, p, pts = df.iloc[-1], df.iloc[-1]["Close"], 0
    pts += 1 if p > x["SMA50"] else -1
    if not np.isnan(x["SMA200"]):
        pts += 1 if p > x["SMA200"] else -1
        pts += 1 if x["SMA50"] > x["SMA200"] else -1
    pts += 1 if x["MACD"] > x["SIG"] else -1
    pts += 1 if x["RSI"] < 30 else -1 if x["RSI"] > 70 else 0
    v = ("Strong Buy" if pts >= 3 else "Buy" if pts >= 1 else "Neutral" if pts > -1
         else "Sell" if pts > -3 else "Strong Sell")
    return pts, v


def history(sym):
    for _ in range(3):
        try:
            df = yf.Ticker(sym).history(period="2y", auto_adjust=True)
            if df is not None and len(df) > 60:
                return df.dropna(subset=["Close"])
        except Exception:
            pass
        time.sleep(2)
    return None


def fundamentals(sym):
    try:
        return yf.Ticker(sym).info or {}
    except Exception:
        return {}


def fund_score(info, sector):
    checks = []
    pe, roe = info.get("trailingPE"), info.get("returnOnEquity")
    de, pm, rg = info.get("debtToEquity"), info.get("profitMargins"), info.get("revenueGrowth")
    if pe is not None: checks.append(0 < pe < 30)
    if roe is not None: checks.append(roe > 0.15)
    if de is not None and sector not in FINANCIAL: checks.append(de < 100)
    if pm is not None: checks.append(pm > 0.10)
    if rg is not None: checks.append(rg > 0.08)
    if not checks:
        return None
    return round(sum(checks) / len(checks) * 5, 1)


def analyze(sym, sector):
    df = history(sym + ".NS")
    if df is None:
        return None
    df = add_indicators(df)
    pts, verdict = tech_score(df)
    x, prev = df.iloc[-1], df.iloc[-2]
    info = fundamentals(sym + ".NS")
    time.sleep(0.4)
    fs = fund_score(info, sector)
    tech5 = (pts + 5) / 10 * 5
    combined = round(0.6 * tech5 + 0.4 * fs, 1) if fs is not None else round(tech5, 1)
    rating = "Strong" if combined >= 3.5 else "Watch" if combined >= 2.5 else "Weak"

    why = [("Trend upar" if x["Close"] > x["SMA50"] else "Trend neeche"),
           f"RSI {x['RSI']:.0f}" + (" (oversold)" if x["RSI"] < 30 else " (overbought)" if x["RSI"] > 70 else "")]
    if info.get("returnOnEquity") is not None: why.append(f"ROE {info['returnOnEquity'] * 100:.0f}%")
    if info.get("trailingPE") is not None: why.append(f"PE {info['trailingPE']:.0f}")
    return {
        "symbol": sym, "name": info.get("shortName") or sym, "sector": sector,
        "price": f(x["Close"]), "chg": f((x["Close"] / prev["Close"] - 1) * 100),
        "ret1m": f((x["Close"] / df["Close"].iloc[-22] - 1) * 100) if len(df) > 22 else None,
        "rsi": f(x["RSI"], 1), "tech_score": pts, "verdict": verdict,
        "fund": fs, "combined": combined, "rating": rating,
        "above200": bool(x["Close"] > x["SMA200"]) if not np.isnan(x["SMA200"]) else None,
        "pe": f(info.get("trailingPE"), 1), "roe": f((info.get("returnOnEquity") or 0) * 100, 1) if info.get("returnOnEquity") is not None else None,
        "reason": " • ".join(why),
    }


def index_row(name, tkr):
    try:
        h = yf.Ticker(tkr).history(period="7d")["Close"].dropna()
        return {"name": name, "value": f(h.iloc[-1]), "chg": f((h.iloc[-1] / h.iloc[-2] - 1) * 100)}
    except Exception:
        return None


def main():
    stocks = []
    for i, (sym, sec) in enumerate(STOCKS.items(), 1):
        r = analyze(sym, sec)
        print(f"[{i}/{len(STOCKS)}] {sym}: {'ok' if r else 'skip'}", flush=True)
        if r:
            stocks.append(r)
    if len(stocks) < 10:
        print("Bahut kam stocks ka data mila, purana data rakh rahe hain.")
        sys.exit(1)

    n = len(stocks)
    breadth = {
        "total": n,
        "advance": sum(1 for s in stocks if (s["chg"] or 0) > 0),
        "decline": sum(1 for s in stocks if (s["chg"] or 0) < 0),
        "bullish_pct": round(100 * sum(s["verdict"] in ("Buy", "Strong Buy") for s in stocks) / n),
        "above200_pct": round(100 * sum(bool(s["above200"]) for s in stocks) / n),
    }
    ist = timezone(timedelta(hours=5, minutes=30))
    out = {"updated": datetime.now(ist).strftime("%d %b %Y, %I:%M %p IST"),
           "indices": [r for r in (index_row(k, v) for k, v in INDICES.items()) if r],
           "breadth": breadth, "stocks": stocks}
    os.makedirs("data", exist_ok=True)
    with open("data/market.json", "w") as fh:
        json.dump(out, fh, ensure_ascii=False)
    print("Done:", n, "stocks,", out["updated"])


if __name__ == "__main__":
    main()
  
