"""Archive briefing JSON + HTML and enforce 30-day retention."""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"

_STAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2})-(am|pm)")


def _default_json(o):
    import numpy as np
    import pandas as pd
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    if isinstance(o, (pd.Timestamp, dt.datetime, dt.date)):
        return str(o)
    return str(o)


def save_briefing(payload: dict, html: str, day: str, session: str,
                  retention_days: int = 30) -> dict:
    """Write data/<day>-<session>.json and reports/<day>-<session>.html (+ latest.html)."""
    DATA_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)
    stamp = f"{day}-{session}"

    json_path = DATA_DIR / f"{stamp}.json"
    json_path.write_text(json.dumps(payload, indent=2, default=_default_json))

    html_path = REPORTS_DIR / f"{stamp}.html"
    html_path.write_text(html)
    (REPORTS_DIR / "latest.html").write_text(html)
    # index.html so the GitHub Pages root URL serves the latest briefing directly.
    (REPORTS_DIR / "index.html").write_text(html)

    pruned = prune(retention_days)
    return {"json": str(json_path), "html": str(html_path), "pruned": pruned}


def prune(retention_days: int = 30) -> List[str]:
    """Delete archived files older than retention_days. Returns removed paths."""
    cutoff = dt.date.today() - dt.timedelta(days=retention_days)
    removed: List[str] = []
    for folder, suffix in ((DATA_DIR, ".json"), (REPORTS_DIR, ".html")):
        if not folder.exists():
            continue
        for f in folder.glob(f"*{suffix}"):
            m = _STAMP_RE.search(f.name)
            if not m:
                continue
            file_day = dt.date.fromisoformat(m.group(1))
            if file_day < cutoff:
                f.unlink()
                removed.append(str(f))
    return removed


def load_archive(retention_days: int = 30) -> List[dict]:
    """Load recent briefing JSON payloads (for the accuracy backtest)."""
    out = []
    if not DATA_DIR.exists():
        return out
    for f in sorted(DATA_DIR.glob("*.json")):
        try:
            out.append(json.loads(f.read_text()))
        except json.JSONDecodeError:
            continue
    return out
