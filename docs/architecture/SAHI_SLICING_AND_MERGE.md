# SAHI Slicing and Merge

## Status and Scope

Task 11 converts one decoded RGB source frame into bounded FP16 batches for the
Task 10 worker, then maps decoder-produced tile boxes back to the original
frame and merges duplicate same-class evidence.

Inference remains on the original high-resolution acquisition frames, not the
reconstructed visualization. This task is decoder-neutral: the imported
bundle's approved decoder converts raw Task 10 tensors into `SliceDetection`
records at the later composition boundary.

This task does not write tile images, run ONNX itself, project predictions onto
the reconstructed disc, persist results, orchestrate runs, expose an API, or
add UI.

## Immutable Execution Configuration

The current production profile requires:

- fixed `1312 x 1312` slice geometry;
- exactly 50-percent horizontal and vertical overlap;
- an FP16 preprocessing manifest;
- a selected batch size present in the model bundle's validated batch list;
- a positive model class count;
- an explicit overlap-merge threshold in `(0, 1]`;
- an explicit uint8 padding value, initially zero.

Changing overlap, batch, preprocessing, class inventory, padding, or merge
threshold creates a new pipeline snapshot and requires validation. Task 11 does
not silently select a batch size from available GPU memory.

## Deterministic Window Plan

Window origins are row-major. The stride is 656 pixels. For dimensions larger
than one slice, the final origin is anchored to the far source edge. This
avoids uncovered edge strips while keeping stable window identity.

A `6560 x 4948` production frame produces exactly 9 columns by 7 rows, or 63
slices. All 16 frames therefore produce 1008 slices.

Images smaller than one slice use one top-left window. Missing right/bottom
pixels are filled with the configured raw uint8 padding value. Each window
records its valid source width and height so detections entirely inside padding
can never become source evidence.

## In-Memory Preprocessing and Batches

The source boundary accepts only `H x W x 3` uint8 RGB arrays. For each bounded
batch:

1. copy each source region into a fixed raw tile;
2. reverse RGB to BGR only when the imported preprocessing contract requires
   it;
3. apply `(pixel * scale - mean) / standard_deviation`;
4. transpose HWC to NCHW;
5. store the result in one C-contiguous FP16 batch tensor;
6. mark the complete tensor read-only.

The generator yields one batch at a time and retains a smaller final batch
instead of inventing dummy inference items. No JPEG/PNG/TIFF slice files or
thousands of temporary paths are created.

## Source Mapping and Padding Rejection

Each decoded tile box contains its slice index, class index, confidence, and
`x1, y1, x2, y2` coordinates within `0..1312`.

Before source mapping:

- the slice and class identities are validated;
- coordinates and confidence must be finite and bounded;
- boxes are clipped to the window's valid source area;
- a box with no valid area after clipping is discarded.

The remaining coordinates are translated by the exact window origin and
clipped to source dimensions.

## Class-Aware Merge

Only detections from the same source frame and class may merge. Candidates are
processed in deterministic confidence/geometry order.

The overlap score is the larger of:

- intersection over union (IoU);
- intersection over the smaller box (IoS).

IoS is required for crack boundaries: one tile may contain only a truncated
part while an overlapping tile contains the complete crack. When the saved
threshold is met, the merged box uses the union extent, maximum confidence,
and sorted unique contributing slice indices. Transitive overlap is evaluated
until the group is stable.

Different classes and spatially separate defects remain separate. The exact
merge threshold is pipeline evidence and is qualified against known cracks;
it is not hidden in the worker.

## Verification

Focused tests prove:

- the exact 63-window production plan and row-major identities;
- far-edge anchoring without missing source pixels;
- deterministic small-image padding;
- RGB/BGR, scale, mean, standard-deviation, NCHW, and FP16 preprocessing;
- bounded ordered batches and a retained smaller final batch;
- horizontal and vertical boundary cracks merging to their full source extent;
- deterministic class-aware behavior with separate defects retained;
- padded-only detection rejection and partial-box clipping;
- invalid overlap profile, source dtype, slice identity, and class rejection.
