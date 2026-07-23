# Implementation Tasks

## Document Status

- Current phase: Production reconstruction
- Current task: Task 7 - Modular dense/projective reconstruction
- Current task status: `COMMITTED`
- Application code started: Yes, foundation only
- Production feature code started: Yes, reconstruction geometry only

## Working Agreement

1. Work on one task at a time.
2. Explain design, risks, and affected files before editing.
3. Implement only the approved task.
4. Preserve unrelated/local reference material.
5. Run task-proportional checks.
6. Mark implementation `READY FOR USER REVIEW` and stop.
7. User reviews/tests.
8. Update task result and commit only after explicit approval.
9. Push only explicitly approved tracked files.
10. Never commit models, datasets, databases, logs, outputs, transfer bundles, or secrets.
11. Accuracy changes require evidence; performance is not allowed to silently reduce crack detection.
12. Database tests use a real isolated test database.

## Status Definitions

- `PLANNED`
- `IN PROGRESS`
- `READY FOR USER REVIEW`
- `APPROVED`
- `COMMITTED`
- `BLOCKED`
- `DEFERRED`

## Phase 0 - Documentation and Safe Foundation

### Task 0 - Architecture and Product Documentation

Status: `APPROVED`

Deliverables:

- documentation index and authority rules;
- confirmed/current/future/pending product requirements;
- standalone system and module architecture;
- Production Run and Setup & Validation UI design;
- pipeline/model lifecycle;
- performance/concurrency architecture;
- pending online connector contract;
- accepted/pending architecture decisions;
- task-by-task implementation ledger;
- repository ignore protection for local/generated artifacts.

Acceptance:

- No application code is created.
- Documents agree on product boundaries and modes.
- Transfer/reference bundle remains untracked.
- User approves the architecture before Task 1.

Approval recorded on 2026-07-22:

- The user approved the complete documentation plan and architecture direction.
- The user confirmed that they will guide later production features incrementally.
- Before and after every task, progress and results must be explained in simple language unless the user requests technical detail.
- Uncertainty must be raised with the user before making a material design assumption.
- On 2026-07-23, the user authorized autonomous implementation, full testing,
  documentation updates, focused commits, and pushes for Tasks 4 through 14.
- Each of Tasks 4 through 14 must still pass its own complete gate before its
  commit; commits use professional task-specific messages and contain no
  assistant attribution.
- After Task 15 is implemented and internally tested, stop for the user's
  hands-on UI and workflow review before beginning Task 16.

### Task 1 - Repository and Tooling Foundation

Status: `COMMITTED`

Work:

- define supported Python and Node versions;
- add minimal backend/frontend/electron package manifests;
- establish formatting, linting, typing, and test commands;
- add environment/config examples without secrets;
- add CI-ready commands without building features;
- create only the minimal folder skeleton required by tooling.

Gate: clean installation/import/build smoke checks with no production feature.

Additional Task 1 gate:

- tracked runtime source contains no hardcoded Windows drive/developer path;
- Electron packaged resources resolve relative to the runtime location;
- writable path implementation remains blocked until Task 2 defines the
  central safe path contract.

Result recorded on 2026-07-23:

- pinned Python, Node, npm, frontend, Electron, and quality-tool foundations;
- added a minimal FastAPI health boundary, typed React screen, and secure
  Electron shell without production feature code;
- added lint, type, unit-test, build, dependency, security-audit, and CI-ready
  commands;
- verified the backend health endpoint and the built UI in a real browser;
- verified the browser at port 10000 with no console, page, or asset errors;
- verified tracked runtime source contains no absolute developer/drive paths;
- kept transfer data, generated outputs, environments, models, databases,
  images, logs, and build artifacts untracked.

### Task 2 - Core Contracts and Configuration

Status: `COMMITTED`

Work:

- versioned pipeline, model bundle, acquisition, run, stage, transform, prediction, artifact, and error contracts;
- safe data-root configuration;
- deterministic serialization/checksums;
- atomic configuration persistence;
- strict path containment.

Gate: positive, rejection, round-trip, and schema-version tests pass.

Result recorded on 2026-07-23:

- added strict schema-versioned model bundle, pipeline, acquisition, run,
  stage, transform, prediction, artifact, error, and application-configuration
  contracts;
- added canonical JSON serialization, deterministic SHA-256 generation, and
  tampered-payload verification;
- added an absolute resource-root contract and configurable writable data root
  with explicit argument, environment, and application-relative fallback
  precedence;
- added normalized safe relative paths, Windows portability checks, root
  containment, explicit data-layout creation, and absolute-to-relative
  conversion;
- added validated atomic configuration save/load with same-directory temporary
  files and cleanup;
- passed 33 backend tests, all Python quality gates, unchanged
  frontend/Electron checks and builds, npm security audit, runtime path scan,
  and Git diff hygiene;
