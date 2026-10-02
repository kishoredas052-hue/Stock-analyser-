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

            # Fetch Fundamental Info with Fallbacks
            info = stock.info or {}
            fast = getattr(stock, 'fast_info', {})
            
            # P/E Ratio Fallback
            pe = info.get('trailingPE') or info.get('forwardPE')
            pe_val = f"{pe:.2f}" if isinstance(pe, (int, float)) else "N/A"
            
            # 52 Week High / Low
            high_52 = fast.get('year_high') or info.get('fiftyTwoWeekHigh', 'N/A')
            low_52 = fast.get('year_low') or info.get('fiftyTwoWeekLow', 'N/A')
            
            # Market Cap
            mcap = fast.get('market_cap') or info.get('marketCap')
            if isinstance(mcap, (int, float)):
                mcap_cr = f"₹{mcap / 10000000:.0f} Cr"
            else:
                mcap_cr = "N/A"

            # ROE & Debt/Equity
            roe = info.get('returnOnEquity')
            roe_val = f"{roe * 100:.2f}%" if isinstance(roe, (int, float)) else "N/A"
            
            debt_equity = info.get('debtToEquity')
            de_val = f"{debt_equity:.2f}" if isinstance(debt_equity, (int, float)) else "N/A"

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
                st.write(f"**Market Cap:** `{mcap_cr}`")
                st.write(f"**P/E Ratio:** `{pe_val}`")
                st.write(f"**52W High:** `₹{high_52:.2f}`" if isinstance(high_52, (int, float)) else f"**52W High:** `{high_52}`")
                st.write(f"**52W Low:** `₹{low_52:.2f}`" if isinstance(low_52, (int, float)) else f"**52W Low:** `{low_52}`")
                st.write(f"**ROE:** `{roe_val}`")
                st.write(f"**Debt/Equity:** `{de_val}`")

        else:
            st.warning("डेटा नहीं मिला। सही NSE सिंबल दर्ज करें।")
    except Exception as e:
        st.error(f"डेटा फेच करने में समस्या आई: {e}")
        
