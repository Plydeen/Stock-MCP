"""Auth configuration tests."""

import pytest

from app.auth import build_auth
from app.config import Settings


def test_build_auth_disabled_for_basic_mode():
    settings = Settings(mcp_auth_mode="basic")
    assert build_auth(settings) is None


def test_build_auth_requires_oauth_credentials():
    settings = Settings(
        mcp_auth_mode="oauth",
        mcp_public_base_url="https://mcp.example.com",
        mcp_oauth_provider="github",
    )
    with pytest.raises(ValueError, match="MCP_OAUTH_CLIENT_ID"):
        build_auth(settings)


def test_build_auth_requires_public_base_url():
    settings = Settings(
        mcp_auth_mode="oauth",
        mcp_oauth_client_id="id",
        mcp_oauth_client_secret="secret",
        mcp_oauth_provider="github",
    )
    with pytest.raises(ValueError, match="MCP_PUBLIC_BASE_URL"):
        build_auth(settings)
