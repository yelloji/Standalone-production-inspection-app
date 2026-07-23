"""Build small valid ONNX bundles for import and validation tests."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, cast

import onnx
from onnx import TensorProto, helper


def create_model_bundle(
    root: Path,
    *,
    model_bundle_id: str = "crack-detector-v1",
) -> Path:
    root.mkdir(parents=True)
    _write_model(root / "model.onnx")
    _write_json(
        root / "model_manifest.json",
        {
            "schema_version": 1,
            "model_bundle_id": model_bundle_id,
            "display_name": "Crack Detector",
            "model_version": "1.0.0",
            "model_file": "model.onnx",
            "onnx_opset": 18,
            "required_execution_provider": "CUDAExecutionProvider",
            "inputs": [
                {
                    "name": "images",
                    "element_type": "float32",
                    "shape": ["batch", 3, 1312, 1312],
                }
            ],
            "outputs": [
                {
                    "name": "detections",
                    "element_type": "float32",
                    "shape": ["batch", 3, 1312, 1312],
                }
            ],
        },
    )
    _write_json(
        root / "classes.json",
        {
            "schema_version": 1,
            "classes": [{"index": 0, "name": "crack"}],
        },
    )
    _write_json(
        root / "preprocessing.json",
        {
            "schema_version": 1,
            "layout": "NCHW",
            "input_element_type": "float32",
            "color_order": "RGB",
            "scale": 1 / 255,
            "mean": [0, 0, 0],
            "standard_deviation": [1, 1, 1],
        },
    )
    _write_json(
        root / "postprocessing.json",
        {
            "schema_version": 1,
            "task": "object_detection",
            "decoder": "validated-test-decoder",
            "output_names": ["detections"],
        },
    )
    _write_json(
        root / "sahi_config.json",
        {
            "schema_version": 1,
            "slice_width": 1312,
            "slice_height": 1312,
            "overlap_width_ratio": 0.5,
            "overlap_height_ratio": 0.5,
            "validated_batch_sizes": [1, 16, 32],
        },
    )
    vector = root / "test_vectors" / "vector-001.bin"
    vector.parent.mkdir()
    vector.write_bytes(b"immutable parity evidence")
    _write_json(
        root / "validation_results.json",
        {
            "schema_version": 1,
            "passed": True,
            "exporter_runtime": "reference-exporter-1.0",
            "test_vectors": ["test_vectors/vector-001.bin"],
            "maximum_absolute_difference": 0.0001,
            "mean_absolute_difference": 0.00001,
        },
    )
    rewrite_checksums(root)
    return root


def rewrite_checksums(root: Path) -> None:
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "checksums.json":
            files[path.relative_to(root).as_posix()] = _sha256(path)
    _write_json(root / "checksums.json", {"schema_version": 1, "files": files})


def zip_bundle(root: Path, destination: Path) -> Path:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(root).as_posix())
    return destination


def read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def write_json(path: Path, value: dict[str, Any]) -> None:
    _write_json(path, value)


def _write_model(path: Path) -> None:
    input_value = helper.make_tensor_value_info(
        "images",
        TensorProto.FLOAT,
        ["batch", 3, 1312, 1312],
    )
    output_value = helper.make_tensor_value_info(
        "detections",
        TensorProto.FLOAT,
        ["batch", 3, 1312, 1312],
    )
    graph = helper.make_graph(
        [helper.make_node("Identity", ["images"], ["detections"])],
        "task4-test-model",
        [input_value],
        [output_value],
    )
    model = helper.make_model(
        graph,
        producer_name="task4-tests",
        opset_imports=[helper.make_opsetid("", 18)],
    )
    onnx.save(model, path)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()
