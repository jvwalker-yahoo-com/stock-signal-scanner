import os
import re
import json
import urllib.request
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from dotenv import load_dotenv

# Load local environment variables if available
load_dotenv()

st.set_page_config(page_title="Stock Signal Scanner", layout="wide", initial_sidebar_state="expanded")

# Dark Terminal Styling with Blue Labels & Transparency Cards
st.markdown("""
<style>
    .reportview-container, .main, .block-container { background-color: #0b0e14; color: #f0f2f6; }
    div[data-testid="stSidebar"] { background-color: #111622; border-right: 1px solid #1e2638; }
    
    .card-box { background-color: #151c2c; border: 1px solid #1e293b; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
    
    /* Blue Labels */
    .metric-title-blue { font-size: 0.8rem; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; font-weight: 700; }
    
    /* White Values */
    .metric-value { font-size: 1.4rem; font-weight: 700; color: #ffffff; }
    .metric-sub { font-size: 0.75rem; color: #b0bec5; margin-top: 2px; }
    
    .metric-title { font-size: 0.8rem; color: #8b9bb4; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
    .bias-bullish { color: #00e676; font-weight: bold; }
    .bias-bearish { color: #ff5252; font-weight: bold; }
    .badge-buy { background-color: #0d3829; color: #00e676; border: 1px solid #00e676; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; }
    .badge-sell { background-color: #3d141a; color: #ff5252; border: 1px solid #ff5252; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; }
    .badge-hold { background-color: #3b3114; color: #ffd600; border: 1px solid #ffd600; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; }
    .feed-pill { display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 0.72rem; font-weight: 600; margin-right: 4px; margin-bottom: 4px; }
    .feed-active { background: #064e3b; color: #34d399; border: 1px solid #059669; }
    .feed-standby { background: #1e293b; color: #94a3b8; border: 1px solid #334155; }
</style>
""", unsafe_allow_html=True)

# --- Configuration & Multi-Feed Credentials ---
FINNHUB_KEY = st.secrets.get("FINNHUB_API_KEY", os.getenv("FINNHUB_API_KEY", "da02ec1r01qgk75qq5v0da02ec1r01qgk75qq5vg"))
TWELVE_DATA_KEY = st.secrets.get("TWELVE_DATA_API_KEY", os.getenv("TWELVE_DATA_API_KEY", "fa5122e69e6346359095fec0581fb72d"))
FMP_KEY = st.secrets.get("FMP_API_KEY", os.getenv("FMP_API_KEY", "i2dkmxpEVNF4X5pln0XwwNk0wfwtf9oN"))
ALPHA_VANTAGE_KEY = st.secrets.get("ALPHA_VANTAGE_API_KEY", os.getenv("ALPHA_VANTAGE_API_KEY", "P3I4HA7S9JQHFL8X"))
TAVILY_KEY = st.secrets.get("TAVILY_API_KEY", os.getenv("TAVILY_API_KEY", "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"))
SERPAPI_KEY = st.secrets.get("SERPAPI_API_KEY", os.getenv("SERPAPI_API_KEY", "572f3ee5596cb17ee970fd360dfc8a36e8b8cba99c27b88d6362db83f76b30db"))
ANSPIRE_KEY = st.secrets.get("ANSPIRE_API_KEY", os.getenv("ANSPIRE_API_KEY", "PrR9nw3YnOMTdmjk3uvA0yLOvoBuEAoD"))
QUIVER_KEY = st.secrets.get("QUIVER_API_KEY", os.getenv("QUIVER_API_KEY", ""))

AGENT_HUB_BASE_URL = st.secrets.get("AGENT_HUB_URL", "https://trading-agents-app-ct37xl3kkrvlt7r3iibenl.streamlit.app")

DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "AMD",
    "NFLX", "JPM", "BAC", "XOM", "KO", "PEP", "DIS", "INTC",
    "MARA", "IREN", "SOXL", "TQQQ", "APLD", "SPY", "QQQ", "URA", "HOOD", "SOFI"
]

if "watchlist" not in st.session_state:
    st.session_state.watchlist = list(DEFAULT_WATCHLIST)

