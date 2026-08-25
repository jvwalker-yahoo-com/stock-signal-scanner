import os
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

st.set_page_config(page_title="Stock Signal Scanner", layout="wide", initial_sidebar_state="expanded")

# Dark Terminal Styling matching the Screenshot
st.markdown("""
<style>
    .reportview-container, .main, .block-container { background-color: #0b0e14; color: #f0f2f6; }
    div[data-testid="stSidebar"] { background-color: #111622; border-right: 1px solid #1e2638; }
    .card-box { background-color: #151c2c; border: 1px solid #222d44; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
    .metric-title { font-size: 0.8rem; color: #8b9bb4; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
    .metric-value { font-size: 1.4rem; font-weight: 700; color: #ffffff; }
    .metric-sub { font-size: 0.75rem; color: #6b7c96; margin-top: 2px; }
    .bias-bullish { color: #00e676; font-weight: bold; }
    .bias-bearish { color: #ff5252; font-weight: bold; }
    .badge-buy { background-color: #0d3829; color: #00e676; border: 1px solid #00e676; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; }
    .badge-sell { background-color: #3d141a; color: #ff5252; border: 1px solid #ff5252; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; }
    .badge-hold { background-color: #3b3114; color: #ffd600; border: 1px solid #ffd600; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

FINNHUB_KEY = st.secrets.get("FINNHUB_API_KEY", os.getenv("FINNHUB_API_KEY", "da02ec1r01qgk75qq5v0da02ec1r01qgk75qq5vg"))

DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "AMD",
    "NFLX", "JPM", "BAC", "XOM", "KO", "PEP", "DIS", "INTC",
    "MARA", "IREN", "SOXL", "TQQQ", "APLD", "SPY", "QQQ", "URA", "HOOD", "SOFI"
]

# --- Quick Watchlist State Helper ---
if "watchlist" not in st.session_state:
    st.session_state.watchlist = list(DEFAULT_WATCHLIST)

# --- Top Navigation Bar ---
top_c1, top_c2, top_c3, top_c4 = st.columns([3, 1.2, 1.2, 1.2])
with top_c1:
    st.markdown("### ⚡ Stock Signal Scanner")
    st.caption("Candlestick structure analysis • Trend, momentum & buy/sell execution zones")
with top_c2:
    timeframe = st.selectbox("Interval", ["15 min", "5 min", "1 hour", "1 Day"], index=0)
with top_c3:
    range_select = st.selectbox("Lookback", ["5 Days", "1 Day", "1 Month", "1 Year"], index=0)
with top_c4:
    mode = st.radio("Trading Mode", ["Day Trader", "Swing Trader"], horizontal=True)

# --- Watchlist Quick-Fetcher ---
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
                
                # Fast mini score
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

# Sidebar Mini Watchlist Display
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

# --- Intraday & Day Trader Engine ---
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

    # 1. EMA 20
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()

    # 2. Intraday VWAP
    cum_vol = df['Volume'].cumsum()
    cum_vol_price = (df['Volume'] * ((df['High'] + df['Low'] + df['Close']) / 3)).cumsum()
    df['VWAP'] = cum_vol_price / (cum_vol + 1e-9)

    # 3. ATR (14)
    tr = pd.concat([df['High'] - df['Low'], np.abs(df['High'] - df['Close'].shift()), np.abs(df['Low'] - df['Close'].shift())], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()

    last = df.iloc[-1]
    cur_p = round(float(last['Close']), 2)
    vwap_val = round(float(last['VWAP']), 2)
    ema20_val = round(float(last['EMA20']), 2)
    atr_val = round(float(last['ATR']), 2) if not np.isnan(last['ATR']) else 0.5

    # Session Stats
    session_open = round(float(df['Open'].iloc[-1]), 2)
    session_high = round(float(df['High'].tail(16).max()), 2)
    session_low = round(float(df['Low'].tail(16).min()), 2)
    prev_close = round(float(df['Close'].iloc[-2]), 2) if len(df) > 1 else cur_p

    # Liquidity Zones (Local swing points)
    liq_above = round(float(df['High'].tail(30).max()), 2)
    liq_below = round(float(df['Low'].tail(30).min()), 2)

    # Bias Logic
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

    # Trend of VWAP
    if df['VWAP'].iloc[-1] >= df['VWAP'].iloc[-5]:
        reasoning.append("VWAP sloping upward over the lookback")
    else:
        reasoning.append("VWAP sloping downward over the lookback")

    if bias_score <= -1.0:
        bias = "Bearish"
        bias_color = "red"
        setup_type = "BEARISH"
        entry_zone = f"${vwap_val:.2f} - ${cur_p:.2f}"
        stop_loss = round(liq_above + (0.5 * atr_val), 2)
        target = round(liq_below, 2)
        invalidation = f"Plan invalid if price closes above ${stop_loss:.2f}"
        reasoning.append("Bearish break of structure - close below recent intraday pivot")
    else:
        bias = "Bullish"
        bias_color = "green"
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
        "ticker": ticker,
        "price": cur_p,
        "bias": bias,
        "bias_score": abs(bias_score) + 1.5,
        "bias_color": bias_color,
        "vwap": vwap_val,
        "ema20": ema20_val,
        "session_open": session_open,
        "session_high": session_high,
        "session_low": session_low,
        "prev_close": prev_close,
        "liq_above": liq_above,
        "liq_below": liq_below,
        "setup_type": setup_type,
        "entry_zone": entry_zone,
        "stop_loss": stop_loss,
        "target": target,
        "rr_ratio": rr_ratio,
        "risk_dollars": round(risk, 2),
        "reward_dollars": round(reward, 2),
        "invalidation": invalidation,
        "reasoning": reasoning
    }

# --- Main Dashboard Execution ---
df, stats = analyze_daytrade(selected_ticker, timeframe, range_select)

if stats:
    # 1. Top Section
    st.markdown(f"## {stats['ticker']} <span style='font-size:1.1rem; color:#8b9bb4;'>Day Trader</span>", unsafe_allow_html=True)
    st.markdown(f"# ${stats['price']:.2f}")
    
    # Intraday Pills
    p1, p2, p3, p4 = st.columns([1, 1.2, 1.5, 3])
    p1.button(f"{timeframe}", disabled=True)
    p2.button(f"VWAP: ${stats['vwap']:.2f}", disabled=True)
    p3.button(f"Session: ${stats['session_low']:.2f} - ${stats['session_high']:.2f}", disabled=True)

    # Bias Box
    b_class = "bias-bullish" if stats["bias"] == "Bullish" else "bias-bearish"
    st.markdown(
        f"""
        <div class="card-box" style="margin-top:10px; width: 300px;">
            <div class="metric-title">INTRADAY BIAS</div>
            <div class="{b_class}" style="font-size: 1.6rem;">{stats['bias']}</div>
            <div class="metric-sub">Bias score: {stats['bias_score']:.1f}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 2. Intraday Chart Section
    st.markdown(f"##### INTRADAY {timeframe.upper()} CHART • {stats['ticker']} (VWAP + EMA20, DASHED = LIQUIDITY)")
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
    
    # Candlestick
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['VWAP'], line=dict(color='#ffab00', width=1.5), name='VWAP'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#00d2ff', width=1.2), name='EMA 20'), row=1, col=1)
    
    # Liquidity Levels (Dashed)
    fig.add_hline(y=stats['liq_above'], line_dash="dash", line_color="#ff5252", annotation_text="Liquidity Above", row=1, col=1)
    fig.add_hline(y=stats['liq_below'], line_dash="dash", line_color="#00e676", annotation_text="Liquidity Below", row=1, col=1)

    # Volume
    colors = ['#00e676' if row['Close'] >= row['Open'] else '#ff5252' for _, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)

    fig.update_layout(template="plotly_dark", height=500, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # 3. Setup Cards
    st.markdown(f"##### SETUP • {stats['setup_type']}")
    s1, s2, s3 = st.columns(3)
    
    with s1:
        st.markdown(
            f"""
            <div class="card-box">
                <div class="metric-title">ENTRY ZONE</div>
                <div class="metric-value">{stats['entry_zone']}</div>
                <div class="metric-sub">Pullback to VWAP / Market</div>
            </div>
            """, unsafe_allow_html=True
        )
    with s2:
        st.markdown(
            f"""
            <div class="card-box">
                <div class="metric-title">STOP-LOSS</div>
                <div class="metric-value">${stats['stop_loss']:.2f}</div>
                <div class="metric-sub">Beyond structural pivot</div>
            </div>
            """, unsafe_allow_html=True
        )
    with s3:
        st.markdown(
            f"""
            <div class="card-box">
                <div class="metric-title">TARGET</div>
                <div class="metric-value">${stats['target']:.2f}</div>
                <div class="metric-sub">Liquidity / Measured move</div>
            </div>
            """, unsafe_allow_html=True
        )

    # Risk Management Note
    st.markdown(
        f"""
        <div class="card-box" style="border-left: 4px solid #2962ff;">
            <div class="metric-title">RISK : REWARD &bull; 1 : {stats['rr_ratio']:.2f} (${stats['risk_dollars']:.2f} Risk / ${stats['reward_dollars']:.2f} Reward)</div>
            <div style="font-size:0.85rem; color:#b0bec5; margin-top:4px;">
                Risk 1-2% of capital per trade. Max daily loss 4-6% - stop trading after 2 consecutive losses. No averaging down - cut losers fast. Target reward:risk between 1.5:1 and 3:1.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 4. Key Levels Grid
    st.markdown("##### KEY LEVELS")
    k1, k2, k3 = st.columns(3)
    k4, k5, k6 = st.columns(3)

    k1.markdown(f'<div class="card-box"><div class="metric-title">VWAP</div><div class="metric-value">${stats["vwap"]:.2f}</div><div class="metric-sub">Intraday Anchor</div></div>', unsafe_allow_html=True)
    k2.markdown(f'<div class="card-box"><div class="metric-title">SESSION OPEN</div><div class="metric-value">${stats["session_open"]:.2f}</div><div class="metric-sub">Reference Open</div></div>', unsafe_allow_html=True)
    k3.markdown(f'<div class="card-box"><div class="metric-title">SESSION HIGH</div><div class="metric-value">${stats["session_high"]:.2f}</div><div class="metric-sub">Buy-Side Liquidity</div></div>', unsafe_allow_html=True)

    k4.markdown(f'<div class="card-box"><div class="metric-title">SESSION LOW</div><div class="metric-value">${stats["session_low"]:.2f}</div><div class="metric-sub">Sell-Side Liquidity</div></div>', unsafe_allow_html=True)
    k5.markdown(f'<div class="card-box"><div class="metric-title">PREV CLOSE</div><div class="metric-value">${stats["prev_close"]:.2f}</div><div class="metric-sub">Reference Pivot</div></div>', unsafe_allow_html=True)
    k6.markdown(f'<div class="card-box"><div class="metric-title">LIQUIDITY ABOVE</div><div class="metric-value">${stats["liq_above"]:.2f}</div><div class="metric-sub">Pivot Highs</div></div>', unsafe_allow_html=True)

    # 5. Reasoning Breakdown
    st.markdown("##### REASONING")
    r_box = '<div class="card-box">'
    for item in stats['reasoning']:
        r_box += f'<div style="margin-bottom:6px; font-size:0.9rem;">&bull; {item}</div>'
    r_box += '</div>'
    st.markdown(r_box, unsafe_allow_html=True)

    # 6. Invalidation Box
    st.markdown("##### INVALIDATION • ALTERNATIVE")
    st.markdown(
        f"""
        <div class="card-box" style="border-left: 4px solid #ff5252;">
            <span style="color:#ff5252; font-weight:bold;">Invalidation:</span> {stats['invalidation']}
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.error(f"Could not load intraday data for {selected_ticker}. Please verify ticker.")
