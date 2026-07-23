# Prediction Projection and Deduplication

## Status and Scope

Task 13 maps source-frame predictions through the exact saved frame-to-canvas
transforms, excludes all non-acquired reconstruction pixels, and combines
duplicate detections observed in the 16 acquisition views.

Inference evidence still originates from the original high-resolution images.
Reference center pixels are visualization only and can never create a valid
disc prediction.

This task does not implement a model-specific output decoder, database
persistence, API, UI, alert policy, or operator review workflow.

## Source Evidence Contract

Each source prediction carries:

- a unique source prediction identifier;
- source frame index;
- model class index and confidence;
- source-coordinate box;
- one or more contributing SAHI slice indices;
- optional source-coordinate polygon;
- optional bounded sparse boolean mask with source origin.

All identifiers, indices, confidence, finite geometry, polygon size, box
ordering, mask dtype/content, and source-frame containment are validated.

Projection requires exactly one finite invertible saved transform for each
frame index `0..15`. Missing, duplicate, or unknown frame identities fail the
complete operation.

## Box, Polygon, and Mask Projection

Boxes become four-point source polygons. Supplied polygons retain their exact
vertices. Both are mapped with the saved homogeneous projective matrix.

When a source mask exists, its mask-origin translation is composed with the
same projective matrix and the mask is warped with nearest-neighbor sampling.
Without a mask, the mapped box/polygon is rasterized.

Every prediction therefore receives a pixel-exact projected footprint in
addition to its mapped polygon. Per-footprint and total-footprint limits are
checked before large allocation.

## Acquired-Provenance Gate

The Task 9 provenance map is validated in bounded chunks. Only value `1`
(`acquired`) is eligible prediction evidence.

Each projected footprint is intersected with acquired provenance:

- no-data pixels are removed;
- reference center-fill pixels are removed;
- reserved approved-screen-replacement pixels are removed;
- a footprint with no acquired pixels is discarded.

The result is trimmed to its remaining acquired extent. Its `disc_box` is
derived from that trimmed footprint. The mapped polygon remains geometric
audit information; the acquired boolean footprint is authoritative when the
polygon crosses holes or reference regions.

## Exact Cross-View Deduplication

Deduplication is strictly same-class. Candidate overlap is calculated from
their acquired boolean footprints, not from reference pixels or loose visual
boxes.

The score is the larger of:

- intersection over union;
- intersection over the smaller acquired footprint.

When the saved threshold is met, the result contains:

- union of acquired footprint pixels;
- acquired-derived disc box;
- convex hull of all mapped polygon vertices;
- maximum confidence;
- a deterministic disc prediction identifier;
- sorted links to every original source prediction, frame, source box, and
  contributing SAHI slice.

Transitive overlap is evaluated until stable. Different classes and spatially
separate defects remain distinct. Input ordering cannot change result identity
or evidence links.

## Memory and Failure Policy

One projected footprint is bounded by configuration, initially 4,194,304
pixels. All pre-merge footprints share a second total memory budget, initially
67,108,864 boolean pixels.

The native provenance image is never copied or globally sorted; value
validation reads bounded chunks. Invalid provenance values, excessive
footprints, bad source geometry, unknown classes/frames, unsafe transforms, and
duplicate source IDs fail without publishing partial results.

## Verification

Focused tests prove:

- 16 identical frame detections become one disc prediction with 16 evidence
  links;
- reference-overlap geometry is clipped to acquired pixels;
- reference-only predictions are discarded;
- polygons and sparse masks follow a saved projective transform;
- deterministic same-class merging and strict cross-class separation;
- separate same-class defects remain separate;
- invalid provenance/frame/class/identity/source bounds are rejected;
- per-footprint and total-footprint memory gates fail before unsafe allocation.
