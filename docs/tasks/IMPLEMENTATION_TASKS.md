# Implementation Tasks

## Document Status

- Current phase: Professional application interface
- Current task: Task 14 - Backend API and event boundary
- Current task status: `COMMITTED`
- Application code started: Yes, foundation only
- Production feature code started: Yes, backend pipeline and local API boundary

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

Status: `COMMITTED`

Work:

- upper black-plate-only strategy;
- downside flash/screen detection, cyclic correspondence, and shared rotation;
- acquired/reference provenance separation;
- no universal hardcoded `160-degree` angle.

Result recorded on 2026-07-23:

- added strict immutable center-asset contracts with checksummed portable
  paths, measured circles/markers, upper component exclusion, and exactly ten
  unique lower screen angles;
- added pipeline-owned upper/lower center-completion profiles with explicit
  strategies, angular thresholds, acquired-pixel preservation,
  inference-ineligible reference fill, and optional separately provenanced
  real-screen replacement;
- added an upper black-plate-only affine plan that aligns the light marker to
  the image-1 start ray, scales to the measured opening, and excludes gray
  ring, silver fixtures, and surrounding overview pixels by contract;
- added circular flash-peak detection from a 360-bin acquired-pixel angular
  score profile with deterministic smoothing, distance, prominence, count,
  and diagnostic evidence;
- added all-shift cyclic screen/flash correspondence, one shared assembly
  rotation, marker-based 36-degree symmetry resolution, and median/maximum
  angular failure gates;
- reproduced the historical `160.0`-degree/`2.0`-degree-median proof evidence
  while proving a different dataset produces its own rotation; production
  contains no fixed 160-degree fallback;
- reserved distinct no-data, acquired, reference-fill, and approved real-screen
  replacement provenance values for the Task 9 renderer and later inference
  exclusion;
- documented proof provenance, rejected diagnostic behaviors, immutable asset
  boundaries, pixel ownership, and the separation between angular detection,
  placement planning, and rendering;
- passed 8 focused center-completion tests and 109 backend tests total, strict
  formatting/lint/type gates, frontend/Electron tests and builds, dependency
  checks, npm audit, portability/isolation/hardcoded-angle scans, runtime import
  smoke, and Git whitespace hygiene;
- no reference image, generated reconstruction, source mask, database change,
  API, UI, transfer file, or diagnostic artifact was committed.

### Task 9 - Tiled Reconstruction and Artifacts

Status: `COMMITTED`

Work:

- bounded tiled/memory-mapped rendering;
- preview, transforms, validation, coverage, provenance, BigTIFF;
- disk-space checks, atomic finalization, cancellation, and reopening validation.

Result recorded on 2026-07-23:

- added strict ordered 16-frame render requests with portable checksummed
  source paths, finite invertible projective matrices, bounded tile sizes, and
  optional checksummed side-specific reference layers;
- computed the uncropped integer canvas from every full transformed source
  corner so top, bottom, outer surface, and center evidence are preserved;
- added bounded projective tile sampling with capped native-edge feather
  weights, exact acquired-contributor coverage counts, and no full native RGB
  output allocation in memory;
- applied Task 8 reference pixels only where acquired coverage is zero and
  persisted distinct no-data, acquired, and reference-fill provenance;
- generated uncompressed RGB, coverage, and provenance BigTIFF files plus a
  bounded during-render PNG preview, exact transform JSON, and reconstruction
  report;
- added streaming checksums, byte sizes, disk-capacity preflight, per-tile
  cancellation, Windows-safe mapped-file closure, TIFF/PNG reopening
  validation, failure cleanup, existing-output rejection, and atomic directory
  publication;
- pinned `tifffile 2025.5.10`, the latest selected release supporting the
  project's Python 3.10 floor;
- passed 6 focused rendering tests and the complete Python, frontend,
  Electron, build, dependency, security, portability, isolation, artifact,
  and Git hygiene gates;
- no source/reference image, generated artifact, database change, API, UI,
  inference worker, transfer file, or diagnostic output was committed.

## Phase 3 - Production ONNX SAHI

### Task 10 - Persistent ONNX GPU Worker

Status: `COMMITTED`

Work:

