"""Risk/reward and spread engine for defined-risk long-call structures.

Massive/Polygon snapshots provide bid, ask, strike, and premium but not payoff-ratio
screening. This module fills that gap for asymmetric long-call research: spread
discipline, breakeven, payoff ratio at a target underlying, and Black-Scholes
fallback when snapshot greeks/IV are null.
"""

from __future__ import annotations

import math
from typing import Any

SPREAD_TARGET = 0.07
SPREAD_MAX = 0.10
RR_FLOOR = 3.0


def _round(x: float | None, n: int = 2) -> float | None:
    return None if x is None else round(x, n)


def spread_pct(bid: float | None, ask: float | None) -> float | None:
    """Bid/ask spread as a fraction of the mid. None if quotes missing."""
    if bid is None or ask is None:
        return None
    mid = (bid + ask) / 2.0
    if mid <= 0:
        return None
    return (ask - bid) / mid


def _flags(
    sp: float | None,
    spread_max: float,
    rr: float | None,
    rr_floor: float,
) -> str:
    out: list[str] = []
    if sp is None:
        out.append("no quotes -> spread discipline NOT checked (snapshot bid/ask missing?)")
    elif sp > spread_max:
        out.append(
            f"SPREAD {sp * 100:.1f}% > {spread_max * 100:.0f}% ceiling -> disqualify, not a nuisance"
        )
    if rr is None:
        out.append("entry premium <= 0, cannot compute payoff ratio")
    elif rr < rr_floor:
        out.append(f"payoff {rr:.1f}:1 < {rr_floor:.0f}:1 floor -> asymmetry too thin")
    if not out:
        out.append("clears spread + payoff floors")
    return "; ".join(out)


def long_call(
    entry: float,
    strike: float,
    target: float,
    bid: float | None = None,
    ask: float | None = None,
    *,
    spread_max: float = SPREAD_MAX,
    rr_floor: float = RR_FLOOR,
    label: str | None = None,
) -> dict[str, Any]:
    """Defined-risk long call economics (per-share; multiply by 100 for per-contract)."""
    cost = entry
    breakeven = strike + entry
    intrinsic_at_target = max(target - strike, 0.0)
    profit_per_share = intrinsic_at_target - cost
    rr = (profit_per_share / cost) if cost > 0 else None
    sp = spread_pct(bid, ask)

    spread_ok = sp is not None and sp <= spread_max
    rr_ok = rr is not None and rr >= rr_floor

    return {
        "label": label,
        "entry_premium": _round(cost),
        "strike": _round(strike),
        "target_underlying": _round(target),
        "breakeven": _round(breakeven),
        "max_loss_per_contract": _round(cost * 100, 2),
        "value_at_target_per_contract": _round(intrinsic_at_target * 100, 2),
        "profit_at_target_per_contract": _round(profit_per_share * 100, 2),
        "payoff_ratio_at_target": _round(rr, 2),
        "spread_pct": None if sp is None else _round(sp * 100, 1),
        "spread_ok": spread_ok,
        "rr_ok": rr_ok,
        "tradeable": bool(spread_ok and rr_ok),
        "notes": _flags(sp, spread_max, rr, rr_floor),
    }


