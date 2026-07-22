# System Architecture

## Architectural Goal

Keep the desktop UI responsive, isolate production computation, preserve auditable state, and allow future connectors/features without coupling them to reconstruction or inference.

## Runtime Components

```text
Electron Main Process
  |-- owns the Windows application lifecycle
  |-- starts/monitors the local backend
  |-- provides controlled native dialogs
  `-- applies desktop security policy

React Renderer
  |-- Production Run UI
  |-- Setup & Validation UI
  |-- History/result visualization
  `-- System readiness and diagnostics

FastAPI Backend
  |-- local authenticated API
  |-- validation and command boundary
  |-- status/event delivery
  `-- no heavy reconstruction or inference in request handlers

Run Orchestrator
  |-- claims one run exactly once
  |-- resolves an immutable pipeline snapshot
  |-- coordinates stages/checkpoints
  |-- controls cancellation/recovery
  `-- publishes durable progress

Workers
  |-- CPU reconstruction worker(s)
  |-- persistent ONNX GPU worker
  `-- bounded image loading/preprocessing workers

Persistence
  |-- SQLite/SQLAlchemy metadata database
  `-- filesystem artifact/model/pipeline storage
```

## Critical Data Flow

```text
Offline Folder or Future Online Connector
                    |
                    v
          Intake and Immutable Manifest
                    |
          +---------+---------+
          |                   |
          v                   v
CPU Reconstruction      GPU ONNX SAHI
          |                   |
          +---------+---------+
                    v
      Reconstruction Validation Gate
                    |
                    v
       Prediction Projection and Merge
                    |
                    v
       Database + Artifacts + UI Result
```

Raw inference may execute concurrently with reconstruction, but predictions cannot be published if reconstruction validation fails.

## Future Repository Boundaries

```text
backend/
|-- app/               # lifecycle and composition root
|-- api/               # routes, API schemas, dependencies, errors
|-- core/              # configuration, logging, paths, security
|-- domain/            # pure business contracts and rules
|-- services/          # application use cases
|-- workers/           # process entry points and execution adapters
|-- database/          # models, repositories, migrations, session
`-- storage/           # safe artifact/model/pipeline persistence

frontend/
|-- src/app/           # routing, providers, application shell
|-- src/features/      # production-run, setup, history, system
|-- src/components/    # reusable design-system components
|-- src/services/      # local API/event clients
|-- src/hooks/         # reusable UI behavior
`-- src/styles/        # tokens, themes, global styling

electron/
|-- main/              # process/backend/window lifecycle
|-- preload/           # minimal typed secure bridge
`-- security/          # navigation, permissions, CSP policy

tests/
|-- unit/
|-- integration/
|-- database/
|-- api/
|-- ui/
|-- golden/
`-- performance/
```

Folders are created only when an approved task needs them.

## Dependency Rules

- Domain code imports no FastAPI, React, Electron, database model, or application-global settings.
- API routes call services; they do not reconstruct, infer, or access arbitrary paths.
- Frontend accesses backend contracts only through a typed client boundary.
- Frontend and Electron never open SQLite directly.
- Database repositories store metadata; large images and masks are filesystem artifacts.
- Reconstruction and inference are independent services joined by versioned contracts.
- Online/offline connectors feed the same intake contract.
- Workers never decide UI behavior.
- Pipeline snapshots are immutable during a run.
- The production app never imports from the AI Studio repository.

## Process Isolation

- Electron/React failure must not corrupt an active worker result.
- FastAPI remains responsive while workers run.
- One persistent GPU worker owns the loaded ONNX session.
- CPU work uses bounded processes/threads to avoid oversubscription.
- A run lock prevents duplicate ownership.
- Workers communicate through validated commands/status and durable checkpoints, not shared arbitrary mutable state.

## Storage Boundary

The source repository contains code and tracked documentation only. Runtime data resolves beneath a configurable production data root:

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

Paths are resolved and checked for containment. Production data, model binaries, databases, logs, and generated artifacts are never committed to Git.

## Reliability Rules

- Atomic metadata and artifact finalization.
- Stage checkpoints and idempotent retry boundaries.
- Disk-space gate before large output.
- Model, pipeline, input, transform, and artifact checksums.
- Operator-safe errors plus detailed local technical logs.
- A failure cannot become a zero-detection pass.
- The last approved working pipeline/model remains available for rollback.
