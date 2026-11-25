"""FastAPI application factory for source-extract."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from source_extract import __version__
from source_extract.api.routers import adapters, commands, datasets, health, jobs, models, review
from source_extract.constants.api_tags import API_TAGS


def create_app() -> FastAPI:
    # Behind nginx, uvicorn is started with ``--root-path /source-extractor`` so
    # Swagger/ReDoc fetch ``/source-extractor/openapi.json`` instead of ``/openapi.json``.
    app = FastAPI(
        title="source-extract",
        description="Single entry point for source extract: adapters, commands, jobs, review, models.",
        version=__version__,
        openapi_tags=[{"name": t} for t in API_TAGS],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(adapters.router, prefix="/api/v1")
    app.include_router(commands.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(models.router, prefix="/api/v1")
    app.include_router(datasets.router, prefix="/api/v1")
    app.include_router(review.router, prefix="/api/v1")

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "source-extract", "docs": "/docs", "api": "/api/v1/health"}

    return app


app = create_app()
