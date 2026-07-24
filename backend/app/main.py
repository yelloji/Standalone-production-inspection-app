"""FastAPI composition root for the standalone production application."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from backend import __version__
from backend.api.contracts import HealthResponse
from backend.api.events import BoundedEventBroker
from backend.api.routes import ApiServices, create_api_router


def create_app(services: ApiServices | None = None) -> FastAPI:
    """Create a local API with injectable database and background command services."""

    selected = (
        ApiServices(
            session_factory=None,
            commands=None,
            events=BoundedEventBroker(),
        )
        if services is None
        else services
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        del application
        if selected.commands is not None:
            selected.commands.start()
        try:
            yield
        finally:
            if selected.commands is not None:
                selected.commands.close()
            if selected.model_jobs is not None:
                selected.model_jobs.close()
            if selected.reconstruction_jobs is not None:
                selected.reconstruction_jobs.close()

    application = FastAPI(
        title="Standalone Production Inspection API",
        version=__version__,
        lifespan=lifespan,
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @application.get("/api/v1/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ready",
            service="standalone-production-inspection-backend",
            version=__version__,
        )

    application.include_router(create_api_router(selected))
    return application


app = create_app()
