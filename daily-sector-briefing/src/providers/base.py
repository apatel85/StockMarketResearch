"""Data provider interface.

All providers return plain pandas objects so the analysis layer is provider-agnostic.
Daily bars are returned as a dict keyed by symbol, each a DataFrame indexed by date
with columns: open, high, low, close, volume.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import pandas as pd


class DataProvider(ABC):
    """Abstract market-data source."""

    name: str = "base"

    @abstractmethod
    def get_daily_bars(
        self, symbols: List[str], lookback_days: int = 260
    ) -> Dict[str, pd.DataFrame]:
        """Return {symbol: DataFrame[open,high,low,close,volume]} indexed by date."""

    def get_grouped_daily(self, date: str) -> Optional[pd.DataFrame]:
        """Whole-market OHLCV for a single date (Polygon only). None if unsupported.

        Returns a DataFrame indexed by symbol with columns open/high/low/close/volume.
        """
        return None

    def get_options_chain(self, symbol: str) -> Optional[pd.DataFrame]:
        """Return an options snapshot DataFrame or None if unsupported.

        Columns (when available): expiry, type ('call'/'put'), strike, lastPrice,
        volume, openInterest, impliedVolatility.
        """
        return None

    def get_fundamentals(self, symbol: str) -> dict:
        """Return a dict of fundamental fields (may be empty)."""
        return {}

    def get_news(self, symbols: List[str], limit: int = 5) -> Dict[str, list]:
        """Return {symbol: [ {title, publisher, link, published} ]}."""
        return {}
