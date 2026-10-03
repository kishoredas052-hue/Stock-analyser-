import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from rapidfuzz import process, fuzz
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from google import genai

st.set_page_config(page_title="Global FinTrack & Analyzer", layout="wide")

# CSS Styling - Cards, Badges, Logos
st.markdown("""
<style>
.metric-card {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 14px;
    margin-bottom: 12px;
    color: white;
}
.signal-box {
    padding: 10px 4px;
    border-radius: 8px;
    text-align: center;
    font-weight: bold;
    font-size: 13px;
    margin-bottom: 6px;
}
.strong-buy { background-color: #15803d; color: #ffffff; }
.buy { background-color: #22c55e; color: #000000; }
.neutral { background-color: #475569; color: #f8fafc; }
.sell { background-color: #ef4444; color: #ffffff; }
.strong-sell { background-color: #991b1b; color: #ffffff; }
.logo-img {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    vertical-align: middle;
    margin-right: 10px;
    background-color: #fff;
    padding: 2px;
}
</style>
""", unsafe_allow_html=True)

# Session state for Watchlist
if "watchlist" not in st.session_state:
    st.session_state.watchlist = ["TATAMOTORS.NS", "RELIANCE.NS", "AAPL"]

# Preset database for smart fuzzy search & logo mapping
STOCK_DB = {
    "TATAMOTORS": {"name": "Tata Motors Ltd", "ticker": "TATAMOTORS.NS", "domain": "tatamotors.com", "type": "NSE"},
    "RELIANCE": {"name": "Reliance Industries", "ticker": "RELIANCE.NS", "domain": "ril.com", "type": "NSE"},
    "TCS": {"name": "Tata Consultancy Services", "ticker": "TCS.NS", "domain": "tcs.com", "type": "NSE"},
    "INFY": {"name": "Infosys Ltd", "ticker": "INFY.NS", "domain": "infosys.com", "type": "NSE"},
    "HDFCBANK": {"name": "HDFC Bank Ltd", "ticker": "HDFCBANK.NS", "domain": "hdfcbank.com", "type": "NSE"},
    "SBIN": {"name": "State Bank of India", "ticker": "SBIN.NS", "domain": "sbi.co.in", "type": "NSE"},
    "ICICIBANK": {"name": "ICICI Bank Ltd", "ticker": "ICICIBANK.NS", "domain": "icicibank.com", "type": "NSE"},
    "BHARTIARTL": {"name": "Bharti Airtel", "ticker": "BHARTIARTL.NS", "domain": "airtel.in", "type": "NSE"},
    "ITC": {"name": "ITC Ltd", "ticker": "ITC.NS", "domain": "itcportal.com", "type": "NSE"},
    "AAPL": {"name": "Apple Inc", "ticker": "AAPL", "domain": "apple.com", "type": "US"},
    "TSLA": {"name": "Tesla Inc", "ticker": "TSLA", "domain": "tesla.com", "type": "US"},
    "GOOGL": {"name": "Alphabet (Google)", "ticker": "GOOGL", "domain": "google.com", "type": "US"},
    "MSFT": {"name": "Microsoft Corp", "ticker": "MSFT", "domain": "microsoft.com", "type": "US"},
    "NVDA": {"name": "NVIDIA Corp", "ticker": "NVDA", "domain": "nvidia.com", "type": "US"},
    "AMZN": {"name": "Amazon.com Inc", "ticker": "AMZN", "domain": "amazon.com", "type": "US"}
}

def resolve_ticker(query):
    clean = query.strip().upper().replace(" ", "").replace(".NS", "")
    if clean in STOCK_DB:
        return STOCK_DB[clean]["ticker"], STOCK_DB[clean]["name"], STOCK_DB[clean]["domain"]
    
    # Fuzzy match for spelling mistakes (e.g. Tatamoters -> TATAMOTORS)
    match, score, _ = process.extractOne(clean, list(STOCK_DB.keys()), scorer=fuzz.WRatio)
    if score >= 70:
        return STOCK_DB[match]["ticker"], STOCK_DB[match]["name"], STOCK_DB[match]["domain"]
    
    # Default fallback
    if "." not in query and len(query) <= 12:
        return f"{clean}.NS", clean, ""
    return clean, clean, ""

def calculate_signal(df):
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

# Sidebar API settings
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("Gemini API Key:", type="password")
    st.caption("Free key: aistudio.google.com")

