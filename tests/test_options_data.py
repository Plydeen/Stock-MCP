"""Unit tests for options snapshot parsing and the snapshot-backed MCP tools."""

from datetime import date, timedelta

import pytest

from app import mcp_server
from app.massive_rest import MassiveAPIError, _clean_params
from app.options_data import (
    CHAIN_COLUMNS,
    flatten_option_snapshot,
    indicator_to_rows,
    normalize_option_ticker,
    parse_occ_ticker,
    quotes_to_rows,
    rows_to_csv,
    snapshot_premium_and_iv,
    snapshot_quote,
    summarize_chain,
    trades_to_rows,
)

TODAY = date(2026, 11, 4)
NEAR_EXPIRY = (date.today() + timedelta(days=60)).isoformat()


def _snap(strike=300.0, ctype="call", exp="2026-12-18", *, quote=None, close=55.83, oi=21702, iv=0.2866):
    letter = "C" if ctype == "call" else "P"
    snap = {
        "day": {"close": close, "previous_close": 35.92, "change_percent": 55.4, "volume": 122},
        "details": {
            "contract_type": ctype,
            "expiration_date": exp,
            "strike_price": strike,
            "ticker": f"O:AAPL261218{letter}{int(strike * 1000):08d}",
        },
        "greeks": {"delta": 0.9578, "gamma": 0.0025, "theta": -0.0629, "vega": 0.1074},
        "implied_volatility": iv,
        "open_interest": oi,
        "underlying_asset": {"ticker": "AAPL"},
    }
    if quote:
        snap["last_quote"] = quote
    return snap


# --- OCC tickers -----------------------------------------------------------


def test_parse_occ_ticker_roundtrip():
    parts = parse_occ_ticker("O:AAPL261218C00290000")
    assert parts == {
        "ticker": "O:AAPL261218C00290000",
        "underlying": "AAPL",
        "expiration_date": "2026-12-18",
        "contract_type": "call",
        "strike": 290.0,
    }


def test_parse_occ_ticker_adds_prefix_and_handles_puts_and_decimals():
    parts = parse_occ_ticker("spy261218p00592500")
    assert parts["ticker"] == "O:SPY261218P00592500"
    assert parts["contract_type"] == "put"
    assert parts["strike"] == 592.5


def test_parse_occ_ticker_rejects_stock():
    with pytest.raises(ValueError):
        parse_occ_ticker("AAPL")


def test_normalize_ticker_passes_stocks_through():
    assert mcp_server._normalize_ticker("aapl") == "AAPL"
    assert mcp_server._normalize_ticker("AAPL261218C00290000") == "O:AAPL261218C00290000"
    assert normalize_option_ticker("O:aapl261218c00290000") == "O:AAPL261218C00290000"


# --- snapshot parsing ------------------------------------------------------


def test_snapshot_quote_falls_back_to_close_without_quotes():
    q = snapshot_quote(_snap())
    assert q["bid"] is None and q["ask"] is None
    assert q["mark"] == 55.83
    assert q["mark_source"] == "session_close"


def test_snapshot_quote_uses_previous_close_when_session_empty():
    snap = _snap(close=0)
    assert snapshot_quote(snap)["mark_source"] == "previous_close"
    assert snapshot_quote(snap)["mark"] == 35.92


def test_snapshot_quote_prefers_mid_and_computes_spread():
    q = snapshot_quote(_snap(quote={"bid": 9.5, "ask": 10.5}))
    assert q["mid"] == 10.0
    assert q["mark_source"] == "quote_mid"
    assert q["spread_pct"] == pytest.approx(0.1)


def test_flatten_snapshot_row():
    row = flatten_option_snapshot(_snap(), today=TODAY)
    assert row["ticker"] == "O:AAPL261218C00300000"
    assert row["dte"] == 44
    assert row["strike"] == 300.0
    assert row["implied_volatility"] == 0.2866
    assert row["delta"] == 0.9578
    assert row["open_interest"] == 21702
    assert set(CHAIN_COLUMNS) <= set(row)


