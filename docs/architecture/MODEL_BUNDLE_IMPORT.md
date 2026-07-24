# Manual ONNX Bundle Import

## Status

- Task: 4
- State: `COMMITTED`
- Supported production model format: ONNX only
- Runtime inference included: No

## Import Boundary

A technical user may select a model-bundle directory or ZIP file. The import
service never executes from that source and never stores a dependency on it.
It copies safe files into application-controlled staging beneath `DATA_ROOT`,
validates the complete bundle, and atomically moves the validated bundle into
application-owned model storage.

Invalid imports are rejected and cleaned from staging. An import never
overwrites an existing bundle and never changes the active model.

## Required Bundle

```text
model.onnx
model_manifest.json
classes.json
preprocessing.json
postprocessing.json
sahi_config.json
validation_results.json
checksums.json
test_vectors/
```

All JSON documents carry `schema_version: 1` and reject unknown fields.
`checksums.json` covers every payload file other than itself. Undeclared files,
missing files, duplicate archive names, unsafe paths, links, oversized
archives, and suspicious compression ratios are rejected.

## ONNX Validation

Static validation:

- parses and checks the ONNX graph;
- rejects external tensor-data references;
- compares graph input/output names, element types, ranks, and dimensions with
  the manifest;
- requires NCHW spatial input dimensions of `1312 x 1312`;
- validates declared batch behavior and ONNX opset information;
- verifies class, preprocessing, postprocessing, and SAHI schemas.

Task 4 validates supplied test-vector inventory and exporter parity evidence.
It does not claim CUDA compatibility or rerun inference. Actual ONNX Runtime
CUDA loading, warm-up, and test-vector execution belong to Task 10.

## Lifecycle

```text
Imported/Staging -> Valid -> Approved -> Active
                         \-> Rejected
Active -> Approved (when another approved model activates)
```

Import produces `Valid`, never `Active`. Approval and activation are explicit
technical actions. Activation updates the old active model and new model in one
database transaction. The previous valid/approved model and its immutable
files remain available for rollback.

## Task 16 Model Library Integration

The Configuration Mode Model Library now exposes the committed importer through
a controlled desktop workflow:

- Electron selects one local validated ZIP bundle through a native file dialog;
- the renderer receives no general filesystem or Electron API;
- the API submits import to a single background model worker and immediately
  returns a job identity;
- the UI polls bounded job state and refreshes durable model metadata after
  completion;
- the portable runtime owns SQLite and model storage beneath the resolved data
  root;
- import remains `Valid`, never active.

Multiple immutable versions may coexist. The library shows model name, version,
identifier, state, import date, dependency protection, and available actions.

Archive and deletion are intentionally separate:

1. Active models cannot be archived.
2. Models referenced by any saved pipeline cannot be archived or deleted.
3. Archive changes an unused model to `Retired` but preserves its files.
4. Only a retired, unreferenced model may be permanently deleted.
5. Permanent deletion moves owned files aside before the database transaction;
   a database failure restores them.

Model import/archive/delete operations never run inside HTTP request handlers.
Authentication for protected technical access remains a pending product
decision; current APIs remain loopback-only.

## Original Task Boundary

Task 4 added no API endpoint or UI. Task 14 established the typed local
boundary. Task 16 now provides the technical Model Library interface.

## Task 4 Verification

Completed on 2026-07-23:

- 67 backend tests passed, including generated valid ONNX graphs;
- directory and ZIP imports copied independently into application storage;
- traversal, absolute/drive-qualified archive members, links, duplicate paths,
  undeclared files, checksum tampering, corrupt ONNX, schema errors, tensor
  mismatch, and duplicate imports were rejected;
- graph checker, opset, tensor names, element types, shapes, fixed `1312 x
  1312` spatial dimensions, bundle metadata, and parity-evidence inventory
  were validated;
- approval, activation, single-active enforcement, and rollback to the prior
  approved model passed while preserving both immutable bundles;
- Python dependency integrity, formatting, linting, strict typing, full
  frontend/Electron checks and builds, and npm audit passed;
- runtime scans found no fixed machine path, AI Studio coupling, `.pt`
  production support, unsafe bulk archive extraction, or tracked model/database
  artifacts.
