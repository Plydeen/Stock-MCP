"""Pure helpers for Massive options data: OCC tickers, snapshot flattening, CSV.

No network calls here, so everything is unit-testable. The MCP tools in
:mod:`app.mcp_server` fetch from :mod:`app.massive_rest` and shape results with
these functions.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# O:AAPL261218C00290000 -> underlying, yymmdd, C/P, strike*1000 (8 digits).
# Underlyings can contain digits (e.g. adjusted contracts like "AAPL1").
_OCC_RE = re.compile(r"^(?:O:)?([A-Z0-9.]{1,6})(\d{6})([CP])(\d{8})$")

CHAIN_COLUMNS = [
    "ticker",
    "contract_type",
    "expiration_date",
    "dte",
    "strike",
    "bid",
    "ask",
    "mid",
    "spread_pct",
    "last",
    "mark",
    "mark_source",
    "change_pct",
    "volume",
    "open_interest",
    "implied_volatility",
    "delta",
    "gamma",
    "theta",
    "vega",
    "break_even_price",
    "underlying_price",
]

TRADE_COLUMNS = ["datetime", "price", "size", "exchange", "conditions"]
QUOTE_COLUMNS = ["datetime", "bid", "bid_size", "ask", "ask_size", "mid", "spread", "bid_exchange", "ask_exchange"]


def parse_occ_ticker(options_ticker: str) -> dict[str, Any]:
    """Split an OCC/Massive option ticker into its parts.

    Raises ValueError for anything that is not an option ticker.
    """
    raw = options_ticker.strip().upper()
    match = _OCC_RE.match(raw)
    if not match:
        raise ValueError(
            f"'{options_ticker}' is not an option ticker; expected e.g. O:AAPL261218C00290000"
        )
    underlying, yymmdd, cp, strike_raw = match.groups()
    expiration = datetime.strptime(yymmdd, "%y%m%d").date()
    return {
        "ticker": f"O:{underlying}{yymmdd}{cp}{strike_raw}",
        "underlying": underlying,
        "expiration_date": expiration.isoformat(),
        "contract_type": "call" if cp == "C" else "put",
        "strike": int(strike_raw) / 1000.0,
    }


def normalize_option_ticker(options_ticker: str) -> str:
    """Upper-case and ensure the `O:` prefix Massive expects."""
    return parse_occ_ticker(options_ticker)["ticker"]


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pos(value: Any) -> float | None:
    """Positive float or None (Massive uses 0 for 'no data' in several fields)."""
    num = _num(value)
    return num if num is not None and num > 0 else None


def _r(value: float | None, n: int) -> float | None:
    return None if value is None else round(value, n)


def ns_to_et_iso(timestamp_ns: Any) -> str | None:
    if timestamp_ns in (None, ""):
        return None
    dt = datetime.fromtimestamp(int(timestamp_ns) / 1_000_000_000.0, tz=timezone.utc).astimezone(ET)
    return dt.isoformat()


def ms_to_et_iso(timestamp_ms: Any) -> str | None:
    if timestamp_ms in (None, ""):
        return None
    dt = datetime.fromtimestamp(float(timestamp_ms) / 1000.0, tz=timezone.utc).astimezone(ET)
    return dt.isoformat()


def snapshot_quote(snapshot: dict[str, Any]) -> dict[str, float | None]:
    """Extract bid / ask / mid / last / mark from an option snapshot.

    `mark` is the best available per-share price, in priority order:
    quote midpoint -> fair market value -> last trade -> session close ->
    previous close. `mark_source` says which one was used. Plans without quote
    entitlement omit `last_quote`, so mark falls back to trade-based prices.
    """
    quote = snapshot.get("last_quote") or {}
    trade = snapshot.get("last_trade") or {}
    day = snapshot.get("day") or snapshot.get("session") or {}

    bid = _pos(quote.get("bid"))
    ask = _pos(quote.get("ask"))
    mid = _pos(quote.get("midpoint"))
    if mid is None and bid is not None and ask is not None:
        mid = (bid + ask) / 2.0
    spread = (ask - bid) / mid if (bid is not None and ask is not None and mid) else None

    last = _pos(trade.get("price"))
    close = _pos(day.get("close"))
    prev_close = _pos(day.get("previous_close"))
    fmv = _pos(snapshot.get("fmv"))

    mark, mark_source = None, None
    for value, source in (
        (mid, "quote_mid"),
        (fmv, "fmv"),
        (last, "last_trade"),
        (close, "session_close"),
        (prev_close, "previous_close"),
    ):
        if value is not None:
            mark, mark_source = value, source
            break

    return {
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "spread_pct": spread,
        "last": last if last is not None else close,
        "mark": mark,
        "mark_source": mark_source,
    }


def flatten_option_snapshot(snapshot: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    """One compact, flat row per contract snapshot (per-share prices)."""
    details = snapshot.get("details") or {}
    greeks = snapshot.get("greeks") or {}
    day = snapshot.get("day") or snapshot.get("session") or {}
    underlying = snapshot.get("underlying_asset") or {}
    quote = snapshot_quote(snapshot)

    ticker = details.get("ticker") or snapshot.get("ticker")
    expiration = details.get("expiration_date")
    dte = None
    if expiration:
        try:
            dte = (date.fromisoformat(expiration) - (today or date.today())).days
        except ValueError:
            dte = None

    return {
        "ticker": ticker,
        "contract_type": details.get("contract_type"),
        "expiration_date": expiration,
        "dte": dte,
        "strike": _num(details.get("strike_price")),
        "bid": _r(quote["bid"], 4),
        "ask": _r(quote["ask"], 4),
        "mid": _r(quote["mid"], 4),
        "spread_pct": _r(None if quote["spread_pct"] is None else quote["spread_pct"] * 100, 2),
        "last": _r(quote["last"], 4),
        "mark": _r(quote["mark"], 4),
        "mark_source": quote["mark_source"],
        "change_pct": _r(_num(day.get("change_percent")), 3),
        "volume": _num(day.get("volume")),
        "open_interest": _num(snapshot.get("open_interest")),
        "implied_volatility": _r(_pos(snapshot.get("implied_volatility")), 4),
        "delta": _r(_num(greeks.get("delta")), 4),
        "gamma": _r(_num(greeks.get("gamma")), 5),
        "theta": _r(_num(greeks.get("theta")), 4),
        "vega": _r(_num(greeks.get("vega")), 4),
        "break_even_price": _r(_num(snapshot.get("break_even_price")), 4),
        "underlying_price": _r(_pos(underlying.get("price") or underlying.get("value")), 4),
    }


def rows_to_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(["" if row.get(col) is None else row.get(col) for col in columns])
    return buffer.getvalue()


def summarize_chain(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate stats: put/call volume + OI ratios, expirations, strike range."""
    calls = [r for r in rows if r.get("contract_type") == "call"]
    puts = [r for r in rows if r.get("contract_type") == "put"]

    def total(items: list[dict[str, Any]], key: str) -> float:
        return sum(r.get(key) or 0 for r in items)

    call_vol, put_vol = total(calls, "volume"), total(puts, "volume")
    call_oi, put_oi = total(calls, "open_interest"), total(puts, "open_interest")
    strikes = [r["strike"] for r in rows if r.get("strike") is not None]
    return {
        "contracts": len(rows),
        "calls": len(calls),
        "puts": len(puts),
        "expirations": sorted({r["expiration_date"] for r in rows if r.get("expiration_date")}),
        "strike_range": [min(strikes), max(strikes)] if strikes else None,
        "call_volume": call_vol,
        "put_volume": put_vol,
        "put_call_volume_ratio": _r(put_vol / call_vol, 3) if call_vol else None,
        "call_open_interest": call_oi,
        "put_open_interest": put_oi,
        "put_call_oi_ratio": _r(put_oi / call_oi, 3) if call_oi else None,
        "has_quotes": any(r.get("bid") is not None for r in rows),
        "has_greeks": any(r.get("delta") is not None for r in rows),
    }