def test_flatten_handles_unified_snapshot_shape():
    snap = _snap()
    snap["session"] = snap.pop("day")
    assert flatten_option_snapshot(snap, today=TODAY)["mark"] == 55.83


def test_summarize_chain_ratios():
    rows = [
        flatten_option_snapshot(_snap(300, "call", oi=100), today=TODAY),
        flatten_option_snapshot(_snap(300, "put", oi=50), today=TODAY),
    ]
    summary = summarize_chain(rows)
    assert summary["calls"] == 1 and summary["puts"] == 1
    assert summary["put_call_oi_ratio"] == 0.5
    assert summary["put_call_volume_ratio"] == 1.0
    assert summary["has_greeks"] is True
    assert summary["has_quotes"] is False


def test_chain_csv_header_and_blank_nulls():
    csv_text = rows_to_csv([flatten_option_snapshot(_snap(), today=TODAY)], CHAIN_COLUMNS)
    header, line = csv_text.strip().split("\n")
    assert header.split(",") == CHAIN_COLUMNS
    assert ",," in line  # missing bid/ask render as empty cells


def test_snapshot_premium_side_selection():
    quoted = _snap(quote={"bid": 9.5, "ask": 10.5})
    assert snapshot_premium_and_iv(quoted, side="sell")["premium"] == 9.5
    assert snapshot_premium_and_iv(quoted, side="sell")["premium_source"] == "snapshot_bid"
    assert snapshot_premium_and_iv(quoted, side="buy")["premium"] == 10.5
    unquoted = snapshot_premium_and_iv(_snap(), side="sell")
    assert unquoted["premium_source"] == "snapshot_session_close"
    assert unquoted["iv"] == 0.2866
    assert snapshot_premium_and_iv(_snap(iv=0), side="sell")["iv"] is None


# --- trades / quotes / indicators -----------------------------------------


def test_trades_and_quotes_rows():
    trades = trades_to_rows([{"sip_timestamp": 1793806382556000000, "price": 5.1, "size": 3, "exchange": 302, "conditions": [209, 219]}])
    assert trades[0]["price"] == 5.1
    assert trades[0]["conditions"] == "209 219"
    assert trades[0]["datetime"].startswith("2026-11-04")

    quotes = quotes_to_rows([{"sip_timestamp": 1793806382556000000, "bid_price": 5.0, "ask_price": 5.2, "bid_size": 10, "ask_size": 12}])
    assert quotes[0]["mid"] == 5.1
    assert quotes[0]["spread"] == 0.2


def test_indicator_rows_sorted_oldest_first():
    rows = indicator_to_rows(
        [
            {"timestamp": 1793768400000, "value": 57.6},
            {"timestamp": 1793682000000, "value": 39.1},
        ]
    )
    assert [r["value"] for r in rows] == [39.1, 57.6]


def test_clean_params_drops_none_and_lowercases_bools():
    assert _clean_params({"a": None, "b": True, "c": 5}) == {"b": "true", "c": 5}


# --- tools against a fake client ------------------------------------------


class FakeClient:
    def __init__(self, chain=None, contract_snapshot=None, snapshot_error=False):
        self.chain = chain or []
        self.contract_snapshot = contract_snapshot
        self.snapshot_error = snapshot_error
        self.calls: list[tuple] = []

    async def get_options_chain_snapshot(self, underlying, **kwargs):
        self.calls.append(("chain", underlying, kwargs))
        return self.chain[: kwargs.get("max_results", 250)]

    async def get_option_contract_snapshot(self, underlying, ticker):
        self.calls.append(("contract", underlying, ticker))
        if self.snapshot_error:
            raise MassiveAPIError("NOT_AUTHORIZED", status_code=403)
        return self.contract_snapshot

    async def get_stock_snapshot(self, ticker):
        return {"day": {"c": 300.0}}

    async def get_ticker_aggs(self, *args, **kwargs):
        return [{"c": 7.0, "t": 0}]


