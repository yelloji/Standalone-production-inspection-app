# Persistent ONNX GPU Worker

## Status and Scope

Task 10 provides the standalone application's persistent ONNX Runtime CUDA
session boundary. It loads an already imported and validated model once, warms
it before readiness, accepts bounded in-memory batches, and returns immutable
raw model outputs.

This task does not create SAHI slices, preprocess camera images, decode
detections, merge predictions, orchestrate runs, expose an API, or add UI.
Those responsibilities begin in Tasks 11 through 15.

## Production Configuration Contract

The worker requires:

- a portable model path beneath the configured application data root;
- the immutable model SHA-256 recorded during import;
- the validated version-1 model and SAHI manifests;
- exactly one FP16 NCHW model input with three channels and fixed
  `1312 x 1312` spatial geometry;
- `CUDAExecutionProvider`;
- a maximum batch size explicitly listed in the bundle's validated batch
  sizes;
- one through ten warm-up executions.

For a static-batch model, its declared batch must equal the configured maximum.
A dynamic-batch model accepts batches from one through the configured maximum.

The model checksum is verified again immediately before session creation.
Relative-path containment and link rejection use the central application path
contract.

## Runtime and Readiness

`onnxruntime-gpu 1.23.2` is pinned for the supported Python and Windows
environment. The native adapter:

1. confirms that `CUDAExecutionProvider` is available;
2. creates one session with CUDA explicitly requested;
3. sets ONNX Runtime's `session.disable_cpu_ep_fallback` option;
4. confirms CUDA is the session's active first provider;
5. compares all runtime input/output names, types, ranks, and dimensions with
   the imported manifest;
6. executes the configured warm-up count;
7. validates every warm-up output before reporting ready.

There is no CPU retry or model reload per request. Calling `start` again on a
ready worker returns the same readiness identity without creating a new
session. Closing the worker is terminal.

## Inference Contract

Each request supplies a non-empty request identifier and one C-contiguous FP16
NumPy tensor. The worker validates rank, static dimensions, and batch bound
before entering ONNX Runtime.

One lock serializes session use. Task 12 may run CPU reconstruction in parallel,
but it must not issue concurrent calls into this single GPU owner.

Each successful result records:

- request identifier;
- exact model checksum;
- batch size;
- measured forward-pass duration;
- ordered named raw output tensors.

Every output is checked against its manifest type, rank, static dimensions,
and dynamic batch. The worker copies each result to application-owned
C-contiguous memory and marks it read-only so later decode/merge stages cannot
mutate the raw evidence.

The caller owns the input buffer and must not mutate it until `infer` returns.

## Failure Policy

Stable failures distinguish:

- CUDA provider unavailable or inactive;
- model checksum/session/manifest initialization failure;
- invalid input;
- invalid runtime output;
- GPU out of memory;
- other CUDA execution failure;
- invalid lifecycle state.

Initialization or warm-up failure moves the worker to `failed` and clears the
session. An inference failure never produces a partial `RawPredictionBatch`.
There is no silent CPU fallback.

Task 12 decides whether a failed request or worker requires cancellation,
bounded retry, or process restart. Task 22 qualifies batch sizes and timing on
the approved RTX 4090-class production hardware and real model.

## Verification

Focused adapter-injected tests prove:

- exactly one session creation and configured warm-up count;
- idempotent readiness and persistent session reuse;
- immutable, ordered raw output ownership;
- absent and inactive CUDA-provider rejection;
- checksum and runtime IO-contract rejection;
- wrong dtype, geometry, batch, and memory-layout rejection;
- distinct GPU OOM and output-validation failures;
- invalid warm-up output blocking readiness;
- terminal close and readiness-required inference.

The installed native package import and CUDA provider visibility are checked in
the task gate. Real-model numerical parity and production-hardware performance
remain explicit commissioning evidence, not simulated unit-test claims.
