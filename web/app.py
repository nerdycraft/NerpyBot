"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

if TYPE_CHECKING:
    from web.config import WebConfig
    from web.cache import ValkeyClient


def create_app(
    config: WebConfig | None = None,
    valkey_client: ValkeyClient | None = None,
    config_path: Path | str | None = None,
    spa_dist: Path | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Config resolution order:
    1. Explicit ``config`` parameter (used by tests)
    2. Load from ``config_path`` (or ``./config.yaml`` if None) + env var overlay
    """
    from web.cache import ValkeyClient
    from web.config import WebConfig
    from web.dependencies import _TEST_MODE, get_config, get_db_session, get_valkey
    from web.routes import auth, guilds, health, legal, operator, support, wow

    if config is None:
        config = WebConfig.load(config_path)

    # Configure log level for the whole web package
    level = getattr(logging, config.log_level.upper(), logging.INFO)
    web_log = logging.getLogger("web")
    web_log.setLevel(level)
    if not web_log.handlers:
        _handler = logging.StreamHandler()
        _handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
        web_log.addHandler(_handler)
    web_log.info("log level: %s", config.log_level)

    engine_kwargs = {}
    if config.db_connection_string.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(config.db_connection_string, **engine_kwargs)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    if valkey_client is None:
        if _TEST_MODE:
            valkey_client = ValkeyClient.create_fake()
        else:
            valkey_client = ValkeyClient.create(config.valkey_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Initialize app state on startup and clean up on shutdown."""
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.config = config
        app.state.valkey = valkey_client
        yield
        valkey_client.close()
        engine.dispose()

    app = FastAPI(
        title="NerpyBot Dashboard API",
        description="Management API for NerpyBot Discord bot",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Wire up dependency defaults
    app.dependency_overrides[get_config] = lambda: config
    app.dependency_overrides[get_valkey] = lambda: valkey_client

    def _get_db_session():
        """Yield a SQLAlchemy session, committing on success and rolling back on error."""
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = _get_db_session

    # Register routers
    app.include_router(auth.router, prefix="/api")
    app.include_router(guilds.router, prefix="/api")
    app.include_router(health.router, prefix="/api")
    app.include_router(operator.router, prefix="/api")
    app.include_router(wow.router, prefix="/api")
    app.include_router(legal.router, prefix="/api")
    app.include_router(support.router, prefix="/api")

    # Serve Vue SPA — mount assets then catch-all for client-side routing
    _dist = spa_dist or Path(__file__).parent / "frontend" / "dist"
    _assets = _dist / "assets"
    if _dist.exists() and _assets.exists():
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles

        app.mount("/assets", StaticFiles(directory=str(_assets)), name="spa-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            from fastapi import HTTPException as _HTTPException

            if full_path == "api" or full_path.startswith("api/"):
                raise _HTTPException(status_code=404, detail="Not Found")
            dist_root = _dist.resolve()
            candidate = (dist_root / full_path).resolve()
            if candidate.is_file() and dist_root in candidate.parents:
                return FileResponse(str(candidate))
            return FileResponse(str(_dist / "index.html"))

    return app
