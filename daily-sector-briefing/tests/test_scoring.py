from src import scoring, strategies, options_flow, sentiment, fundamentals


WEIGHTS = {"technical": 0.35, "fundamental": 0.20, "sentiment": 0.15, "flow": 0.30}


def _bull_feats():
    return {"last": 100, "atr": 2.0, "rsi": 62, "macd_hist": 0.5,
            "above_sma": {20: True, 50: True, 200: True}, "rel_strength_20": 5.0,
            "vol_surge": 1.8, "pivots": {"pivot": 100, "r1": 103, "s1": 97, "r2": 106, "s2": 94}}


def _bear_feats():
    return {"last": 100, "atr": 2.0, "rsi": 38, "macd_hist": -0.5,
            "above_sma": {20: False, 50: False, 200: False}, "rel_strength_20": -5.0,
            "vol_surge": 1.2, "pivots": {"pivot": 100, "r1": 103, "s1": 97, "r2": 106, "s2": 94}}


def test_confidence_in_bounds():
    s = scoring.composite(_bull_feats(), {"score": 70}, {"score": 65},
                          {"available": True, "bias": "bullish", "pc_ratio_vol": 0.5}, WEIGHTS)
    assert 0 <= s["confidence"] <= 100


def test_bullish_inputs_give_long_bias():
    s = scoring.composite(_bull_feats(), {"score": 70}, {"score": 65},
                          {"available": True, "bias": "bullish", "pc_ratio_vol": 0.5}, WEIGHTS)
    assert s["bias"] == "long"


def test_bearish_inputs_give_short_bias():
    s = scoring.composite(_bear_feats(), {"score": 30}, {"score": 35},
                          {"available": True, "bias": "bearish", "pc_ratio_vol": 1.8}, WEIGHTS)
    assert s["bias"] == "short"


def test_trade_levels_long_risk_reward():
    lv = strategies.trade_levels(_bull_feats(), "long")
    assert lv["stop"] < lv["entry"] < lv["target"]


def test_trade_levels_short_risk_reward():
    lv = strategies.trade_levels(_bear_feats(), "short")
    assert lv["target"] < lv["entry"] < lv["stop"]


def test_option_strategies_count_and_iv_regime():
    rich = strategies.option_strategies("long", iv_rank=80, expected_move=3.0)
    cheap = strategies.option_strategies("long", iv_rank=10, expected_move=3.0)
    assert len(rich) == 3 and len(cheap) == 3
    assert "credit" in rich[0]["name"].lower() or "put" in rich[0]["name"].lower()


def test_flow_bias_from_pc_ratio():
    res = options_flow._flow_bias(0.5, 100, 50)
    assert res == "bullish"
    assert options_flow._flow_bias(1.8, 50, 90) == "bearish"


def test_sentiment_headline_tone():
    pos = sentiment.headline_tone([{"title": "Company beats and raises guidance"}])
    neg = sentiment.headline_tone([{"title": "Company misses, downgrade and lawsuit"}])
    assert pos["score"] > 50 > neg["score"]


def test_fundamentals_neutral_when_empty():
    assert fundamentals.score_fundamentals({})["score"] == 50.0