- persistent ONNX Runtime CUDA FP16 session;
- warm-up/readiness;
- bounded batch execution and IO validation;
- immutable raw predictions;
- clear provider/OOM failures.

Result recorded on 2026-07-23:

- added a single-owner persistent ONNX Runtime session with explicit CUDA
  provider selection and disabled CPU execution-provider fallback;
- required a portable checksummed model, exact validated runtime IO contract,
  FP16 three-channel NCHW `1312 x 1312` input, approved batch limit, and
  bounded warm-up count before readiness;
- added idempotent start, terminal close, explicit created/ready/failed/closed
  states, session reuse, and serialized inference access;
- validated every warm-up and inference output against manifest dtype, rank,
  dimensions, names, and dynamic batch before returning evidence;
- copied raw outputs into C-contiguous application-owned read-only arrays with
  request, model, batch, and forward-duration identity;
- added distinct fail-closed provider, initialization, input, output, CUDA
  execution, GPU OOM, and lifecycle errors with no partial result or CPU retry;
- pinned and imported `onnxruntime-gpu 1.23.2` and verified native CUDA
  provider visibility while keeping production-model parity/hardware timing
  as explicit commissioning evidence;
- passed 7 focused worker tests and the complete Python, frontend, Electron,
  build, dependency, security, portability, isolation, artifact, and Git
  hygiene gates;
- no model, prediction, GPU-specific machine path, database change, API, UI,
  SAHI slicing, decoder, orchestration, or generated artifact was committed.

### Task 11 - SAHI 1312 Slicing and Merge

Status: `COMMITTED`

Work:

- in-memory `1312 x 1312` slicing;
- initial 50-percent overlap;
- deterministic edge padding;
- saved validated batch;
- source-coordinate conversion and class-aware merge;
- known-crack boundary tests.

Result recorded on 2026-07-23:

- added an immutable execution configuration enforcing `1312 x 1312` FP16
  slices, the current 50-percent overlap, an explicitly bundle-validated batch
  size, class count, merge threshold, and padding value;
- added deterministic row-major 656-pixel-stride windows with far-edge
  anchoring and proved the exact 9-by-7/63-slice plan for a `6560 x 4948`
  production frame;
- added bounded generator-based RGB/BGR, scale, mean, standard-deviation,
  NCHW, and FP16 preprocessing into read-only C-contiguous in-memory batches;
- retained a smaller valid final batch and created no temporary slice image,
  slice path, or disk artifact;
- added strict decoder-box contracts, padding clipping/rejection, exact source
  coordinate conversion, source-bound clipping, and unknown slice/class
  rejection;
- added deterministic same-frame/same-class greedy merge using maximum
  IoU/intersection-over-smaller overlap, union extent, maximum confidence, and
  complete contributing-slice evidence;
- proved known horizontal and vertical boundary cracks recover their full
  source extent while different classes and separate defects remain distinct;
- passed 8 focused SAHI tests and the complete Python, frontend, Electron,
  build, dependency, security, portability, isolation, artifact, and Git
  hygiene gates;
- no image, tile, model, prediction artifact, decoder-specific code, database
  change, API, UI, orchestration, transfer file, or generated output was
  committed.

### Task 12 - Parallel Run Orchestration

Status: `COMMITTED`

Work:

- durable state machine/checkpoints;
- CPU reconstruction and GPU inference concurrency;
- bounded queues/resources;
- cancellation/restart/retry/locking;
- reconstruction gate before result publication.

Result recorded on 2026-07-23:

- added additive migration `0003_run_orchestration` with one durable
  cancellation/lease control per run and status/attempt/evidence/failure
  checkpoints for reconstruction, inference, validation, and publication;
- backfilled existing run controls during migration and made new run/control
  creation one transaction to eliminate first-owner initialization races;
- added expiring single-owner database leases with bounded heartbeat renewal,
  ownership-loss failure, active-owner rejection, and release on every exit;
- added an exactly two-worker executor so CPU reconstruction and the
  single-owner GPU inference stage run concurrently without an unbounded task
  queue;
- added portable checksummed stage evidence, regular-file/link checks,
  cumulative attempt counts, crashed-running-stage recovery, valid-checkpoint
  reuse, and tampered-checkpoint rerun;
