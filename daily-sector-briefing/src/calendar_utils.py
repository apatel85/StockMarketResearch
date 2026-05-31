"""NYSE trading-day / holiday helpers.

Uses pandas_market_calendars when available; otherwise falls back to a weekday-only
approximation (still excludes weekends, but not holidays). The fallback keeps the
package usable in minimal/offline environments while logging a warning.
"""
from __future__ import annotations

import datetime as dt
from typing import List, Optional

import pandas as pd

_FALLBACK_WARNED = False


def _calendar():
    try:
        import pandas_market_calendars as mcal
        return mcal.get_calendar("XNYS")
    except Exception:
        return None


def trading_days(start: dt.date, end: dt.date) -> List[pd.Timestamp]:
    """Sorted list of NYSE trading days in [start, end]."""
    cal = _calendar()
    if cal is not None:
        sched = cal.schedule(start_date=str(start), end_date=str(end))
        return [pd.Timestamp(d).normalize() for d in sched.index]
    # Fallback: business days (Mon-Fri), no holiday awareness.
    global _FALLBACK_WARNED
    if not _FALLBACK_WARNED:
        print("[calendar] pandas_market_calendars unavailable; using weekday fallback")
        _FALLBACK_WARNED = True
    rng = pd.bdate_range(start=start, end=end)
    return [pd.Timestamp(d).normalize() for d in rng]


def last_completed_trading_day(as_of: Optional[dt.datetime] = None) -> pd.Timestamp:
    """The most recent trading day whose session has fully closed.

    A session is considered complete after 16:00 America/New_York. If `as_of` is on a
    trading day before the close, the prior trading day is returned.
    """
    as_of = as_of or _now_et()
    today = as_of.date()
    days = trading_days(today - dt.timedelta(days=12), today)
    if not days:
        return pd.Timestamp(today)
    is_trading_today = days[-1].date() == today
    after_close = as_of.hour >= 16
    if is_trading_today and not after_close:
        return days[-2] if len(days) > 1 else days[-1]
    return days[-1]


def is_trading_day(day: dt.date) -> bool:
    return any(d.date() == day for d in trading_days(day, day))


def previous_trading_day(day: pd.Timestamp) -> pd.Timestamp:
    days = trading_days((day - dt.timedelta(days=12)).date(), (day - dt.timedelta(days=1)).date())
    return days[-1] if days else day - pd.Timedelta(days=1)


def _now_et() -> dt.datetime:
    """Current time in US/Eastern (DST-aware)."""
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return dt.datetime.utcnow() - dt.timedelta(hours=5)
