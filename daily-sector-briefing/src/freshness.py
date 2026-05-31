"""Data freshness guard.

Hard requirement: only the previous or current trading day's data is acceptable. This
module verifies that fetched daily bars end on the expected last completed trading day,
flags stale/missing series, and (per config) aborts the run rather than publishing stale
data.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from .calendar_utils import last_completed_trading_day


class StaleDataError(RuntimeError):
    """Raised when core data is older than the expected last trading day."""


@dataclass
class FreshnessReport:
    expected_day: pd.Timestamp
    fresh: List[str] = field(default_factory=list)
    stale: Dict[str, str] = field(default_factory=dict)   # symbol -> last date seen
    missing: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.stale and not self.missing

    def summary(self) -> str:
        return (
            f"expected={self.expected_day.date()} "
            f"fresh={len(self.fresh)} stale={len(self.stale)} missing={len(self.missing)}"
        )


def check_freshness(
    bars: Dict[str, pd.DataFrame],
    required: List[str],
    expected_day: Optional[pd.Timestamp] = None,
    max_stale_days: int = 0,
    as_of: Optional[dt.datetime] = None,
) -> FreshnessReport:
    """Validate that each required symbol's latest bar is recent enough.

    `max_stale_days` = 0 means the last bar must equal the expected trading day.
    """
    expected_day = (expected_day or last_completed_trading_day(as_of)).normalize()
    report = FreshnessReport(expected_day=expected_day)
    for sym in required:
        df = bars.get(sym)
        if df is None or df.empty:
            report.missing.append(sym)
            continue
        last = pd.Timestamp(df.index.max()).normalize()
        age = len(pd.bdate_range(last, expected_day)) - 1  # business-day gap
        if age > max_stale_days:
            report.stale[sym] = str(last.date())
        else:
            report.fresh.append(sym)
    return report


def enforce(report: FreshnessReport, abort_on_stale: bool = True) -> None:
    """Raise StaleDataError if the report is not OK and aborting is enabled."""
    if report.ok or not abort_on_stale:
        return
    raise StaleDataError(
        "Refusing to publish: data not current. "
        f"{report.summary()} | stale={report.stale} missing={report.missing[:10]}"
    )