- added cooperative durable cancellation, terminal cancelled runs, explicit
  retry-only exceptions, and a persisted one-through-three attempt limit that
  process restart cannot reset;
- placed the explicit reconstruction-pass gate before validation checkpoint
  completion and prohibited publication or completed run state until every
  gate/evidence check succeeds;
- passed 6 focused orchestration and 23 combined real-SQLite
  database/orchestration tests plus the complete Python, frontend, Electron,
  build, dependency, security, portability, isolation, artifact, and Git
  hygiene gates;
- no model, image, prediction, generated run evidence, database file, API, UI,
  online connector, transfer file, or absolute machine path was committed.

### Task 13 - Prediction Projection and Deduplication

Status: `COMMITTED`

Work:

- project boxes/polygons/masks through saved transforms;
- acquired-provenance clipping;
- overlap and `16 -> 1` duplicate merging;
- link every disc result to original evidence.

Result recorded on 2026-07-23:

- added strict source prediction, sparse mask, 16-frame projection,
  configuration, acquired-footprint, disc prediction, and original-evidence
  link contracts;
- projected source boxes and polygons with exact saved homogeneous transforms
  and warped sparse source masks with composed origin/projective geometry;
- rasterized every prediction into a bounded pixel footprint and intersected
  it only with provenance value 1 so no-data, reference-fill, and reserved
  replacement pixels cannot become crack evidence;
- derived disc boxes from trimmed acquired pixels while retaining mapped
  polygon geometry and exact read-only acquired footprints for audit/viewers;
- added deterministic same-class deduplication using exact footprint
  IoU/intersection-over-smaller, transitive union, maximum confidence, convex
  polygon hull, and stable result identity;
- proved 16 duplicate frame observations become one result linked to all 16
  original frame/box/slice records while different classes and separate
  defects remain distinct;
- replaced whole-image provenance validation with bounded chunk scanning and
  added both per-footprint and total-footprint memory rejection gates;
- passed 7 focused projection tests and the complete Python, frontend,
  Electron, build, dependency, security, portability, isolation, artifact,
  and Git hygiene gates;
- no source image, provenance artifact, prediction artifact, model, database
  change, decoder-specific code, API, UI, transfer file, or generated output
  was committed.

## Phase 4 - Professional Application Interface

### Task 14 - Backend API and Event Boundary

Status: `COMMITTED`

Work:

- FastAPI lifecycle/readiness;
- typed local endpoints;
- run commands, durable status, artifacts, models/pipelines;
- event/progress delivery;
- no heavy work in request handlers.

Result recorded on 2026-07-23:

- added immutable typed request/response contracts for liveness, component
  readiness, models, pipelines, run creation/status/checkpoints/artifacts,
  commands, and sequenced progress events;
- added paginated repository queries for models, pipelines, and runs while
  retaining short-lived transaction ownership in the backend;
- added approved-pipeline run creation, durable run/control transaction,
  lifecycle command validation, duplicate/missing/conflict/queue/service
  responses, and artifact metadata views without arbitrary file serving;
- added a one-worker bounded run dispatcher with nonblocking submission,
  duplicate active rejection, injected Task 12 execute/cancel callbacks,
  lifecycle close, and sanitized state events;
- added a fixed-capacity thread-safe event ring with monotonic sequences,
  bounded reads, validated progress pairs, and gap detection that directs UI
  clients back to durable state;
- separated process liveness from production readiness and made unconfigured
  services fail closed with 503 responses;
- added loopback Trusted Host enforcement and explicit Vite development CORS
  origins/methods/headers without wildcard or credential access;
- proved an HTTP start response completes while the controlled heavy worker is
  still blocked, so request handlers contain no reconstruction/inference work;
- passed 6 focused API/health tests and the complete Python, frontend,
  Electron, build, dependency, security, portability, isolation, artifact,
  and Git hygiene gates;
- no model, image, database file, generated run/artifact, visible UI, online
  connector, transfer file, external bind, or absolute machine path was
  committed.

### Task 15 - Electron/React Shell and Design System

Status: `COMMITTED`

Work:

