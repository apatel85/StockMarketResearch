"""Hybrid provider: route each data type to the best available source.

- Equity EOD bars / grouped-daily / news -> Polygon (free tier) when a key is present.
- Options chains / fundamentals -> yfinance.
- If no Polygon key, fall back to yfinance for everything.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

import pandas as pd

from .polygon_provider import PolygonProvider
from .yfinance_provider import YFinanceProvider


def build_provider(name: str = "hybrid"):
    name = (name or "hybrid").lower()
    if name == "polygon":
        return PolygonProvider()
    if name == "yfinance":
        return YFinanceProvider()
    return HybridProvider()


class HybridProvider:
    name = "hybrid"

    def __init__(self):
        self.yf = YFinanceProvider()
        self.poly = PolygonProvider() if os.environ.get("POLYGON_API_KEY") else None

    @property
    def has_polygon(self) -> bool:
        return self.poly is not None

    def get_grouped_daily(self, date: str) -> Optional[pd.DataFrame]:
        if self.poly:
            return self.poly.get_grouped_daily(date)
        return None

    def get_daily_bars(
        self, symbols: List[str], lookback_days: int = 260
    ) -> Dict[str, pd.DataFrame]:
        if self.poly:
            bars = self.poly.get_daily_bars(symbols, lookback_days)
            missing = [s for s in symbols if s not in bars]
            if missing:
                bars.update(self.yf.get_daily_bars(missing, lookback_days))
            return bars
        return self.yf.get_daily_bars(symbols, lookback_days)

    def get_options_chain(self, symbol: str) -> Optional[pd.DataFrame]:
        return self.yf.get_options_chain(symbol)

    def get_fundamentals(self, symbol: str) -> dict:
        return self.yf.get_fundamentals(symbol)

    def get_news(self, symbols: List[str], limit: int = 5) -> Dict[str, list]:
        if self.poly:
            news = self.poly.get_news(symbols, limit)
            if any(news.values()):
                return news
        return self.yf.get_news(symbols, limit)
