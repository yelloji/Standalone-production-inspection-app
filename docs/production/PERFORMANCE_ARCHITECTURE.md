# Performance Architecture

## Goal

Minimize production latency without weakening crack recall, reconstruction geometry, evidence traceability, recovery, or correctness.

No timing is promised until measured with the approved production model, images, hardware, and storage.

## Reference Hardware and Workload

- GPU: NVIDIA RTX 4090-class, normally 24 GB VRAM.
- System RAM: 128 GB.
- Storage: fast production NVMe required; exact layout pending.
- Per side: 16 images at approximately `6560 x 4948`.
- SAHI slice: `1312 x 1312`.
- Initial overlap under validation: 50 percent.
- Approximate workload: 63 slices/image, 1008 slices/side.
- At validated batch 32: approximately 32 GPU batches; batch 32 is not assumed to fit until tested.

## Concurrency Model

```text
Validated acquisition
        |
        +-----------------------+
        |                       |
        v                       v
CPU registration/render   GPU SAHI inference
        |                       |
        +-----------+-----------+
                    v
       Validation/projection/merge
                    v
        Critical result persistence
                    v
     Large audit artifacts in background
```

## GPU Strategy

- One persistent ONNX Runtime session/worker.
- CUDA FP16 first; TensorRT provider evaluated through a separate validated optimization task.
- Fixed spatial input `1312 x 1312`; batch dimension/configuration explicitly supported by the bundle.
- Warm-up before Run readiness.
- Bounded prefetch and pinned memory where profiling validates benefit.
- Asynchronous host-to-device behavior where safe.
- No model reload per inspection.
- No repeated unconditional CUDA cache clearing.
- Provider/OOM failure blocks a valid result; it does not silently fall back to slow CPU in online production.

## CPU and RAM Strategy

- Stream/hash inputs and decode with bounded workers.
- Reuse decoded data only within explicit memory limits.
- Avoid Python per-pixel loops; use OpenCV/NumPy/native libraries.
- Bound OpenCV/native thread counts to prevent oversubscription.
- Use process isolation for CPU-heavy Python orchestration where required.
- Use tile/memory-mapped rendering rather than dense full-canvas floating-point allocation.

## Disk and Artifact Strategy

- Critical result: validation, transforms, predictions, compact preview, database status.
- Background audit: full native BigTIFF, detailed provenance, complete evidence package when policy requires it.
- Atomic partial/final paths.
- Disk-space preflight based on expected output.
- Benchmark tiled lossless compression before selecting final encoding.
- No thousands of temporary SAHI tile images; slices are generated in memory.

## UI Performance Strategy

- UI receives metadata, progress, compact previews, and bounded prediction data.
- Large artifacts use tile/stream endpoints.
- Progress updates are rate-limited/coalesced.
- History is indexed and paginated.
- Viewers load only visible tiles and overlays.
- Electron hardware acceleration is measured; it may be disabled if Chromium materially competes with inference.

## Required Benchmarks

Measure independently:

- folder discovery and validation;
- hashing;
- JPEG decoding;
- SAHI slice generation;
- host-to-GPU transfer;
- ONNX forward pass;
- decode/NMS/slice merge;
- registration and transform solve;
- tiled reconstruction;
- projection/deduplication;
- database transaction;
- preview and BigTIFF output;
- end-to-end cold and warm latency;
- peak RAM, VRAM, CPU, GPU, and disk throughput.

Report median, p95, maximum, cold/warm behavior, and accuracy for repeated representative runs.

## Optimization Gates

- Batch sizes 8, 16, 24, and 32 are profiled at `1312 x 1312`.
- Overlap reduction is permitted only after known-crack boundary/recall validation.
- TensorRT is permitted only after ONNX Runtime parity and deployment compatibility checks.
- INT8 is deferred until representative calibration and defect-level accuracy approval.
- Custom C++/CUDA is permitted only for a measured bottleneck through an isolated contract and separate approved task.
