"""Branding asset tests."""

from app.branding import FAVICON_PATH, favicon_data_uri, server_icons


def test_favicon_asset_exists():
    assert FAVICON_PATH.is_file()


def test_favicon_data_uri():
    uri = favicon_data_uri()
    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > 100


def test_server_icons_includes_embedded_and_url():
    icons = server_icons("https://mcp.kowens.tech")
    assert len(icons) == 2
    assert icons[0].src.startswith("data:image/png;base64,")
    assert icons[1].src == "https://mcp.kowens.tech/favicon.png"
