"""Persistent CUDA worker lifecycle, contract, and failure tests."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
import numpy.typing as npt
import pytest

from backend.core.paths import ApplicationPaths
from backend.domain.model_bundle import ModelManifest, SahiManifest
from backend.inference.onnx_worker import (
    CUDA_PROVIDER,
    InferenceInputError,
    InferenceOutOfMemoryError,
    InferenceOutputError,
    OnnxWorkerConfiguration,
    PersistentOnnxCudaWorker,
    ProviderUnavailableError,
    RuntimeSession,
    WorkerInitializationError,
    WorkerState,
    WorkerStateError,
)


@dataclass
class FakeMetadata:
    name: str
    shape: list[int | str | None]
    type: str


class FakeSession:
    def __init__(self) -> None:
        self.inputs = [FakeMetadata("images", ["batch", 3, 1312, 1312], "tensor(float16)")]
        self.outputs = [FakeMetadata("detections", ["batch", "detections", 6], "tensor(float16)")]
        self.providers = [CUDA_PROVIDER]
        self.run_calls = 0
        self.failure: Exception | None = None
        self.output_dtype: np.dtype[np.generic] = np.dtype(np.float16)

    def get_inputs(self) -> list[FakeMetadata]:
        return self.inputs

    def get_outputs(self) -> list[FakeMetadata]:
        return self.outputs

    def get_providers(self) -> list[str]:
        return self.providers

    def run(
        self,
        output_names: list[str],
        input_feed: dict[str, npt.NDArray[np.generic]],
    ) -> list[npt.NDArray[np.generic]]:
        self.run_calls += 1
        if self.failure is not None:
            raise self.failure
        batch = next(iter(input_feed.values())).shape[0]
        return [np.ones((batch, 2, 6), dtype=self.output_dtype)]


class FakeRuntime:
    def __init__(self, session: FakeSession | None = None) -> None:
        self.providers = [CUDA_PROVIDER]
        self.session = FakeSession() if session is None else session
        self.create_calls = 0

    def available_providers(self) -> list[str]:
        return self.providers

    def create_cuda_session(self, model_path: Path) -> RuntimeSession:
        self.create_calls += 1
        return cast(RuntimeSession, self.session)


def _paths(tmp_path: Path) -> ApplicationPaths:
    paths = ApplicationPaths.resolve(
        resource_root=tmp_path.resolve(),
        data_root=(tmp_path / "data").resolve(),
    )
    paths.ensure_data_layout()
    return paths


def _configuration(paths: ApplicationPaths) -> OnnxWorkerConfiguration:
    model_path = paths.resolve_data_path("models/crack-v1/model.onnx")
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"immutable onnx model")
    checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()
    return OnnxWorkerConfiguration(
        model_relative_path=paths.to_data_relative_path(model_path),
        model_sha256=checksum,
        model_manifest=ModelManifest.model_validate(
            {
                "schema_version": 1,
                "model_bundle_id": "crack-v1",
                "display_name": "Crack detector",
                "model_version": "1.0",
                "model_file": "model.onnx",
                "onnx_opset": 18,
                "required_execution_provider": CUDA_PROVIDER,
                "inputs": [
                    {
                        "name": "images",
                        "element_type": "float16",
                        "shape": ["batch", 3, 1312, 1312],
                    }
                ],
                "outputs": [
                    {
                        "name": "detections",
                        "element_type": "float16",
                        "shape": ["batch", "detections", 6],
                    }
                ],
            }
        ),
        sahi_manifest=SahiManifest(
            slice_width=1312,
            slice_height=1312,
            overlap_width_ratio=0.5,
            overlap_height_ratio=0.5,
            validated_batch_sizes=(1, 4),
        ),
        maximum_batch_size=4,
        warmup_runs=2,
    )


def _worker(
    tmp_path: Path,
    runtime: FakeRuntime | None = None,
) -> tuple[PersistentOnnxCudaWorker, FakeRuntime]:
    paths = _paths(tmp_path)
    selected_runtime = FakeRuntime() if runtime is None else runtime
    return (
        PersistentOnnxCudaWorker(
            paths=paths,
            configuration=_configuration(paths),
            runtime=selected_runtime,
        ),
        selected_runtime,
    )


def test_starts_once_warms_session_and_returns_immutable_raw_outputs(tmp_path: Path) -> None:
    worker, runtime = _worker(tmp_path)

    readiness = worker.start()
    repeated = worker.start()
    batch = np.zeros((2, 3, 1312, 1312), dtype=np.float16)
    result = worker.infer(request_id="request-001", input_tensor=batch)

    assert readiness == repeated
    assert readiness.provider == CUDA_PROVIDER
    assert readiness.maximum_batch_size == 4
    assert runtime.create_calls == 1
    assert runtime.session.run_calls == 3
    assert result.request_id == "request-001"
    assert result.batch_size == 2
    assert result.outputs[0].name == "detections"
    assert result.outputs[0].values.shape == (2, 2, 6)
    assert not result.outputs[0].values.flags.writeable
    with pytest.raises(ValueError):
        result.outputs[0].values[0, 0, 0] = 5


def test_missing_or_inactive_cuda_provider_fails_closed(tmp_path: Path) -> None:
    runtime = FakeRuntime()
    runtime.providers = ["CPUExecutionProvider"]
    worker, _ = _worker(tmp_path, runtime)
    with pytest.raises(ProviderUnavailableError):
        worker.start()
    assert worker.state is WorkerState.FAILED

    inactive_session = FakeSession()
    inactive_session.providers = ["CPUExecutionProvider"]
    worker, _ = _worker(tmp_path / "inactive", FakeRuntime(inactive_session))
    with pytest.raises(ProviderUnavailableError):
        worker.start()
    assert worker.state is WorkerState.FAILED


def test_model_checksum_and_runtime_io_mismatch_fail_initialization(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    configuration = _configuration(paths)
    paths.resolve_data_path(configuration.model_relative_path).write_bytes(b"tampered")
    worker = PersistentOnnxCudaWorker(
        paths=paths,
        configuration=configuration,
        runtime=FakeRuntime(),
    )
    with pytest.raises(WorkerInitializationError, match="checksum"):
        worker.start()

    session = FakeSession()
    session.outputs[0].name = "wrong-output"
    worker, _ = _worker(tmp_path / "io", FakeRuntime(session))
    with pytest.raises(WorkerInitializationError, match="output contract"):
        worker.start()


def test_rejects_wrong_dtype_geometry_batch_and_noncontiguous_input(tmp_path: Path) -> None:
    worker, _ = _worker(tmp_path)
    worker.start()

    invalid = (
        np.zeros((1, 3, 1312, 1312), dtype=np.float32),
        np.zeros((1, 3, 100, 100), dtype=np.float16),
        np.zeros((5, 3, 1312, 1312), dtype=np.float16),
        np.zeros((1, 3, 1312, 1312), dtype=np.float16)[:, :, :, ::-1],
    )
    for tensor in invalid:
        with pytest.raises(InferenceInputError):
            worker.infer(request_id="invalid", input_tensor=tensor)


def test_oom_and_invalid_outputs_are_distinct_failures(tmp_path: Path) -> None:
    session = FakeSession()
    session.failure = RuntimeError("CUDA_ERROR_OUT_OF_MEMORY")
    worker, _ = _worker(tmp_path, FakeRuntime(session))
    with pytest.raises(InferenceOutOfMemoryError):
        worker.start()
    assert worker.state is WorkerState.FAILED

    session = FakeSession()
    worker, _ = _worker(tmp_path / "output", FakeRuntime(session))
    worker.start()
    session.output_dtype = np.dtype(np.float32)
    tensor = np.zeros((1, 3, 1312, 1312), dtype=np.float16)
    with pytest.raises(InferenceOutputError):
        worker.infer(request_id="bad-output", input_tensor=tensor)


def test_invalid_warmup_output_prevents_readiness(tmp_path: Path) -> None:
    session = FakeSession()
    session.output_dtype = np.dtype(np.float32)
    worker, _ = _worker(tmp_path, FakeRuntime(session))

    with pytest.raises(InferenceOutputError):
        worker.start()

    assert worker.state is WorkerState.FAILED


def test_close_is_terminal_and_inference_requires_readiness(tmp_path: Path) -> None:
    worker, _ = _worker(tmp_path)
    tensor = np.zeros((1, 3, 1312, 1312), dtype=np.float16)
    with pytest.raises(WorkerStateError):
        worker.infer(request_id="too-early", input_tensor=tensor)
    worker.start()
    worker.close()
    assert worker.state is WorkerState.CLOSED
    with pytest.raises(WorkerStateError):
        worker.start()
    with pytest.raises(WorkerStateError):
        worker.infer(request_id="too-late", input_tensor=tensor)
