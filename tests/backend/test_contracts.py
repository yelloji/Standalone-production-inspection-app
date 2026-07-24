"""Versioned production contract tests."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.core.serialization import (
    ChecksumMismatchError,
    canonical_checksum,
    canonical_json_bytes,
    sha256_hex,
    validate_json_model,
    verify_sha256,
)
from backend.domain.contracts import (
    AcquisitionConfiguration,
    AcquisitionContract,
    AcquisitionMode,
    AcquisitionSource,
    ApplicationConfiguration,
    ArtifactContract,
    ArtifactKind,
    AutomaticAcquisitionConfiguration,
    BoundingBox,
    DiscSide,
    ErrorContract,
    ErrorSeverity,
    InferenceConfiguration,
    InferenceMode,
    ModelBundleContract,
    PipelineContract,
    PredictionContract,
    ReconstructionConfiguration,
    RunContract,
    RunStatus,
    SahiConfiguration,
    StageContract,
    StageStatus,
    TransformContract,
)

NOW = datetime(2026, 7, 23, 10, 0, tzinfo=timezone.utc)
CHECKSUM = "a" * 64


def make_pipeline() -> PipelineContract:
    return PipelineContract(
        pipeline_id="brake-disc-upper",
        revision=1,
        display_name="Brake Disc Upper",
        model_bundle_id="crack-detector-v1",
        acquisition=AcquisitionConfiguration(
            source=AcquisitionSource.OFFLINE,
            expected_frame_count=16,
            ordered=True,
            side=DiscSide.UPPER,
        ),
        inference=InferenceConfiguration(
            mode=InferenceMode.SAHI,
            confidence_threshold=0.4,
            sahi=SahiConfiguration(
                slice_width=1312,
                slice_height=1312,
                overlap_width_ratio=0.5,
                overlap_height_ratio=0.5,
                batch_size=32,
            ),
        ),
        reconstruction=ReconstructionConfiguration(
            enabled=True,
            segment_count=16,
            degrees_per_segment=22.5,
        ),
    )


def test_pipeline_round_trip_and_checksum_are_deterministic() -> None:
    pipeline = make_pipeline()
    payload = canonical_json_bytes(pipeline)

    restored = validate_json_model(payload, PipelineContract)

    assert restored == pipeline
    assert canonical_checksum(restored) == canonical_checksum(pipeline)
    assert canonical_json_bytes({"b": 2, "a": 1}) == canonical_json_bytes({"a": 1, "b": 2})


def test_exact_payload_checksum_rejects_tampering() -> None:
    payload = canonical_json_bytes(make_pipeline())
    checksum = sha256_hex(payload)

    verify_sha256(payload, checksum)
    with pytest.raises(ChecksumMismatchError):
        verify_sha256(payload + b"tampered", checksum)


def test_all_top_level_contracts_have_supported_schema() -> None:
    model = ModelBundleContract(
        model_bundle_id="crack-detector-v1",
        display_name="Crack Detector",
        model_version="1.0.0",
        model_path="models/crack-detector/model.onnx",
        model_sha256=CHECKSUM,
        input_width=1312,
        input_height=1312,
        class_names=("crack",),
    )
    acquisition = AcquisitionContract(
        acquisition_id="acquisition-001",
        source=AcquisitionSource.OFFLINE,
        side=DiscSide.UPPER,
        captured_at=NOW,
        frame_paths=("incoming/acquisition-001/01.jpg",),
    )
    error = ErrorContract(
        code="INPUT_INVALID",
        severity=ErrorSeverity.ERROR,
        operator_message="The input set is incomplete.",
        technical_detail="Expected 16 frames.",
        retryable=True,
    )
    failed_stage = StageContract(
        stage_id="validate-input",
        name="Validate input",
        status=StageStatus.FAILED,
        started_at=NOW,
        finished_at=NOW,
        error=error,
    )
    run = RunContract(
        run_id="run-001",
        acquisition_id=acquisition.acquisition_id,
        pipeline_id="brake-disc-upper",
        pipeline_revision=1,
        pipeline_sha256=canonical_checksum(make_pipeline()),
        status=RunStatus.FAILED,
        created_at=NOW,
        stages=(failed_stage,),
    )
    transform = TransformContract(
        transform_id="transform-001",
        source_frame_index=0,
        segment_index=0,
        angle_degrees=0,
        source_to_output_matrix=(1, 0, 0, 0, 1, 0, 0, 0, 1),
    )
    prediction = PredictionContract(
        prediction_id="prediction-001",
        class_name="crack",
        confidence=0.95,
        source_frame_index=0,
        source_box=BoundingBox(x=10, y=20, width=30, height=40),
        transform_id=transform.transform_id,
    )
    artifact = ArtifactContract(
        artifact_id="artifact-001",
        kind=ArtifactKind.RECONSTRUCTED_IMAGE,
        relative_path="completed/run-001/reconstructed.tif",
        sha256=CHECKSUM,
        size_bytes=1234,
        media_type="image/tiff",
        created_at=NOW,
    )
    configuration = ApplicationConfiguration(
        configuration_revision=1,
        active_pipeline_id="brake-disc-upper",
        updated_at=NOW,
    )

    contracts = (
        model,
        make_pipeline(),
        acquisition,
        error,
        failed_stage,
        run,
        transform,
        prediction,
        artifact,
        configuration,
    )
    assert all(contract.schema_version == 1 for contract in contracts)


def test_unsupported_schema_and_unknown_fields_are_rejected() -> None:
    valid_payload = make_pipeline().model_dump(mode="json")

    with pytest.raises(ValidationError):
        PipelineContract.model_validate({**valid_payload, "schema_version": 2})

    with pytest.raises(ValidationError):
        PipelineContract.model_validate({**valid_payload, "unexpected": True})


def test_invalid_sahi_and_reconstruction_combinations_are_rejected() -> None:
    with pytest.raises(ValidationError):
        InferenceConfiguration(
            mode=InferenceMode.SAHI,
            confidence_threshold=0.4,
        )

    with pytest.raises(ValidationError):
        ReconstructionConfiguration(
            enabled=True,
            segment_count=16,
            degrees_per_segment=20,
        )


def test_automatic_acquisition_requires_safe_explicit_tokens() -> None:
    automatic = AutomaticAcquisitionConfiguration(filename_template="{cycle}_{position}.jpg")
    configuration = AcquisitionConfiguration(
        source=AcquisitionSource.ONLINE,
        expected_frame_count=16,
        side=DiscSide.UPPER,
        mode=AcquisitionMode.AUTOMATIC_FOLDER,
        automatic=automatic,
    )

    assert configuration.automatic == automatic
    with pytest.raises(ValidationError):
        AutomaticAcquisitionConfiguration(filename_template="disc_{position}.jpg")
    with pytest.raises(ValidationError):
        AutomaticAcquisitionConfiguration(filename_template="{cycle}/{position}.jpg")
    with pytest.raises(ValidationError):
        AcquisitionConfiguration(
            source=AcquisitionSource.ONLINE,
            expected_frame_count=16,
            mode=AcquisitionMode.AUTOMATIC_FOLDER,
        )


def test_pipeline_stages_are_independently_optional_but_not_all_disabled() -> None:
    reconstruction_only = make_pipeline().model_copy(
        update={
            "model_bundle_id": None,
            "inference": InferenceConfiguration(enabled=False),
        }
    )
    inference_only = make_pipeline().model_copy(
        update={"reconstruction": ReconstructionConfiguration(enabled=False)}
    )

    assert PipelineContract.model_validate(reconstruction_only.model_dump()).model_bundle_id is None
    assert not PipelineContract.model_validate(inference_only.model_dump()).reconstruction.enabled

    with pytest.raises(ValidationError):
        PipelineContract.model_validate(
            {
                **reconstruction_only.model_dump(),
                "reconstruction": ReconstructionConfiguration(enabled=False).model_dump(),
            }
        )


def test_invalid_contract_values_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ModelBundleContract(
            model_bundle_id="model",
            display_name="Model",
            model_version="1",
            model_path="C:/models/model.onnx",
            model_sha256="not-a-checksum",
            input_width=0,
            input_height=1312,
            class_names=(),
        )

    with pytest.raises(ValidationError):
        PredictionContract(
            prediction_id="prediction",
            class_name="crack",
            confidence=1.1,
            source_frame_index=0,
            source_box=BoundingBox(x=0, y=0, width=10, height=10),
        )
