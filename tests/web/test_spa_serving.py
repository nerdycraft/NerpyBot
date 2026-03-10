"""Tests that FastAPI serves the SPA index.html for non-API routes."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def spa_client(tmp_path):
    """TestClient with a fake dist/ containing index.html."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>NerpyBot</body></html>")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "main.js").write_text("// js")

    from web.config import WebConfig
    from web.app import create_app
    from web.cache import ValkeyClient

    cfg = WebConfig._build(
        {
            "bot": {"client_id": "123", "ops": "456"},
            "web": {"client_secret": "s", "jwt_secret": "j"},
        }
    )
    vk = MagicMock(spec=ValkeyClient)
    app = create_app(config=cfg, valkey_client=vk, spa_dist=dist)
    return TestClient(app, raise_server_exceptions=True)


def test_spa_index_served_for_root(spa_client):
    response = spa_client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert "NerpyBot" in response.text


def test_spa_index_served_for_unknown_route(spa_client):
    """SPA catch-all: any non-API path returns index.html."""
    response = spa_client.get("/guilds/123", follow_redirects=False)
    assert response.status_code == 200
    assert "NerpyBot" in response.text


def test_api_routes_not_swallowed_by_catchall(spa_client):
    """API routes must not be caught by the SPA fallback."""
    response = spa_client.get("/api/docs")
    assert response.status_code == 200


def test_static_asset_served(spa_client):
    response = spa_client.get("/assets/main.js")
    assert response.status_code == 200


def test_root_static_file_served(tmp_path):
    """Files at the dist root (e.g. favicon.svg) are served directly, not as index.html."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>NerpyBot</body></html>")
    (dist / "favicon.svg").write_text("<svg></svg>")
    (dist / "assets").mkdir()

    from unittest.mock import MagicMock
    from web.config import WebConfig
    from web.app import create_app
    from web.cache import ValkeyClient

    cfg = WebConfig._build(
        {
            "bot": {"client_id": "123", "ops": "456"},
            "web": {"client_secret": "s", "jwt_secret": "j"},
        }
    )
    vk = MagicMock(spec=ValkeyClient)
    app = create_app(config=cfg, valkey_client=vk, spa_dist=dist)
    client = TestClient(app, raise_server_exceptions=True)

    response = client.get("/favicon.svg")
    assert response.status_code == 200
    assert response.text == "<svg></svg>"
