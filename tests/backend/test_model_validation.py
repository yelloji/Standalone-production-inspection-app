"""Static ONNX bundle schema, checksum, and graph validation tests."""

from pathlib import Path

import pytest

from backend.services.model_validation import (
    ModelBundleValidationError,
    validate_model_bundle,
)
from tests.backend.model_bundle_factory import (
    create_model_bundle,
    read_json,
    rewrite_checksums,
    write_json,
)


def test_valid_bundle_matches_onnx_graph_and_evidence(tmp_path: Path) -> None:
    root = create_model_bundle(tmp_path / "bundle")

    validated = validate_model_bundle(root)

    assert validated.model_manifest.model_bundle_id == "crack-detector-v1"
    assert validated.model_manifest.inputs[0].shape == ("batch", 3, 1312, 1312)
    assert validated.classes.classes[0].name == "crack"
    assert validated.sahi.slice_width == 1312
    assert len(validated.model_sha256) == 64


def test_checksum_tampering_is_rejected(tmp_path: Path) -> None:
    root = create_model_bundle(tmp_path / "bundle")
    (root / "model.onnx").write_bytes(b"tampered")

    with pytest.raises(ModelBundleValidationError, match="checksum mismatch"):
        validate_model_bundle(root)


def test_undeclared_payload_file_is_rejected(tmp_path: Path) -> None:
    root = create_model_bundle(tmp_path / "bundle")
    (root / "unexpected.txt").write_text("not declared", encoding="utf-8")

    with pytest.raises(ModelBundleValidationError, match="checksum inventory"):
        validate_model_bundle(root)


def test_manifest_tensor_mismatch_is_rejected_after_valid_checksums(
    tmp_path: Path,
) -> None:
    root = create_model_bundle(tmp_path / "bundle")
    manifest_path = root / "model_manifest.json"
    manifest = read_json(manifest_path)
    manifest["inputs"][0]["name"] = "wrong-input"
    write_json(manifest_path, manifest)
    rewrite_checksums(root)

    with pytest.raises(ModelBundleValidationError, match="inputs/outputs"):
        validate_model_bundle(root)


def test_unknown_schema_field_is_rejected(tmp_path: Path) -> None:
    root = create_model_bundle(tmp_path / "bundle")
    classes_path = root / "classes.json"
    classes = read_json(classes_path)
    classes["unknown"] = True
    write_json(classes_path, classes)
    rewrite_checksums(root)

    with pytest.raises(ModelBundleValidationError, match="invalid classes.json"):
        validate_model_bundle(root)


def test_non_1312_manifest_is_rejected(tmp_path: Path) -> None:
    root = create_model_bundle(tmp_path / "bundle")
    manifest_path = root / "model_manifest.json"
    manifest = read_json(manifest_path)
    manifest["inputs"][0]["shape"] = ["batch", 3, 640, 640]
    write_json(manifest_path, manifest)
    rewrite_checksums(root)

    with pytest.raises(ModelBundleValidationError, match="invalid model_manifest"):
        validate_model_bundle(root)


def test_corrupt_onnx_is_rejected_even_with_matching_checksum(tmp_path: Path) -> None:
    root = create_model_bundle(tmp_path / "bundle")
    (root / "model.onnx").write_bytes(b"not an ONNX graph")
    rewrite_checksums(root)

    with pytest.raises(ModelBundleValidationError, match="ONNX graph"):
        validate_model_bundle(root)
