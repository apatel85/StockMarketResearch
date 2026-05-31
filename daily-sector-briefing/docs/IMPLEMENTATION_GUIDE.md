# Daily Sector Analysis Briefing — Implementation Guide

> A complete, self-contained specification so **any AI model or engineer can rebuild this
> system from scratch**. It documents what was built, the data model, the analysis logic, and
> **two implementation options** (GitHub-automated vs. live API HTML dashboard) for you to
> choose from.

---

## 1. Purpose & goal

An automated US-equity research briefing for an active options/futures trader (day & swing via
options; ES future-options + MNQ futures daily; long-term holds hedged with SPY). It runs
**twice every trading day — 5:00 AM ET (pre-open) and 5:00 PM ET (post-close)** — and surfaces
*stocks likely to move with high probability*, with:

- Sector & sub-sector performance (last day + last week), hottest/coldest.
- Top-10 winners & losers (overall and per sector/sub-sector).
- Options inflow/outflow (put/call, unusual vol/OI, IV, expected move).
- Long & short candidates with a **confidence %**, fusing **fundamental + technical +
  sentiment + flow**.
- Entry / stop / target levels and **top-3 option strategies** tuned to IV.
- ES/NQ/VIX key levels for futures trading.
- An interactive, multi-tab report with global fundamental filters, sector→sub-sector
  drill-down, glossary tooltips, and one-click TradingView charts.

**Hard rule:** only the *previous or current trading day's* data is acceptable. Stale data must
never be published — a freshness guard aborts and shows a diagnostic instead.

---

## 2. Choose your implementation — TWO OPTIONS

| | **Option A — GitHub-automated (current build)** | **Option B — Live API HTML dashboard** |
|---|---|---|
| How it runs | GitHub Actions cron (5am/5pm ET) runs a Python generator, commits a static HTML report, publishes to GitHub Pages | A single HTML/JS app that calls the data API **directly from the browser** on load/refresh; no server, no schedule |
| Where data is fetched | Server-side (Actions runner) | Client-side (user's browser) |
| Freshness | Snapshot at run time (twice daily) | Live whenever opened / on a timer |
| API key exposure | **Secret stays server-side** (safe) | **Key is exposed in the browser** unless proxied → needs a key-restricted/proxy setup |
| Cost / infra | Free (Actions + Pages) | Free static hosting, but live calls hit rate limits faster; may need a tiny proxy (e.g. Cloudflare Worker) to hide the key |
| Heavy analysis (scoring, backtests) | Full Python/pandas power | Limited to JS in-browser; heavy logic must move to a proxy/function |
| Best when | You want a reliable scheduled briefing, archived history, zero maintenance | You want on-demand/live refresh and are OK exposing a restricted key or running a small proxy |

**Recommendation:** **Option A** for the scheduled 5am/5pm briefing (matches the goal, keeps the
key safe, supports the full analysis + 30-day archive + accuracy backtest). Use **Option B**
(or a hybrid: Option A generates data JSON, Option B renders it live) only if you need
intraday/on-demand refresh. Section 10 specifies Option B in full.

> The rest of this guide (sections 3–9) documents **Option A**, which is implemented in this
> repo. Section 10 specifies **Option B**. Both share sections 3–8 (requirements, data model,
> analysis, UI).

---

## 3. Functional requirements

1. **Universe:** S&P 500 constituents mapped to GICS sector + industry (sub-sector), plus the
   11 SPDR sector ETFs (XLK, XLV, XLF, XLY, XLC, XLI, XLP, XLE, XLU, XLRE, XLB) and macro
   context (^GSPC, ^NDX, ^DJI, ^RUT, ES=F, NQ=F, ^VIX, ^TNX, ^TYX, DXY, CL=F, GC=F, SPY).
2. **Two sessions/day:** `am` (pre-open: overnight/futures/calendar framing) and `pm`
   (post-close recap). A scheduler triggers both at 5am/5pm ET.
3. **Freshness guard:** compute the expected last completed NYSE trading day; require the
   benchmark (SPY) + all sector ETFs to have a bar for that day, else abort and publish a
   diagnostic page (never stale data).
4. **Analysis:** sectors, sub-sectors, movers, options flow, fundamentals, technicals,
   sentiment → composite confidence; long/short ranking; trade levels; option strategies;
   futures levels; rolling accuracy.
5. **Report:** interactive multi-tab HTML, self-contained (no build step), mobile-friendly.
6. **Archive:** 30 days of dated JSON + HTML, older pruned. Per-day fundamentals cache.

---

## 4. Data sources & feed strategy (hybrid)

- **Polygon.io free "Stocks Basic"** — primary EOD equities. Key endpoint:
  `GET /v2/aggs/grouped/locale/us/market/stocks/{date}?adjusted=true` returns the **whole
  market's daily OHLCV in one call** → ranks S&P 500 movers + aggregates sectors within the
  5-calls/min free limit. Also `/v2/aggs/ticker/{sym}/range/1/day/{from}/{to}` and
  `/v2/reference/news`. Real-time is **not needed** (both run times are outside market hours).
- **yfinance** — options chains (P/C, IV, OI), fundamentals (P/E, fwd P/E, debt/equity,
  growth, market cap), pre-market/overnight, and the bars Polygon's stock tier lacks (indices,
  futures, rates, commodities).