st.title("🌐 Global FinTrack & Screener")

tab_stocks, tab_mf, tab_watchlist = st.tabs(["📈 Stocks (NSE & Global)", "💼 Indian Mutual Funds", "⭐ My Watchlist"])

# ================= TAB 1: STOCKS =================
with tab_stocks:
    default_options = ["TATAMOTORS", "RELIANCE", "TCS", "AAPL", "NVDA"]
    selected_items = st.multiselect(
        "Search or Select Stocks (Spelling-tolerant & Multi-select):",
        options=list(STOCK_DB.keys()),
        default=default_options[:4]
    )

    custom_search = st.text_input("Or type custom ticker / spelling (e.g. 'tatamoters', 'msft', 'infy'):", "")
    if custom_search:
        resolved_t, _, _ = resolve_ticker(custom_search)
        if resolved_t not in selected_items:
            selected_items.append(resolved_t)

    if selected_items:
        st.markdown("### 📊 Top Overview Cards")
        cols = st.columns(min(len(selected_items), 4))
        
        stock_data_map = {}
        for idx, item in enumerate(selected_items):
            tkr, comp_name, domain = resolve_ticker(item)
            try:
                data = yf.Ticker(tkr).history(period="6mo")
                if not data.empty and len(data) > 1:
                    curr = data['Close'].iloc[-1]
                    chg = ((curr - data['Close'].iloc[-2]) / data['Close'].iloc[-2]) * 100
                    sig_label, sig_cls = calculate_signal(data)
                    stock_data_map[tkr] = {"name": comp_name, "data": data, "curr": curr, "chg": chg, "signal": (sig_label, sig_cls), "domain": domain}
                    
                    with cols[idx % 4]:
                        logo_html = f"<img src='https://logo.clearbit.com/{domain}' class='logo-img' onerror=\"this.style.display='none'\">" if domain else ""
                        currency = "$" if not tkr.endswith(".NS") else "₹"
                        st.markdown(f"""
                        <div class="metric-card">
                            {logo_html}<b>{comp_name}</b><br>
                            <span style="font-size:18px; font-weight:bold;">{currency}{curr:.2f}</span>
                            <span style="color:{'#22c55e' if chg>=0 else '#ef4444'}; font-size:13px;"> ({chg:+.2f}%)</span>
                            <div class="signal-box {sig_cls}" style="margin-top:8px;">{sig_label}</div>
                        </div>
                        """, unsafe_allow_html=True)
            except Exception:
                pass

        st.write("---")
        # Detail View Selector
        active_ticker = st.selectbox("Select a stock from above for Deep-Dive Analysis:", list(stock_data_map.keys()))
        
        if active_ticker in stock_data_map:
            stk_info = stock_data_map[active_ticker]
            df = stk_info["data"]
            curr = stk_info["curr"]
            chg = stk_info["chg"]

            # Watchlist Add button
            c_head, c_btn = st.columns([3, 1])
            with c_head:
                st.subheader(f"🔍 Deep Analysis: {stk_info['name']} ({active_ticker})")
            with c_btn:
                if st.button("⭐ Add to Watchlist"):
                    if active_ticker not in st.session_state.watchlist:
                        st.session_state.watchlist.append(active_ticker)
                        st.success("Added!")

            # Multi-Timeframe Signals
            stk_obj = yf.Ticker(active_ticker)
            try: df_wk = stk_obj.history(period="2y", interval="1wk")
            except: df_wk = df
            try: df_mo = stk_obj.history(period="5y", interval="1mo")
            except: df_mo = df

            lbl_d, cls_d = calculate_signal(df)
            lbl_w, cls_w = calculate_signal(df_wk)
            lbl_m, cls_m = calculate_signal(df_mo)

            s1, s2, s3 = st.columns(3)
            with s1: st.markdown(f"**Short (Daily)**<div class='signal-box {cls_d}'>{lbl_d}</div>", unsafe_allow_html=True)
            with s2: st.markdown(f"**Medium (Weekly)**<div class='signal-box {cls_w}'>{lbl_w}</div>", unsafe_allow_html=True)
            with s3: st.markdown(f"**Long (Monthly)**<div class='signal-box {cls_m}'>{lbl_m}</div>", unsafe_allow_html=True)

            # Chart
            st.line_chart(df['Close'])

            # Fundamentals
            info = stk_obj.info or {}
            pe = info.get('trailingPE') or info.get('forwardPE') or "N/A"
            roe = info.get('returnOnEquity')
            roe_val = f"{roe * 100:.2f}%" if isinstance(roe, (int, float)) else "N/A"

            f1, f2 = st.columns(2)
            f1.write(f"**P/E Ratio:** `{pe if isinstance(pe, str) else round(pe, 2)}`")
            f2.write(f"**ROE:** `{roe_val}`")

            # AI Report
            if api_key:
    if st.button("🤖 Generate AI Analysis Report"):
        with st.spinner("AI डेटा प्रोसेस कर रहा है..."):
            try:
                client = genai.Client(api_key=api_key.strip())
                prompt = f"Analyze stock {stk_info['name']} ({active_ticker}). Price: {curr}, Daily: {lbl_d}, Weekly: {lbl_w}, Monthly: {lbl_m}, PE: {pe}, ROE: {roe_val}. Give clear short-term swing levels and long-term advice in concise Hinglish."
                res = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                st.markdown(res.text)
            except Exception as err:
                st.error(f"API Key अमान्य या इनएक्टिव है। कृपया AI Studio से नई की बनाकर डालें। विवरण: {err}")
                

