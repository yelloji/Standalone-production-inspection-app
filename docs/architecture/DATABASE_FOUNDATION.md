# Database Foundation

## Status

- Task: 3
- State: `COMMITTED`
- Database: standalone application-owned SQLite
- AI Studio database access: forbidden

## Ownership and Boundaries

The backend is the only process layer allowed to open the database. Electron,
React, domain contracts, and processing algorithms do not import SQLAlchemy or
access SQLite directly.

The database stores searchable metadata and durable relationships. Models,
images, masks, reports, pipeline snapshots, and other large artifacts remain
files beneath the approved data root; database rows store validated relative
paths and checksums.

Task 3 introduces metadata for:

- imported model bundles;
- immutable pipeline snapshots;
- inspection runs;
- ordered source frames;
- generated artifacts.

Task 12 extends the same application-owned database through additive migration
`0003_run_orchestration` with one cancellation/lease control per inspection
run and durable per-stage checkpoints. The detailed ownership, evidence, retry,
and recovery rules are defined in
[Durable Parallel Run Orchestration](DURABLE_PARALLEL_RUN_ORCHESTRATION.md).

The schema deliberately excludes model-import workflow, inference results,
reconstruction details, operator screens, and online connector behavior until
their approved tasks.

## Location and Portability

The default database path is:

```text
{DATA_ROOT}/database/inspection.sqlite3
```

It is resolved through `ApplicationPaths`. No database module contains a fixed
drive, repository, profile, or installation path.

Tests always use a new real SQLite file under an isolated temporary data root.
Production code never imports or opens the Gevis AI Studio database.

## Connection Policy

Every SQLite connection enables:

- foreign-key enforcement;
- write-ahead logging;
- normal synchronous durability;
- a bounded busy timeout.

Sessions are short-lived. The transaction context commits on success, rolls
back on any exception, and always closes. Repositories never commit internally,
allowing one service operation to remain one atomic transaction.

## Migration Policy

Alembic is the only production schema creation/change mechanism. Migrations are
ordered, reviewed, additive upgrades. Startup may upgrade an application-owned
database only through the explicit migration service. Runtime code does not
call `metadata.create_all`.

The initial migration creates constraints and indexes with stable explicit
names. Later changes receive new revision files; an existing migration is never
rewritten after release. Automatic production downgrade is not supported.

## Backup and Recovery

Backups use SQLite's online backup API into a temporary database under the
approved data root. The temporary backup is integrity-checked and atomically
renamed only after success.

Recovery:

1. validates the selected backup;
2. restores into a temporary database beside the target;
3. validates the restored temporary database;
4. atomically replaces the closed target database.

Recovery must run while application database sessions/workers are stopped.
Corrupt backups are rejected before the current database is changed.

## Task Boundary

Task 3 does not add API endpoints or visible UI. It does not import models,
process acquisitions, reconstruct images, or run inference.

## Task 3 Verification

Completed on 2026-07-23:

- 50 backend tests passed using isolated real SQLite files;
- migration upgrade, idempotency, required schema/indexes, and exact
  migration-to-model metadata parity passed;
- foreign keys, WAL mode, synchronous policy, and busy timeout were verified;
- repository round trips, frame ordering, constraints, atomic transactions,
  rollback, and timezone preservation passed;
- backup, integrity validation, successful recovery, corrupt-backup rejection,
  and containment rejection passed;
- Python dependency integrity, formatting, linting, and strict typing passed;
- unchanged frontend and Electron linting, typing, unit tests, and production
  builds passed;
- npm reported zero known vulnerabilities;
- runtime scans found no fixed machine paths, AI Studio coupling, or direct
  schema-creation shortcuts;
- no SQLite database file is tracked by Git, and the transfer bundle remains
  ignored.
