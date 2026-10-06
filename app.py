import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# AI part optional hai: ai_tools.py + GEMINI_API_KEY ho tabhi chalega
try:
    from ai_tools import ask_ai, build_context
    AI_OK = True
except Exception:
    AI_OK = False

st.set_page_config(page_title="Pro Screener", page_icon="⚡", layout="wide")

NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "ITC", "SBIN",
    "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA",
    "TITAN", "BAJFINANCE", "HCLTECH", "WIPRO", "ULTRACEMCO", "NTPC", "ONGC",
    "POWERGRID", "TATAMOTORS", "TATASTEEL", "M&M", "ADANIENT", "COALINDIA",
    "TECHM", "NESTLEIND", "JSWSTEEL", "INDUSINDBK", "BAJAJFINSV", "GRASIM",
    "CIPLA", "DRREDDY", "EICHERMOT", "HEROMOTOCO", "BRITANNIA", "APOLLOHOSP",
]

TIMEFRAMES = {
    "Short (Hourly)": ("60m", "60d"),
    "Short (Daily)": ("1d", "2y"),
    "Medium (Weekly)": ("1wk", "5y"),
    "Long (Monthly)": ("1mo", "10y"),
}


# ---------- HELPERS ----------
def fix_symbol(s: str) -> str:
    s = s.strip().upper()
    if "." in s or s.startswith("^") or "=" in s or "-" in s:
        return s
    return s + ".NS"


def currency(symbol: str) -> str:
    return "₹" if symbol.endswith((".NS", ".BO")) else "$"


@st.cache_data(ttl=3600, show_spinner=False)
def search_symbol(query: str):
    """Company naam se ticker dhundo (Nvidia -> NVDA)."""
    try:
        res = yf.Search(query, max_results=8).quotes
    except Exception:
        return []
    out = []
    for q in res:
        if q.get("quoteType") in ("EQUITY", "ETF"):
            name = q.get("shortname") or q.get("longname") or ""
            out.append((q["symbol"], name, q.get("exchDisp", "")))
    return out


@st.cache_data(ttl=900, show_spinner=False)
def load(symbol: str, interval: str = "1d", period: str = "2y"):
    try:
        df = yf.download(symbol, interval=interval, period=period,
                         auto_adjust=True, progress=False, threads=False)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["Close"])


# ---------- INDICATORS ----------
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c = df["Close"]
    for n in (20, 50, 200):
        df[f"SMA{n}"] = c.rolling(n).mean()

    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    df["RSI"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIG"] = df["MACD"].ewm(span=9, adjust=False).mean()

    mid = c.rolling(20).mean()
    std = c.rolling(20).std()
    df["BB_UP"], df["BB_LO"] = mid + 2 * std, mid - 2 * std

    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - c.shift()).abs(),
                    (df["Low"] - c.shift()).abs()], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()
    return df


def score(df: pd.DataFrame) -> dict:
    last = df.iloc[-1]
    pts, notes = 0.0, []

    def chk(cond, p, text):
        nonlocal pts
        if cond:
            pts += p
            notes.append(text)

    price = last["Close"]
    chk(price > last["SMA50"], 1, "Price > SMA50")
    chk(price < last["SMA50"], -1, "Price < SMA50")
    if not np.isnan(last["SMA200"]):
        chk(price > last["SMA200"], 1, "Price > SMA200")
        chk(price < last["SMA200"], -1, "Price < SMA200")
        chk(last["SMA50"] > last["SMA200"], 1, "SMA50 > SMA200")
        chk(last["SMA50"] < last["SMA200"], -1, "SMA50 < SMA200")
    chk(last["MACD"] > last["MACD_SIG"], 1, "MACD bullish")
    chk(last["MACD"] < last["MACD_SIG"], -1, "MACD bearish")
    chk(last["RSI"] < 30, 1, "RSI oversold")
    chk(last["RSI"] > 70, -1, "RSI overbought")

    if pts >= 3: verdict = "Strong Buy"
    elif pts >= 1: verdict = "Buy"
    elif pts > -1: verdict = "Neutral"
    elif pts > -3: verdict = "Sell"
    else: verdict = "Strong Sell"
    return {"score": pts, "verdict": verdict, "notes": notes}


