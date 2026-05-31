"""Deterministic synthetic data so the pipeline + report render with no network.

Used by `run_briefing.py --demo` and by unit tests. Generates plausible daily bars,
options chains, fundamentals, and news for a list of symbols.
"""
from __future__ import annotations

import datetime as dt
from typing import Dict, List

import numpy as np
import pandas as pd

from .calendar_utils import last_completed_trading_day, trading_days


def _series(symbol: str, days: List[pd.Timestamp], seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(days)
    drift = rng.normal(0.0004, 0.0006)
    rets = rng.normal(drift, 0.015, n)
    price = 100 * np.exp(np.cumsum(rets)) * (1 + (seed % 7))
    close = pd.Series(price, index=days)
    high = close * (1 + np.abs(rng.normal(0, 0.008, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.008, n)))
    open_ = close.shift(1).fillna(close.iloc[0])
    vol = rng.integers(1_000_000, 30_000_000, n)
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close, "volume": vol}, index=days)


class DemoProvider:
    name = "demo"

    def __init__(self, as_of: dt.datetime | None = None):
        end = last_completed_trading_day(as_of)
        self.days = trading_days((end - dt.timedelta(days=420)).date(), end.date())

    def get_daily_bars(self, symbols: List[str], lookback_days: int = 260) -> Dict[str, pd.DataFrame]:
        days = self.days[-(lookback_days + 5):]
        return {s: _series(s, days, abs(hash(s)) % 9973) for s in symbols}

    def get_grouped_daily(self, date: str):
        return None  # force per-symbol path in demo

    def get_options_chain(self, symbol: str) -> pd.DataFrame:
        rng = np.random.default_rng(abs(hash(symbol)) % 9973)
        spot = 100 + (abs(hash(symbol)) % 200)
        strikes = np.round(np.linspace(spot * 0.8, spot * 1.2, 9))
        rows = []
        exp = (dt.date.today() + dt.timedelta(days=14)).isoformat()
        for k in strikes:
            for side in ("call", "put"):
                rows.append({
                    "expiry": exp, "type": side, "strike": float(k),
                    "lastPrice": float(rng.uniform(0.5, 8)),
                    "volume": int(rng.integers(0, 5000)),
                    "openInterest": int(rng.integers(100, 4000)),
                    "impliedVolatility": float(rng.uniform(0.2, 0.6)),
                })
        return pd.DataFrame(rows)

    def get_fundamentals(self, symbol: str) -> dict:
        rng = np.random.default_rng(abs(hash(symbol)) % 9973)
        pe = float(rng.uniform(8, 55))
        return {
            "trailingPE": pe,
            "forwardPE": pe * float(rng.uniform(0.7, 1.0)),
            "pegRatio": float(rng.uniform(0.6, 3.0)),
            "profitMargins": float(rng.uniform(-0.05, 0.35)),
            "revenueGrowth": float(rng.uniform(-0.1, 0.45)),
            "earningsGrowth": float(rng.uniform(-0.2, 0.4)),
            "recommendationMean": float(rng.uniform(1.5, 4.0)),
            "marketCap": float(rng.integers(2, 3200)) * 1e9,
            "debtToEquity": float(rng.uniform(5, 220)),
        }

    def get_news(self, symbols: List[str], limit: int = 5) -> Dict[str, list]:
        samples = ["{} beats earnings, raises guidance", "{} downgraded on weak demand",
                   "{} announces buyback", "{} faces lawsuit over disclosures"]
        out = {}
        for i, s in enumerate(symbols):
            out[s] = [{"title": samples[(i + j) % len(samples)].format(s),
                       "publisher": "DemoWire", "link": "#", "published": ""}
                      for j in range(2)]
        return out
