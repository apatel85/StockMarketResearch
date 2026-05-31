import numpy as np
import pandas as pd

from src import movers, sectors


def _bars(start, drift, n=12):
    idx = pd.bdate_range(end="2024-06-14", periods=n)
    c = pd.Series(start * (1 + drift) ** np.arange(n), index=idx)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99,
                         "close": c, "volume": np.full(n, 2_000_000.0)})


def _meta():
    return pd.DataFrame(
        {"name": ["A Co", "B Co", "C Co", "D Co"],
         "sector": ["Tech", "Tech", "Energy", "Energy"],
         "industry": ["Semis", "Software", "Oil", "Oil"]},
        index=["AAA", "BBB", "CCC", "DDD"],
    )


def test_change_table_filters_and_joins():
    bars = {"AAA": _bars(100, 0.02), "BBB": _bars(100, -0.01),
            "CCC": _bars(100, 0.01), "DDD": _bars(2, 0.0)}  # DDD below min_price
    tbl = movers.build_change_table(bars, _meta(), min_price=5.0, min_dollar_volume=1e6)
    assert "DDD" not in tbl.index
    assert tbl.loc["AAA", "sector"] == "Tech"
    assert tbl.loc["AAA", "chg_1d"] > 0


def test_top_movers_ordering():
    bars = {"AAA": _bars(100, 0.03), "BBB": _bars(100, -0.02), "CCC": _bars(100, 0.005)}
    tbl = movers.build_change_table(bars, _meta(), 5.0, 1e6)
    tm = movers.top_movers(tbl, "chg_1d", n=3)
    assert tm["winners"].index[0] == "AAA"
    assert tm["losers"].index[0] == "BBB"


def test_subsector_aggregation():
    bars = {"AAA": _bars(100, 0.03), "BBB": _bars(100, 0.01),
            "CCC": _bars(100, -0.02), "DDD": _bars(100, -0.01)}
    tbl = movers.build_change_table(bars, _meta(), 5.0, 1e6)
    sub = sectors.subsector_performance(tbl, "chg_1d")
    assert {"sector", "industry", "median", "pct_up", "count"} <= set(sub.columns)


def test_hot_sector():
    perf = pd.DataFrame({"chg_1d": [2.0, -1.5, 0.5]},
                        index=["Tech", "Energy", "Health"])
    hs = sectors.hot_sector(perf, "chg_1d")
    assert hs["hot"]["sector"] == "Tech" and hs["cold"]["sector"] == "Energy"