- **Hybrid router:** equity bars/grouped/news → Polygon (if `POLYGON_API_KEY` set, else
  yfinance); options/fundamentals → yfinance. Missing symbols fall back to yfinance.
- **Upgrade path:** add **Polygon Options Starter ($29/mo)** later by implementing
  `get_options_chain` in the Polygon provider — no other code changes.
- **Secret handling:** `POLYGON_API_KEY` via GitHub Actions repository secret (Option A) or a
  proxy (Option B). Never commit the key; never paste it in code.

---

## 5. Architecture (Option A) — modules & data flow

```
config/        settings.yaml (universe, weights, thresholds, retention),
               subsector_map.yaml, sp500.csv (symbol,name,sector,industry)
src/providers/ base.py (interface), polygon_provider.py, yfinance_provider.py,
               hybrid.py (router + build_provider())
src/           calendar_utils.py  NYSE trading-day / last-completed-session logic
               freshness.py       expected-day check + StaleDataError + enforce()
               data_fetch.py      grouped-window fetch, shortlist history, fundamentals cache
               indicators.py      SMA/EMA, RSI, MACD, ATR, rel-strength, vol surge, pivots
               movers.py          change table + top/bottom N (day & week, per group)
               sectors.py         ETF perf, sub-sector medians, hot sector, RRG quadrants
               options_flow.py    P/C, vol/OI unusual, ATM IV, expected move, IV rank
               fundamentals.py    0-100 fundamental sub-score + earnings catalyst
               sentiment.py       headline tone + P/C + VIX regime → sentiment sub-score
               scoring.py         technical/flow sub-scores + weighted composite confidence
               strategies.py      entry/stop/target + top-3 IV-aware option strategies
               futures_levels.py  ES/NQ levels, VIX-implied move, SPX gamma proxy
               backtest.py        rolling hit-rate from the 30-day archive
               storage.py         write dated JSON+HTML+index.html+latest.html; prune 30d
               report.py          Jinja2 render + render_error_html diagnostic
               glossary.py        finance-term definitions for tooltips
               demo_data.py       deterministic synthetic provider (offline tests/demo)
               run_briefing.py    orchestrator + CLI (--session am|pm|auto, --demo)
templates/report.html.j2          self-contained multi-tab UI (inline CSS/JS + Chart.js CDN)
.github/workflows/briefing.yml    cron + push + dispatch; commit archive; publish Pages
tests/                            pytest (indicators, freshness, scoring, movers, e2e, error)
```

**Pipeline (`build_payload`):**
1. Load `settings.yaml` + `sp500.csv`. Compute `expected_day = last_completed_trading_day()`.
2. `fetch_universe`: grouped-daily window (~12 trading days) for the change table; per-symbol
   ~260-day history for ETFs/benchmark/macro context.
3. **Freshness:** `check_freshness({**context_bars, **change_bars}, [SPY]+ETFs, expected_day)`
   → `enforce()` (raises `StaleDataError` if stale → diagnostic page).
4. Movers (day & week), sector ETF perf, sub-sector medians, RRG, hot/cold sector.
5. Build a **shortlist** (day+week movers, ≤30) → fetch full history → per symbol compute
   features, options flow, fundamentals, sentiment → `scoring.composite` → trade plan.