- no database, inference, reconstruction, production UI, or online intake was
  added.

## Phase 1 - Durable Offline Core

### Task 3 - Database Foundation

Status: `COMMITTED`

Work:

- SQLAlchemy session/repository boundary;
- pipeline/model/run/frame/artifact metadata foundation;
- additive migrations, transactions, indexes, backup/recovery tests;
- real isolated SQLite test database.

Gate: migration, repository, transaction, constraint, index, backup, recovery,
integrity, and full regression tests pass.

Result recorded on 2026-07-23:

- added a portable application-owned SQLite engine and short-lived transaction
  boundary with foreign keys, WAL, normal synchronous durability, and a
  bounded busy timeout;
- added framework-neutral repositories for model bundle, pipeline snapshot,
  inspection run, ordered source-frame, and artifact metadata;
- added validated portable metadata paths, SHA-256 values, and timezone-aware
  timestamps;
- added the initial additive Alembic migration with explicit constraints,
  foreign keys, uniqueness rules, and query indexes;
- added integrity-checked online backup and closed-database atomic recovery
  beneath the approved data root;
- passed 50 backend tests using real isolated SQLite files, including exact
  migration/model parity, idempotent upgrade, transactions, rollback,
  constraints, indexes, backup, recovery, corruption, and path rejection;
- passed all Python, frontend, Electron, build, dependency, security,
  portability, isolation, and Git hygiene gates;
- no database file, AI Studio dependency, API endpoint, production UI,
  inference, reconstruction, or acquisition workflow was added.

### Task 4 - Manual ONNX Bundle Import

Status: `COMMITTED`

Work:

- safe staged import;
- checksum/schema/ONNX IO validation;
- test-vector/parity evidence;
- model lifecycle and rollback-safe activation.

Gate: valid directory/ZIP import, rejection, checksum, schema, ONNX graph/IO,
parity-evidence, registration, activation, rollback, and full regression tests
pass.

Result recorded on 2026-07-23:

- added strict version-1 schemas for model, classes, preprocessing,
  postprocessing, SAHI, validation evidence, test vectors, and checksums;
- added application-controlled directory/ZIP staging with traversal, absolute
  path, drive path, links, duplicate/case collision, encryption, file-count,
  total-size, and compression-ratio protections;
- added complete declared-file SHA-256 verification and rejection of missing
  or undeclared payloads;
- added ONNX graph checker, external-data rejection, opset verification, and
  exact input/output name, type, rank, and dimension comparison;
- enforced NCHW `1312 x 1312` spatial input while leaving CUDA execution and
  real test-vector inference for Task 10;
- added atomic application-owned registration, a single-active-model database
  guarantee, and explicit approval/activation with transactional rollback to a
  preserved prior approved model;
- passed 67 backend tests using generated ONNX files plus the full Python,
  frontend, Electron, build, dependency, security, portability, isolation,
  archive-safety, and Git hygiene gates;
- no API endpoint, UI, inference worker, `.pt` support, external model
  dependency, or model binary was committed.

### Task 5 - Offline Acquisition Intake

Status: `COMMITTED`

Work:

- safe folder selection/registration;
- exactly 16 ordered immutable images;
- geometry/format/hash/duplicate/completeness validation;
- immutable acquisition manifest.

Gate: explicit order, exact count/completeness, real decode, format, geometry,
duplicate, checksum, source-independence, atomic finalization, rejection, and
full regression tests pass.

Result recorded on 2026-07-23:

- added a strict version-1 acquisition manifest for 16 positional frames,
  upper/lower side, `22.5`-degree angles, owned paths, dimensions, formats,
  sizes, and SHA-256 values;
- required an absolute selected folder and explicit 16-file order; production
  order is never inferred from filenames, timestamps, or directory iteration;
- required the selected folder image inventory to exactly match the ordered
  list and rejected a missing or unselected seventeenth image;
- fully decoded JPEG, PNG, and TIFF files, enforced configured geometry and
  supported pixel modes, and rejected corruption or multi-frame input;
- rejected unsafe/linked paths, duplicate names/content, unsupported files,
  copy mismatch, and existing acquisition identifiers;
- added application-controlled staging, deterministic owned filenames,
  post-copy verification, canonical manifest/checksum persistence, failure
  cleanup, and atomic publication;
- passed 80 backend tests plus the complete Python, database, ONNX, frontend,
  Electron, build, dependency, security, portability, isolation, ordering,
  artifact, and Git hygiene gates;
- no UI, API endpoint, reconstruction, inference, run orchestration, source
  image, or generated acquisition was committed.

## Phase 2 - Production Reconstruction

### Task 6 - Port Reconstruction Contracts and Core Geometry

