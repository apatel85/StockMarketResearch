"""Fundamental scoring from provider fundamentals + earnings-date catalyst flag."""
from __future__ import annotations

import datetime as dt
from typing import Optional


def score_fundamentals(f: dict) -> dict:
    """Map raw fundamentals to a 0-100 sub-score and human-readable notes.

    Neutral (50) when data is missing, so unknown names are not unduly penalised.
    """
    if not f:
        return {"score": 50.0, "notes": ["no fundamental data"], "earnings_soon": False}

    score = 50.0
    notes = []

    growth = f.get("earningsGrowth") or f.get("revenueGrowth")
    if growth is not None:
        if growth > 0.15:
            score += 12; notes.append(f"strong growth {growth:.0%}")
        elif growth < 0:
            score -= 12; notes.append(f"contracting growth {growth:.0%}")

    margin = f.get("profitMargins")
    if margin is not None:
        if margin > 0.20:
            score += 8; notes.append(f"high margin {margin:.0%}")
        elif margin < 0:
            score -= 10; notes.append("unprofitable")

    peg = f.get("pegRatio")
    if peg is not None and peg > 0:
        if peg < 1.0:
            score += 8; notes.append(f"cheap PEG {peg:.2f}")
        elif peg > 2.5:
            score -= 6; notes.append(f"rich PEG {peg:.2f}")

    rec = f.get("recommendationMean")  # 1=strong buy ... 5=sell
    if rec is not None:
        if rec <= 2.0:
            score += 8; notes.append("analysts bullish")
        elif rec >= 3.5:
            score -= 8; notes.append("analysts bearish")

    short = f.get("shortPercentOfFloat")
    if short is not None and short > 0.10:
        notes.append(f"high short float {short:.0%} (squeeze risk)")

    earnings_soon = _earnings_within(f.get("earningsTimestamp"), days=10)
    if earnings_soon:
        notes.append("earnings within ~10 days (catalyst)")

    return {
        "score": float(max(0.0, min(100.0, score))),
        "notes": notes,
        "earnings_soon": earnings_soon,
    }


def _earnings_within(ts: Optional[float], days: int = 10) -> bool:
    if not ts:
        return False
    try:
        when = dt.datetime.utcfromtimestamp(float(ts))
    except (ValueError, OSError, TypeError):
        return False
    delta = (when - dt.datetime.utcnow()).days
    return 0 <= delta <= days
