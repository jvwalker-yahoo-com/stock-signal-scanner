import os
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import finnhub

st.set_page_config(page_title="Stock Signal Scanner", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .reportview-container, .main, .block-container { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #1a1f2c; padding: 12px; border-radius: 8px; border: 1px solid #2d3748; }
</style>
""", unsafe_allow_html=True)

finnhub_key = st.secrets.get("FINNHUB_API_KEY", os.getenv("FINNHUB_API_KEY", ""))
finnhub_client = finnhub.Client(api_key=finnhub_key) if finnhub_key else None

DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "AMD",
    "NFLX", "JPM", "BAC", "XOM", "KO", "PEP", "DIS", "INTC",
    "MARA", "IREN", "SOXL", "TQQQ", "APLD", "SPY", "QQQ", "URA", "HOOD", "SOFI"
]

st.sidebar.title("⚡ Stock Signal Scanner")
horizon = st.sidebar.selectbox(
    "Trading Horizon",
    ["Short Term (1-3 Weeks)", "Medium Term (1-3 Months)", "Long Term (6-12 Months)"],
    index=1
)
horizon_key = "short" if "Short" in horizon else ("medium" if "Medium" in horizon else "long")

custom_ticker = st.sidebar.text_input("Add Ticker to Scan", "").upper().strip()
watchlist = list(DEFAULT_WATCHLIST)
if custom_ticker and custom_ticker not in watchlist:
    watchlist.insert(0, custom_ticker)

selected_ticker = st.sidebar.selectbox("Select Asset", watchlist, index=0)

@st.cache_data(ttl=1800)
def get_finnhub_data(ticker):
    data = {
        "target_mean": None, "target_high": None, "target_low": None,
        "analyst_consensus": "N/A", "buy_ratings": 0, "hold_ratings": 0,
        "sell_ratings": 0, "insider_sentiment": "Neutral"
    }
    if not finnhub_client:
        return data

    try:
        pt = finnhub_client.price_target(ticker)
        if pt and pt.get("targetMean"):
            data["target_mean"] = round(float(pt["targetMean"]), 2)
            data["target_high"] = round(float(pt["targetHigh"]), 2)
            data["target_low"] = round(float(pt["targetLow"]), 2)

        recs = finnhub_client.recommendation_trends(ticker)
        if recs and len(recs) > 0:
            latest = recs[0]
            data["buy_ratings"] = latest.get("strongBuy", 0) + latest.get("buy", 0)
            data["hold_ratings"] = latest.get("hold", 0)
            data["sell_ratings"] = latest.get("sell", 0) + latest.get("strongSell", 0)
            if data["buy_ratings"] > (data["hold_ratings"] + data["sell_ratings"]):
                data["analyst_consensus"] = "Bullish Consensus"
            elif data["sell_ratings"] > (data["buy_ratings"] + data["hold_ratings"]):
                data["analyst_consensus"] = "Bearish Consensus"
            else:
                data["analyst_consensus"] = "Neutral / Mixed"

        sentiment = finnhub_client.stock_insider_sentiment(ticker, '2025-01-01', '2026-08-01')
        if sentiment and sentiment.get("data") and len(sentiment["data"]) > 0:
            latest_mspr = sentiment["data"][-1].get("mspr", 0)
            if latest_mspr > 20:
                data["insider_sentiment"] = "Net Insider Accumulation"
            elif latest_mspr < -20:
                data["insider_sentiment"] = "Insider Selling Pressure"
            else:
                data["insider_sentiment"] = "Balanced"
    except Exception:
        pass

    return data

@st.cache_data(ttl=900)
def analyze_asset(ticker, horizon_mode):
    interval = "1d" if horizon_mode in ["short", "medium"] else "1wk"
    period = "1y" if horizon_mode == "short" else ("2y" if horizon_mode == "medium" else "5y")
    
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if df.empty:
        return None, None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    ma_fast_len = 20 if horizon_mode == "short" else 50
    ma_slow_len = 50 if horizon_mode == "short" else 200
    df['SMA_Fast'] = df['Close'].rolling(ma_fast_len).mean()
    df['SMA_Slow'] = df['Close'].rolling(ma_slow_len).mean()

    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))

    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    tr = pd.concat([df['High'] - df['Low'], np.abs(df['High'] - df['Close'].shift()), np.abs(df['Low'] - df['Close'].shift())], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()

    last = df.iloc[-1]
    cur_p = round(float(last['Close']), 2)
    atr_val = float(last['ATR'])

    score = 0.0
    drivers = []

    if last['Close'] > last['SMA_Fast']:
        score += 1.5
        drivers.append(f"Price above {ma_fast_len}-day SMA")
    else:
        score -= 1.5
        drivers.append(f"Price below {ma_fast_len}-day SMA")

    if last['SMA_Fast'] > last['SMA_Slow']:
        score += 1.5
        drivers.append(f"SMA{ma_fast_len} > SMA{ma_slow_len} (Macro Uptrend)")
    else:
        score -= 1.5
        drivers.append(f"SMA{ma_fast_len} < SMA{ma_slow_len} (Macro Downtrend)")

    rsi_val = float(last['RSI'])
    if rsi_val >= 60:
        score += 1.5
        drivers.append(f"RSI {rsi_val:.1f} Bullish Momentum")
    elif rsi_val <= 40:
        score -= 1.5
        drivers.append(f"RSI {rsi_val:.1f} Bearish Momentum")
    else:
        drivers.append(f"RSI {rsi_val:.1f} Neutral Consolidation")

    if last['MACD'] > last['MACD_Signal']:
        score += 1.5
        drivers.append("MACD > Signal (Bullish Momentum)")
    else:
        score -= 1.5
        drivers.append("MACD < Signal (Bearish Momentum)")

    fh_data = get_finnhub_data(ticker)
    if fh_data.get("target_mean"):
        upside = ((fh_data["target_mean"] - cur_p) / cur_p) * 100
        if upside > 15:
            score += 2.0
            drivers.append(f"Wall St. Target: ${fh_data['target_mean']} (+{upside:.1f}% Upside)")
        elif upside < -5:
            score -= 2.0
            drivers.append(f"Wall St. Target: ${fh_data['target_mean']} ({upside:.1f}% Downside)")
        else:
            drivers.append(f"Wall St. Target: ${fh_data['target_mean']} (Fair Value)")

    if "Bullish" in fh_data.get("analyst_consensus", ""):
        score += 1.0
        drivers.append(f"Wall Street Consensus: {fh_data['buy_ratings']} Buys vs {fh_data['sell_ratings']} Sells")
    elif "Bearish" in fh_data.get("analyst_consensus", ""):
        score -= 1.0
        drivers.append("Wall Street Consensus: Majority Sell Ratings")

    if "Accumulation" in fh_data.get("insider_sentiment", ""):
        score += 1.0
        drivers.append("Finnhub Insider Signals: Net Insider Accumulation")

    score = round(max(-10.0, min(10.0, score)), 1)
    if score >= 6.0: rating = "STRONG BUY"
    elif score >= 2.0: rating = "BUY"
    elif score <= -6.0: rating = "STRONG SELL"
    elif score <= -2.0: rating = "SELL"
    else: rating = "HOLD"

    lookback = 30 if horizon_mode == "short" else (60 if horizon_mode == "medium" else 120)
    support = round(float(df['Low'].tail(lookback).min()), 2)
    resistance = fh_data["target_mean"] if fh_data.get("target_mean") and fh_data["target_mean"] > cur_p else round(float(df['High'].tail(lookback).max()), 2)
    
    atr_mult = 1.0 if horizon_mode == "short" else (2.0 if horizon_mode == "medium" else 3.0)
    buy_zone_upper = round(support + (atr_mult * atr_val), 2)
    stop_loss = round(support - (0.5 * atr_mult * atr_val), 2)
    
    risk = max(cur_p - stop_loss, 0.01)
    reward = max(resistance - cur_p, 0.01)
    rr_ratio = round(reward / risk, 2)

    return df, {
        "ticker": ticker, "price": cur_p, "rating": rating, "score": score,
        "rsi": rsi_val, "buy_zone": f"${support:.2f} - ${buy_zone_upper:.2f}",
        "target": f"${resistance:.2f}", "stop_loss": f"${stop_loss:.2f}",
        "risk_reward": f"1 : {rr_ratio}", "support": support, "resistance": resistance,
        "buy_zone_upper": buy_zone_upper, "finnhub": fh_data, "drivers": drivers
    }

df, stats = analyze_asset(selected_ticker, horizon_key)

if stats:
    st.header(f"{stats['ticker']} — ${stats['price']:.2f} USD")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Signal Rating", stats['rating'])
    col2.metric("Composite Score", f"{stats['score']} / 10")
    col3.metric("RSI (14)", f"{stats['rsi']:.1f}")
    col4.metric("Risk / Reward", stats['risk_reward'])

    fh = stats["finnhub"]
    st.subheader("🏛️ Institutional & Analyst Intelligence (Finnhub)")
    f1, f2, f3 = st.columns(3)
    f1.metric("Wall St. Target", f"${fh['target_mean']}" if fh.get('target_mean') else "N/A", f"High: ${fh['target_high']} | Low: ${fh['target_low']}" if fh.get('target_high') else None)
    f2.metric("Analyst Consensus", fh['analyst_consensus'], f"{fh['buy_ratings']} Buys | {fh['hold_ratings']} Holds | {fh['sell_ratings']} Sells")
    f3.metric("Insider Sentiment", fh['insider_sentiment'])

    st.subheader("🎯 Position Parameters")
    r1, r2, r3 = st.columns(3)
    r1.info(f"**Accumulation Zone:**\n{stats['buy_zone']}")
    r2.success(f"**Target Objective:**\n{stats['target']}")
    r3.error(f"**Structural Stop-Loss:**\n{stats['stop_loss']}")

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_Fast'], line=dict(color='orange', width=1.5), name='Fast SMA'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_Slow'], line=dict(color='purple', width=1.5), name='Slow SMA'), row=1, col=1)
    fig.add_hrect(y0=stats['support'], y1=stats['buy_zone_upper'], fillcolor="green", opacity=0.15, line_width=0, row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='#00d2ff', width=1.5), name='RSI'), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#2962FF', width=1), name='MACD'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], line=dict(color='#FF6D00', width=1), name='Signal'), row=3, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name='Hist'), row=3, col=1)

    fig.update_layout(template="plotly_dark", height=650, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("🔍 Decision Drivers")
    for d in stats['drivers']:
        st.markdown(f"- {d}")
else:
    st.error("Unable to load data. Please check ticker.")
