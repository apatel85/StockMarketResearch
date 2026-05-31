"""Sector & sub-sector performance, hot-sector detection, and rotation (RRG) quadrants."""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd


def sector_etf_performance(bars: Dict[str, pd.DataFrame], etf_map: Dict[str, str]) -> pd.DataFrame:
    """Daily & weekly % return for each sector ETF, plus a momentum reading."""
    rows = []
    for etf, sector in etf_map.items():
        df = bars.get(etf)
        if df is None or len(df) < 6:
            continue
        c = df["close"]
        rows.append(
            {
                "etf": etf,
                "sector": sector,
                "chg_1d": float(c.iloc[-1] / c.iloc[-2] - 1) * 100,
                "chg_5d": float(c.iloc[-1] / c.iloc[-6] - 1) * 100,
                "chg_20d": float(c.iloc[-1] / c.iloc[-21] - 1) * 100 if len(c) > 21 else float("nan"),
            }
        )
    return pd.DataFrame(rows).set_index("sector").sort_values("chg_1d", ascending=False)


def subsector_performance(change_tbl: pd.DataFrame, col: str = "chg_1d") -> pd.DataFrame:
    """Aggregate constituent returns by GICS industry (sub-sector) = median + breadth."""
    if change_tbl.empty or "industry" not in change_tbl:
        return pd.DataFrame()
    grp = change_tbl.dropna(subset=[col]).groupby(["sector", "industry"])
    agg = grp[col].agg(["median", "mean", "count"])
    breadth = grp[col].apply(lambda s: float((s > 0).mean() * 100)).rename("pct_up")
    out = agg.join(breadth).reset_index().sort_values("median", ascending=False)
    return out


def hot_sector(perf: pd.DataFrame, col: str = "chg_1d") -> dict:
    """Best and worst sector for the given horizon."""
    if perf.empty:
        return {}
    s = perf[col].dropna()
    if s.empty:
        return {}
    return {
        "hot": {"sector": s.idxmax(), "chg": float(s.max())},
        "cold": {"sector": s.idxmin(), "chg": float(s.min())},
    }


def rrg_quadrants(bars: Dict[str, pd.DataFrame], etf_map: Dict[str, str],
                  benchmark: str = "SPY", window: int = 12) -> pd.DataFrame:
    """Simplified Relative Rotation Graph: relative-strength ratio vs its momentum.

    quadrant: Leading (RS>0, mom>0), Weakening (RS>0, mom<0),
              Lagging (RS<0, mom<0), Improving (RS<0, mom>0).
    """
    bench = bars.get(benchmark)
    if bench is None or len(bench) < window + 5:
        return pd.DataFrame()
    bench_c = bench["close"]
    rows = []
    for etf, sector in etf_map.items():
        df = bars.get(etf)
        if df is None or len(df) < window + 5:
            continue
        ratio = (df["close"] / bench_c).dropna()
        if len(ratio) < window + 1:
            continue
        rs = float(ratio.iloc[-1] / ratio.iloc[-window - 1] - 1) * 100
        rs_prev = float(ratio.iloc[-2] / ratio.iloc[-window - 2] - 1) * 100
        mom = rs - rs_prev
        if rs >= 0 and mom >= 0:
            quad = "Leading"
        elif rs >= 0 and mom < 0:
            quad = "Weakening"
        elif rs < 0 and mom < 0:
            quad = "Lagging"
        else:
            quad = "Improving"
        rows.append({"sector": sector, "etf": etf, "rs": rs, "momentum": mom, "quadrant": quad})
    return pd.DataFrame(rows).set_index("sector")