6. Fetch **fundamentals for every displayed symbol** (cached daily) for the global filter.
7. Assemble payload (section 6); render HTML; save + prune; (on any error) publish diagnostic.

---

## 6. Data model (payload → report)

```jsonc
{
  "as_of": "YYYY-MM-DD", "session": "am|pm", "session_label": "...", "generated_at": "...",
  "provider": "hybrid", "freshness": {"ok": true, "expected_day": "...", "summary": "..."},
  "market_pulse": { "indices": [{symbol,last,chg_1d}], "futures": [...], "vix": {last,regime},
                    "rates": [...], "intermarket": [...], "breadth": {adv, decl} },
  "sectors": { "etf_perf": [{sector,etf,chg_1d,chg_5d,chg_20d}], "hot_day": {hot,cold},
               "hot_week": {...}, "subsectors": [{sector,industry,median,mean,count,pct_up}],
               "rrg": [{sector,etf,rs,momentum,quadrant}] },
  "winners": [{symbol,name,sector,industry,chg_1d,chg_5d,close,catalyst}], "losers": [...],
  "sector_cards": [{sector,chg_1d}], "sector_etf": {sector: etf}, "subsector_hierarchy": {sector:[{industry,median,count}]},
  "movers_filter": { "Overall": {day:{winners,losers},week:{...}}, "<sector>": {...}, "<sector>|||<industry>": {...} },
  "fundamentals_map": { "SYM": {mcap, pe, fpe, de, growth, is_growth} },
  "options": { "table": [{symbol,sector,industry,pc_ratio_vol,atm_iv,expected_move_pct,bias,unusual_count}] },
  "ideas": [{symbol,name,sector,bias,confidence,components,notes,levels:{entry,stop,target,rr},
             option_strategies:[{name,rationale,tenor}], earnings_soon}],
  "longs": [...], "shorts": [...],
  "futures": {ES,NQ,VIX_implied,gamma_flip}, "watchlist": {sectors,subsectors,stocks},
  "accuracy": {available,n,hit_rate,hit_rate_long,hit_rate_short,by_confidence}, "outofbox": [...]
}
```
The renderer injects the filter/options/fundamentals/glossary structures as JSON into the page
for client-side filtering (with `<` escaped to `<` to prevent `</script>` breakout).

---

## 7. Analysis & scoring logic

- **Indicators:** SMA(20/50/200), EMA, RSI(14, Wilder), MACD(12/26/9), ATR(14), 20-day
  relative strength vs SPY, volume surge (last vs 20-day avg), gap %, floor-trader pivots.
- **Sub-sector performance:** median 1-day return of constituents grouped by GICS industry +
  breadth (% up); cross-checked against industry ETFs (config `subsector_map.yaml`).
- **RRG quadrant:** ratio = price/SPY; RS = window return of ratio; momentum = ΔRS.
  Leading (RS≥0, mom≥0), Weakening (RS≥0, mom<0), Lagging (RS<0, mom<0), Improving (RS<0, mom≥0).
- **Options flow:** P/C = put vol / call vol (near expiries); unusual = contract vol/OI ≥ 2;
  ATM IV + expected move from the nearest-expiry ATM straddle (straddle/spot). Bias: P/C<0.7
  bullish, >1.3 bearish.
- **Sub-scores (0–100, 50 = neutral):**
  - *Technical:* trend vs SMAs, RSI zones, MACD sign, rel-strength, volume.
  - *Fundamental:* growth, margins, PEG, analyst rating; +earnings-soon flag. Missing → 50.
  - *Sentiment:* 0.60·headline tone + 0.25·(P/C-derived) + 0.15·VIX regime.
  - *Flow:* bullish/neutral/bearish bias + unusual-activity bonus.
- **Composite confidence:** `blended = Σ weight·subscore` (default weights technical 0.35,
  fundamental 0.20, sentiment 0.15, flow 0.30). `bias = long if blended≥50 else short`;
  `confidence = |blended−50|·2` (0–100). Surface as long/short if confidence ≥ threshold (60).