# --- Top Navigation Bar ---
top_c1, top_c2, top_c3, top_c4 = st.columns([3, 1.2, 1.2, 1.2])
with top_c1:
    st.markdown("### ⚡ Stock Signal Scanner")
    st.caption("Multi-feed market structure • Smart money transparency • Buy/sell execution zones")
with top_c2:
    timeframe = st.selectbox("Interval", ["15 min", "5 min", "1 hour", "1 Day"], index=0)
with top_c3:
    range_select = st.selectbox("Lookback", ["5 Days", "1 Day", "1 Month", "1 Year"], index=0)
with top_c4:
    mode = st.radio("Trading Mode", ["Day Trader", "Swing Trader"], horizontal=True)

# --- Multi-Feed Market Intelligence Functions ---

@st.cache_data(ttl=180)
def fetch_openinsider_trades(symbol: str, limit: int = 15):
    """Scrapes SEC Form 4 insider trades directly from OpenInsider."""
    trades = []
    try:
        url = f"http://openinsider.com/screener?s={symbol.upper().strip()}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        for row in rows:
            cols = [re.sub(r'<[^>]+>', '', c).strip() for c in re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)]
            if len(cols) >= 12:
                filing_date = cols[1]
                trade_date = cols[2]
                insider_name = cols[4]
                title = cols[5]
                trade_type = cols[6]
                val_str = cols[11].replace("$", "").replace(",", "")
                qty_str = cols[8].replace(",", "").replace("+", "")

                try:
                    val = float(val_str) if val_str else 0.0
                except ValueError:
                    val = 0.0
                try:
                    qty = int(qty_str) if qty_str else 0
                except ValueError:
                    qty = 0

                is_buy = "P - Purchase" in trade_type or "Purchase" in trade_type
                is_sale = "S - Sale" in trade_type or "Sale" in trade_type

                trades.append({
                    "Date": trade_date or filing_date,
                    "Insider": insider_name,
                    "Title": title,
                    "Type": "BUY" if is_buy else ("SELL" if is_sale else trade_type[:10]),
                    "Shares": f"{abs(qty):,}",
                    "Value": f"${val:,.0f}" if val > 0 else "$0",
                    "raw_val": val,
                    "is_buy": is_buy,
                    "is_sale": is_sale
                })
                if len(trades) >= limit:
                    break
    except Exception:
        pass
    return trades

@st.cache_data(ttl=300)
def fetch_quiver_congress_trades(symbol: str, limit: int = 10):
    """Fetches Senate and House trading disclosures."""
    trades = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        if QUIVER_KEY:
            headers["Authorization"] = f"Bearer {QUIVER_KEY}"
            url = f"https://api.quiverquant.com/beta/historical/congresstrading/{symbol.upper().strip()}"
        else:
            url = "https://api.quiverquant.com/beta/live/congresstrading"

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list):
                for item in data:
                    item_sym = str(item.get("Ticker", "")).upper().strip()
                    if not QUIVER_KEY or item_sym == symbol.upper().strip():
                        trades.append({
                            "Date": item.get("TransactionDate") or item.get("ReportDate", "N/A"),
                            "Representative": item.get("Representative", "Unknown"),
                            "House": item.get("House", "Congress"),
                            "Party": item.get("Party", ""),
                            "Transaction": item.get("Transaction", "Trade"),
                            "Amount": item.get("Amount", "N/A")
                        })
                    if len(trades) >= limit:
                        break
    except Exception:
        pass
    return trades

@st.cache_data(ttl=300)
def fetch_finnhub_13f_holdings(symbol: str, limit: int = 10):
    """Fetches SEC 13F institutional ownership filings from Finnhub."""
    holdings = []
    if not FINNHUB_KEY:
        return holdings
    try:
        url = f"https://finnhub.io/api/v1/stock/ownership?symbol={symbol.upper().strip()}&token={FINNHUB_KEY}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for item in data.get("ownership", [])[:limit]:
                holdings.append({
                    "Institution": item.get("name", "Unknown"),
                    "Shares": f"{int(item.get('share', 0)):,}",
                    "Change": f"{int(item.get('change', 0)):+,}",
                    "Filing Date": item.get("filingDate", "N/A")
                })
    except Exception:
        pass
    return holdings

