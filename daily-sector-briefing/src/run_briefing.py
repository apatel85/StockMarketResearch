"""Orchestrator: fetch -> validate freshness -> analyze -> score -> render -> archive.

Usage:
    python -m src.run_briefing --session pm
    python -m src.run_briefing --session am --demo      # offline synthetic data
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
from typing import Dict, List

import pandas as pd
import yaml

from . import movers, sectors, options_flow, fundamentals as fund, sentiment as sent
from . import scoring, strategies, futures_levels, backtest, storage
from .calendar_utils import _now_et, last_completed_trading_day
from .data_fetch import fetch_universe, fetch_shortlist_history, fetch_fundamentals_map
from .freshness import check_freshness, enforce
from .indicators import compute_features
from .report import render_html

ROOT = Path(__file__).resolve().parent.parent
DISCLAIMER = (
    "For research and educational purposes only. Not investment advice. Options and futures "
    "trading involves substantial risk of loss. Data may be delayed or incomplete; verify before "
    "trading. Past performance and model signals do not guarantee future results."
)


# --------------------------------------------------------------------------- helpers
def load_settings(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def _q(bars: Dict[str, pd.DataFrame], sym: str) -> dict:
    df = bars.get(sym)
    if df is None or len(df) < 2:
        return {"symbol": sym, "last": float("nan"), "chg_1d": float("nan")}
    c = df["close"]
    return {"symbol": sym, "last": float(c.iloc[-1]),
            "chg_1d": float(c.iloc[-1] / c.iloc[-2] - 1) * 100}


def _catalyst_from_news(news_items: list) -> str:
    if not news_items:
        return ""
    return (news_items[0] or {}).get("title", "") or ""


def _build_movers_filter(change_tbl, news: dict, n: int) -> dict:
    """Top-N winners/losers (day & week) for 'Overall' and per sector, for the
    client-side sector filter on the Winners/Losers tab."""
    def recs(df):
        out = df.reset_index().to_dict("records")
        for r in out:
            r["catalyst"] = _catalyst_from_news(news.get(r["symbol"], []))
        return out

    def block(tbl):
        day = movers.top_movers(tbl, "chg_1d", n)
        wk = movers.top_movers(tbl, "chg_5d", n)
        return {
            "day": {"winners": recs(day["winners"]), "losers": recs(day["losers"])},
            "week": {"winners": recs(wk["winners"]), "losers": recs(wk["losers"])},
        }

    result = {"Overall": block(change_tbl)}
    if not change_tbl.empty:
        for sector, grp in change_tbl.dropna(subset=["chg_1d"]).groupby("sector"):
            result[str(sector)] = block(grp)
            # Sub-sector (GICS industry) drill-down keys: "Sector|||Industry"
            for industry, sub in grp.groupby("industry"):
                result[f"{sector}|||{industry}"] = block(sub)
    return result


def _subsector_hierarchy(change_tbl) -> dict:
    """{sector: [{industry, median, count}]} for the second-level filter chips."""
    if change_tbl.empty:
        return {}
    hier: dict = {}
    grp = change_tbl.dropna(subset=["chg_1d"]).groupby(["sector", "industry"])["chg_1d"]
    agg = grp.agg(["median", "count"]).reset_index().sort_values("median", ascending=False)
    for r in agg.to_dict("records"):
        hier.setdefault(str(r["sector"]), []).append(
            {"industry": str(r["industry"]), "median": float(r["median"]), "count": int(r["count"])}
        )
    return hier


# --------------------------------------------------------------------------- main build
def build_payload(provider, settings: dict, session: str,
                  as_of: dt.datetime | None = None) -> dict:
    meta = pd.read_csv(settings["universe"]["sp500_csv"]).set_index("symbol")
    expected_day = last_completed_trading_day(as_of)

    fetched = fetch_universe(provider, meta, settings, as_of)
    change_bars = fetched["change_bars"]
    context_bars = fetched["context_bars"]
    etfs, bench = fetched["etfs"], fetched["benchmark"]

    # ---- Freshness guard (hard requirement) -------------------------------
    required = [bench] + etfs
    fr = check_freshness(
        {**context_bars, **change_bars}, required, expected_day,
        max_stale_days=settings["freshness"]["max_stale_days"], as_of=as_of,
    )
    enforce(fr, abort_on_stale=settings["freshness"]["abort_on_stale"])

    # ---- Movers + sectors -------------------------------------------------
    mcfg = settings["movers"]
    change_tbl = movers.build_change_table(
        change_bars, meta, mcfg["min_price"], float(mcfg["min_dollar_volume"]))
    day = movers.top_movers(change_tbl, "chg_1d", mcfg["top_n"])
    week = movers.top_movers(change_tbl, "chg_5d", mcfg["top_n"])

    etf_perf = sectors.sector_etf_performance(context_bars, settings["universe"]["sector_etfs"])
    rrg = sectors.rrg_quadrants(context_bars, settings["universe"]["sector_etfs"], bench)
    subsec = sectors.subsector_performance(change_tbl, "chg_1d")

    # ---- Catalyst news for movers ----------------------------------------
    mover_syms = list(day["winners"].index) + list(day["losers"].index)
    news = provider.get_news(mover_syms, limit=3) if mover_syms else {}

    def _movers_records(df):
        recs = df.reset_index().to_dict("records")
        for r in recs:
            r["catalyst"] = _catalyst_from_news(news.get(r["symbol"], []))
        return recs

    # ---- Idea shortlist: day & week movers -------------------------------
    shortlist = list(dict.fromkeys(mover_syms + list(week["winners"].index)
                                   + list(week["losers"].index)))[:30]
    idea_bars = fetch_shortlist_history(provider, shortlist)

    vix_q = _q(context_bars, "^VIX")
    vix_last = vix_q["last"]
    bench_close = context_bars.get(bench, pd.DataFrame()).get("close")

    ideas, options_rows = [], []
    weights = settings["scoring"]["weights"]
    for sym in shortlist:
        df = idea_bars.get(sym)
        if df is None or len(df) < 30:
            continue
        feats = compute_features(df, bench_close, settings["indicators"])
        chain = None
        try:
            chain = provider.get_options_chain(sym)
        except Exception:
            chain = None
        flow = options_flow.analyze_chain(
            chain, feats["last"],
            settings["options"]["unusual_vol_oi_ratio"],
            settings["options"]["near_expiries"])
        row = meta.loc[sym] if sym in meta.index else {}
        sec = row.get("sector", "") if hasattr(row, "get") else ""
        ind = row.get("industry", "") if hasattr(row, "get") else ""
        if flow.get("available"):
            options_rows.append({"symbol": sym, "sector": sec, "industry": ind,
                                 **{k: flow.get(k) for k in
                                 ("pc_ratio_vol", "atm_iv", "expected_move_pct",
                                  "bias", "unusual_count")}})
        fundamentals = fund.score_fundamentals(_safe(provider.get_fundamentals, sym))
        headlines = _safe(provider.get_news, [sym], 4).get(sym, [])
        sentiment = sent.score_sentiment(headlines, flow.get("pc_ratio_vol", float("nan")), vix_last)
        scored = scoring.composite(feats, fundamentals, sentiment, flow, weights)
        plan = strategies.build_plan(feats, scored, flow, None,
                                     "day" if session == "am" else "swing")
        ideas.append({
            "symbol": sym,
            "name": row.get("name", sym) if hasattr(row, "get") else sym,
            "sector": sec,
            **scored, **plan,
        })

    ideas.sort(key=lambda x: x["confidence"], reverse=True)
    ideas = ideas[: settings["scoring"]["max_ideas"]]
    lt, st = settings["scoring"]["long_threshold"], settings["scoring"]["short_threshold"]
    longs = [i for i in ideas if i["bias"] == "long" and i["confidence"] >= lt]
    shorts = [i for i in ideas if i["bias"] == "short" and i["confidence"] >= st]

    # ---- Accuracy backtest vs realized 1D returns ------------------------
    realized = change_tbl["chg_1d"].dropna().to_dict()
    accuracy = backtest.evaluate(storage.load_archive(settings["retention_days"]), realized)

    # ---- Panels -----------------------------------------------------------
    spx_q = _q(context_bars, "^GSPC")
    futures = futures_levels.build_futures_panel(context_bars, spx_q["last"], vix_last)
    hot_day = sectors.hot_sector(etf_perf, "chg_1d")
    hot_week = sectors.hot_sector(etf_perf, "chg_5d")

    adv = int((change_tbl["chg_1d"] > 0).sum()) if not change_tbl.empty else 0
    decl = int((change_tbl["chg_1d"] < 0).sum()) if not change_tbl.empty else 0

    # ---- Sector-filterable movers + sector/sub-sector cards --------------
    movers_filter = _build_movers_filter(change_tbl, news, mcfg["top_n"])
    subsec_hierarchy = _subsector_hierarchy(change_tbl)
    spy_chg = _q(context_bars, bench)["chg_1d"]
    sector_cards = [{"sector": "Overall", "chg_1d": spy_chg}] + [
        {"sector": r["sector"], "chg_1d": r["chg_1d"]} for r in etf_perf.reset_index().to_dict("records")
    ]
    # ETF symbol per sector (for chart links on sector chips/rows).
    sector_etf = {v: k for k, v in settings["universe"]["sector_etfs"].items()}
    sector_etf["Overall"] = bench

    # ---- Fundamentals for every displayed symbol (global filter) ---------
    displayed = set()
    for blk in movers_filter.values():
        for horizon in ("day", "week"):
            for side in ("winners", "losers"):
                displayed.update(r["symbol"] for r in blk[horizon][side])
    displayed.update(r["symbol"] for r in options_rows)
    displayed.update(i["symbol"] for i in ideas)
    fundamentals_map = fetch_fundamentals_map(
        provider, sorted(displayed),
        max_symbols=int(settings.get("fundamentals", {}).get("max_symbols", 400)))

    payload = {
        "as_of": str(expected_day.date()),
        "session": session,
        "session_label": "Evening (post-close)" if session == "pm" else "Morning (pre-open)",
        "session_note": _session_note(session),
        "generated_at": _now_et().strftime("%Y-%m-%d %H:%M ET"),
        "provider": getattr(provider, "name", "?"),
        "freshness": {"ok": fr.ok, "expected_day": str(fr.expected_day.date()),
                      "summary": fr.summary()},
        "disclaimer": DISCLAIMER,
        "market_pulse": {
            "indices": [_q(context_bars, s) for s in settings["universe"]["macro"]["indices"]],
            "futures": [_q(context_bars, s) for s in settings["universe"]["macro"]["futures"]],
            "vix": {"last": vix_last, "regime": sent.vix_regime(vix_last)["regime"]},
            "rates": [_q(context_bars, s) for s in settings["universe"]["macro"]["rates"]],
            "intermarket": [_q(context_bars, s) for s in settings["universe"]["macro"]["intermarket"]],
            "breadth": {"pct_above_50": None, "pct_above_200": None, "adv": adv, "decl": decl},
        },
        "sectors": {
            "etf_perf": etf_perf.reset_index().to_dict("records"),
            "hot_day": hot_day, "hot_week": hot_week,
            "subsectors": subsec.to_dict("records") if not subsec.empty else [],
            "rrg": rrg.reset_index().to_dict("records") if not rrg.empty else [],
        },
        "winners": _movers_records(day["winners"]),
        "losers": _movers_records(day["losers"]),
        "winners_week": week["winners"].reset_index().to_dict("records"),
        "losers_week": week["losers"].reset_index().to_dict("records"),
        "sector_cards": sector_cards,
        "sector_etf": sector_etf,
        "subsector_hierarchy": subsec_hierarchy,
        "movers_filter": movers_filter,
        "fundamentals_map": fundamentals_map,
        "options": {"table": sorted(options_rows, key=lambda x: -(x.get("unusual_count") or 0))},
        "ideas": ideas, "longs": longs, "shorts": shorts,
        "futures": futures,
        "watchlist": _watchlist(hot_day, subsec, ideas),
        "accuracy": accuracy,
        "outofbox": _outofbox(rrg, futures, accuracy),
        "sector_chart_json": {
            "labels": list(etf_perf.index),
            "values": [round(float(v), 2) for v in etf_perf["chg_1d"]],
        },
    }
    return payload


def _safe(fn, *a):
    try:
        return fn(*a) or {}
    except Exception:
        return {}


def _session_note(session: str) -> str:
    if session == "am":
        return ("Pre-open: review overnight futures, global markets, today's economic & earnings "
                "calendar, and key ES/MNQ levels before the open. Watchlist carried from prior PM.")
    return ("Post-close: full recap of the completed session. Use ranked setups to build the "
            "next-session game plan.")


def _watchlist(hot_day, subsec, ideas) -> dict:
    sects = []
    if hot_day:
        sects = [hot_day["hot"]["sector"], hot_day["cold"]["sector"]]
    subs = list(subsec["industry"].head(3)) + list(subsec["industry"].tail(3)) if len(subsec) else []
    stocks = [i["symbol"] for i in ideas[:10]]
    return {"sectors": sects, "subsectors": subs, "stocks": stocks}


def _outofbox(rrg, futures, accuracy) -> List[str]:
    out = []
    if len(rrg):
        lead = list(rrg[rrg["quadrant"] == "Leading"].index)
        imp = list(rrg[rrg["quadrant"] == "Improving"].index)
        if lead:
            out.append(f"Rotation: leading sectors {', '.join(lead)} — momentum + relative strength.")
        if imp:
            out.append(f"Rotation: improving sectors {', '.join(imp)} — early rotation candidates.")
    if futures.get("gamma_flip", {}).get("available"):
        out.append(f"ES/SPX dealer pivot proxy near {futures['gamma_flip']['proxy_level']:.0f}; "
                   "watch for acceleration above / mean-reversion below.")
    if accuracy.get("available"):
        out.append(f"Model self-check: {accuracy['hit_rate']*100:.0f}% hit-rate over {accuracy['n']} "
                   "archived signals — weight higher-confidence buckets.")
    out.append("Consider: earnings-calendar straddle expected-move scan, VIX term-structure regime, "
               "and intermarket (yields/DXY/oil) confirmation before sizing.")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Daily Sector Analysis Briefing")
    ap.add_argument("--session", choices=["am", "pm", "auto"], default="pm",
                    help="'auto' picks am/pm from the current ET hour (for cron).")
    ap.add_argument("--config", default=str(ROOT / "config" / "settings.yaml"))
    ap.add_argument("--demo", action="store_true", help="use offline synthetic data")
    ap.add_argument("--out", default=None, help="write report HTML to this path too")
    args = ap.parse_args(argv)

    # 'auto' resolves the session by ET hour so a handful of UTC crons cover 5am/5pm ET
    # under both EST and EDT, running exactly once per intended time.
    if args.session == "auto":
        hour = _now_et().hour
        if hour == 5:
            args.session = "am"
        elif hour == 17:
            args.session = "pm"
        else:
            print(f"[briefing] ET hour {hour} not a 5am/5pm window — skipping.")
            return 0

    load_env(ROOT / ".env")
    settings = load_settings(args.config)

    if args.demo:
        from .demo_data import DemoProvider
        provider = DemoProvider()
    else:
        from .providers import build_provider
        provider = build_provider(settings.get("provider", "hybrid"))

    payload = build_payload(provider, settings, args.session)
    html = render_html(payload)
    saved = storage.save_briefing(payload, html, payload["as_of"], args.session,
                                  settings["retention_days"])
    if args.out:
        Path(args.out).write_text(html)
    print(f"[briefing] {payload['as_of']} {args.session} | {payload['freshness']['summary']} | "
          f"ideas={len(payload['ideas'])} longs={len(payload['longs'])} shorts={len(payload['shorts'])}")
    print(f"[briefing] saved: {saved['html']} (pruned {len(saved['pruned'])} old files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
