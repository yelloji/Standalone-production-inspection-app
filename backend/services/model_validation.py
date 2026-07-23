"""Complete static validation for staged ONNX model bundles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeVar

import onnx
from onnx import TensorProto, checker
from pydantic import BaseModel, ValidationError

from backend.domain.model_bundle import (
    ChecksumsManifest,
    ClassesManifest,
    ModelManifest,
    PostprocessingManifest,
    PreprocessingManifest,
    SahiManifest,
    TensorSpecification,
    ValidationResultsManifest,
)
from backend.domain.value_objects import normalize_relative_path

REQUIRED_ROOT_FILES = {
    "model.onnx",
    "model_manifest.json",
    "classes.json",
    "preprocessing.json",
    "postprocessing.json",
    "sahi_config.json",
    "validation_results.json",
    "checksums.json",
}
MAX_JSON_BYTES = 10 * 1024 * 1024
SchemaT = TypeVar("SchemaT", bound=BaseModel)


class ModelBundleValidationError(ValueError):
    """Raised when a staged bundle is unsafe, incomplete, or inconsistent."""


@dataclass(frozen=True, slots=True)
class ValidatedModelBundle:
    root: Path
    model_manifest: ModelManifest
    classes: ClassesManifest
    preprocessing: PreprocessingManifest
    postprocessing: PostprocessingManifest
    sahi: SahiManifest
    validation_results: ValidationResultsManifest
    model_sha256: str


def validate_model_bundle(root: Path) -> ValidatedModelBundle:
    files = _inventory(root)
    missing = REQUIRED_ROOT_FILES - files
    if missing:
        raise ModelBundleValidationError(f"required bundle files are missing: {sorted(missing)}")
    if not any(path.startswith("test_vectors/") for path in files):
        raise ModelBundleValidationError("bundle must contain test-vector evidence")

    checksums = _load_json(root / "checksums.json", ChecksumsManifest)
    declared = set(checksums.files)
    payload_files = files - {"checksums.json"}
    if declared != payload_files:
        missing_checksums = payload_files - declared
        undeclared = declared - payload_files
        raise ModelBundleValidationError(
            f"checksum inventory mismatch; missing={sorted(missing_checksums)}, "
            f"unknown={sorted(undeclared)}"
        )
    for relative_path, expected in checksums.files.items():
        if _sha256_file(root / relative_path) != expected:
            raise ModelBundleValidationError(f"checksum mismatch: {relative_path}")

    manifest = _load_json(root / "model_manifest.json", ModelManifest)
    classes = _load_json(root / "classes.json", ClassesManifest)
    preprocessing = _load_json(root / "preprocessing.json", PreprocessingManifest)
    postprocessing = _load_json(root / "postprocessing.json", PostprocessingManifest)
    sahi = _load_json(root / "sahi_config.json", SahiManifest)
    validation = _load_json(
        root / "validation_results.json",
        ValidationResultsManifest,
    )

    if set(validation.test_vectors) - files:
        raise ModelBundleValidationError("validation results reference missing test vectors")
    if preprocessing.input_element_type != manifest.inputs[0].element_type:
        raise ModelBundleValidationError("preprocessing element type differs from model input")
    if set(postprocessing.output_names) != {item.name for item in manifest.outputs}:
        raise ModelBundleValidationError("postprocessing outputs differ from model manifest")

    _validate_onnx(root / manifest.model_file, manifest)
    return ValidatedModelBundle(
        root=root,
        model_manifest=manifest,
        classes=classes,
        preprocessing=preprocessing,
        postprocessing=postprocessing,
        sahi=sahi,
        validation_results=validation,
        model_sha256=checksums.files[manifest.model_file],
    )


def _inventory(root: Path) -> set[str]:
    inventory: set[str] = set()
    casefolded: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ModelBundleValidationError("links are not allowed in model bundles")
        if not path.is_file():
            continue
        relative = normalize_relative_path(path.relative_to(root).as_posix())
        folded = relative.casefold()
        if folded in casefolded:
            raise ModelBundleValidationError("case-colliding bundle paths are not allowed")
        casefolded.add(folded)
        inventory.add(relative)
    return inventory


def _load_json(path: Path, model_type: type[SchemaT]) -> SchemaT:
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ModelBundleValidationError(f"JSON document is too large: {path.name}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return model_type.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as error:
        raise ModelBundleValidationError(f"invalid {path.name}") from error


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_onnx(path: Path, manifest: ModelManifest) -> None:
    try:
        model = onnx.load(path, load_external_data=False)
        if any(
            tensor.data_location == TensorProto.EXTERNAL or tensor.external_data
            for tensor in model.graph.initializer
        ):
            raise ModelBundleValidationError("external ONNX tensor data is not allowed")
        checker.check_model(model, full_check=True)
    except ModelBundleValidationError:
        raise
    except Exception as error:
        raise ModelBundleValidationError("ONNX graph validation failed") from error

    initializers = {tensor.name for tensor in model.graph.initializer}
    inputs = tuple(
        _tensor_specification(value)
        for value in model.graph.input
        if value.name not in initializers
    )
    outputs = tuple(_tensor_specification(value) for value in model.graph.output)
    if inputs != manifest.inputs or outputs != manifest.outputs:
        raise ModelBundleValidationError("ONNX graph inputs/outputs differ from manifest")

    default_opsets = [item.version for item in model.opset_import if item.domain in {"", "ai.onnx"}]
    if not default_opsets or max(default_opsets) != manifest.onnx_opset:
        raise ModelBundleValidationError("ONNX opset differs from manifest")


def _tensor_specification(value: onnx.ValueInfoProto) -> TensorSpecification:
    tensor_type = value.type.tensor_type
    element_type: Literal["float16", "float32"]
    if tensor_type.elem_type == TensorProto.FLOAT:
        element_type = "float32"
    elif tensor_type.elem_type == TensorProto.FLOAT16:
        element_type = "float16"
    else:
        raise ModelBundleValidationError(f"unsupported tensor element type: {value.name}")

    dimensions: list[int | str] = []
    for dimension in tensor_type.shape.dim:
        if dimension.HasField("dim_value"):
            dimensions.append(dimension.dim_value)
        elif dimension.dim_param:
            dimensions.append(dimension.dim_param)
        else:
            raise ModelBundleValidationError(f"unnamed dynamic dimension: {value.name}")
    return TensorSpecification(
        name=value.name,
        element_type=element_type,
        shape=tuple(dimensions),
    )
