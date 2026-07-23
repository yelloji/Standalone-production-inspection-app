# Development and Runtime Foundation

## Status

- Task: 1
- State: `COMMITTED`
- Production features included: None

## Supported Development Toolchain

- Python: `>=3.10,<3.13`; current development interpreter `3.10.0`.
- Node.js: `>=22.12,<25`; current development runtime `22.16.0`.
- npm: `>=10,<12`; current development version `10.9.2`.
- Frontend language: TypeScript.
- Package layout: npm workspaces for `frontend` and `electron`.
- Python environment: repository-local `.venv`.

Dependencies are pinned in `pyproject.toml`, workspace `package.json` files, and
the generated root `package-lock.json`.

## Development Behavior

Development commands intentionally keep backend, frontend, and Electron
terminals visible. Developers need direct logs and stack traces while building
and testing.

```text
npm run dev
  |-- visible FastAPI terminal
  |-- visible Vite terminal
  `-- visible Electron terminal
```

## Production EXE Behavior

The installed application will open only the Electron application window.
Backend and worker processes must use Windows no-console/hidden-process
creation. This behavior is implemented and tested during packaging, not faked
in the Task 1 development launcher.

All production errors appear in the application. Technical details are written
to structured local logs and shown through protected diagnostics. Closing the
application must stop its backend and workers according to the approved
shutdown policy.

## Foundation Boundaries

Task 1 creates:

- a minimal FastAPI composition root and health endpoint;
- a typed React/Vite foundation screen;
- a security-hardened Electron window foundation;
- backend and frontend smoke tests;
- lint, type, test, build, and CI-ready commands.

Task 1 does not create:

- reconstruction;
- ONNX/SAHI;
- database models;
- production run/setup screens;
- online integration;
- packaging or hidden backend process implementation.

## Confirmed Database Direction

The application will use a new standalone SQLite database through SQLAlchemy
repositories. It will never reuse or open the Gevis AI Studio database.
Database code and migrations begin only in the approved database task.

## Portable Path Rule

Task 1 contains no hardcoded developer drive path. Electron resolves the
packaged frontend relative to its compiled runtime file. Task 2 will introduce
the central data/resource path contracts before any database, model, input, or
artifact storage is implemented.

## Task 1 Verification

Completed on 2026-07-23:

- Python dependency integrity, Ruff, mypy, and pytest passed.
- Frontend and Electron lint and TypeScript checks passed.
- Frontend unit tests and both production builds passed.
- npm security audit reported zero known vulnerabilities.
- The FastAPI health endpoint returned the expected versioned response.
- The production frontend was inspected in a real browser on temporary port
  `10000`; the page returned HTTP 200 with no console, runtime, or asset errors.
- Runtime-source path scanning found no absolute Windows drive/developer paths.
