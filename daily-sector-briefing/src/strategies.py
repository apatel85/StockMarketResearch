"""Trade-plan builder: entry/stop/target levels + top-3 option strategies by IV regime.

Levels are derived from pivots and ATR so they are concrete and risk-defined. Option
strategy selection keys off direction (long/short) and IV rank (cheap vs rich premium),
matching how a discretionary options trader picks structures.
"""
from __future__ import annotations

from typing import List, Optional


def trade_levels(feats: dict, bias: str) -> dict:
    """Entry / stop / target from pivots + ATR. R-multiple target of ~2R."""
    last = feats.get("last")
    atr = feats.get("atr")
    piv = feats.get("pivots", {})
    if last is None:
        return {}
    atr = atr if (atr and atr == atr) else last * 0.02

    if bias == "long":
        entry = piv.get("pivot", last)
        stop = min(piv.get("s1", last - atr), last - 1.5 * atr)
        risk = max(entry - stop, atr)
        target = entry + 2.0 * risk
    else:
        entry = piv.get("pivot", last)
        stop = max(piv.get("r1", last + atr), last + 1.5 * atr)
        risk = max(stop - entry, atr)
        target = entry - 2.0 * risk

    return {
        "entry": round(float(entry), 2),
        "stop": round(float(stop), 2),
        "target": round(float(target), 2),
        "risk_per_share": round(float(risk), 2),
        "rr": 2.0,
    }


def option_strategies(bias: str, iv_rank: Optional[float], expected_move: Optional[float],
                      horizon: str = "swing") -> List[dict]:
    """Return top-3 option strategies tailored to direction and IV regime."""
    rich_iv = iv_rank is not None and iv_rank == iv_rank and iv_rank >= 50
    cheap_iv = iv_rank is not None and iv_rank == iv_rank and iv_rank < 50
    em = f" (expected move ~{expected_move:.1f}%)" if expected_move and expected_move == expected_move else ""

    if bias == "long":
        if rich_iv:
            ideas = [
                ("Bull put credit spread", "Sell OTM put, buy lower put — collect rich premium, defined risk."),
                ("Cash-secured put", "Sell put at support to get paid while IV is high; assignment = long entry."),
                ("Call debit spread", "Buy ATM / sell OTM call to cut the inflated long-premium cost."),
            ]
        else:
            ideas = [
                ("Long call / call debit spread", "Cheap IV favours owning premium for upside convexity."),
                ("Call calendar", "Sell front, buy back-month call to exploit low front IV into a catalyst."),
                ("Stock + protective put", "Own shares, hedge with a cheap put for swing holds."),
            ]
    else:  # short
        if rich_iv:
            ideas = [
                ("Bear call credit spread", "Sell OTM call, buy higher call — collect rich premium, defined risk."),
                ("Put debit spread", "Buy ATM / sell OTM put to reduce inflated long-put cost."),
                ("Covered-call overwrite", "On longs you want to trim, sell calls into high IV."),
            ]
        else:
            ideas = [
                ("Long put / put debit spread", "Cheap IV favours owning downside premium."),
                ("Put calendar", "Sell front, buy back-month put when front IV is low."),
                ("Bear put spread", "Defined-risk directional short with limited cost."),
            ]
    tag = "0-2 DTE / weeklies" if horizon == "day" else "2-6 week expiries"
    return [{"name": n, "rationale": r + em, "tenor": tag} for n, r in ideas]


def build_plan(feats: dict, scored: dict, flow: dict, iv_rank: Optional[float],
               horizon: str = "swing") -> dict:
    bias = scored["bias"]
    return {
        "levels": trade_levels(feats, bias),
        "option_strategies": option_strategies(
            bias, iv_rank, (flow or {}).get("expected_move_pct"), horizon
        ),
    }
