"""FastMCP tools for Massive market data research."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from fastmcp import FastMCP

from app.config import get_settings
from app.csv_format import (
    build_csv_response,
    flat_file_row_to_chart_row,
    rest_aggs_to_rows,
)
from app.massive_flat import get_flat_client
from app.massive_rest import get_rest_client

mcp = FastMCP("massive-research-tools")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


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
    O:AAPL250620C00200000). Parse the `csv` field for charting.
    """

    settings = get_settings()
    client = get_rest_client()
    aggs = await client.get_ticker_aggs(
        options_ticker.upper(),
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
    strike_price: float | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List options contracts for an underlying ticker.

    Use to find contract tickers before calling `get_options_bars_csv`.
    """

    client = get_rest_client()
    results = await client.list_options_contracts(
        underlying_ticker.upper(),
        contract_type=contract_type,
        expiration_date=expiration_date,
        strike_price=strike_price,
        limit=limit,
    )
    return {
        "underlying_ticker": underlying_ticker.upper(),
        "count": len(results),
        "contracts": results,
        "fetched_at": _utc_now_iso(),
    }


@mcp.tool()
async def get_options_chain_snapshot(underlying: str) -> dict[str, Any]:
    """Get a full options chain snapshot for an underlying ticker.

    Requires a paid Massive options plan. Use for chain overview before
    selecting a contract to chart.
    """

    client = get_rest_client()
    chain = await client.get_options_chain_snapshot(underlying.upper())
    return {"underlying": underlying.upper(), "chain": chain, "fetched_at": _utc_now_iso()}


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
async def get_market_movers(direction: Literal["gainers", "losers"] = "gainers") -> dict[str, Any]:
    """Get top 20 market movers by percent change from previous close.

    Quick research tool. Requires a paid Massive stocks plan.
    """

    client = get_rest_client()
    movers = await client.get_market_movers(direction)
    return {"direction": direction, "count": len(movers), "tickers": movers, "fetched_at": _utc_now_iso()}


if __name__ == "__main__":
    mcp.run()
