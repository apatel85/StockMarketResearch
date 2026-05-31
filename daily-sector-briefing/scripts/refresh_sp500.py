"""Refresh config/sp500.csv with the current S&P 500 constituents + GICS sector/industry.

Pulls the membership table from Wikipedia (no API key). Run occasionally to keep the
universe current:  python scripts/refresh_sp500.py

Requires network + `pandas`/`lxml` (pip install lxml). The committed sp500.csv is a seed
so the pipeline works out-of-the-box; this script keeps it fresh.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

WIKI = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
OUT = Path(__file__).resolve().parent.parent / "config" / "sp500.csv"


def main() -> int:
    tables = pd.read_html(WIKI)
    df = tables[0]
    df = df.rename(columns={
        "Symbol": "symbol", "Security": "name",
        "GICS Sector": "sector", "GICS Sub-Industry": "industry",
    })[["symbol", "name", "sector", "industry"]]
    df["symbol"] = df["symbol"].str.replace(".", "-", regex=False)  # Polygon/Yahoo style
    df.to_csv(OUT, index=False)
    print(f"Wrote {len(df)} constituents to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