@pytest.fixture
def fake(monkeypatch):
    def install(client):
        monkeypatch.setattr(mcp_server, "get_rest_client", lambda: client)
        return client

    return install


async def test_chain_snapshot_tool_rows_csv_and_truncation(fake):
    chain = [_snap(s) for s in (310.0, 300.0, 290.0)]
    client = fake(FakeClient(chain=chain))

    out = await mcp_server.get_options_chain_snapshot("aapl", contract_type="call", max_contracts=2)
    assert out["count"] == 2 and out["truncated"] is True
    assert [r["strike"] for r in out["contracts"]] == [300.0, 310.0]  # sorted by strike
    assert "quote_note" in out
    assert client.calls[0][2]["contract_type"] == "call"
    assert client.calls[0][2]["max_results"] == 3

    out_csv = await mcp_server.get_options_chain_snapshot("AAPL", output="csv")
    assert out_csv["csv"].startswith(",".join(CHAIN_COLUMNS))
    assert "contracts" not in out_csv


async def test_contract_snapshot_tool_derives_underlying(fake):
    client = fake(FakeClient(contract_snapshot=_snap()))
    out = await mcp_server.get_option_contract_snapshot("AAPL261218C00300000")
    assert client.calls[0] == ("contract", "AAPL", "O:AAPL261218C00300000")
    assert out["summary"]["implied_volatility"] == 0.2866


async def test_screen_long_calls_from_chain_sorts_and_filters(fake):
    chain = [
        _snap(290.0, quote={"bid": 1.9, "ask": 2.0}, oi=500),
        _snap(300.0, quote={"bid": 0.95, "ask": 1.0}, oi=500),
        _snap(320.0, quote={"bid": 0.1, "ask": 0.5}, oi=5),  # filtered by OI
    ]
    fake(FakeClient(chain=chain))
    out = await mcp_server.screen_long_calls_from_chain("AAPL", target=310.0, min_open_interest=100)
    assert out["screened"] == 2 and out["skipped"] == 1
    tickers = [leg["ticker"] for leg in out["legs"]]
    # At target 310: 300C pays (10 - 1.0)/1.0 = 9.0:1; 290C pays (20 - 2.0)/2.0 = 9.0:1.
    assert set(tickers) == {"O:AAPL261218C00290000", "O:AAPL261218C00300000"}
    assert [leg["payoff_ratio_at_target"] for leg in out["legs"]] == [9.0, 9.0]
    assert all(leg["entry_source"] == "snapshot_ask" for leg in out["legs"])
    assert out["quotes_available"] is True
    assert all(leg["spread_ok"] for leg in out["legs"])


async def test_covered_call_uses_snapshot_bid_and_iv(fake):
    fake(FakeClient(contract_snapshot=_snap(320.0, quote={"bid": 6.0, "ask": 6.4}, iv=0.28)))
    out = await mcp_server.covered_call_sim(
        "AAPL",
        [mcp_server.Scenario(strike=320.0, expiration=NEAR_EXPIRY)],
        price_steps=3,
        date_steps=2,
    )
    assumptions = out["scenarios"][0]["assumptions"]
    assert assumptions["premium"] == 6.0
    assert assumptions["premium_source"] == "snapshot_bid"
    assert assumptions["iv"] == 0.28
    assert assumptions["iv_source"] == "snapshot"
    assert assumptions["iv_quality"] == "market"
    assert "premium_note" not in out


async def test_covered_call_falls_back_to_last_trade_when_snapshot_denied(fake):
    fake(FakeClient(snapshot_error=True))
    out = await mcp_server.covered_call_sim(
        "AAPL",
        [mcp_server.Scenario(strike=320.0, expiration=NEAR_EXPIRY)],
        price_steps=3,
        date_steps=2,
    )
    assumptions = out["scenarios"][0]["assumptions"]
    assert assumptions["premium"] == 7.0
    assert assumptions["premium_source"] == "last_trade"
    assert assumptions["iv_quality"] == "approximate"
    assert "premium_note" in out
