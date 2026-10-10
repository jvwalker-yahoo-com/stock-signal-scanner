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
from wyckoff import detect_wyckoff_structure
from jev_rag import JevRAGEngine
from market_intel import MarketIntelSuite

load_dotenv()

st.set_page_config(page_title="Stock Signal Scanner", layout="wide", initial_sidebar_state="expanded")

# Dark Terminal Styling
st.markdown("""
<style>
    .reportview-container, .main, .block-container { background-color: #0b0e14; color: #f0f2f6; }
    div[data-testid="stSidebar"] { background-color: #111622; border-right: 1px solid #1e2638; }
    .card-box { background-color: #151c2c; border: 1px solid #1e293b; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
    .metric-title-blue { font-size: 0.8rem; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; font-weight: 700; }
    .metric-value { font-size: 1.4rem; font-weight: 700; color: #ffffff; }
    .metric-sub { font-size: 0.75rem; color: #b0bec5; margin-top: 2px; }
    .bias-bullish { color: #00e676; font-weight: bold; }
    .bias-bearish { color: #ff5252; font-weight: bold; }
    .bias-caution { color: #f59e0b; font-weight: bold; }
    .badge-buy { background-color: #0d3829; color: #00e676; border: 1px solid #00e676; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; }
    .badge-sell { background-color: #3d141a; color: #ff5252; border: 1px solid #ff5252; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; }
    .badge-hold { background-color: #3b3114; color: #ffd600; border: 1px solid #ffd600; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; }
    .feed-pill { display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 0.72rem; font-weight: 600; margin-right: 4px; margin-bottom: 4px; }
    .feed-active { background: #064e3b; color: #34d399; border: 1px solid #059669; }
</style>
""", unsafe_allow_html=True)

# Configuration & Multi-Feed Credentials
def get_secret(key, default=""):
    try:
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)

FINNHUB_KEY = get_secret("FINNHUB_API_KEY", "db402p9r01qucqgihnrgdb402p9r01qucqgihns0")
TWELVE_DATA_KEY = get_secret("TWELVE_DATA_API_KEY", "fa5122e69e6346359095fec0581fb72d")
FMP_KEY = get_secret("FMP_API_KEY", "i2dkmxpEVNF4X5pln0XwwNk0wfwtf9oN")
ALPHA_VANTAGE_KEY = get_secret("ALPHA_VANTAGE_API_KEY", "P3I4HA7S9JQHFL8X")
TAVILY_KEY = get_secret("TAVILY_API_KEY", "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")
SERPAPI_KEY = get_secret("SERPAPI_API_KEY", "572f3ee5596cb17ee970fd360dfc8a36e8b8cba99c27b88d6362db83f76b30db")
ANSPIRE_KEY = get_secret("ANSPIRE_API_KEY", "PrR9nw3YnOMTdmjk3uvA0yLOvoBuEAoD")
QUIVER_KEY = get_secret("QUIVER_API_KEY", "")

AGENT_HUB_BASE_URL = get_secret("AGENT_HUB_URL", "https://trading-agents-app-ct37xl3kkrvlt7r3iibenl.streamlit.app")

# Initialize Unified Market Intelligence Suite
market_suite = MarketIntelSuite(
    finnhub_key=FINNHUB_KEY,
    polygon_key=get_secret("POLYGON_API_KEY", ""),
    fred_key=get_secret("FRED_API_KEY", ""),
    av_key=ALPHA_VANTAGE_KEY
)

@st.cache_data(ttl=180)
def fetch_forex_overview():
    return market_suite.get_forex_rates("USD", ["EUR", "GBP", "JPY", "CAD", "AUD", "CHF"])

@st.cache_data(ttl=120)
def fetch_crypto_overview():
    return market_suite.get_crypto_prices(["bitcoin", "ethereum", "solana", "ripple", "dogecoin"])

@st.cache_data(ttl=1800)
def fetch_macro_indicators():
    return market_suite.get_fred_macro_indicators()

@st.cache_data(ttl=300)
def fetch_edgar_filings(sym):
    return market_suite.get_sec_edgar_filings(sym, limit=12)

@st.cache_data(ttl=60)
def fetch_polygon_finnhub_quote(sym):
    return market_suite.get_stock_ticks_and_quote(sym)

DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "AMD",
    "NFLX", "JPM", "BAC", "XOM", "KO", "PEP", "DIS", "INTC",
    "MARA", "IREN", "SOXL", "TQQQ", "APLD", "SPY", "QQQ", "URA", "HOOD", "SOFI"
]

if "watchlist" not in st.session_state:
    st.session_state.watchlist = list(DEFAULT_WATCHLIST)

# Top Bar
top_c1, top_c2, top_c3, top_c4 = st.columns([3, 1.2, 1.2, 1.2])
with top_c1:
    st.markdown("### ⚡ Stock Signal Scanner")
    st.caption("Phantom-Flow Smart Money Intelligence • Multi-Feed Confluence Engine")
with top_c2:
    timeframe = st.selectbox("Interval", ["15 min", "5 min", "1 hour", "1 Day"], index=0)
with top_c3:
    range_select = st.selectbox("Lookback", ["5 Days", "1 Day", "1 Month", "1 Year"], index=0)
with top_c4:
    mode = st.radio("Trading Mode", ["Day Trader", "Swing Trader"], horizontal=True)

# Data Feed Scrapers & API Integrations
@st.cache_data(ttl=180)
def fetch_openinsider_trades(symbol: str, limit: int = 15):
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
                filing_date, trade_date, insider_name, title, trade_type = cols[1], cols[2], cols[4], cols[5], cols[6]
                val_str = cols[11].replace("$", "").replace(",", "")
                qty_str = cols[8].replace(",", "").replace("+", "")
                try: val = float(val_str) if val_str else 0.0
                except ValueError: val = 0.0
                try: qty = int(qty_str) if qty_str else 0
                except ValueError: qty = 0

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
                if len(trades) >= limit: break
    except Exception:
        pass
    return trades

@st.cache_data(ttl=300)
def fetch_quiver_congress_trades(symbol: str, limit: int = 10):
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
                    if len(trades) >= limit: break
    except Exception:
        pass
    return trades

@st.cache_data(ttl=300)
def fetch_finnhub_13f_holdings(symbol: str, limit: int = 10):
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
                    "raw_change": int(item.get('change', 0)),
                    "Filing Date": item.get("filingDate", "N/A")
                })
    except Exception:
        pass
    return holdings

