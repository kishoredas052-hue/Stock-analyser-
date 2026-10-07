import html
import json
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Market Dashboard", page_icon="🏠", layout="wide")

st.markdown("""
<style>
.stApp {background: linear-gradient(135deg,#0f2027,#203a43,#2c5364) fixed !important;}
[data-testid="stHeader"] {background: transparent;}
.block-container {padding-top: 2.5rem; padding-bottom: 3rem; max-width: 1100px;}
.ttl {font-size: 1.7rem; font-weight: 800;
  background: linear-gradient(90deg,#22d3ee,#4ade80);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;}
.sub {color: #94a3b8; font-size: .8rem;}
.grid {display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 12px;}
@media (min-width: 800px) {.grid {grid-template-columns: repeat(4, 1fr);} .grid.p {grid-template-columns: repeat(3, 1fr);}}
.tile, .card {background: rgba(17,26,46,.85); border: 1px solid #1e2a44; border-radius: 14px; padding: 12px 14px;}
.tile .t {color: #94a3b8; font-size: .78rem;}
.tile .v {font-size: 1.15rem; font-weight: 700; margin: 2px 0;}
.row {display: flex; justify-content: space-between; align-items: center; gap: 8px;}
.card .price {font-size: 1.25rem; font-weight: 700;}
.rt {font-size: .7rem; font-weight: 700; padding: 2px 8px; border-radius: 99px; color: #04121f;}
.bar {height: 6px; background: #1e2a44; border-radius: 6px; margin: 8px 0 4px;}
.bar div {height: 6px; border-radius: 6px; background: linear-gradient(90deg,#06b6d4,#22c55e);}
.why {color: #cbd5e1; font-size: .8rem; margin-top: 6px;}
.mood {background: rgba(17,26,46,.85); border: 1px solid #1e2a44; border-radius: 14px;
  padding: 14px 16px; margin-bottom: 12px;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "market.json")
RC = {"Strong": "#22c55e", "Watch": "#f59e0b", "Weak": "#ef4444"}


@st.cache_data(show_spinner=False)
def load_data(mtime: float):
    with open(DATA) as fh:
        return json.load(fh)


def esc(s):
    return html.escape(str(s))


def tile(name, value, chg):
    if value is None:
        return ""
    col, arrow = ("#22c55e", "▲") if (chg or 0) >= 0 else ("#ef4444", "▼")
    chg_txt = f"{arrow} {chg:+.2f}%" if chg is not None else ""
    return (f"<div class='tile'><div class='t'>{esc(name)}</div><div class='v'>{value:,.2f}</div>"
            f"<div style='color:{col};font-size:.85rem'>{chg_txt}</div></div>")


def pick_card(s):
    col = "#22c55e" if (s["chg"] or 0) >= 0 else "#ef4444"
    fund = f"{s['fund']}/5" if s["fund"] is not None else "NA"
    return (
        f"<div class='card'><div class='row'><b>{esc(s['name'])}</b>"
        f"<span class='rt' style='background:{RC[s['rating']]}'>{s['rating']}</span></div>"
        f"<div class='sub'>{esc(s['symbol'])} • {esc(s['sector'])}</div>"
        f"<div class='row'><span class='price'>₹{s['price']:,.2f}</span>"
        f"<span style='color:{col}'>{s['chg']:+.2f}%</span></div>"
        f"<div class='bar'><div style='width:{s['combined'] / 5 * 100:.0f}%'></div></div>"
        f"<div class='sub'>Score {s['combined']}/5 • Technical: {esc(s['verdict'])} • Fundamental: {fund}</div>"
        f"<div class='why'>{esc(s['reason'])}</div></div>"
    )


st.markdown("<div class='ttl'>🏠 Market Dashboard</div>", unsafe_allow_html=True)

if not os.path.exists(DATA):
    st.info("Abhi data nahi bana hai. GitHub me **Actions → Daily market update → Run workflow** dabao, "
            "3 se 5 minute baad yahan data aa jaayega.")
    st.stop()

d = load_data(os.path.getmtime(DATA))
stocks = pd.DataFrame(d["stocks"])
b = d["breadth"]

c1, c2 = st.columns([4, 1])
c1.markdown(f"<div class='sub'>Last update: {esc(d['updated'])} • Roz shaam 5 baje auto-update</div>",
            unsafe_allow_html=True)
if c2.button("🔄 Reload"):
    st.cache_data.clear()
    st.rerun()

# ---- Market mood ----
bp = b["bullish_pct"]
mood, icon = (("Bullish", "🟢") if bp >= 55 else ("Bearish", "🔴") if bp <= 35 else ("Mixed / Neutral", "🟡"))
st.markdown(
    f"<div class='mood'><b>{icon} Market mood: {mood}</b>"
    f"<div class='sub' style='margin-top:4px'>{b['total']} bade stocks me se {bp}% me Buy signal, "
    f"{b['above200_pct']}% apne SMA200 ke upar. Aaj {b['advance']} chadhe, {b['decline']} gire.</div></div>",
    unsafe_allow_html=True)

# ---- Indices ----
st.markdown("#### 📈 Market Snapshot")
st.markdown("<div class='grid'>" + "".join(tile(i["name"], i["value"], i["chg"]) for i in d["indices"]) + "</div>",
            unsafe_allow_html=True)

# ---- Top picks ----
st.markdown("#### 🏆 Aaj ke Top Analysis Picks")
st.caption("Technical (60%) + Fundamental (40%) score ke hisaab se. Ye analysis hai, buy/sell salaah nahi.")
top = stocks.sort_values("combined", ascending=False).head(6).to_dict("records")
st.markdown("<div class='grid p'>" + "".join(pick_card(s) for s in top) + "</div>", unsafe_allow_html=True)

# ---- Tabs ----
t1, t2, t3, t4 = st.tabs(["🚀 Gainers", "📉 Losers", "🏭 Sectors", "📋 Sab stocks"])
cols = ["symbol", "name", "price", "chg", "verdict", "rating"]
rename = {"symbol": "Symbol", "name": "Naam", "price": "Price ₹", "chg": "1D %", "verdict": "Technical", "rating": "Rating"}
with t1:
    st.dataframe(stocks.sort_values("chg", ascending=False).head(5)[cols].rename(columns=rename),
                 hide_index=True, use_container_width=True)
with t2:
    st.dataframe(stocks.sort_values("chg").head(5)[cols].rename(columns=rename),
                 hide_index=True, use_container_width=True)
with t3:
    sec = stocks.groupby("sector")["chg"].mean().sort_values()
    fig = go.Figure(go.Bar(x=sec.values, y=sec.index, orientation="h",
                           marker_color=["#22c55e" if v >= 0 else "#ef4444" for v in sec.values],
                           text=[f"{v:+.2f}%" for v in sec.values], textposition="outside"))
    fig.update_layout(height=max(280, 30 * len(sec)), margin=dict(l=0, r=40, t=10, b=0), dragmode=False,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True, config={"staticPlot": True})
    st.caption("Har sector ke stocks ka aaj ka average % change.")
with t4:
    f1, f2 = st.columns(2)
    ratings = f1.multiselect("Rating", ["Strong", "Watch", "Weak"], default=["Strong", "Watch", "Weak"])
    sectors = f2.multiselect("Sector", sorted(stocks["sector"].unique()))
    view = stocks[stocks["rating"].isin(ratings)]
    if sectors:
        view = view[view["sector"].isin(sectors)]
    show = view.sort_values("combined", ascending=False)[
        ["symbol", "sector", "price", "chg", "rsi", "verdict", "fund", "combined", "rating"]]
    st.dataframe(show.rename(columns={"symbol": "Symbol", "sector": "Sector", "price": "Price ₹", "chg": "1D %",
                                       "rsi": "RSI", "verdict": "Technical", "fund": "Fund /5",
                                       "combined": "Score /5", "rating": "Rating"}),
                 hide_index=True, use_container_width=True)

st.caption("Sirf educational analysis. Ye financial advice nahi hai. Kisi stock ka detail dekhne ke liye "
           "sidebar (☰) me 'app' page kholo.")
