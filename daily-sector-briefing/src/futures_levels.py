"""ES / NQ / VIX key levels for the user's futures & index-options trading.

Provides prior-day high/low/close, ATR-based expected daily range, VIX-implied 1-day
move, and a coarse SPX 'gamma flip' proxy (the round level nearest spot, where dealer
hedging often pivots). The exact gamma model requires an options-OI feed (paid upgrade).
"""
from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np
import pandas as pd

from .indicators import atr


def levels_for(df: Optional[pd.DataFrame], label: str) -> dict:
    if df is None or len(df) < 2:
        return {"symbol": label, "available": False}
    prior = df.iloc[-2]
    last = df.iloc[-1]
    a = float(atr(df, 14).iloc[-1]) if len(df) > 14 else float(df["high"].iloc[-1] - df["low"].iloc[-1])
    close = float(last["close"])
    return {
        "symbol": label,
        "available": True,
        "last": close,
        "prior_high": float(prior["high"]),
        "prior_low": float(prior["low"]),
        "prior_close": float(prior["close"]),
        "atr": round(a, 2),
        "expected_range": [round(close - a, 2), round(close + a, 2)],
    }


def vix_implied_move(spx_last: float, vix_last: float) -> dict:
    if not spx_last or not vix_last or np.isnan(vix_last):
        return {"available": False}
    daily = vix_last / math.sqrt(252)  # % 1-sigma daily move
    return {
        "available": True,
        "vix": round(float(vix_last), 2),
        "implied_daily_move_pct": round(float(daily), 2),
        "implied_band": [
            round(spx_last * (1 - daily / 100), 2),
            round(spx_last * (1 + daily / 100), 2),
        ],
    }


def gamma_flip_proxy(spx_last: float, step: int = 25) -> dict:
    """Coarse proxy: nearest large round strike to spot (common dealer pivot)."""
    if not spx_last:
        return {"available": False}
    flip = round(spx_last / step) * step
    return {"available": True, "proxy_level": float(flip),
            "note": "Round-strike proxy; exact GEX needs an options-OI feed."}


def build_futures_panel(bars: Dict[str, pd.DataFrame], spx_last: float,
                        vix_last: float) -> dict:
    return {
        "ES": levels_for(bars.get("ES=F"), "ES (S&P 500 future)"),
        "NQ": levels_for(bars.get("NQ=F"), "NQ (Nasdaq-100 future)"),
        "VIX_implied": vix_implied_move(spx_last, vix_last),
        "gamma_flip": gamma_flip_proxy(spx_last),
    }