- secure Electron lifecycle/preload;
- React routing/application shell;
- design tokens and reusable accessible components;
- typed API client and error/state foundation.

Result prepared on 2026-07-23:

- secured the Electron lifecycle with single-instance ownership, exact-origin
  navigation, denied permission/webview access, packaged developer-tool
  protection, and HTTPS-only external link handling;
- exposed a frozen narrow preload contract without Node, filesystem, process,
  arbitrary IPC, or arbitrary URL access;
- added a validated loopback backend adapter with explicit versioned
  route/method allow-listing, bounded timeout, sanitized unavailable state,
  and executable acceptance/rejection tests;
- added hash-based routing for Production Run, Setup & Validation, Inspection
  History, and System Status so the same routes work in development and
  packaged file loading;
- replaced the temporary foundation screen with a professional responsive
  production shell, stable navigation/status regions, station and active
  pipeline identity, protected technical-mode distinction, and honest
  not-yet-implemented states;
- added semantic design tokens and reusable typed icons, status badges,
  buttons, surfaces, headings, readiness, empty, diagnostic, and safety states;
- added a typed Task 14 API client with automatic preload/browser transport,
  stable errors, abort support, health/readiness separation, shared 15-second
  status refresh, and manual refresh;
- added React tests for route/readiness behavior and desktop/unavailable
  transports, plus Electron allow-list security tests;
- passed frontend/Electron lint, strict type checking, 7 tests, production
  builds, and a dependency audit with zero known vulnerabilities;
- passed the full Python dependency, formatting, lint, strict typing, and
  148-test regression gate;
- passed Playwright review of all four routes, live local status/refresh,
  keyboard focus, 1440x900 and 1024x768 layout with no horizontal overflow,
  zero console errors, and zero page errors;
- kept Playwright screenshots under ignored local `temp/`; no model, image,
  database, run artifact, transfer file, or absolute production path is part
  of the Task 15 source change;
- the initial implementation remained uncommitted for the agreed hands-on UI
  review.

User-directed Task 15 revision prepared on 2026-07-24:

- replaced the shared four-section navigation with two completely separate
  modes so routine operators never see technical navigation;
- made Run Mode the unconditional application default and limited it to
  production/station status, current run, latest cycle, Previous inspections,
  and a small Configuration entry;
- made Configuration Mode a distinct technical shell with Setup & Validation,
  System Status, and a persistent Return to Run Mode action;
- moved operator history into Run Mode under the plain-language name Previous
  inspections and defined every entry as one completed 16-image acquisition
  cycle with reconstruction, final defects, result, side, and durable
  evidence;
- preserved the safely locked Start action until later tasks prove an approved
  active pipeline rather than exposing a misleading control;
- added isolated tests proving default Run Mode has no technical navigation,
  Configuration Mode has no Run view, and Previous inspections remains inside
  Run Mode;
- the user accepted the revised two-mode UI on 2026-07-24, completing the
  Task 15 review gate.

### Task 16 - Setup & Validation UI

Status: `IN PROGRESS - MODEL LIBRARY AND PIPELINE LIFECYCLE READY FOR USER REVIEW`

Work:

- protected model import;
- pipeline configuration/versioning;
- offline test execution;
- validation/performance diagnostics;
- approve/activate/rollback workflows.

Model Library milestone prepared on 2026-07-24:

- composed a portable local runtime with application-owned data layout, SQLite
  migration, model storage, and model-job services while leaving production
  run commands safely unavailable;
- reused the committed staged bundle importer and all checksum, archive/path,
  ONNX graph, schema, tensor, SAHI, and parity-evidence validation;
- added one background model worker so import, archive, and filesystem deletion
  never execute inside HTTP request handlers;
- added typed APIs for model import jobs, job status, archive, delete, and
  dependency-aware model summaries;
- added safe lifecycle rules: active or pipeline-referenced models cannot be
  archived; deletion requires an archived, unreferenced model;
- added rollback-safe owned-file removal that restores the model directory if
  database deletion fails;
- added a narrow native Electron ZIP selector without exposing arbitrary
  Electron, Node, or filesystem APIs to the renderer;
- added a professional Configuration Mode library with empty/loading/error/
  success states, multiple versions, states, dates, archive, protected, and
  two-step permanent delete behavior;
