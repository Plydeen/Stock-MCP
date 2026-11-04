"""MCP OAuth configuration for remote clients (Claude Custom Connectors, etc.)."""

from __future__ import annotations

from fastmcp import FastMCP

from app.branding import register_favicon_routes, server_icons
from app.config import Settings, get_settings


def build_auth(settings: Settings):
    """Return a FastMCP auth provider when OAuth mode is enabled."""

    if settings.mcp_auth_mode != "oauth":
        return None

    if not settings.mcp_oauth_client_id or not settings.mcp_oauth_client_secret:
        raise ValueError(
            "MCP_AUTH_MODE=oauth requires MCP_OAUTH_CLIENT_ID and MCP_OAUTH_CLIENT_SECRET"
        )

    base_url = settings.mcp_public_base_url.rstrip("/")
    if not base_url:
        raise ValueError("MCP_AUTH_MODE=oauth requires MCP_PUBLIC_BASE_URL")

    provider = settings.mcp_oauth_provider.lower()
    common_kwargs: dict = {
        "client_id": settings.mcp_oauth_client_id,
        "client_secret": settings.mcp_oauth_client_secret,
        "base_url": base_url,
        # Skip the intermediate consent form (CSRF-prone); GitHub handles authorization.
        "require_authorization_consent": "external",
    }
    if settings.mcp_oauth_jwt_signing_key:
        common_kwargs["jwt_signing_key"] = settings.mcp_oauth_jwt_signing_key

    if provider == "github":
        from fastmcp.server.auth.providers.github import GitHubProvider

        return GitHubProvider(**common_kwargs)

    if provider == "google":
        from fastmcp.server.auth.providers.google import GoogleProvider

        return GoogleProvider(
            **common_kwargs,
            required_scopes=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
            ],
        )

    raise ValueError(
        f"Unsupported MCP_OAUTH_PROVIDER={settings.mcp_oauth_provider!r}; use github or google"
    )


def create_mcp() -> FastMCP:
    settings = get_settings()
    auth = build_auth(settings)
    base_url = settings.mcp_public_base_url.rstrip("/") or None
    mcp = FastMCP(
        "ButtonScale Research",
        instructions=(
            "Massive stock + options market data and asymmetric long-call risk/reward screening. "
            "For charts, use get_stock_bars_csv / get_options_bars_csv and parse the csv field; "
            "overlay get_technical_indicator_csv. For options, filter get_options_chain_snapshot "
            "by expiration and strike band (output=csv to chart IV smile or OI by strike), use "
            "get_option_contract_snapshot for one contract, and screen_long_calls_from_chain to "
            "run the long-call risk/reward screen directly on live chain data."
        ),
        website_url=base_url,
        icons=server_icons(base_url) or None,
        auth=auth,
    )
    register_favicon_routes(mcp)
    return mcp
