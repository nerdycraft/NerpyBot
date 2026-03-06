"""Shared fixtures for web API tests."""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure NerdyPy is on the path (same as main conftest.py)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "NerdyPy"))

from utils.database import BASE


@pytest.fixture
def web_db_engine():
    """In-memory SQLite for web API tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Import all models
    from models.admin import BotModeratorRole, GuildLanguageConfig, PermissionSubscriber  # noqa: F401
    from models.application import ApplicationForm, ApplicationQuestion  # noqa: F401
    from models.leavemsg import LeaveMessage  # noqa: F401
    from models.moderation import AutoDelete, AutoKicker  # noqa: F401
    from models.music import Playlist, PlaylistEntry  # noqa: F401
    from models.reactionrole import ReactionRoleEntry, ReactionRoleMessage  # noqa: F401
    from models.reminder import ReminderMessage  # noqa: F401
    from models.rolemanage import RoleMapping  # noqa: F401
    from models.tagging import Tag, TagEntry  # noqa: F401
    from models.wow import CraftingBoardConfig, CraftingOrder, CraftingRoleMapping, WowGuildNewsConfig  # noqa: F401

    BASE.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def web_db_session(web_db_engine):
    """DB session for web tests."""
    _session = sessionmaker(bind=web_db_engine)
    session = _session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def fake_valkey():
    """Dict-backed fake Valkey client."""
    from web.cache import ValkeyClient

    return ValkeyClient.create_fake()


@pytest.fixture
def web_config():
    """Minimal WebConfig for testing."""
    from web.config import WebConfig

    return WebConfig(
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="http://localhost:8000/api/auth/callback",
        jwt_secret="test_jwt_secret",
        jwt_expiry_hours=24,
        valkey_url="valkey://localhost:6379",
        ops=[111222333],
        db_connection_string="sqlite:///:memory:",
    )


@pytest.fixture
def client(web_db_engine, web_db_session, web_config, fake_valkey):
    """FastAPI TestClient with overridden dependencies."""
    from fastapi.testclient import TestClient

    from web.app import create_app
    from web.dependencies import get_config, get_db_session, get_valkey

    app = create_app(web_config, fake_valkey)

    def override_session():
        yield web_db_session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_config] = lambda: web_config
    app.dependency_overrides[get_valkey] = lambda: fake_valkey

    with TestClient(app) as tc:
        yield tc


def make_auth_header(user_id: str = "123456", username: str = "TestUser", secret: str = "test_jwt_secret") -> dict:
    """Create a valid Authorization header for testing."""
    from web.auth.jwt import create_access_token

    token = create_access_token(user_id=user_id, username=username, secret=secret, expiry_hours=1)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_header():
    """Auth header for a regular user."""
    return make_auth_header()


@pytest.fixture
def operator_header():
    """Auth header for an operator (user ID 111222333, matches web_config.ops)."""
    return make_auth_header(user_id="111222333", username="Operator")
