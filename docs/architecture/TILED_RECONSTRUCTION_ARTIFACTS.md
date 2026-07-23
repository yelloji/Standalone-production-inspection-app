# Tiled Reconstruction Artifacts

## Status and Scope

Task 9 turns a validated 16-frame transform set into a complete, auditable
reconstruction artifact set. Rendering is bounded by tile size and does not
allocate the native full-disc image in RAM.

This task does not select transforms, infer cracks, modify the database, expose
an API, or add UI. Task 10 and later services consume the published artifacts.

## Render Contract

A render request requires:

- exactly 16 frames in explicit positions 1 through 16;
- a checksummed portable path for every immutable acquired image;
- one finite, invertible source-to-reference matrix per frame;
- the validated common source geometry;
- a portable application-data output directory;
- a bounded tile size of at most 1,048,576 pixels;
- an optional checksummed side-specific reference image and mask with an
  invertible source-to-canvas affine.

Every source checksum and image geometry is verified again immediately before
rendering. Symlinks and paths outside the configured data root remain rejected
by the central path contract. A transform whose homogeneous denominator
changes sign over a source frame is rejected because it crosses the projective
horizon and cannot describe one finite camera view.

## Full Canvas and Seam Policy

The canvas is the integer union of all four transformed corners from every
full source frame. No radial, rectangular, top, bottom, or center crop is
applied. This preserves all acquired surface evidence supplied by the cameras.

Each contributor is projectively sampled into the current tile. Overlaps use a
native-source edge-distance feather capped at 512 pixels. This gives central
image evidence more weight while retaining every valid contributor. Coverage
counts remain the exact number of acquired contributors and are independent of
blend weights.

## Center Completion and Pixel Ownership

The optional Task 8 reference layer is sampled only into pixels with zero
acquired coverage. It cannot overwrite acquired evidence.

The persisted provenance map uses:

| Value | Meaning |
|---:|---|
| 0 | no data |
| 1 | acquired image evidence |
| 2 | reference center fill |
| 3 | approved real-screen replacement, reserved |

Task 9 writes values 0 through 2. Value 3 remains reserved until a separately
approved replacement layer exists. Later inference must exclude every pixel
whose provenance is not acquired.

## Artifact Set

One successful render atomically publishes one directory containing:

- `reconstructed-disc.tif`: uncompressed RGB uint8 BigTIFF;
- `coverage-map.tif`: uint8 acquired-contributor count BigTIFF;
- `provenance-map.tif`: uint8 pixel-origin BigTIFF;
- `reconstructed-preview.png`: bounded navigation preview;
- `transforms.json`: exact source-to-canvas matrices and dimensions;
- `reconstruction-report.json`: render settings and coverage diagnostics.

The preview is assembled during tiled rendering and never requires loading the
completed native image. Every published file is returned with a streaming
SHA-256 and byte size.

## Failure Safety

Before allocating output files, the renderer estimates the uncompressed
artifact requirement plus safety overhead and checks available disk space.
Cancellation is checked for every tile.

All files are first written to a unique staging directory beside the requested
destination. BigTIFF maps are flushed and closed, all TIFF dimensions/types
and the PNG are reopened and validated, and only then is the complete
directory atomically renamed into place. Any checksum, geometry, disk,
cancellation, decode, write, or reopen failure closes mapped files and removes
staging; a partial final directory is never published.

An existing destination is rejected rather than overwritten.

## Dependency and Performance Boundary

`tifffile 2025.5.10` is the latest selected release supporting the project's
Python 3.10 floor. Uncompressed BigTIFF is intentionally favored for
predictable memory-mapped writes and lossless detail. Native production-image
size, disk throughput, compression alternatives, and cycle-time targets remain
part of Task 22 hardware qualification; performance work may not weaken
geometry, coverage, provenance, or crack evidence.

## Verification

Focused tests prove:

- complete BigTIFF/PNG/JSON publication and reopening;
- exact coverage, provenance, dimensions, checksums, and file sizes;
- weighted overlap rendering;
- reference fill of uncovered pixels without acquired-pixel replacement;
- disk-space rejection before artifact allocation;
- cancellation cleanup with no partial final directory;
- checksum mismatch and existing-output rejection;
- projective-horizon rejection before artifact allocation;
- Windows-safe mapped-file closure before cleanup/publication.
