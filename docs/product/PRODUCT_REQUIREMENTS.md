# Product Requirements

## Product Definition

Build a professional, standalone Windows production-inspection application for the brake-disc workflow. It must run independently when Gevis AI Studio is closed or not installed.

Gevis AI Studio remains responsible for labeling, training, analysis, validation, and model export. This application is responsible for production intake, reconstruction, ONNX inference, result visualization, alerts, storage, and future online integration.

## Product Quality Goal

This is not a temporary converter or small prototype. The first release will be implemented incrementally, but its architecture, UI system, data contracts, recovery behavior, and module boundaries must support later production features without uncontrolled rewrites.

## Confirmed Current Requirements

### Standalone operation

- No runtime dependency on Gevis AI Studio, its API, database, source tree, or installation.
- No internet connection required for normal production operation.
- Models are imported manually as validated production ONNX bundles.
- The application owns its database, configuration, logs, models, and artifacts.

### Two user modes

1. `Production Run Mode` for operators.
2. `Setup & Validation Mode` for technical/developer users.

Production operators must not configure model, SAHI, reconstruction, storage, or connection parameters. Technical users configure and validate a versioned pipeline before activating it for production.

### Offline-first implementation

- The first functional workflow selects a completed folder manually.
- It validates and processes the acquisition using the same pipeline engine planned for online operation.
- Online signal integration is added only after the external acquisition-software contract is confirmed.

### Brake-disc acquisition

- One side contains exactly 16 ordered images.
- Current reference geometry is `6560 x 4948` pixels per image.
- Nominal acquisition step is `22.5 degrees`.
- Upper and downside behavior is selected/configured inside the approved pipeline, not as an application-wide mode.
- Source acquisitions remain immutable.

### Production inference

- Production model format: ONNX.
- Primary execution: ONNX Runtime CUDA FP16.
- TensorRT provider/engine optimization may be evaluated later.
- SAHI spatial slice: fixed `1312 x 1312` pixels.
- Initial overlap under validation: 50 percent.
- Batch size is measured on the production machine, approved, and saved; it is not guessed per run.
- AI inference runs on original high-resolution source frames.
- Predictions are projected onto the reconstructed disc through saved transforms.

### Professional application structure

- Electron desktop shell.
- React frontend.
- FastAPI local backend.
- Independent Python domain services and workers.
- SQLite/SQLAlchemy initial local database behind repository interfaces.
- Structured local artifact storage.
- Clear tests, documentation, logging, security, recovery, and packaging boundaries.

### Development and production windows

- Development terminals remain visible for engineering and debugging.
- The packaged production application opens only its Electron window.
- Backend and worker processes remain hidden in production.
- Operator errors appear inside the Run View; terminals and stack traces are not
  shown to production users.
- Closing the application must shut down its backend and workers cleanly, with
  no console or orphaned process left behind.

### Portable and dynamic paths

- No runtime code may depend on a developer drive, repository location, user
  profile, or fixed installation directory.
- Development paths resolve from the repository and explicit configuration.
- Packaged resources resolve from the running executable/application resource
  location.
- Writable production data resolves beneath a configurable application data
  root.
- Database, model, pipeline, log, temporary, and artifact records use validated
  relative paths beneath the approved data root.
- Moving or installing the application in another valid location must not break
  resource or data resolution.

## Confirmed Future Requirements

- Online automatic acquisition intake from the external software.
- When a crack is detected, save the complete inspection evidence.
- Show an operator alert and crack visualization.
- Show the crack on the reconstructed disc and link it to original high-resolution source evidence.
- Inspection history, reports, review state, model/pipeline identity, and processing timings.
- Additional advanced features will be specified by the user incrementally.

These requirements define extension points but are not permission to implement them during the documentation or first foundation task.

## Pending Decisions

- External online signal mechanism and acknowledgement protocol.
- Exact production cycle-time target.
- Approved batch size for `1312 x 1312` on the production ONNX model.
- Whether 50-percent overlap remains necessary after defect-level validation.
- Final production data drive/root and retention policy.
- Exact user authentication/role mechanism.
- Final report format and external system integrations.
- Whether the first production database remains local SQLite or later connects to a plant database.

## Non-Goals for the First Milestone

- A universal runtime for unrelated AI Studio projects.
- Reusing AI Studio as a production server.
- `.pt` inference in production.
- A complete C++ rewrite.
- PLC/MES integration before the external contract is known.
- Fully unattended pass/fail before supervised acceptance.
- Implementing every future UI screen in the initial task.

## Success Definition

The product succeeds when a production operator can start an approved online pipeline with one clear action, the system processes acquisitions safely and quickly, results remain traceable to immutable evidence, technical complexity stays in protected setup tools, and failures cannot appear as valid zero-defect inspections.
