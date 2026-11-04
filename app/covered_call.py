"""Covered-call scenario engine.

Computes covered-call profit/loss across a grid of underlying prices x evaluation
dates, for one or more contract scenarios, and returns chart-ready long-format CSV
plus a per-scenario metrics/assumptions block. Compute only -- the calling agent
renders the charts.

The Black-Scholes engine (``bs_call``) and the implied-vol solver (``implied_vol``)
are reused from :mod:`app.risk_reward`; this module never calls the MCP per cell.
Intermediate-date pricing (tau > 0) uses BS; at the expiration eval date (tau == 0)
it uses intrinsic value directly, avoiding a divide-by-zero in sigma * sqrt(tau).

Pure stdlib (no numpy) -- a grid capped at ``MAX_CELLS`` is trivial in Python.
"""

from __future__ import annotations

import csv
import io
import math
from datetime import date, timedelta
from typing import Any

from app.risk_reward import _norm_cdf, bs_call, implied_vol

# Hard cap on total grid cells (scenarios x price_steps x date_steps) to guard the
# calling agent's context budget. See build_plan section 9.
MAX_CELLS = 1500

CSV_COLUMNS = [
    "scenario_id",
    "strike",
    "expiration",
    "eval_date",
    "dte_at_eval",
    "underlying_price",
    "call_value",
    "pl_per_share",
    "pl_total",
    "pct_return",
]


class ScenarioError(Exception):
    """Raised when a single scenario cannot be computed. Degrade per-scenario."""


def occ_ticker(underlying: str, expiration: date, strike: float, contract_type: str = "C") -> str:
    """Build a Polygon/OCC option ticker, e.g. O:AAPL260821C00320000.

    Strike is encoded as an 8-digit integer of (strike * 1000).
    """
    yymmdd = expiration.strftime("%y%m%d")
    strike_int = round(strike * 1000)
    return f"O:{underlying.upper()}{yymmdd}{contract_type.upper()}{strike_int:08d}"


def price_grid(center: float, range_pct: float, steps: int) -> list[float]:
    """Underlying prices spanning center +/- range_pct. Odd steps includes center."""
    if steps < 1:
        raise ValueError("price_steps must be >= 1")
    if steps == 1:
        return [center]
    lo = center * (1.0 - range_pct)
    hi = center * (1.0 + range_pct)
    step = (hi - lo) / (steps - 1)
    return [lo + step * i for i in range(steps)]


def eval_date_offsets(dte: int, steps: int) -> list[int]:
    """Day offsets from today (0) to expiration (dte), inclusive.

    The last offset always equals ``dte`` so the final eval date lands exactly on
    expiration (tau == 0 -> intrinsic payoff line).
    """
    if steps < 1:
        raise ValueError("date_steps must be >= 1")
    if dte <= 0:
        return [0]
    if steps == 1:
        return [dte]
    offsets = []
    for i in range(steps):
        frac = i / (steps - 1)
        offsets.append(round(frac * dte))
    # De-duplicate while preserving order (small DTE + many steps can collide),
    # and guarantee endpoints.
    seen: set[int] = set()
    unique: list[int] = []
    for off in offsets:
        if off not in seen:
            seen.add(off)
            unique.append(off)
    if unique[-1] != dte:
        unique.append(dte)
    return unique


def _call_value(spot: float, strike: float, dte_at_eval: int, sigma: float, rate: float, q: float) -> float:
    """Call value at an eval date: intrinsic at expiry, else Black-Scholes price."""
    if dte_at_eval <= 0:
        return max(0.0, spot - strike)
    greeks = bs_call(spot, strike, dte_at_eval, sigma, rate, q)
    if greeks is None or greeks.get("price") is None:
        return max(0.0, spot - strike)
    return float(greeks["price"])


def _d1(spot: float, strike: float, t_years: float, sigma: float, rate: float, q: float) -> float:
    return (math.log(spot / strike) + (rate - q + 0.5 * sigma * sigma) * t_years) / (sigma * math.sqrt(t_years))