COLORS = {"Strong Buy": "#15803d", "Buy": "#22c55e", "Neutral": "#64748b",
          "Sell": "#ef4444", "Strong Sell": "#b91c1c"}


def badge(label, verdict):
    st.markdown(
        f"<div style='background:{COLORS[verdict]};padding:10px;border-radius:8px;"
        f"text-align:center;color:white;margin-bottom:6px'><small>{label}</small>"
        f"<br><b>{verdict}</b></div>", unsafe_allow_html=True)


def summary_hi(df, sc, cur) -> str:
    l = df.iloc[-1]
    trend = "Bullish (तेजी)" if l["Close"] > l["SMA50"] else "Bearish (मंदी)"
    rsi = l["RSI"]
    mom = "Oversold" if rsi < 30 else "Overbought" if rsi > 70 else "Neutral (संतुलित)"
    return (
        f"1. **ट्रेंड:** स्टॉक अभी {trend} है (SMA50: {cur}{l['SMA50']:.2f})\n\n"
        f"2. **मोमेंटम (RSI):** {rsi:.1f} → {mom}\n\n"
        f"3. **सपोर्ट/रेजिस्टेंस:** 20-दिन का निचला स्तर {cur}{df['Low'].tail(20).min():.2f}, "
        f"ऊपरी स्तर {cur}{df['High'].tail(20).max():.2f}\n\n"
        f"4. **वोलैटिलिटी (ATR):** {cur}{l['ATR']:.2f} प्रति कैंडल\n\n"
        f"**Verdict:** {sc['verdict']} (score {sc['score']:+.1f})"
    )