- **Trade levels:** entry = pivot; stop = structure/1.5·ATR; target = entry ± 2·risk (R:R 2.0).
- **Option strategies:** chosen by bias × IV regime (rich IV → sell premium: credit spreads,
  CSP, covered calls; cheap IV → buy premium: debit spreads, long calls/puts, calendars).
  Tenor: weeklies (am/day) vs 2–6 week (pm/swing).
- **Accuracy backtest:** match prior archived ideas to realized next-day return; hit if a long
  rose / a short fell; report overall + by confidence bucket.

---

## 8. Report UI spec (shared by both options)

Self-contained HTML, dark theme, sticky nav, **9 tabs**: Overview, Sectors, Winners & Losers,
Options Flow, Long & Short Ideas, Trade Setups, Futures & Levels, Watchlist, Accuracy.

- **Global fundamentals filter** (sticky, all tabs): Market Cap ≥, P/E ≤, Fwd P/E ≤,
  Debt/Equity ≤, Growth ≥, Growth-only toggle, Reset, live match counter. Filters every stock
  list (client-side via the `fundamentals_map`); strict (a constrained-but-missing field hides
  the row).
- **Sector → sub-sector drill-down** on Winners/Losers & Options Flow: sector chips (with 1-day
  %) → on select, sub-sector chips appear (with median %) → breadcrumb shows path. "Overall" =
  whole market default.