def scenario_metrics(
    *,
    entry_price: float,
    strike: float,
    premium: float,
    sigma: float,
    dte: int,
    rate: float,
    dividend_yield: float,
) -> dict[str, Any]:
    """Per-scenario covered-call metrics (build_plan section 6).

    All probability metrics are Black-Scholes model-dependent; label as such upstream.
    """
    net_cost = entry_price - premium
    breakeven = entry_price - premium
    max_profit = (strike - entry_price) + premium
    max_loss = premium - entry_price  # S -> 0, still holding worthless stock
    static_return = (premium / net_cost) if net_cost != 0 else None
    if_called_return = ((premium + strike - entry_price) / net_cost) if net_cost != 0 else None
    downside_cushion = (premium / entry_price) if entry_price != 0 else None

    ann = (365.0 / dte) if dte > 0 else None
    static_ann = static_return * ann if (static_return is not None and ann is not None) else None
    if_called_ann = if_called_return * ann if (if_called_return is not None and ann is not None) else None

    prob_profit = None
    prob_assignment = None
    t_years = dte / 365.0
    if sigma > 0 and t_years > 0:
        if breakeven > 0:
            d_be = (
                math.log(entry_price / breakeven)
                + (rate - dividend_yield - 0.5 * sigma * sigma) * t_years
            ) / (sigma * math.sqrt(t_years))
            prob_profit = _norm_cdf(d_be)
        prob_assignment = _norm_cdf(_d1(entry_price, strike, t_years, sigma, rate, dividend_yield))

    # Early-assignment / ex-dividend risk: call ITM at entry, a dividend is paid,
    # and the remaining extrinsic value is below the expected dividend before expiry.
    assignment_risk_flag = False
    if entry_price > strike and dividend_yield > 0 and dte > 0:
        call_now = _call_value(entry_price, strike, dte, sigma, rate, dividend_yield)
        extrinsic = call_now - max(0.0, entry_price - strike)
        expected_div = entry_price * dividend_yield * t_years
        assignment_risk_flag = extrinsic < expected_div

    def r4(x: float | None) -> float | None:
        return None if x is None else round(x, 4)

    def r2(x: float | None) -> float | None:
        return None if x is None else round(x, 2)

    return {
        "breakeven": r2(breakeven),
        "max_profit": r2(max_profit),
        "max_loss": r2(max_loss),
        "static_return": r4(static_return),
        "if_called_return": r4(if_called_return),
        "static_return_annualized": r4(static_ann),
        "if_called_return_annualized": r4(if_called_ann),
        "downside_cushion": r4(downside_cushion),
        "prob_profit": r4(prob_profit),
        "prob_assignment": r4(prob_assignment),
        "assignment_risk_flag": assignment_risk_flag,
    }


def scenario_rows(
    *,
    scenario_id: int,
    strike: float,
    expiration: date,
    today: date,
    entry_price: float,
    premium: float,
    sigma: float,
    dte: int,
    rate: float,
    dividend_yield: float,
    shares_per_contract: int,
    contracts: int,
    price_range_pct: float,
    price_steps: int,
    date_steps: int,
) -> list[list[Any]]:
    """Long-format grid rows for one scenario (one row per price x eval-date cell)."""
    prices = price_grid(entry_price, price_range_pct, price_steps)
    offsets = eval_date_offsets(dte, date_steps)
    net_cost = entry_price - premium
    rows: list[list[Any]] = []
    for offset in offsets:
        eval_date = today + timedelta(days=offset)
        dte_at_eval = dte - offset
        for spot in prices:
            call_value = _call_value(spot, strike, dte_at_eval, sigma, rate, dividend_yield)
            stock_pl = spot - entry_price
            option_pl = premium - call_value
            pl_per_share = stock_pl + option_pl
            pl_total = pl_per_share * shares_per_contract * contracts
            pct_return = (pl_per_share / net_cost) if net_cost != 0 else None
            rows.append(
                [
                    scenario_id,
                    round(strike, 2),
                    expiration.isoformat(),
                    eval_date.isoformat(),
                    dte_at_eval,
                    round(spot, 2),
                    round(call_value, 2),
                    round(pl_per_share, 2),
                    round(pl_total, 2),
                    None if pct_return is None else round(pct_return, 4),
                ]
            )
    return rows