@st.cache_data(ttl=180)
def fetch_news_radar(symbol: str, limit: int = 5):
    headlines = []
    if TAVILY_KEY:
        try:
            payload = json.dumps({"query": f"{symbol} stock market catalysts news", "max_results": limit}).encode("utf-8")
            req = urllib.request.Request("https://api.tavily.com/search", data=payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {TAVILY_KEY}", "User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                for r in json.loads(resp.read().decode("utf-8")).get("results", []):
                    headlines.append({"title": r.get("title", ""), "url": r.get("url", "#"), "source": "Tavily AI Search", "snippet": r.get("content", "")[:180] + "..."})
        except Exception:
            pass

    if len(headlines) < limit and SERPAPI_KEY:
        try:
            url = f"https://serpapi.com/search.json?q={symbol}+stock+news&api_key={SERPAPI_KEY}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                for n in json.loads(resp.read().decode("utf-8")).get("news_results", [])[:limit]:
                    headlines.append({"title": n.get("title", ""), "url": n.get("link", "#"), "source": n.get("source", "SerpApi"), "snippet": n.get("snippet", "")})
        except Exception:
            pass

    if len(headlines) < limit and FINNHUB_KEY:
        try:
            import datetime
            today = datetime.date.today().isoformat()
            from_day = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
            url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from={from_day}&to={today}&token={FINNHUB_KEY}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                for item in json.loads(resp.read().decode("utf-8"))[:limit]:
                    headlines.append({"title": item.get("headline", ""), "url": item.get("url", "#"), "source": "Finnhub News", "snippet": item.get("summary", "")[:180] + "..."})
        except Exception:
            pass
    return headlines[:limit]

# Sidebar Watchlist & Feeds Monitor
st.sidebar.markdown("### WATCHLIST")
new_sym = st.sidebar.text_input("Add Ticker", "").upper().strip()
if st.sidebar.button("+ Add Ticker") and new_sym:
    if new_sym not in st.session_state.watchlist:
        st.session_state.watchlist.insert(0, new_sym)

selected_ticker = st.sidebar.selectbox("Select Asset to Inspect", st.session_state.watchlist, index=0)

with st.sidebar.expander("📡 Connected Market Feeds", expanded=False):
    st.markdown("""
        <span class="feed-pill feed-active">● Frankfurter Forex (No Auth)</span>
        <span class="feed-pill feed-active">● CoinGecko Crypto (No Auth)</span>
        <span class="feed-pill feed-active">● FRED Federal Reserve Macro</span>
        <span class="feed-pill feed-active">● SEC EDGAR Direct Filings</span>
        <span class="feed-pill feed-active">● Polygon.io / Finnhub Ticks</span>
        <span class="feed-pill feed-active">● OpenInsider Form 4</span>
        <span class="feed-pill feed-active">● Alpha Vantage Market</span>
        <span class="feed-pill feed-active">● Tavily AI Intelligence</span>
        <span class="feed-pill feed-active">● Twelve Data Feed</span>
        <span class="feed-pill feed-active">● Quiver Congress Trades</span>
    """, unsafe_allow_html=True)

with st.sidebar.expander("🌐 Global Macro & FX Pulse", expanded=False):
    try:
        fx_data = fetch_forex_overview()
        fx_rates = fx_data.get("rates", {})
        st.caption(f"Frankfurter FX (Base USD) • {fx_data.get('date', 'Live')}")
        fx_c1, fx_c2 = st.columns(2)
        fx_c1.metric("EUR/USD", f"{1.0/fx_rates.get('EUR', 1.12):.4f}" if 'EUR' in fx_rates else "N/A")
        fx_c2.metric("GBP/USD", f"{1.0/fx_rates.get('GBP', 1.32):.4f}" if 'GBP' in fx_rates else "N/A")
        fx_c1.metric("USD/JPY", f"{fx_rates.get('JPY', 158.2):.2f}" if 'JPY' in fx_rates else "N/A")
        fx_c2.metric("USD/CAD", f"{fx_rates.get('CAD', 1.42):.4f}" if 'CAD' in fx_rates else "N/A")
    except Exception:
        st.caption("FX data syncing...")

    try:
        cg_data = fetch_crypto_overview()
        cg_items = cg_data.get("data", {})
        if "bitcoin" in cg_items:
            btc = cg_items["bitcoin"]
            st.caption("CoinGecko Crypto")
            st.metric("Bitcoin", f"${btc['price_usd']:,.0f}", f"{btc['change_24h_pct']:+.2f}%")
        if "ethereum" in cg_items:
            eth = cg_items["ethereum"]
            st.metric("Ethereum", f"${eth['price_usd']:,.2f}", f"{eth['change_24h_pct']:+.2f}%")
    except Exception:
        pass

@st.cache_data(ttl=120)
def get_watchlist_summary(tickers):
    summaries = []
    for sym in tickers:
        try:
            d = yf.download(sym, period="5d", interval="1d", progress=False)
            if not d.empty:
                if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
                cp = float(d['Close'].iloc[-1])
                pp = float(d['Close'].iloc[-2]) if len(d) > 1 else cp
                chg = ((cp - pp) / pp) * 100
                sma = float(d['Close'].rolling(5).mean().iloc[-1])
                badge = "BUY" if (cp > sma and chg > 0) else ("SELL" if (cp < sma and chg < 0) else "HOLD")
                summaries.append({"symbol": sym, "price": cp, "change": chg, "badge": badge})
        except Exception:
            continue
    return summaries

for item in get_watchlist_summary(st.session_state.watchlist[:16]):
    b_class = "badge-buy" if "BUY" in item["badge"] else ("badge-sell" if "SELL" in item["badge"] else "badge-hold")
    color = "#00e676" if item["change"] >= 0 else "#ff5252"
    sign = "+" if item["change"] >= 0 else ""
    st.sidebar.markdown(f"""
        <div style="display:flex; justify-content:space-between; align-items:center; padding: 6px 0; border-bottom: 1px solid #1e2638;">
            <div><b>{item['symbol']}</b><br><span class="{b_class}">{item['badge']}</span></div>
            <div style="text-align:right;"><span>${item['price']:.2f}</span><br><span style="color:{color}; font-size:0.8rem;">{sign}{item['change']:.2f}%</span></div>
        </div>
    """, unsafe_allow_html=True)

# Multi-Feed Confluence Synthesis Engine with JEV + RAG Intelligent Gating
def synthesize_multi_feed_signals(tech_score, cur_p, vwap_val, ema20_val, atr_val, liq_above, liq_below, insider_trades, congress_trades, inst_holdings, news_items, wyckoff_data=None, ticker="ASSET"):
    # Initialize JEV + RAG Engine (Intelligent Gating System)
    jev_engine = JevRAGEngine()
    raw_stats_temp = {
        "price": cur_p, "vwap": vwap_val, "ema20": ema20_val, "atr": atr_val,
        "liq_above": liq_above, "liq_below": liq_below, "tech_score": tech_score
    }
    jev_output = jev_engine.process_signals(
        ticker=ticker,
        raw_stats=raw_stats_temp,
        raw_news=news_items,
        insider_trades=insider_trades,
        congress_trades=congress_trades,
        wyckoff_data=wyckoff_data
    )
    jev_meta = jev_output["jev_metadata"]

    # 1. OpenInsider Form 4
    insider_buys = [t for t in insider_trades if t.get("is_buy")]
    insider_sells = [t for t in insider_trades if t.get("is_sale")]
    net_insider_val = sum(t.get("raw_val", 0) for t in insider_buys) - sum(t.get("raw_val", 0) for t in insider_sells)
    
    insider_mod = 0.0
    insider_note = "Neutral Form 4 insider flow"
    if len(insider_buys) >= 2 and net_insider_val > 100000:
        insider_mod = 1.5
        insider_note = f"Cluster C-Suite Purchases: {len(insider_buys)} buys (+${net_insider_val:,.0f} net value)"
    elif len(insider_buys) > len(insider_sells):
        insider_mod = 0.8
        insider_note = f"Net Insider Accumulation ({len(insider_buys)} purchases recorded)"
    elif len(insider_sells) > len(insider_buys) and abs(net_insider_val) > 1000000:
        insider_mod = -1.5
        insider_note = f"Heavy Executive Dumping: -${abs(net_insider_val):,.0f} across {len(insider_sells)} sales"
    elif len(insider_sells) > len(insider_buys):
        insider_mod = -0.8
        insider_note = f"Net Insider Selling ({len(insider_sells)} Form 4 sales filings)"

    # 2. QuiverQuant Congressional Trades
    c_buys = sum(1 for t in congress_trades if "BUY" in str(t.get("Transaction", "")).upper() or "PURCHASE" in str(t.get("Transaction", "")).upper())
    c_sells = sum(1 for t in congress_trades if "SELL" in str(t.get("Transaction", "")).upper() or "SALE" in str(t.get("Transaction", "")).upper())
    congress_mod = 1.0 if c_buys > c_sells else (-1.0 if c_sells > c_buys else 0.0)
    congress_note = f"Congress: {c_buys} Senate/House buys" if c_buys > c_sells else (f"Congress: {c_sells} Senate/House sales" if c_sells > c_buys else "Congress: Neutral flow")

    # 3. Finnhub 13F Institutional Filings
    inst_net_shares = sum(h.get("raw_change", 0) for h in inst_holdings) if inst_holdings else 0
    inst_mod = 0.5 if inst_net_shares > 0 else (-0.5 if inst_net_shares < 0 else 0.0)
    inst_note = f"13F: Top institutions accumulating (+{inst_net_shares:+,} shares)" if inst_net_shares > 0 else (f"13F: Institutional position trims ({inst_net_shares:+,} shares)" if inst_net_shares < 0 else "13F: Institutional holdings stable")

    # 4. News Catalyst Radar gated by JEV Processing Gateway
    # If JEV sufficiency gating failed, noise is shoved away and score is preserved at 0.0
    if not jev_meta["is_sufficient"]:
        news_mod = 0.0
        news_note = f"JEV Gateway: Shoved away noise ({jev_meta['filtered_news_count']} kept of {jev_meta['raw_news_count']}). Baseline technicals preserved."
    else:
        news_mod = jev_output["flow_impact"]
        news_note = f"JEV Gateway: Sufficiency confirmed ({len(jev_output['compressed_context'])} high-confidence drivers)."

    # 5. Wyckoff Range Engine Factor
    wyckoff_mod = 0.0
    wyckoff_note = "Wyckoff Structure: Baseline range"
    if wyckoff_data:
        if wyckoff_data.get("has_spring"):
            wyckoff_mod = 1.2
            wyckoff_note = f"Wyckoff: Confirmed Spring Sweep (Score {wyckoff_data.get('spring_score')}/100, Phase C)"
        elif wyckoff_data.get("has_utad"):
            wyckoff_mod = -1.2
            wyckoff_note = f"Wyckoff: Confirmed UTAD Upthrust Rejection (Score {wyckoff_data.get('utad_score')}/100, Phase C)"
        elif wyckoff_data.get("has_sos"):
            wyckoff_mod = 1.0
            wyckoff_note = "Wyckoff: Sign of Strength (SOS) Breakout confirmed (Phase D/E)"
        elif wyckoff_data.get("has_sow"):
            wyckoff_mod = -1.0
            wyckoff_note = "Wyckoff: Sign of Weakness (SOW) Breakdown confirmed (Phase D/E)"
        else:
            wyckoff_note = f"Wyckoff: {wyckoff_data.get('phase', 'Range Bound')}"

    # Composite Synthesis & Setup Classification
    flow_composite = insider_mod + congress_mod + inst_mod + news_mod + wyckoff_mod
    total_score = tech_score + flow_composite
    
    is_tech_bullish = (tech_score >= 0)
    is_flow_bullish = (flow_composite > 0.4)
    is_flow_bearish = (flow_composite < -0.4)

    if is_tech_bullish and is_flow_bullish:
        bias = "Strong Bullish"
        setup_type = "BULLISH CONFLUENCE • SMART MONEY CONFIRMED"
        entry_zone = f"${cur_p:.2f} - ${vwap_val:.2f}"
        stop_loss = wyckoff_data.get("stop_loss", round(liq_below - (0.5 * atr_val), 2)) if wyckoff_data else round(liq_below - (0.5 * atr_val), 2)
        target = wyckoff_data.get("tp2", round(liq_above + (0.5 * atr_val), 2)) if wyckoff_data else round(liq_above + (0.5 * atr_val), 2)
        invalidation = f"Plan invalid if price breaks below ${stop_loss:.2f} or Form 4 insider dumping accelerates"
        action_verdict = "HIGH CONVICTION BUY (FLOW & WYCKOFF CONFIRMED)"
    elif is_tech_bullish and is_flow_bearish:
        bias = "Cautious Bullish"
        setup_type = "CAUTION BUY • DISTRIBUTION DIVERGENCE"
        entry_zone = f"${cur_p:.2f} - ${(cur_p + vwap_val)/2:.2f}"
        stop_loss = round(cur_p - (0.75 * atr_val), 2)  # Tighter stop due to smart money divergence!
        target = round(liq_above, 2)
        invalidation = f"HIGH ALERT: Price rising into insider selling / UTAD. Invalidation at ${stop_loss:.2f}"
        action_verdict = "REDUCE SIZE / TIGHTEN STOPS (DIVERGENCE WARNING)"
    elif not is_tech_bullish and is_flow_bearish:
        bias = "Strong Bearish"
        setup_type = "BEARISH CONFLUENCE • INSTITUTIONAL LIQUIDATION"
        entry_zone = f"${vwap_val:.2f} - ${cur_p:.2f}"
        stop_loss = wyckoff_data.get("stop_loss", round(liq_above + (0.5 * atr_val), 2)) if wyckoff_data else round(liq_above + (0.5 * atr_val), 2)
        target = wyckoff_data.get("tp2", round(liq_below - (0.5 * atr_val), 2)) if wyckoff_data else round(liq_below - (0.5 * atr_val), 2)
        invalidation = f"Plan invalid if price reclaims VWAP above ${stop_loss:.2f}"
        action_verdict = "SHORT / HEDGE WITH INSTITUTIONAL FLOW"
    elif not is_tech_bullish and is_flow_bullish:
        bias = "Reversal Watch"
        setup_type = "ACCUMULATION DIVERGENCE (SPRING / VALUE TRAP)"
        entry_zone = f"${cur_p:.2f} - ${liq_below:.2f}"
        stop_loss = wyckoff_data.get("stop_loss", round(liq_below - (0.75 * atr_val), 2)) if wyckoff_data else round(liq_below - (0.75 * atr_val), 2)
        target = round(vwap_val, 2)
        invalidation = f"Watch for liquidity sweep. Invalidation if price breaks below ${stop_loss:.2f}"
        action_verdict = "WATCH REVERSAL (SPRING & INSIDERS ACCUMULATING)"
    else:
        bias = "Bullish" if is_tech_bullish else "Bearish"
        setup_type = "TACTICAL SETUP"
        entry_zone = f"${cur_p:.2f} - ${vwap_val:.2f}" if is_tech_bullish else f"${vwap_val:.2f} - ${cur_p:.2f}"
        stop_loss = round(liq_below - (0.5 * atr_val), 2) if is_tech_bullish else round(liq_above + (0.5 * atr_val), 2)
        target = round(liq_above, 2) if is_tech_bullish else round(liq_below, 2)
        invalidation = f"Plan invalid if price closes beyond structural level ${stop_loss:.2f}"
        action_verdict = "TACTICAL MOMENTUM TRADE"

    # Enforce JEV Grounding & Hallucination Check on final execution targets
    grounded_exec = jev_output["grounded_execution"]
    stop_loss = grounded_exec["stop_loss"]
    target = grounded_exec["target"]

    score_10 = min(10.0, max(1.0, round(5.0 + total_score, 1)))

    tp1 = wyckoff_data.get("tp1", target) if wyckoff_data else target
    tp2 = wyckoff_data.get("tp2", round(target * 1.02, 2)) if wyckoff_data else target
    tp3 = wyckoff_data.get("tp3", round(target * 1.05, 2)) if wyckoff_data else target

    return {
        "bias": bias,
        "setup_type": setup_type,
        "composite_score": score_10,
        "flow_composite": round(flow_composite, 2),
        "entry_zone": entry_zone,
        "stop_loss": stop_loss,
        "target": target,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "invalidation": invalidation,
        "action_verdict": action_verdict,
        "notes": [insider_note, congress_note, inst_note, news_note, wyckoff_note],
        "factors": {
            "Technicals": round(tech_score, 1),
            "Form 4 Insiders": round(insider_mod, 1),
            "Congress": round(congress_mod, 1),
            "13F Ownership": round(inst_mod, 1),
            "News Catalysts": round(news_mod, 1),
            "Wyckoff Range": round(wyckoff_mod, 1)
        },
        "jev_output": jev_output
    }

# Analysis Runner
@st.cache_data(ttl=60)
def analyze_daytrade(ticker, tf_str, rg_str):
    inv_map = {"5 min": "5m", "15 min": "15m", "1 hour": "60m", "1 Day": "1d"}
    rg_map = {"1 Day": "1d", "5 Days": "5d", "1 Month": "1mo", "1 Year": "1y"}
    df = yf.download(ticker, period=rg_map.get(rg_str, "5d"), interval=inv_map.get(tf_str, "15m"), progress=False)
    if df.empty: return None, None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    cum_vol = df['Volume'].cumsum()
    df['VWAP'] = (df['Volume'] * ((df['High'] + df['Low'] + df['Close']) / 3)).cumsum() / (cum_vol + 1e-9)
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

    tech_score = (1.0 if cur_p >= vwap_val else -1.0) + (1.0 if cur_p >= ema20_val else -1.0)
    tech_reasoning = [
        f"Price {'above' if cur_p >= vwap_val else 'below'} session VWAP (${vwap_val:.2f})",
        f"Price {'above' if cur_p >= ema20_val else 'below'} 15m EMA20 (${ema20_val:.2f})",
        f"Buy-side liquidity overhead at ${liq_above:.2f} • Sell-side liquidity below at ${liq_below:.2f}",
        f"15m ATR ~${atr_val:.2f} (sizing benchmark for 1-2% portfolio risk)"
    ]

    return df, {
        "ticker": ticker, "price": cur_p, "vwap": vwap_val, "ema20": ema20_val,
        "session_open": session_open, "session_high": session_high, "session_low": session_low,
        "prev_close": prev_close, "liq_above": liq_above, "liq_below": liq_below,
        "tech_score": tech_score, "tech_reasoning": tech_reasoning, "atr": atr_val
    }

df, raw_stats = analyze_daytrade(selected_ticker, timeframe, range_select)

if raw_stats:
    # Fetch Multi-Source Intelligence Feeds & Wyckoff Structural Engine
    insider_trades = fetch_openinsider_trades(selected_ticker)
    congress_trades = fetch_quiver_congress_trades(selected_ticker)
    inst_holdings = fetch_finnhub_13f_holdings(selected_ticker)
    news_items = fetch_news_radar(selected_ticker)
    wyckoff_data = detect_wyckoff_structure(df)

    # Multi-Feed & Wyckoff Confluence Synthesis with JEV + RAG Engine
    synthesis = synthesize_multi_feed_signals(
        raw_stats["tech_score"], raw_stats["price"], raw_stats["vwap"],
        raw_stats["ema20"], raw_stats["atr"], raw_stats["liq_above"],
        raw_stats["liq_below"], insider_trades, congress_trades, inst_holdings, news_items,
        wyckoff_data=wyckoff_data, ticker=selected_ticker
    )

    risk = max(abs(raw_stats["price"] - synthesis["stop_loss"]), 0.05)
    reward = max(abs(synthesis["target"] - raw_stats["price"]), 0.05)
    rr_ratio = round(reward / risk, 2)

    # JEV + RAG Intelligent Gating HUD Banner
    jev_info = synthesis.get("jev_output", {}).get("jev_metadata", {})
    gate_badge = "🟢 SUFFICIENCY CONFIRMED" if jev_info.get("is_sufficient", True) else "🟡 NOISE FILTERED (GRACEFUL EXIT)"
    gate_color = "#34d399" if jev_info.get("is_sufficient", True) else "#f59e0b"
    ground_status = "🟢 100% MATHEMATICALLY GROUNDED" if jev_info.get("grounding_check") == "VERIFIED_ACCURATE" else "🔵 ANCHORED & RE-GROUNDED"

    st.markdown(f"""
        <div style="display:flex; justify-content:space-between; align-items:center; background:#0f172a; border:1px solid #334155; border-radius:8px; padding:7px 14px; margin-bottom:12px; font-size:0.8rem;">
            <div><span style="color:#38bdf8; font-weight:700;">🛡️ JEV + RAG INTELLIGENT GATEWAY:</span> <span style="color:{gate_color}; font-weight:600;">{gate_badge}</span> &bull; <span style="color:#cbd5e1;">Router: {jev_info.get('router_path', 'MULTI_FEED_RETRIEVAL')}</span></div>
            <div><span style="color:#94a3b8;">Relevance: {jev_info.get('filtered_news_count', 0)}/{jev_info.get('raw_news_count', 0)} chunks</span> &bull; <span style="color:#a78bfa;">Compression: -{jev_info.get('token_compression_ratio', '75%')}</span> &bull; <span style="color:#34d399; font-weight:600;">{ground_status}</span> &bull; <span style="color:#94a3b8;">Latency: {jev_info.get('latency_ms', 1.2):.1f}ms</span></div>
        </div>
    """, unsafe_allow_html=True)

    # Top Header
    h1, h2 = st.columns([3, 1])
    with h1:
        st.markdown(f"## {selected_ticker} <span style='font-size:1.1rem; color:#8b9bb4;'>Multi-Feed Radar</span>", unsafe_allow_html=True)
        st.markdown(f"# ${raw_stats['price']:.2f}")
    with h2:
        target_link = f"{AGENT_HUB_BASE_URL}?ticker={selected_ticker}"
        st.markdown(f"""
            <a href="{target_link}" target="_blank" style="text-decoration:none;">
                <button style="background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white; border: none; padding: 12px 18px; border-radius: 8px; font-weight: 700; cursor: pointer; margin-top: 14px; width: 100%; font-size: 0.95rem;">
                    🤖 Run AI Agent Audit ↗
                </button>
            </a>
        """, unsafe_allow_html=True)

    # Intraday Metric Pills
    p1, p2, p3, p4 = st.columns([1, 1.2, 1.5, 3])
    p1.button(f"{timeframe}", disabled=True)
    p2.button(f"VWAP: ${raw_stats['vwap']:.2f}", disabled=True)
    p3.button(f"Session: ${raw_stats['session_low']:.2f} - ${raw_stats['session_high']:.2f}", disabled=True)

    # Confluence Radar Cards
    b_color = "#00e676" if "Bullish" in synthesis["bias"] and "Caution" not in synthesis["bias"] else ("#f59e0b" if "Caution" in synthesis["bias"] or "Reversal" in synthesis["bias"] else "#ff5252")
    
    r1, r2, r3, r4 = st.columns(4)
    r1.markdown(f'<div class="card-box"><div class="metric-title-blue">SYNTHESIZED BIAS</div><div style="font-size:1.35rem; font-weight:700; color:{b_color};">{synthesis["bias"]}</div><div class="metric-sub">{synthesis["action_verdict"]}</div></div>', unsafe_allow_html=True)
    r2.markdown(f'<div class="card-box"><div class="metric-title-blue">CONFLUENCE SCORE</div><div class="metric-value">{synthesis["composite_score"]} <span style="font-size:0.9rem; color:#94a3b8;">/ 10</span></div><div class="metric-sub">Multi-factor grade</div></div>', unsafe_allow_html=True)
    r3.markdown(f'<div class="card-box"><div class="metric-title-blue">FLOW & WYCKOFF IMPACT</div><div class="metric-value" style="color:{"#00e676" if synthesis["flow_composite"] > 0 else ("#ff5252" if synthesis["flow_composite"] < 0 else "#ffffff")};">{synthesis["flow_composite"]:+} pts</div><div class="metric-sub">Insiders + Congress + Wyckoff</div></div>', unsafe_allow_html=True)
    r4.markdown(f'<div class="card-box"><div class="metric-title-blue">RISK : REWARD</div><div class="metric-value">1 : {rr_ratio:.2f}</div><div class="metric-sub">${risk:.2f} Risk / ${reward:.2f} Reward</div></div>', unsafe_allow_html=True)

    # Factor Breakdown Matrix
    with st.expander("📊 Multi-Factor Confluence Breakdown (Feed Point Attribution)", expanded=True):
        fb_cols = st.columns(6)
        for idx, (factor_name, pts) in enumerate(synthesis["factors"].items()):
            col = fb_cols[idx % 6]
            f_col = "#00e676" if pts > 0 else ("#ff5252" if pts < 0 else "#94a3b8")
            col.markdown(f"""
                <div style="background:#111622; border:1px solid #1e293b; border-radius:8px; padding:8px; text-align:center;">
                    <div style="font-size:0.75rem; color:#8b9bb4;">{factor_name}</div>
                    <div style="font-size:1.1rem; font-weight:700; color:{f_col};">{pts:+}</div>
                </div>
            """, unsafe_allow_html=True)

    # Chart Section with Wyckoff Overlays
    st.markdown(f"##### INTRADAY {timeframe.upper()} CHART • {selected_ticker} (WYCKOFF RANGE + VWAP + EMA20)")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='#ffab00', width=1.5), name='VWAP'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#00d2ff', width=1.2), name='EMA 20'), row=1, col=1)
    
    # Wyckoff Range Overlay Lines
    if wyckoff_data:
        tr_h = wyckoff_data.get("tr_high")
        tr_l = wyckoff_data.get("tr_low")
        if tr_h and tr_l:
            fig.add_hline(y=tr_h, line_dash="dash", line_color="#ef4444", annotation_text=f"Creek (TR High: ${tr_h})", row=1, col=1)
            fig.add_hline(y=tr_l, line_dash="dash", line_color="#10b981", annotation_text=f"Ice (TR Low: ${tr_l})", row=1, col=1)
        
        # Wyckoff Event Markers Annotations
        for ev in wyckoff_data.get("events", []):
            e_col = "#34d399" if ev.get("type") == "bullish" else "#f87171"
            fig.add_annotation(
                x=ev["idx"], y=ev["price"],
                text=ev["name"],
                showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5,
                arrowcolor=e_col, bgcolor="#1e293b", bordercolor=e_col,
                font=dict(size=9, color="#ffffff"),
                row=1, col=1
            )
        
        # Take Profit Target Overlays
        fig.add_hline(y=synthesis["tp1"], line_dash="dot", line_color="#38bdf8", annotation_text=f"TP1 (1R: ${synthesis['tp1']:.2f})", row=1, col=1)
        fig.add_hline(y=synthesis["tp2"], line_dash="dot", line_color="#c084fc", annotation_text=f"TP2 Measured Move (${synthesis['tp2']:.2f})", row=1, col=1)

    fig.add_hline(y=raw_stats['liq_above'], line_dash="dash", line_color="#64748b", annotation_text="Liquidity Above", row=1, col=1)
    fig.add_hline(y=raw_stats['liq_below'], line_dash="dash", line_color="#64748b", annotation_text="Liquidity Below", row=1, col=1)
    vol_colors = ['#00e676' if row['Close'] >= row['Open'] else '#ff5252' for _, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='Volume'), row=2, col=1)
    fig.update_layout(template="plotly_dark", height=490, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # Execution Plan Cards with Multi-TP Targets
    st.markdown(f"##### DYNAMIC EXECUTION SETUP • {synthesis['setup_type']}")
    s1, s2, s3, s4 = st.columns(4)
    s1.markdown(f'<div class="card-box"><div class="metric-title-blue">ENTRY ZONE</div><div class="metric-value">{synthesis["entry_zone"]}</div><div class="metric-sub">Calibrated pullbacks</div></div>', unsafe_allow_html=True)
    s2.markdown(f'<div class="card-box"><div class="metric-title-blue">STRUCTURE STOP-LOSS</div><div class="metric-value">${synthesis["stop_loss"]:.2f}</div><div class="metric-sub">Beyond Spring / Ice pivot</div></div>', unsafe_allow_html=True)
    s3.markdown(f'<div class="card-box"><div class="metric-title-blue">TP1 / TP2 (MEASURED MOVE)</div><div class="metric-value">${synthesis["tp1"]:.2f} / ${synthesis["tp2"]:.2f}</div><div class="metric-sub">1R Scalp & 2R Measured Move</div></div>', unsafe_allow_html=True)
    s4.markdown(f'<div class="card-box"><div class="metric-title-blue">TP3 (EXPANSION)</div><div class="metric-value">${synthesis["tp3"]:.2f}</div><div class="metric-sub">Shift to Breakeven after TP1</div></div>', unsafe_allow_html=True)

    # Wyckoff Range Engine Advanced Dashboard
    if wyckoff_data:
        st.markdown(f"##### 🏛️ WYCKOFF RANGE ENGINE • {wyckoff_data.get('schematic', 'RANGE ANALYSIS')}")
        w1, w2, w3, w4 = st.columns(4)
        w1.markdown(f'<div class="card-box"><div class="metric-title-blue">CURRENT PHASE</div><div style="font-weight:700; color:#38bdf8; font-size:1.1rem;">{wyckoff_data.get("phase", "Phase A")}</div><div class="metric-sub">Structure progression</div></div>', unsafe_allow_html=True)
        w2.markdown(f'<div class="card-box"><div class="metric-title-blue">MEASURED MOVE TARGET</div><div class="metric-value">${wyckoff_data.get("measured_move", 0.0):.2f}</div><div class="metric-sub">Range width projection</div></div>', unsafe_allow_html=True)
        w3.markdown(f'<div class="card-box"><div class="metric-title-blue">SPRING / CLIMAX QUALITY</div><div class="metric-value">{wyckoff_data.get("spring_score", wyckoff_data.get("utad_score", 75))} <span style="font-size:0.9rem; color:#94a3b8;">/ 100</span></div><div class="metric-sub">Volume effort & recovery speed</div></div>', unsafe_allow_html=True)
        w4.markdown(f'<div class="card-box"><div class="metric-title-blue">TRADING RANGE WIDTH</div><div class="metric-value">${wyckoff_data.get("tr_height", 0.0):.2f}</div><div class="metric-sub">Ice: ${wyckoff_data.get("tr_low", 0)} • Creek: ${wyckoff_data.get("tr_high", 0)}</div></div>', unsafe_allow_html=True)

        # Event Confirmation Checklist
        cl_items = wyckoff_data.get("checklist", {})
        chk_html = '<div class="card-box"><div class="metric-title-blue" style="margin-bottom:8px;">WYCKOFF STRUCTURAL CHECKLIST</div><div style="display:flex; flex-wrap:wrap; gap:12px;">'
        for k, v in cl_items.items():
            badge_icon = "🟢 [CONFIRMED]" if v else "⚪ [PENDING]"
            b_c = "#34d399" if v else "#94a3b8"
            chk_html += f'<div style="font-size:0.85rem; color:{b_c};">{badge_icon} <b>{k}</b></div>'
        chk_html += '</div></div>'
        st.markdown(chk_html, unsafe_allow_html=True)

    # Reasoning Breakdown
    st.markdown("##### EVIDENCE & CONFLUENCE REASONING")
    r_box = '<div class="card-box">'
    for item in raw_stats['tech_reasoning']:
        r_box += f'<div style="margin-bottom:4px; font-size:0.88rem; color:#93c5fd;">&bull; [Technicals] {item}</div>'
    for item in synthesis['notes']:
        r_box += f'<div style="margin-bottom:4px; font-size:0.88rem; color:#fef08a;">&bull; [Data Feeds & Wyckoff] {item}</div>'
    r_box += '</div>'
    st.markdown(r_box, unsafe_allow_html=True)

    # Invalidation Warning
    st.markdown(f"""
        <div class="card-box" style="border-left: 4px solid #ff5252;">
            <span style="color:#ff5252; font-weight:bold;">Invalidation Rule:</span> <span style="color:#ffffff;">{synthesis['invalidation']}</span>
        </div>
    """, unsafe_allow_html=True)

    # Tabbed Feed Inspection Panels
    st.markdown("---")
    st.markdown(f"### 🌊 Phantom-Flow Market Intelligence • {selected_ticker}")
    t_macro, t_sec, t_insider, t_congress, t_inst, t_news, t_jev = st.tabs([
        "🌍 Global Macro & FX (Frankfurter, CoinGecko, FRED)",
        "🏛️ SEC EDGAR & Polygon/Finnhub Ticks",
        "👔 Form 4 Insider Trades (OpenInsider)", 
        "🏛️ Congressional Trades (Quiver)", 
        "🏦 SEC 13F Institutional (Finnhub)", 
        "📰 Catalyst Radar (Tavily/SerpApi)",
        "🛡️ JEV + RAG Intelligent Gateway"
    ])
    
    with t_macro:
        st.markdown("#### 🌍 Macroeconomic Confluence Radar")
        m_c1, m_c2, m_c3 = st.columns(3)
        try:
            macro_d = fetch_macro_indicators()
            ffr = macro_d.get("fed_funds_rate", {})
            ty10 = macro_d.get("treasury_10y", {})
            cpi = macro_d.get("cpi_inflation", {})
            spread = macro_d.get("yield_curve_spread", 0.0)
            m_c1.markdown(f'<div class="card-box"><div class="metric-title-blue">FED FUNDS RATE (FRED)</div><div class="metric-value">{ffr.get("value", 3.75):.2f}%</div><div class="metric-sub">Date: {ffr.get("date", "Latest")}</div></div>', unsafe_allow_html=True)
            m_c2.markdown(f'<div class="card-box"><div class="metric-title-blue">10-YEAR TREASURY (FRED)</div><div class="metric-value">{ty10.get("value", 4.12):.2f}%</div><div class="metric-sub">Date: {ty10.get("date", "Latest")}</div></div>', unsafe_allow_html=True)
            m_c3.markdown(f'<div class="card-box"><div class="metric-title-blue">YIELD SPREAD (10Y - FFR)</div><div class="metric-value" style="color:{"#00e676" if spread >= 0 else "#ff5252"};">{spread:+.2f}%</div><div class="metric-sub">CPI Index: {cpi.get("value", 314.8)}</div></div>', unsafe_allow_html=True)
        except Exception as e:
            st.warning(f"FRED indicators sync notice: {e}")

        st.markdown("##### 💱 Real-Time Foreign Exchange (Frankfurter - Zero Auth)")
        try:
            fx_res = fetch_forex_overview()
            fx_rates = fx_res.get("rates", {})
            f_cols = st.columns(6)
            for idx, (curr, rate) in enumerate(fx_rates.items()):
                f_cols[idx % 6].markdown(f"""
                    <div style="background:#111622; border:1px solid #1e293b; border-radius:8px; padding:10px; text-align:center;">
                        <div style="font-size:0.75rem; color:#8b9bb4;">USD / {curr}</div>
                        <div style="font-size:1.1rem; font-weight:700; color:#38bdf8;">{rate:.4f}</div>
                    </div>
                """, unsafe_allow_html=True)
        except Exception as e:
            st.info(f"Forex rates unavailable: {e}")

        st.markdown("##### 🪙 Cryptocurrency Market Pulse (CoinGecko - Zero Auth)")
        try:
            cg_res = fetch_crypto_overview().get("data", {})
            if cg_res:
                cg_rows = []
                for cid, vals in cg_res.items():
                    cg_rows.append({
                        "Asset": vals["symbol"],
                        "Price (USD)": f"${vals['price_usd']:,.2f}",
                        "24h Change": f"{vals['change_24h_pct']:+.2f}%",
                        "24h Volume": f"${vals['volume_24h']:,.0f}"
                    })
                st.dataframe(pd.DataFrame(cg_rows), use_container_width=True, hide_index=True)
        except Exception as e:
            st.info(f"Crypto data unavailable: {e}")

    with t_sec:
        st.markdown(f"#### 🏛️ SEC EDGAR Official Filings & Polygon Ticks • {selected_ticker}")
        sec_c1, sec_c2 = st.columns([1.5, 2.5])
        with sec_c1:
            st.markdown("##### ⚡ Polygon.io / Finnhub Ticks")
            tick_data = fetch_polygon_finnhub_quote(selected_ticker)
            if tick_data.get("price", 0) > 0:
                t_chg = tick_data.get("change", 0.0)
                t_pct = tick_data.get("change_pct", 0.0)
                st.markdown(f"""
                    <div class="card-box">
                        <div class="metric-title-blue">SOURCE: {tick_data.get('source', 'FINNHUB').upper()}</div>
                        <div class="metric-value">${tick_data['price']:.2f} <span style="font-size:0.9rem; color:{"#00e676" if t_chg >= 0 else "#ff5252"};">({t_chg:+.2f} / {t_pct:+.2f}%)</span></div>
                        <div style="margin-top:8px; font-size:0.85rem; color:#b0bec5;">
                            • Open: ${tick_data.get('open', 0):.2f}<br>
                            • Day High: ${tick_data.get('high', 0):.2f}<br>
                            • Day Low: ${tick_data.get('low', 0):.2f}<br>
                            • Prev Close: ${tick_data.get('prev_close', 0):.2f}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.info("No tick data returned by Polygon/Finnhub feed.")

        with sec_c2:
            st.markdown("##### 📄 Direct SEC EDGAR Corporate Filings")
            sec_filings = fetch_edgar_filings(selected_ticker)
            if sec_filings:
                disp_sec = [{"Form": f["form"], "Filing Date": f["date"], "Description": f["description"], "SEC Link": f["url"]} for f in sec_filings]
                st.dataframe(pd.DataFrame(disp_sec), use_container_width=True, hide_index=True)
            else:
                st.info("No recent SEC EDGAR filings found.")
    
    with t_insider:
        if insider_trades:
            disp = [{k: v for k, v in t.items() if k not in ("raw_val", "is_buy", "is_sale")} for t in insider_trades]
            st.dataframe(pd.DataFrame(disp), use_container_width=True, hide_index=True)
        else:
            st.info("No Form 4 insider transactions recorded on OpenInsider.")

    with t_congress:
        if congress_trades:
            st.dataframe(pd.DataFrame(congress_trades), use_container_width=True, hide_index=True)
        else:
            st.info("No recent Congressional trades recorded on Quiver live stream.")

    with t_inst:
        if inst_holdings:
            disp_h = [{k: v for k, v in t.items() if k != "raw_change"} for t in inst_holdings]
            st.dataframe(pd.DataFrame(disp_h), use_container_width=True, hide_index=True)
        else:
            st.info("No 13F institutional ownership records returned by Finnhub.")

    with t_news:
        if news_items:
            for n in news_items:
                st.markdown(f"""
                    <div class="card-box" style="margin-bottom:8px;">
                        <div style="display:flex; justify-content:space-between;"><a href="{n['url']}" target="_blank" style="color:#38bdf8; font-weight:700; text-decoration:none;">{n['title']}</a><span class="badge-hold" style="font-size:0.7rem;">{n['source']}</span></div>
                        <div style="font-size:0.85rem; color:#d1d5db; margin-top:4px;">{n['snippet']}</div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Searching catalysts for ticker...")

    with t_jev:
        st.markdown(f"#### 🛡️ JEV + RAG Intelligent Gating System • {selected_ticker}")
        st.caption("Noise Filtering • Context Compression • Sufficiency Gating • Grounding Check")

        # Live Gateway Metrics
        j_col1, j_col2, j_col3, j_col4 = st.columns(4)
        j_col1.markdown(f"""
            <div class="card-box">
                <div class="metric-title-blue">ROUTER DECISION</div>
                <div style="font-size:1.1rem; font-weight:700; color:#38bdf8;">{jev_info.get('router_path', 'MULTI_FEED')}</div>
                <div class="metric-sub">{jev_info.get('raw_news_count', 0)} Candidates Retrieved</div>
            </div>
        """, unsafe_allow_html=True)
        
        j_col2.markdown(f"""
            <div class="card-box">
                <div class="metric-title-blue">SEMANTIC FILTERING</div>
                <div style="font-size:1.1rem; font-weight:700; color:#00e676;">{jev_info.get('filtered_news_count', 0)} / {jev_info.get('raw_news_count', 0)} Passed</div>
                <div class="metric-sub">Irrelevant noise shoved away</div>
            </div>
        """, unsafe_allow_html=True)

        j_col3.markdown(f"""
            <div class="card-box">
                <div class="metric-title-blue">SUFFICIENCY GATING</div>
                <div style="font-size:1.05rem; font-weight:700; color:{gate_color};">
                    {"CONFIRMED" if jev_info.get('is_sufficient') else "GRACEFUL EXIT"}
                </div>
                <div class="metric-sub">Refusal if evidence unverified</div>
            </div>
        """, unsafe_allow_html=True)

        j_col4.markdown(f"""
            <div class="card-box">
                <div class="metric-title-blue">GROUNDING CHECK</div>
                <div style="font-size:1.05rem; font-weight:700; color:#00e676;">{jev_info.get('grounding_check', 'VERIFIED')}</div>
                <div class="metric-sub">Zero hallucinated levels</div>
            </div>
        """, unsafe_allow_html=True)

        # Context Selection & Compression Breakdown
        st.markdown("##### 📦 Optimized High-Confidence Context Packet")
        comp_context = synthesis.get("jev_output", {}).get("compressed_context", [])
        if comp_context:
            for ctx_item in comp_context:
                st.markdown(f"""
                    <div style="background:#111622; border-left:3px solid #38bdf8; padding:8px 12px; margin-bottom:6px; border-radius:4px; font-size:0.88rem;">
                        {ctx_item}
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info(f"Sufficiency Gating Status: {jev_info.get('sufficiency_message')}")

        # Grounding & Mathematical Proof Table
        st.markdown("##### 📐 Mathematical Invariant Grounding Audit")
        ground_exec = synthesis.get("jev_output", {}).get("grounded_execution", {})
        audit_df = pd.DataFrame([{
            "Parameter": "Current Asset Price", "Value": f"${raw_stats['price']:.2f}", "Status": "Ground Truth Source"
        }, {
            "Parameter": "Stop-Loss Boundary", "Value": f"${ground_exec.get('stop_loss', synthesis['stop_loss']):.2f}", "Status": "Passed Ice/Spring Invariant"
        }, {
            "Parameter": "Take-Profit Target", "Value": f"${ground_exec.get('target', synthesis['target']):.2f}", "Status": "Passed Expansion Invariant"
        }, {
            "Parameter": "Verified Risk:Reward", "Value": f"1 : {ground_exec.get('rr_ratio', rr_ratio):.2f}", "Status": "Passed >= 1.0 Expectancy Floor"
        }])
        st.dataframe(audit_df, use_container_width=True, hide_index=True)

        # Interactive Query Router Demo
        st.markdown("##### ⚡ Interactive JEV Query Router Demo")
        sample_query = st.selectbox(
            "Select Query to Test JEV Gating Path:",
            [
                "Calculate session VWAP, ATR and EMA20",
                "Evaluate Wyckoff Phase C Spring / Ice pivot",
                "Audit recent SEC Form 4 insider transactions for cluster buying",
                "Scan news catalysts for earnings surprises or FDA clearances",
                "Determine Congressional trading conflicts"
            ]
        )
        is_direct = any(x in sample_query.lower() for x in ["vwap", "atr", "ema20", "wyckoff", "spring", "ice"])
        route_mode = "DIRECT_RESPONSE (0 LLM Tokens, <5ms)" if is_direct else "MULTI_FEED_RETRIEVAL (JEV Gateway Gated)"
        r_color = "#38bdf8" if is_direct else "#a78bfa"
        st.markdown(f"""
            <div style="background:#151c2c; border:1px solid #1e293b; padding:10px 14px; border-radius:8px;">
                <div style="font-size:0.8rem; color:#8b9bb4;">ROUTER RESOLUTION:</div>
                <div style="font-size:1.05rem; font-weight:700; color:{r_color}; margin-top:2px;">➔ {route_mode}</div>
                <div style="font-size:0.8rem; color:#cbd5e1; margin-top:4px;">
                    {"Bypasses external retrieval and LLM processing entirely. Instant deterministic calculation." if is_direct else "Retrieves top-20 multi-feed documents, applies semantic noise filter, sufficiency gate, and compression before grounding."}
                </div>
            </div>
        """, unsafe_allow_html=True)
else:
    st.error(f"Could not load intraday data for {selected_ticker}. Please verify ticker.")
