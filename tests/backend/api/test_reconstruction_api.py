"""Offline reconstruction job API tests."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.events import BoundedEventBroker
from backend.api.reconstruction_jobs import ReconstructionJobDispatcher
from backend.api.routes import ApiServices
from backend.app.main import create_app
from backend.core.paths import ApplicationPaths
from backend.domain.contracts import DiscSide
from backend.reconstruction.preview import ReconstructionPreview
from backend.services.offline_reconstruction import OfflineReconstructionResult


class FakeReconstructionService:
    def __init__(self, paths: ApplicationPaths) -> None:
        self.paths = paths

    def reconstruct(
        self,
        *,
        source_directory: Path,
        side: DiscSide,
        preview_size: int,
        progress: object,
    ) -> OfflineReconstructionResult:
        del source_directory
        assert preview_size == 5000
        assert callable(progress)
        progress("registering", 16, 16)
        relative = "completed/fake/reconstructed-preview.png"
        preview_path = self.paths.resolve_data_path(relative)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        return OfflineReconstructionResult(
            acquisition_id="offline-fake",
            side=side,
            source_names=tuple(f"{index}.jpg" for index in range(1, 17)),
            production_approved=False,
            validation_median_px=0.47,
            validation_p95_px=0.84,
            validation_maximum_px=2.03,
            passed_join_count=11,
            total_join_count=16,
            preview=ReconstructionPreview(
                relative_path=relative,
                sha256="0" * 64,
                size_bytes=12,
                width=5000,
                height=5000,
                source_canvas_width=32000,
                source_canvas_height=31840,
            ),
            report_relative_path="completed/fake/reconstruction-report.json",
            failure_reasons=("maximum held-out error exceeds profile limit",),
        )


def test_submit_poll_and_preview_reconstruction_job(tmp_path: Path) -> None:
    paths = ApplicationPaths.resolve(resource_root=tmp_path, data_root=tmp_path / "data")
    paths.ensure_data_layout()
    jobs = ReconstructionJobDispatcher(FakeReconstructionService(paths))  # type: ignore[arg-type]
    services = ApiServices(
        session_factory=None,
        commands=None,
        events=BoundedEventBroker(),
        reconstruction_jobs=jobs,
    )
    with TestClient(create_app(services)) as client:
        submitted = client.post(
            "/api/v1/reconstruction-jobs",
            json={"source_path": str(tmp_path), "side": "lower"},
        )
        assert submitted.status_code == 202
        job_id = submitted.json()["job_id"]
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            completed = client.get(f"/api/v1/reconstruction-jobs/{job_id}")
            if completed.json()["status"] == "completed":
                break
            time.sleep(0.01)
        payload = completed.json()
        assert payload["production_approved"] is False
        assert payload["validation_median_px"] == 0.47
        assert payload["passed_join_count"] == 11
        assert payload["preview_width"] == 5000
        assert payload["preview_height"] == 5000
        assert payload["preview_relative_path"].endswith("reconstructed-preview.png")
        preview = client.get(payload["preview_url"])
        assert preview.status_code == 200
        assert preview.headers["content-type"] == "image/png"


def test_reconstruction_job_rejects_invalid_side_and_unknown_job(tmp_path: Path) -> None:
    paths = ApplicationPaths.resolve(resource_root=tmp_path, data_root=tmp_path / "data")
    paths.ensure_data_layout()
    jobs = ReconstructionJobDispatcher(FakeReconstructionService(paths))  # type: ignore[arg-type]
    services = ApiServices(
        session_factory=None,
        commands=None,
        events=BoundedEventBroker(),
        reconstruction_jobs=jobs,
    )
    with TestClient(create_app(services)) as client:
        invalid = client.post(
            "/api/v1/reconstruction-jobs",
            json={"source_path": str(tmp_path), "side": "unknown"},
        )
        assert invalid.status_code == 422
        assert client.get("/api/v1/reconstruction-jobs/missing").status_code == 404
