import numpy as np
import pandas as pd

from src import indicators as ind


def _df(closes):
    n = len(closes)
    idx = pd.bdate_range("2024-01-01", periods=n)
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99,
                         "close": c, "volume": np.arange(1, n + 1) * 1000.0})


def test_sma_basic():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    assert ind.sma(s, 2).iloc[-1] == 4.5


def test_rsi_all_gains_is_high():
    s = pd.Series(np.arange(1, 40), dtype=float)
    assert ind.rsi(s, 14).iloc[-1] > 90


def test_rsi_all_losses_is_low():
    s = pd.Series(np.arange(40, 1, -1), dtype=float)
    assert ind.rsi(s, 14).iloc[-1] < 10


def test_macd_columns():
    df = _df(np.linspace(10, 20, 60))
    m = ind.macd(df["close"])
    assert {"macd", "signal", "hist"} <= set(m.columns)


def test_atr_positive():
    df = _df(np.linspace(10, 20, 60))
    assert ind.atr(df, 14).iloc[-1] > 0


def test_relative_strength_sign():
    up = pd.Series(np.linspace(10, 30, 60), dtype=float)
    flat = pd.Series(np.full(60, 10.0))
    assert ind.relative_strength(up, flat, 20) > 0


def test_pivots_keys():
    df = _df(np.linspace(10, 20, 30))
    p = ind.pivots(df)
    assert {"pivot", "r1", "s1", "r2", "s2"} <= set(p)
    assert p["r1"] > p["pivot"] > p["s1"]


def test_compute_features_bundle():
    df = _df(np.linspace(50, 100, 220))
    feats = ind.compute_features(df, cfg={"sma_windows": [20, 50, 200]})
    assert feats["above_sma"][50] is True   # rising series
    assert "pivots" in feats and "rsi" in feats
