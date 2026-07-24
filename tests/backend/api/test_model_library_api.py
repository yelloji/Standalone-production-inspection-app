import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from backend.api.events import BoundedEventBroker
from backend.api.model_jobs import ModelJobDispatcher
from backend.api.routes import ApiServices
from backend.app.main import create_app
from backend.core.paths import ApplicationPaths
from backend.services.model_import import ModelImportService
from backend.services.model_library import ModelLibraryService
from tests.backend.model_bundle_factory import create_model_bundle, zip_bundle


def test_background_import_archive_and_delete_api(
    tmp_path: Path,
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    bundle = create_model_bundle(tmp_path / "bundle", model_bundle_id="library-model")
    archive = zip_bundle(bundle, tmp_path / "library-model.zip")
    jobs = ModelJobDispatcher(
        importer=ModelImportService(
            paths=application_paths,
            session_factory=session_factory,
        ),
        library=ModelLibraryService(
            paths=application_paths,
            session_factory=session_factory,
        ),
    )
    services = ApiServices(
        session_factory=session_factory,
        commands=None,
        events=BoundedEventBroker(),
        model_jobs=jobs,
    )

    with TestClient(create_app(services)) as client:
        imported = client.post(
            "/api/v1/models/import",
            json={"source_path": str(archive)},
        )
        assert imported.status_code == 202
        completed = _wait_for_job(client, imported.json()["job_id"])
        assert completed["status"] == "completed"
        assert completed["model_bundle_id"] == "library-model"

        models = client.get("/api/v1/models").json()
        assert models[0]["can_archive"] is True
        assert models[0]["can_delete"] is False

        archived = client.post("/api/v1/models/library-model/archive")
        assert archived.status_code == 202
        assert _wait_for_job(client, archived.json()["job_id"])["status"] == "completed"
        archived_model = client.get("/api/v1/models").json()[0]
        assert archived_model["state"] == "retired"
        assert archived_model["can_delete"] is True

        deleted = client.post("/api/v1/models/library-model/delete")
        assert deleted.status_code == 202
        assert _wait_for_job(client, deleted.json()["job_id"])["status"] == "completed"
        assert client.get("/api/v1/models").json() == []


def test_model_jobs_fail_safely_and_unknown_resources_return_404(
    tmp_path: Path,
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    jobs = ModelJobDispatcher(
        importer=ModelImportService(
            paths=application_paths,
            session_factory=session_factory,
        ),
        library=ModelLibraryService(
            paths=application_paths,
            session_factory=session_factory,
        ),
    )
    services = ApiServices(
        session_factory=session_factory,
        commands=None,
        events=BoundedEventBroker(),
        model_jobs=jobs,
    )

    with TestClient(create_app(services)) as client:
        submitted = client.post(
            "/api/v1/models/import",
            json={"source_path": str(tmp_path / "missing.zip")},
        )
        failed = _wait_for_job(client, submitted.json()["job_id"])
        assert failed["status"] == "failed"
        assert failed["message"] == "the selected model bundle is no longer available"
        assert client.get("/api/v1/model-jobs/missing").status_code == 404
        assert client.post("/api/v1/models/missing/archive").status_code == 404


def _wait_for_job(client: TestClient, job_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        payload: dict[str, object] = client.get(f"/api/v1/model-jobs/{job_id}").json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("model job did not finish")
