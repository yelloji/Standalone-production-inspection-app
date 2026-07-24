"""Portable local runtime composition used by the desktop process."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from backend.api.events import BoundedEventBroker
from backend.api.model_jobs import ModelJobDispatcher
from backend.api.reconstruction_jobs import ReconstructionJobDispatcher
from backend.api.routes import ApiServices
from backend.app.main import create_app
from backend.core.paths import ApplicationPaths
from backend.database.engine import (
    create_session_factory,
    create_sqlite_engine,
    database_path,
)
from backend.database.migration import upgrade_to_head
from backend.services.model_import import ModelImportService
from backend.services.model_library import ModelLibraryService
from backend.services.offline_reconstruction import OfflineReconstructionService
from backend.services.pipeline_lifecycle import PipelineLifecycleService


def create_runtime_app() -> FastAPI:
    resource_root = Path(__file__).resolve().parents[2]
    paths = ApplicationPaths.resolve(resource_root=resource_root)
    paths.ensure_data_layout()
    engine = create_sqlite_engine(database_path(paths))
    upgrade_to_head(engine)
    session_factory = create_session_factory(engine)
    model_jobs = ModelJobDispatcher(
        importer=ModelImportService(paths=paths, session_factory=session_factory),
        library=ModelLibraryService(paths=paths, session_factory=session_factory),
    )
    pipelines = PipelineLifecycleService(
        paths=paths,
        session_factory=session_factory,
    )
    application = create_app(
        ApiServices(
            session_factory=session_factory,
            commands=None,
            events=BoundedEventBroker(),
            model_jobs=model_jobs,
            pipelines=pipelines,
            reconstruction_jobs=ReconstructionJobDispatcher(
                OfflineReconstructionService(paths),
            ),
        )
    )
    application.state.database_engine = engine
    application.state.application_paths = paths
    return application


app = create_runtime_app()
