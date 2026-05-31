"""Polygon.io provider (free 'Stocks Basic' tier friendly).

Primary EOD equity source. The key feature is `get_grouped_daily`, which returns the
entire US market's daily OHLCV in ONE request — ideal for ranking S&P 500 movers and
aggregating sectors without hitting the 5-calls/min free-tier limit.

The free tier is end-of-day only and does NOT include options; options/fundamentals are
served by the yfinance provider in hybrid mode. Upgrading to a paid Options plan later
only requires implementing get_options_chain here.
"""
from __future__ import annotations

import os
import time
from typing import Dict, List, Optional

import pandas as pd
import requests

BASE = "https://api.polygon.io"


class PolygonProvider:
    name = "polygon"

    def __init__(self, api_key: Optional[str] = None, max_per_min: int = 5):
        self.api_key = api_key or os.environ.get("POLYGON_API_KEY", "")
        self.max_per_min = max_per_min
        self._min_interval = 60.0 / max_per_min if max_per_min else 0.0
        self._last_call = 0.0
        self.session = requests.Session()

    # -- internal -----------------------------------------------------------
    def _throttle(self) -> None:
        if self._min_interval <= 0:
            return
        wait = self._min_interval - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.time()

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        if not self.api_key:
            raise RuntimeError("POLYGON_API_KEY is not set")
        params = dict(params or {})
        params["apiKey"] = self.api_key
        self._throttle()
        resp = self.session.get(f"{BASE}{path}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    # -- interface ----------------------------------------------------------
    def get_grouped_daily(self, date: str) -> Optional[pd.DataFrame]:
        """All tickers' OHLCV for `date` (YYYY-MM-DD) in a single call."""
        data = self._get(
            f"/v2/aggs/grouped/locale/us/market/stocks/{date}",
            {"adjusted": "true"},
        )
        results = data.get("results") or []
        if not results:
            return None
        rows = {
            r["T"]: {
                "open": r.get("o"),
                "high": r.get("h"),
                "low": r.get("l"),
                "close": r.get("c"),
                "volume": r.get("v"),
            }
            for r in results
        }
        df = pd.DataFrame.from_dict(rows, orient="index")
        df.index.name = "symbol"
        return df

    def get_daily_bars(
        self, symbols: List[str], lookback_days: int = 260
    ) -> Dict[str, pd.DataFrame]:
        """Per-symbol daily aggregates. Rate-limited; use sparingly on the free tier
        (prefer get_grouped_daily for breadth)."""
        end = pd.Timestamp.utcnow().normalize()
        start = end - pd.Timedelta(days=int(lookback_days * 1.6) + 5)
        out: Dict[str, pd.DataFrame] = {}
        for sym in symbols:
            try:
                data = self._get(
                    f"/v2/aggs/ticker/{sym}/range/1/day/"
                    f"{start.date()}/{end.date()}",
                    {"adjusted": "true", "sort": "asc", "limit": 50000},
                )
            except requests.HTTPError:
                continue
            results = data.get("results") or []
            if not results:
                continue
            df = pd.DataFrame(results)
            df["date"] = pd.to_datetime(df["t"], unit="ms").dt.normalize()
            df = df.rename(
                columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
            ).set_index("date")[["open", "high", "low", "close", "volume"]]
            out[sym] = df
        return out

    def get_news(self, symbols: List[str], limit: int = 5) -> Dict[str, list]:
        out: Dict[str, list] = {}
        for sym in symbols:
            try:
                data = self._get(
                    "/v2/reference/news", {"ticker": sym, "limit": limit}
                )
            except requests.HTTPError:
                continue
            out[sym] = [
                {
                    "title": a.get("title"),
                    "publisher": (a.get("publisher") or {}).get("name"),
                    "link": a.get("article_url"),
                    "published": a.get("published_utc"),
                }
                for a in (data.get("results") or [])
            ]
        return out
