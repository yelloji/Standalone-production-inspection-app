"""FastAPI composition root for the standalone production application."""

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from backend import __version__


class HealthResponse(BaseModel):
    """Stable readiness response used by the desktop shell and diagnostics."""

    model_config = ConfigDict(frozen=True)

    status: str
    service: str
    version: str


def create_app() -> FastAPI:
    """Create the local backend without starting workers or production services."""

    application = FastAPI(
        title="Standalone Production Inspection API",
        version=__version__,
    )

    @application.get("/api/v1/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ready",
            service="standalone-production-inspection-backend",
            version=__version__,
        )

    return application


app = create_app()
