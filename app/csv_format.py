"""CSV formatting for chart-ready OHLCV data."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
CSV_HEADER = ["datetime", "open", "high", "low", "close", "volume", "transactions"]


def _ms_to_et_iso(timestamp_ms: int | float) -> str:
    dt = datetime.fromtimestamp(float(timestamp_ms) / 1000.0, tz=timezone.utc).astimezone(ET)
    return dt.isoformat()


def _ns_to_et_iso(timestamp_ns: int | str) -> str:
    dt = datetime.fromtimestamp(int(timestamp_ns) / 1_000_000_000.0, tz=timezone.utc).astimezone(ET)
    return dt.isoformat()


def rest_aggs_to_rows(aggs: list[dict[str, Any]]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for bar in aggs:
        rows.append(
            [
                _ms_to_et_iso(bar["t"]),
                bar.get("o"),
                bar.get("h"),
                bar.get("l"),
                bar.get("c"),
                bar.get("v"),
                bar.get("n", ""),
            ]
        )
    return rows


def flat_file_row_to_chart_row(row: dict[str, str], *, ticker_col: str = "ticker") -> list[Any] | None:
    if row.get(ticker_col) is None:
        return None
    window_start = row.get("window_start")
    if not window_start:
        return None
    return [
        _ns_to_et_iso(window_start),
        row.get("open"),
        row.get("high"),
        row.get("low"),
        row.get("close"),
        row.get("volume"),
        row.get("transactions", ""),
    ]


def rows_to_csv(rows: list[list[Any]], *, max_rows: int) -> tuple[str, int, bool]:
    truncated = len(rows) > max_rows
    limited = rows[:max_rows]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    writer.writerows(limited)
    return buffer.getvalue(), len(limited), truncated


def build_csv_response(
    *,
    rows: list[list[Any]],
    max_rows: int,
    source: str,
    ticker: str,
    date_from: str,
    date_to: str,
    fetched_at: str,
) -> dict[str, Any]:
    csv_text, row_count, truncated = rows_to_csv(rows, max_rows=max_rows)
    return {
        "csv": csv_text,
        "row_count": row_count,
        "truncated": truncated,
        "source": source,
        "ticker": ticker,
        "date_range": {"from": date_from, "to": date_to},
        "fetched_at": fetched_at,
    }
