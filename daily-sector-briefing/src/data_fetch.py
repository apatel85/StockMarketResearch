"""Fetch orchestration: build per-symbol daily bars efficiently.

Strategy that respects the free Polygon tier:
- Universe-wide change table uses Polygon `grouped_daily` over a short window (~12 trading
  days) — a handful of calls cover the whole S&P 500 for 1D/1W returns & sub-sector medians.
- A focused shortlist (movers + watchlist + sector leaders) gets full history for deep
  indicators (200DMA, ATR, RSI…).
- Macro/index/futures symbols (not on the free stocks tier) fall back to yfinance via hybrid.
"""
from __future__ import annotations

import datetime as dt
from typing import Dict, List

import pandas as pd

from .calendar_utils import last_completed_trading_day, trading_days


def fetch_grouped_window(provider, symbols: List[str], window_days: int,
                         as_of: dt.datetime | None = None) -> Dict[str, pd.DataFrame]:
    """Build {symbol: bars} from grouped-daily over the last `window_days` trading days.

    Returns {} if the provider does not support grouped daily (caller falls back).
    """
    if not hasattr(provider, "get_grouped_daily"):
        return {}
    end = last_completed_trading_day(as_of)
    days = [d for d in trading_days((end - dt.timedelta(days=window_days * 2 + 8)).date(),
                                    end.date())][-window_days:]
    symset = set(symbols)
    per_sym: Dict[str, list] = {}
    for d in days:
        g = None
        try:
            g = provider.get_grouped_daily(str(d.date()))
        except Exception:
            g = None
        if g is None:
            return {}  # signal fallback
        for sym in symset.intersection(g.index):
            row = g.loc[sym]
            per_sym.setdefault(sym, []).append(
                {"date": d, "open": row["open"], "high": row["high"],
                 "low": row["low"], "close": row["close"], "volume": row["volume"]}
            )
    return {s: pd.DataFrame(rows).set_index("date") for s, rows in per_sym.items() if rows}


def fetch_universe(provider, meta: pd.DataFrame, settings: dict,
                   as_of: dt.datetime | None = None) -> dict:
    """Return dicts of bars needed by the analysis layer."""
    symbols = list(meta.index)
    macro = settings["universe"]["macro"]
    macro_syms = (macro["indices"] + macro["futures"] + macro["volatility"]
                  + macro["rates"] + macro["intermarket"])
    etfs = list(settings["universe"]["sector_etfs"].keys())
    bench = settings["universe"]["benchmark"]

    # 1) Universe change table via grouped window (cheap), else per-symbol fallback.
    change_bars = fetch_grouped_window(provider, symbols, window_days=12, as_of=as_of)
    if not change_bars:
        change_bars = provider.get_daily_bars(symbols, lookback_days=15)

    # 2) Macro + ETFs + benchmark need full history -> per symbol (hybrid routes correctly).
    context_bars = provider.get_daily_bars(macro_syms + etfs + [bench], lookback_days=260)

    return {
        "change_bars": change_bars,
        "context_bars": context_bars,
        "macro_syms": macro_syms,
        "etfs": etfs,
        "benchmark": bench,
    }


def fetch_shortlist_history(provider, symbols: List[str]) -> Dict[str, pd.DataFrame]:
    """Full ~1y history for the idea shortlist (deep indicators)."""
    symbols = list(dict.fromkeys(symbols))
    if not symbols:
        return {}
    return provider.get_daily_bars(symbols, lookback_days=260)
