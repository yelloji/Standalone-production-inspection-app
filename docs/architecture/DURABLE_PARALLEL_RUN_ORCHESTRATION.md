# Durable Parallel Run Orchestration

## Status and Scope

Task 12 coordinates one inspection run across CPU reconstruction and GPU
inference, durable validation, and final publication. It provides process-safe
ownership, bounded concurrency, cooperative cancellation, restart checkpoints,
and explicit retry policy.

The coordinator is framework-neutral. Concrete stage adapters connect Tasks
5–11 and later Task 13 persistence. Task 12 does not expose an API or UI and
does not define an online connector.

## Durable Database State

Additive migration `0003_run_orchestration` creates:

- `run_controls`: one row per inspection run containing durable cancellation,
  lease owner, lease expiry, and update time;
- `run_stage_checkpoints`: one row per run/stage containing status, cumulative
  attempt count, checksummed evidence path, failure code, and update time.

Existing runs are backfilled during migration. New inspection runs create their
control row in the same database transaction, so two coordinators cannot race
to initialize ownership.

The four stage identities are:

```text
reconstruction ─┐
                ├─> validation gate -> publication
inference ──────┘
```

Checkpoint states are `pending`, `running`, `completed`, `failed`, and
`cancelled`. Run states remain `created`, `running`, `completed`, `failed`, and
`cancelled`.

## Lease and Single-Owner Policy

Before changing a run, a coordinator acquires its database lease with a unique
owner ID. A non-expired lease held by another owner rejects the second
coordinator without changing run state.

While work is active, bounded waits renew the lease and read durable
cancellation state. Losing ownership is a hard failure. The owner releases the
lease on every normal, failed, or cancelled exit.

A crashed process leaves an expiring lease. A later coordinator may claim the
run only after expiry and continue from valid checkpoints.

## Bounded Parallelism

One `ThreadPoolExecutor` owns exactly two workers:

- the CPU reconstruction stage;
- the single-owner GPU inference stage.

Validation runs only after both have successfully completed. Publication runs
only after validation. No unbounded queue, per-slice future, or nested worker
pool is created by orchestration.

Task adapters receive a cooperative cancellation callback. Long loops such as
tiled rendering and SAHI batching must check it at their existing bounded work
boundaries.

## Checksummed Stage Evidence

Every successful stage returns one portable relative evidence path and SHA-256.
The stage is marked completed only after the coordinator proves the file:

- resolves beneath the approved data root;
- exists as a regular non-link file;
- matches the supplied checksum.

On restart, completed stage evidence is reverified before reuse. Missing,
linked, or tampered evidence invalidates the checkpoint and causes the stage to
run again within its remaining attempt limit.

A checkpoint left in `running` by a crash is not trusted and is rerun.

## Reconstruction Gate

Validation evidence must explicitly set `reconstruction_passed=true`. The gate
is checked before the validation checkpoint can become completed. This ordering
is critical: even a crash immediately after checkpoint persistence cannot turn
a failed reconstruction into publishable evidence.

Publication is never submitted when the gate fails. A run cannot become
completed until publication evidence itself is checksummed and checkpointed.

## Retry and Cancellation Policy

Only `RetryableStageError` is retried. The configured attempt limit is from one
through three and defaults to two. Unknown, validation, checksum, provider,
input, output, and other failures fail immediately; they are not relabeled as
transient.

Attempt counts persist across restart, so process restart cannot reset a retry
budget.

Cancellation is durable in `run_controls`. It is propagated to both parallel
stages, prevents validation/publication, records cancelled checkpoints, marks
the run cancelled, and releases ownership. A cancelled run is terminal; a new
inspection request receives a new run identity.

## Recovery Behavior

A failed run may be explicitly resumed:

- valid completed reconstruction/inference evidence is reused;
- invalid completed evidence is rerun;
- failed or crash-interrupted stages use only remaining attempts;
- started time is preserved and terminal time is replaced;
- publication is still gated by a newly completed or safely reused validation
  checkpoint.

Completed and cancelled runs cannot be executed again.

## Verification

Focused real-SQLite tests prove:

- migration/model parity, backup revision, and run-control creation;
- true simultaneous reconstruction and inference;
- four durable checksummed checkpoints and terminal completion;
- failed reconstruction validation blocking publication;
- restart reuse of valid evidence and cumulative attempts;
- tampered completed evidence forcing rerun;
- one bounded retry only for an explicitly retryable error;
- durable cancellation reaching both workers and the run;
- active lease rejection without run-state mutation;
- lease release on success, failure, and cancellation.
