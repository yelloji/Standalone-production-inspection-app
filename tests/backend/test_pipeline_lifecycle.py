"""Modular pipeline draft, validation, activation, and rollback tests."""

from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from backend.core.paths import ApplicationPaths
from backend.database.engine import transaction
from backend.database.repositories import MetadataRepository
from backend.domain.contracts import (
    AcquisitionConfiguration,
    AcquisitionSource,
    DiscSide,
    InferenceConfiguration,
    InferenceMode,
    ReconstructionConfiguration,
    SahiConfiguration,
)
from backend.services.pipeline_lifecycle import (
    PipelineDraft,
    PipelineLifecycleError,
    PipelineLifecycleService,
)
from tests.backend.database.factories import model_bundle


def _service(
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> PipelineLifecycleService:
    application_paths.ensure_data_layout()
    return PipelineLifecycleService(
        paths=application_paths,
        session_factory=session_factory,
    )


def _acquisition(side: DiscSide = DiscSide.UPPER) -> AcquisitionConfiguration:
    return AcquisitionConfiguration(
        source=AcquisitionSource.OFFLINE,
        expected_frame_count=16,
        ordered=True,
        side=side,
    )


def _reconstruction(enabled: bool = True) -> ReconstructionConfiguration:
    return (
        ReconstructionConfiguration(
            enabled=True,
            segment_count=16,
            degrees_per_segment=22.5,
        )
        if enabled
        else ReconstructionConfiguration(enabled=False)
    )


def _inference(enabled: bool = True) -> InferenceConfiguration:
    return (
        InferenceConfiguration(
            enabled=True,
            mode=InferenceMode.SAHI,
            confidence_threshold=0.4,
            sahi=SahiConfiguration(batch_size=32),
        )
        if enabled
        else InferenceConfiguration(enabled=False)
    )


def test_reconstruction_only_pipeline_is_saved_validated_and_activated(
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    service = _service(application_paths, session_factory)
    draft = service.create_draft(
        PipelineDraft(
            pipeline_id="reconstruction-only",
            display_name="Reconstruction Only",
            model_bundle_id=None,
            acquisition=_acquisition(),
            inference=_inference(False),
            reconstruction=_reconstruction(),
        )
    )

    assert draft.state == "draft"
    assert draft.model_bundle_id is None
    assert application_paths.resolve_data_path(draft.contract_path).is_file()
    assert service.validate(draft.pipeline_snapshot_id).state == "validated"
    assert service.approve_and_activate(draft.pipeline_snapshot_id).state == "active"

    with transaction(session_factory) as session:
        active = MetadataRepository(session).get_active_pipeline_snapshot()
    assert active is not None
    assert active.pipeline_snapshot_id == draft.pipeline_snapshot_id


def test_inference_only_pipeline_requires_a_valid_model(
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    service = _service(application_paths, session_factory)
    with pytest.raises(PipelineLifecycleError, match="does not exist"):
        service.create_draft(
            PipelineDraft(
                pipeline_id="inference-only",
                display_name="Inference Only",
                model_bundle_id="missing-model",
                acquisition=_acquisition(),
                inference=_inference(),
                reconstruction=_reconstruction(False),
            )
        )

    with transaction(session_factory) as session:
        MetadataRepository(session).add_model_bundle(model_bundle())
    saved = service.create_draft(
        PipelineDraft(
            pipeline_id="inference-only",
            display_name="Inference Only",
            model_bundle_id="model-v1",
            acquisition=_acquisition(),
            inference=_inference(),
            reconstruction=_reconstruction(False),
        )
    )
    contract = service.get_contract(saved)
    assert not contract.reconstruction.enabled
    assert contract.inference.enabled


def test_activation_preserves_previous_version_for_rollback(
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    service = _service(application_paths, session_factory)
    first = service.create_draft(
        PipelineDraft(
            pipeline_id="brake-disc",
            display_name="Brake Disc",
            model_bundle_id=None,
            acquisition=_acquisition(),
            inference=_inference(False),
            reconstruction=_reconstruction(),
        )
    )
    service.validate(first.pipeline_snapshot_id)
    service.approve_and_activate(first.pipeline_snapshot_id)

    second = service.create_draft(
        PipelineDraft(
            pipeline_id="brake-disc",
            display_name="Brake Disc",
            model_bundle_id=None,
            acquisition=_acquisition(DiscSide.LOWER),
            inference=_inference(False),
            reconstruction=_reconstruction(),
        )
    )
    service.validate(second.pipeline_snapshot_id)
    service.approve_and_activate(second.pipeline_snapshot_id)

    with transaction(session_factory) as session:
        repository = MetadataRepository(session)
        old = repository.get_pipeline_snapshot(first.pipeline_snapshot_id)
        active = repository.get_active_pipeline_snapshot()
    assert old is not None and old.state == "approved"
    assert active is not None and active.pipeline_snapshot_id == second.pipeline_snapshot_id

    restored = service.approve_and_activate(first.pipeline_snapshot_id)
    assert restored.state == "active"


def test_pipeline_contract_file_tampering_blocks_validation(
    application_paths: ApplicationPaths,
    session_factory: sessionmaker[Session],
) -> None:
    service = _service(application_paths, session_factory)
    draft = service.create_draft(
        PipelineDraft(
            pipeline_id="tamper-test",
            display_name="Tamper Test",
            model_bundle_id=None,
            acquisition=_acquisition(),
            inference=_inference(False),
            reconstruction=_reconstruction(),
        )
    )
    Path(application_paths.resolve_data_path(draft.contract_path)).write_text(
        "{}",
        encoding="utf-8",
    )

    with pytest.raises(PipelineLifecycleError, match="cannot be loaded safely"):
        service.validate(draft.pipeline_snapshot_id)
