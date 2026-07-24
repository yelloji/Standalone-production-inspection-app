# Pipeline and Model Lifecycle

## Principle

Technical users configure and validate production behavior once. Operators repeatedly run an immutable approved configuration.

## Production Pipeline

A pipeline snapshot identifies and configures:

- product/project identity;
- expected acquisition and side behavior;
- reconstruction profile/version;
- model bundle/version/checksum;
- inference provider and precision;
- SAHI slice, overlap, batch, and merge policy;
- confidence, IoU, class, and NMS policy;
- prediction projection/deduplication policy;
- storage, artifact, alert, report, and retention policy;
- online connector configuration reference;
- software/contract versions.

For automatic folder acquisition it also stores the portable filename
template, exact positional width/order, file-stability interval, and incomplete
cycle timeout. The machine-specific watched folder is station configuration,
not part of the portable pipeline snapshot.

The stage graph is modular:

```text
Acquisition/Input (required)
  |-- Reconstruction (optional)
  |-- AI inference (optional)
  |     `-- Normal/direct or SAHI
  |-- Prediction mapping (only when reconstruction and inference are enabled)
  `-- Durable result/artifacts
```

At least one of reconstruction or AI inference must be enabled. A
reconstruction-only pipeline has no model dependency. An inference-only
pipeline keeps predictions against source-image evidence and does not create a
reconstructed-disc artifact.

## Pipeline States

```text
Draft -> Configuration Validated -> Approved/Active
                                      |
                                      `-> previous Active becomes Approved
```

- `Draft`: editable technical configuration.
- `Validated`: the immutable contract, checksum, enabled-stage dependencies,
  and selected model passed configuration validation.
- `Approved`: authorized but not necessarily active.
- `Active`: selectable by Production Run Mode.
- `Retired`: preserved for history/rollback evidence, not new runs.
- `Rejected/Archived`: retained with reason, never usable in production.

Only a deliberate activation action changes the active version. Exactly one
snapshot may be active. Editing an approved/active pipeline creates a new draft
revision. Activating another validated revision demotes the previous active
snapshot to `Approved`, preserving a deliberate rollback path.

The application-owned SQLite database is authoritative for lifecycle state and
the active selection. Every database record points to an application-owned,
canonical JSON contract with a stored SHA-256 checksum. Run Mode resolves the
single active snapshot from the database; it never accepts a manually edited
loose configuration file.

## Configuration Workflow

1. Create or revise a pipeline draft.
2. Enable reconstruction, AI inference, or both.
3. Configure only the enabled stages.
4. Save a new immutable revision.
5. Validate the saved contract and dependencies.
6. Run controlled offline acquisition/performance validation when that
   execution layer is commissioned.
7. Approve and activate deliberately.
8. Run Mode loads the exact active revision on application start.

The current Task 16 implementation completes steps 1-5 and 7-8 for contract
and dependency validation. Controlled full-image offline execution and its
performance evidence remain a separate visible validation layer; the UI does
not falsely present that future execution as already completed.

## Model Bundle

The version-1 manual import package contains:

```text
model.onnx
model_manifest.json
classes.json
preprocessing.json
postprocessing.json
sahi_config.json
validation_results.json
checksums.json
test_vectors/
```

The authoritative schemas and safety behavior are documented in
[Manual ONNX Bundle Import](../architecture/MODEL_BUNDLE_IMPORT.md).

## Model States

```text
Imported -> Verifying -> Valid -> Approved -> Active -> Retired
                  \-> Rejected
```

Import behavior:

1. Copy into an application-controlled staging area.
2. Validate archive/path safety.
3. Verify checksums and required files.
4. Inspect ONNX input/output contract.
5. Confirm fixed `1312 x 1312` spatial input and supported batch.
6. Confirm classes/preprocessing/postprocessing.
7. Verify GPU provider compatibility.
8. Run included test vectors/parity evidence.
9. Register locally.
10. Require explicit technical approval/activation.

An invalid model never replaces the current active model. The application never continues reading from the USB/network/source import location after successful controlled import.

## Run Snapshot

Every run stores an immutable resolved snapshot containing:

- run ID and timestamps;
- pipeline ID/version/checksum;
- model ID/version/checksum;
- software/schema versions;
- input manifest and hashes;
- resolved side/profile;
- transforms and validation results;
- resolved batch/provider/thresholds;
- raw/projected/merged prediction identity;
- artifact/report checksums;
- result/review/alert state.

This allows an old result to remain explainable after configuration changes.

## Change Control

The following always create a new pipeline version:

- model;
- image count/geometry/order convention;
- reconstruction calibration or thresholds;
- side strategy/reference assets;
- slice/overlap/batch;
- confidence/IoU/NMS/merge rules;
- provider/precision;
- artifact, alert, report, or retention policy.

Activation is forbidden while a production run is using the prior active snapshot unless the orchestration design explicitly proves safe version coexistence.
