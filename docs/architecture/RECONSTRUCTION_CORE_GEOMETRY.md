# Reconstruction Contracts and Core Geometry

## Status and Scope

Task 6 establishes the independent, deterministic geometry layer for a
16-frame brake-disc acquisition. It does not decode images, detect features,
render a reconstructed image, write artifacts, or expose an API/UI.

The implemented boundary contains:

- strict calibration and transform contracts;
- evidence records for measured adjacent-frame similarities;
- robust fixed-center calibration from measured evidence;
- exact nominal placement at `22.5`-degree increments;
- homogeneous point mapping and clipped source-ROI bounds;
- bounded global fine-angle correction with explicit loop-closure rejection;
- a complete-source similarity pose graph that computes uncropped union
  bounds.

## Coordinate Convention

- Source and output origins are the top-left pixel center.
- Positive x points right and positive y points down.
- Matrices are row-major `3 x 3` homogeneous transforms.
- `source_to_output_matrix` maps source pixel centers into reconstruction
  pixel centers.
- `output_to_source_matrix` is its validated inverse.
- Frame positions are one-based and ordered from `1` through `16`.
- Nominal frame angles are `(position - 1) * 22.5` degrees.
- Measured source-to-next-frame motion is expected near `-22.5` degrees in
  image coordinates.

No crop is silently applied by the geometry layer. The pose graph evaluates
all four original source corners and reports their complete union bounds.

## Validation and Failure Rules

Calibration:

- requires all 16 neighbor-pair attempts, including `16 -> 1`;
- accepts only fixed-camera scale in `[0.995, 1.005]`;
- accepts pair rotation within `+/-2` degrees of the expected step;
- requires at least five robust correspondences and residual at most four
  native pixels;
- requires at least five pair centers to agree;
- rejects non-finite, degenerate, outlier, or incomplete evidence;
- derives a conservative radial band visible across a full 22.5-degree
  sector.

Fine registration:

- validates every ordered pair independently;
- never converts missing or weak evidence into a nominal pass;
- requires each measured center to remain within 150 native pixels of the
  fixed calibration center;
- anchors frame 1 and solves all frame corrections jointly;
- rejects any frame correction beyond `+/-2` degrees;
- converts closure-angle residual to native outer-radius pixels and rejects
  residual above four pixels;
- publishes corrected transforms only after every gate passes.

## Dependency and Isolation Decisions

NumPy `2.2.6` is a direct pinned dependency because the global least-squares
solvers and matrix operations use it directly.

OpenCV is intentionally not a Task 6 dependency. The historical proof mixed
pure geometry with SIFT extraction, constrained image correlation, diagnostic
drawing, decoding, and file output. Those operations belong to the modular
reconstruction services in later tasks and require their own accuracy and
native-packaging qualification.

The production modules:

- import nothing from AI Studio;
- import nothing from the ignored transfer directory;
- use no absolute developer path or application-global setting;
- use the existing immutable acquisition manifest and safe relative-path
  value objects;
- keep database, API, UI, and filesystem artifact persistence outside the
  geometry layer.

## Audited Source Provenance

The algorithms were independently ported from the ignored local transfer
bundle:

- `reusable_src/inspection_runtime/schemas/reconstruction.py`
- `reusable_src/inspection_runtime/reconstruction/calibration.py`
- `reusable_src/inspection_runtime/reconstruction/placement.py`
- `reusable_src/inspection_runtime/reconstruction/registration.py`
- `reusable_src/inspection_runtime/reconstruction/uncropped.py`
- the five matching `tests/backend/test_inspection_runtime_*.py` files.

The transfer remains historical evidence only and is never imported, packaged,
or committed.

Intentional differences from the proof:

- contracts use the standalone application's schema version, identifiers,
  disc-side enum, acquisition manifest, and portable relative paths;
- American-English field names match the standalone codebase;
- list-shaped matrices became fixed-size immutable tuples;
- pair observations validate finite and non-negative evidence on creation;
- contract reconstruction after correction is fully revalidated rather than
  using unchecked model copies;
- duplicate calibration/transform JSON writers were not ported because the
  standalone application already has canonical serialization and safe storage
  boundaries;
- image feature extraction, correlation fallback, hole detection, masks,
  overlays, and rendering are deferred to their approved service tasks.

## Verification

Focused tests cover:

- contract inverse/ROI rejection;
- exact fixed-center recovery and robust outlier rejection;
- complete and weak calibration evidence failures;
- all 16 exact nominal placements;
- physical-point agreement across adjacent frames;
- forward/inverse round trips and clipped bounds;
- global correction recovery and `16 -> 1` closure;
- missing evidence, wrong center, frame-angle limit, and pixel-closure failure;
- complete-source pose recovery, union bounds, and missing-edge rejection.