Status: `COMMITTED`

Work:

- port schemas, calibration, placement, registration building blocks, and focused tests from the audited transfer bundle;
- remove all AI Studio coupling;
- preserve source provenance and record intentional differences.

Result recorded on 2026-07-23:

- added strict immutable calibration, registration-evidence, frame-transform,
  and complete transform-set contracts integrated with the standalone
  acquisition manifest, disc-side enum, identifiers, and portable paths;
- added finite evidence validation, robust common-center calibration,
  conservative native-pixel radial-band derivation, and explicit rejection of
  incomplete, weak, degenerate, or outlier pair evidence;
- added exact 16-frame nominal placement at `22.5`-degree increments,
  homogeneous point mapping, validated forward/inverse transforms, and clipped
  source-ROI output bounds;
- added a confidence-gated global fine-angle solve anchored to frame 1 with
  fixed-center, scale, residual, `+/-2`-degree correction, and four-pixel loop
  closure gates;
- added a complete-source similarity pose graph that preserves all source
  corners and reports uncropped union bounds without allocating a full output;
- pinned direct NumPy `2.2.6` use while intentionally deferring OpenCV image
  matching, masks, rendering, and artifacts to later approved tasks;
- documented the exact ignored transfer provenance and all intentional
  standalone differences; production code has no transfer or AI Studio
  import/runtime coupling;
- passed 14 focused reconstruction tests and 94 backend tests total, strict
  formatting/lint/type gates, frontend/Electron tests and builds, dependency
  checks, npm audit, portability/isolation scans, and Git whitespace hygiene;
- no source image, generated reconstruction, API, database change, inference,
  UI, or transfer file was committed.

### Task 7 - Modular Dense/Projective Reconstruction

Status: `COMMITTED`

Work:

- convert proof algorithms into services;
- joint 16-frame solve and held-out validation;
- explicit closure and failure gates;
- upper/downside profile behavior.

Result recorded on 2026-07-23:

- added immutable dense pair-evidence records with finite native-coordinate,
  equal-count, minimum-fit, and immutable-copy guarantees;
- added deterministic spatial fit/held-out separation with bounded,
  distributed sampling so validation evidence never contributes to fitting;
- added explicit immutable lower and upper projective profile identities for
  pipeline selection and independent future qualification;
- added direct-linear homography warm starts and one normalized sparse
  nonlinear solve for 15 free frame poses with frame 1 fixed and all 16
  neighbor edges included;
- added independent per-pair native-pixel median, 95th-percentile, maximum,
  minimum-count, transform-conditioning, optimizer, and explicit `16 -> 1`
  loop-closure gates;
- made transform publication fail closed: any evidence or validation failure
  retains diagnostics but returns no frame-to-reference transform set;
- pinned SciPy `1.15.3` for supported Python 3.10-3.12 solver wheels and the
  matching `scipy-stubs 1.15.3.0` development contract;
- documented the modular image-adapter boundary, proof provenance, strict
  one-pixel policy, historical diagnostic failures, and intentional exclusion
  of decoding, OpenCV coupling, rendering, cropping, storage, API, and UI;
- passed 7 focused dense/projective tests and 101 backend tests total, strict
  formatting/lint/type gates, frontend/Electron tests and builds, dependency
  checks, npm audit, portability/isolation scans, runtime import smoke, and Git
  whitespace hygiene;
- no image, model, database, generated reconstruction, transfer file, or
  diagnostic artifact was committed.

### Task 8 - Side-Specific Center Completion

Status: `PLANNED`

Work:

- upper black-plate-only strategy;
- downside flash/screen detection, cyclic correspondence, and shared rotation;
- acquired/reference provenance separation;
- no universal hardcoded `160-degree` angle.

### Task 9 - Tiled Reconstruction and Artifacts

Status: `PLANNED`

Work:

- bounded tiled/memory-mapped rendering;
- preview, transforms, validation, coverage, provenance, BigTIFF;
- disk-space checks, atomic finalization, cancellation, and reopening validation.

## Phase 3 - Production ONNX SAHI

### Task 10 - Persistent ONNX GPU Worker

Status: `PLANNED`

Work:

- persistent ONNX Runtime CUDA FP16 session;
- warm-up/readiness;
- bounded batch execution and IO validation;
- immutable raw predictions;
- clear provider/OOM failures.

### Task 11 - SAHI 1312 Slicing and Merge

Status: `PLANNED`

Work:

- in-memory `1312 x 1312` slicing;
- initial 50-percent overlap;
- deterministic edge padding;
- saved validated batch;
- source-coordinate conversion and class-aware merge;
- known-crack boundary tests.

### Task 12 - Parallel Run Orchestration

Status: `PLANNED`

Work:

