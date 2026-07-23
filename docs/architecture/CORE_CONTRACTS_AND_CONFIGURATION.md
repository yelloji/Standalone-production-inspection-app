# Core Contracts and Configuration

## Status

- Task: 2
- State: `COMMITTED`
- Database, inference, reconstruction, and production UI included: No

## Contract Rules

All persisted or cross-process production records use strict Pydantic contracts.
Every top-level contract carries `schema_version: 1`; unknown fields and
unsupported schema versions are rejected.

Task 2 defines contracts for:

- model bundles and pipeline snapshots;
- acquisitions and ordered source frames;
- runs and processing stages;
- reconstruction transforms;
- predictions and bounding boxes;
- generated artifacts;
- operator-safe and technical errors.

Identifiers, SHA-256 values, timestamps, confidence values, dimensions, and
relative artifact paths are validated at the contract boundary.

## Portable Path Rules

Runtime code receives a resource root and resolves one writable data root using
this precedence:

1. an explicit data-root argument supplied by the application launcher;
2. the `PRODUCTION_DATA_ROOT` environment setting;
3. a `data` directory relative to the supplied resource root.

A relative override is resolved from the resource root. No path is resolved
from the developer's current working directory.

Persisted paths use normalized forward-slash relative values. Absolute paths,
drive-qualified paths, traversal segments, Windows-reserved names, and unsafe
characters are rejected. Resolved filesystem paths must remain contained under
the approved resource or data root, including after existing symbolic links
are resolved.

The standard writable layout is:

```text
{DATA_ROOT}/
|-- configuration/
|-- pipelines/
|-- models/
|-- incoming/
|-- processing/
|-- completed/
|-- failed/
|-- database/
|-- logs/
`-- temp/
```

Directory creation is explicit. Merely constructing the path service does not
write to the filesystem.

## Serialization and Persistence

Canonical JSON uses UTF-8, sorted object keys, compact separators, JSON-safe
Pydantic values, and rejects non-finite numbers. SHA-256 checksums are computed
from those canonical bytes, making checksums independent of indentation or
dictionary insertion order.

Configuration JSON is written to a uniquely named temporary file in the target
directory, flushed to disk, and atomically replaced. Failed writes clean their
temporary file. Reads validate the requested schema before returning a model.

## Task Boundary

Task 2 provides contracts and infrastructure only. It does not:

- create or migrate SQLite;
- import a model;
- perform ONNX or SAHI inference;
- reconstruct an image;
- implement production screens or online intake.

## Task 2 Verification

Completed on 2026-07-23:

- 33 backend tests passed, including positive, rejection, round-trip,
  schema-version, checksum-tampering, path-containment, and atomic-replacement
  cases;
- Python dependency integrity, formatting, linting, and strict typing passed;
- unchanged frontend and Electron linting, typing, unit tests, and production
  builds passed;
- npm reported zero known vulnerabilities;
- runtime-source scanning found no fixed developer drive, workspace, user
  profile, or installation path;
- Git diff hygiene passed and the local transfer bundle remains ignored.
