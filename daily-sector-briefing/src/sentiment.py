"""Lightweight sentiment: headline keyword tone + options P/C + VIX regime.

Deliberately rule-based (no external model) so it runs offline and deterministically.
Returns a 0-100 score and notes that the report can display.
"""
from __future__ import annotations

from typing import List

_POSITIVE = {
    "beats", "beat", "surge", "soar", "record", "upgrade", "raises", "raised",
    "outperform", "buyback", "approval", "wins", "strong", "growth", "tops",
    "bullish", "rally", "jumps", "expands", "partnership", "guidance raised",
}
_NEGATIVE = {
    "miss", "misses", "plunge", "falls", "downgrade", "cuts", "cut", "lawsuit",
    "probe", "recall", "warning", "weak", "slump", "bearish", "halts", "delays",
    "investigation", "layoffs", "guidance cut", "bankruptcy", "fraud",
}


def headline_tone(headlines: List[dict]) -> dict:
    pos = neg = 0
    hits = []
    for item in headlines or []:
        title = (item.get("title") or "").lower()
        p = sum(1 for w in _POSITIVE if w in title)
        n = sum(1 for w in _NEGATIVE if w in title)
        pos += p
        neg += n
        if p or n:
            hits.append({"title": item.get("title"), "tone": "+" * p + "-" * n})
    total = pos + neg
    score = 50.0 if total == 0 else 50.0 + (pos - neg) / total * 50.0
    return {"score": float(max(0.0, min(100.0, score))), "pos": pos, "neg": neg, "hits": hits[:3]}


def vix_regime(vix_last: float) -> dict:
    if vix_last is None or vix_last != vix_last:  # NaN
        return {"regime": "unknown", "score": 50.0}
    if vix_last < 15:
        return {"regime": "calm", "score": 60.0}
    if vix_last < 20:
        return {"regime": "normal", "score": 52.0}
    if vix_last < 28:
        return {"regime": "elevated", "score": 42.0}
    return {"regime": "stress", "score": 30.0}


def score_sentiment(headlines: List[dict], pc_ratio_vol: float, vix_last: float) -> dict:
    """Blend headline tone (60%), options P/C (25%), VIX regime (15%)."""
    tone = headline_tone(headlines)
    vix = vix_regime(vix_last)

    pc_score = 50.0
    if pc_ratio_vol == pc_ratio_vol:  # not NaN
        # low P/C (call-heavy) -> bullish; high P/C -> bearish
        pc_score = max(0.0, min(100.0, 50.0 + (1.0 - pc_ratio_vol) * 40.0))

    blended = 0.60 * tone["score"] + 0.25 * pc_score + 0.15 * vix["score"]
    return {
        "score": float(max(0.0, min(100.0, blended))),
        "tone": tone,
        "pc_score": pc_score,
        "vix": vix,
    }
