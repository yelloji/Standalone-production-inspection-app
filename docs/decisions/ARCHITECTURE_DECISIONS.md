# Architecture Decisions

## Accepted Decisions

### ADR-001 - Standalone repository and application

- Status: Accepted
- Decision: The production application is independent from Gevis AI Studio.
- Consequence: no runtime imports, shared database, required API, or installation dependency.

### ADR-002 - Manual production model import

- Status: Accepted
- Decision: Technical users manually import validated ONNX model bundles.
- Consequence: the application copies, verifies, registers, and versions its own model package; the original import location is not a runtime dependency.

### ADR-003 - Electron, React, FastAPI, and Python workers

- Status: Accepted
- Decision: Electron provides the Windows shell, React the UI, FastAPI the local command/status boundary, and isolated Python workers the heavy processing.
- Consequence: Electron/UI never performs reconstruction or inference.

### ADR-004 - ONNX production inference

- Status: Accepted
- Decision: production does not depend on `.pt`; use ONNX Runtime CUDA FP16 initially.
- Consequence: ONNX bundle parity, input/output, preprocessing, and checksums are required.

### ADR-005 - Offline first, online through a connector

- Status: Accepted
- Decision: implement manual folder intake first; online integration uses the same manifest/pipeline through a connector interface.
- Consequence: external-protocol uncertainty cannot contaminate reconstruction/inference design.

### ADR-006 - Operator Run versus technical Setup & Validation

- Status: Accepted
- Decision: operators receive a simple Start/Stop production workflow; technical users configure, test, approve, activate, and diagnose pipelines.
- Consequence: active production parameters are immutable and hidden from operators.

### ADR-007 - Versioned immutable production pipelines

- Status: Accepted
- Decision: changes produce a new draft version; production runs store a resolved immutable snapshot.
- Consequence: old inspections remain reproducible and the last working version can be restored.

### ADR-008 - Parallel reconstruction and source-frame inference

- Status: Accepted in architecture; implementation requires validation
- Decision: CPU reconstruction and raw GPU inference may execute concurrently after intake validation. Predictions are projected/published only after reconstruction validation passes.
- Consequence: latency can be hidden without treating invalid reconstruction as success.

### ADR-009 - Tested algorithm port, not AI Studio cloning

- Status: Accepted
- Decision: port pure reconstruction contracts/algorithms with tests; rebuild production ONNX/SAHI, orchestration, database, UI, and packaging.
- Consequence: the new application preserves proven mathematics without inheriting AI Studio coupling.

## Pending Decisions

- ADR-P01: Exact online connector protocol.
- ADR-P02: Final authentication/roles implementation.
- ADR-P03: Final production data root and retention.
- ADR-P04: CUDA versus TensorRT production provider after benchmarks.
- ADR-P05: Final batch and overlap after accuracy/performance validation.
- ADR-P06: Final SQLite versus plant/server database evolution.
- ADR-P07: Final alert modalities and external result integration.

New decisions must be added here before implementation when they materially change architecture, deployment, data, security, performance, or operator behavior.