def candle_chart(df, name):
    d = df.tail(180)
    fig = go.Figure()
    fig.add_candlestick(x=d.index, open=d["Open"], high=d["High"], low=d["Low"],
                        close=d["Close"], name=name)
    for col, color in (("SMA20", "#f59e0b"), ("SMA50", "#3b82f6"), ("SMA200", "#a855f7")):
        fig.add_scatter(x=d.index, y=d[col], name=col, line=dict(width=1.2, color=color))
    fig.add_scatter(x=d.index, y=d["BB_UP"], name="BB Up",
                    line=dict(width=0.6, dash="dot", color="#94a3b8"))
    fig.add_scatter(x=d.index, y=d["BB_LO"], name="BB Low",
                    line=dict(width=0.6, dash="dot", color="#94a3b8"))
    fig.update_layout(height=450, xaxis_rangeslider_visible=False,
                      margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h"))
    return fig


# ---------- STATE ----------
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

st.title("⚡ Pro Investment Terminal")
tab1, tab2, tab3 = st.tabs(["📈 Stock Analysis", "🔎 Screener", "⭐ Watchlist"])

# ---------- TAB 1 ----------
with tab1:
    raw = st.text_input("Company ya symbol likho (Nvidia, Apple, TCS, NIFTYBEES)", "NIFTYBEES")
    symbol = None
    if raw.strip():
        opts = search_symbol(raw.strip())
        if opts:
            labels = [f"{s} — {n} ({e})" for s, n, e in opts]
            pick = st.selectbox("Sahi stock chuno", labels)
            symbol = opts[labels.index(pick)][0]
        else:
            symbol = fix_symbol(raw)

    if symbol:
        cur = currency(symbol)
        daily = load(symbol, "1d", "2y")
        if daily is None or len(daily) < 60:
            st.error("Data nahi mila. Dusra naam ya symbol try karo.")
        else:
            daily = add_indicators(daily)
            price, prev = daily["Close"].iloc[-1], daily["Close"].iloc[-2]
            st.metric(symbol, f"{cur}{price:,.2f}", f"{(price / prev - 1) * 100:+.2f}%")

            if st.button("⭐ Watchlist me save karein"):
                if symbol not in st.session_state.watchlist:
                    st.session_state.watchlist.append(symbol)
                st.toast("Saved!")

            st.subheader("⏱ Technical Verdict by Timeframe")
            cols = st.columns(4)
            for col, (label, (itv, per)) in zip(cols, TIMEFRAMES.items()):
                tf = load(symbol, itv, per)
                with col:
                    if tf is None or len(tf) < 55:
                        st.caption(f"{label}: data kam hai")
                    else:
                        badge(label, score(add_indicators(tf))["verdict"])

            st.plotly_chart(candle_chart(daily, symbol), use_container_width=True)

            sc = score(daily)
            st.subheader("📊 Analysis Summary")
            with st.container(border=True):
                st.markdown(summary_hi(daily, sc, cur))
                st.caption("Signals: " + " • ".join(sc["notes"]))

            if AI_OK:
                st.subheader("🤖 AI Deep Analysis")
                ctx = build_context(symbol, daily, sc)
                if st.button("AI se analysis karo"):
                    with st.spinner("AI soch raha hai..."):
                        st.session_state.ai_out = ask_ai(
                            ctx, "Technical + fundamental + news analysis do. "
                                 "Bull case, bear case aur key levels batao.")
                if "ai_out" in st.session_state:
                    st.markdown(st.session_state.ai_out)

                q = st.text_input("Is stock ke baare me kuch bhi poocho")
                if q:
                    with st.spinner("AI soch raha hai..."):
                        st.markdown(ask_ai(ctx, q))

# ---------- TAB 2 ----------
with tab2:
    st.subheader("Nifty Screener")
    c1, c2, c3 = st.columns(3)
    rsi_min, rsi_max = c1.slider("RSI range", 0, 100, (0, 100))
    verdict_f = c2.multiselect("Verdict", list(COLORS), default=["Strong Buy", "Buy"])
    above200 = c3.checkbox("Sirf SMA200 ke upar")
    universe = st.text_area("Stock list (comma separated)", ", ".join(NIFTY_50), height=100)

    if st.button("🚀 Scan karo", type="primary"):
        syms = [s.strip() for s in universe.split(",") if s.strip()]
        rows, bar = [], st.progress(0.0)
        for i, s in enumerate(syms, 1):
            bar.progress(i / len(syms), text=f"{s} ({i}/{len(syms)})")
            d = load(fix_symbol(s), "1d", "2y")
            if d is None or len(d) < 210:
                continue
            d = add_indicators(d)
            l, sc = d.iloc[-1], score(d)
            rows.append({
                "Stock": s, "Price": round(l["Close"], 2),
                "1D %": round((l["Close"] / d["Close"].iloc[-2] - 1) * 100, 2),
                "RSI": round(l["RSI"], 1), "Verdict": sc["verdict"], "Score": sc["score"],
                "vs SMA200 %": round((l["Close"] / l["SMA200"] - 1) * 100, 1),
                "52W High %": round((l["Close"] / d["High"].tail(252).max() - 1) * 100, 1),
            })
        bar.empty()
        st.session_state.scan = pd.DataFrame(rows)

    if "scan" in st.session_state and not st.session_state.scan.empty:
        df = st.session_state.scan
        df = df[df["RSI"].between(rsi_min, rsi_max)]
        if verdict_f:
            df = df[df["Verdict"].isin(verdict_f)]
        if above200:
            df = df[df["vs SMA200 %"] > 0]
        st.write(f"**{len(df)} stocks mile**")
        st.dataframe(df.sort_values("Score", ascending=False),
                     use_container_width=True, hide_index=True)

# ---------- TAB 3 ----------
with tab3:
    if not st.session_state.watchlist:
        st.info("Watchlist khali hai.")
    for s in list(st.session_state.watchlist):
        d = load(s, "1d", "1y")
        a, b, c = st.columns([2, 2, 1])
        a.write(f"**{s}**")
        if d is not None and len(d) > 2:
            b.write(f"{currency(s)}{d['Close'].iloc[-1]:,.2f} "
                    f"({(d['Close'].iloc[-1] / d['Close'].iloc[-2] - 1) * 100:+.2f}%)")
        if c.button("❌", key=f"rm_{s}"):
            st.session_state.watchlist.remove(s)
            st.rerun()

st.caption("Sirf educational use ke liye. Ye financial advice nahi hai.")
    
