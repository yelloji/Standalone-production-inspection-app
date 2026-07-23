# Implementation Tasks

## Document Status

- Current phase: Safe foundation
- Current task: Task 1 - Repository and tooling foundation
- Current task status: `COMMITTED`
- Application code started: Yes, foundation only
- Production feature code started: No

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

Status: `PLANNED`

Work:

- safe staged import;
- checksum/schema/ONNX IO validation;
- test-vector/parity evidence;
- model lifecycle and rollback-safe activation.

### Task 5 - Offline Acquisition Intake

Status: `PLANNED`

Work:

- safe folder selection/registration;
- exactly 16 ordered immutable images;
- geometry/format/hash/duplicate/completeness validation;
- immutable acquisition manifest.

## Phase 2 - Production Reconstruction

### Task 6 - Port Reconstruction Contracts and Core Geometry

Status: `PLANNED`

Work:

- port schemas, calibration, placement, registration building blocks, and focused tests from the audited transfer bundle;
- remove all AI Studio coupling;
- preserve source provenance and record intentional differences.

### Task 7 - Modular Dense/Projective Reconstruction

Status: `PLANNED`

Work:

- convert proof algorithms into services;
- joint 16-frame solve and held-out validation;
- explicit closure and failure gates;
- upper/downside profile behavior.

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
| 2026-07-23 | Task 3 - Database foundation | COMMITTED | Independent SQLite metadata, migrations, transactions, indexes, backup/recovery; full regression gate passed | This focused task commit |