- added real SQLite service/API tests and frontend/Electron workflow tests;
- passed 153 backend tests, 10 frontend/Electron tests, strict typing, lint,
  production builds, and a zero-vulnerability dependency audit;
- passed Playwright Model Library layout/action/mode-separation checks at
  1440x900 with no overflow, console errors, or page errors;
- no ONNX model, database, runtime data, screenshot, transfer file, or absolute
  production path is part of the source change;
- this Task 16 milestone remains uncommitted until user review.

Desktop review correction on 2026-07-24:

- fixed the sandboxed preload so its runtime imports only Electron and shares
  local contracts as erased TypeScript types;
- added a compiled-output regression test that rejects any local module
  `require` from the preload;
- this restores the native model-bundle picker in the Electron window after a
  development-session restart.

Pipeline lifecycle milestone prepared on 2026-07-24:

- made reconstruction and AI inference independent optional stages while
  requiring at least one enabled production stage;
- allowed reconstruction-only pipelines without an artificial model
  dependency and inference-only pipelines without reconstruction settings;
- added immutable application-owned JSON pipeline contracts with canonical
  checksums and SQLite lifecycle metadata;
- added automatic monotonically increasing revisions under a stable pipeline
  identity;
- added contract/dependency validation, deliberate approve-and-activate,
  exactly-one-active database enforcement, and rollback by reactivating a
  preserved approved version;
- added typed local API and Electron allow-list routes for create, list,
  validate, activate, and active-pipeline resolution;
- separated Configuration Mode into Pipeline Builder, Model Library, Offline
  Validation, and System Status pages;
- added modular stage cards for acquisition, reconstruction, ONNX model,
  normal/SAHI inference, confidence, overlap, batch, and immutable draft save;
- made Run Mode load and show the exact active pipeline name and revision;
- kept Start disabled until Task 17 connects actual production execution;
- explicitly kept full saved-image offline execution visible as the next
  validation layer instead of claiming that configuration validation is an
  accuracy/performance test;
- added real SQLite service/API/migration tests for modular modes, versioning,
  activation, rollback, checksums, corruption, and invalid transitions;
- passed 160 backend tests, 10 frontend/Electron tests, strict Python and
  TypeScript typing, lint and formatting, production builds, Git whitespace
  checks, and a zero-vulnerability dependency audit;
- passed Playwright verification of independent stage toggles, conditional
  model settings, approve/activate, Run Mode active identity, separate
  configuration pages, 1440x900 layout, and zero overflow, console, or page
  errors;
- this expanded Task 16 milestone remains uncommitted until user review.

Automatic acquisition contract milestone prepared on 2026-07-24:

- confirmed that production operators never browse for or order source images;
- added a portable automatic-folder naming contract with mandatory `{cycle}`
  and `{position}` tokens, fixed position width, file-stability interval, and
  incomplete-cycle timeout;
- kept the machine-specific watched folder outside the portable pipeline so a
  transferred pipeline cannot silently monitor the wrong station path;
- added deterministic filename generation, exact parsing, and positional
  ordering that never depends on lexical directory order, timestamps, or file
  arrival order;
- rejected unsafe templates, traversal, wrong extensions, invalid/out-of-range
  positions, duplicate positions, mixed cycle identities, and incomplete
  cycles;
- added Pipeline Builder controls and examples for automatic naming, stability,
  and timeout configuration;
- added Run Mode presentation for Waiting, Receiving, Verifying, Validating
  order, and Processing states with no operator file-selection controls;
- passed 168 backend tests and 11 frontend/Electron tests plus strict
  formatting, lint, typing, production builds, and dependency audit;
- passed Playwright configuration and Run Mode verification at 1440x900 with
  no horizontal overflow, console errors, or page errors;
- actual background folder watching, stable-file observation, station folder
  mapping, and automatic run dispatch remain Task 17 implementation work and
  are not falsely reported as running yet.

Offline reconstruction workbench milestone prepared on 2026-07-24:

- reprioritized Task 16 before Run Mode automation for the Monday CEO
  demonstration;
- added pinned headless OpenCV to the Python backend without adding vision or
  filesystem authority to Electron/React;
