"""FastMCP tools for Massive market data research."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any, Literal

from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from app.auth import create_mcp
from app.config import get_settings
from app.covered_call import (
    MAX_CELLS,
    build_response as build_covered_call_response,
    cell_count,
    occ_ticker,
    solve_iv,
)
from app.csv_format import (
    build_csv_response,
    flat_file_row_to_chart_row,
    rest_aggs_to_rows,
)
from app.massive_flat import get_flat_client
from app.massive_rest import MassiveAPIError, get_rest_client
from app.options_data import (
    CHAIN_COLUMNS,
    ms_to_et_iso,
    ns_to_et_iso,
    QUOTE_COLUMNS,
    TRADE_COLUMNS,
    flatten_option_snapshot,
    indicator_columns,
    indicator_to_rows,
    normalize_option_ticker,
    parse_occ_ticker,
    quotes_to_rows,
    rows_to_csv as dict_rows_to_csv,
    snapshot_premium_and_iv,
    summarize_chain,
    trades_to_rows,
)
from app.risk_reward import (
    SPREAD_MAX,
    RR_FLOOR,
    analyze_long_call_batch,
    black_scholes_call_analysis,
    long_call,
)

mcp = create_mcp()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _normalize_ticker(ticker: str) -> str:
    """Upper-case a ticker; option tickers get the `O:` prefix if it was omitted."""
    try:
        return normalize_option_ticker(ticker)
    except ValueError:
        return ticker.strip().upper()


# Hard cap for chain pulls so one call cannot flood the agent's context.
MAX_CHAIN_CONTRACTS = 2500


@mcp.tool()
async def get_stock_bars_csv(
    ticker: str,
    from_date: str,
    to_date: str,
    timespan: Literal["minute", "hour", "day", "week", "month"] = "day",
    multiplier: int = 1,
    adjusted: bool = True,
) -> dict[str, Any]:
    """Return chart-ready OHLCV CSV for a stock ticker.

    Use this when you need time-series data to plot candlestick or line charts.
    Parse the `csv` field from the response. If `truncated` is true, narrow the
    date range or switch to a coarser timespan (for example day instead of minute).
    """

    settings = get_settings()
    client = get_rest_client()
    aggs = await client.get_ticker_aggs(
        ticker.upper(),
        multiplier,
        timespan,
        from_date,
        to_date,
        adjusted=adjusted,
    )
    rows = rest_aggs_to_rows(aggs)
    return build_csv_response(
        rows=rows,
        max_rows=settings.max_csv_rows,
        source="rest",
        ticker=ticker.upper(),
        date_from=from_date,
        date_to=to_date,
        fetched_at=_utc_now_iso(),
    )


@mcp.tool()
async def get_options_bars_csv(
    options_ticker: str,
    from_date: str,
    to_date: str,
    timespan: Literal["minute", "hour", "day", "week", "month"] = "day",
    multiplier: int = 1,
    adjusted: bool = True,
) -> dict[str, Any]:
    """Return chart-ready OHLCV CSV for an options contract ticker.

    Use `list_options_contracts` first to find the contract ticker (for example
    O:AAPL250620C00200000; the `O:` prefix is optional). Parse the `csv` field
    for charting. For indicator overlays use `get_technical_indicator_csv`.
    """

    settings = get_settings()
    client = get_rest_client()
    options_ticker = _normalize_ticker(options_ticker)
    aggs = await client.get_ticker_aggs(
        options_ticker,
        multiplier,
        timespan,
        from_date,
        to_date,
        adjusted=adjusted,
    )
    rows = rest_aggs_to_rows(aggs)
    return build_csv_response(
        rows=rows,
        max_rows=settings.max_csv_rows,
        source="rest",
        ticker=options_ticker.upper(),
        date_from=from_date,
        date_to=to_date,
        fetched_at=_utc_now_iso(),
    )


@mcp.tool()
async def get_flat_file_bars_csv(
    asset_class: Literal["stocks", "options"],
    dataset: Literal["day", "minute"],
    ticker: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Return chart-ready OHLCV CSV from Massive Flat Files (S3 bulk data).

    Best for longer historical ranges without many REST calls. Requires
    MASSIVE_S3_ACCESS_KEY and MASSIVE_S3_SECRET_KEY. Use `dataset=day` for
    multi-year charts; use `minute` for intraday history (narrow date ranges).
    """

    settings = get_settings()
    flat = get_flat_client()
    raw_rows, truncated = flat.collect_ticker_bars(
        asset_class=asset_class,
        dataset=dataset,
        ticker=ticker.upper(),
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        max_rows=settings.max_csv_rows,
    )
    chart_rows = []
    for row in raw_rows:
        mapped = flat_file_row_to_chart_row(row)
        if mapped:
            chart_rows.append(mapped)

    response = build_csv_response(
        rows=chart_rows,
        max_rows=settings.max_csv_rows,
        source="flat_file",
        ticker=ticker.upper(),
        date_from=start_date,
        date_to=end_date,
        fetched_at=_utc_now_iso(),
    )
    response["truncated"] = truncated or response["truncated"]
    return response