def analyze_long_call_batch(
    legs: list[dict[str, Any]],
    *,
    spread_max: float = SPREAD_MAX,
    rr_floor: float = RR_FLOOR,
) -> dict[str, Any]:
    """Screen multiple long-call legs; returns per-leg results and aggregate pass/fail."""
    results: list[dict[str, Any]] = []
    all_ok = True
    for leg in legs:
        result = long_call(
            entry=float(leg["entry"]),
            strike=float(leg["strike"]),
            target=float(leg["target"]),
            bid=leg.get("bid"),
            ask=leg.get("ask"),
            spread_max=spread_max,
            rr_floor=rr_floor,
            label=leg.get("label"),
        )
        results.append(result)
        all_ok = all_ok and result["tradeable"]

    return {
        "count": len(results),
        "all_tradeable": all_ok,
        "spread_target_pct": _round(SPREAD_TARGET * 100, 1),
        "spread_max_pct": _round(spread_max * 100, 1),
        "rr_floor": rr_floor,
        "legs": results,
    }


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_call(
    spot: float,
    strike: float,
    dte_days: float,
    iv: float,
    rate: float = 0.04,
    div_yield: float = 0.0,
) -> dict[str, float | None] | None:
    """Black-Scholes call price and greeks. iv is decimal (e.g. 0.30)."""
    t = max(dte_days, 1) / 365.0
    if iv <= 0 or spot <= 0 or strike <= 0:
        return None
    d1 = (math.log(spot / strike) + (rate - div_yield + 0.5 * iv * iv) * t) / (iv * math.sqrt(t))
    d2 = d1 - iv * math.sqrt(t)
    disc_q = math.exp(-div_yield * t)
    disc_r = math.exp(-rate * t)
    price = spot * disc_q * _norm_cdf(d1) - strike * disc_r * _norm_cdf(d2)
    delta = disc_q * _norm_cdf(d1)
    gamma = disc_q * _norm_pdf(d1) / (spot * iv * math.sqrt(t))
    vega = spot * disc_q * _norm_pdf(d1) * math.sqrt(t) / 100.0
    theta = (
        -(spot * disc_q * _norm_pdf(d1) * iv) / (2 * math.sqrt(t))
        - rate * strike * disc_r * _norm_cdf(d2)
        + div_yield * spot * disc_q * _norm_cdf(d1)
    ) / 365.0
    return {
        "price": _round(price, 3),
        "delta": _round(delta, 4),
        "gamma": _round(gamma, 5),
        "vega": _round(vega, 4),
        "theta": _round(theta, 4),
    }


def implied_vol(
    market_price: float,
    spot: float,
    strike: float,
    dte_days: float,
    rate: float = 0.04,
    div_yield: float = 0.0,
) -> float | None:
    """Solve IV from a call mid price via bisection. Returns decimal or None."""
    lo, hi = 1e-4, 5.0

    def f(vol: float) -> float:
        result = bs_call(spot, strike, dte_days, vol, rate, div_yield)
        if result is None or result["price"] is None:
            return float("inf")
        return result["price"] - market_price

    if f(lo) > 0:
        return None
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if f(mid) > 0:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-5:
            break
    return _round((lo + hi) / 2.0, 4)


def black_scholes_call_analysis(
    spot: float,
    strike: float,
    dte_days: float,
    *,
    iv: float | None = None,
    market_price: float | None = None,
    rate: float = 0.04,
    div_yield: float = 0.0,
) -> dict[str, Any]:
    """Return BS greeks from IV, or solve IV from market price then return greeks."""
    if market_price is not None:
        solved_iv = implied_vol(market_price, spot, strike, dte_days, rate, div_yield)
        if solved_iv is None:
            return {
                "spot": spot,
                "strike": strike,
                "dte_days": dte_days,
                "implied_vol": None,
                "greeks": None,
                "notes": "could not solve implied vol from market price",
            }
        greeks = bs_call(spot, strike, dte_days, solved_iv, rate, div_yield)
        return {
            "spot": spot,
            "strike": strike,
            "dte_days": dte_days,
            "market_price": market_price,
            "implied_vol": solved_iv,
            "greeks": greeks,
            "notes": "IV solved from market price; use when snapshot greeks/IV are null",
        }

    if iv is None:
        return {
            "spot": spot,
            "strike": strike,
            "dte_days": dte_days,
            "implied_vol": None,
            "greeks": None,
            "notes": "provide iv or market_price",
        }

    return {
        "spot": spot,
        "strike": strike,
        "dte_days": dte_days,
        "iv": iv,
        "greeks": bs_call(spot, strike, dte_days, iv, rate, div_yield),
        "notes": "greeks from supplied IV",
    }