- added deterministic full-cycle image evidence for every adjacent pair and
  the mandatory `16 -> 1` loop closure;
- added color-aware coarse discovery and bounded multi-plane dense optical-flow
  fallback for the current RGB-compensated compressed inputs;
- preserved the strict spatially held-out one-pixel production gate;
- separated review-only diagnostic transforms from production-publishable
  transforms so a useful preview cannot be reported as approved;
- added bounded atomic uncropped PNG rendering without generating multi-gigabyte
  proof artifacts during commissioning;
- added one background reconstruction worker, typed submit/status/preview APIs,
  native Electron folder selection, stage progress, result metrics, and an
  in-app full-disc viewer;
- proved the real lower-side 20% set: all 16 joins completed, median `0.4744
  px`, p95 `0.8443 px`, maximum `2.0291 px`, and `11 / 16` strict join passes;
- correctly labels the real result `Validation required`; production transforms
  remain blocked because the maximum is above one pixel;
- generated a `3979 x 4000` review preview from an uncropped `31822 x 31988`
  source canvas in an ignored portable temp data root;
- passed 177 backend tests, 11 frontend/Electron tests, full strict Python and
  TypeScript typing, lint, and production builds;
- passed Playwright empty/completed Reconstruction UI checks at 1440x900 with
  the real preview loaded, no horizontal overflow, no console errors, and no
  page errors;
- fixed Content Security Policy to allow preview images only from the local
  loopback backend;
- fixed Configuration navigation continuity so leaving Offline Validation does
  not lose visible ownership of the background job; returning restores the
  folder, side, job identity, live progress, and eventual result;
- added component and visible router round-trip regression checks proving the
  same upper-side job reconnects after visiting Pipeline Builder, with no
  console or page errors;
- added a persistent output-size selector for exact `3000 x 3000`, `4000 x
  4000`, or default `5000 x 5000` automatically saved PNGs;
- fits and centers the complete reconstruction proportionally inside the
  selected square, with no crop or geometric stretching, and displays the
  saved application-relative path and decoded output dimensions;
- 60%/100% and upper-side proof data, final profile commissioning, and
  full-resolution production artifacts remain explicit follow-up work;
- this expanded Task 16 milestone remains uncommitted until user review.

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
| 2026-07-23 | Task 7 - Modular dense/projective reconstruction | COMMITTED | Spatially held-out evidence, normalized joint 16-frame projective solve, strict pair/closure gates, and side profiles; full regression gate passed | `2add121` |
| 2026-07-23 | Task 8 - Side-specific center completion | COMMITTED | Upper black-plate plan, lower flash detection/cyclic shared rotation, and explicit provenance policy; full regression gate passed | `cf0dae6` |
| 2026-07-23 | Task 9 - Tiled reconstruction and artifacts | COMMITTED | Bounded uncropped rendering, BigTIFF/preview/coverage/provenance artifacts, validation, cleanup, and atomic publication; full regression gate passed | `b063fc6` |
| 2026-07-23 | Task 10 - Persistent ONNX GPU worker | COMMITTED | Persistent fail-closed CUDA FP16 session, warm readiness, bounded batches, immutable raw outputs, and explicit provider/OOM failures; full regression gate passed | `2d3b7a2` |
| 2026-07-23 | Task 11 - SAHI 1312 slicing and merge | COMMITTED | Deterministic bounded in-memory batches, source mapping, padding rejection, and class-aware boundary-crack merge; full regression gate passed | `34b1ad4` |
| 2026-07-23 | Task 12 - Parallel run orchestration | COMMITTED | Durable leases/checkpoints, bounded CPU/GPU concurrency, cancellation/restart/retry, and pre-publication reconstruction gate; full regression gate passed | `743c3ed` |
| 2026-07-23 | Task 13 - Prediction projection and deduplication | COMMITTED | Projective boxes/polygons/masks, acquired-only provenance clipping, exact 16-view deduplication, and complete source evidence links; full regression gate passed | `dffd007` |
| 2026-07-23 | Task 14 - Backend API and event boundary | COMMITTED | Typed local resources/commands, component readiness, bounded background dispatch, sequenced events, and loopback security; full regression gate passed | This focused task commit |
