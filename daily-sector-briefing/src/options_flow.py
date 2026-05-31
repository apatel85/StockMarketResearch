"""Options flow analytics from a chain snapshot.

Derives put/call ratios, volume/open-interest (unusual activity), a coarse IV reading,
and an ATM-straddle expected move. Works on the columns produced by the providers:
expiry, type, strike, lastPrice, volume, openInterest, impliedVolatility.

Note: free/EOD chains are snapshots, not live sweep/dark-pool flow. This surfaces
*relative* positioning; true order-flow tape is a documented paid upgrade.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def analyze_chain(chain: Optional[pd.DataFrame], spot: float,
                  unusual_ratio: float = 2.0, near_expiries: int = 3) -> dict:
    if chain is None or chain.empty:
        return {"available": False}

    df = chain.copy()
    for c in ["volume", "openInterest", "impliedVolatility", "strike", "lastPrice"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["strike", "type"])

    # Restrict to the nearest N expiries (most flow-relevant).
    expiries = sorted(df["expiry"].dropna().unique())[:near_expiries]
    near = df[df["expiry"].isin(expiries)]

    call_vol = float(near.loc[near["type"] == "call", "volume"].sum())
    put_vol = float(near.loc[near["type"] == "put", "volume"].sum())
    call_oi = float(near.loc[near["type"] == "call", "openInterest"].sum())
    put_oi = float(near.loc[near["type"] == "put", "openInterest"].sum())

    pc_vol = put_vol / call_vol if call_vol else float("nan")
    pc_oi = put_oi / call_oi if call_oi else float("nan")

    # Unusual activity: per-contract volume / open interest.
    near = near.assign(
        vol_oi=near["volume"] / near["openInterest"].replace(0, np.nan)
    )
    unusual = near[near["vol_oi"] >= unusual_ratio].sort_values("volume", ascending=False)

    # ATM IV + expected move from the nearest expiry's ATM straddle.
    atm_iv, exp_move = _atm_metrics(near, spot, expiries[:1])

    bias = _flow_bias(pc_vol, call_vol, put_vol)
    return {
        "available": True,
        "call_volume": call_vol,
        "put_volume": put_vol,
        "pc_ratio_vol": pc_vol,
        "pc_ratio_oi": pc_oi,
        "atm_iv": atm_iv,
        "expected_move_pct": exp_move,
        "unusual_count": int(len(unusual)),
        "unusual_top": unusual.head(5)[
            ["expiry", "type", "strike", "volume", "openInterest", "vol_oi"]
        ].to_dict("records"),
        "bias": bias,
    }


def _atm_metrics(near: pd.DataFrame, spot: float, expiries) -> tuple:
    if not len(expiries) or not spot or np.isnan(spot):
        return float("nan"), float("nan")
    front = near[near["expiry"] == expiries[0]]
    if front.empty:
        return float("nan"), float("nan")
    front = front.assign(dist=(front["strike"] - spot).abs())
    atm_strike = front.sort_values("dist")["strike"].iloc[0]
    atm = front[front["strike"] == atm_strike]
    iv = float(atm["impliedVolatility"].mean())
    call = atm[atm["type"] == "call"]["lastPrice"].mean()
    put = atm[atm["type"] == "put"]["lastPrice"].mean()
    straddle = np.nansum([call, put])
    exp_move = float(straddle / spot * 100) if spot else float("nan")
    return iv, exp_move


def _flow_bias(pc_vol: float, call_vol: float, put_vol: float) -> str:
    if not call_vol and not put_vol:
        return "neutral"
    if np.isnan(pc_vol):
        return "neutral"
    if pc_vol < 0.7:
        return "bullish"
    if pc_vol > 1.3:
        return "bearish"
    return "neutral"


def iv_rank(iv_history: pd.Series) -> float:
    """IV rank (0-100) of the latest value within its trailing range."""
    s = pd.to_numeric(iv_history, errors="coerce").dropna()
    if len(s) < 2:
        return float("nan")
    lo, hi = s.min(), s.max()
    if hi == lo:
        return float("nan")
    return float((s.iloc[-1] - lo) / (hi - lo) * 100)
