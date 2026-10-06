import base64
import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from PIL import Image

# AI part optional hai: ai_tools.py + GEMINI_API_KEY ho tabhi chalega
try:
    from ai_tools import ask_ai, build_context, get_fundamentals, get_news
    AI_OK = True
except Exception:
    AI_OK = False

st.set_page_config(page_title="Pro Screener", page_icon="⚡", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 2.5rem; padding-bottom: 3rem; max-width: 1200px;}
.app-title {font-size: 1.7rem; font-weight: 800; margin-bottom: 0.1rem;
  background: linear-gradient(90deg,#22d3ee,#4ade80);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;}
.app-sub {color: #94a3b8; font-size: 0.85rem; margin-bottom: 1rem;}
[data-testid="stHeader"] {background: transparent;}
[data-testid="stMetric"] {background: rgba(17,26,46,0.85); border: 1px solid #1e2a44;
  padding: 14px 16px; border-radius: 14px;}
[data-testid="stMetricValue"] {font-size: 1.9rem; font-weight: 700;}
.stButton > button {border-radius: 10px; border: 1px solid #1e2a44; font-weight: 600;}
.stButton > button[kind="primary"] {background: linear-gradient(90deg,#06b6d4,#22c55e);
  border: none; color: #04121f;}
.stTabs [data-baseweb="tab-list"] {gap: 6px;}
.stTabs [data-baseweb="tab"] {background: rgba(17,26,46,0.85); border-radius: 10px 10px 0 0; padding: 8px 14px;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius: 14px;}
h2, h3 {font-size: 1.25rem !important; margin-top: 0.8rem;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

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
        f"<div style='background:{COLORS[verdict]};padding:12px;border-radius:12px;"
        f"text-align:center;color:white;margin-bottom:8px;box-shadow:0 2px 8px rgba(0,0,0,.35)'><small>{label}</small>"
        f"<br><b>{verdict}</b></div>", unsafe_allow_html=True)


def esc(text: str) -> str:
    """Streamlit markdown me $ ko math samajhta hai, isliye escape karo."""
    return text.replace("$", "\\$")


def summary_hl(df, sc, cur) -> str:
    cur = esc(cur)
    l = df.iloc[-1]
    trend = "Bullish (tezi)" if l["Close"] > l["SMA50"] else "Bearish (mandi)"
    rsi = l["RSI"]
    mom = ("Oversold (bohot gira hua)" if rsi < 30
           else "Overbought (bohot chadha hua)" if rsi > 70 else "Neutral (normal)")
    return (
        f"1. **Trend:** Stock abhi {trend} hai (SMA50: {cur}{l['SMA50']:.2f})\n\n"
        f"2. **Momentum (RSI):** {rsi:.1f} → {mom}\n\n"
        f"3. **Support/Resistance:** 20 din ka low {cur}{df['Low'].tail(20).min():.2f}, "
        f"high {cur}{df['High'].tail(20).max():.2f}\n\n"
        f"4. **Uthal-puthal (ATR):** {cur}{l['ATR']:.2f} per candle\n\n"
        f"**Verdict:** {sc['verdict']} (score {sc['score']:+.1f})"
    )


def price_chart(df, name, days, style):
    d = df.tail(days)
    fig = go.Figure()
    if style == "Candle":
        fig.add_candlestick(x=d.index, open=d["Open"], high=d["High"], low=d["Low"],
                            close=d["Close"], name=name)
    else:
        fig.add_scatter(x=d.index, y=d["Close"], name="Price",
                        line=dict(width=2.4, color="#22d3ee"))
    for col, color in (("SMA20", "#f59e0b"), ("SMA50", "#3b82f6"), ("SMA200", "#a855f7")):
        fig.add_scatter(x=d.index, y=d[col], name=col, line=dict(width=1.2, color=color))
    fig.update_layout(height=380, xaxis_rangeslider_visible=False, dragmode=False,
                      margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h"),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def gauge(score_val, verdict):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score_val,
        number={"font": {"size": 34}, "valueformat": "+.0f"},
        title={"text": verdict, "font": {"size": 22}},
        gauge={
            "axis": {"range": [-5, 5], "tickvals": [-5, 0, 5],
                     "ticktext": ["Sell", "Neutral", "Buy"]},
            "bar": {"color": "#e2e8f0", "thickness": 0.25},
            "steps": [
                {"range": [-5, -3], "color": "#b91c1c"}, {"range": [-3, -1], "color": "#ef4444"},
                {"range": [-1, 1], "color": "#64748b"}, {"range": [1, 3], "color": "#22c55e"},
                {"range": [3, 5], "color": "#15803d"}],
        }))
    fig.update_layout(height=270, margin=dict(l=45, r=45, t=70, b=35),
                      paper_bgcolor="rgba(0,0,0,0)", font={"color": "#e2e8f0"})
    return fig


def plain_line(df, sc, tfv) -> str:
    v, rsi = sc["verdict"], df.iloc[-1]["RSI"]
    if v in ("Strong Buy", "Buy"):
        s = "Trend majboot hai. Dip aane par buy karna ek option hai, par stop-loss zaroor rakho."
    elif v == "Neutral":
        s = "Abhi direction clear nahi hai. Breakout ka wait karna better rahega."
    else:
        s = "Trend kamzor hai. Abhi naya buy risky hai; support hold hone ya trend palatne ka wait karo."
    if rsi < 30 and v in ("Sell", "Strong Sell", "Neutral"):
        s += " Lekin RSI oversold hai, isliye chhota bounce aa sakta hai."
    if rsi > 70 and v in ("Buy", "Strong Buy"):
        s += " Par RSI overbought hai, isliye naye buy me jaldi mat karo."
    vals = set(tfv.values())
    if vals & {"Buy", "Strong Buy"} and vals & {"Sell", "Strong Sell"}:
        s += " Alag-alag timeframe ke signal mix hain, isliye short aur long term ka plan alag rakho."
    return s


def lights(df, tfv) -> str:
    l = df.iloc[-1]
    p = l["Close"]
    n = int(p > l["SMA50"]) + int(p > (l["SMA200"] if not np.isnan(l["SMA200"]) else l["SMA50"]))
    rows = []
    rows.append({2: "🟢 **Trend:** upar hai (price dono average ke upar)",
                 1: "🟡 **Trend:** mixed hai (ek average ke upar, ek ke neeche)",
                 0: "🔴 **Trend:** neeche hai (price dono average ke neeche)"}[n])
    rows.append("🟢 **Momentum:** bullish (MACD upar)" if l["MACD"] > l["MACD_SIG"]
                else "🔴 **Momentum:** bearish (MACD neeche)")
    r = l["RSI"]
    rows.append(f"🟢 **RSI {r:.0f}:** oversold, bohot gira hua, bounce ho sakta hai" if r < 30
                else f"🔴 **RSI {r:.0f}:** overbought, bohot chadha hua, correction ka risk" if r > 70
                else f"🟡 **RSI {r:.0f}:** normal zone")
    ap = l["ATR"] / p * 100
    rows.append(f"🟢 **Uthal-puthal:** kam ({ap:.1f}% per candle)" if ap < 1.5
                else f"🟡 **Uthal-puthal:** medium ({ap:.1f}% per candle)" if ap < 3
                else f"🔴 **Uthal-puthal:** zyada ({ap:.1f}% per candle)")
    if tfv:
        b = sum(v in ("Buy", "Strong Buy") for v in tfv.values())
        s_ = sum(v in ("Sell", "Strong Sell") for v in tfv.values())
        icon = "🟢" if b > s_ else "🔴" if s_ > b else "🟡"
        rows.append(f"{icon} **Timeframes:** {len(tfv)} me se {b} Buy, {s_} Sell, baaki Neutral")
    return "\n".join(f"- {r}" for r in rows)


def levels_table(df, cur) -> str:
    cur = esc(cur)
    l = df.iloc[-1]
    price, atr = l["Close"], l["ATR"]
    sup, res = df["Low"].tail(20).min(), df["High"].tail(20).max()
    sl = price - 1.5 * atr
    tgt = max(res, price + 2 * atr) if res > price else price + 2 * atr
    rr = (tgt - price) / (price - sl)
    return (
        "| Level | Price | Matlab |\n|---|---|---|\n"
        f"| 🛡 Support | {cur}{sup:.2f} | Yahan tak gira to buyers aa sakte hain |\n"
        f"| 🚧 Resistance | {cur}{res:.2f} | Yahan upar rukawat aa sakti hai |\n"
        f"| ⛔ Stop-loss idea | {cur}{sl:.2f} | Isse neeche gira to nikal jao (1.5×ATR) |\n"
        f"| 🎯 Target idea | {cur}{tgt:.2f} | Pehla target |\n"
        f"| ⚖ Risk:Reward | 1 : {rr:.1f} | 1 se zyada ho to behtar |"
    )


# ---------- WALLPAPER ----------
WALLPAPERS = {
    "Plain Dark": "#0b1220",
    "Aurora": "linear-gradient(135deg,#0f2027,#203a43,#2c5364)",
    "Sunset": "linear-gradient(135deg,#1a0b2e,#5b2a86,#c2410c)",
    "Forest": "linear-gradient(135deg,#052e16,#14532d,#0f172a)",
    "Ocean": "linear-gradient(135deg,#020617,#1e3a8a,#0e7490)",
}
DEFAULT_WALLPAPER = "Aurora"   # <- app khulte hi ye wallpaper dikhega, yahan naam badal sakte ho


def image_to_data_uri(file) -> str:
    img = Image.open(file).convert("RGB")
    img.thumbnail((1080, 1920))                     # chhota karo taaki app slow na ho
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def apply_wallpaper(bg: str, dim=None):
    if dim is not None:   # photo: upar dark overlay lagao taaki text padha jaye
        overlay = f"rgba(11,18,32,{dim})"
        bg = f"linear-gradient({overlay},{overlay}), {bg} center / cover no-repeat fixed"
    st.markdown(f"<style>.stApp {{background: {bg} !important;}}</style>",
                unsafe_allow_html=True)


# ---------- STATE ----------
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

st.markdown("<div class='app-title'>⚡ Pro Investment Terminal</div>"
            "<div class='app-sub'>NSE + Global stocks • Technical screener • AI analysis</div>",
            unsafe_allow_html=True)

with st.expander("🎨 Wallpaper / Theme"):
    mode = st.radio("Wallpaper type", ["Preset", "Photo URL", "Upload photo"], horizontal=True)
    bg, dim = WALLPAPERS[DEFAULT_WALLPAPER], None
    if mode == "Preset":
        names = list(WALLPAPERS)
        pick = st.selectbox("Preset chuno", names, index=names.index(DEFAULT_WALLPAPER))
        bg = WALLPAPERS[pick]
    else:
        dim = st.slider("Dark overlay (text padhne ke liye)", 0.0, 0.9, 0.6, 0.05)
        if mode == "Photo URL":
            url = st.text_input("Image ka link (https://...jpg)")
            if url.startswith("http"):
                bg = f'url("{url.replace(chr(34), "%22")}")'
            else:
                dim = None
        else:
            up = st.file_uploader("Photo chuno", type=["png", "jpg", "jpeg", "webp"])
            if up:
                bg = f'url("{image_to_data_uri(up)}")'
            else:
                dim = None
apply_wallpaper(bg, dim)

tab1, tab2, tab3 = st.tabs(["📈 Stock Analysis", "🔎 Screener", "⭐ Watchlist"])

# ---------- TAB 1 ----------
with tab1:
    raw = st.text_input("Company ya symbol likho (Nvidia, Apple, TCS, NIFTYBEES)", "NIFTYBEES")
    symbol, sel_name = None, ""
    if raw.strip():
        opts = search_symbol(raw.strip())
        if opts:
            labels = [f"{s} — {n} ({e})" for s, n, e in opts]
            pick = st.selectbox("Sahi stock chuno", labels)
            symbol = opts[labels.index(pick)][0]
            sel_name = opts[labels.index(pick)][1]
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

            sc = score(daily)
            tfv = {}
            for label, (itv, per) in TIMEFRAMES.items():
                tf = load(symbol, itv, per)
                if tf is not None and len(tf) >= 55:
                    tfv[label] = score(add_indicators(tf))["verdict"]

            # ---- QUICK VIEW ----
            st.subheader("⚡ Quick View (30 second me samjho)")
            st.plotly_chart(gauge(sc["score"], sc["verdict"]),
                            use_container_width=True, config={"staticPlot": True})
            st.info(plain_line(daily, sc, tfv))
            st.markdown(lights(daily, tfv))
            with st.container(border=True):
                st.markdown("**📍 Important levels** (agar buy karna ho to, ye idea hai, advice nahi)")
                                if sc["verdict"] in ("Sell", "Strong Sell"):
                    st.warning("⚠️ Trend kamzor hai. Ye levels tabhi dekho jab trend palatne ka signal mile, abhi buy ka signal nahi hai.")

            st.subheader("⏱ Timeframe wise Verdict")
            cols = st.columns(2) + st.columns(2)
            for col, label in zip(cols, TIMEFRAMES):
                with col:
                    if label in tfv:
                        badge(label, tfv[label])
                    else:
                        st.caption(f"{label}: data kam hai")

            # ---- CHART ----
            r1, r2 = st.columns(2)
            rng = r1.radio("Range", ["1M", "3M", "6M", "1Y"], index=2, horizontal=True)
            style = r2.radio("Chart", ["Line", "Candle"], horizontal=True)
            days = {"1M": 22, "3M": 66, "6M": 132, "1Y": 252}[rng]
            hover = st.checkbox("Hover/tap se price dekhna hai (scroll atak sakta hai)")
            cfg = {"displayModeBar": False, "scrollZoom": False} if hover else {"staticPlot": True}
            st.plotly_chart(price_chart(daily, symbol, days, style),
                            use_container_width=True, config=cfg)

            # ---- DETAILS (collapsed, jise padhna ho wo khole) ----
            lv = daily.iloc[-1]
            hi52, lo52 = daily["High"].tail(252).max(), daily["Low"].tail(252).min()
            with st.expander("🔢 Aur numbers (52W High/Low, RSI, ATR)"):
                k1, k2 = st.columns(2)
                k1.metric("52W High", f"{cur}{hi52:,.2f}", f"{(price / hi52 - 1) * 100:.1f}%",
                          help="Pichle 1 saal ka sabse ucha price. % = abhi ke price se kitna neeche.")
                k2.metric("52W Low", f"{cur}{lo52:,.2f}", f"{(price / lo52 - 1) * 100:+.1f}%",
                          help="Pichle 1 saal ka sabse neecha price.")
                k3, k4 = st.columns(2)
                k3.metric("RSI (14)", f"{lv['RSI']:.1f}",
                          help="30 se neeche = bohot gira hua (oversold). 70 se upar = bohot chadha hua (overbought).")
                k4.metric("ATR", f"{cur}{lv['ATR']:.2f}",
                          help="Ek din me price average kitna upar-neeche hota hai. Stop-loss set karne me kaam aata hai.")

            with st.expander("📖 Detail me padho"):
                st.markdown(summary_hl(daily, sc, cur))
                st.caption("Signals: " + " • ".join(sc["notes"]))

            with st.expander("📚 Shabd samjho (SMA, RSI, MACD...)"):
                st.markdown(
                    "- **SMA (Moving Average):** pichhle X din ka average price. Price iske upar = tezi, neeche = mandi.\n"
                    "- **SMA50 / SMA200:** 50 aur 200 din ka average. SMA200 lambe trend ki line hai.\n"
                    "- **RSI:** 0 se 100 ka meter. 30 se neeche = bohot gira, 70 se upar = bohot chadha.\n"
                    "- **MACD:** momentum batata hai. Signal line ke upar = tezi ka josh.\n"
                    "- **ATR:** price ki daily uthal-puthal. Zyada ATR = zyada risk.\n"
                    "- **Support:** wo level jahan se price pehle ghoom kar upar gaya.\n"
                    "- **Resistance:** wo level jahan price pehle ruk kar neeche aaya.\n"
                    "- **Stop-loss:** wo price jahan loss cut karke nikal jaate hain.")

            # ---- AI ----
            if AI_OK:
                st.subheader("🤖 AI Samjhaye (Hinglish)")
                ctx = build_context(symbol, daily, sc, sel_name)
                fund, news = get_fundamentals(symbol), get_news(symbol, sel_name)
                st.caption(f"Data: Fundamentals {'✅' if fund else '❌'} • "
                           f"News {'✅ ' + str(len(news)) if news else '❌'}")
                st.session_state.setdefault("ai_out", {})
                if st.button("AI se analysis karo"):
                    with st.spinner("AI soch raha hai..."):
                        st.session_state.ai_out[symbol] = ask_ai(
                                         ctx, "Is stock ka simple analysis do.", fmt=True)
                if symbol in st.session_state.ai_out:
                    st.markdown(esc(st.session_state.ai_out[symbol]))
                if news:
                    with st.expander("📰 Latest news headlines"):
                        for n_ in news:
                            st.markdown(f"- {esc(n_)}")

                q = st.text_input(f"{symbol} ke baare me kuch bhi poocho", key=f"q_{symbol}")
                if q:
                    with st.spinner("AI soch raha hai..."):
                        st.markdown(esc(ask_ai(ctx, q)))

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
