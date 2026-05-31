"""Composite confidence scoring — fuses technical, fundamental, sentiment, and flow.

Produces a directional bias and a 0-100 confidence used to rank long/short ideas.
A symmetric design: the same engine scores bullish and bearish setups.
"""
from __future__ import annotations

from typing import Dict

import numpy as np


def technical_score(feats: dict) -> dict:
    """0-100 technical sub-score (higher = more bullish) with notes."""
    score = 50.0
    notes = []
    above = feats.get("above_sma", {})
    if above:
        bull = sum(1 for v in above.values() if v)
        score += (bull - len(above) / 2) * 8
        if above.get(50) and above.get(200):
            notes.append("above 50 & 200 DMA (uptrend)")
        elif not above.get(50) and not above.get(200):
            notes.append("below 50 & 200 DMA (downtrend)")

    rsi = feats.get("rsi")
    if rsi == rsi:
        if rsi > 70:
            score += 4; notes.append(f"RSI {rsi:.0f} overbought")
        elif rsi < 30:
            score -= 4; notes.append(f"RSI {rsi:.0f} oversold")
        elif rsi > 55:
            score += 6
        elif rsi < 45:
            score -= 6

    if feats.get("macd_hist", 0) > 0:
        score += 6; notes.append("MACD positive")
    else:
        score -= 6

    rs = feats.get("rel_strength_20")
    if rs is not None and rs == rs:
        score += float(np.clip(rs, -10, 10))
        if rs > 3:
            notes.append(f"+{rs:.1f}% vs SPY (leader)")
        elif rs < -3:
            notes.append(f"{rs:.1f}% vs SPY (laggard)")

    vs = feats.get("vol_surge")
    if vs is not None and vs == vs and vs > 1.5:
        notes.append(f"volume {vs:.1f}x avg")

    return {"score": float(max(0.0, min(100.0, score))), "notes": notes}


def flow_score(flow: dict) -> dict:
    if not flow or not flow.get("available"):
        return {"score": 50.0, "notes": ["no options data"]}
    bias = flow.get("bias", "neutral")
    score = {"bullish": 68.0, "neutral": 50.0, "bearish": 32.0}[bias]
    notes = [f"options flow {bias} (P/C {flow.get('pc_ratio_vol', float('nan')):.2f})"]
    if flow.get("unusual_count"):
        score += min(10, flow["unusual_count"])
        notes.append(f"{flow['unusual_count']} unusual contracts")
    return {"score": float(max(0.0, min(100.0, score))), "notes": notes}


def composite(feats: dict, fundamental: dict, sentiment: dict, flow: dict,
              weights: Dict[str, float]) -> dict:
    """Blend sub-scores -> {bias, confidence, components, notes}."""
    tech = technical_score(feats)
    flw = flow_score(flow)
    comps = {
        "technical": tech["score"],
        "fundamental": fundamental.get("score", 50.0),
        "sentiment": sentiment.get("score", 50.0),
        "flow": flw["score"],
    }
    blended = sum(comps[k] * weights.get(k, 0.0) for k in comps)
    # Distance from neutral (50) = conviction; direction = sign.
    bias = "long" if blended >= 50 else "short"
    confidence = abs(blended - 50.0) * 2.0  # 0..100
    notes = tech["notes"] + flw["notes"] + fundamental.get("notes", []) + \
        ([f"news tone {sentiment['tone']['pos']}+/{sentiment['tone']['neg']}-"]
         if sentiment.get("tone") else [])
    return {
        "bias": bias,
        "confidence": float(round(min(100.0, confidence), 1)),
        "raw": float(round(blended, 1)),
        "components": {k: round(v, 1) for k, v in comps.items()},
        "notes": notes[:8],
        "earnings_soon": fundamental.get("earnings_soon", False),
    }
