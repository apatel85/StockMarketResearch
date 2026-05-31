# Daily Sector Analysis Briefing

An automated US-equity research briefing for active options/futures traders. It runs
**twice every trading day — 5:00 AM ET (pre-open) and 5:00 PM ET (post-close)** — and
produces an **interactive multi-tab HTML report** covering sector/sub-sector performance,
top-10 winners & losers, options flow, ranked long/short ideas with a **confidence %**,
**entry/stop/target levels + top-3 option strategies**, and ES/NQ key levels.

> ⚠️ For research and education only. Not investment advice. Trading involves risk of loss.

## What it produces (report tabs)

1. **Overview** — indices, ES/NQ futures, VIX, rates, intermarket, breadth.
2. **Sectors** — 11 SPDR sector ETFs + GICS sub-sector medians, hot/cold sector (day & week),
   and an RRG rotation table (Leading / Improving / Weakening / Lagging vs SPY).
3. **Winners & Losers** — top/bottom 10 for the day and the week, each with a catalyst.
4. **Options Flow** — put/call ratios, ATM IV, expected move, unusual vol/OI activity.
5. **Long & Short Ideas** — ranked, with confidence % and the drivers behind each call.
6. **Trade Setups** — entry/stop/target (ATR + pivots) and 3 option strategies tuned to IV.
7. **Futures & Levels** — ES/NQ prior-day H/L, ATR range, VIX-implied move, SPX gamma proxy.
8. **Watchlist** — sectors / sub-sectors / stocks to monitor.
9. **Accuracy** — rolling hit-rate of prior signals from the 30-day archive + extra signals.

## How signals are built

A composite **confidence %** fuses four sub-scores (weights in `config/settings.yaml`):
**Technical** (trend vs 20/50/200 DMA, RSI, MACD, relative strength, volume) ·
**Fundamental** (valuation, growth, margins, analyst rating, earnings-date catalyst) ·
**Sentiment** (headline tone, put/call, VIX regime) · **Flow** (options positioning).

## Data feed (hybrid)

- **Polygon (free "Stocks Basic")** — primary EOD equities. The **Grouped Daily** endpoint
  returns the whole market in one call, so the full S&P 500 is ranked within the free
  rate limit. Set `POLYGON_API_KEY` (see below).
- **yfinance** — options chains, fundamentals, and index/futures context the free tier lacks.
- Falls back to yfinance automatically if no Polygon key is present.
- Upgrade path: add **Polygon Options Starter ($29/mo)** later — implement `get_options_chain`
  in `src/providers/polygon_provider.py`; no other code changes.

Both run times are outside market hours, so **real-time data is not required** — settled
end-of-day / delayed data is sufficient and more accurate.

## Setup

```bash
cd daily-sector-briefing
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then put your free Polygon key in .env
```

## Run

```bash
# Offline demo (synthetic data) — renders a full report with no network/key:
python -m src.run_briefing --session pm --demo

# Live (uses POLYGON_API_KEY + yfinance):
python -m src.run_briefing --session pm      # post-close
python -m src.run_briefing --session am      # pre-open

# Output: reports/latest.html (+ dated reports/<date>-<session>.html, data/<date>-<session>.json)
```

Refresh the S&P 500 universe occasionally:
```bash
python scripts/refresh_sp500.py
```

## Automation (5am & 5pm ET)

`.github/workflows/briefing.yml` runs on a UTC cron covering 5am/5pm ET under both EST and
EDT (the `--session auto` guard fires exactly once per intended time), then commits the
archive and publishes `reports/` to GitHub Pages.

It also runs a **PM briefing automatically whenever app changes land on the default branch**
(e.g. when you merge a PR), so the dashboard refreshes without touching the Actions UI. The
bot's archive commits carry `[skip ci]`, so this never loops.

**To enable:**
1. Repo **Settings → Secrets and variables → Actions → New repository secret**:
   `POLYGON_API_KEY = <your key>`.
2. Repo **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. (Optional) Trigger manually via the **workflow_dispatch** "Run workflow" button.

**View it on the web:** after a successful run, the report is published to GitHub Pages at
`https://<owner>.github.io/<repo>/` (root serves the latest briefing via `index.html`).

## Data freshness guard

Only the previous/current trading day's data is accepted. `src/freshness.py` computes the
expected last completed NYSE trading day and **aborts the run** (rather than publishing) if
core series (sector ETFs + benchmark) are stale or missing.

## Retention

`src/storage.py` keeps **30 days** of dated JSON + HTML and prunes older files. Git history
is the long-term archive. (Optional later: persist to the connected Supabase project.)

## Tests

```bash
pytest -q          # offline; indicators, freshness, scoring, movers, and an end-to-end smoke test
```

## Layout

```
src/providers/   polygon (free EOD) + yfinance + hybrid router
src/             calendar, freshness, indicators, sectors, movers, options_flow,
                 fundamentals, sentiment, scoring, strategies, futures_levels,
                 backtest, storage, report, run_briefing, demo_data
config/          settings.yaml, subsector_map.yaml, sp500.csv
templates/       report.html.j2 (multi-tab, self-contained)
.github/workflows/briefing.yml
```
