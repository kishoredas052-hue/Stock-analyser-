import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import xml.etree.ElementTree as ET
from google import genai

# =========================================================
# 1. PAGE SETUP & MODERN FINTECH THEME
# =========================================================
st.set_page_config(
    page_title="Pro Investment Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .reportview-container, .main {
        background-color: #0b0f19;
        color: #e2e8f0;
    }
    .metric-card {
        background: #151c2c;
        border: 1px solid #232f45;
        border-radius: 10px;
        padding: 12px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    .metric-title { font-size: 12px; color: #94a3b8; margin-bottom: 4px; }
    .metric-value { font-size: 18px; font-weight: 700; color: #f8fafc; }
    .metric-delta-pos { font-size: 12px; color: #22c55e; font-weight: 600; }
    .metric-delta-neg { font-size: 12px; color: #ef4444; font-weight: 600; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #151c2c;
        border-radius: 8px 8px 0px 0px;
        color: #94a3b8;
        padding: 10px 18px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563eb !important;
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 2. AI ENGINE CONFIGURATION
# =========================================================
def get_client():
    key = st.secrets.get("GEMINI_API_KEY", None)
    if not key:
        return None
    return genai.Client(api_key=key)

@st.cache_data(ttl=1800, show_spinner=False)
def get_fundamentals(symbol: str) -> dict:
    try:
        tk = yf.Ticker(symbol)
        info = tk.info or {}
        keys = ['sector', 'trailingPE', 'priceToBook', 'debtToEquity', 'returnOnEquity', 'marketCap']
        return {k: info.get(k, 'N/A') for k in keys}
    except Exception:
        return {}

@st.cache_data(ttl=1800, show_spinner=False)
def get_google_news(query: str, max_items: int = 4) -> list:
    try:
        url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        resp = requests.get(url, timeout=5)
        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall('.//item')[:max_items]:
            title = item.find('title').text if item.find('title') is not None else ""
            if title:
                items.append(title)
        return items
    except Exception:
        return []

def build_prompt(symbol: str, df: pd.DataFrame, news: list, fundamentals: dict) -> str:
    close = df['Close'].iloc[-1]
    sma20 = df['SMA20'].iloc[-1] if 'SMA20' in df else close
    sma50 = df['SMA50'].iloc[-1] if 'SMA50' in df else close
    rsi = df['RSI'].iloc[-1] if 'RSI' in df else 50.0

    prompt = f"""
    Stock: {symbol}
    Current Price: ₹{close:.2f}
    SMA 20: ₹{sma20:.2f} | SMA 50: ₹{sma50:.2f} | RSI: {rsi:.1f}
    Fundamentals: {fundamentals}
    Recent News Headings: {news}

    Task:
    Aap ek pro market analyst hain. Simple Hinglish mein short aur clear analysis dein:
    1. Overall Mood aur Trend kaisa hai?
    2. Support aur Resistance levels ka kya matlab hai?
    3. Actionable verdict (Entry/Exit/Wait) aur Stop Loss.
    """
    return prompt

def ask_ai_with_news(symbol: str, df: pd.DataFrame):
    client = get_client()
    if not client:
        return "⚠️ Gemini API Key configure nahi hai. Streamlit settings mein 'GEMINI_API_KEY' check karein."

    news = get_google_news(f"{symbol} stock share market")
    fundamentals = get_fundamentals(symbol)
    prompt = build_prompt(symbol, df, news, fundamentals)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"AI analysis generate karne mein error aaya: {str(e)}"

# =========================================================
# 3. TOP MACRO TICKER BAR
# =========================================================
@st.cache_data(ttl=300)
def fetch_ticker_data(symbol):
    try:
        t = yf.Ticker(symbol)
        df = t.history(period="5d")
        if len(df) >= 2:
            current = df['Close'].iloc[-1]
            prev = df['Close'].iloc[-2]
            pct = ((current - prev) / prev) * 100
            return current, pct
    except Exception:
        pass
    return None, None

col1, col2, col3, col4, col5 = st.columns(5)
tickers = [
    ("^NSEI", "NIFTY 50", col1),
    ("^NSEBANK", "BANK NIFTY", col2),
    ("GOLDBEES.NS", "GOLD ETF", col3),
    ("SILVERBEES.NS", "SILVER ETF", col4),
    ("INR=X", "USD / INR", col5)
]

for sym, label, col in tickers:
    val, delta = fetch_ticker_data(sym)
    with col:
        if val is not None:
            delta_class = "metric-delta-pos" if delta >= 0 else "metric-delta-neg"
            delta_sign = "+" if delta >= 0 else ""
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">{label}</div>
                <div class="metric-value">₹{val:,.2f}</div>
                <div class="{delta_class}">{delta_sign}{delta:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">{label}</div>
                <div class="metric-value">N/A</div>
            </div>
            """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# =========================================================
# 4. MAIN WORKSPACE TABS
# =========================================================
tab_stocks, tab_gold, tab_mf = st.tabs([
    "📈 Stocks Radar", 
    "🪙 Gold & Commodities", 
    "📊 Mutual Funds Tracker"
])

# ----------------- TAB 1: STOCKS RADAR -----------------
with tab_stocks:
    c_left, c_right = st.columns([1, 3])

    with c_left:
        st.subheader("Select Stock")
        stock_symbol = st.selectbox(
            "Quick Select",
            ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ITC.NS", "TATAMOTORS.NS"],
            index=0
        )
        custom_stock = st.text_input("Ya Dusra Stock Likhein (e.g. SBIN.NS)", "")
        if custom_stock:
            stock_symbol = custom_stock.strip().upper()

    t = yf.Ticker(stock_symbol)
    df = t.history(period="6mo")
    info = t.info or {}

    if df is not None and not df.empty:
        # Inbuilt Technical Calculations (Bina kisi extra library ke)
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['SMA50'] = df['Close'].rolling(window=50).mean()

        # Inbuilt RSI Calculation
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        latest_price = df['Close'].iloc[-1]
        latest_rsi = df['RSI'].iloc[-1] if not pd.isna(df['RSI'].iloc[-1]) else 50.0
        latest_sma20 = df['SMA20'].iloc[-1] if not pd.isna(df['SMA20'].iloc[-1]) else latest_price
        
        support = df['Low'].tail(20).min()
        resistance = df['High'].tail(20).max()
        stop_loss = round(latest_price * 0.97, 2)
        target = round(latest_price * 1.06, 2)

        # Verdict logic
        score = 0
        if latest_price > latest_sma20: score += 1
        if 40 <= latest_rsi <= 65: score += 1
        if latest_price > support: score += 1

        if score >= 3:
            verdict, verdict_color = "Strong Buy", "#22c55e"
        elif score == 2:
            verdict, verdict_color = "Moderate Buy", "#38bdf8"
        else:
            verdict, verdict_color = "Sell / Caution", "#ef4444"

        with c_left:
            st.markdown(f"""
            <div style="background:#151c2c; border:1px solid #232f45; border-radius:10px; padding:15px; margin-top:15px;">
                <div style="font-size:12px; color:#94a3b8;">Daily Verdict</div>
                <div style="font-size:24px; font-weight:800; color:{verdict_color};">{verdict}</div>
                <hr style="border-color:#232f45;">
                <div style="font-size:13px;"><b>CMP:</b> ₹{latest_price:,.2f}</div>
                <div style="font-size:13px;"><b>RSI (14):</b> {latest_rsi:.1f}</div>
                <div style="font-size:13px;"><b>Support:</b> ₹{support:,.2f}</div>
                <div style="font-size:13px;"><b>Resistance:</b> ₹{resistance:,.2f}</div>
                <div style="font-size:13px; color:#ef4444;"><b>Stop Loss:</b> ₹{stop_loss:,.2f}</div>
                <div style="font-size:13px; color:#22c55e;"><b>Target:</b> ₹{target:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)

        with c_right:
            # Chart
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=df.index,
                open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'],
                name="Price"
            ))
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='#38bdf8', width=1.5), name="SMA 20"))
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='#f59e0b', width=1.5), name="SMA 50"))
            
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0b0f19",
                plot_bgcolor="#111827",
                height=420,
                margin=dict(l=10, r=10, t=30, b=10),
                xaxis_rangeslider_visible=False
            )
            st.plotly_chart(fig, use_container_width=True)

            # Fundamentals
            st.markdown("#### 🔍 Fundamental Ratios")
            f1, f2, f3, f4 = st.columns(4)
            pe = info.get("trailingPE", "N/A")
            roe = info.get("returnOnEquity", "N/A")
            roe_val = f"{roe*100:.1f}%" if isinstance(roe, (int, float)) else "N/A"
            mcap = info.get("marketCap", "N/A")
            mcap_val = f"₹{mcap/10000000:.0f} Cr" if isinstance(mcap, (int, float)) else "N/A"
            de = info.get("debtToEquity", "N/A")

            f1.metric("P/E Ratio", f"{pe:.1f}" if isinstance(pe, (int, float)) else pe)
            f2.metric("ROE", roe_val)
            f3.metric("Market Cap", mcap_val)
            f4.metric("Debt-to-Equity", f"{de:.2f}" if isinstance(de, (int, float)) else de)

            # AI Insights
            st.markdown("---")
            st.markdown("#### 🤖 AI Samjhaye (Hinglish Analysis)")
            if st.button("Generate AI Market Summary ⚡"):
                with st.spinner("AI news aur indicators scan kar raha hai..."):
                    ai_response = ask_ai_with_news(stock_symbol, df)
                    st.markdown(f"""
                    <div style="background:#151c2c; border-left: 4px solid #38bdf8; padding: 16px; border-radius: 6px; line-height: 1.6;">
                        {ai_response}
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.error("Stock data load nahi hua. Kripya symbol check karein.")

# ----------------- TAB 2: GOLD & COMMODITIES -----------------
with tab_gold:
    st.subheader("🪙 Gold & Precious Metals Radar")
    g1, g2 = st.columns([1, 2])
    
    with g1:
        g_etf_price, g_etf_delta = fetch_ticker_data("GOLDBEES.NS")
        if g_etf_price:
            st.metric("Gold BeES ETF Price (NSE)", f"₹{g_etf_price:.2f}", f"{g_etf_delta:.2f}%")
        st.info("💡 **Gold Allocation:** Market volatility se bachav ke liye standard rule ke mutabiq 10-15% Gold hold karna chahiye.")

    with g2:
        gold_df = yf.download("GOLDBEES.NS", period="1y", interval="1d")
        if not gold_df.empty:
            g_fig = go.Figure()
            g_fig.add_trace(go.Scatter(
                x=gold_df.index, y=gold_df['Close'],
                mode='lines', line=dict(color='#eab308', width=2),
                name="Gold BeES"
            ))
            g_fig.update_layout(
                title="Gold BeES 1-Year Price Trend",
                template="plotly_dark",
                paper_bgcolor="#0b0f19",
                plot_bgcolor="#111827",
                height=320,
                margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(g_fig, use_container_width=True)

# ----------------- TAB 3: MUTUAL FUNDS TRACKER -----------------
with tab_mf:
    st.subheader("📊 Mutual Funds & SIP Planning")
    mf1, mf2 = st.columns([1, 1])

    with mf1:
        st.markdown("#### Curated Funds List")
        mf_table = pd.DataFrame({
            "Scheme Name": [
                "Parag Parikh Flexi Cap Fund",
                "Mirae Asset Large & Midcap",
                "Nippon India Small Cap Fund",
                "UTI Nifty 50 Index Fund"
            ],
            "Category": ["Flexi Cap", "Large & Mid Cap", "Small Cap", "Index Fund"],
            "Risk Profile": ["Moderate", "Moderately High", "Very High", "Low-Moderate"],
            "3Y Return": ["18.2%", "21.5%", "26.4%", "14.8%"]
        })
        st.dataframe(mf_table, use_container_width=True, hide_index=True)

    with mf2:
        st.markdown("#### 💰 Visual SIP Planner")
        sip_amount = st.slider("Monthly SIP Amount (₹)", 1000, 50000, 5000, step=1000)
        expected_cagr = st.slider("Expected Annual Return (%)", 8, 25, 13)
        time_period = st.slider("Investment Period (Years)", 1, 30, 10)
        
        months = time_period * 12
        monthly_rate = (expected_cagr / 100) / 12
        invested_amt = sip_amount * months
        future_val = sip_amount * (((1 + monthly_rate) ** months - 1) / monthly_rate) * (1 + monthly_rate)
        wealth_gain = future_val - invested_amt
        
        s1, s2 = st.columns(2)
        s1.metric("Invested Capital", f"₹{invested_amt:,.0f}")
        s2.metric("Total Future Value", f"₹{future_val:,.0f}", f"+₹{wealth_gain:,.0f}")

st.markdown("<br><hr>", unsafe_allow_html=True)
st.caption("⚠️ Disclaimer: Yeh app algorithmic analysis aur educational purposes ke liye hai. Yeh SEBI registered investment advice nahi hai.")
            
