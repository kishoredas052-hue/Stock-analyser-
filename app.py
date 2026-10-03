import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import plotly.graph_objects as go
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from google import genai

st.set_page_config(page_title="Pro Financial Dashboard", layout="wide", initial_sidebar_state="collapsed")

# Sleek Glassmorphism & Dark Fintech CSS
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
</style>
""", unsafe_allow_html=True)

# Smart API Key Handling (Secrets first, fallback to sidebar)
api_key = None
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]

if not api_key:
    with st.sidebar:
        st.header("⚙️ Settings")
        api_key = st.text_input("Gemini API Key (Backup):", type="password")
        st.caption("Tip: Isse Streamlit Settings > Secrets me daal dein taaki bar-bar na dalna pade.")

if "watchlist" not in st.session_state:
    st.session_state.watchlist = ["TATAMOTORS.NS", "RELIANCE.NS"]

# Caching Data for Instant Speed & No Lag
@st.cache_data(ttl=300)
def search_symbol(query):
    query = query.strip()
    if not query:
        return None, None
    clean_sym = query.upper().replace(" ", "").replace(".NS", "").replace(".BO", "")
    try:
        t = yf.Ticker(f"{clean_sym}.NS")
        hist = t.history(period="5d")
        if not hist.empty:
            name = t.info.get("shortName") or clean_sym
            return f"{clean_sym}.NS", name
    except Exception:
        pass
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=6&newsCount=0"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
        quotes = res.get("quotes", [])
        for q in quotes:
            sym = q.get("symbol", "")
            if sym.endswith(".NS") or sym.endswith(".BO"):
                return sym, q.get("shortname") or q.get("longname") or sym
        if quotes:
            return quotes[0].get("symbol"), quotes[0].get("shortname") or quotes[0].get("longname") or quotes[0].get("symbol")
    except Exception:
        pass
    return f"{clean_sym}.NS", clean_sym

@st.cache_data(ttl=300)
def get_stock_data(ticker):
    stock = yf.Ticker(ticker)
    df_daily = stock.history(period="1y", interval="1d")
    try: df_hourly = stock.history(period="7d", interval="1h")
    except: df_hourly = None
    try: df_weekly = stock.history(period="2y", interval="1wk")
    except: df_weekly = None
    try: df_monthly = stock.history(period="5y", interval="1mo")
    except: df_monthly = None
    info = stock.info or {}
    return df_daily, df_hourly, df_weekly, df_monthly, info

def get_signal(df):
    if df is None or len(df) < 14:
        return "Neutral →", "neutral"
    close = df['Close']
    curr = close.iloc[-1]
    rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
    sma20 = SMAIndicator(close, window=20).sma_indicator().iloc[-1] if len(close) >= 20 else curr
    sma50 = SMAIndicator(close, window=50).sma_indicator().iloc[-1] if len(close) >= 50 else sma20
    buy, sell = 0, 0
    if rsi < 35: buy += 2
    elif rsi < 45: buy += 1
    elif rsi > 70: sell += 2
    elif rsi > 55: sell += 1
    if curr > sma20: buy += 1
    else: sell += 1
    if curr > sma50: buy += 2
    else: sell += 2
    score = buy - sell
    if score >= 3: return "Strong Buy ↗", "strong-buy"
    elif score >= 1: return "Buy ↗", "buy"
    elif score <= -3: return "Strong Sell ↘", "strong-sell"
    elif score <= -1: return "Sell ↘", "sell"
    return "Neutral →", "neutral"

st.title("⚡ Pro Investment Terminal")

tab_stocks, tab_mf, tab_watchlist = st.tabs(["📈 Stocks (NSE & Global)", "💼 Mutual Funds", "⭐ Watchlist"])

# ================= TAB 1: STOCKS =================
with tab_stocks:
    search_query = st.text_input("🔍 Search Any Stock:", value="TATAMOTORS", placeholder="e.g. jk paper, sbc exports, reliance, apple, tsla...")

    if search_query:
        ticker, company_name = search_symbol(search_query)
        if ticker:
            with st.spinner("Loading market data..."):
                df_daily, df_hourly, df_weekly, df_monthly, info = get_stock_data(ticker)

            if not df_daily.empty and len(df_daily) > 1:
                curr_price = df_daily['Close'].iloc[-1]
                prev_price = df_daily['Close'].iloc[-2]
                pct_chg = ((curr_price - prev_price) / prev_price) * 100
                currency = "$" if not ticker.endswith((".NS", ".BO")) else "₹"
                sig_d, cls_d = get_signal(df_daily)

                # Modern KPI Card
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size:22px; font-weight:800;">{company_name} <span style="font-size:14px; color:#94a3b8;">({ticker})</span></div>
                    <div style="margin-top:4px;">
                        <span style="font-size:28px; font-weight:800;">{currency}{curr_price:.2f}</span>
                        <span style="color:{'#22c55e' if pct_chg>=0 else '#ef4444'}; font-size:16px; font-weight:700;"> ({pct_chg:+.2f}%)</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col_btn, _ = st.columns([2, 3])
                with col_btn:
                    if st.button("⭐ Watchlist me Save karein"):
                        if ticker not in st.session_state.watchlist:
                            st.session_state.watchlist.append(ticker)
                            st.success("Watchlist me add ho gaya!")
                        else:
                            st.info("Already watchlist me hai.")

                # Multi-Timeframe Signal Cards
                lbl_h, cls_h = get_signal(df_hourly if df_hourly is not None and not df_hourly.empty else df_daily.tail(30))
                lbl_w, cls_w = get_signal(df_weekly if df_weekly is not None and not df_weekly.empty else df_daily)
                lbl_m, cls_m = get_signal(df_monthly if df_monthly is not None and not df_monthly.empty else df_daily)

                st.markdown("### ⏱️ Technical Verdict by Timeframe")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.markdown('<div class="timeframe-label">Short (Hourly)</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="signal-box {cls_h}">{lbl_h}</div>', unsafe_allow_html=True)
                with c2:
                    st.markdown('<div class="timeframe-label">Short (Daily)</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="signal-box {cls_d}">{lbl_d}</div>', unsafe_allow_html=True)
                with c3:
                    st.markdown('<div class="timeframe-label">Medium (Weekly)</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="signal-box {cls_w}">{lbl_w}</div>', unsafe_allow_html=True)
                with c4:
                    st.markdown('<div class="timeframe-label">Long (Monthly)</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="signal-box {cls_m}">{lbl_m}</div>', unsafe_allow_html=True)

                # Professional Interactive Candlestick + Volume Chart
                st.markdown("### 📊 Interactive Chart")
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=df_daily.index,
                    open=df_daily['Open'],
                    high=df_daily['High'],
                    low=df_daily['Low'],
                    close=df_daily['Close'],
                    name="Candlestick"
                ))
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="#0b0f19",
                    plot_bgcolor="#0f172a",
                    xaxis_rangeslider_visible=False,
                    height=380,
                    margin=dict(l=10, r=10, t=10, b=10)
                )
                st.plotly_chart(fig, use_container_width=True)

                # Fundamentals
                pe = info.get('trailingPE') or info.get('forwardPE') or "N/A"
                roe = info.get('returnOnEquity')
                roe_val = f"{roe * 100:.2f}%" if isinstance(roe, (int, float)) else "N/A"
                mcap = info.get('marketCap')
                mcap_str = f"₹{mcap/10000000:.0f} Cr" if isinstance(mcap, (int, float)) else "N/A"

                st.markdown("### 🏢 Valuation & Health")
                f1, f2, f3 = st.columns(3)
                f1.metric("P/E Ratio", f"{pe if isinstance(pe, str) else round(pe, 2)}")
                f2.metric("ROE", f"{roe_val}")
                f3.metric("Market Cap", f"{mcap_str}")

                # AI Assistant Section
                st.write("---")
                st.markdown("### 🤖 AI Financial Analyst")
                if api_key:
                    if st.button("✨ Generate AI Analysis Report"):
                        with st.spinner("AI report tayar kar raha hai..."):
                            try:
                                client = genai.Client(api_key=api_key.strip())
                                prompt = f"""
                                Analyze {company_name} ({ticker}):
                                Price: {currency}{curr_price:.2f} ({pct_chg:+.2f}%)
                                Technicals: Hourly: {lbl_h}, Daily: {lbl_d}, Weekly: {lbl_w}, Monthly: {lbl_m}
                                Fundamentals: P/E: {pe}, ROE: {roe_val}, MCap: {mcap_str}

                                Provide a clear, actionable report in concise Hinglish:
                                1. Short-Term Swing: Entry zones, Stop-Loss, Target.
                                2. Long-Term Value: Fair price, Accumulation strategy.
                                3. Final Take: Immediate action.
                                """
                                res = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                                st.markdown(res.text)
                            except Exception as err:
                                st.error(f"AI Error: {err}. API key check karein.")
                else:
                    st.info("💡 AI report ke liye sidebar me API key dalein ya Streamlit Secrets me GEMINI_API_KEY set karein.")
            else:
                st.warning("Data fetch nahi ho paya. Kripya dusra symbol check karein.")

# ================= TAB 2: MUTUAL FUNDS =================
with tab_mf:
    st.subheader("💼 Indian Mutual Funds (Direct / Regular)")
    POPULAR_FUNDS = {
        "Parag Parikh Flexi Cap Fund - Direct": 122639,
        "Nippon India Small Cap Fund - Direct": 118778,
        "Quant Small Cap Fund - Direct": 120828,
        "HDFC Mid-Cap Opportunities Fund - Direct": 118989,
        "SBI Bluechip Fund - Direct": 119598
    }
    selected_mf = st.selectbox("Popular Schemes:", list(POPULAR_FUNDS.keys()))
    if st.button("📊 Fetch Fund NAV"):
        with st.spinner("Fetching AMFI NAV..."):
            try:
                code = POPULAR_FUNDS[selected_mf]
                res = requests.get(f"https://api.mfapi.in/mf/{code}", timeout=6).json()
                meta = res.get("meta", {})
                data = res.get("data", [])
                if data:
                    c_nav = float(data[0]["nav"])
                    p_nav = float(data[1]["nav"])
                    chg_nav = ((c_nav - p_nav) / p_nav) * 100
                    st.metric("Current NAV", f"₹{c_nav:.2f}", f"{chg_nav:+.2f}%")
                    st.write(f"**Fund House:** {meta.get('fund_house')}")
                    st.write(f"**Category:** {meta.get('scheme_category')}")
                    
                    df_nav = pd.DataFrame(data[:365])
                    df_nav["date"] = pd.to_datetime(df_nav["date"], format="%d-%m-%Y")
                    df_nav["nav"] = df_nav["nav"].astype(float)
                    st.line_chart(df_nav.sort_values("date").set_index("date")["nav"])
            except Exception as ex:
                st.error(f"Error: {ex}")

# ================= TAB 3: WATCHLIST =================
with tab_watchlist:
    st.subheader("⭐ Saved Watchlist")
    if st.session_state.watchlist:
        for sym in st.session_state.watchlist:
            st.info(f"📌 **{sym}**")
        if st.button("Clear Watchlist"):
            st.session_state.watchlist = []
            st.rerun()
    else:
        st.write("Aapki watchlist khali hai. Stocks tab me jakar ⭐ Watchlist me Save karein dabayein.")
                
