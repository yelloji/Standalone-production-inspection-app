# Side-Specific Center Completion

## Status and Scope

Task 8 defines strict assets, profiles, provenance values, angular detection,
and placement plans for the physically different upper and lower disc centers.

It does not commit a reference photograph, automatically choose an asset,
decode a reference image, create a source mask, render pixels, modify acquired
pixels, or write a reconstruction artifact. Task 9 consumes a validated plan
through bounded rendering and verifies its provenance.

## Immutable Asset Contract

Every center asset is manually imported/configured and records:

- a portable relative path beneath the approved data root;
- exact SHA-256;
- measured source center and circular mask radius;
- measured light-marker center;
- whether it is black-plate-only;
- whether real silver retaining screens are present;
- all ten measured source-screen angles for a lower assembly.

An upper asset cannot declare screens. A lower complete assembly must declare
exactly ten unique source-screen angles. No production constant points to
`upper.jpg`, `down.jpg`, a developer folder, or a proof artifact.

## Upper Strategy

The upper profile permits only an approved black circular plate:

- exclude gray support ring;
- exclude silver fixtures/clamps;
- exclude surrounding overview surface;
- rotate the light marker to the image-1 start ray;
- scale the source plate radius to the measured target opening radius;
- center it on the reconstructed disc center;
- preserve all acquired pixels above reference fill;
- mark reference pixels as inference-ineligible.

The output is a pure affine plan. Task 9 applies its plate mask only to allowed
pixels and proves acquired-pixel preservation.

## Lower Strategy

The lower profile requires the complete black center assembly with its ten real
silver screens.

### Flash detection

An image-evidence adapter produces one 360-bin angular score profile using only
acquired reconstruction pixels in the configured flash band. The core detector:

- requires exactly 360 finite bins;
- applies circular smoothing;
- detects peaks with configured distance and prominence;
- ranks peaks deterministically;
- requires exactly the configured ten strongest valid peaks;
- returns each angle, score, and prominence for audit.

The detector has no reference-image pixel input.

### Cyclic correspondence

The alignment service:

1. validates ten unique source-screen and ten unique detected-flash angles;
2. evaluates every cyclic sequence shift;
3. estimates one median shared rotation for each candidate;
4. measures circular residuals for all ten correspondences;
5. uses the light marker/image-1 start ray only to resolve the 36-degree
   physical screen-sequence symmetry;
6. applies configured median and maximum residual gates;
7. returns one scale, rotation, affine matrix, correspondence list, and
   diagnostic metrics.

No screen is independently moved, painted, or synthesized. A lower pipeline
may explicitly allow real-screen replacement, but such pixels use a distinct
provenance value and never become acquired crack evidence.

## No Hardcoded 160-Degree Rule

The historical proof's detected flash angles:

`12, 46, 77, 118, 148, 190, 222, 262, 292, 329`

and its measured source-screen angles produce a `160.0-degree` shared rotation
with `2.0-degree` median absolute spacing residual. The service reproduces this
as a test vector.

`160.0` does not appear in production configuration or implementation. A
different marker/flash dataset produces its own measured rotation, and missing,
duplicate, or high-residual evidence fails instead of falling back to the proof
angle.

## Provenance Contract

The persisted map values reserved for Task 9 are:

| Value | Meaning | Inference evidence |
|---:|---|---|
| 0 | no data | no |
| 1 | immutable acquired reconstruction | yes |
| 2 | reference center fill | no |
| 3 | explicitly approved real-screen replacement | no |

The profile always preserves acquired pixels. If later pipeline approval
permits a narrowly defined screen replacement, it remains distinguishable from
both acquired and ordinary reference-fill pixels.

## Audited Proof Provenance

Reviewed ignored evidence:

- `documents/INSPECTION_RUNTIME_REFERENCE_CENTER_PROOF_REPORT.md`
- the side-specific section of
  `documents/INSPECTION_RUNTIME_FULL_AUTOMATION_PLAN.md`
- `reference_tools/reconstruction_proofs/insert_reference_centers_preview.py`
- `reference_tools/reconstruction_proofs/render_upper_black_plate_native.py`
- `reference_tools/reconstruction_proofs/render_down_flash_aligned_native.py`

Rejected diagnostic behaviors were not ported: gray-ring insertion,
marker-only lower alignment, fixed one-step correction, independently painted
screen masks, hardcoded source paths, full-image allocation, and top-level
BigTIFF rendering.

## Verification

Focused tests prove:

- upper asset component exclusion and exact marker affine placement;
- acquired-pixel and inference-eligibility policy;
- circular detection of the ten historical flash peaks;
- invalid angular profile and insufficient-peak rejection;
- reproduction of the historical `160.0`/`2.0` evidence;
- a different dataset producing a different measured rotation;
- missing, duplicate, and excessive-residual rejection;
- wrong side/strategy/asset rejection;
- four distinct provenance values.
