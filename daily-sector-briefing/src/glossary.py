"""Plain-English definitions for finance terms used across the report.

Surfaced as click/hover tooltips in the UI. Keys are referenced via data-g="<key>".
"""

GLOSSARY = {
    "relative_strength": "Relative Strength — a stock/sector's return minus the benchmark's "
        "(SPY) over the same period. Positive = outperforming the market (a leader).",
    "quadrant": "RRG Quadrant — Relative Rotation Graph state vs SPY. Leading (strong & "
        "rising), Weakening (strong but fading), Lagging (weak & falling), Improving "
        "(weak but turning up). Rotation usually flows Leading→Weakening→Lagging→Improving.",
    "rrg": "Relative Rotation Graph — plots a group's relative strength vs its momentum to "
        "show where it sits in the rotation cycle.",
    "put_call": "Put/Call ratio — put volume divided by call volume. Below ~0.7 is call-heavy "
        "(bullish positioning); above ~1.3 is put-heavy (bearish/hedging).",
    "iv": "Implied Volatility (IV) — the market's expected future volatility priced into "
        "options. Higher IV = more expensive options.",
    "atm_iv": "At-the-Money IV — implied volatility of the option whose strike is nearest the "
        "current price; a clean read on expected movement.",
    "iv_rank": "IV Rank — where current IV sits within its 1-year range (0–100). High rank "
        "favours selling premium; low rank favours buying it.",
    "expected_move": "Expected Move — the price swing the options market is pricing in, from "
        "the at-the-money straddle. Useful for setting targets and strike selection.",
    "vol_oi": "Volume / Open Interest — a contract's day volume divided by its existing open "
        "interest. Well above 1 flags unusual (possibly new, informed) activity.",
    "unusual": "Unusual Options Activity — contracts trading far above their open interest, "
        "often a sign of fresh institutional positioning.",
    "atr": "Average True Range (ATR) — average daily price range over ~14 days; a volatility "
        "measure used to size stops and expected ranges.",
    "rsi": "Relative Strength Index (RSI) — momentum oscillator (0–100). Above 70 = overbought, "
        "below 30 = oversold.",
    "macd": "MACD — Moving Average Convergence Divergence. A positive histogram signals "
        "upward momentum; negative signals downward.",
    "dma": "Daily Moving Average (DMA) — average closing price over N days (20/50/200). Price "
        "above them = uptrend; below = downtrend.",
    "pivot": "Pivot Points — support/resistance levels from the prior day's high/low/close, "
        "used for intraday entries and targets.",
    "gamma_flip": "Gamma Flip — the index level where options-dealer hedging shifts from "
        "stabilising to amplifying moves. Above it markets tend to be calmer; below, choppier.",
    "confidence": "Confidence % — the model's conviction in a setup, blending technical, "
        "fundamental, sentiment, and options-flow sub-scores.",
    "breadth": "Market Breadth — how broadly stocks participate (advancers vs decliners, % "
        "above moving averages). Strong breadth confirms a trend.",
    "vix": "VIX — the market's 30-day expected volatility ('fear gauge'). Below 15 calm, above "
        "20 elevated, above 28 stress.",
    "rr": "Risk/Reward (R:R) — potential reward divided by risk. 2.0 means the target is twice "
        "the distance to the stop.",
    "bias": "Directional Bias — whether the setup leans long (expecting up) or short (down).",
    "entry": "Entry — suggested price/trigger to initiate the trade.",
    "stop": "Stop — price where the thesis is wrong and the trade is exited to cap loss.",
    "target": "Target — projected profit-taking level, here ~2x the risk distance.",
    "catalyst": "Catalyst — the news/event (earnings, guidance, upgrade) driving the move.",
}
