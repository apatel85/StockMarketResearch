"""Render the interactive multi-tab HTML briefing from a payload dict via Jinja2."""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .glossary import GLOSSARY
from .storage import _default_json

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["pct"] = lambda v: ("—" if v is None or v != v else f"{v:+.2f}%")
    env.filters["num"] = lambda v: ("—" if v is None or v != v else f"{v:,.2f}")
    env.filters["money"] = lambda v: ("—" if v is None or v != v else f"${v:,.0f}")
    return env


def _dumps(obj) -> str:
    # Escape '<' so embedded strings (e.g. news titles) can't break out of <script>.
    return json.dumps(obj, default=_default_json).replace("<", "\\u003c")


def render_error_html(exc: Exception, traceback_text: str, session: str,
                      provider: str, day: str) -> str:
    """A self-contained diagnostic page shown (and committed) when a run can't complete.

    Keeps the website 'working' and surfaces the exact failure for debugging.
    """
    import html as _html
    kind = type(exc).__name__
    is_stale = kind == "StaleDataError"
    headline = ("Data freshness guard tripped" if is_stale
                else "Briefing could not be generated")
    hint = (
        "The pipeline refused to publish because the latest market data was not for the "
        "expected trading day (e.g. a market holiday, or the data feed had not posted yet). "
        "This is intentional — it never shows stale data as if it were current."
        if is_stale else
        "The data feed or analysis step failed. The traceback below shows the cause. "
        "If it mentions rate limits or empty data, the provider (Polygon free tier / yfinance) "
        "likely throttled the request; re-running usually resolves it."
    )
    tb = _html.escape(traceback_text)
    msg = _html.escape(str(exc))
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Sector Briefing — diagnostic {day} {session.upper()}</title>
<style>body{{margin:0;background:#0d1117;color:#e6edf3;font:14px/1.6 -apple-system,Segoe UI,Roboto,Arial,sans-serif}}
.wrap{{max-width:860px;margin:0 auto;padding:32px 20px}}
.badge{{display:inline-block;background:rgba(248,81,73,.16);color:#f85149;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:700}}
h1{{font-size:20px;margin:14px 0 4px}} .mut{{color:#8b949e}}
.card{{background:#161b22;border:1px solid #21262d;border-radius:12px;padding:16px;margin:16px 0}}
code{{color:#f0883e}} pre{{background:#0b0f15;border:1px solid #21262d;border-radius:8px;padding:12px;overflow:auto;font-size:12px;color:#c9d1d9}}</style></head>
<body><div class="wrap">
<span class="badge">⚠ {kind}</span>
<h1>{headline}</h1>
<div class="mut">Session: {session.upper()} · expected trading day: {day} · provider: {provider}</div>
<div class="card"><b>What happened</b><p class="mut">{hint}</p>
<p>Message: <code>{msg}</code></p></div>
<div class="card"><b>Diagnostic detail</b><pre>{tb}</pre></div>
<p class="mut">This page is generated automatically so the dashboard is never blank. The next
scheduled run (5am / 5pm ET) will retry; you can also re-run the workflow manually.</p>
</div></body></html>"""


def render_html(payload: dict) -> str:
    """Render templates/report.html.j2 with the briefing payload.

    Data consumed by client-side JS (sector filter, options table, glossary) is
    injected as JSON strings so the template can embed it safely.
    """
    ctx = dict(payload)
    ctx["sector_chart_json"] = _dumps(payload.get("sector_chart_json", {}))
    ctx["movers_filter_json"] = _dumps(payload.get("movers_filter", {}))
    ctx["sector_cards_json"] = _dumps(payload.get("sector_cards", []))
    ctx["sector_etf_json"] = _dumps(payload.get("sector_etf", {}))
    ctx["subsector_hierarchy_json"] = _dumps(payload.get("subsector_hierarchy", {}))
    ctx["options_rows_json"] = _dumps(payload.get("options", {}).get("table", []))
    ctx["fundamentals_json"] = _dumps(payload.get("fundamentals_map", {}))
    ctx["glossary_json"] = _dumps(GLOSSARY)
    return _env().get_template("report.html.j2").render(**ctx)
