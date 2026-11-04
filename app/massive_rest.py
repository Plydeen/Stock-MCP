"""Massive REST API client."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx

from app.config import Settings, get_settings

MAX_PAGES = 10


def _clean_params(params: dict[str, Any] | None) -> dict[str, Any]:
    """Drop None values and lowercase booleans so they serialize as Massive expects."""
    cleaned: dict[str, Any] = {}
    for key, value in (params or {}).items():
        if value is None:
            continue
        cleaned[key] = str(value).lower() if isinstance(value, bool) else value
    return cleaned


class MassiveAPIError(Exception):
    def __init__(self, message: str, *, request_id: str | None = None, status_code: int | None = None):
        self.request_id = request_id
        self.status_code = status_code
        super().__init__(message)


class MassiveRESTClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> MassiveRESTClient:
        self._client = httpx.AsyncClient(
            base_url=self.settings.massive_api_base_url.rstrip("/"),
            timeout=30.0,
            headers={"Authorization": f"Bearer {self.settings.require_api_key()}"},
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.massive_api_base_url.rstrip("/"),
                timeout=30.0,
                headers={"Authorization": f"Bearer {self.settings.require_api_key()}"},
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _check_response(response: httpx.Response) -> Any:
        """Raise MassiveAPIError on HTTP or envelope errors; return the decoded JSON."""
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            message = payload.get("error") or payload.get("message") or response.text
            raise MassiveAPIError(
                str(message),
                request_id=payload.get("request_id"),
                status_code=response.status_code,
            )

        payload = response.json()
        # A few endpoints (e.g. market holidays) return a bare JSON array.
        if isinstance(payload, dict):
            status = payload.get("status")
            if status and status not in ("OK", "DELAYED"):
                raise MassiveAPIError(
                    str(payload.get("error") or payload.get("message") or status),
                    request_id=payload.get("request_id"),
                    status_code=response.status_code,
                )
        return payload

    async def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None) -> Any:
        client = self._get_client()
        response = await client.request(method, path, params=_clean_params(params))
        return self._check_response(response)

    async def _request_paginated(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        results_key: str = "results",
        max_pages: int = MAX_PAGES,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Follow `next_url` cursors, stopping at `max_pages` or `max_results`."""
        client = self._get_client()
        results: list[dict[str, Any]] = []
        next_url: str | None = path
        query = _clean_params(params)
        pages = 0

        while next_url and pages < max_pages:
            if next_url.startswith("http"):
                response = await client.get(next_url)
            else:
                response = await client.get(next_url, params=query if pages == 0 else None)

            payload = self._check_response(response)
            page_results = payload.get(results_key) or []
            if isinstance(page_results, list):
                results.extend(page_results)
            pages += 1

            if max_results is not None and len(results) >= max_results:
                return results[:max_results]

            next_url = payload.get("next_url")
            if next_url and not next_url.startswith("http"):
                next_url = urljoin(f"{self.settings.massive_api_base_url.rstrip('/')}/", next_url.lstrip("/"))

        return results

    async def get_ticker_aggs(
        self,
        ticker: str,
        multiplier: int,
        timespan: str,
        from_date: str,
        to_date: str,
        *,
        adjusted: bool = True,
        sort: str = "asc",
        limit: int = 50000,
    ) -> list[dict[str, Any]]:
        path = f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
        return await self._request_paginated(
            path,
            params={"adjusted": str(adjusted).lower(), "sort": sort, "limit": limit},
        )

    async def search_tickers(
        self,
        *,
        search: str | None = None,
        ticker: str | None = None,
        market: str = "stocks",
        active: bool = True,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "market": market,
            "active": str(active).lower(),
            "limit": limit,
            "sort": "ticker",
        }
        if search:
            params["search"] = search
        if ticker:
            params["ticker"] = ticker
        return await self._request_paginated("/v3/reference/tickers", params=params)

    async def get_ticker_details(self, ticker: str) -> dict[str, Any]:
        payload = await self._request("GET", f"/v3/reference/tickers/{ticker}")
        results = payload.get("results")
        if isinstance(results, dict):
            return results
        return payload

    async def get_stock_snapshot(self, ticker: str) -> dict[str, Any]:
        payload = await self._request("GET", f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}")
        return payload.get("ticker") or payload

    async def list_options_contracts(
        self,
        underlying_ticker: str,
        *,
        contract_type: str | None = None,
        expiration_date: str | None = None,
        expiration_date_gte: str | None = None,
        expiration_date_lte: str | None = None,
        strike_price: float | None = None,
        strike_price_gte: float | None = None,
        strike_price_lte: float | None = None,
        as_of: str | None = None,
        expired: bool | None = None,
        sort: str = "expiration_date",
        order: str = "asc",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "underlying_ticker": underlying_ticker,
            "contract_type": contract_type,
            "expiration_date": expiration_date,
            "expiration_date.gte": expiration_date_gte,
            "expiration_date.lte": expiration_date_lte,
            "strike_price": strike_price,
            "strike_price.gte": strike_price_gte,
            "strike_price.lte": strike_price_lte,
            "as_of": as_of,
            "expired": expired,
            "sort": sort,
            "order": order,
            "limit": min(limit, 1000),
        }
        return await self._request_paginated(
            "/v3/reference/options/contracts", params=params, max_results=limit
        )

    async def get_options_contract(self, options_ticker: str, *, as_of: str | None = None) -> dict[str, Any]:
        payload = await self._request(
            "GET", f"/v3/reference/options/contracts/{options_ticker}", params={"as_of": as_of}
        )
        results = payload.get("results")
        return results if isinstance(results, dict) else payload

    async def get_option_contract_snapshot(self, underlying: str, options_ticker: str) -> dict[str, Any]:
        payload = await self._request("GET", f"/v3/snapshot/options/{underlying}/{options_ticker}")
        results = payload.get("results")
        return results if isinstance(results, dict) else payload

    async def get_options_chain_snapshot(
        self,
        underlying: str,
        *,
        contract_type: str | None = None,
        expiration_date: str | None = None,
        expiration_date_gte: str | None = None,
        expiration_date_lte: str | None = None,
        strike_price: float | None = None,
        strike_price_gte: float | None = None,
        strike_price_lte: float | None = None,
        sort: str | None = None,
        order: str | None = None,
        max_results: int = 250,
    ) -> list[dict[str, Any]]:
        """Chain snapshot, following pagination (250 contracts per page) up to `max_results`."""
        params: dict[str, Any] = {
            "contract_type": contract_type,
            "expiration_date": expiration_date,
            "expiration_date.gte": expiration_date_gte,
            "expiration_date.lte": expiration_date_lte,
            "strike_price": strike_price,
            "strike_price.gte": strike_price_gte,
            "strike_price.lte": strike_price_lte,
            "sort": sort,
            "order": order,
            "limit": min(max_results, 250),
        }
        return await self._request_paginated(
            f"/v3/snapshot/options/{underlying}",
            params=params,
            max_pages=max(1, -(-max_results // 250)),
            max_results=max_results,
        )

    async def get_unified_snapshot(self, tickers: list[str]) -> list[dict[str, Any]]:
        """Multi-asset snapshot (stocks + options + ...) for up to 250 tickers."""
        payload = await self._request(
            "GET", "/v3/snapshot", params={"ticker.any_of": ",".join(tickers), "limit": 250}
        )
        results = payload.get("results") or []
        return results if isinstance(results, list) else []

    async def get_previous_close(self, ticker: str, *, adjusted: bool = True) -> list[dict[str, Any]]:
        payload = await self._request(
            "GET", f"/v2/aggs/ticker/{ticker}/prev", params={"adjusted": adjusted}
        )
        results = payload.get("results") or []
        return results if isinstance(results, list) else []

    async def get_daily_open_close(self, ticker: str, day: str, *, adjusted: bool = True) -> dict[str, Any]:
        return await self._request("GET", f"/v1/open-close/{ticker}/{day}", params={"adjusted": adjusted})

    async def get_trades(
        self,
        ticker: str,
        *,
        timestamp: str | None = None,
        timestamp_gte: str | None = None,
        timestamp_lte: str | None = None,
        order: str = "desc",
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        params = {
            "timestamp": timestamp,
            "timestamp.gte": timestamp_gte,
            "timestamp.lte": timestamp_lte,
            "order": order,
            "sort": "timestamp",
            "limit": min(limit, 50000),
        }
        return await self._request_paginated(f"/v3/trades/{ticker}", params=params, max_results=limit)

    async def get_quotes(
        self,
        ticker: str,
        *,
        timestamp: str | None = None,
        timestamp_gte: str | None = None,
        timestamp_lte: str | None = None,
        order: str = "desc",
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        params = {
            "timestamp": timestamp,
            "timestamp.gte": timestamp_gte,
            "timestamp.lte": timestamp_lte,
            "order": order,
            "sort": "timestamp",
            "limit": min(limit, 50000),
        }
        return await self._request_paginated(f"/v3/quotes/{ticker}", params=params, max_results=limit)

    async def get_last_trade(self, ticker: str) -> dict[str, Any]:
        payload = await self._request("GET", f"/v2/last/trade/{ticker}")
        results = payload.get("results")
        return results if isinstance(results, dict) else payload

    async def get_indicator(
        self,
        indicator: str,
        ticker: str,
        *,
        timespan: str = "day",
        adjusted: bool = True,
        window: int | None = None,
        short_window: int | None = None,
        long_window: int | None = None,
        signal_window: int | None = None,
        series_type: str = "close",
        timestamp_gte: str | None = None,
        timestamp_lte: str | None = None,
        order: str = "desc",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """SMA / EMA / MACD / RSI values (newest first by default)."""
        params = {
            "timespan": timespan,
            "adjusted": adjusted,
            "window": window,
            "short_window": short_window,
            "long_window": long_window,
            "signal_window": signal_window,
            "series_type": series_type,
            "timestamp.gte": timestamp_gte,
            "timestamp.lte": timestamp_lte,
            "order": order,
            "limit": min(limit, 5000),
        }
        payload = await self._request("GET", f"/v1/indicators/{indicator}/{ticker}", params=params)
        values = (payload.get("results") or {}).get("values") or []
        return values if isinstance(values, list) else []

    async def get_market_status(self) -> dict[str, Any]:
        return await self._request("GET", "/v1/marketstatus/now")

    async def get_market_holidays(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/v1/marketstatus/upcoming")
        return payload if isinstance(payload, list) else []

    async def list_exchanges(self, *, asset_class: str | None = None) -> list[dict[str, Any]]:
        payload = await self._request(
            "GET", "/v3/reference/exchanges", params={"asset_class": asset_class, "locale": "us"}
        )
        results = payload.get("results") or []
        return results if isinstance(results, list) else []

    async def list_conditions(
        self, *, asset_class: str | None = None, data_type: str | None = None, limit: int = 1000
    ) -> list[dict[str, Any]]:
        params = {"asset_class": asset_class, "data_type": data_type, "limit": min(limit, 1000)}
        return await self._request_paginated("/v3/reference/conditions", params=params, max_results=limit)

    async def get_market_movers(self, direction: str = "gainers") -> list[dict[str, Any]]:
        payload = await self._request(
            "GET",
            f"/v2/snapshot/locale/us/markets/stocks/{direction}",
        )
        tickers = payload.get("tickers") or []
        return tickers if isinstance(tickers, list) else []


_client: MassiveRESTClient | None = None


def get_rest_client() -> MassiveRESTClient:
    global _client
    if _client is None:
        _client = MassiveRESTClient()
    return _client