def trades_to_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for t in trades:
        rows.append(
            {
                "datetime": ns_to_et_iso(t.get("sip_timestamp") or t.get("participant_timestamp")),
                "price": t.get("price"),
                "size": t.get("size"),
                "exchange": t.get("exchange"),
                "conditions": " ".join(str(c) for c in (t.get("conditions") or [])),
            }
        )
    return rows


def quotes_to_rows(quotes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for q in quotes:
        bid, ask = _num(q.get("bid_price")), _num(q.get("ask_price"))
        mid = (bid + ask) / 2.0 if bid is not None and ask is not None else None
        rows.append(
            {
                "datetime": ns_to_et_iso(q.get("sip_timestamp") or q.get("participant_timestamp")),
                "bid": bid,
                "bid_size": q.get("bid_size"),
                "ask": ask,
                "ask_size": q.get("ask_size"),
                "mid": _r(mid, 4),
                "spread": _r(ask - bid, 4) if mid is not None else None,
                "bid_exchange": q.get("bid_exchange"),
                "ask_exchange": q.get("ask_exchange"),
            }
        )
    return rows


def indicator_columns(indicator: str) -> list[str]:
    return ["datetime", "value", "signal", "histogram"] if indicator == "macd" else ["datetime", "value"]


def indicator_to_rows(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Indicator values, sorted oldest-first for charting."""
    rows = [
        {
            "datetime": ms_to_et_iso(v.get("timestamp")),
            "value": v.get("value"),
            "signal": v.get("signal"),
            "histogram": v.get("histogram"),
            "_ts": v.get("timestamp") or 0,
        }
        for v in values
    ]
    rows.sort(key=lambda r: r["_ts"])
    for r in rows:
        r.pop("_ts")
    return rows


def snapshot_premium_and_iv(snapshot: dict[str, Any], *, side: str) -> dict[str, Any]:
    """Pick a premium and IV from a contract snapshot.

    `side="sell"` prefers the bid (what a writer collects); `side="buy"` prefers
    the ask (what a buyer pays). Without quotes it falls back to `mark`.
    """
    quote = snapshot_quote(snapshot)
    premium, source = None, None
    preferred = quote["bid"] if side == "sell" else quote["ask"]
    if preferred is not None:
        premium, source = preferred, f"snapshot_{'bid' if side == 'sell' else 'ask'}"
    elif quote["mark"] is not None:
        premium, source = quote["mark"], f"snapshot_{quote['mark_source']}"

    iv = _pos(snapshot.get("implied_volatility"))
    return {
        "premium": premium,
        "premium_source": source,
        "iv": iv,
        "bid": quote["bid"],
        "ask": quote["ask"],
        "has_quote": quote["bid"] is not None and quote["ask"] is not None,
    }
