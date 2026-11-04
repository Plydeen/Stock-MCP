"""Tests for long-call risk/reward and Black-Scholes helpers."""

import pytest

from app.risk_reward import (
    SPREAD_MAX,
    analyze_long_call_batch,
    black_scholes_call_analysis,
    bs_call,
    implied_vol,
    long_call,
    spread_pct,
)


def test_spread_pct_from_quotes():
    assert spread_pct(4.10, 4.30) == pytest.approx(0.0476, rel=1e-3)


def test_long_call_tradeable_when_spread_and_rr_clear():
    result = long_call(entry=4.20, strike=250, target=300, bid=4.10, ask=4.30)
    assert result["breakeven"] == 254.2
    assert result["payoff_ratio_at_target"] == 10.9
    assert result["spread_ok"] is True
    assert result["rr_ok"] is True
    assert result["tradeable"] is True


def test_long_call_fails_wide_spread():
    result = long_call(entry=4.20, strike=250, target=300, bid=3.0, ask=6.0)
    assert result["spread_ok"] is False
    assert result["tradeable"] is False
    assert "SPREAD" in result["notes"]


def test_long_call_fails_thin_payoff():
    result = long_call(entry=4.20, strike=250, target=255, bid=4.10, ask=4.30, rr_floor=3.0)
    assert result["rr_ok"] is False
    assert result["tradeable"] is False


def test_long_call_without_quotes_skips_spread_check():
    result = long_call(entry=4.20, strike=250, target=300)
    assert result["spread_pct"] is None
    assert result["spread_ok"] is False
    assert result["tradeable"] is False
    assert "no quotes" in result["notes"]


def test_analyze_long_call_batch_aggregate():
    payload = analyze_long_call_batch(
        [
            {"label": "good", "entry": 4.20, "strike": 250, "target": 300, "bid": 4.10, "ask": 4.30},
            {"label": "bad", "entry": 4.20, "strike": 250, "target": 255, "bid": 4.10, "ask": 4.30},
        ]
    )
    assert payload["count"] == 2
    assert payload["all_tradeable"] is False
    assert payload["spread_max_pct"] == SPREAD_MAX * 100


def test_bs_call_returns_greeks():
    result = bs_call(spot=245, strike=250, dte_days=540, iv=0.30)
    assert result is not None
    assert result["price"] is not None
    assert result["delta"] is not None


def test_implied_vol_round_trip():
    greeks = bs_call(spot=245, strike=250, dte_days=540, iv=0.30)
    assert greeks is not None
    iv = implied_vol(greeks["price"], spot=245, strike=250, dte_days=540)
    assert iv == 0.30


def test_black_scholes_call_analysis_from_iv():
    result = black_scholes_call_analysis(spot=245, strike=250, dte_days=540, iv=0.30)
    assert result["greeks"] is not None
    assert result["greeks"]["price"] is not None


def test_black_scholes_call_analysis_from_price():
    greeks = bs_call(spot=245, strike=250, dte_days=540, iv=0.30)
    result = black_scholes_call_analysis(
        spot=245,
        strike=250,
        dte_days=540,
        market_price=greeks["price"],
    )
    assert result["implied_vol"] == 0.30
    assert result["greeks"] is not None