def rows_to_csv(rows: list[list[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    return buffer.getvalue()


def cell_count(num_scenarios: int, price_steps: int, date_steps: int) -> int:
    return num_scenarios * price_steps * date_steps


def solve_iv(
    *, premium: float, spot: float, strike: float, dte: int, rate: float, dividend_yield: float
) -> float | None:
    """Solve implied vol from a premium via the reused bisection solver."""
    return implied_vol(premium, spot, strike, dte, rate, dividend_yield)


def build_response(
    *,
    ticker: str,
    resolved_scenarios: list[dict[str, Any]],
    today: date,
    entry_price: float,
    contracts: int,
    rate: float,
    dividend_yield: float,
    price_range_pct: float,
    price_steps: int,
    date_steps: int,
) -> dict[str, Any]:
    """Assemble the full tool response from already-resolved scenarios.

    Each entry in ``resolved_scenarios`` is either an error stub
    (``{"scenario_id", "label", "error"}``) or a fully-resolved scenario with
    ``strike``, ``expiration`` (date), ``premium``, ``iv``, ``dte``,
    ``shares_per_contract`` and the ``*_source`` / ``iv_quality`` provenance fields.
    Failed scenarios are skipped in the CSV but still reported in ``scenarios``.
    """
    all_rows: list[list[Any]] = []
    scenario_blocks: list[dict[str, Any]] = []

    for res in resolved_scenarios:
        sid = res["scenario_id"]
        label = res.get("label")
        if res.get("error"):
            scenario_blocks.append({"scenario_id": sid, "label": label, "error": res["error"]})
            continue

        strike = res["strike"]
        expiration = res["expiration"]
        premium = res["premium"]
        sigma = res["iv"]
        dte = res["dte"]
        shares = res["shares_per_contract"]

        rows = scenario_rows(
            scenario_id=sid,
            strike=strike,
            expiration=expiration,
            today=today,
            entry_price=entry_price,
            premium=premium,
            sigma=sigma,
            dte=dte,
            rate=rate,
            dividend_yield=dividend_yield,
            shares_per_contract=shares,
            contracts=contracts,
            price_range_pct=price_range_pct,
            price_steps=price_steps,
            date_steps=date_steps,
        )
        all_rows.extend(rows)

        metrics = scenario_metrics(
            entry_price=entry_price,
            strike=strike,
            premium=premium,
            sigma=sigma,
            dte=dte,
            rate=rate,
            dividend_yield=dividend_yield,
        )
        scenario_blocks.append(
            {
                "scenario_id": sid,
                "label": label or f"{ticker.upper()} {strike:g}C {expiration.isoformat()}",
                "metrics": metrics,
                "assumptions": {
                    "entry_price": round(entry_price, 2),
                    "premium": round(premium, 4),
                    "premium_source": res.get("premium_source"),
                    "iv": round(sigma, 4),
                    "iv_source": res.get("iv_source"),
                    "iv_quality": res.get("iv_quality"),
                    "rate": rate,
                    "dividend_yield": dividend_yield,
                    "shares_per_contract": shares,
                    "contracts": contracts,
                    "dte": dte,
                },
            }
        )

    return {
        "ticker": ticker.upper(),
        "csv": rows_to_csv(all_rows),
        "row_count": len(all_rows),
        "scenarios": scenario_blocks,
        "render_hint": {
            "x": "underlying_price",
            "series": "eval_date",
            "facet": "scenario_id",
            "y": "pl_per_share",
            "suggested_charts": ["expiration_payoff", "time_decay_fan", "strike_comparison"],
        },
        "disclaimer": (
            "Scenario map, not a forecast. Black-Scholes prices European options; "
            "equity options are American and can be assigned early. IV is held "
            "constant across the grid (ignores skew, term structure, IV crush). "
            "Probabilities are model-dependent."
        ),
    }
