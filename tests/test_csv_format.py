"""Tests for CSV formatting."""

from app.csv_format import (
    build_csv_response,
    flat_file_row_to_chart_row,
    rest_aggs_to_rows,
    rows_to_csv,
)


def test_rest_aggs_to_rows_maps_fields():
    aggs = [
        {"t": 1_718_800_200_000, "o": 210.1, "h": 211.0, "l": 209.5, "c": 210.8, "v": 1000, "n": 42},
    ]
    rows = rest_aggs_to_rows(aggs)
    assert len(rows) == 1
    assert rows[0][1:6] == [210.1, 211.0, 209.5, 210.8, 1000]
    assert rows[0][6] == 42
    assert "T" in rows[0][0]


def test_flat_file_row_to_chart_row():
    row = {
        "ticker": "AAPL",
        "open": "200.29",
        "high": "200.63",
        "low": "200.29",
        "close": "200.5",
        "volume": "4930",
        "window_start": "1744792500000000000",
        "transactions": "129",
    }
    mapped = flat_file_row_to_chart_row(row)
    assert mapped is not None
    assert mapped[1:] == ["200.29", "200.63", "200.29", "200.5", "4930", "129"]


def test_rows_to_csv_truncates():
    rows = [[f"2025-01-{i:02d}T09:30:00-05:00", 1, 2, 0.5, 1.5, 100, 10] for i in range(1, 11)]
    csv_text, row_count, truncated = rows_to_csv(rows, max_rows=5)
    assert row_count == 5
    assert truncated is True
    assert csv_text.startswith("datetime,open,high,low,close,volume,transactions\n")
    assert csv_text.count("\n") == 6


def test_build_csv_response_envelope():
    rows = [["2025-06-20T09:30:00-04:00", 1, 2, 0.5, 1.5, 100, 10]]
    response = build_csv_response(
        rows=rows,
        max_rows=100,
        source="rest",
        ticker="AAPL",
        date_from="2025-06-01",
        date_to="2025-06-20",
        fetched_at="2025-06-21T12:00:00Z",
    )
    assert response["row_count"] == 1
    assert response["truncated"] is False
    assert response["source"] == "rest"
    assert "datetime,open" in response["csv"]