@mcp.tool()
async def search_tickers(
    search: str | None = None,
    ticker: str | None = None,
    market: str = "stocks",
    active: bool = True,
    limit: int = 20,
) -> dict[str, Any]:
    """Search for ticker symbols by name or symbol.

    Use for discovery before charting. Returns JSON metadata, not CSV.
    """

    client = get_rest_client()
    results = await client.search_tickers(
        search=search,
        ticker=ticker,
        market=market,
        active=active,
        limit=limit,
    )
    return {"count": len(results), "results": results, "fetched_at": _utc_now_iso()}


@mcp.tool()
async def get_ticker_details(ticker: str) -> dict[str, Any]:
    """Get company and instrument metadata for one ticker.

    Use for research context only. For charts, call `get_stock_bars_csv`.
    """

    client = get_rest_client()
    details = await client.get_ticker_details(ticker.upper())
    return {"ticker": ticker.upper(), "details": details, "fetched_at": _utc_now_iso()}


@mcp.tool()
async def get_stock_snapshot(ticker: str) -> dict[str, Any]:
    """Get the latest snapshot (price, day bar, last trade) for a stock.

    Use before charting to understand current market context. Requires a paid
    Massive plan for live snapshot data.
    """

    client = get_rest_client()
    snapshot = await client.get_stock_snapshot(ticker.upper())
    return {"ticker": ticker.upper(), "snapshot": snapshot, "fetched_at": _utc_now_iso()}


