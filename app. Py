import streamlit as st
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator

st.set_page_config(page_title="Stock Analyzer", layout="centered")
st.title("📈 Stock Auto-Analyzer")

ticker_input = st.text_input("NSE Stock (e.g. TATAMOTORS, RELIANCE, INFY):", "TCS").upper().strip()

if ticker_input:
    ticker = f"{ticker_input}.NS"
    stock = yf.Ticker(ticker)
    
    try:
        df = stock.history(period="6mo")
        if not df.empty:
            curr_price = df['Close'].iloc[-1]
            prev_price = df['Close'].iloc[-2]
            pct_chg = ((curr_price - prev_price) / prev_price) * 100
            
            st.metric(label=f"{ticker_input} (LTP)", value=f"₹{curr_price:.2f}", delta=f"{pct_chg:.2f}%")

            # Technical Indicators
            df['RSI'] = RSIIndicator(df['Close'], window=14).rsi()
            df['SMA_50'] = SMAIndicator(df['Close'], window=50).sma_indicator()
            
            latest_rsi = df['RSI'].iloc[-1]
            latest_sma = df['SMA_50'].iloc[-1]

            # Fundamental Info
            info = stock.info
            pe = info.get('trailingPE', 'N/A')
            roe = info.get('returnOnEquity', 'N/A')
            debt_equity = info.get('debtToEquity', 'N/A')

            st.write("---")
            st.subheader("Automated Analysis Verdict")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 📊 Technical")
                st.write(f"**RSI (14):** `{latest_rsi:.1f}`")
                if latest_rsi < 35:
                    st.success("🟢 Oversold (Bullish Signal)")
                elif latest_rsi > 70:
                    st.error("🔴 Overbought (Bearish Risk)")
                else:
                    st.info("⚪ Neutral Range")

                trend = "Bullish (Above 50 SMA)" if curr_price > latest_sma else "Bearish (Below 50 SMA)"
                st.write(f"**Trend:** {trend}")

            with col2:
                st.markdown("### 🏢 Fundamental")
                st.write(f"**P/E Ratio:** `{pe}`")
                st.write(f"**ROE:** `{roe * 100:.2f}%`" if isinstance(roe, (int, float)) else f"**ROE:** {roe}")
                st.write(f"**Debt/Equity:** `{debt_equity}`")

        else:
            st.warning("डेटा नहीं मिला। सही NSE सिंबल दर्ज करें।")
    except Exception:
        st.error("डेटा फेच करने में समस्या आई।")
