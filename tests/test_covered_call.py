"""Tests for the covered-call scenario engine (build_plan section 12 checks)."""

from datetime import date

import pytest

from app.covered_call import (
    MAX_CELLS,
    cell_count,
    eval_date_offsets,
    occ_ticker,
    price_grid,
    scenario_metrics,
    scenario_rows,
    solve_iv,
    build_response,
)
from app.risk_reward import bs_call

TODAY = date(2026, 1, 1)
EXPIRY = date(2026, 2, 10)  # 40 days out
DTE = (EXPIRY - TODAY).days


def _rows(**overrides):
    params = dict(
        scenario_id=0,
        strike=105.0,
        expiration=EXPIRY,
        today=TODAY,
        entry_price=100.0,
        premium=2.0,
        sigma=0.30,
        dte=DTE,
        rate=0.04,
        dividend_yield=0.0,
        shares_per_contract=100,
        contracts=1,
        price_range_pct=0.20,
        price_steps=21,
        date_steps=5,
    )
    params.update(overrides)
    return scenario_rows(**params)


# Column indices in the long-format rows
I_EVAL, I_DTE, I_PRICE, I_CALLVAL, I_PLPS, I_PLTOT, I_PCT = 3, 4, 5, 6, 7, 8, 9


def test_occ_ticker_format():
    assert occ_ticker("AAPL", date(2026, 8, 21), 320.0) == "O:AAPL260821C00320000"
    assert occ_ticker("aapl", date(2026, 8, 21), 320.5) == "O:AAPL260821C00320500"


def test_price_grid_odd_includes_center():
    grid = price_grid(300.0, 0.20, 5)
    assert grid[0] == pytest.approx(240.0)
    assert grid[-1] == pytest.approx(360.0)
    assert grid[2] == pytest.approx(300.0)  # odd -> center included


def test_eval_offsets_endpoints_and_dedup():
    assert eval_date_offsets(40, 5) == [0, 10, 20, 30, 40]
    # Small DTE with many steps collides -> dedup but keeps expiry endpoint.
    assert eval_date_offsets(3, 5)[-1] == 3
    assert len(set(eval_date_offsets(3, 5))) == len(eval_date_offsets(3, 5))


def test_expiration_line_equals_payoff():
    """At the expiration eval date, pl_per_share == (S - S0) + p - max(0, S-K)."""
    rows = _rows()
    S0, K, p = 100.0, 105.0, 2.0
    expiry_rows = [r for r in rows if r[I_DTE] == 0]
    assert expiry_rows, "expected an eval date landing on expiration"
    for r in expiry_rows:
        S = r[I_PRICE]
        expected = (S - S0) + p - max(0.0, S - K)
        assert r[I_PLPS] == pytest.approx(round(expected, 2), abs=0.01)


def test_breakeven_zero_at_expiry():
    """Underlying == S0 - p should give ~0 P/L at expiry (breakeven, OTM)."""
    rows = _rows()
    be = 100.0 - 2.0  # 98, a grid point
    match = [r for r in rows if r[I_DTE] == 0 and r[I_PRICE] == pytest.approx(be)]
    assert match
    assert match[0][I_PLPS] == pytest.approx(0.0, abs=0.01)


def test_max_profit_cap_flat_above_strike():
    """At expiry, for all S >= K, pl_per_share is flat at (K - S0) + p."""
    rows = _rows()
    cap = (105.0 - 100.0) + 2.0  # 7.0
    itm = [r for r in rows if r[I_DTE] == 0 and r[I_PRICE] >= 105.0]
    assert itm
    for r in itm:
        assert r[I_PLPS] == pytest.approx(cap, abs=0.01)


def test_theta_decay_call_value_ordering():
    """For a fixed price, an earlier eval date's call value >= a later one (theta)."""
    rows = _rows()
    # Group call values by (price) across eval dates; earlier dte_at_eval is larger.
    center = 100.0
    at_center = [r for r in rows if r[I_PRICE] == pytest.approx(center)]
    at_center.sort(key=lambda r: -r[I_DTE])  # descending time remaining
    call_vals = [r[I_CALLVAL] for r in at_center]
    for earlier, later in zip(call_vals, call_vals[1:]):
        assert earlier + 1e-9 >= later  # compresses toward expiry


def test_iv_round_trip():
    """Feed a known premium -> solve IV -> reprice -> recover the premium."""
    premium = bs_call(300, 320, 40, 0.30, 0.04, 0.0)["price"]
    iv = solve_iv(premium=premium, spot=300, strike=320, dte=40, rate=0.04, dividend_yield=0.0)
    assert iv == pytest.approx(0.30, abs=1e-3)
    reprice = bs_call(300, 320, 40, iv, 0.04, 0.0)["price"]
    assert reprice == pytest.approx(premium, abs=0.02)


def test_metrics_core_identities():
    m = scenario_metrics(
        entry_price=100.0, strike=105.0, premium=2.0, sigma=0.30,
        dte=DTE, rate=0.04, dividend_yield=0.0,
    )
    assert m["breakeven"] == pytest.approx(98.0)
    assert m["max_profit"] == pytest.approx(7.0)
    assert m["max_loss"] == pytest.approx(-98.0)
    assert m["static_return"] == pytest.approx(2.0 / 98.0, abs=1e-4)
    assert m["if_called_return"] == pytest.approx(7.0 / 98.0, abs=1e-4)
    assert 0.0 <= m["prob_profit"] <= 1.0
    assert 0.0 <= m["prob_assignment"] <= 1.0
    assert m["assignment_risk_flag"] is False  # no dividend


def test_assignment_risk_flag_itm_with_dividend():
    # Deep ITM, near expiry, meaningful dividend -> extrinsic below expected div.
    m = scenario_metrics(
        entry_price=120.0, strike=100.0, premium=21.0, sigma=0.30,
        dte=5, rate=0.04, dividend_yield=0.05,
    )
    assert m["assignment_risk_flag"] is True


def test_cell_budget_helper():
    assert cell_count(3, 21, 5) == 315
    assert cell_count(1, 21, 5) < MAX_CELLS
    assert cell_count(2, 30, 30) > MAX_CELLS


def test_build_response_shape_and_degradation():
    resolved = [
        {
            "scenario_id": 0, "label": None, "strike": 105.0, "expiration": EXPIRY,
            "premium": 2.0, "iv": 0.30, "dte": DTE, "shares_per_contract": 100,
            "premium_source": "override", "iv_source": "override", "iv_quality": "exact",
        },
        {"scenario_id": 1, "label": "bad", "error": "no recent trade; pass premium"},
    ]
    resp = build_response(
        ticker="aapl", resolved_scenarios=resolved, today=TODAY, entry_price=100.0,
        contracts=1, rate=0.04, dividend_yield=0.0, price_range_pct=0.20,
        price_steps=21, date_steps=5,
    )
    assert resp["ticker"] == "AAPL"
    assert resp["csv"].startswith("scenario_id,strike,expiration")
    assert resp["row_count"] == 21 * 5  # only the good scenario contributed rows
    assert len(resp["scenarios"]) == 2
    assert resp["scenarios"][0]["label"] == "AAPL 105C 2026-02-10"
    assert resp["scenarios"][1]["error"]
    assert "render_hint" in resp and "disclaimer" in resp
