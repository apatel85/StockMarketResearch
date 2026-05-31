"""Winners & losers ranking (day and week), overall and per sector."""
from __future__ import annotations

from typing import Dict, List

import pandas as pd


def _return_pct(df: pd.DataFrame, periods: int) -> float:
    if df is None or len(df) <= periods:
        return float("nan")
    return float(df["close"].iloc[-1] / df["close"].iloc[-1 - periods] - 1) * 100


def build_change_table(
    bars: Dict[str, pd.DataFrame],
    meta: pd.DataFrame,
    min_price: float = 5.0,
    min_dollar_volume: float = 5e6,
) -> pd.DataFrame:
    """Per-symbol daily & weekly % change plus liquidity, joined to sector metadata.

    `meta` is the sp500 table indexed by symbol with columns name/sector/industry.
    """
    rows = []
    for sym, df in bars.items():
        if df is None or df.empty:
            continue
        last_close = float(df["close"].iloc[-1])
        last_vol = float(df["volume"].iloc[-1]) if "volume" in df else 0.0
        if last_close < min_price or last_close * last_vol < min_dollar_volume:
            continue
        rows.append(
            {
                "symbol": sym,
                "close": last_close,
                "chg_1d": _return_pct(df, 1),
                "chg_5d": _return_pct(df, 5),
                "dollar_vol": last_close * last_vol,
            }
        )
    tbl = pd.DataFrame(rows).set_index("symbol")
    if tbl.empty:
        return tbl
    return tbl.join(meta[["name", "sector", "industry"]], how="left")


def top_movers(tbl: pd.DataFrame, col: str = "chg_1d", n: int = 10) -> Dict[str, pd.DataFrame]:
    """Return {'winners': ..., 'losers': ...} sorted by `col`."""
    clean = tbl.dropna(subset=[col])
    return {
        "winners": clean.sort_values(col, ascending=False).head(n),
        "losers": clean.sort_values(col, ascending=True).head(n),
    }


def movers_by_sector(tbl: pd.DataFrame, col: str = "chg_1d", n: int = 5) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for sector, grp in tbl.dropna(subset=[col]).groupby("sector"):
        out[sector] = {
            "winners": grp.sort_values(col, ascending=False).head(n),
            "losers": grp.sort_values(col, ascending=True).head(n),
        }
    return out
