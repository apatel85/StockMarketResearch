"""Accuracy tracker: did prior briefing ideas move the predicted way the next day?

Reads the 30-day JSON archive, matches each idea to the realized next-session return,
and reports a hit-rate by bias and confidence bucket. Over time this validates (and can
auto-tune) the scoring weights.
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd


def evaluate(archive: List[dict], realized_returns: Dict[str, float]) -> dict:
    """Score the most recent archived ideas against realized next-day returns.

    `realized_returns` maps symbol -> next-session % change (provided by the caller from
    fresh bars). An idea is a 'hit' if a long rose / a short fell.
    """
    rows = []
    for payload in archive:
        for idea in payload.get("ideas", []):
            sym = idea.get("symbol")
            if sym not in realized_returns:
                continue
            ret = realized_returns[sym]
            bias = idea.get("bias")
            hit = (bias == "long" and ret > 0) or (bias == "short" and ret < 0)
            rows.append(
                {
                    "date": payload.get("as_of"),
                    "session": payload.get("session"),
                    "symbol": sym,
                    "bias": bias,
                    "confidence": idea.get("confidence"),
                    "realized_pct": ret,
                    "hit": bool(hit),
                }
            )
    if not rows:
        return {"available": False, "n": 0}

    df = pd.DataFrame(rows)
    by_conf = (
        df.assign(bucket=pd.cut(df["confidence"], [0, 40, 60, 80, 100],
                                labels=["<40", "40-60", "60-80", "80+"]))
        .groupby("bucket", observed=True)["hit"].agg(["mean", "count"])
    )
    return {
        "available": True,
        "n": int(len(df)),
        "hit_rate": float(df["hit"].mean()),
        "hit_rate_long": float(df.loc[df.bias == "long", "hit"].mean()) if (df.bias == "long").any() else None,
        "hit_rate_short": float(df.loc[df.bias == "short", "hit"].mean()) if (df.bias == "short").any() else None,
        "avg_realized": float(df["realized_pct"].mean()),
        "by_confidence": {str(k): {"hit_rate": float(v["mean"]), "n": int(v["count"])}
                          for k, v in by_conf.iterrows()},
        "rows": rows[-50:],
    }
