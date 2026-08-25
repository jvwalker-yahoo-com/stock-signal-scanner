import os
import json
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from openai import OpenAI
import requests

st.set_page_config(
    page_title="TradingAgents Hub",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark styling matching the agent terminal design
st.markdown("""
<style>
    .reportview-container, .main, .block-container { background-color: #0b0e14; color: #f0f2f6; }
    div[data-testid="stSidebar"] { background-color: #111622; border-right: 1px solid #1e2638; }
    .agent-card { background-color: #151c2c; border: 1px solid #1e293b; border-radius: 10px; padding: 16px; margin-bottom: 14px; }
    .agent-header { font-size: 1.05rem; font-weight: 700; margin-bottom: 6px; display: flex; align-items: center; gap: 8px; }
    .agent-title-blue { color: #38bdf8; }
    .agent-title-purple { color: #c084fc; }
    .agent-title-green { color: #4ade80; }
    .agent-title-orange { color: #fb923c; }
    .verdict-box { background-color: #0f172a; border: 2px solid #2563eb; border-radius: 10px; padding: 18px; margin-top: 10px; }
    .metric-val { font-size: 1.3rem; font-weight: bold; color: #ffffff; }
    .metric-lbl { font-size: 0.8rem; color: #38bdf8; text-transform: uppercase; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# API Keys setup
openai_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
finnhub_key = st.secrets.get("FINNHUB_API_KEY", os.getenv("FINNHUB_API_KEY", "da02ec1r01qgk75qq5v0da02ec1r01qgk75qq5vg"))
base_url = st.secrets.get("OPENAI_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))

# Auto-read ticker passed via URL Query Params (e.g., ?ticker=AAPL)
url_params = st.query_params
initial_ticker = url_params.get("ticker", "NVDA").upper()

# --- Sidebar Configuration ---
st.sidebar.title("🤖 TradingAgents Hub")
st.sidebar.caption("Multi-Agent Autonomous Market Intelligence")

api_key_input = st.sidebar.text_input("OpenAI / OpenRouter API Key", value=openai_key, type="password")
model_choice = st.sidebar.selectbox(
    "LLM Engine",
    ["gpt-4o-mini", "gpt-4o", "deepseek-chat", "claude-3-5-sonnet"],
    index=0
)

ticker_input = st.sidebar.text_input("Asset Ticker", value=initial_ticker).upper().strip()
time_horizon = st.sidebar.selectbox("Agent Strategy Horizon", ["Day Trade (15m/1h)", "Swing Trade (Daily)", "Position (Macro)"], index=1)

run_agents = st.sidebar.button("🚀 Run Agent Committee", use_container_width=True)

# Auto-trigger run if launched from URL parameter
auto_run = False
if "ticker" in url_params and "auto_evaluated" not in st.session_state:
    auto_run = True
    st.session_state.auto_evaluated = True

# --- Finnhub Data Engine ---
@st.cache_data(ttl=300)
def fetch_finnhub_intel(ticker, token):
    intel = {
        "target_mean": "N/A", "target_high": "N/A", "target_low": "N/A",
        "buy_recs": 0, "hold_recs": 0, "sell_recs": 0, "consensus": "N/A",
        "insider_bias": "Neutral"
    }
    if not token:
        return intel

    try:
        url_pt = f"https://finnhub.io/api/v1/stock/price-target?symbol={ticker}&token={token}"
        r_pt = requests.get(url_pt, timeout=4).json()
        if r_pt and r_pt.get("targetMean"):
            intel["target_mean"] = round(float(r_pt["targetMean"]), 2)
            intel["target_high"] = round(float(r_pt.get("targetHigh", 0)), 2)
            intel["target_low"] = round(float(r_pt.get("targetLow", 0)), 2)

        url_rec = f"https://finnhub.io/api/v1/stock/recommendation?symbol={ticker}&token={token}"
        r_rec = requests.get(url_rec, timeout=4).json()
        if isinstance(r_rec, list) and len(r_rec) > 0:
            top = r_rec[0]
            intel["buy_recs"] = int(top.get("strongBuy", 0) + top.get("buy", 0))
            intel["hold_recs"] = int(top.get("hold", 0))
            intel["sell_recs"] = int(top.get("sell", 0) + top.get("strongSell", 0))
            
            if intel["buy_recs"] > (intel["hold_recs"] + intel["sell_recs"]):
                intel["consensus"] = "Bullish Outperform"
            elif intel["sell_recs"] > (intel["buy_recs"] + intel["hold_recs"]):
                intel["consensus"] = "Bearish Underperform"
            else:
                intel["consensus"] = "Hold / Neutral"

        url_ins = f"https://finnhub.io/api/v1/stock/insider-sentiment?symbol={ticker}&from=2025-01-01&token={token}"
        r_ins = requests.get(url_ins, timeout=4).json()
        if r_ins and r_ins.get("data") and len(r_ins["data"]) > 0:
            mspr = float(r_ins["data"][-1].get("mspr", 0))
            if mspr > 10:
                intel["insider_bias"] = "Net Insider Accumulation"
            elif mspr < -10:
                intel["insider_bias"] = "Net Insider Selling Pressure"
            else:
                intel["insider_bias"] = "Neutral / Balanced"
    except Exception:
        pass
    return intel

# --- Technical & Yahoo Finance Data ---
@st.cache_data(ttl=300)
def fetch_market_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo", interval="1d")
        if df.empty:
            return None, None
        
        info = stock.info
        df['SMA20'] = df['Close'].rolling(20).mean()
        df['SMA50'] = df['Close'].rolling(50).mean()
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        df['RSI'] = 100 - (100 / (1 + rs))
        
        latest = df.iloc[-1]
        
        tech_summary = {
            "current_price": round(float(latest['Close']), 2),
            "sma20": round(float(latest['SMA20']), 2),
            "sma50": round(float(latest['SMA50']), 2),
            "rsi": round(float(latest['RSI']), 2),
            "market_cap": info.get("marketCap", "N/A"),
            "pe_ratio": info.get("trailingPE", "N/A"),
            "forward_pe": info.get("forwardPE", "N/A"),
            "revenue_growth": info.get("revenueGrowth", "N/A"),
            "profit_margins": info.get("profitMargins", "N/A")
        }
        return df, tech_summary
    except Exception:
        return None, None

def query_llm(prompt, client, model):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a hedge fund intelligence engine leading an autonomous multi-agent quantitative committee."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error executing agent: {str(e)}"

# --- Layout ---
df, stats = fetch_market_data(ticker_input)
fh_intel = fetch_finnhub_intel(ticker_input, finnhub_key)

if df is not None and stats is not None:
    st.markdown(f"## {ticker_input} — <span style='color:#00d2ff;'>${stats['current_price']:.2f} USD</span>", unsafe_allow_html=True)
    
    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(f'<div class="agent-card"><div class="metric-lbl">RSI (14)</div><div class="metric-val">{stats["rsi"]}</div></div>', unsafe_allow_html=True)
    m2.markdown(f'<div class="agent-card"><div class="metric-lbl">50 SMA</div><div class="metric-val">${stats["sma50"]}</div></div>', unsafe_allow_html=True)
    m3.markdown(f'<div class="agent-card"><div class="metric-lbl">Finnhub Target</div><div class="metric-val">${fh_intel["target_mean"]}</div></div>', unsafe_allow_html=True)
    m4.markdown(f'<div class="agent-card"><div class="metric-lbl">Wall St. Consensus</div><div class="metric-val" style="font-size:1.1rem;">{fh_intel["consensus"]}</div></div>', unsafe_allow_html=True)

    if run_agents or auto_run:
        if not api_key_input:
            st.error("Please provide an OpenAI or OpenRouter API Key in the sidebar.")
        else:
            client = OpenAI(api_key=api_key_input, base_url=base_url)
            st.markdown("### 🏛️ Autonomous Agent Deliberation")
            
            with st.status("Executing Agent Committee Workflow...", expanded=True) as status:
                st.write("📈 **Technical Strategist** evaluating price action & moving averages...")
                prompt_tech = f"""
                Analyze the technical setup for {ticker_input} (Horizon: {time_horizon}):
                - Current Price: ${stats['current_price']}
                - 20 SMA: ${stats['sma20']} | 50 SMA: ${stats['sma50']}
                - RSI: {stats['rsi']}
                Provide key support/resistance levels, trend health, and immediate entry bias. Keep under 110 words.
                """
                tech_report = query_llm(prompt_tech, client, model_choice)

                st.write("📊 **Fundamental Analyst** parsing Finnhub targets & valuation multiples...")
                prompt_fund = f"""
                Evaluate the fundamentals and valuation for {ticker_input}:
                - Trailing P/E: {stats['pe_ratio']} | Forward P/E: {stats['forward_pe']}
                - Profit Margins: {stats['profit_margins']} | Revenue Growth: {stats['revenue_growth']}
                - Finnhub Wall St Consensus Target: ${fh_intel['target_mean']} (High: ${fh_intel['target_high']}, Low: ${fh_intel['target_low']})
                - Wall St Rating Breakdown: {fh_intel['buy_recs']} Buys, {fh_intel['hold_recs']} Holds, {fh_intel['sell_recs']} Sells
                Give a sharp assessment of valuation margin of safety. Keep under 110 words.
                """
                fund_report = query_llm(prompt_fund, client, model_choice)

                st.write("🌐 **Sentiment & Insider Agent** analyzing Finnhub executive transactions & macro drivers...")
                prompt_sent = f"""
                Review market sentiment and executive insider signals for {ticker_input}:
                - Finnhub Insider Sentiment Status: {fh_intel['insider_bias']}
                - Wall St Recommendation Consensus: {fh_intel['consensus']}
                Identify 2 primary upside catalysts and 2 critical tail-risk threats. Keep under 100 words.
                """
                sent_report = query_llm(prompt_sent, client, model_choice)

                st.write("⚖️ **Chief Risk Officer** adjudicating setup, invalidation & position sizing...")
                prompt_cro = f"""
                You are the Chief Risk Officer. Adjudicate the committee findings for {ticker_input} (Price: ${stats['current_price']}):
                TECHNICALS: {tech_report}
                FUNDAMENTALS & FINNHUB TARGET: {fund_report}
                SENTIMENT & INSIDER FLOW: {sent_report}

                Deliver the final execution mandate in this exact structured format:
                - FINAL ACTION: [STRONG BUY / BUY / HOLD / SELL / STRONG SELL]
                - CONVICTION SCORE: [1-10]
                - ENTRY ZONE: [Price range]
                - STOP LOSS: [Hard invalidation price]
                - TARGET OBJECTIVE: [Take-profit price]
                - RISK SIZING: [Recommended capital risk % / leverage guideline]
                - COMMITTEE RATIONALE: [2 punchy sentences summarizing the core trade thesis]
                """
                cro_verdict = query_llm(prompt_cro, client, model_choice)
                status.update(label="Committee Deliberation Complete!", state="complete", expanded=False)

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"""
                <div class="agent-card">
                    <div class="agent-header agent-title-blue">📈 Technical Strategist</div>
                    <div style="font-size: 0.9rem; color: #e2e8f0;">{tech_report}</div>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"""
                <div class="agent-card">
                    <div class="agent-header agent-title-green">📊 Fundamental Analyst (Finnhub Data)</div>
                    <div style="font-size: 0.9rem; color: #e2e8f0;">{fund_report}</div>
                </div>
                """, unsafe_allow_html=True)

            with col_b:
                st.markdown(f"""
                <div class="agent-card">
                    <div class="agent-header agent-title-purple">🌐 Sentiment & Insider Agent (Finnhub MSPR)</div>
                    <div style="font-size: 0.9rem; color: #e2e8f0;">{sent_report}</div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(f"""
                <div class="agent-card">
                    <div class="agent-header agent-title-orange">⚖️ Committee Consensus</div>
                    <div style="font-size: 0.85rem; color: #94a3b8;">Aggregated quantitative technicals, Finnhub analyst estimates, and insider flow metrics.</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("### 🎯 Chief Risk Officer (Execution Mandate)")
            st.markdown(f"""
            <div class="verdict-box">
                <div style="white-space: pre-line; font-size: 0.95rem; color: #f8fafc; line-height: 1.6;">
                {cro_verdict}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("👈 Set your strategy horizon and click **Run Agent Committee** in the sidebar to begin autonomous analysis.")
else:
    st.error(f"Could not retrieve market data for '{ticker_input}'. Please check the symbol.")