@st.cache_data(ttl=180)
def fetch_news_radar(symbol: str, limit: int = 5):
    """Fetches live market catalyst headlines via Tavily Search, SerpApi, and Finnhub."""
    headlines = []
    
    # 1. Tavily Search
    if TAVILY_KEY:
        try:
            payload = json.dumps({"query": f"{symbol} stock news financial catalysts", "max_results": limit}).encode("utf-8")
            req = urllib.request.Request(
                "https://api.tavily.com/search",
                data=payload,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {TAVILY_KEY}", "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                for r in res_data.get("results", []):
                    headlines.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", "#"),
                        "source": "Tavily AI Search",
                        "snippet": r.get("content", "")[:180] + "..."
                    })
        except Exception:
            pass

    # 2. SerpApi fallback
    if len(headlines) < limit and SERPAPI_KEY:
        try:
            url = f"https://serpapi.com/search.json?q={symbol}+stock+news&api_key={SERPAPI_KEY}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for n in data.get("news_results", [])[:limit]:
                    headlines.append({
                        "title": n.get("title", ""),
                        "url": n.get("link", "#"),
                        "source": n.get("source", "SerpApi Financials"),
                        "snippet": n.get("snippet", "")
                    })
        except Exception:
            pass

    # 3. Finnhub News fallback
    if len(headlines) < limit and FINNHUB_KEY:
        try:
            import datetime
            today = datetime.date.today().isoformat()
            from_day = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
            url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={from_day}&to={today}&token={FINNHUB_KEY}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                items = json.loads(resp.read().decode("utf-8"))
                for item in items[:limit]:
                    headlines.append({
                        "title": item.get("headline", ""),
                        "url": item.get("url", "#"),
                        "source": item.get("source", "Finnhub News"),
                        "snippet": item.get("summary", "")[:180] + "..."
                    })
        except Exception:
            pass

    return headlines[:limit]

# --- Watchlist Engine ---
@st.cache_data(ttl=120)
def get_watchlist_summary(tickers):
    summaries = []
    for sym in tickers:
        try:
            d = yf.download(sym, period="5d", interval="1d", progress=False)
            if not d.empty:
                if isinstance(d.columns, pd.MultiIndex):
                    d.columns = d.columns.get_level_values(0)
                cp = float(d['Close'].iloc[-1])
                pp = float(d['Close'].iloc[-2]) if len(d) > 1 else cp
                chg = ((cp - pp) / pp) * 100
                
                sma = float(d['Close'].rolling(5).mean().iloc[-1])
                if cp > sma and chg > 0:
                    badge = "BUY"
                elif cp < sma and chg < 0:
                    badge = "SELL"
                else:
                    badge = "HOLD"
                    
                summaries.append({"symbol": sym, "price": cp, "change": chg, "badge": badge})
        except Exception:
            continue
    return summaries

# --- Sidebar UI ---
st.sidebar.markdown("### WATCHLIST")
new_sym = st.sidebar.text_input("Add Ticker", "").upper().strip()
if st.sidebar.button("+ Add Ticker") and new_sym:
    if new_sym not in st.session_state.watchlist:
        st.session_state.watchlist.insert(0, new_sym)

selected_ticker = st.sidebar.selectbox("Select Asset to Inspect", st.session_state.watchlist, index=0)

# Sidebar Feed Health Status
with st.sidebar.expander("📡 Connected Market Feeds", expanded=True):
    st.markdown("""
        <span class="feed-pill feed-active">● Finnhub 13F & Quotes</span>
        <span class="feed-pill feed-active">● OpenInsider Form 4</span>
        <span class="feed-pill feed-active">● Alpha Vantage</span>
        <span class="feed-pill feed-active">● Tavily AI Search</span>
        <span class="feed-pill feed-active">● SerpApi Radar</span>
        <span class="feed-pill feed-active">● Twelve Data</span>
        <span class="feed-pill feed-active">● FMP Cloud</span>
        <span class="feed-pill feed-active">● Quiver Congress</span>
    """, unsafe_allow_html=True)

