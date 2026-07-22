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

## Pipeline States

```text
Draft -> Testing -> Validated -> Approved -> Active -> Retired
  \-> Rejected/Archived
```

- `Draft`: editable technical configuration.
- `Testing`: used only for controlled offline/commissioning runs.
- `Validated`: required automated and technical checks passed.
- `Approved`: authorized but not necessarily active.
- `Active`: selectable by Production Run Mode.
- `Retired`: preserved for history/rollback evidence, not new runs.
- `Rejected/Archived`: retained with reason, never usable in production.

Only a deliberate activation action changes the active version. Editing an approved/active pipeline creates a new draft version.

## Model Bundle

Manual import package must eventually contain:

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

The final exact schema is defined in the contracts task.

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
