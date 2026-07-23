# Local Backend API and Events

## Status and Scope

Task 14 exposes the standalone backend through a versioned, typed, local-only
FastAPI boundary. HTTP handlers perform validation and short database
transactions, then submit heavy work to a bounded command dispatcher.

This task does not add visible UI, model import controls, setup workflows,
artifact file streaming, online connectors, or package the backend process.
Task 15 consumes these contracts through the secure Electron/React shell.

## Liveness and Readiness

`GET /api/v1/health` is process liveness used by Electron startup. It remains
HTTP 200 when the API process is running.

`GET /api/v1/readiness` separately reports:

- database readiness;
- run-command dispatcher readiness;
- event broker readiness.

Production Run UI must use readiness, not liveness, before enabling Start.
An unconfigured composition reports `not_ready` and resource/command endpoints
return 503 instead of pretending the production pipeline can run.

The FastAPI lifespan starts the command dispatcher before serving requests and
closes it after request acceptance stops.

## Typed Versioned Routes

All contracts are immutable Pydantic models that reject unknown fields.
Current routes are:

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/v1/health` | process liveness |
| GET | `/api/v1/readiness` | component readiness |
| GET | `/api/v1/models` | paginated model metadata |
| GET | `/api/v1/pipelines` | paginated pipeline snapshots |
| GET | `/api/v1/runs` | paginated durable runs |
| POST | `/api/v1/runs` | create one run/control transaction |
| GET | `/api/v1/runs/{run_id}` | run, checkpoints, artifacts |
| GET | `/api/v1/runs/{run_id}/artifacts` | artifact metadata |
| POST | `/api/v1/runs/{run_id}/start` | nonblocking start command |
| POST | `/api/v1/runs/{run_id}/cancel` | durable cancellation command |
| GET | `/api/v1/events` | bounded sequenced event polling |

List limits and offsets are bounded. Creating a run requires an existing
approved or active immutable pipeline snapshot. Duplicate identities, missing
resources, invalid contracts, disallowed lifecycle commands, queue saturation,
and unavailable services have explicit 4xx/503 responses.

Artifact endpoints return only portable metadata. Native BigTIFF file delivery
and viewer tiles belong to Task 18 and cannot be exposed as arbitrary paths.

## Background Command Boundary

`RunCommandDispatcher` owns:

- exactly one run-command worker, matching the single production GPU owner;
- a bounded pending-run semaphore;
- duplicate active run rejection;
- nonblocking submission;
- injected Task 12 execution/cancellation callbacks;
- lifecycle start/close;
- start/completion/failure/cancellation-request events.

The HTTP start handler only verifies durable state and calls `submit`. It never
invokes reconstruction, ONNX, SAHI, projection, or artifact rendering.

Errors published to UI events contain the stable exception type, not arbitrary
internal exception text or paths. Durable detailed failure remains in run
metadata/logging.

## Bounded Event Delivery

The thread-safe event broker assigns one monotonic sequence and UTC timestamp
to every event. Events may carry run, stage, bounded progress, and a short
message.

Clients poll with `after_sequence` and bounded `limit`. The broker uses a fixed
ring capacity. If a client falls behind discarded events, `gap_detected=true`
instructs it to refresh durable run state rather than assuming the event stream
is complete.

Events are transient UI notifications; SQLite runs/checkpoints/artifacts remain
authoritative after restart.

## Local Security Boundary

The production server command binds only to `127.0.0.1`. FastAPI also applies:

- trusted hosts limited to `127.0.0.1`, `localhost`, and the test host;
- development CORS origins limited to the two explicit Vite loopback origins;
- GET/POST methods only;
- `Content-Type` request header only;
- no wildcard origins or credentials.

Packaged Electron access will use the isolated preload/main-process bridge
introduced in Task 15 rather than widening browser CORS to arbitrary file or
web origins.

## Composition Rule

`create_app` accepts injected `ApiServices`:

- real short-lived SQLite session factory;
- bounded run command dispatcher connected to the concrete Task 12 stage
  adapter;
- bounded event broker.

Unit tests use a real isolated SQLite database and a controlled background
worker. The module-level foundation app remains safely unconfigured until the
desktop runtime composition has selected paths, migrated its owned database,
resolved an approved pipeline/model, and built the concrete stage adapter.

## Verification

Focused tests prove:

- unchanged liveness response;
- configured and unconfigured readiness;
- typed model, pipeline, run, checkpoint, and artifact responses;
- approved-pipeline run creation and duplicate rejection;
- nonblocking background start while heavy work is still blocked;
- duplicate active command rejection and cancellation dispatch;
- bounded ordered events and completion delivery;
- ring-buffer gap detection;
- missing/invalid resource and pagination rejection;
- untrusted Host rejection.