@mcp.tool()
async def list_options_contracts(
    underlying_ticker: str,
    contract_type: Literal["call", "put"] | None = None,
    expiration_date: str | None = None,
    expiration_date_gte: str | None = None,
    expiration_date_lte: str | None = None,
    strike_price: float | None = None,
    strike_price_gte: float | None = None,
    strike_price_lte: float | None = None,
    as_of: str | None = None,
    expired: bool | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List options contracts (reference data) for an underlying ticker.

    Use to find contract tickers before `get_options_bars_csv` or
    `get_option_contract_snapshot`. Filter by exact or ranged expiration
    (YYYY-MM-DD) and strike. Set `expired=true` (optionally with `as_of`) to find
    historical contracts for backtests. No prices; for live pricing/greeks use
    `get_options_chain_snapshot`.
    """

    client = get_rest_client()
    results = await client.list_options_contracts(
        underlying_ticker.upper(),
        contract_type=contract_type,
        expiration_date=expiration_date,
        expiration_date_gte=expiration_date_gte,
        expiration_date_lte=expiration_date_lte,
        strike_price=strike_price,
        strike_price_gte=strike_price_gte,
        strike_price_lte=strike_price_lte,
        as_of=as_of,
        expired=expired,
        limit=max(1, limit),
    )
    return {
        "underlying_ticker": underlying_ticker.upper(),
        "count": len(results),
        "contracts": results,
        "fetched_at": _utc_now_iso(),
    }


@mcp.tool()
async def get_option_contract_details(options_ticker: str, as_of: str | None = None) -> dict[str, Any]:
    """Reference spec for one option contract: type, exercise style, expiration,
    strike, shares per contract, underlying, primary exchange.

    Use `as_of` (YYYY-MM-DD) for expired contracts.
    """

    client = get_rest_client()
    ticker = _normalize_ticker(options_ticker)
    details = await client.get_options_contract(ticker, as_of=as_of)
    return {"ticker": ticker, "details": details, "fetched_at": _utc_now_iso()}


@mcp.tool()
async def get_option_contract_snapshot(options_ticker: str) -> dict[str, Any]:
    """Live snapshot of one option contract: IV, greeks, open interest, day bar,
    and (when the plan includes them) last quote / last trade.

    `summary` is a flat per-share row (mark = best available price, with
    `mark_source`); `snapshot` is the raw Massive payload. Feed `summary` values
    into `analyze_long_call_risk_reward` or `black_scholes_call_greeks`.
    """

    parts = parse_occ_ticker(options_ticker)
    client = get_rest_client()
    snapshot = await client.get_option_contract_snapshot(parts["underlying"], parts["ticker"])
    return {
        "ticker": parts["ticker"],
        "underlying": parts["underlying"],
        "summary": flatten_option_snapshot(snapshot, today=datetime.now(timezone.utc).date()),
        "snapshot": snapshot,
        "fetched_at": _utc_now_iso(),
    }


@mcp.tool()
async def get_options_chain_snapshot(
    underlying: str,
    contract_type: Literal["call", "put"] | None = None,
    expiration_date: str | None = None,
    expiration_date_gte: str | None = None,
    expiration_date_lte: str | None = None,
    strike_price_gte: float | None = None,
    strike_price_lte: float | None = None,
    max_contracts: int = 250,
    output: Literal["rows", "csv", "raw"] = "rows",
) -> dict[str, Any]:
    """Options chain snapshot with pricing, IV, greeks, and open interest.

    Always filter: a liquid underlying has thousands of contracts. Narrow with
    `contract_type`, an expiration window (`expiration_date` or `_gte`/`_lte`,
    YYYY-MM-DD) and a strike band around spot. Pages are followed automatically
    up to `max_contracts` (cap 2500); `truncated=true` means more matched.

    output:
    - `rows` (default): compact flat JSON rows (per-share prices)
    - `csv`: the same columns as CSV, for charting IV smile/skew, OI or volume
      by strike, or a greeks profile
    - `raw`: the unmodified Massive payload (large)

    `summary` gives put/call volume + OI ratios and the expirations covered.
    """

    max_contracts = max(1, min(max_contracts, MAX_CHAIN_CONTRACTS))
    client = get_rest_client()
    raw = await client.get_options_chain_snapshot(
        underlying.upper(),
        contract_type=contract_type,
        expiration_date=expiration_date,
        expiration_date_gte=expiration_date_gte,
        expiration_date_lte=expiration_date_lte,
        strike_price_gte=strike_price_gte,
        strike_price_lte=strike_price_lte,
        max_results=max_contracts + 1,  # one extra to detect truncation
    )
    truncated = len(raw) > max_contracts
    raw = raw[:max_contracts]

    today = datetime.now(timezone.utc).date()
    rows = [flatten_option_snapshot(item, today=today) for item in raw]
    rows.sort(key=lambda r: (r.get("expiration_date") or "", r.get("contract_type") or "", r.get("strike") or 0))

    response: dict[str, Any] = {
        "underlying": underlying.upper(),
        "filters": {
            "contract_type": contract_type,
            "expiration_date": expiration_date,
            "expiration_date_gte": expiration_date_gte,
            "expiration_date_lte": expiration_date_lte,
            "strike_price_gte": strike_price_gte,
            "strike_price_lte": strike_price_lte,
        },
        "count": len(rows),
        "truncated": truncated,
        "summary": summarize_chain(rows),
    }
    if output == "csv":
        response["csv"] = dict_rows_to_csv(rows, CHAIN_COLUMNS)
    elif output == "raw":
        response["chain"] = raw
    else:
        response["contracts"] = rows
    if not response["summary"]["has_quotes"]:
        response["quote_note"] = (
            "No bid/ask in this snapshot (plan lacks quote entitlement or market closed); "
            "`mark` falls back to last trade / session close."
        )
    response["fetched_at"] = _utc_now_iso()
    return response


@mcp.tool()
async def get_unified_snapshot(tickers: list[str]) -> dict[str, Any]:
    """Snapshot of up to 250 mixed tickers (stocks and option contracts) in one call.

    Use to price a multi-leg position, or a stock plus its options, together.
    Option entries also get a flat `summary` row (IV, greeks, mark).
    """

    if not tickers:
        return {"error": "provide at least one ticker"}
    if len(tickers) > 250:
        return {"error": f"{len(tickers)} tickers exceeds the 250-ticker limit"}

    normalized = [_normalize_ticker(t) for t in tickers]
    client = get_rest_client()
    results = await client.get_unified_snapshot(normalized)
    today = datetime.now(timezone.utc).date()
    for item in results:
        if item.get("type") == "options" and not item.get("error"):
            merged = {**item, "details": {**(item.get("details") or {}), "ticker": item.get("ticker")}}
            item["summary"] = flatten_option_snapshot(merged, today=today)
    return {"count": len(results), "results": results, "fetched_at": _utc_now_iso()}


@mcp.tool()
async def get_previous_day_bar(ticker: str, adjusted: bool = True) -> dict[str, Any]:
    """Previous trading day's OHLCV + VWAP for a stock or option contract."""

    client = get_rest_client()
    symbol = _normalize_ticker(ticker)
    bars = await client.get_previous_close(symbol, adjusted=adjusted)
    bar = bars[0] if bars else None
    return {
        "ticker": symbol,
        "bar": None
        if bar is None
        else {
            "date": (ms_to_et_iso(bar.get("t")) or "")[:10] or None,
            "open": bar.get("o"),
            "high": bar.get("h"),
            "low": bar.get("l"),
            "close": bar.get("c"),
            "volume": bar.get("v"),
            "vwap": bar.get("vw"),
            "transactions": bar.get("n"),
        },
        "fetched_at": _utc_now_iso(),
    }


@mcp.tool()
async def get_daily_open_close(ticker: str, date: str, adjusted: bool = True) -> dict[str, Any]:
    """Open / high / low / close / volume plus pre-market and after-hours prices
    for a stock or option contract on one date (YYYY-MM-DD)."""

    client = get_rest_client()
    symbol = _normalize_ticker(ticker)
    payload = await client.get_daily_open_close(symbol, date, adjusted=adjusted)
    payload.pop("status", None)
    return {"ticker": symbol, "date": date, "summary": payload, "fetched_at": _utc_now_iso()}


def _ts_param(value: str | None) -> str | None:
    """Accept YYYY-MM-DD, ISO datetimes, or nanosecond integers as-is."""
    return value.strip() if value else None


@mcp.tool()
async def get_trades_csv(
    ticker: str,
    from_timestamp: str | None = None,
    to_timestamp: str | None = None,
    limit: int = 1000,
) -> dict[str, Any]:
    """Tick-level trades for an option contract (or stock) as chronological CSV.

    Columns: datetime,price,size,exchange,conditions. Timestamps accept
    YYYY-MM-DD, ISO-8601, or nanoseconds. Returns the most recent `limit` trades
    in the window. Requires trades entitlement on the Massive plan; map
    exchange/condition IDs with `list_exchanges` / `list_condition_codes`.
    """

    settings = get_settings()
    limit = max(1, min(limit, settings.max_csv_rows))
    symbol = _normalize_ticker(ticker)
    client = get_rest_client()
    trades = await client.get_trades(
        symbol,
        timestamp_gte=_ts_param(from_timestamp),
        timestamp_lte=_ts_param(to_timestamp),
        order="desc",
        limit=limit,
    )
    rows = list(reversed(trades_to_rows(trades)))
    return {
        "ticker": symbol,
        "csv": dict_rows_to_csv(rows, TRADE_COLUMNS),
        "row_count": len(rows),
        "truncated": len(rows) >= limit,
        "fetched_at": _utc_now_iso(),
    }


@mcp.tool()
async def get_quotes_csv(
    ticker: str,
    from_timestamp: str | None = None,
    to_timestamp: str | None = None,
    limit: int = 1000,
) -> dict[str, Any]:
    """Historical NBBO bid/ask quotes for an option contract (or stock) as CSV.

    Columns: datetime,bid,bid_size,ask,ask_size,mid,spread,bid_exchange,ask_exchange.
    Use to chart spread width over time or check fill quality. Requires quotes
    entitlement on the Massive plan.
    """

    settings = get_settings()
    limit = max(1, min(limit, settings.max_csv_rows))
    symbol = _normalize_ticker(ticker)
    client = get_rest_client()
    quotes = await client.get_quotes(
        symbol,
        timestamp_gte=_ts_param(from_timestamp),
        timestamp_lte=_ts_param(to_timestamp),
        order="desc",
        limit=limit,
    )
    rows = list(reversed(quotes_to_rows(quotes)))
    return {
        "ticker": symbol,
        "csv": dict_rows_to_csv(rows, QUOTE_COLUMNS),
        "row_count": len(rows),
        "truncated": len(rows) >= limit,
        "fetched_at": _utc_now_iso(),
    }


@mcp.tool()
async def get_last_trade(ticker: str) -> dict[str, Any]:
    """Most recent trade for an option contract (or stock). Requires trades entitlement."""

    client = get_rest_client()
    symbol = _normalize_ticker(ticker)
    trade = await client.get_last_trade(symbol)
    return {
        "ticker": symbol,
        "price": trade.get("p"),
        "size": trade.get("s"),
        "exchange": trade.get("x"),
        "conditions": trade.get("c"),
        "datetime": ns_to_et_iso(trade.get("t")),
        "raw": trade,
        "fetched_at": _utc_now_iso(),
    }


@mcp.tool()
async def get_technical_indicator_csv(
    ticker: str,
    indicator: Literal["sma", "ema", "macd", "rsi"],
    timespan: Literal["minute", "hour", "day", "week", "month"] = "day",
    window: int | None = None,
    short_window: int | None = None,
    long_window: int | None = None,
    signal_window: int | None = None,
    series_type: Literal["open", "high", "low", "close"] = "close",
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 250,
    adjusted: bool = True,
) -> dict[str, Any]:
    """SMA / EMA / RSI / MACD series for a stock or option contract, as chart-ready CSV.

    Columns: datetime,value (MACD adds signal,histogram), oldest first, so it can
    be overlaid on `get_stock_bars_csv` / `get_options_bars_csv` output.
    `window` applies to SMA/EMA/RSI (Massive defaults: 50 for SMA/EMA, 14 for
    RSI); MACD uses `short_window`/`long_window`/`signal_window` (12/26/9).
    """

    settings = get_settings()
    limit = max(1, min(limit, settings.max_csv_rows, 5000))
    symbol = _normalize_ticker(ticker)
    client = get_rest_client()
    values = await client.get_indicator(
        indicator,
        symbol,
        timespan=timespan,
        adjusted=adjusted,
        window=window if indicator != "macd" else None,
        short_window=short_window if indicator == "macd" else None,
        long_window=long_window if indicator == "macd" else None,
        signal_window=signal_window if indicator == "macd" else None,
        series_type=series_type,
        timestamp_gte=from_date,
        timestamp_lte=to_date,
        order="desc",
        limit=limit,
    )
    rows = indicator_to_rows(values)
    response: dict[str, Any] = {
        "ticker": symbol,
        "indicator": indicator,
        "timespan": timespan,
        "csv": dict_rows_to_csv(rows, indicator_columns(indicator)),
        "row_count": len(rows),
        "truncated": len(rows) >= limit,
    }
    if not rows:
        response["note"] = (
            "No values returned. Thinly traded option contracts often have fewer bars "
            "than the indicator window needs; try a smaller `window`, a finer `timespan`, "
            "or a more liquid strike."
        )
    response["fetched_at"] = _utc_now_iso()
    return response


@mcp.tool()
async def get_market_status() -> dict[str, Any]:
    """Current market status (open / closed / extended hours) per exchange.

    Check before reading snapshots: off-hours, session fields are zero and quotes stale.
    """

    client = get_rest_client()
    status = await client.get_market_status()
    return {"status": status, "fetched_at": _utc_now_iso()}


@mcp.tool()
async def get_market_holidays() -> dict[str, Any]:
    """Upcoming market holidays and early closes (affects DTE / theta planning)."""

    client = get_rest_client()
    holidays = await client.get_market_holidays()
    return {"count": len(holidays), "holidays": holidays, "fetched_at": _utc_now_iso()}


@mcp.tool()
async def list_exchanges(
    asset_class: Literal["stocks", "options", "crypto", "fx", "futures"] | None = "options",
) -> dict[str, Any]:
    """Exchange reference (id, name, MIC). Maps exchange IDs in trades/quotes."""

    client = get_rest_client()
    exchanges = await client.list_exchanges(asset_class=asset_class)
    compact = [
        {k: e.get(k) for k in ("id", "name", "acronym", "mic", "participant_id", "type")}
        for e in exchanges
    ]
    return {"asset_class": asset_class, "count": len(compact), "exchanges": compact, "fetched_at": _utc_now_iso()}


@mcp.tool()
async def list_condition_codes(
    asset_class: Literal["stocks", "options", "crypto", "fx"] | None = "options",
    data_type: Literal["trade", "bbo", "nbbo"] | None = None,
) -> dict[str, Any]:
    """Trade/quote condition code reference. Maps `conditions` IDs in trades."""

    client = get_rest_client()
    conditions = await client.list_conditions(asset_class=asset_class, data_type=data_type)
    compact = [
        {k: c.get(k) for k in ("id", "abbreviation", "name", "type", "data_types", "description")}
        for c in conditions
    ]
    return {"asset_class": asset_class, "count": len(compact), "conditions": compact, "fetched_at": _utc_now_iso()}


@mcp.tool()
async def list_flat_file_datasets(
    asset_class: Literal["stocks", "options", "indices", "forex", "crypto"] | None = None,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    """List available Massive Flat File datasets and optional S3 objects for a month.

    Use to discover bulk CSV sources before `get_flat_file_bars_csv`.
    """

    flat = get_flat_client()
    catalog = flat.list_catalog()
    if asset_class:
        catalog = [entry for entry in catalog if entry["asset_class"] == asset_class]

    objects: dict[str, list[str]] = {}
    if asset_class and year and month:
        entry = next((item for item in catalog if item["asset_class"] == asset_class), None)
        if entry:
            for dataset in entry["datasets"]:
                if dataset in ("day_aggs_v1", "minute_aggs_v1"):
                    keys = flat.list_objects_for_month(entry["prefix"], dataset, year, month)
                    objects[dataset] = keys

    return {
        "catalog": catalog,
        "objects": objects,
        "fetched_at": _utc_now_iso(),
    }


@mcp.tool()
async def analyze_long_call_risk_reward(
    entry: float,
    strike: float,
    target: float,
    bid: float | None = None,
    ask: float | None = None,
    label: str | None = None,
    spread_max: float = SPREAD_MAX,
    rr_floor: float = RR_FLOOR,
) -> dict[str, Any]:
    """Screen a defined-risk long call for spread discipline and payoff asymmetry.

    Use after `get_options_chain_snapshot` or `list_options_contracts` to evaluate
    a candidate leg. `entry` is premium per share (use mid when bid/ask exist).
    `target` is the underlying price for payoff math. Returns breakeven, max loss,
    profit at target, payoff ratio (e.g. 4.0 = 4:1), spread %, and tradeable flag.
    Prices are per-share; per-contract figures are ×100.
    """

    result = long_call(
        entry=entry,
        strike=strike,
        target=target,
        bid=bid,
        ask=ask,
        spread_max=spread_max,
        rr_floor=rr_floor,
        label=label,
    )
    return {**result, "fetched_at": _utc_now_iso()}


@mcp.tool()
async def analyze_long_call_risk_reward_batch(
    legs: list[dict[str, Any]],
    spread_max: float = SPREAD_MAX,
    rr_floor: float = RR_FLOOR,
) -> dict[str, Any]:
    """Screen multiple long-call legs in one call.

    Each leg needs `entry`, `strike`, and `target`. Optional fields: `label`,
    `bid`, `ask`. Use when comparing barbell cores, PMCC long legs, or a chain
    shortlist. `all_tradeable` is false if any leg fails spread or payoff floors.
    """

    payload = analyze_long_call_batch(legs, spread_max=spread_max, rr_floor=rr_floor)
    return {**payload, "fetched_at": _utc_now_iso()}


@mcp.tool()
async def screen_long_calls_from_chain(
    underlying: str,
    target: float,
    expiration_date: str | None = None,
    expiration_date_gte: str | None = None,
    expiration_date_lte: str | None = None,
    strike_price_gte: float | None = None,
    strike_price_lte: float | None = None,
    min_open_interest: int = 0,
    max_contracts: int = 200,
    tradeable_only: bool = False,
    spread_max: float = SPREAD_MAX,
    rr_floor: float = RR_FLOOR,
) -> dict[str, Any]:
    """Pull call snapshots from the live chain and run the long-call risk/reward screen on each.

    One call replaces chain snapshot -> manual leg building -> batch screen.
    Entry is the ask when quotes exist (what a buyer pays), otherwise the
    snapshot mark (last trade / close; spread discipline then cannot be checked
    and `spread_ok` is false). `target` is the underlying price for payoff math.
    Results are sorted by payoff ratio, best first, with IV/delta/OI attached.
    """

    max_contracts = max(1, min(max_contracts, MAX_CHAIN_CONTRACTS))
    client = get_rest_client()
    raw = await client.get_options_chain_snapshot(
        underlying.upper(),
        contract_type="call",
        expiration_date=expiration_date,
        expiration_date_gte=expiration_date_gte,
        expiration_date_lte=expiration_date_lte,
        strike_price_gte=strike_price_gte,
        strike_price_lte=strike_price_lte,
        max_results=max_contracts + 1,
    )
    truncated = len(raw) > max_contracts
    today = datetime.now(timezone.utc).date()

    legs: list[dict[str, Any]] = []
    context: list[dict[str, Any]] = []
    skipped = 0
    for item in raw[:max_contracts]:
        row = flatten_option_snapshot(item, today=today)
        if (row.get("open_interest") or 0) < min_open_interest or row.get("strike") is None:
            skipped += 1
            continue
        priced = snapshot_premium_and_iv(item, side="buy")
        if priced["premium"] is None:
            skipped += 1
            continue
        legs.append(
            {
                "label": row["ticker"],
                "entry": priced["premium"],
                "strike": row["strike"],
                "target": target,
                "bid": priced["bid"],
                "ask": priced["ask"],
            }
        )
        context.append(
            {
                "ticker": row["ticker"],
                "expiration_date": row["expiration_date"],
                "dte": row["dte"],
                "entry_source": priced["premium_source"],
                "implied_volatility": row["implied_volatility"],
                "delta": row["delta"],
                "open_interest": row["open_interest"],
                "volume": row["volume"],
            }
        )

    payload = analyze_long_call_batch(legs, spread_max=spread_max, rr_floor=rr_floor)
    combined = [{**ctx, **res} for ctx, res in zip(context, payload["legs"])]
    if tradeable_only:
        combined = [r for r in combined if r["tradeable"]]
    combined.sort(key=lambda r: r["payoff_ratio_at_target"] if r["payoff_ratio_at_target"] is not None else float("-inf"), reverse=True)

    return {
        "underlying": underlying.upper(),
        "target_underlying": target,
        "screened": len(legs),
        "skipped": skipped,
        "truncated": truncated,
        "tradeable_count": sum(1 for r in combined if r["tradeable"]),
        "quotes_available": any(r.get("entry_source") == "snapshot_ask" for r in combined),
        "spread_max_pct": payload["spread_max_pct"],
        "rr_floor": rr_floor,
        "legs": combined,
        "fetched_at": _utc_now_iso(),
    }


@mcp.tool()
async def black_scholes_call_greeks(
    spot: float,
    strike: float,
    dte_days: float,
    iv: float | None = None,
    market_price: float | None = None,
    rate: float = 0.04,
) -> dict[str, Any]:
    """Black-Scholes call price and greeks; fallback when snapshot greeks/IV are null.

    Supply `iv` (decimal, e.g. 0.30) to price the call, or `market_price` (mid)
    to solve implied vol first. `dte_days` is calendar days to expiration.
    """

    result = black_scholes_call_analysis(
        spot=spot,
        strike=strike,
        dte_days=dte_days,
        iv=iv,
        market_price=market_price,
        rate=rate,
    )
    return {**result, "fetched_at": _utc_now_iso()}


@mcp.tool()
async def get_market_movers(direction: Literal["gainers", "losers"] = "gainers") -> dict[str, Any]:
    """Get top 20 market movers by percent change from previous close.

    Quick research tool. Requires a paid Massive stocks plan.
    """

    client = get_rest_client()
    movers = await client.get_market_movers(direction)
    return {"direction": direction, "count": len(movers), "tickers": movers, "fetched_at": _utc_now_iso()}


class Scenario(BaseModel):
    """One covered-call contract to simulate against the underlying grid."""

    strike: float = Field(..., description="Call strike price.", examples=[320.0])
    expiration: str = Field(
        ..., description="Contract expiration date, YYYY-MM-DD.", examples=["2026-08-21"]
    )
    premium: float | None = Field(
        None,
        description=(
            "Per-share credit collected for writing the call (override). If omitted, "
            "the tool derives it from the contract's most recent daily close (a stale "
            "last-trade price that may have printed at bid or ask)."
        ),
        examples=[6.25],
    )
    iv: float | None = Field(
        None,
        description=(
            "Implied volatility as a decimal, e.g. 0.30 (override). If omitted, the "
            "tool solves it from the premium via Black-Scholes."
        ),
        examples=[0.28],
    )
    label: str | None = Field(None, description="Optional display label for the scenario.")


def _snapshot_price(snapshot: dict[str, Any]) -> float | None:
    """Read a usable last price: day close if nonzero, else previous-day close.

    Off-hours the Massive snapshot returns zeros in `day`/`min` and the real value
    in `prevDay`.
    """
    day_close = (snapshot.get("day") or {}).get("c")
    if day_close:
        return float(day_close)
    prev_close = (snapshot.get("prevDay") or {}).get("c")
    if prev_close:
        return float(prev_close)
    return None


async def _derive_last_trade_premium(client: Any, contract_ticker: str, today: date) -> float | None:
    """Most recent daily close for a contract, used as a premium proxy."""
    from_date = (today - timedelta(days=10)).isoformat()
    to_date = today.isoformat()
    try:
        aggs = await client.get_ticker_aggs(contract_ticker, 1, "day", from_date, to_date)
    except MassiveAPIError:
        return None
    if not aggs:
        return None
    close = aggs[-1].get("c")
    return None if close is None else float(close)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Covered-call P/L scenario map",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def covered_call_sim(
    ticker: str,
    scenarios: list[Scenario],
    entry_price: float | None = None,
    contracts: int = 1,
    rate: float = 0.04,
    dividend_yield: float = 0.0,
    price_range_pct: float = 0.20,
    price_steps: int = 21,
    date_steps: int = 5,
    shares_per_contract: int = 100,
) -> dict[str, Any]:
    """Simulate covered-call P/L across an underlying-price x eval-date grid.

    Use this to compare one or more short-call scenarios against a long stock
    position (e.g. "compare the 320 / 325 / 330 calls on AAPL expiring next three
    Fridays") in a single call. Returns chart-ready long-format `csv` (one row per
    price x date cell) plus a per-scenario `metrics`/`assumptions` block; the agent
    renders the charts (expiration payoff, time-decay fan, strike comparison).

    Premium and IV are derive-or-override: pass `premium`/`iv` per scenario to
    override. Otherwise premium comes from the live contract snapshot (bid when
    quotes are available, else last trade / close) and IV from the snapshot's
    market implied volatility; if the snapshot is unavailable they fall back to
    the last daily bar and a Black-Scholes IV solve (flagged `approximate`). It is a scenario map using a
    European Black-Scholes model with constant IV, not a forecast.
    """

    today = datetime.now(timezone.utc).date()

    if not scenarios:
        return {"error": "provide at least one scenario (strike + expiration)."}

    total_cells = cell_count(len(scenarios), price_steps, date_steps)
    if total_cells > MAX_CELLS:
        return {
            "error": (
                f"grid too large: {len(scenarios)} scenarios x {price_steps} price_steps "
                f"x {date_steps} date_steps = {total_cells} cells exceeds the {MAX_CELLS} "
                "cell cap. Lower price_steps/date_steps or split the scenarios across calls."
            )
        }

    client = get_rest_client()

    # Resolve the shared underlying price once.
    spot: float | None = None
    snapshot_error: str | None = None
    try:
        snapshot = await client.get_stock_snapshot(ticker.upper())
        spot = _snapshot_price(snapshot)
    except MassiveAPIError as exc:
        snapshot_error = str(exc)

    if spot is None:
        spot = entry_price  # fall back to an explicit basis if the snapshot is unusable
    resolved_entry = entry_price if entry_price is not None else spot

    if resolved_entry is None:
        return {
            "error": (
                "could not resolve an underlying price"
                + (f" ({snapshot_error})" if snapshot_error else "")
                + "; pass `entry_price` explicitly."
            )
        }

    resolved: list[dict[str, Any]] = []
    for idx, scn in enumerate(scenarios):
        block: dict[str, Any] = {"scenario_id": idx, "label": scn.label}
        try:
            expiration = date.fromisoformat(scn.expiration)
        except ValueError:
            block["error"] = f"invalid expiration '{scn.expiration}'; use YYYY-MM-DD."
            resolved.append(block)
            continue

        dte = (expiration - today).days
        if dte < 0:
            block["error"] = f"expiration {scn.expiration} is in the past (dte={dte})."
            resolved.append(block)
            continue

        contract_ticker = occ_ticker(ticker, expiration, scn.strike)

        # Live contract snapshot supplies the bid (writer's credit) and market IV.
        snap: dict[str, Any] | None = None
        if scn.premium is None or scn.iv is None:
            try:
                raw_snap = await client.get_option_contract_snapshot(ticker.upper(), contract_ticker)
                snap = snapshot_premium_and_iv(raw_snap, side="sell")
            except MassiveAPIError:
                snap = None

        # Premium: override -> snapshot bid / mark -> last daily trade.
        premium = scn.premium
        premium_source = "override"
        if premium is None and snap and snap["premium"] is not None:
            premium = snap["premium"]
            premium_source = snap["premium_source"]
        if premium is None:
            premium = await _derive_last_trade_premium(client, contract_ticker, today)
            premium_source = "last_trade"
            if premium is None:
                block["error"] = (
                    f"no snapshot price or recent trade for {contract_ticker}; check the "
                    "strike/expiration exists or pass `premium` explicitly."
                )
                resolved.append(block)
                continue
        if premium <= 0:
            block["error"] = f"non-positive premium ({premium}) for {contract_ticker}."
            resolved.append(block)
            continue

        # IV: override -> snapshot market IV -> solve from premium.
        if scn.iv is not None:
            iv = scn.iv
            iv_source = "override"
            iv_quality = "exact"
        elif snap and snap["iv"] is not None:
            iv = snap["iv"]
            iv_source = "snapshot"
            iv_quality = "market"
        else:
            if spot is None:
                block["error"] = (
                    "cannot solve IV without an underlying price; pass `iv` for this "
                    "scenario or `entry_price` for the call."
                )
                resolved.append(block)
                continue
            iv = solve_iv(
                premium=premium, spot=spot, strike=scn.strike, dte=dte,
                rate=rate, dividend_yield=dividend_yield,
            )
            iv_source = f"solved_from_{premium_source}"
            iv_quality = "exact" if premium_source in _FIRM_PREMIUM_SOURCES else "approximate"
            if iv is None or iv <= 0:
                block["error"] = (
                    f"could not solve implied vol for {contract_ticker} from premium "
                    f"{premium}; pass `iv` explicitly."
                )
                resolved.append(block)
                continue

        block.update(
            {
                "strike": scn.strike,
                "expiration": expiration,
                "premium": premium,
                "iv": iv,
                "dte": dte,
                "shares_per_contract": shares_per_contract,
                "premium_source": premium_source,
                "iv_source": iv_source,
                "iv_quality": iv_quality,
            }
        )
        resolved.append(block)

    response = build_covered_call_response(
        ticker=ticker,
        resolved_scenarios=resolved,
        today=today,
        entry_price=resolved_entry,
        contracts=contracts,
        rate=rate,
        dividend_yield=dividend_yield,
        price_range_pct=price_range_pct,
        price_steps=price_steps,
        date_steps=date_steps,
    )
    response["entry_price_source"] = "override" if entry_price is not None else "snapshot"
    if premium_uses_last_trade(resolved):
        response["premium_note"] = (
            "One or more premiums come from a last trade / session close rather than "
            "a live bid (no quote in the snapshot), so they may have printed at the "
            "ask. Pass `premium` (the bid) per scenario for a true writer's credit."
        )
    response["fetched_at"] = _utc_now_iso()
    return response


# Premium sources that represent an actual executable price (not a stale print).
_FIRM_PREMIUM_SOURCES = {"override", "snapshot_bid", "snapshot_quote_mid"}


def premium_uses_last_trade(resolved: list[dict[str, Any]]) -> bool:
    return any(
        r.get("premium_source") not in _FIRM_PREMIUM_SOURCES
        for r in resolved
        if not r.get("error")
    )


if __name__ == "__main__":
    mcp.run()
