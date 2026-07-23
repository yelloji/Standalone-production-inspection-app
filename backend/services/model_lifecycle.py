"""Explicit approval, activation, and rollback-safe model lifecycle."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from backend.database.engine import transaction
from backend.database.records import ModelBundleMetadata
from backend.database.repositories import MetadataRepository


class ModelLifecycleError(RuntimeError):
    """Raised when a requested model-state transition is not allowed."""


class ModelLifecycleService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def approve(self, model_bundle_id: str) -> ModelBundleMetadata:
        with transaction(self._session_factory) as session:
            repository = MetadataRepository(session)
            current = _required(repository, model_bundle_id)
            if current.state != "valid":
                raise ModelLifecycleError("only a valid model bundle can be approved")
            repository.set_model_bundle_state(model_bundle_id, "approved")
            return _required(repository, model_bundle_id)

    def activate(self, model_bundle_id: str) -> ModelBundleMetadata:
        with transaction(self._session_factory) as session:
            repository = MetadataRepository(session)
            requested = _required(repository, model_bundle_id)
            if requested.state != "approved":
                raise ModelLifecycleError("only an approved model bundle can be activated")
            active = repository.get_active_model_bundle()
            if active is not None:
                repository.set_model_bundle_state(active.model_bundle_id, "approved")
            repository.set_model_bundle_state(model_bundle_id, "active")
            return _required(repository, model_bundle_id)


def _required(
    repository: MetadataRepository,
    model_bundle_id: str,
) -> ModelBundleMetadata:
    value = repository.get_model_bundle(model_bundle_id)
    if value is None:
        raise ModelLifecycleError(f"unknown model bundle: {model_bundle_id}")
    return value
