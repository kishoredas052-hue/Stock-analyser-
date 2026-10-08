import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import xml.etree.ElementTree as ET
from google import genai

# --- PAGE SETUP ---
st.set_page_config(
    page_title="Terminal Pro",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- MODERN FINTECH MOBILE CSS ---
st.markdown("""
<style>
    /* Dark Theme & Container Lock */
    .stApp {
        background-color: #0d111a;
        color: #f1f5f9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 2rem !important;
        max-width: 480px !important;
        margin: auto;
    }
    header, footer { visibility: hidden; }

    /* Custom Glassmorphic Cards */
    .app-card {
        background: linear-gradient(145deg, #161e2e, #111723);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 18px;
        padding: 16px;
        margin-bottom: 14px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    }

    /* Price Section */
    .stock-title { font-size: 14px; color: #94a3b8; font-weight: 500; }
    .big-price { font-size: 32px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; }
    .badge-pill-green {
        display: inline-block;
        background: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
    }
    .badge-pill-red {
        display: inline-block;
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
    }

    /* Grid Layout */
    .grid-2x2 {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        margin-top: 8px;
    }
    .stat-item {
        background: rgba(255, 255, 255, 0.03);
        padding: 10px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.04);
    }
    .stat-label { font-size: 11px; color: #64748b; margin-bottom: 2px; }
    .stat-value { font-size: 14px; font-weight: 700; color: #e2e8f0; }

    /* Modern Tabs */
    .stTabs [data-baseweb="tab-list"] {
        display: flex;
        background: #161e2e;
        border-radius: 12px;
        padding: 4px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    .stTabs [data-baseweb="tab"] {
        flex: 1;
        text-align: center;
        border-radius: 10px;
        padding: 8px 10px;
        color: #94a3b8;
        font-size: 13px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #3b82f6 !important;
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

# --- AI CONFIGURATION ---
def get_client():
    key = st.secrets.get("GEMINI_API_KEY", None)
    return genai.Client(api_key=key) if key else None

@st.cache_data(ttl=1800, show_spinner=False)
def get_news(query: str):
    try:
        url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        resp = requests.get(url, timeout=4)
        root = ET.fromstring(resp.content)
        return [item.find('title').text for item in root.findall('.//item')[:3] if item.find('title') is not None]
    except Exception:
        return []

def ask_gemini(symbol, price, rsi, support, resistance, news):
    client = get_client()
    if not client:
        return "⚠️ Gemini API Key missing hai. Streamlit Secrets check karein."
    
    prompt = f"""
    Aap ek pro technical market analyst hain.
    Stock: {symbol} | CMP: ₹{price} | RSI: {rsi:.1f} | Support: ₹{support} | Resistance: ₹{resistance}
    News: {news}

    Task:
    Ek dum simple Hinglish mein 3 bullet points mein seedhi baat batao:
    1. Trend Mood (Bullish/Bearish)
    2. Trade Setup (Entry/Wait/Risk)
    3. Actionable Stop-Loss & Target
    """
    try:
        res = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return res.text
    except Exception as e:
        return f"AI analysis error: {str(e)}"

# --- TOP HEADER ---
st.markdown("""
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
    <div style="font-size:18px; font-weight:800; color:#ffffff; letter-spacing: -0.3px;">⚡ Market Terminal</div>
    <div style="font-size:12px; color:#38bdf8; background:rgba(56,189,248,0.1); padding:4px 10px; border-radius:12px; font-weight:600;">LIVE FEED</div>
</div>
""", unsafe_allow_html=True)

# --- STOCK SELECTION ---
col_sel, col_in = st.columns([1, 1])
with col_sel:
    preset_stock = st.selectbox("", ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "TATAMOTORS.NS", "INFY.NS", "GOLDBEES.NS"], label_visibility="collapsed")
with col_in:
    custom_stock = st.text_input("", placeholder="Other (e.g. SBIN.NS)", label_visibility="collapsed")

symbol = custom_stock.strip().upper() if custom_stock else preset_stock

# --- DATA PROCESSING ---
@st.cache_data(ttl=300)
def load_data(sym):
    t = yf.Ticker(sym)
    df = t.history(period="6mo")
    info = t.info or {}
    return df, info

df, info = load_data(symbol)

if df is not None and len(df) > 20:
    # Technicals
    latest_close = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2]
    pct_change = ((latest_close - prev_close) / prev_close) * 100
    
    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    latest_rsi = df['RSI'].iloc[-1] if not pd.isna(df['RSI'].iloc[-1]) else 50.0

    support = round(df['Low'].tail(20).min(), 2)
    resistance = round(df['High'].tail(20).max(), 2)
    sl = round(latest_close * 0.97, 2)
    target = round(latest_close * 1.05, 2)

    badge_class = "badge-pill-green" if pct_change >= 0 else "badge-pill-red"
    badge_sign = "+" if pct_change >= 0 else ""

    # MAIN PRICE CARD
    st.markdown(f"""
    <div class="app-card">
        <div class="stock-title">{symbol} • NSE</div>
        <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-top:4px;">
            <div class="big-price">₹{latest_close:,.2f}</div>
            <div class="{badge_class}">{badge_sign}{pct_change:.2f}%</div>
        </div>
        <div class="grid-2x2">
            <div class="stat-item"><div class="stat-label">Support</div><div class="stat-value">₹{support:,.2f}</div></div>
            <div class="stat-item"><div class="stat-label">Resistance</div><div class="stat-value">₹{resistance:,.2f}</div></div>
            <div class="stat-item"><div class="stat-label">Stop-Loss</div><div class="stat-value" style="color:#f87171;">₹{sl:,.2f}</div></div>
            <div class="stat-item"><div class="stat-label">Target</div><div class="stat-value" style="color:#4ade80;">₹{target:,.2f}</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- TABS WORKSPACE ---
    tab_chart, tab_ai, tab_fundamentals = st.tabs(["📊 Area Chart", "🤖 AI Insights", "📋 Details"])

    with tab_chart:
        fig = go.Figure()
        # Modern Neon Gradient Curve
        fig.add_trace(go.Scatter(
            x=df.index, y=df['Close'],
            mode='lines',
            line=dict(color='#38bdf8', width=2.5),
            fill='tozeroy',
            fillcolor='rgba(56, 189, 248, 0.08)',
            name='Price'
        ))
        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=280,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(showgrid=False, zeroline=False),
            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', zeroline=False),
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    with tab_ai:
        if st.button("Generate AI Market Breakdown ⚡", use_container_width=True):
            with st.spinner("AI scanning chart & news..."):
                news_items = get_news(f"{symbol} stock share")
                ai_text = ask_gemini(symbol, round(latest_close, 2), latest_rsi, support, resistance, news_items)
                st.markdown(f"""
                <div class="app-card" style="font-size:13px; line-height:1.6; border-left: 3px solid #38bdf8;">
                    {ai_text}
                </div>
                """, unsafe_allow_html=True)

    with tab_fundamentals:
        pe = info.get("trailingPE", "N/A")
        roe = info.get("returnOnEquity", "N/A")
        roe_val = f"{roe*100:.1f}%" if isinstance(roe, (int, float)) else "N/A"
        mcap = info.get("marketCap", "N/A")
        mcap_val = f"₹{mcap/10000000:.0f} Cr" if isinstance(mcap, (int, float)) else "N/A"
        de = info.get("debtToEquity", "N/A")

        st.markdown(f"""
        <div class="app-card">
            <div class="grid-2x2">
                <div class="stat-item"><div class="stat-label">P/E Ratio</div><div class="stat-value">{pe if isinstance(pe, str) else f'{pe:.1f}'}</div></div>
                <div class="stat-item"><div class="stat-label">ROE</div><div class="stat-value">{roe_val}</div></div>
                <div class="stat-item"><div class="stat-label">Market Cap</div><div class="stat-value">{mcap_val}</div></div>
                <div class="stat-item"><div class="stat-label">Debt to Equity</div><div class="stat-value">{de if isinstance(de, str) else f'{de:.2f}'}</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

else:
    st.error("Data load nahi ho saka. Stock symbol verify karein.")
    
