"""Massive Flat Files (S3) client."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import Settings, get_settings

ASSET_PREFIXES = {
    "stocks": "us_stocks_sip",
    "options": "us_options_opra",
    "indices": "us_indices",
    "forex": "global_forex",
    "crypto": "global_crypto",
}

DATASETS = {
    "day": "day_aggs_v1",
    "minute": "minute_aggs_v1",
}

DATASET_CATALOG = [
    {
        "asset_class": "stocks",
        "prefix": "us_stocks_sip",
        "datasets": ["day_aggs_v1", "minute_aggs_v1", "trades_v1", "quotes_v1"],
    },
    {
        "asset_class": "options",
        "prefix": "us_options_opra",
        "datasets": ["day_aggs_v1", "minute_aggs_v1", "trades_v1", "quotes_v1"],
    },
    {
        "asset_class": "indices",
        "prefix": "us_indices",
        "datasets": ["day_aggs_v1", "minute_aggs_v1", "values_v1"],
    },
    {
        "asset_class": "forex",
        "prefix": "global_forex",
        "datasets": ["day_aggs_v1", "minute_aggs_v1", "quotes_v1"],
    },
    {
        "asset_class": "crypto",
        "prefix": "global_crypto",
        "datasets": ["day_aggs_v1", "minute_aggs_v1", "trades_v1"],
    },
]


class MassiveFlatFilesClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client = None

    def _s3(self):
        if self._client is None:
            access_key, secret_key = self.settings.require_s3_credentials()
            session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
            self._client = session.client(
                "s3",
                endpoint_url=self.settings.massive_s3_endpoint,
                config=Config(signature_version="s3v4"),
            )
        return self._client

    def list_catalog(self) -> list[dict[str, Any]]:
        return DATASET_CATALOG

    def list_objects_for_month(self, prefix: str, dataset: str, year: int, month: int) -> list[str]:
        s3 = self._s3()
        month_prefix = f"{prefix}/{dataset}/{year}/{month:02d}/"
        keys: list[str] = []
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.settings.massive_s3_bucket, Prefix=month_prefix):
            for obj in page.get("Contents", []):
                key = obj.get("Key")
                if key and key.endswith(".csv.gz"):
                    keys.append(key)
        return sorted(keys)

    def _object_key(self, prefix: str, dataset: str, day: date) -> str:
        return f"{prefix}/{dataset}/{day.year}/{day.month:02d}/{day.isoformat()}.csv.gz"

    def _cache_path(self, object_key: str) -> Path:
        cache_dir = Path(self.settings.flat_file_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(object_key.encode()).hexdigest()
        return cache_dir / f"{digest}.csv.gz"

    def _get_object_bytes(self, object_key: str) -> bytes:
        cache_file = self._cache_path(object_key)
        ttl_seconds = self.settings.flat_file_cache_ttl_hours * 3600
        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < ttl_seconds:
                return cache_file.read_bytes()

        s3 = self._s3()
        response = s3.get_object(Bucket=self.settings.massive_s3_bucket, Key=object_key)
        body = response["Body"].read()
        cache_file.write_bytes(body)
        return body

    def stream_ticker_rows(self, object_key: str, ticker: str) -> Iterator[dict[str, str]]:
        raw = self._get_object_bytes(object_key)
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as gz:
            text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
            reader = csv.DictReader(text)
            target = ticker.upper()
            for row in reader:
                row_ticker = (row.get("ticker") or "").upper()
                if row_ticker == target:
                    yield row

    def iter_trading_days(self, start_date: date, end_date: date) -> Iterator[date]:
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                yield current
            current += timedelta(days=1)

    def collect_ticker_bars(
        self,
        *,
        asset_class: str,
        dataset: str,
        ticker: str,
        start_date: date,
        end_date: date,
        max_rows: int,
    ) -> tuple[list[dict[str, str]], bool]:
        prefix = ASSET_PREFIXES.get(asset_class)
        dataset_name = DATASETS.get(dataset)
        if not prefix or not dataset_name:
            raise ValueError(f"Unsupported asset_class={asset_class!r} or dataset={dataset!r}")

        rows: list[dict[str, str]] = []
        truncated = False
        for day in self.iter_trading_days(start_date, end_date):
            object_key = self._object_key(prefix, dataset_name, day)
            try:
                for row in self.stream_ticker_rows(object_key, ticker):
                    rows.append(row)
                    if len(rows) >= max_rows:
                        truncated = True
                        return rows, truncated
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in {"NoSuchKey", "404", "NotFound"}:
                    continue
                raise
        return rows, truncated


_client: MassiveFlatFilesClient | None = None


def get_flat_client() -> MassiveFlatFilesClient:
    global _client
    if _client is None:
        _client = MassiveFlatFilesClient()
    return _client
