# Modular Dense and Projective Reconstruction

## Status and Scope

Task 7 converts the accepted parts of the dense/projective diagnostic proof
into independent production services. It establishes:

- immutable dense pair-evidence records;
- deterministic spatial fit/validation separation;
- distinct upper and lower projective pipeline profiles;
- a normalized joint solve for 15 free frame homographies with frame 1 fixed;
- independent native-pixel validation for all 16 neighbor joins;
- an explicit `16 -> 1` loop-closure result;
- fail-closed transform publication.

This task does not select a source folder, infer image order, decode images,
extract SIFT/optical-flow features, render pixels, blend seams, crop a disc,
write artifacts, or expose API/UI commands. Those responsibilities remain
separate adapters and later approved services.

## Modular Boundary

```text
image evidence adapter (later)
        |
        v
native matched point pairs
        |
        v
spatial evidence splitter
  |-- fit points
  `-- held-out points
        |
        v
joint projective solver
        |
        v
all-pair held-out gate
  |-- passed: 16 transforms may continue
  `-- failed: no transforms are published
```

The solver is independent of OpenCV. A later evidence adapter may use a
qualified image library without changing the fit/validation or publication
contract.

## Dense Evidence Rules

- A pair record maps one source frame to its exact next frame.
- The full cycle is `1 -> 2` through `15 -> 16`, then `16 -> 1`.
- Source and target arrays must be finite `N x 2` native-pixel coordinates with
  equal counts.
- At least ten candidate correspondences are required before splitting.
- Evidence is ordered deterministically by spatial tile, x/y location, and
  original stable order.
- Every fifth ordered point is reserved for validation by default.
- Validation points never enter homography estimation or bundle fitting.
- Fit and validation arrays are copied, immutable, and separately count-gated.
- Bounded, spatially distributed subsampling avoids allowing one dense region
  to dominate runtime or confidence.

## Joint Projective Solve

- Frame 1 is the fixed identity reference.
- Each pair's fit evidence supplies a direct-linear-transform warm start.
- The first 15 neighbor homographies initialize frames 2 through 16.
- All 16 pair edges, including loop closure, contribute to one normalized
  nonlinear least-squares fit.
- Pixel coordinates are normalized by source width during optimization and
  transformed back to native coordinates afterward.
- Sparse Jacobian structure limits work to the two poses touched by each edge.
- Each output matrix must be finite, invertible, and below the configured
  condition-number bound.

SciPy `1.15.3` is pinned as the newest selected release with a Windows wheel
for every supported Python version beginning at Python 3.10. Matching
`scipy-stubs 1.15.3.0` is pinned for the strict development type gate.

## Side Profiles

Two independent immutable profile identities exist:

- `brake-disc-lower-projective-v1`
- `brake-disc-upper-projective-v1`

Both currently use the proven quarter-scale evidence-adapter setting, top
exclusion fraction `0.18`, and the same strict native-pixel validation gate.
They remain distinct because future evidence masks, physical boundaries,
lighting behavior, or qualified thresholds may differ by side. Side selection
belongs to the immutable pipeline snapshot; it is not an application-wide
mode and is never inferred from an image.

## Validation and Publication Gate

Every pair requires:

- at least eight fit correspondences;
- at least five spatially held-out correspondences;
- held-out median at most `1.0 px`;
- held-out 95th percentile at most `1.0 px`;
- held-out maximum at most `1.0 px`.

The optimizer must also report success and every frame transform must pass its
condition-number gate. Pair 16 is explicitly marked as loop closure.

If any gate fails:

- the result is `passed = false`;
- exact pair and global failure reasons are retained;
- metrics remain available for technical diagnosis;
- `frame_to_reference_matrices` is `None`;
- rendering and downstream publication cannot receive an apparently valid
  transform set.

This preserves the diagnostic evidence: the historic downside proof reached a
`1.389 px` maximum and the upper proof reached `3.915 px`; both are useful
experiments but neither can silently pass the configured one-pixel maximum.

## Audited Proof Provenance

Reviewed ignored evidence:

- `documents/INSPECTION_RUNTIME_PROJECTIVE_PROOF_REPORT.md`
- `documents/INSPECTION_RUNTIME_DENSE_60_PERCENT_PROOF_REPORT.md`
- `documents/INSPECTION_RUNTIME_UNCROPPED_PROOF_REPORT.md`
- `documents/INSPECTION_RUNTIME_UPPER_SIDE_PROOF_REPORT.md`
- `reference_tools/reconstruction_proofs/run_projective_bundle.py`
- `reference_tools/reconstruction_proofs/render_full_60_percent_proof.py`
- the Task 6 proof variants and Task 6 core geometry port.

The reference scripts are never imported or executed by production. Hardcoded
paths, filename ordering, top-level execution, image decoding, artifact
writing, and diagnostic-only rendering were intentionally excluded.

## Verification

Focused tests prove:

- deterministic split independent of input enumeration;
- fit/validation disjointness and immutable evidence;
- malformed and insufficient evidence rejection;
- explicit, distinct upper/lower profiles;
- exact recovery of a synthetic 16-frame projective cycle;
- subpixel held-out success and explicit closure validation;
- transform suppression after a held-out closure outlier;
- transform suppression after insufficient held-out evidence;
- incomplete and misordered cycle rejection.
