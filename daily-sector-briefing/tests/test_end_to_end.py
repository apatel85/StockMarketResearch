"""End-to-end smoke test using the offline DemoProvider — no network required."""
from pathlib import Path

import yaml

from src.demo_data import DemoProvider
from src.run_briefing import build_payload
from src.report import render_html, render_error_html
from src.freshness import StaleDataError

ROOT = Path(__file__).resolve().parent.parent


def _settings():
    with open(ROOT / "config" / "settings.yaml") as f:
        return yaml.safe_load(f)


def test_build_payload_and_render():
    provider = DemoProvider()
    payload = build_payload(provider, _settings(), session="pm")

    # Core sections present
    for key in ("market_pulse", "sectors", "winners", "losers", "ideas",
                "options", "futures", "watchlist", "accuracy"):
        assert key in payload

    assert payload["freshness"]["ok"] is True
    assert len(payload["winners"]) > 0
    assert len(payload["ideas"]) > 0
    # Every idea has a directional bias, confidence and a plan
    for idea in payload["ideas"]:
        assert idea["bias"] in ("long", "short")
        assert 0 <= idea["confidence"] <= 100
        assert len(idea["option_strategies"]) == 3

    html = render_html(payload)
    assert "Daily Sector Briefing" in html
    assert "Trade Setups" in html
    assert len(html) > 5000


def test_error_page_renders():
    html = render_error_html(StaleDataError("data not current"), "Traceback...\nStaleDataError",
                             "pm", "hybrid", "2026-05-29")
    assert "freshness guard" in html.lower()
    assert "data not current" in html
    generic = render_error_html(RuntimeError("boom"), "tb", "am", "hybrid", "2026-05-29")
    assert "could not be generated" in generic.lower() and "boom" in generic
