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
