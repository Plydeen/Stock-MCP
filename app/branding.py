"""Server branding: MCP icons and public favicon routes."""

from __future__ import annotations

import base64
from pathlib import Path

from fastmcp import FastMCP
from mcp.types import Icon
from starlette.requests import Request
from starlette.responses import Response

FAVICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "favicon.png"


def favicon_bytes() -> bytes:
    return FAVICON_PATH.read_bytes()


def favicon_data_uri() -> str:
    encoded = base64.b64encode(favicon_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def server_icons(public_base_url: str | None = None) -> list[Icon]:
    if not FAVICON_PATH.is_file():
        return []

    icons = [
        Icon(
            src=favicon_data_uri(),
            mimeType="image/png",
            sizes=["128x128", "any"],
        ),
    ]
    if public_base_url:
        icons.append(
            Icon(
                src=f"{public_base_url.rstrip('/')}/favicon.png",
                mimeType="image/png",
                sizes=["128x128"],
            )
        )
    return icons


def register_favicon_routes(mcp: FastMCP) -> None:
    @mcp.custom_route("/", methods=["GET"])
    async def root(_request: Request) -> Response:
        return Response(
            content="ButtonScale Research MCP — connect via /mcp",
            media_type="text/plain",
        )

    if not FAVICON_PATH.is_file():
        return

    data = favicon_bytes()

    @mcp.custom_route("/favicon.ico", methods=["GET"])
    async def favicon_ico(_request: Request) -> Response:
        return Response(content=data, media_type="image/png")

    @mcp.custom_route("/favicon.png", methods=["GET"])
    async def favicon_png(_request: Request) -> Response:
        return Response(content=data, media_type="image/png")

    @mcp.custom_route("/apple-touch-icon.png", methods=["GET"])
    async def apple_touch_icon(_request: Request) -> Response:
        return Response(content=data, media_type="image/png")
