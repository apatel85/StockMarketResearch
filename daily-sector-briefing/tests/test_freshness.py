import datetime as dt

import pandas as pd
import pytest

from src import freshness
from src.calendar_utils import last_completed_trading_day


def _bars_ending(day, n=10):
    idx = pd.bdate_range(end=day, periods=n)
    return pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0,
                         "close": 1.0, "volume": 1.0}, index=idx)


def test_fresh_when_last_bar_is_expected_day():
    as_of = dt.datetime(2024, 6, 14, 18, 0)  # Fri after close
    expected = last_completed_trading_day(as_of)
    bars = {"SPY": _bars_ending(expected)}
    rep = freshness.check_freshness(bars, ["SPY"], expected, max_stale_days=0, as_of=as_of)
    assert rep.ok and "SPY" in rep.fresh


def test_stale_data_is_flagged_and_aborts():
    as_of = dt.datetime(2024, 6, 14, 18, 0)
    expected = last_completed_trading_day(as_of)
    stale_day = expected - pd.Timedelta(days=7)
    bars = {"SPY": _bars_ending(stale_day)}
    rep = freshness.check_freshness(bars, ["SPY"], expected, max_stale_days=0, as_of=as_of)
    assert not rep.ok and "SPY" in rep.stale
    with pytest.raises(freshness.StaleDataError):
        freshness.enforce(rep, abort_on_stale=True)


def test_missing_symbol_is_flagged():
    as_of = dt.datetime(2024, 6, 14, 18, 0)
    expected = last_completed_trading_day(as_of)
    rep = freshness.check_freshness({}, ["XLK"], expected, as_of=as_of)
    assert "XLK" in rep.missing and not rep.ok


def test_no_abort_when_disabled():
    as_of = dt.datetime(2024, 6, 14, 18, 0)
    expected = last_completed_trading_day(as_of)
    rep = freshness.check_freshness({}, ["XLK"], expected, as_of=as_of)
    freshness.enforce(rep, abort_on_stale=False)  # should not raise