# ================= TAB 2: MUTUAL FUNDS =================
with tab_mf:
    st.subheader("💼 Indian Mutual Funds (Direct / Regular)")
    
    # Curated Popular Schemes with AMFI Codes
    POPULAR_FUNDS = {
        "Parag Parikh Flexi Cap Fund - Direct": 122639,
        "Nippon India Small Cap Fund - Direct": 118778,
        "Quant Small Cap Fund - Direct": 120828,
        "HDFC Mid-Cap Opportunities Fund - Direct": 118989,
        "Mirae Asset Large & Midcap Fund - Direct": 118834,
        "SBI Bluechip Fund - Direct": 119598
    }

    selected_fund_name = st.selectbox("Select or Search Scheme:", list(POPULAR_FUNDS.keys()))
    scheme_code = POPULAR_FUNDS[selected_fund_name]

    if st.button("📊 Fetch Fund Data"):
        with st.spinner("Fetching AMFI NAV details..."):
            try:
                res = requests.get(f"https://api.mfapi.in/mf/{scheme_code}").json()
                meta = res.get("meta", {})
                nav_data = res.get("data", [])
                
                if nav_data:
                    curr_nav = float(nav_data[0]["nav"])
                    prev_nav = float(nav_data[1]["nav"])
                    nav_chg = ((curr_nav - prev_nav) / prev_nav) * 100
                    
                    m1, m2 = st.columns(2)
                    m1.metric("Current NAV", f"₹{curr_nav:.2f}", f"{nav_chg:+.2f}%")
                    m2.write(f"**Fund House:** {meta.get('fund_house')}\n\n**Category:** {meta.get('scheme_category')}")

                    # NAV Chart
                    df_nav = pd.DataFrame(nav_data[:365])
                    df_nav["date"] = pd.to_datetime(df_nav["date"], format="%d-%m-%Y")
                    df_nav["nav"] = df_nav["nav"].astype(float)
                    df_nav = df_nav.sort_values("date")
                    st.line_chart(df_nav.set_index("date")["nav"])

                    if api_key:
                        if st.button("🤖 AI Review for SIP / Lumpsum"):
                            client = genai.Client(api_key=api_key)
                            mf_prompt = f"Review Mutual Fund: {selected_fund_name}, Category: {meta.get('scheme_category')}, Current NAV: {curr_nav}. Explain suitability for 5-10 year SIP in clean Hinglish."
                            mf_res = client.models.generate_content(model="gemini-2.5-flash", contents=mf_prompt)
                            st.markdown(mf_res.text)
            except Exception as e:
                st.error(f"Failed to fetch MF data: {e}")

# ================= TAB 3: WATCHLIST =================
with tab_watchlist:
    st.subheader("⭐ Saved Watchlist")
    if st.session_state.watchlist:
        w_cols = st.columns(min(len(st.session_state.watchlist), 4))
        for idx, item in enumerate(st.session_state.watchlist):
            with w_cols[idx % 4]:
                st.info(f"📌 **{item}**")
        if st.button("Clear Watchlist"):
            st.session_state.watchlist = []
            st.rerun()
    else:
        st.write("Aapki watchlist abhi khali hai. Stocks tab me jakar ⭐ Add to Watchlist dabayein.")
                            
        
