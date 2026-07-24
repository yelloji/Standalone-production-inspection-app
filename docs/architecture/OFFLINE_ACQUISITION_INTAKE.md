# Offline Acquisition Intake

## Status

- Task: 5
- State: `COMMITTED`
- Current brake-disc frame count: exactly 16
- Automatic filename-order guessing: forbidden

## Intake Contract

A technical workflow supplies:

- an absolute selected source directory;
- an explicit ordered list of exactly 16 relative filenames;
- a unique acquisition identifier;
- the configured side/profile;
- expected width and height.

Order is positional: list entry zero is acquisition frame 1 and each following
entry is the next physical `22.5`-degree step. The service never infers
production order from filename sorting, timestamps, or filesystem enumeration.

## Validation and Ownership

Before finalization, the service:

1. rejects relative roots, links, traversal, duplicates, and files outside the
   selected directory;
2. requires exactly 16 distinct supported JPEG, PNG, or TIFF images;
3. fully decodes every image and rejects truncation, animation/multiple frames,
   unsupported pixel modes, and unexpected geometry;
4. computes SHA-256 and rejects duplicate image content;
5. copies into application-controlled staging using deterministic stored names;
6. revalidates copied bytes;
7. writes a canonical versioned manifest containing order, side, geometry,
   format, original filename, owned relative path, size, and checksum;
8. atomically publishes the complete acquisition directory.

The source folder may be removed after successful intake without affecting the
owned acquisition. The application never modifies the original source images.

## Task Boundary

Task 5 creates no UI, reconstruction, inference, or run orchestration. Task 14
exposes intake through the local API and Task 16 provides technical selection
and ordering controls.

## Confirmed Offline Validation Workflow

Task 16 exposes this committed intake core through the protected Offline
Validation workspace:

1. Select a saved pipeline revision.
2. Select one source folder through the native desktop dialog.
3. Inspect the supported image inventory without modifying source files.
4. Resolve order from the pipeline filename contract when it matches exactly,
   otherwise require explicit technical 1-16 ordering.
5. Display every filename, position, angle, format, and discovered geometry for
   confirmation.
6. Start a background validation/copy job.
7. Fully decode, hash, reject duplicate content, copy to application-owned
   staging, revalidate, and atomically publish the acquisition manifest.
8. Show durable acquisition identity and validation evidence.

Selecting or inspecting a folder does not activate a pipeline, run inference,
or change production. Offline mode uses the selected saved pipeline revision
only as immutable validation context.

## Task 5 Verification

Completed on 2026-07-23:

- 80 backend tests passed using real decoded JPEG, PNG, and TIFF images;
- explicit order was preserved independently of deliberately reversed
  filenames and mapped to `0` through `337.5` degrees;
- wrong count, an unselected seventeenth image, repeated filenames, duplicate
  content, corruption, wrong geometry, unsafe paths, links, relative roots,
  unsupported inputs, and duplicate acquisition identifiers were rejected;
- source and copied image bytes were hashed, copied bytes were revalidated, and
  staging was cleaned on failure;
- the canonical manifest and persisted checksum reopened and validated after
  the original source directory was removed;
- Python dependency integrity, formatting, linting, strict typing, all prior
  database/ONNX tests, frontend/Electron checks and builds, and npm audit
  passed;
- scans found no fixed machine path, AI Studio coupling, filename-sorted
  production order, uncontrolled directory copy, or tracked runtime artifact.