- **Winners/Losers:** side-by-side winners | losers, day on top, week below (no scrolling).
- **Universal chart links:** click any symbol or sector ETF (or a chip's 📈 icon) → confirm →
  open TradingView (`tradingview.com/chart/?symbol=<tv>`); symbol map for indices/futures/rates.
- **Glossary tooltips:** dotted terms; hover to preview, click to pin (definitions in
  `glossary.py`).
- **Trade Setups:** responsive 3–4 wide card grid; click a card → open its chart; fundamental
  tags on each card.
- **Diagnostic page:** on failure, a styled page states the error (freshness vs. data) + a
  traceback, so the site is never blank.

---

## 9. Automation & ops (Option A)

- **`.github/workflows/briefing.yml`:**
  - Triggers: `schedule` (four UTC crons covering 5am/5pm ET under EST+EDT; `--session auto`
    resolves am/pm by ET hour and skips off-times), `workflow_dispatch` (manual, choose
    session), and `push` to the default branch on `daily-sector-briefing/**` (auto-run a PM
    briefing on merge; bot commits carry `[skip ci]` to avoid loops).
  - Job `briefing`: checkout → setup Python 3.11 → `pip install -r requirements.txt` →
    `python -m src.run_briefing --session ...` → commit `data/` + `reports/` → **upload Pages
    artifact from the freshly generated `reports/`** (`if: always()`).
  - Job `deploy-pages` (`needs: briefing`): `actions/deploy-pages@v4` (no checkout — deploys the
    uploaded artifact). **This avoids publishing a stale checkout.**
- **Enable:** repo secret `POLYGON_API_KEY`; Settings → Pages → Source = GitHub Actions.
- **View:** `https://<owner>.github.io/<repo>/` (root serves `index.html` = latest briefing).
- **Retention:** `storage.prune()` deletes dated files older than 30 days; git history is the
  long-term archive.

**Run/test commands**
```bash
pip install -r requirements.txt
python -m src.run_briefing --session pm           # live
python -m src.run_briefing --session pm --demo    # offline synthetic
pytest -q                                         # 27 tests
```

---

## 10. Option B — Live API HTML dashboard (full spec)

A single static page (`dashboard.html` + `app.js`) that fetches and analyses **in the browser**,
refreshable on demand. Reuse sections 6–8 verbatim for the data model, analysis, and UI.

**10.1 Architecture**
- `index.html` — the multi-tab UI from section 8 (port `report.html.j2` to static markup +
  the same embedded JS for filtering/charts/tooltips).
- `app.js` — on load (and on a refresh button / optional timer): fetch data, run the analysis,
  populate the tabs.
- **Key safety (critical):** browsers expose any embedded key. Do **one** of:
  1. **Proxy (recommended):** a tiny **Cloudflare Worker / Vercel function** holds
     `POLYGON_API_KEY` server-side and forwards whitelisted requests. The dashboard calls the
     proxy, never Polygon directly.
  2. **Key restriction:** if the provider supports domain/referrer-restricted keys, use a
     read-only restricted key (Polygon does not restrict by referrer → prefer the proxy).
- **Endpoints (via proxy):** Polygon grouped-daily (movers/sectors), per-symbol aggs
  (indicators), reference news; for options/fundamentals use a provider with CORS/JSON
  (e.g. Polygon options on a paid tier, or a serverless function wrapping yfinance).

**10.2 Client analysis**
Re-implement sections 5–7 in JavaScript (or call a serverless "analyze" function that runs the
existing Python and returns the section-6 payload — **recommended hybrid**: Option A's generator
emits `data/<date>-<session>.json`, and Option B's page just renders it live). The JS port needs:
SMA/EMA/RSI/MACD/ATR, relative strength, pivots, sub-sector medians, RRG, options-flow math,
and the composite scoring — all already specified with formulas in section 7.

**10.3 Freshness**
Apply the same guard client-side: derive the expected last trading day (ship a small holiday
list or call a calendar endpoint) and refuse to render if the latest bar predates it — show the
diagnostic panel instead.

**10.4 Hosting**
Static host (GitHub Pages / Netlify / Vercel) + the proxy function. No schedule needed; the page
is live whenever opened. Add a "Last refreshed" timestamp and a manual Refresh button.

**10.5 Trade-offs vs Option A**
+ Live/on-demand, no waiting for cron. − Key needs a proxy; heavy analysis is easier server-side;
no automatic archive/accuracy unless you add storage (e.g. the proxy writes daily snapshots).

**Recommended hybrid:** keep **Option A** generating the section-6 JSON on schedule (safe key,
full analysis, archive), and **add Option B** as a live viewer that reads the latest JSON and can
*also* do a live intraday refresh via the proxy. Best of both.

---

## 11. Config reference (`config/settings.yaml`)

`provider` (hybrid|polygon|yfinance), `retention_days` (30), `universe` (sp500_csv, sector_etfs,
macro, benchmark), `movers` (top_n, min_price, min_dollar_volume), `indicators` (sma_windows,
rsi/atr periods, macd, volume lookback), `scoring.weights` + thresholds + max_ideas, `options`
(unusual_vol_oi_ratio, near_expiries, iv_rank_lookback), `fundamentals.max_symbols`,
`freshness` (max_stale_days, abort_on_stale).

---

## 12. Changelog — everything built in this project

1. **Scaffold (Option A):** Python package, hybrid Polygon+yfinance providers, NYSE calendar,
   freshness guard, indicators, movers, sectors/RRG, options flow, fundamentals, sentiment,
   composite scoring, strategies, futures levels, 30-day storage, accuracy backtest, Jinja2
   multi-tab report, demo provider, 26 tests, GitHub Actions cron + Pages, README.
2. **Interactive UX v1:** compact sector filter chips on Winners/Losers & Options Flow;
   side-by-side winners|losers (day + week); glossary tooltips on finance terms; Trade Setups as
   a clickable grid (→ TradingView); JSON safely embedded.
3. **Filters, drill-down, chart links:** global fundamentals filter (Market Cap, P/E, Fwd P/E,
   Debt/Equity, Growth, Growth-only) across all tabs with a match counter; sector→sub-sector
   (GICS industry) drill-down with breadcrumb; universal TradingView chart links on every
   symbol/ETF; per-stock fundamentals fetched + cached daily; design pass (gradient nav/pills,
   hover-lift cards, fundamental tags, RRG legend).
4. **Go-live + robustness:** auto-run on merge (push trigger) + serve at Pages root via
   `index.html`; **fixed the Pages deploy** to publish the freshly generated files (not a stale
   checkout); **resilient generator** that always publishes a styled diagnostic page (and
   commits it) on any failure — the dashboard is never blank — with a freshness-specific message.
5. **This document.**

---

## 13. Acceptance criteria

- `pytest -q` green. `--demo` renders all 9 tabs with working filters, drill-down, tooltips,
  chart links. Live run on a trading day publishes a populated report at the Pages root; a
  holiday/stale feed publishes a diagnostic (never stale data). 30-day archive prunes correctly.
- Research/education only — not investment advice.
```
