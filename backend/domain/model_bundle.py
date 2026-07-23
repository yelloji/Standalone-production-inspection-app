"""Strict schemas for manually imported production ONNX bundles."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from backend.domain.value_objects import ContractIdentifier, SafeRelativePath, Sha256Hex

NonEmptyText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=500, strip_whitespace=True),
]
TensorDimension = int | str


class BundleSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class TensorSpecification(BundleSchema):
    name: ContractIdentifier
    element_type: Literal["float16", "float32"]
    shape: tuple[TensorDimension, ...]

    @model_validator(mode="after")
    def validate_shape(self) -> TensorSpecification:
        if not self.shape:
            raise ValueError("tensor shape must not be empty")
        for dimension in self.shape:
            if isinstance(dimension, int) and dimension < 1:
                raise ValueError("static tensor dimensions must be positive")
            if isinstance(dimension, str) and not dimension.strip():
                raise ValueError("dynamic tensor dimensions must have a name")
        return self


class ModelManifest(BundleSchema):
    schema_version: Literal[1] = 1
    model_bundle_id: ContractIdentifier
    display_name: NonEmptyText
    model_version: NonEmptyText
    model_file: Literal["model.onnx"] = "model.onnx"
    onnx_opset: Annotated[int, Field(ge=1)]
    required_execution_provider: Literal["CUDAExecutionProvider"]
    inputs: tuple[TensorSpecification, ...]
    outputs: tuple[TensorSpecification, ...]

    @model_validator(mode="after")
    def validate_io(self) -> ModelManifest:
        if not self.inputs or not self.outputs:
            raise ValueError("model manifest requires input and output tensors")
        for tensors in (self.inputs, self.outputs):
            names = [tensor.name for tensor in tensors]
            if len(names) != len(set(names)):
                raise ValueError("tensor names must be unique")
        primary = self.inputs[0]
        if len(primary.shape) != 4 or primary.shape[-2:] != (1312, 1312):
            raise ValueError("primary model input must be NCHW with 1312 x 1312 spatial size")
        return self


class ClassDefinition(BundleSchema):
    index: Annotated[int, Field(ge=0)]
    name: NonEmptyText


class ClassesManifest(BundleSchema):
    schema_version: Literal[1] = 1
    classes: tuple[ClassDefinition, ...]

    @model_validator(mode="after")
    def validate_classes(self) -> ClassesManifest:
        if not self.classes:
            raise ValueError("at least one model class is required")
        indices = [item.index for item in self.classes]
        names = [item.name for item in self.classes]
        if indices != list(range(len(indices))):
            raise ValueError("class indices must be contiguous and start at zero")
        if len(names) != len(set(names)):
            raise ValueError("class names must be unique")
        return self


class PreprocessingManifest(BundleSchema):
    schema_version: Literal[1] = 1
    layout: Literal["NCHW"]
    input_element_type: Literal["float16", "float32"]
    color_order: Literal["RGB", "BGR"]
    scale: Annotated[float, Field(gt=0)]
    mean: tuple[float, float, float]
    standard_deviation: tuple[
        Annotated[float, Field(gt=0)],
        Annotated[float, Field(gt=0)],
        Annotated[float, Field(gt=0)],
    ]


class PostprocessingManifest(BundleSchema):
    schema_version: Literal[1] = 1
    task: Literal["object_detection"]
    decoder: NonEmptyText
    output_names: tuple[ContractIdentifier, ...]

    @model_validator(mode="after")
    def validate_outputs(self) -> PostprocessingManifest:
        if not self.output_names or len(self.output_names) != len(set(self.output_names)):
            raise ValueError("postprocessing output names must be non-empty and unique")
        return self


class SahiManifest(BundleSchema):
    schema_version: Literal[1] = 1
    slice_width: Literal[1312]
    slice_height: Literal[1312]
    overlap_width_ratio: Annotated[float, Field(ge=0, lt=1)]
    overlap_height_ratio: Annotated[float, Field(ge=0, lt=1)]
    validated_batch_sizes: tuple[Annotated[int, Field(ge=1)], ...]

    @model_validator(mode="after")
    def validate_batches(self) -> SahiManifest:
        if not self.validated_batch_sizes:
            raise ValueError("at least one validated batch size is required")
        if len(set(self.validated_batch_sizes)) != len(self.validated_batch_sizes):
            raise ValueError("validated batch sizes must be unique")
        return self


class ValidationResultsManifest(BundleSchema):
    schema_version: Literal[1] = 1
    passed: Literal[True]
    exporter_runtime: NonEmptyText
    test_vectors: tuple[SafeRelativePath, ...]
    maximum_absolute_difference: Annotated[float, Field(ge=0)]
    mean_absolute_difference: Annotated[float, Field(ge=0)]

    @model_validator(mode="after")
    def validate_vectors(self) -> ValidationResultsManifest:
        if not self.test_vectors:
            raise ValueError("passing validation requires at least one test vector")
        if len(set(self.test_vectors)) != len(self.test_vectors):
            raise ValueError("test-vector paths must be unique")
        if not all(path.startswith("test_vectors/") for path in self.test_vectors):
            raise ValueError("test vectors must be stored below test_vectors/")
        return self


class ChecksumsManifest(BundleSchema):
    schema_version: Literal[1] = 1
    files: dict[SafeRelativePath, Sha256Hex]