- durable state machine/checkpoints;
- CPU reconstruction and GPU inference concurrency;
- bounded queues/resources;
- cancellation/restart/retry/locking;
- reconstruction gate before result publication.

### Task 13 - Prediction Projection and Deduplication

Status: `PLANNED`

Work:

- project boxes/polygons/masks through saved transforms;
- acquired-provenance clipping;
- overlap and `16 -> 1` duplicate merging;
- link every disc result to original evidence.

## Phase 4 - Professional Application Interface

### Task 14 - Backend API and Event Boundary

Status: `PLANNED`

Work:

- FastAPI lifecycle/readiness;
- typed local endpoints;
- run commands, durable status, artifacts, models/pipelines;
- event/progress delivery;
- no heavy work in request handlers.

### Task 15 - Electron/React Shell and Design System

Status: `PLANNED`

Work:

- secure Electron lifecycle/preload;
- React routing/application shell;
- design tokens and reusable accessible components;
- typed API client and error/state foundation.

### Task 16 - Setup & Validation UI

Status: `PLANNED`

Work:

- protected model import;
- pipeline configuration/versioning;
- offline test execution;
- validation/performance diagnostics;
- approve/activate/rollback workflows.

### Task 17 - Production Run UI

Status: `PLANNED`

Work:

- readiness;
- simple Start/Stop operator workflow;
- waiting/processing/result/fault states;
- no technical settings in operator flow.

### Task 18 - History, Visualization, and Alerts

Status: `PLANNED`

Work:

- paginated history;
- tiled reconstructed-disc viewer;
- crack overlays and original evidence;
- saved alert/review state;
- report/export behavior after user specification.

## Phase 5 - Online Production and Acceptance

### Task 19 - Connector Interface and Simulator

Status: `PLANNED`

Work:

- connector contract independent of pipeline;
- signal simulator, atomic claim, acknowledgement, retry, restart, duplicate handling.

### Task 20 - Approved External Connector

Status: `BLOCKED` pending external-team contract

Work:

- implement only the selected protocol;
- real integration testing and failure recovery.

### Task 21 - Security, Recovery, and Retention

Status: `PLANNED`

Work:

- roles/secrets/path safety;
- disk-full, corrupt input, worker/GPU/database/connector failure injection;
- recovery, quarantine, retention, audit logs.

### Task 22 - Performance Qualification

Status: `PLANNED`

Work:

- production-hardware stage benchmarks;
- batch/provider comparison;
- accuracy-gated optimization;
- isolated C++/CUDA task only if evidence requires it.

### Task 23 - Windows Packaging

Status: `PLANNED`

Work:

- Electron/backend/native dependency packaging;
- clean-PC readiness;
- installer/upgrade/rollback/uninstall preserving data.

### Task 24 - Supervised Production Pilot

Status: `PLANNED`

Work:

- approved upper/down data and physical samples;
- repeated online/offline behavior;
- reconstruction, detection, projection, alert, database, recovery, and cycle-time acceptance;
- explicit user approval before unattended production.

## Task History

| Date | Task | Status | Result | Commit |
|---|---|---|---|---|
| 2026-07-22 | Initial repository README | COMMITTED | README-only root commit pushed; transfer bundle excluded | `7b0c505` |
| 2026-07-22 | Task 0 - Documentation foundation | COMMITTED | 9 linked documents; no application code; transfer bundle ignored | `8c3c3b6` |
| 2026-07-23 | Task 1 - Repository and tooling foundation | COMMITTED | Portable backend/frontend/Electron foundation; full quality and runtime smoke checks passed | `80095fd` |
| 2026-07-23 | Task 2 - Core contracts and configuration | COMMITTED | Portable path/configuration service and strict versioned contracts; complete regression gate passed | `326fad4` |
| 2026-07-23 | Task 3 - Database foundation | COMMITTED | Independent SQLite metadata, migrations, transactions, indexes, backup/recovery; full regression gate passed | `247475c` |
| 2026-07-23 | Task 4 - Manual ONNX bundle import | COMMITTED | Safe staged import, strict schemas/checksums/ONNX validation, and rollback-safe activation; full regression gate passed | `67c9c8a` |
| 2026-07-23 | Task 5 - Offline acquisition intake | COMMITTED | Explicit 16-image order, full image validation, immutable owned manifest, and atomic intake; full regression gate passed | `068e899` |
| 2026-07-23 | Task 6 - Reconstruction contracts and core geometry | COMMITTED | Standalone calibrated geometry, nominal placement, bounded global registration, and uncropped pose graph; full regression gate passed | `4d48b61` |
| 2026-07-23 | Task 7 - Modular dense/projective reconstruction | COMMITTED | Spatially held-out evidence, normalized joint 16-frame projective solve, strict pair/closure gates, and side profiles; full regression gate passed | This focused task commit |
