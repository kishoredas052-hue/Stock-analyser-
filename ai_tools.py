import xml.etree.ElementTree as ET

import requests
import streamlit as st
import yfinance as yf
from google import genai
from google.genai import types

# Free model. Agar 429/"limit 0" error aaye to AI Studio me dekho kaunsa model free hai aur yahan naam badlo.
MODEL = "gemini-3.5-flash"

SYSTEM_BASE = (
    "Tum ek stock market analyst assistant ho. Jawab Hindi (Devanagari + zaroorat ho to English terms) me do, "
    "chhote aur clear points me. Bull aur bear dono side batao. "
    "Ye educational analysis hai, financial advice nahi, ye ek line me yaad dilao."
)
NO_SEARCH = " Sirf diye gaye data ka use karo; jo data me nahi hai uska andaza mat lagao, bolo ki data nahi hai."
WITH_SEARCH = (
    " Diye gaye data me fundamentals/news kam hain, isliye Google Search se latest fundamentals "
    "(PE, ROE, debt, ETF ho to NAV/expense ratio) aur taaza news dhundo. Web se mili cheez ke saamne "
    "'(web search)' likho. Jo search me bhi na mile uska andaza mat lagao."
)


def get_client():
    key = st.secrets.get("GEMINI_API_KEY", None)
    return genai.Client(api_key=key) if key else None


# ---------- FUNDAMENTALS ----------
@st.cache_data(ttl=1800, show_spinner=False)
def _fundamentals(symbol: str) -> dict:
    tk = yf.Ticker(symbol)
    out = {}
    try:
        info = tk.info or {}
        keys = ["longName", "sector", "category", "marketCap", "trailingPE", "priceToBook",
                "returnOnEquity", "debtToEquity", "dividendYield", "navPrice", "totalAssets",
                "ytdReturn", "threeYearAverageReturn", "fiftyTwoWeekHigh", "fiftyTwoWeekLow"]
        out = {k: info.get(k) for k in keys if info.get(k) is not None}
    except Exception:
        pass
    if not out:
        try:
            fi = tk.fast_info
            out = {"marketCap": fi.get("marketCap"), "fiftyTwoWeekHigh": fi.get("yearHigh"),
                   "fiftyTwoWeekLow": fi.get("yearLow")}
            out = {k: v for k, v in out.items() if v}
        except Exception:
            pass
    if not out:
        raise ValueError("empty")  # khali result cache nahi hoga
    return out


def get_fundamentals(symbol: str) -> dict:
    try:
        return _fundamentals(symbol)
    except Exception:
        return {}


# ---------- NEWS ----------
def _google_news(query: str) -> list:
    r = requests.get(
        "https://news.google.com/rss/search",
        params={"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
        headers={"User-Agent": "Mozilla/5.0"}, timeout=8,
    )
    root = ET.fromstring(r.content)
    return [i.findtext("title") for i in root.iter("item") if i.findtext("title")][:6]


@st.cache_data(ttl=1800, show_spinner=False)
def _news(symbol: str, name: str) -> list:
    titles = []
    try:  # 1) Yahoo
        for it in (yf.Ticker(symbol).news or [])[:6]:
            t = (it.get("content") or {}).get("title") or it.get("title")
            if t:
                titles.append(t)
    except Exception:
        pass
    if not titles:  # 2) Google News RSS (free, key nahi chahiye)
        try:
            base = symbol.split(".")[0]
            q = f"{name or base} {'share' if symbol.endswith(('.NS', '.BO')) else 'stock'}"
            titles = _google_news(q)
        except Exception:
            pass
    if not titles:
        raise ValueError("empty")
    return titles


def get_news(symbol: str, name: str = "") -> list:
    try:
        return _news(symbol, name or "")
    except Exception:
        return []


# ---------- AI ----------
def build_context(symbol, df, sc, name: str = "") -> str:
    l = df.iloc[-1]
    tech = (
        f"Price {l['Close']:.2f}, SMA20 {l['SMA20']:.2f}, SMA50 {l['SMA50']:.2f}, "
        f"SMA200 {l['SMA200']:.2f}, RSI {l['RSI']:.1f}, MACD {l['MACD']:.3f} (signal {l['MACD_SIG']:.3f}), "
        f"ATR {l['ATR']:.2f}, 20-day low {df['Low'].tail(20).min():.2f}, "
        f"20-day high {df['High'].tail(20).max():.2f}. "
        f"Rule-based verdict: {sc['verdict']} (score {sc['score']:+.1f})."
    )
    fund = get_fundamentals(symbol)
    news = get_news(symbol, name)
    return (
        f"Symbol: {symbol} ({name})\nTECHNICALS: {tech}\n"
        f"FUNDAMENTALS: {fund or 'data nahi mila'}\n"
        f"LATEST NEWS HEADLINES: {news or 'koi news nahi mili'}"
    )


def ask_ai(context: str, question: str, history=None) -> str:
    client = get_client()
    if client is None:
        return "⚠️ GEMINI_API_KEY Streamlit secrets me set nahi hai."

    use_search = "data nahi mila" in context  # fundamentals missing -> Google Search se poochho
    contents = f"DATA:\n{context}\n\nSAWAL: {question}"

    def run(with_search: bool):
        cfg = types.GenerateContentConfig(
            system_instruction=SYSTEM_BASE + (WITH_SEARCH if with_search else NO_SEARCH),
            max_output_tokens=2500,
            tools=[types.Tool(google_search=types.GoogleSearch())] if with_search else None,
        )
        return client.models.generate_content(model=MODEL, contents=contents, config=cfg)

    try:
        try:
            resp = run(use_search)
        except Exception as e:
            if use_search and "429" not in str(e):
                resp = run(False)      # search tool na chale to bina search ke chalao
            else:
                raise
        return resp.text or "AI ne khali jawab diya, dobara try karo."
    except Exception as e:
        if "429" in str(e):
            return "⏳ Free limit khatam ho gayi. 1 minute baad try karo."
        return f"AI error: {e}"
        
