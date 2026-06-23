"""Optional integration tests against live Massive APIs."""

import os

import pytest

from app.massive_rest import MassiveRESTClient
from app.config import get_settings

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="Set RUN_INTEGRATION=1 and provide MASSIVE_API_KEY to run",
)


@pytest.fixture
def settings():
    s = get_settings()
    if not s.massive_api_key:
        pytest.skip("MASSIVE_API_KEY not set")
    return s


@pytest.mark.asyncio
async def test_fetch_aapl_daily_bars(settings):
    async with MassiveRESTClient(settings) as client:
        aggs = await client.get_ticker_aggs(
            "AAPL",
            1,
            "day",
            "2025-06-01",
            "2025-06-10",
        )
    assert len(aggs) >= 1
    assert "t" in aggs[0]
    assert "c" in aggs[0]
