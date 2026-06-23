"""Massive REST API client."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx

from app.config import Settings, get_settings

MAX_PAGES = 10


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

    async def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        client = self._get_client()
        response = await client.request(method, path, params=params)
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            message = payload.get("error") or payload.get("message") or response.text
            raise MassiveAPIError(
                str(message),
                request_id=payload.get("request_id"),
                status_code=response.status_code,
            )

        payload = response.json()
        status = payload.get("status")
        if status and status != "OK":
            raise MassiveAPIError(
                str(status),
                request_id=payload.get("request_id"),
                status_code=response.status_code,
            )
        return payload

    async def _request_paginated(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        results_key: str = "results",
    ) -> list[dict[str, Any]]:
        client = self._get_client()
        results: list[dict[str, Any]] = []
        next_url: str | None = path
        query = dict(params or {})
        pages = 0

        while next_url and pages < MAX_PAGES:
            if next_url.startswith("http"):
                response = await client.get(next_url)
            else:
                response = await client.get(next_url, params=query if pages == 0 else None)

            if response.status_code >= 400:
                try:
                    payload = response.json()
                except ValueError:
                    payload = {}
                message = payload.get("error") or payload.get("message") or response.text
                raise MassiveAPIError(
                    str(message),
                    request_id=payload.get("request_id"),
                    status_code=response.status_code,
                )

            payload = response.json()
            status = payload.get("status")
            if status and status != "OK":
                raise MassiveAPIError(
                    str(status),
                    request_id=payload.get("request_id"),
                    status_code=response.status_code,
                )

            page_results = payload.get(results_key) or []
            if isinstance(page_results, list):
                results.extend(page_results)

            next_url = payload.get("next_url")
            if next_url and not next_url.startswith("http"):
                next_url = urljoin(f"{self.settings.massive_api_base_url.rstrip('/')}/", next_url.lstrip("/"))
            pages += 1

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
        strike_price: float | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "underlying_ticker": underlying_ticker,
            "limit": limit,
            "sort": "expiration_date",
        }
        if contract_type:
            params["contract_type"] = contract_type
        if expiration_date:
            params["expiration_date"] = expiration_date
        if strike_price is not None:
            params["strike_price"] = strike_price
        return await self._request_paginated("/v3/reference/options/contracts", params=params)

    async def get_options_chain_snapshot(self, underlying: str) -> dict[str, Any]:
        payload = await self._request("GET", f"/v3/snapshot/options/{underlying}")
        return payload

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