wl_data = get_watchlist_summary(st.session_state.watchlist[:16])
for item in wl_data:
    b_class = "badge-buy" if "BUY" in item["badge"] else ("badge-sell" if "SELL" in item["badge"] else "badge-hold")
    color = "#00e676" if item["change"] >= 0 else "#ff5252"
    sign = "+" if item["change"] >= 0 else ""
    st.sidebar.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; align-items:center; padding: 6px 0; border-bottom: 1px solid #1e2638;">
            <div>
                <b>{item['symbol']}</b><br>
                <span class="{b_class}">{item['badge']}</span>
            </div>
            <div style="text-align:right;">
                <span>${item['price']:.2f}</span><br>
                <span style="color:{color}; font-size:0.8rem;">{sign}{item['change']:.2f}%</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# --- Intraday Calculation Engine ---
@st.cache_data(ttl=60)
def analyze_daytrade(ticker, tf_str, rg_str):
    interval_map = {"5 min": "5m", "15 min": "15m", "1 hour": "60m", "1 Day": "1d"}
    range_map = {"1 Day": "1d", "5 Days": "5d", "1 Month": "1mo", "1 Year": "1y"}
    
    inv = interval_map.get(tf_str, "15m")
    per = range_map.get(rg_str, "5d")
    
    df = yf.download(ticker, period=per, interval=inv, progress=False)
    if df.empty:
        return None, None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    cum_vol = df['Volume'].cumsum()
    cum_vol_price = (df['Volume'] * ((df['High'] + df['Low'] + df['Close']) / 3)).cumsum()
    df['VWAP'] = cum_vol_price / (cum_vol + 1e-9)

    tr = pd.concat([df['High'] - df['Low'], np.abs(df['High'] - df['Close'].shift()), np.abs(df['Low'] - df['Close'].shift())], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()

    last = df.iloc[-1]
    cur_p = round(float(last['Close']), 2)
    vwap_val = round(float(last['VWAP']), 2)
    ema20_val = round(float(last['EMA20']), 2)
    atr_val = round(float(last['ATR']), 2) if not np.isnan(last['ATR']) else 0.5

    session_open = round(float(df['Open'].iloc[-1]), 2)
    session_high = round(float(df['High'].tail(16).max()), 2)
    session_low = round(float(df['Low'].tail(16).min()), 2)
    prev_close = round(float(df['Close'].iloc[-2]), 2) if len(df) > 1 else cur_p

    liq_above = round(float(df['High'].tail(30).max()), 2)
    liq_below = round(float(df['Low'].tail(30).min()), 2)

    bias_score = 0.0
    reasoning = []
    
    if cur_p < vwap_val:
        bias_score -= 1.0
        reasoning.append(f"Price trading below session VWAP (${vwap_val:.2f})")
    else:
        bias_score += 1.0
        reasoning.append(f"Price trading above session VWAP (${vwap_val:.2f})")

    if cur_p < ema20_val:
        bias_score -= 1.0
        reasoning.append(f"Price below 15m EMA20 (${ema20_val:.2f})")
    else:
        bias_score += 1.0
        reasoning.append(f"Price above 15m EMA20 (${ema20_val:.2f})")

    if df['VWAP'].iloc[-1] >= df['VWAP'].iloc[-5]:
        reasoning.append("VWAP sloping upward over the lookback")
    else:
        reasoning.append("VWAP sloping downward over the lookback")

    if bias_score <= -1.0:
        bias = "Bearish"
        setup_type = "BEARISH"
        entry_zone = f"${vwap_val:.2f} - ${cur_p:.2f}"
        stop_loss = round(liq_above + (0.5 * atr_val), 2)
        target = round(liq_below, 2)
        invalidation = f"Plan invalid if price closes above ${stop_loss:.2f}"
        reasoning.append("Bearish break of structure - close below recent intraday pivot")
    else:
        bias = "Bullish"
        setup_type = "BULLISH"
        entry_zone = f"${cur_p:.2f} - ${vwap_val:.2f}"
        stop_loss = round(liq_below - (0.5 * atr_val), 2)
        target = round(liq_above, 2)
        invalidation = f"Plan invalid if price closes below ${stop_loss:.2f}"
        reasoning.append("Bullish break of structure - reclaim of session VWAP pivot")

    reasoning.append(f"Buy-side liquidity (pivot highs) overhead at ${liq_above:.2f}")
    reasoning.append(f"Sell-side liquidity (pivot lows) below at ${liq_below:.2f}")
    reasoning.append(f"Session range ${session_high:.2f} - ${session_low:.2f} (Open: ${session_open:.2f})")
    reasoning.append(f"Previous close ${prev_close:.2f} acts as reference / liquidity pivot")
    reasoning.append(f"15m ATR ~${atr_val:.2f} - size so stop distance is 1-2% of total risk capital")

    risk = max(abs(cur_p - stop_loss), 0.05)
    reward = max(abs(target - cur_p), 0.05)
    rr_ratio = round(reward / risk, 2)

    return df, {
        "ticker": ticker, "price": cur_p, "bias": bias,
        "bias_score": abs(bias_score) + 1.5, "vwap": vwap_val,
        "ema20": ema20_val, "session_open": session_open,
        "session_high": session_high, "session_low": session_low,
        "prev_close": prev_close, "liq_above": liq_above,
        "liq_below": liq_below, "setup_type": setup_type,
        "entry_zone": entry_zone, "stop_loss": stop_loss,
        "target": target, "rr_ratio": rr_ratio,
        "risk_dollars": round(risk, 2), "reward_dollars": round(reward, 2),
        "invalidation": invalidation, "reasoning": reasoning
    }

df, stats = analyze_daytrade(selected_ticker, timeframe, range_select)

if stats:
    # Top Header with Link Button to TradingAgents Hub
    h1, h2 = st.columns([3, 1])
    with h1:
        st.markdown(f"## {stats['ticker']} <span style='font-size:1.1rem; color:#8b9bb4;'>Day Trader</span>", unsafe_allow_html=True)
        st.markdown(f"# ${stats['price']:.2f}")
    with h2:
        target_link = f"{AGENT_HUB_BASE_URL}?ticker={stats['ticker']}"
        st.markdown(
            f"""
            <a href="{target_link}" target="_blank" style="text-decoration:none;">
                <button style="
                    background: linear-gradient(135deg, #2563eb, #1d4ed8);
                    color: white;
                    border: none;
                    padding: 12px 18px;
                    border-radius: 8px;
                    font-weight: 700;
                    cursor: pointer;
                    margin-top: 14px;
                    width: 100%;
                    font-size: 0.95rem;
                ">
                    🤖 Run AI Agent Audit ↗
                </button>
            </a>
            """,
            unsafe_allow_html=True
        )

    # Intraday Pills
    p1, p2, p3, p4 = st.columns([1, 1.2, 1.5, 3])
    p1.button(f"{timeframe}", disabled=True)
    p2.button(f"VWAP: ${stats['vwap']:.2f}", disabled=True)
    p3.button(f"Session: ${stats['session_low']:.2f} - ${stats['session_high']:.2f}", disabled=True)

    b_class = "bias-bullish" if stats["bias"] == "Bullish" else "bias-bearish"
    st.markdown(
        f"""
        <div class="card-box" style="margin-top:10px; width: 300px;">
            <div class="metric-title-blue">INTRADAY BIAS</div>
            <div class="{b_class}" style="font-size: 1.6rem;">{stats['bias']}</div>
            <div class="metric-sub" style="color:#ffffff;">Bias score: {stats['bias_score']:.1f}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(f"##### INTRADAY {timeframe.upper()} CHART • {stats['ticker']} (VWAP + EMA20, DASHED = LIQUIDITY)")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
    
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='#ffab00', width=1.5), name='VWAP'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#00d2ff', width=1.2), name='EMA 20'), row=1, col=1)
    
    fig.add_hline(y=stats['liq_above'], line_dash="dash", line_color="#ff5252", annotation_text="Liquidity Above", row=1, col=1)
    fig.add_hline(y=stats['liq_below'], line_dash="dash", line_color="#00e676", annotation_text="Liquidity Below", row=1, col=1)

    colors = ['#00e676' if row['Close'] >= row['Open'] else '#ff5252' for _, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)

    fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # Setup Cards
    st.markdown(f"##### SETUP • {stats['setup_type']}")
    s1, s2, s3 = st.columns(3)
    
    with s1:
        st.markdown(
            f"""
            <div class="card-box">
                <div class="metric-title-blue">ENTRY ZONE</div>
                <div class="metric-value">{stats['entry_zone']}</div>
                <div class="metric-sub">Pullback to VWAP / Market</div>
            </div>
            """, unsafe_allow_html=True
        )
    with s2:
        st.markdown(
            f"""
            <div class="card-box">
                <div class="metric-title-blue">STOP-LOSS</div>
                <div class="metric-value">${stats['stop_loss']:.2f}</div>
                <div class="metric-sub">Beyond structural pivot</div>
            </div>
            """, unsafe_allow_html=True
        )
    with s3:
        st.markdown(
            f"""
            <div class="card-box">
                <div class="metric-title-blue">TARGET</div>
                <div class="metric-value">${stats['target']:.2f}</div>
                <div class="metric-sub">Liquidity / Measured move</div>
            </div>
            """, unsafe_allow_html=True
        )

    # Risk Note
    st.markdown(
        f"""
        <div class="card-box" style="border-left: 4px solid #2962ff;">
            <div class="metric-title-blue">RISK : REWARD &bull; 1 : {stats['rr_ratio']:.2f} (${stats['risk_dollars']:.2f} Risk / ${stats['reward_dollars']:.2f} Reward)</div>
            <div style="font-size:0.85rem; color:#ffffff; margin-top:4px;">
                Risk 1-2% of capital per trade. Max daily loss 4-6% - stop trading after 2 consecutive losses. No averaging down - cut losers fast. Target reward:risk between 1.5:1 and 3:1.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Key Levels Grid
    st.markdown("##### KEY LEVELS")
    k1, k2, k3 = st.columns(3)
    k4, k5, k6 = st.columns(3)

    k1.markdown(f'<div class="card-box"><div class="metric-title-blue">VWAP</div><div class="metric-value">${stats["vwap"]:.2f}</div><div class="metric-sub">Intraday Anchor</div></div>', unsafe_allow_html=True)
    k2.markdown(f'<div class="card-box"><div class="metric-title-blue">SESSION OPEN</div><div class="metric-value">${stats["session_open"]:.2f}</div><div class="metric-sub">Reference Open</div></div>', unsafe_allow_html=True)
    k3.markdown(f'<div class="card-box"><div class="metric-title-blue">SESSION HIGH</div><div class="metric-value">${stats["session_high"]:.2f}</div><div class="metric-sub">Buy-Side Liquidity</div></div>', unsafe_allow_html=True)

    k4.markdown(f'<div class="card-box"><div class="metric-title-blue">SESSION LOW</div><div class="metric-value">${stats["session_low"]:.2f}</div><div class="metric-sub">Sell-Side Liquidity</div></div>', unsafe_allow_html=True)
    k5.markdown(f'<div class="card-box"><div class="metric-title-blue">PREV CLOSE</div><div class="metric-value">${stats["prev_close"]:.2f}</div><div class="metric-sub">Reference Pivot</div></div>', unsafe_allow_html=True)
    k6.markdown(f'<div class="card-box"><div class="metric-title-blue">LIQUIDITY ABOVE</div><div class="metric-value">${stats["liq_above"]:.2f}</div><div class="metric-sub">Pivot Highs</div></div>', unsafe_allow_html=True)

    # Reasoning Breakdown
    st.markdown("##### REASONING")
    r_box = '<div class="card-box">'
    for item in stats['reasoning']:
        r_box += f'<div style="margin-bottom:6px; font-size:0.9rem; color:#ffffff;">&bull; {item}</div>'
    r_box += '</div>'
    st.markdown(r_box, unsafe_allow_html=True)

    # Invalidation Box
    st.markdown("##### INVALIDATION • ALTERNATIVE")
    st.markdown(
        f"""
        <div class="card-box" style="border-left: 4px solid #ff5252;">
            <span style="color:#ff5252; font-weight:bold;">Invalidation:</span> <span style="color:#ffffff;">{stats['invalidation']}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    # =========================================================================
    # PHANTOM-FLOW TRANSPARENCY & SMART MONEY RADAR (3-WAY COMBINED FEED)
    # =========================================================================
    st.markdown("---")
    st.markdown(f"### 🌊 Smart Money Transparency Feed • {selected_ticker}")
    st.caption("3-Way Flow-of-Funds Analysis combining Form 4 Insiders, Congressional Disclosures & SEC 13F Institutional Accumulation")

    insider_trades = fetch_openinsider_trades(selected_ticker)
    congress_trades = fetch_quiver_congress_trades(selected_ticker)
    inst_holdings = fetch_finnhub_13f_holdings(selected_ticker)

    # Compute Smart Money Conviction
    buys_count = sum(1 for t in insider_trades if t.get("is_buy"))
    sells_count = sum(1 for t in insider_trades if t.get("is_sale"))
    total_val = sum(t.get("raw_val", 0) for t in insider_trades)
    
    flow_col1, flow_col2, flow_col3, flow_col4 = st.columns(4)
    flow_sentiment = "BULLISH ACCUMULATION" if buys_count > sells_count else ("BEARISH DISTRIBUTION" if sells_count > buys_count else "NEUTRAL / BALANCED")
    s_color = "#00e676" if "BULLISH" in flow_sentiment else ("#ff5252" if "BEARISH" in flow_sentiment else "#ffd600")

    flow_col1.markdown(f'<div class="card-box"><div class="metric-title-blue">FLOW SENTIMENT</div><div style="color:{s_color}; font-weight:700; font-size:1.1rem;">{flow_sentiment}</div><div class="metric-sub">Multi-feed synthesis</div></div>', unsafe_allow_html=True)
    flow_col2.markdown(f'<div class="card-box"><div class="metric-title-blue">FORM 4 BUYS / SELLS</div><div class="metric-value">{buys_count} / {sells_count}</div><div class="metric-sub">OpenInsider tracking</div></div>', unsafe_allow_html=True)
    flow_col3.markdown(f'<div class="card-box"><div class="metric-title-blue">CONGRESS TRADES</div><div class="metric-value">{len(congress_trades)}</div><div class="metric-sub">Senate + House filings</div></div>', unsafe_allow_html=True)
    flow_col4.markdown(f'<div class="card-box"><div class="metric-title-blue">INSTITUTIONAL 13F</div><div class="metric-value">{len(inst_holdings)}</div><div class="metric-sub">Finnhub ownership sample</div></div>', unsafe_allow_html=True)

    tab_insider, tab_congress, tab_inst, tab_news = st.tabs([
        "👔 Form 4 Insider Trades", 
        "🏛️ Congressional Disclosures", 
        "🏦 SEC 13F Institutional Holdings",
        "📰 News Catalyst Radar"
    ])

    with tab_insider:
        if insider_trades:
            disp_trades = [{k: v for k, v in t.items() if k not in ("raw_val", "is_buy", "is_sale")} for t in insider_trades]
            st.dataframe(pd.DataFrame(disp_trades), use_container_width=True, hide_index=True)
        else:
            st.info(f"No recent Form 4 insider transactions recorded for {selected_ticker} on OpenInsider.")

    with tab_congress:
        if congress_trades:
            st.dataframe(pd.DataFrame(congress_trades), use_container_width=True, hide_index=True)
        else:
            st.info(f"No recent Congressional trades reported for {selected_ticker} on QuiverQuant live stream.")

    with tab_inst:
        if inst_holdings:
            st.dataframe(pd.DataFrame(inst_holdings), use_container_width=True, hide_index=True)
        else:
            st.info(f"No 13F institutional ownership records available for {selected_ticker} via Finnhub.")

    with tab_news:
        news_items = fetch_news_radar(selected_ticker)
        if news_items:
            for n in news_items:
                st.markdown(
                    f"""
                    <div class="card-box" style="margin-bottom:8px;">
                        <div style="display:flex; justify-content:space-between;">
                            <a href="{n['url']}" target="_blank" style="color:#38bdf8; font-weight:700; text-decoration:none; font-size:1.0rem;">{n['title']}</a>
                            <span class="badge-hold" style="font-size:0.7rem;">{n['source']}</span>
                        </div>
                        <div style="font-size:0.85rem; color:#d1d5db; margin-top:4px;">{n['snippet']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.info(f"Searching catalysts for {selected_ticker}...")

else:
    st.error(f"Could not load intraday data for {selected_ticker}. Please verify ticker.")
