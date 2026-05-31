"""Render the interactive multi-tab HTML briefing from a payload dict via Jinja2."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

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


def render_html(payload: dict) -> str:
    """Render templates/report.html.j2 with the briefing payload."""
    return _env().get_template("report.html.j2").render(**payload)
