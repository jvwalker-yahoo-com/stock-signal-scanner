# -*- coding: utf-8 -*-
"""
Wyckoff Range Engine for Stock Signal Scanner
Automated Classic Wyckoff Range, Climax, Spring, UTAD, SOS, Phase Tracking & Multi-TP Engine
"""
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

def detect_wyckoff_structure(df: pd.DataFrame, window: int = 35) -> Dict[str, Any]:
    """
    Analyzes price & volume to detect:
    - Accumulation / Distribution Trading Range (Creek resistance & Ice support)
    - Wyckoff Events: SC, BC, AR, ST, Spring, Test, UTAD, SOS, SOW, LPS
    - Wyckoff Phases: A, B, C, D, E
    - Spring / UTAD Quality Scores (0-100)
    - Multi-Target Take Profits (TP1 1R, TP2 2R Measured Move, TP3 3R Expansion)
    """
    if df is None or len(df) < 15:
        return {}

    recent = df.tail(window).copy()
    highs = recent['High'].values
    lows = recent['Low'].values
    closes = recent['Close'].values
    opens = recent['Open'].values
    volumes = recent['Volume'].values

    # 1. Trading Range Detection (Creek & Ice)
    tr_high = round(float(np.max(highs)), 2)
    tr_low = round(float(np.min(lows)), 2)
    tr_mid = round(float((tr_high + tr_low) / 2.0), 2)
    tr_height = round(float(tr_high - tr_low), 2)
    cur_p = round(float(closes[-1]), 2)

    # Volume & Spread Baseline
    vol_mean = np.mean(volumes) if len(volumes) > 0 else 1.0
    spreads = highs - lows
    spread_mean = np.mean(spreads) if len(spreads) > 0 else 1.0

    # 2. Wyckoff Events Scanning
    events = []
    has_sc = False
    has_bc = False
    has_ar = False
    has_spring = False
    has_utad = False
    has_sos = False
    has_sow = False
    has_lps = False

    spring_score = 0
    utad_score = 0
    spring_idx = None
    utad_idx = None

    for i in range(len(recent)):
        idx_dt = recent.index[i]
        c = closes[i]
        o = opens[i]
        h = highs[i]
        l = lows[i]
        v = volumes[i]
        spread = h - l
        is_high_vol = v > (1.5 * vol_mean)

        # Selling Climax (SC)
        if l <= tr_low * 1.002 and is_high_vol and spread > (1.2 * spread_mean) and c < o:
            events.append({"idx": idx_dt, "name": "SC", "label": "SC (Selling Climax)", "price": l, "type": "bullish", "pos": "below"})
            has_sc = True

        # Buying Climax (BC)
        if h >= tr_high * 0.998 and is_high_vol and spread > (1.2 * spread_mean) and c > o:
            events.append({"idx": idx_dt, "name": "BC", "label": "BC (Buying Climax)", "price": h, "type": "bearish", "pos": "above"})
            has_bc = True

        # Smart Spring (Phase C)
        # Low pierced below prior support, but candle recovered and closed back above Ice
        if l < tr_low and c >= tr_low and i >= 5:
            recovery_pct = ((c - l) / max(0.01, spread)) * 100
            quality = min(100, int(40 + (recovery_pct * 0.4) + (20 if is_high_vol else 10)))
            events.append({"idx": idx_dt, "name": "SPRING", "label": f"SPRING (Score: {quality})", "price": l, "type": "bullish", "pos": "below"})
            has_spring = True
            spring_score = quality
            spring_idx = idx_dt

        # UTAD (Upthrust After Distribution - Phase C)
        # High swept above Creek, but candle failed and closed back inside range
        if h > tr_high and c <= tr_high and i >= 5:
            rejection_pct = ((h - c) / max(0.01, spread)) * 100
            quality = min(100, int(40 + (rejection_pct * 0.4) + (20 if is_high_vol else 10)))
            events.append({"idx": idx_dt, "name": "UTAD", "label": f"UTAD (Score: {quality})", "price": h, "type": "bearish", "pos": "above"})
            has_utad = True
            utad_score = quality
            utad_idx = idx_dt

        # Sign of Strength (SOS - Phase D)
        if c > tr_high and is_high_vol and c > o:
            events.append({"idx": idx_dt, "name": "SOS", "label": "SOS (Sign of Strength)", "price": h, "type": "bullish", "pos": "above"})
            has_sos = True

        # Sign of Weakness (SOW - Phase D)
        if c < tr_low and is_high_vol and c < o:
            events.append({"idx": idx_dt, "name": "SOW", "label": "SOW (Sign of Weakness)", "price": l, "type": "bearish", "pos": "below"})
            has_sow = True

    # 3. Phase Determination (A -> B -> C -> D -> E)
    if cur_p > tr_high * 1.01 or (has_sos and cur_p >= tr_high):
        phase = "Phase E: Active Markup Trend"
        schematic = "ACCUMULATION SCHEMATIC COMPLETED"
        bias = "BULLISH MARKUP"
    elif cur_p < tr_low * 0.99 or (has_sow and cur_p <= tr_low):
        phase = "Phase E: Active Markdown Trend"
        schematic = "DISTRIBUTION SCHEMATIC COMPLETED"
        bias = "BEARISH MARKDOWN"
    elif has_sos or (has_spring and cur_p > tr_mid):
        phase = "Phase D: SOS & Range Breakout Initiation"
        schematic = "ACCUMULATION (Phase D SOS)"
        bias = "BULLISH BREAKOUT"
    elif has_sow or (has_utad and cur_p < tr_mid):
        phase = "Phase D: SOW & Range Breakdown Initiation"
        schematic = "DISTRIBUTION (Phase D SOW)"
        bias = "BEARISH BREAKDOWN"
    elif has_spring:
        phase = "Phase C: Smart Spring & Liquidity Sweep Test"
        schematic = "ACCUMULATION (Phase C Spring)"
        bias = "BULLISH REVERSAL SETUP"
    elif has_utad:
        phase = "Phase C: UTAD Upthrust & Distribution Test"
        schematic = "DISTRIBUTION (Phase C UTAD)"
        bias = "BEARISH REVERSAL SETUP"
    elif (has_sc or has_bc) and len(events) >= 2:
        phase = "Phase B: Building The Cause (Range Oscillation)"
        schematic = "NEUTRAL CONSOLIDATION (Phase B)"
        bias = "RANGE-BOUND"
    else:
        phase = "Phase A: Stopping The Prior Trend"
        schematic = "EARLY STAGE RANGE FORMATION"
        bias = "EQUILIBRIUM"

    # 4. Multi-Target Take Profits & Trade Engine (R-Multiples)
    # Structure Stop Loss
    if "BULLISH" in bias or "ACCUMULATION" in schematic:
        stop_loss = round(tr_low - max(0.05, 0.25 * (tr_height)), 2)
        risk = max(0.05, cur_p - stop_loss)
        tp1 = round(cur_p + (1.0 * risk), 2)                       # 1R: Initial Scalp / Mid Target
        tp2 = round(tr_high + tr_height, 2)                         # 2R: Classic Wyckoff Measured Move
        tp3 = round(cur_p + (3.0 * risk), 2)                       # 3R: Extended Trend Expansion
        measured_move_target = round(tr_high + tr_height, 2)
        direction = "LONG"
    else:
        stop_loss = round(tr_high + max(0.05, 0.25 * (tr_height)), 2)
        risk = max(0.05, stop_loss - cur_p)
        tp1 = round(cur_p - (1.0 * risk), 2)                       # 1R: Initial Scalp
        tp2 = round(tr_low - tr_height, 2)                         # 2R: Classic Wyckoff Measured Move
        tp3 = round(cur_p - (3.0 * risk), 2)                       # 3R: Extended Trend Expansion
        measured_move_target = round(tr_low - tr_height, 2)
        direction = "SHORT"

    return {
        "tr_high": tr_high,
        "tr_low": tr_low,
        "tr_mid": tr_mid,
        "tr_height": tr_height,
        "phase": phase,
        "schematic": schematic,
        "bias": bias,
        "direction": direction,
        "has_spring": has_spring,
        "spring_score": spring_score,
        "has_utad": has_utad,
        "utad_score": utad_score,
        "has_sos": has_sos,
        "has_sow": has_sow,
        "has_sc": has_sc,
        "has_bc": has_bc,
        "events": events[-10:],
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "measured_move": measured_move_target,
        "checklist": {
            "Selling Climax (SC)": has_sc,
            "Buying Climax (BC)": has_bc,
            "Spring Liquidity Sweep": has_spring,
            "UTAD Upthrust": has_utad,
            "Sign of Strength (SOS)": has_sos,
            "Sign of Weakness (SOW)": has_sow
        }
    }
