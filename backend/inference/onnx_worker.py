"""Persistent fail-closed ONNX Runtime CUDA inference worker."""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
import numpy.typing as npt
import onnxruntime as ort  # type: ignore[import-untyped]

from backend.core.paths import ApplicationPaths
from backend.domain.model_bundle import ModelManifest, SahiManifest, TensorSpecification
from backend.domain.value_objects import normalize_relative_path

CUDA_PROVIDER = "CUDAExecutionProvider"


class OnnxWorkerError(RuntimeError):
    """Base class for stable worker failures surfaced to orchestration."""

    code = "onnx_worker_error"


class ProviderUnavailableError(OnnxWorkerError):
    code = "cuda_provider_unavailable"


class WorkerInitializationError(OnnxWorkerError):
    code = "worker_initialization_failed"


class WorkerStateError(OnnxWorkerError):
    code = "worker_state_invalid"


class InferenceInputError(OnnxWorkerError):
    code = "inference_input_invalid"


class InferenceOutputError(OnnxWorkerError):
    code = "inference_output_invalid"


class InferenceExecutionError(OnnxWorkerError):
    code = "inference_execution_failed"


class InferenceOutOfMemoryError(InferenceExecutionError):
    code = "gpu_out_of_memory"


class WorkerState(str, Enum):
    CREATED = "created"
    READY = "ready"
    FAILED = "failed"
    CLOSED = "closed"


class RuntimeTensorMetadata(Protocol):
    name: str
    shape: Sequence[int | str | None]
    type: str


class RuntimeSession(Protocol):
    def get_inputs(self) -> Sequence[RuntimeTensorMetadata]: ...

    def get_outputs(self) -> Sequence[RuntimeTensorMetadata]: ...

    def get_providers(self) -> Sequence[str]: ...

    def run(
        self,
        output_names: Sequence[str],
        input_feed: dict[str, npt.NDArray[np.generic]],
    ) -> Sequence[Any]: ...


class RuntimeAdapter(Protocol):
    def available_providers(self) -> Sequence[str]: ...

    def create_cuda_session(self, model_path: Path) -> RuntimeSession: ...


class OnnxRuntimeAdapter:
    """Small adapter that makes the native runtime injectable in unit tests."""

    def available_providers(self) -> Sequence[str]:
        return cast(Sequence[str], ort.get_available_providers())

    def create_cuda_session(self, model_path: Path) -> RuntimeSession:
        options = ort.SessionOptions()
        options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
        session = ort.InferenceSession(
            str(model_path),
            sess_options=options,
            providers=[CUDA_PROVIDER],
        )
        return cast(RuntimeSession, session)


@dataclass(frozen=True, slots=True)
class OnnxWorkerConfiguration:
    model_relative_path: str
    model_sha256: str
    model_manifest: ModelManifest
    sahi_manifest: SahiManifest
    maximum_batch_size: int
    warmup_runs: int = 1

    def __post_init__(self) -> None:
        normalize_relative_path(self.model_relative_path)
        if len(self.model_sha256) != 64 or any(
            character not in "0123456789abcdefABCDEF" for character in self.model_sha256
        ):
            raise ValueError("worker model requires a SHA-256 value")
        if self.model_manifest.required_execution_provider != CUDA_PROVIDER:
            raise ValueError("production worker requires CUDAExecutionProvider")
        if len(self.model_manifest.inputs) != 1:
            raise ValueError("production worker currently requires exactly one model input")
        primary = self.model_manifest.inputs[0]
        if primary.element_type != "float16":
            raise ValueError("production CUDA worker requires an FP16 model input")
        if primary.shape[1] != 3:
            raise ValueError("production worker requires a three-channel NCHW model input")
        if isinstance(primary.shape[0], int) and primary.shape[0] != self.maximum_batch_size:
            raise ValueError("static model batch must equal the configured maximum batch size")
        if self.maximum_batch_size not in self.sahi_manifest.validated_batch_sizes:
            raise ValueError("maximum batch size is not validated by the model bundle")
        if self.warmup_runs < 1 or self.warmup_runs > 10:
            raise ValueError("warm-up run count must be from 1 through 10")


