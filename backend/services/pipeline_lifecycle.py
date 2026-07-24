"""Versioned modular pipeline persistence, validation, and activation."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.core.configuration import AtomicConfigurationStore
from backend.core.paths import ApplicationPaths
from backend.core.serialization import canonical_checksum
from backend.database.engine import transaction
from backend.database.models import utc_now
from backend.database.records import PipelineSnapshotMetadata
from backend.database.repositories import MetadataRepository
from backend.domain.contracts import (
    AcquisitionConfiguration,
    InferenceConfiguration,
    PipelineContract,
    ReconstructionConfiguration,
)


class PipelineLifecycleError(RuntimeError):
    """Raised when a pipeline lifecycle transition is unsafe."""


@dataclass(frozen=True, slots=True)
class PipelineDraft:
    pipeline_id: str
    display_name: str
    model_bundle_id: str | None
    acquisition: AcquisitionConfiguration
    inference: InferenceConfiguration
    reconstruction: ReconstructionConfiguration


class PipelineLifecycleService:
    """Own immutable contract files and their transactional database lifecycle."""

    def __init__(
        self,
        *,
        paths: ApplicationPaths,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._paths = paths
        self._session_factory = session_factory
        self._store = AtomicConfigurationStore(
            paths=paths,
            model_type=PipelineContract,
        )
        self._create_lock = Lock()

    def create_draft(self, draft: PipelineDraft) -> PipelineSnapshotMetadata:
        relative_path: str | None = None
        with self._create_lock:
            try:
                with transaction(self._session_factory) as session:
                    repository = MetadataRepository(session)
                    revision = repository.next_pipeline_revision(draft.pipeline_id)
                    self._validate_model(
                        repository,
                        draft.model_bundle_id,
                        draft.inference.enabled,
                    )
                    try:
                        contract = PipelineContract(
                            pipeline_id=draft.pipeline_id,
                            revision=revision,
                            display_name=draft.display_name,
                            model_bundle_id=draft.model_bundle_id,
                            acquisition=draft.acquisition,
                            inference=draft.inference,
                            reconstruction=draft.reconstruction,
                        )
                    except ValidationError as error:
                        raise PipelineLifecycleError(
                            "pipeline stage configuration is invalid"
                        ) from error
                    snapshot_id = f"{draft.pipeline_id}-r{revision}"
                    relative_path = f"pipelines/{snapshot_id}.json"
                    checksum = self._store.save(relative_path, contract)
                    value = PipelineSnapshotMetadata(
                        pipeline_snapshot_id=snapshot_id,
                        pipeline_id=draft.pipeline_id,
                        revision=revision,
                        display_name=draft.display_name,
                        state="draft",
                        model_bundle_id=draft.model_bundle_id,
                        contract_path=relative_path,
                        sha256=checksum,
                        created_at=utc_now(),
                    )
                    repository.add_pipeline_snapshot(value)
                return value
            except BaseException:
                if relative_path is not None:
                    self._paths.resolve_data_path(relative_path).unlink(missing_ok=True)
                raise

    def validate(self, pipeline_snapshot_id: str) -> PipelineSnapshotMetadata:
        with transaction(self._session_factory) as session:
            repository = MetadataRepository(session)
            value = self._required(repository, pipeline_snapshot_id)
            if value.state != "draft":
                raise PipelineLifecycleError("only a draft pipeline can be validated")
            contract = self._load_verified(value)
            self._validate_model(
                repository,
                contract.model_bundle_id,
                contract.inference.enabled,
            )
            repository.set_pipeline_snapshot_state(pipeline_snapshot_id, "validated")
            return self._required(repository, pipeline_snapshot_id)

    def approve_and_activate(
        self,
        pipeline_snapshot_id: str,
    ) -> PipelineSnapshotMetadata:
        try:
            with transaction(self._session_factory) as session:
                repository = MetadataRepository(session)
                requested = self._required(repository, pipeline_snapshot_id)
                if requested.state not in {"validated", "approved"}:
                    raise PipelineLifecycleError("pipeline must be validated before activation")
                contract = self._load_verified(requested)
                self._validate_model(
                    repository,
                    contract.model_bundle_id,
                    contract.inference.enabled,
                )
                active = repository.get_active_pipeline_snapshot()
                if active is not None and active.pipeline_snapshot_id != pipeline_snapshot_id:
                    repository.set_pipeline_snapshot_state(
                        active.pipeline_snapshot_id,
                        "approved",
                    )
                repository.set_pipeline_snapshot_state(pipeline_snapshot_id, "active")
                return self._required(repository, pipeline_snapshot_id)
        except IntegrityError as error:
            raise PipelineLifecycleError(
                "another pipeline became active; refresh and try again"
            ) from error

    def get_contract(self, value: PipelineSnapshotMetadata) -> PipelineContract:
        return self._load_verified(value)

    def _load_verified(self, value: PipelineSnapshotMetadata) -> PipelineContract:
        try:
            contract = self._store.load(value.contract_path)
        except (OSError, ValidationError) as error:
            raise PipelineLifecycleError(
                "saved pipeline contract cannot be loaded safely"
            ) from error
        if canonical_checksum(contract) != value.sha256:
            raise PipelineLifecycleError("saved pipeline checksum verification failed")
        if (
            contract.pipeline_id != value.pipeline_id
            or contract.revision != value.revision
            or contract.model_bundle_id != value.model_bundle_id
        ):
            raise PipelineLifecycleError("saved pipeline identity does not match metadata")
        return contract

    @staticmethod
    def _required(
        repository: MetadataRepository,
        pipeline_snapshot_id: str,
    ) -> PipelineSnapshotMetadata:
        value = repository.get_pipeline_snapshot(pipeline_snapshot_id)
        if value is None:
            raise KeyError(pipeline_snapshot_id)
        return value

    @staticmethod
    def _validate_model(
        repository: MetadataRepository,
        model_bundle_id: str | None,
        inference_enabled: bool,
    ) -> None:
        if not inference_enabled:
            if model_bundle_id is not None:
                raise PipelineLifecycleError(
                    "reconstruction-only pipelines cannot select an AI model"
                )
            return
        if model_bundle_id is None:
            raise PipelineLifecycleError("AI inference requires a model")
        model = repository.get_model_bundle(model_bundle_id)
        if model is None:
            raise PipelineLifecycleError("selected model does not exist")
        if model.state not in {"valid", "approved", "active"}:
            raise PipelineLifecycleError("selected model is not valid for a pipeline")
