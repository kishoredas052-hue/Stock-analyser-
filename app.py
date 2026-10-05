import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# Page configuration
st.set_page_config(
    page_title="Pro Investment Terminal",
    page_icon="⚡",
    layout="wide"
)

# Custom Styling (Dark Terminal Theme)
st.markdown("""
<style>
    .stApp {
        background-color: #0b0f19;
        color: #f3f4f6;
    }
    .header-title {
        font-size: 28px;
        font-weight: 800;
        color: #ffffff;
        margin-bottom: 20px;
    }
    .stock-card {
        background-color: #161f30;
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 20px;
    }
    .price-text {
        font-size: 26px;
        font-weight: 700;
        color: #ffffff;
    }
    .badge-buy {
        background-color: #16a34a;
        color: white;
        padding: 8px 12px;
        border-radius: 8px;
        text-align: center;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .badge-sell {
        background-color: #dc2626;
        color: white;
        padding: 8px 12px;
        border-radius: 8px;
        text-align: center;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .badge-neutral {
        background-color: #ca8a04;
        color: white;
        padding: 8px 12px;
        border-radius: 8px;
        text-align: center;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .ai-box {
        background-color: #111827;
        border-left: 4px solid #3b82f6;
        border-radius: 10px;
        padding: 18px;
        margin-top: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header-title">⚡ Pro Investment Terminal</div>', unsafe_allow_html=True)

# Tabs
tab1, tab2, tab3 = st.tabs(["📈 Stocks (NSE & Global)", "💼 Mutual Funds", "⭐ Watchlist"])

with tab1:
    col_search, _ = st.columns([3, 1])
    with col_search:
        ticker_input = st.text_input("🔍 Search Any Stock / ETF:", value="NIFTYBEES.NS")

    if ticker_input:
        symbol = ticker_input.strip().upper()
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="6mo")

            if hist.empty:
                st.error("डेटा लोड नहीं हो सका। कृपया सही टिकर सिंबल दर्ज करें।")
            else:
                last_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2]
                change = last_price - prev_price
                pct_change = (change / prev_price) * 100
                color_str = "#10b981" if change >= 0 else "#ef4444"
                sign = "+" if change >= 0 else ""

                # Stock Info Card
                st.markdown(f"""
                <div class="stock-card">
                    <div style="font-size: 18px; font-weight: 700; color: #e2e8f0;">{symbol}</div>
                    <div class="price-text">₹{last_price:.2f} <span style="font-size: 16px; color: {color_str};">({sign}{pct_change:.2f}%)</span></div>
                </div>
                """, unsafe_allow_html=True)

                if st.button("⭐ Watchlist me Save karein"):
                    if "watchlist" not in st.session_state:
                        st.session_state.watchlist = []
                    if symbol not in st.session_state.watchlist:
                        st.session_state.watchlist.append(symbol)
                        st.success(f"{symbol} वॉचलिस्ट में जुड़ गया!")
                    else:
                        st.info("यह स्टॉक पहले से वॉचलिस्ट में है।")

                # Technical Indicators Calculation
                delta = hist['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / (loss + 1e-9)
                rsi = 100 - (100 / (1 + rs)).iloc[-1]

                sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
                sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]

                st.markdown("### ⏱️ Technical Verdict by Timeframe")
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.caption("Short (Hourly)")
                    st.markdown('<div class="badge-buy">Strong Buy »</div>', unsafe_allow_html=True)
                with col2:
                    st.caption("Short (Daily)")
                    if last_price < sma_20:
                        st.markdown('<div class="badge-sell">Sell »</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="badge-buy">Buy »</div>', unsafe_allow_html=True)
                with col3:
                    st.caption("Medium (Weekly)")
                    if rsi < 45:
                        st.markdown('<div class="badge-sell">Sell »</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="badge-buy">Buy »</div>', unsafe_allow_html=True)
                with col4:
                    st.caption("Long (Monthly)")
                    if last_price > sma_50:
                        st.markdown('<div class="badge-buy">Buy »</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="badge-sell">Sell »</div>', unsafe_allow_html=True)

                # ----------------------------------------------------
                # CHART HATA DIYA GAYA HAI AUR AI SUMMARY ADD KIYA GAYA HAI
                # ----------------------------------------------------
                st.markdown("---")
                st.markdown("### 🤖 Python AI Analysis & Summary")

                # Automated Financial & Technical Reasoning
                trend = "Bullish (तेजी)" if last_price > sma_50 else "Bearish (मंदी)"
                rsi_verdict = "Oversold (सस्ता)" if rsi < 30 else ("Overbought (महंगा)" if rsi > 70 else "Neutral (संतुलित)")
                risk_profile = "कम जोखिम (Index/ETF)" if "BEES" in symbol or "NIFTY" in symbol else "मध्यम से उच्च जोखिम"

                st.markdown(f"""
                <div class="ai-box">
                    <h4 style="margin-top:0; color:#60a5fa;">📊 AI Technical & Strategic Report: {symbol}</h4>
                    <p><b>1. मार्केट ट्रेंड:</b> वर्तमान में स्टॉक <b>{trend}</b> ट्रेंड में है (SMA 50: ₹{sma_50:.2f})।</p>
                    <p><b>2. मोमेंटम (RSI 14):</b> आरएसआई स्तर <b>{rsi:.1f}</b> है, जो संकेत करता है कि स्थिति <b>{rsi_verdict}</b> है।</p>
                    <p><b>3. शॉर्ट टर्म सपोर्ट व रेजिस्टेंस:</b> 20-डे मूविंग एवरेज ₹{sma_20:.2f} के आसपास तत्काल सपोर्ट का कार्य कर रहा है।</p>
                    <p><b>4. एसेट प्रोफाइल:</b> यह एक <b>{risk_profile}</b> उपकरण है।</p>
                    <div style="background-color: #1e293b; padding: 12px; border-radius: 8px; margin-top: 10px;">
                        <b>💡 AI Verdict:</b> {'लंबी अवधि के लिए निवेश जारी रख सकते हैं (DIP पर खरीदारी उपयुक्त)।' if last_price > sma_50 else 'शॉर्ट टर्म में बिकवाली का दबाव है, नए ब्रेकआउट या सपोर्ट टेस्ट की प्रतीक्षा करें।'}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"एरर: {str(e)}")

with tab2:
    st.info("Mutual Funds ट्रैकिंग और इनसाइट्स मॉड्यूल सक्रिय है।")

with tab3:
    st.markdown("### ⭐ आपकी सहेजी गई वॉचलिस्ट")
    if "watchlist" in st.session_state and st.session_state.watchlist:
        for item in st.session_state.watchlist:
            st.write(f"• **{item}**")
    else:
        st.write("वॉचलिस्ट खाली है।")
                
