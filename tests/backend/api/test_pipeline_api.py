"""Typed modular pipeline lifecycle API tests."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from backend.api.events import BoundedEventBroker
from backend.api.routes import ApiServices
from backend.app.main import create_app
from backend.core.paths import ApplicationPaths
from backend.services.pipeline_lifecycle import PipelineLifecycleService


def _request() -> dict[str, object]:
    return {
        "pipeline_id": "brake-disc",
        "display_name": "Brake Disc Inspection",
        "model_bundle_id": None,
        "acquisition": {
            "source": "online",
            "expected_frame_count": 16,
            "ordered": True,
            "side": "upper",
            "mode": "automatic_folder",
            "automatic": {
                "filename_template": "{cycle}_{position}.jpg",
                "position_width": 2,
                "stable_for_milliseconds": 1500,
                "incomplete_cycle_timeout_seconds": 120,
            },
        },
        "inference": {
            "enabled": False,
            "mode": None,
            "confidence_threshold": None,
            "sahi": None,
        },
        "reconstruction": {
            "enabled": True,
            "segment_count": 16,
            "degrees_per_segment": 22.5,
        },
    }


def test_pipeline_draft_validation_activation_and_active_resolution(
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    application_paths.ensure_data_layout()
    events = BoundedEventBroker()
    lifecycle = PipelineLifecycleService(
        paths=application_paths,
        session_factory=session_factory,
    )
    services = ApiServices(
        session_factory=session_factory,
        commands=None,
        events=events,
        pipelines=lifecycle,
    )

    with TestClient(create_app(services)) as client:
        assert client.get("/api/v1/pipelines/active").json() is None
        created = client.post("/api/v1/pipelines", json=_request())
        assert created.status_code == 201
        assert created.json()["state"] == "draft"
        assert created.json()["reconstruction_enabled"] is True
        assert created.json()["inference_enabled"] is False
        assert created.json()["acquisition_mode"] == "automatic_folder"
        assert created.json()["filename_template"] == "{cycle}_{position}.jpg"

        snapshot_id = created.json()["pipeline_snapshot_id"]
        validated = client.post(f"/api/v1/pipelines/{snapshot_id}/validate")
        assert validated.status_code == 200
        assert validated.json()["state"] == "validated"

        active = client.post(f"/api/v1/pipelines/{snapshot_id}/activate")
        assert active.status_code == 200
        assert active.json()["state"] == "active"
        assert client.get("/api/v1/pipelines/active").json() == active.json()
        assert events.read(after_sequence=0, limit=10).events[0].event_type == (
            "pipeline_activated"
        )


def test_invalid_pipeline_transitions_are_rejected(
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    application_paths.ensure_data_layout()
    lifecycle = PipelineLifecycleService(
        paths=application_paths,
        session_factory=session_factory,
    )
    with TestClient(
        create_app(
            ApiServices(
                session_factory=session_factory,
                commands=None,
                events=BoundedEventBroker(),
                pipelines=lifecycle,
            )
        )
    ) as client:
        created = client.post("/api/v1/pipelines", json=_request()).json()
        snapshot_id = created["pipeline_snapshot_id"]
        assert client.post(f"/api/v1/pipelines/{snapshot_id}/activate").status_code == 409
        assert client.post("/api/v1/pipelines/missing/validate").status_code == 404
