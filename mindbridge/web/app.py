"""FastAPI application factory.

`create_app()` builds the app (CORS, table creation on startup, routers, health); a module-level
`app` is exposed so `uvicorn mindbridge.web.app:app` works. The web layer is a thin wrapper — all
matching logic stays in the engine, reached through `web.services`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mindbridge.config import settings
from mindbridge.web.db import init_db
from mindbridge.web.routers import auth, jobs, match, profile
from mindbridge.web import services


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup. Cheap and idempotent; keeps first-run zero-config.
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="MindBridge.ai API",
        version="0.2.0",
        summary="Two-sided job⇄talent matching — the M1 engine, served over HTTP.",
        lifespan=lifespan,
    )

    origins = list(settings.cors_origins)
    allow_credentials = True
    if "*" in origins:
        origins = ["*"]
        allow_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        """Liveness + which engine backends are active (embedder/reranker)."""
        return {"status": "ok", **services.engine_info()}

    @app.get("/", tags=["meta"])
    def root() -> dict:
        return {"name": "MindBridge.ai API", "version": "0.2.0", "docs": "/docs"}

    app.include_router(auth.router)
    app.include_router(jobs.router)
    app.include_router(match.router)
    app.include_router(profile.router)
    return app


app = create_app()
