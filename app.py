import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import plotly.graph_objects as go
from ta.momentum import RSIIndicator
from google import genai

st.set_page_config(
    page_title="Pro Investment Terminal v2",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# CSS
# ============================================================
st.markdown("""
<style>
.stApp {
    background-color: #0b0f19;
    color: #f1f5f9;
}
.metric-card {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
}
.signal-box {
    padding: 10px 4px;
    border-radius: 8px;
    text-align: center;
    font-weight: 700;
    font-size: 13px;
    margin-bottom: 6px;
}
.strong-buy { background-color: #15803d; color: #ffffff; }
.buy { background-color: #22c55e; color: #022c22; }
.neutral { background-color: #475569; color: #f8fafc; }
.sell { background-color: #ef4444; color: #ffffff; }
.strong-sell { background-color: #991b1b; color: #ffffff; }
.timeframe-label {
    text-align: center;
    font-size: 12px;
    color: #94a3b8;
    margin-bottom: 4px;
}
.score-box {
    background: linear-gradient(135deg, #172554 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 14px;
    text-align: center;
}
.small-note {
    color: #94a3b8;
    font-size: 12px;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# API KEY
# ============================================================
api_key = None
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]

if not api_key:
    with st.sidebar:
        st.header("⚙️ Settings")
        api_key = st.text_input("Gemini API Key (Backup):", type="password")
        st.caption("Streamlit Settings > Secrets me GEMINI_API_KEY daal sakte hain.")

# ============================================================
# SESSION STATE
# ============================================================
if "watchlist" not in st.session_state:
    st.session_state.watchlist = ["TATAMOTORS.NS", "RELIANCE.NS"]

# ============================================================
# FALLBACK UNIVERSES
# ============================================================
NIFTY50 = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS",
    "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS",
    "BEL.NS", "BHARTIARTL.NS", "CIPLA.NS", "COALINDIA.NS",
    "DRREDDY.NS", "EICHERMOT.NS", "ETERNAL.NS", "GRASIM.NS",
    "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS",
    "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "INDUSINDBK.NS",
    "INFY.NS", "ITC.NS", "JIOFIN.NS", "JSWSTEEL.NS", "KOTAKBANK.NS",
    "LT.NS", "M&M.NS", "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS",
    "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS",
    "SBIN.NS", "SHRIRAMFIN.NS", "SUNPHARMA.NS", "TATACONSUM.NS",
    "TATAMOTORS.NS", "TATASTEEL.NS", "TCS.NS", "TECHM.NS",
    "TITAN.NS", "TRENT.NS", "ULTRACEMCO.NS", "WIPRO.NS"
]

# ============================================================
# DATA FUNCTIONS
# ============================================================
@st.cache_data(ttl=300)
def search_symbol(query):
    query = query.strip()
    if not query:
        return None, None

    clean_sym = (
        query.upper()
        .replace(" ", "")
        .replace(".NS", "")
        .replace(".BO", "")
    )

    try:
        t = yf.Ticker(f"{clean_sym}.NS")
        hist = t.history(period="5d")
        if not hist.empty:
            try:
                name = t.info.get("shortName") or clean_sym
            except Exception:
                name = clean_sym
            return f"{clean_sym}.NS", name
    except Exception:
        pass

    try:
        url = (
            "https://query2.finance.yahoo.com/v1/finance/search"
            f"?q={query}&quotesCount=6&newsCount=0"
        )
        res = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5
        ).json()
        quotes = res.get("quotes", [])

        for q in quotes:
            sym = q.get("symbol", "")
            if sym.endswith(".NS") or sym.endswith(".BO"):
                return (
                    sym,
                    q.get("shortname")
                    or q.get("longname")
                    or sym
                )

        if quotes:
            q = quotes[0]
            return (
                q.get("symbol"),
                q.get("shortname")
                or q.get("longname")
                or q.get("symbol")
            )
    except Exception:
        pass

    return f"{clean_sym}.NS", clean_sym


@st.cache_data(ttl=300)
def get_stock_data(ticker):
    stock = yf.Ticker(ticker)
    df_daily = stock.history(period="1y", interval="1d")

    try:
        df_hourly = stock.history(period="7d", interval="1h")
    except Exception:
        df_hourly = None

    try:
        df_weekly = stock.history(period="2y", interval="1wk")
    except Exception:
        df_weekly = None

    try:
        df_monthly = stock.history(period="5y", interval="1mo")
    except Exception:
        df_monthly = None

    try:
        info = stock.info or {}
    except Exception:
        info = {}

    return df_daily, df_hourly, df_weekly, df_monthly, info


# ============================================================
# TECHNICAL ENGINE
# ============================================================
def technical_metrics(df):
    if df is None or df.empty or len(df) < 50:
        return {}

    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float) if "Volume" in df else pd.Series(index=df.index, dtype=float)

    sma20 = close.rolling(20).mean()
    sma44 = close.rolling(44).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()

    rsi = RSIIndicator(close, window=14).rsi()

    avg_vol20 = volume.rolling(20).mean()

    curr = float(close.iloc[-1])
    sma20_now = float(sma20.iloc[-1]) if pd.notna(sma20.iloc[-1]) else None
    sma44_now = float(sma44.iloc[-1]) if pd.notna(sma44.iloc[-1]) else None
    sma50_now = float(sma50.iloc[-1]) if pd.notna(sma50.iloc[-1]) else None
    sma200_now = float(sma200.iloc[-1]) if pd.notna(sma200.iloc[-1]) else None
    rsi_now = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else None

    # Rising = current > 5 sessions ago > 10 sessions ago
    sma44_rising = False
    if len(sma44.dropna()) >= 11:
        sma44_rising = (
            sma44.iloc[-1] > sma44.iloc[-5] >
            sma44.iloc[-10]
        )

    volume_ratio = None
    if pd.notna(avg_vol20.iloc[-1]) and avg_vol20.iloc[-1] > 0:
        volume_ratio = float(volume.iloc[-1] / avg_vol20.iloc[-1])

    high_52w = float(close.max())
    low_52w = float(close.min())
    from_52w_high = ((curr / high_52w) - 1) * 100 if high_52w else None

    ret_1m = ((curr / close.iloc[-22]) - 1) * 100 if len(close) >= 22 else None
    ret_3m = ((curr / close.iloc[-66]) - 1) * 100 if len(close) >= 66 else None
    ret_6m = ((curr / close.iloc[-126]) - 1) * 100 if len(close) >= 126 else None

    return {
        "price": curr,
        "sma20": sma20_now,
        "sma44": sma44_now,
        "sma50": sma50_now,
        "sma200": sma200_now,
        "sma44_rising": sma44_rising,
        "rsi": rsi_now,
        "volume_ratio": volume_ratio,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "from_52w_high": from_52w_high,
        "ret_1m": ret_1m,
        "ret_3m": ret_3m,
        "ret_6m": ret_6m,
    }


def get_signal(df):
    m = technical_metrics(df)

    if not m or m.get("rsi") is None:
        return "Neutral →", "neutral"

    curr = m["price"]
    rsi = m["rsi"]
    sma20 = m["sma20"]
    sma50 = m["sma50"]
    sma44 = m["sma44"]

    score = 0

    # Trend gets priority.
    if sma44 and curr > sma44:
        score += 2
    else:
        score -= 2

    if sma50 and curr > sma50:
        score += 2
    else:
        score -= 2

    if sma20 and curr > sma20:
        score += 1
    else:
        score -= 1

    # Rising 44 SMA is a positive confirmation.
    if m["sma44_rising"]:
        score += 2

    # Avoid treating every oversold stock as an automatic buy.
    if 50 <= rsi <= 68:
        score += 1
    elif rsi > 75:
        score -= 1
    elif rsi < 30 and m["sma44_rising"]:
        score += 1

    if score >= 5:
        return "Strong Buy ↗", "strong-buy"
    elif score >= 2:
        return "Buy ↗", "buy"
    elif score <= -5:
        return "Strong Sell ↘", "strong-sell"
    elif score <= -2:
        return "Sell ↘", "sell"

    return "Neutral →", "neutral"


# ============================================================
# FUNDAMENTAL + SCORE ENGINE
# ============================================================
def safe_pct(value):
    if isinstance(value, (int, float)) and pd.notna(value):
        return value * 100
    return None


def fundamental_values(info):
    roe = safe_pct(info.get("returnOnEquity"))
    roce = safe_pct(info.get("returnOnCapitalEmployed"))

    # Yahoo does not provide ROCE consistently. Keep it optional.
    debt_equity = info.get("debtToEquity")
    profit_growth = safe_pct(info.get("earningsGrowth"))
    revenue_growth = safe_pct(info.get("revenueGrowth"))

    pe = info.get("trailingPE")
    if pe is None:
        pe = info.get("forwardPE")

    return {
        "pe": pe,
        "roe": roe,
        "roce": roce,
        "debt_equity": debt_equity,
        "profit_growth": profit_growth,
        "revenue_growth": revenue_growth,
    }


def calculate_score(tm, fm):
    """
    Score = 100
    Technical: 50
    Fundamental: 30
    Momentum: 20
    """
    if not tm:
        return 0, []

    score = 0
    reasons = []

    # ---------------- TECHNICAL 50 ----------------
    if tm["sma44_rising"]:
        score += 15
        reasons.append("44 SMA Rising")

    if tm["sma44"] and tm["price"] > tm["sma44"]:
        score += 10
        reasons.append("Price > 44 SMA")

    if tm["sma200"] and tm["price"] > tm["sma200"]:
        score += 10
        reasons.append("Price > 200 SMA")

    if tm["rsi"] is not None and 50 <= tm["rsi"] <= 70:
        score += 5
        reasons.append("RSI 50–70")

    if tm["volume_ratio"] is not None and tm["volume_ratio"] >= 1.2:
        score += 5
        reasons.append("Volume > 20D Avg")

    if tm["from_52w_high"] is not None and tm["from_52w_high"] >= -10:
        score += 5
        reasons.append("Near 52W High")

    # ---------------- FUNDAMENTAL 30 ----------------
    if fm["roe"] is not None and fm["roe"] >= 15:
        score += 10
        reasons.append("ROE > 15%")

    if fm["roce"] is not None and fm["roce"] >= 15:
        score += 10
        reasons.append("ROCE > 15%")

    if fm["debt_equity"] is not None and fm["debt_equity"] <= 100:
        score += 5
        reasons.append("Debt/Equity controlled")

    if fm["profit_growth"] is not None and fm["profit_growth"] >= 10:
        score += 5
        reasons.append("Profit growth > 10%")

    # ---------------- MOMENTUM 20 ----------------
    for key, points, label in [
        ("ret_1m", 5, "1M positive momentum"),
        ("ret_3m", 5, "3M positive momentum"),
        ("ret_6m", 5, "6M positive momentum"),
    ]:
        if tm.get(key) is not None and tm[key] > 0:
            score += points
            reasons.append(label)

    if tm["from_52w_high"] is not None and tm["from_52w_high"] >= -5:
        score += 5
        reasons.append("Within 5% of 52W High")

    return min(score, 100), reasons


def score_label(score):
    if score >= 90:
        return "🔥 Exceptional"
    if score >= 80:
        return "🟢 Strong"
    if score >= 70:
        return "🟡 Good"
    if score >= 60:
        return "⚪ Average"
    return "🔴 Weak"


# ============================================================
# NIFTY UNIVERSE
# ============================================================
@st.cache_data(ttl=86400)
def get_nifty100_symbols():
    urls = [
        "https://www.niftyindices.com/IndexConstituent/ind_nifty100list.csv",
        "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/csv,*/*",
        "Referer": "https://www.niftyindices.com/"
    }

    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.ok and len(r.content) > 100:
                from io import StringIO
                df = pd.read_csv(StringIO(r.text))
                col = next(
                    (c for c in df.columns if "Symbol" in c),
                    None
                )
                if col:
                    syms = [
                        f"{str(x).strip()}.NS"
                        for x in df[col].dropna().tolist()
                    ]
                    if syms:
                        return syms
        except Exception:
            pass

    return NIFTY50


# ============================================================
# SCREENER
# ============================================================
@st.cache_data(ttl=300)
def run_screener(symbols):
    rows = []

    for ticker in symbols:
        try:
            df = yf.download(
                ticker,
                period="1y",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False
            )

            if df is None or df.empty:
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if len(df) < 50:
                continue

            tm = technical_metrics(df)

            try:
                info = yf.Ticker(ticker).info or {}
            except Exception:
                info = {}

            fm = fundamental_values(info)
            score, reasons = calculate_score(tm, fm)

            rows.append({
                "Stock": ticker.replace(".NS", ""),
                "Ticker": ticker,
                "Price": tm.get("price"),
                "RSI": tm.get("rsi"),
                "44 SMA": tm.get("sma44"),
                "44 SMA Rising": "✅" if tm.get("sma44_rising") else "❌",
                "200 SMA": tm.get("sma200"),
                "Volume ×": tm.get("volume_ratio"),
                "1M %": tm.get("ret_1m"),
                "3M %": tm.get("ret_3m"),
                "6M %": tm.get("ret_6m"),
                "ROE %": fm.get("roe"),
                "ROCE %": fm.get("roce"),
                "D/E": fm.get("debt_equity"),
                "P/E": fm.get("pe"),
                "Score": score,
                "Rating": score_label(score),
                "Reasons": ", ".join(reasons[:8])
            })

        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    return (
        pd.DataFrame(rows)
        .sort_values(["Score", "RSI"], ascending=[False, False])
        .reset_index(drop=True)
    )


# ============================================================
# APP
# ============================================================
st.title("⚡ Pro Investment Terminal v2")

tab_screener, tab_stocks, tab_mf, tab_watchlist = st.tabs([
    "🔎 Stock Screener",
    "📈 Stock Analysis",
    "💼 Mutual Funds",
    "⭐ Watchlist"
])

# ============================================================
# TAB 0: SCREENER
# ============================================================
with tab_screener:
    st.subheader("🔎 Smart Stock Screener")
    st.caption(
        "Technical + Fundamental + Momentum scoring. "
        "Score maximum 100."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        universe = st.selectbox(
            "Universe",
            ["NIFTY 50", "NIFTY 100"],
            index=0
        )

    with col2:
        preset = st.selectbox(
            "Preset",
            [
                "Custom",
                "🚀 Momentum",
                "📈 44 SMA Rising",
                "🔥 Breakout",
                "🏆 Quality",
                "💎 Value / Quality"
            ]
        )

    with col3:
        min_score = st.slider(
            "Minimum Score",
            min_value=0,
            max_value=100,
            value=60,
            step=5
        )

    with st.expander("⚙️ Advanced Filters", expanded=True):
        a1, a2, a3, a4 = st.columns(4)

        with a1:
            require_44_rising = st.checkbox(
                "44 SMA Rising",
                value=(preset in ["📈 44 SMA Rising", "🚀 Momentum", "🔥 Breakout"])
            )
            price_above_44 = st.checkbox(
                "Price > 44 SMA",
                value=True
            )

        with a2:
            require_200 = st.checkbox(
                "Price > 200 SMA",
                value=(preset != "💎 Value / Quality")
            )
            min_rsi = st.number_input(
                "RSI minimum",
                min_value=0,
                max_value=100,
                value=50
            )

        with a3:
            max_rsi = st.number_input(
                "RSI maximum",
                min_value=0,
                max_value=100,
                value=70
            )
            min_volume = st.number_input(
                "Min Volume × 20D Avg",
                min_value=0.0,
                max_value=10.0,
                value=1.0,
                step=0.1
            )

        with a4:
            min_roe = st.number_input(
                "Min ROE %",
                min_value=-100.0,
                max_value=200.0,
                value=0.0,
                step=1.0
            )
            min_roce = st.number_input(
                "Min ROCE %",
                min_value=-100.0,
                max_value=200.0,
                value=0.0,
                step=1.0
            )

    if preset == "🏆 Quality":
        min_roe = max(min_roe, 15)
        min_roce = max(min_roce, 15)

    if preset == "🚀 Momentum":
        min_rsi = max(min_rsi, 50)
        max_rsi = min(max_rsi, 70)
        min_volume = max(min_volume, 1.2)

    if preset == "🔥 Breakout":
        min_rsi = max(min_rsi, 55)
        min_volume = max(min_volume, 1.5)

    if preset == "📈 44 SMA Rising":
        require_44_rising = True
        price_above_44 = True

    if preset == "💎 Value / Quality":
        min_roe = max(min_roe, 15)
        min_roce = max(min_roce, 15)
        require_200 = False

    scan_clicked = st.button(
        "🔍 SCAN STOCKS",
        type="primary",
        use_container_width=True
    )

    if scan_clicked:
        symbols = NIFTY50 if universe == "NIFTY 50" else get_nifty100_symbols()

        with st.spinner(
            f"Scanning {len(symbols)} stocks... "
            "Yahoo Finance se data aa raha hai."
        ):
            result_df = run_screener(tuple(symbols))

                if result_df.empty:
            st.error(
                "Data fetch nahi ho paya. Thodi der baad dobara Scan karein."
            )
        else:
            filtered = result_df.copy()

            if require_44_rising:
                filtered = filtered[filtered["44 SMA Rising"] == "✅"]

            if price_above_44:
                filtered = filtered[
                    filtered["Price"] > filtered["44 SMA"]
                ]

            if require_200:
                filtered = filtered[
                    filtered["200 SMA"].notna()
                    & (filtered["Price"] > filtered["200 SMA"])
                ]

            filtered = filtered[
                filtered["RSI"].notna()
                & (filtered["RSI"] >= min_rsi)
                & (filtered["RSI"] <= max_rsi)
            ]

            if min_volume > 0:
                filtered = filtered[
                    filtered["Volume ×"].notna()
                    & (filtered["Volume ×"] >= min_volume)
                ]

            if min_roe > 0:
                filtered = filtered[
                    filtered["ROE %"].notna()
                    & (filtered["ROE %"] >= min_roe)
                ]

            if min_roce > 0:
                # ROCE is not consistently available from Yahoo.
                filtered = filtered[
                    filtered["ROCE %"].notna()
                    & (filtered["ROCE %"] >= min_roce)
                ]

            filtered = filtered[
                filtered["Score"] >= min_score
            ].reset_index(drop=True)

            st.session_state["last_screener"] = filtered
            
                
