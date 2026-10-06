import streamlit as st
import yfinance as yf
from google import genai
from google.genai import types

# Free model. Agar 429/"limit 0" error aaye to AI Studio me dekho kaunsa model free hai aur yahan naam badlo.
MODEL = "gemini-3.5-flash"

SYSTEM = (
    "Tum ek stock market analyst assistant ho. Jawab Hindi (Devanagari + zaroorat ho to English terms) me do, "
    "chhote aur clear points me. Sirf diye gaye data ka use karo; jo data me nahi hai uska andaza mat lagao, "
    "bolo ki data nahi hai. Bull aur bear dono side batao. Ye educational analysis hai, "
    "financial advice nahi, ye ek line me yaad dilao."
)


def get_client():
    key = st.secrets.get("GEMINI_API_KEY", None)
    return genai.Client(api_key=key) if key else None


@st.cache_data(ttl=1800, show_spinner=False)
def get_fundamentals(symbol: str) -> dict:
    try:
        info = yf.Ticker(symbol).info
    except Exception:
        return {}
    keys = ["longName", "sector", "marketCap", "trailingPE", "priceToBook",
            "returnOnEquity", "debtToEquity", "dividendYield",
            "fiftyTwoWeekHigh", "fiftyTwoWeekLow"]
    return {k: info.get(k) for k in keys if info.get(k) is not None}


@st.cache_data(ttl=1800, show_spinner=False)
def get_news(symbol: str) -> list:
    try:
        items = yf.Ticker(symbol).news[:6]
    except Exception:
        return []
    titles = []
    for it in items:
        t = (it.get("content") or {}).get("title") or it.get("title")
        if t:
            titles.append(t)
    return titles


def build_context(symbol, df, sc) -> str:
    l = df.iloc[-1]
    tech = (
        f"Price {l['Close']:.2f}, SMA20 {l['SMA20']:.2f}, SMA50 {l['SMA50']:.2f}, "
        f"SMA200 {l['SMA200']:.2f}, RSI {l['RSI']:.1f}, MACD {l['MACD']:.3f} (signal {l['MACD_SIG']:.3f}), "
        f"ATR {l['ATR']:.2f}, 20-day low {df['Low'].tail(20).min():.2f}, "
        f"20-day high {df['High'].tail(20).max():.2f}. "
        f"Rule-based verdict: {sc['verdict']} (score {sc['score']:+.1f})."
    )
    fund = get_fundamentals(symbol)
    news = get_news(symbol)
    return (
        f"Symbol: {symbol}\nTECHNICALS: {tech}\n"
        f"FUNDAMENTALS: {fund or 'data nahi mila'}\n"
        f"LATEST NEWS HEADLINES: {news or 'koi news nahi mili'}"
    )


def ask_ai(context: str, question: str, history=None) -> str:
    client = get_client()
    if client is None:
        return "⚠️ GEMINI_API_KEY Streamlit secrets me set nahi hai."
    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=f"DATA:\n{context}\n\nSAWAL: {question}",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM, max_output_tokens=1500
            ),
        )
        return resp.text or "AI ne khali jawab diya, dobara try karo."
    except Exception as e:
        if "429" in str(e):
            return "⏳ Free limit khatam ho gayi. 1 minute baad try karo."
        return f"AI error: {e}"
      
