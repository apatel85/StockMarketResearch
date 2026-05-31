"""Pure-pandas technical indicators (no external TA dependency).

Each function takes/returns pandas objects and is unit-tested against known values.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(100.0).where(avg_loss != 0, 100.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def relative_strength(close: pd.Series, bench_close: pd.Series, window: int = 20) -> float:
    """Stock return minus benchmark return over `window` sessions (in %)."""
    if len(close) <= window or len(bench_close) <= window:
        return float("nan")
    stock_ret = close.iloc[-1] / close.iloc[-window - 1] - 1
    bench_ret = bench_close.iloc[-1] / bench_close.iloc[-window - 1] - 1
    return float((stock_ret - bench_ret) * 100)


def volume_surge(volume: pd.Series, lookback: int = 20) -> float:
    """Latest volume divided by trailing average volume."""
    if len(volume) <= lookback:
        return float("nan")
    avg = volume.iloc[-lookback - 1 : -1].mean()
    if not avg:
        return float("nan")
    return float(volume.iloc[-1] / avg)


def gap_pct(df: pd.DataFrame) -> float:
    """Most recent open vs prior close, in %."""
    if len(df) < 2:
        return float("nan")
    return float((df["open"].iloc[-1] / df["close"].iloc[-2] - 1) * 100)


def pivots(df: pd.DataFrame) -> Dict[str, float]:
    """Classic floor-trader pivots from the most recent completed bar."""
    if df.empty:
        return {}
    h, l, c = df["high"].iloc[-1], df["low"].iloc[-1], df["close"].iloc[-1]
    p = (h + l + c) / 3
    return {
        "pivot": float(p),
        "r1": float(2 * p - l), "s1": float(2 * p - h),
        "r2": float(p + (h - l)), "s2": float(p - (h - l)),
    }


def compute_features(df: pd.DataFrame, bench: pd.Series | None = None,
                     cfg: dict | None = None) -> dict:
    """Bundle the indicator readings the scoring layer consumes for one symbol."""
    cfg = cfg or {}
    close = df["close"]
    smas = {w: float(sma(close, w).iloc[-1]) for w in cfg.get("sma_windows", [20, 50, 200])
            if len(close) >= w}
    last = float(close.iloc[-1])
    macd_df = macd(close, **(cfg.get("macd") or {}))
    feats = {
        "last": last,
        "rsi": float(rsi(close, cfg.get("rsi_period", 14)).iloc[-1]),
        "macd_hist": float(macd_df["hist"].iloc[-1]),
        "atr": float(atr(df, cfg.get("atr_period", 14)).iloc[-1]) if len(df) > 14 else float("nan"),
        "sma": smas,
        "above_sma": {w: last > v for w, v in smas.items()},
        "vol_surge": volume_surge(df["volume"], cfg.get("volume_surge_lookback", 20)),
        "gap_pct": gap_pct(df),
        "pivots": pivots(df),
        "ret_1d": float(close.iloc[-1] / close.iloc[-2] - 1) * 100 if len(close) > 1 else float("nan"),
        "ret_5d": float(close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) > 5 else float("nan"),
    }
    if bench is not None:
        feats["rel_strength_20"] = relative_strength(close, bench, 20)
    return feats
