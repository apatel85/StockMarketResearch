"""yfinance provider — options chains, fundamentals, news, and a bars fallback.

Used in hybrid mode for the data the free Polygon tier lacks (options, fundamentals,
pre-market). yfinance is imported lazily so the package imports cleanly in environments
where it is not installed (e.g. offline unit tests).
"""
from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd


def _yf():
    import yfinance as yf  # lazy import
    return yf


class YFinanceProvider:
    name = "yfinance"

    def get_daily_bars(
        self, symbols: List[str], lookback_days: int = 260
    ) -> Dict[str, pd.DataFrame]:
        yf = _yf()
        period_days = int(lookback_days * 1.6) + 10
        out: Dict[str, pd.DataFrame] = {}
        data = yf.download(
            tickers=" ".join(symbols),
            period=f"{period_days}d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
        for sym in symbols:
            try:
                df = data[sym] if len(symbols) > 1 else data
                df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
                df = df.dropna(how="all")
                df.index = pd.to_datetime(df.index).normalize()
                if not df.empty:
                    out[sym] = df
            except (KeyError, TypeError):
                continue
        return out

    def get_options_chain(self, symbol: str) -> Optional[pd.DataFrame]:
        yf = _yf()
        tk = yf.Ticker(symbol)
        expiries = list(tk.options or [])
        frames = []
        for exp in expiries[:6]:
            try:
                chain = tk.option_chain(exp)
            except Exception:
                continue
            for side, frame in (("call", chain.calls), ("put", chain.puts)):
                f = frame.copy()
                f["type"] = side
                f["expiry"] = exp
                frames.append(f)
        if not frames:
            return None
        df = pd.concat(frames, ignore_index=True)
        keep = [
            "expiry", "type", "strike", "lastPrice", "volume",
            "openInterest", "impliedVolatility",
        ]
        for col in keep:
            if col not in df.columns:
                df[col] = pd.NA
        return df[keep]

    def get_fundamentals(self, symbol: str) -> dict:
        yf = _yf()
        try:
            info = yf.Ticker(symbol).info or {}
        except Exception:
            return {}
        keys = [
            "trailingPE", "forwardPE", "pegRatio", "priceToBook",
            "profitMargins", "grossMargins", "revenueGrowth", "earningsGrowth",
            "returnOnEquity", "recommendationMean", "targetMeanPrice",
            "earningsTimestamp", "marketCap", "beta", "shortPercentOfFloat",
        ]
        return {k: info.get(k) for k in keys if info.get(k) is not None}

    def get_news(self, symbols: List[str], limit: int = 5) -> Dict[str, list]:
        yf = _yf()
        out: Dict[str, list] = {}
        for sym in symbols:
            try:
                items = yf.Ticker(sym).news or []
            except Exception:
                items = []
            out[sym] = [
                {
                    "title": it.get("title"),
                    "publisher": it.get("publisher"),
                    "link": it.get("link"),
                    "published": it.get("providerPublishTime"),
                }
                for it in items[:limit]
            ]
        return out