@dataclass(frozen=True, slots=True)
class WorkerReadiness:
    model_sha256: str
    provider: str
    maximum_batch_size: int
    warmup_runs: int


@dataclass(frozen=True, slots=True)
class RawOutputTensor:
    name: str
    values: npt.NDArray[np.generic]


@dataclass(frozen=True, slots=True)
class RawPredictionBatch:
    request_id: str
    model_sha256: str
    batch_size: int
    elapsed_milliseconds: float
    outputs: tuple[RawOutputTensor, ...]


class PersistentOnnxCudaWorker:
    """Own exactly one warmed CUDA session and never fall back to CPU."""

    def __init__(
        self,
        *,
        paths: ApplicationPaths,
        configuration: OnnxWorkerConfiguration,
        runtime: RuntimeAdapter | None = None,
    ) -> None:
        self._paths = paths
        self._configuration = configuration
        self._runtime = OnnxRuntimeAdapter() if runtime is None else runtime
        self._state = WorkerState.CREATED
        self._session: RuntimeSession | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> WorkerState:
        return self._state

    def start(self) -> WorkerReadiness:
        with self._lock:
            if self._state is WorkerState.READY:
                return self._readiness()
            if self._state is not WorkerState.CREATED:
                raise WorkerStateError(f"worker cannot start from {self._state.value} state")
            try:
                model_path = self._verified_model_path()
                if CUDA_PROVIDER not in self._runtime.available_providers():
                    raise ProviderUnavailableError("CUDAExecutionProvider is unavailable")
                session = self._runtime.create_cuda_session(model_path)
                self._validate_session(session)
                self._session = session
                warmup = self._warmup_tensor()
                output_names = [item.name for item in self._configuration.model_manifest.outputs]
                for _ in range(self._configuration.warmup_runs):
                    warmup_outputs = self._run_session(session, output_names, warmup)
                    self._validated_outputs(warmup_outputs, int(warmup.shape[0]))
                self._state = WorkerState.READY
                return self._readiness()
            except OnnxWorkerError:
                self._session = None
                self._state = WorkerState.FAILED
                raise
            except Exception as error:
                self._session = None
                self._state = WorkerState.FAILED
                raise WorkerInitializationError(
                    f"CUDA session initialization failed: {type(error).__name__}"
                ) from error

    def infer(
        self,
        *,
        request_id: str,
        input_tensor: npt.NDArray[np.generic],
    ) -> RawPredictionBatch:
        if not request_id.strip():
            raise InferenceInputError("inference request identifier must not be empty")
        with self._lock:
            if self._state is not WorkerState.READY or self._session is None:
                raise WorkerStateError("worker is not ready")
            batch_size = self._validate_input(input_tensor)
            output_names = [item.name for item in self._configuration.model_manifest.outputs]
            started = time.perf_counter()
            raw_outputs = self._run_session(self._session, output_names, input_tensor)
            elapsed = (time.perf_counter() - started) * 1000.0
            outputs = self._validated_outputs(raw_outputs, batch_size)
            return RawPredictionBatch(
                request_id=request_id,
                model_sha256=self._configuration.model_sha256.lower(),
                batch_size=batch_size,
                elapsed_milliseconds=elapsed,
                outputs=outputs,
            )

    def close(self) -> None:
        with self._lock:
            self._session = None
            self._state = WorkerState.CLOSED

    def _verified_model_path(self) -> Path:
        path = self._paths.resolve_data_path(self._configuration.model_relative_path)
        if not path.is_file() or path.is_symlink():
            raise WorkerInitializationError("configured ONNX model is not a regular file")
        if _file_sha256(path) != self._configuration.model_sha256.lower():
            raise WorkerInitializationError("configured ONNX model checksum mismatch")
        return path

    def _validate_session(self, session: RuntimeSession) -> None:
        providers = tuple(session.get_providers())
        if not providers or providers[0] != CUDA_PROVIDER:
            raise ProviderUnavailableError("session did not activate CUDAExecutionProvider")
        self._validate_metadata(
            session.get_inputs(), self._configuration.model_manifest.inputs, "input"
        )
        self._validate_metadata(
            session.get_outputs(), self._configuration.model_manifest.outputs, "output"
        )

    def _validate_metadata(
        self,
        actual: Sequence[RuntimeTensorMetadata],
        expected: Sequence[TensorSpecification],
        kind: str,
    ) -> None:
        if len(actual) != len(expected):
            raise WorkerInitializationError(f"runtime {kind} count differs from manifest")
        for runtime_tensor, specification in zip(actual, expected, strict=True):
            expected_type = f"tensor({specification.element_type})"
            if (
                runtime_tensor.name != specification.name
                or runtime_tensor.type != expected_type
                or tuple(runtime_tensor.shape) != specification.shape
            ):
                raise WorkerInitializationError(
                    f"runtime {kind} contract differs for {specification.name}"
                )

    def _warmup_tensor(self) -> npt.NDArray[np.float16]:
        specification = self._configuration.model_manifest.inputs[0]
        dimensions = [
            1 if isinstance(dimension, str) else dimension for dimension in specification.shape
        ]
        if isinstance(specification.shape[0], int):
            dimensions[0] = specification.shape[0]
        return np.zeros(tuple(dimensions), dtype=np.float16)

    def _validate_input(self, input_tensor: npt.NDArray[np.generic]) -> int:
        specification = self._configuration.model_manifest.inputs[0]
        if input_tensor.dtype != np.dtype(np.float16):
            raise InferenceInputError("inference input must use model FP16 dtype")
        if not input_tensor.flags.c_contiguous:
            raise InferenceInputError("inference input must be C-contiguous")
        if input_tensor.ndim != len(specification.shape):
            raise InferenceInputError("inference input rank differs from model")
        batch_size = int(input_tensor.shape[0])
        if batch_size < 1 or batch_size > self._configuration.maximum_batch_size:
            raise InferenceInputError("inference batch is outside the configured bound")
        for axis, (actual, expected) in enumerate(
            zip(input_tensor.shape, specification.shape, strict=True)
        ):
            if isinstance(expected, int) and actual != expected:
                raise InferenceInputError(f"inference input dimension {axis} differs from model")
        return batch_size

    def _run_session(
        self,
        session: RuntimeSession,
        output_names: Sequence[str],
        input_tensor: npt.NDArray[np.generic],
    ) -> Sequence[Any]:
        input_name = self._configuration.model_manifest.inputs[0].name
        try:
            return session.run(output_names, {input_name: input_tensor})
        except Exception as error:
            message = str(error).casefold()
            if "out of memory" in message or "cuda_error_out_of_memory" in message:
                raise InferenceOutOfMemoryError("CUDA inference ran out of GPU memory") from error
            raise InferenceExecutionError(
                f"CUDA inference failed: {type(error).__name__}"
            ) from error

    def _validated_outputs(
        self,
        raw_outputs: Sequence[Any],
        batch_size: int,
    ) -> tuple[RawOutputTensor, ...]:
        specifications = self._configuration.model_manifest.outputs
        if len(raw_outputs) != len(specifications):
            raise InferenceOutputError("runtime output count differs from manifest")
        validated = []
        for value, specification in zip(raw_outputs, specifications, strict=True):
            array = np.asarray(value)
            expected_dtype = np.dtype(specification.element_type)
            if array.dtype != expected_dtype or array.ndim != len(specification.shape):
                raise InferenceOutputError(
                    f"runtime output type or rank differs for {specification.name}"
                )
            for axis, (actual, expected) in enumerate(
                zip(array.shape, specification.shape, strict=True)
            ):
                expected_dimension = (
                    batch_size if axis == 0 and isinstance(expected, str) else expected
                )
                if isinstance(expected_dimension, int) and actual != expected_dimension:
                    raise InferenceOutputError(
                        f"runtime output dimension {axis} differs for {specification.name}"
                    )
            immutable = np.array(array, copy=True, order="C")
            immutable.setflags(write=False)
            validated.append(RawOutputTensor(name=specification.name, values=immutable))
        return tuple(validated)

    def _readiness(self) -> WorkerReadiness:
        return WorkerReadiness(
            model_sha256=self._configuration.model_sha256.lower(),
            provider=CUDA_PROVIDER,
            maximum_batch_size=self._configuration.maximum_batch_size,
            warmup_runs=self._configuration.warmup_runs,
        )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
