import streamlit as st
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, EMAIndicator, MACD
from google import genai

st.set_page_config(page_title="Pro Stock Screener", layout="centered")

# कस्टम स्टाइलिंग (स्क्रीनशॉट जैसे बॉक्सेस के लिए)
st.markdown("""
<style>
.signal-box {
    padding: 12px 6px;
    border-radius: 8px;
    text-align: center;
    font-weight: bold;
    font-size: 14px;
    margin-bottom: 8px;
}
.strong-buy { background-color: #1b5e20; color: #ffffff; border: 1px solid #4caf50; }
.buy { background-color: #2e7d32; color: #ffffff; }
.neutral { background-color: #374151; color: #e5e7eb; border: 1px solid #4b5563; }
.sell { background-color: #c62828; color: #ffffff; }
.strong-sell { background-color: #7f1d1d; color: #ffffff; border: 1px solid #ef4444; }
.timeframe-label {
    text-align: center;
    font-size: 12px;
    color: #9ca3af;
    margin-bottom: 4px;
}
</style>
""", unsafe_allow_html=True)

# साइडबार
with st.sidebar:
    st.header("⚙️ AI Assistant Key")
    api_key = st.text_input("Gemini API Key (Optional):", type="password")
    st.caption("Free key available at aistudio.google.com")

st.title("📊 Technical & Fundamental Screener")

ticker_input = st.text_input("Enter NSE Stock (e.g. TATAMOTORS, RELIANCE, SBIN):", "TCS").upper().strip()

def calculate_timeframe_signal(df):
    if df is None or len(df) < 30:
        return "Neutral", "neutral", 0, 0
    
    close = df['Close']
    rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
    sma20 = SMAIndicator(close, window=20).sma_indicator().iloc[-1]
    sma50 = SMAIndicator(close, window=50).sma_indicator().iloc[-1] if len(close) >= 50 else sma20
    curr = close.iloc[-1]
    
    buy_signals = 0
    sell_signals = 0
    
    # RSI Signals
    if rsi < 35: buy_signals += 2
    elif rsi < 45: buy_signals += 1
    elif rsi > 70: sell_signals += 2
    elif rsi > 55: sell_signals += 1
    
    # Moving Average Signals
    if curr > sma20: buy_signals += 1
    else: sell_signals += 1
    
    if curr > sma50: buy_signals += 2
    else: sell_signals += 2

    score = buy_signals - sell_signals
    if score >= 3:
        return "Strong Buy ↗", "strong-buy", buy_signals, sell_signals
    elif score >= 1:
        return "Buy ↗", "buy", buy_signals, sell_signals
    elif score <= -3:
        return "Strong Sell ↘", "strong-sell", buy_signals, sell_signals
    elif score <= -1:
        return "Sell ↘", "sell", buy_signals, sell_signals
    else:
        return "Neutral →", "neutral", buy_signals, sell_signals

if ticker_input:
    ticker = f"{ticker_input}.NS"
    stock = yf.Ticker(ticker)
    
    try:
        df_daily = stock.history(period="1y", interval="1d")
        df_weekly = stock.history(period="2y", interval="1wk")
        df_monthly = stock.history(period="5y", interval="1mo")
        df_hourly = stock.history(period="1mo", interval="1h")

        if not df_daily.empty:
            curr_price = df_daily['Close'].iloc[-1]
            prev_price = df_daily['Close'].iloc[-2]
            pct_chg = ((curr_price - prev_price) / prev_price) * 100
            
            st.metric(
                label=f"{ticker_input} (LTP)", 
                value=f"₹{curr_price:.2f}", 
                delta=f"{pct_chg:.2f}%"
            )

            # सिग्नल कैलकुलेट करें
            lbl_hourly, cls_hourly, b_h, s_h = calculate_timeframe_signal(df_hourly)
            lbl_daily, cls_daily, b_d, s_d = calculate_timeframe_signal(df_daily)
            lbl_weekly, cls_weekly, b_w, s_w = calculate_timeframe_signal(df_weekly)
            lbl_monthly, cls_monthly, b_m, s_m = calculate_timeframe_signal(df_monthly)

            st.write("---")
            st.markdown("### ⏱️ Technical Verdict by Timeframe")

            # 4 कॉलम में शॉर्ट-टर्म से लॉन्ग-टर्म बॉक्सेस
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown('<div class="timeframe-label">Short (Hourly)</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="signal-box {cls_hourly}">{lbl_hourly}</div>', unsafe_allow_html=True)
            with c2:
                st.markdown('<div class="timeframe-label">Short (Daily)</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="signal-box {cls_daily}">{lbl_daily}</div>', unsafe_allow_html=True)
            with c3:
                st.markdown('<div class="timeframe-label">Medium (Weekly)</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="signal-box {cls_weekly}">{lbl_weekly}</div>', unsafe_allow_html=True)
            with c4:
                st.markdown('<div class="timeframe-label">Long (Monthly)</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="signal-box {cls_monthly}">{lbl_monthly}</div>', unsafe_allow_html=True)

            # समरी स्कोर (Buy vs Sell इंडीकेटर्स की संख्या)
            st.markdown("#### 📋 Indicator Summary (Daily)")
            tot_buy = b_d
            tot_sell = s_d
            st.write(f"- **Buy Indicators:** `{tot_buy}`")
            st.write(f"- **Sell Indicators:** `{tot_sell}`")

            # फंडामेंटल डेटा
            info = stock.info or {}
            pe = info.get('trailingPE') or info.get('forwardPE') or "N/A"
            roe = info.get('returnOnEquity')
            roe_val = f"{roe * 100:.2f}%" if isinstance(roe, (int, float)) else "N/A"

            st.write("---")
            st.markdown("### 🏢 Key Fundamentals")
            f1, f2 = st.columns(2)
            f1.write(f"- **P/E Ratio:** `{pe if isinstance(pe, str) else round(pe, 2)}`")
            f2.write(f"- **ROE:** `{roe_val}`")

            # AI Summary सेक्शन
            st.write("---")
            if api_key:
                client = genai.Client(api_key=api_key)
                if st.button("🤖 Generate AI Analysis Report"):
                    with st.spinner("AI डेटा प्रोसेस कर रहा है..."):
                        prompt = f"""
                        You are a certified professional stock analyst.
                        Analyze {ticker_input} based strictly on:
                        Price: ₹{curr_price:.2f} ({pct_chg:.2f}%)
                        Short Term (Hourly/Daily): {lbl_hourly} / {lbl_daily}
                        Medium Term (Weekly): {lbl_weekly}
                        Long Term (Monthly): {lbl_monthly}
                        P/E Ratio: {pe}, ROE: {roe_val}

                        Explain in concise professional Hinglish:
                        1. Short-term swing outlook vs Long-term investing outlook.
                        2. Key risk factors and entry levels.
                        """
                        res = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=prompt
                        )
                        st.markdown(res.text)
            else:
                st.info("💡 AI से विस्तृत विश्लेषण पाने के लिए साइडबार में Gemini API Key डाल सकते हैं।")

        else:
            st.warning("डेटा नहीं मिला। कृपया सही NSE सिंबल दर्ज करें।")
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        
