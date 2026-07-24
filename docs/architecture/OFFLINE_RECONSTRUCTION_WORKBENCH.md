# Offline Reconstruction Workbench

## Status

- Task: 16
- State: `READY FOR USER REVIEW`
- Purpose: technician-controlled commissioning and CEO demonstration
- Production Run Mode automation: not included

## Workflow

The protected Offline Validation page provides one focused reconstruction flow:

1. select `upper` or `lower`;
2. select a local folder through the sandboxed Electron directory dialog;
3. discover exactly 16 images whose filename prefixes uniquely cover `1..16`;
4. fully decode, hash, copy, revalidate, and atomically own the acquisition;
5. register all neighbor pairs including the `16 -> 1` closure;
6. reserve spatially separated evidence before joint projective fitting;
7. solve the complete cycle and apply the existing independent pixel gates;
8. render an uncropped bounded review PNG;
9. display validation metrics and the saved result inside the app.

The technician selects `3000 x 3000`, `4000 x 4000`, or `5000 x 5000` before
starting. The default is `5000 x 5000`. The uncropped reconstruction is fitted
proportionally and centered inside the exact square canvas; it is never
stretched. The PNG and JSON report are saved automatically under the
application-owned `completed/<acquisition-id>/` directory, and the UI displays
the stored relative path and confirmed pixel dimensions.

The work runs on one background CPU worker. HTTP request handlers only submit
or inspect jobs. UI polling reports `verifying`, `registering`, `validating`,
`rendering`, `completed`, or `failed`.

The page stores the active job identifier, selected folder, and selected side
in window-session storage. Navigating to another Configuration page stops only
that page's polling request; it never cancels the backend worker. Returning to
Offline Validation automatically restores the same selection and reconnects to
the same running or completed job.

## Registration

Headless OpenCV is isolated in the Python reconstruction adapter. For the
current RGB-compensated brake-disc imagery:

- SIFT discovery uses the blue channel, which preserves substantially more
  scratch evidence than grayscale in the compressed copies;
- dense bidirectional optical flow evaluates blue, grayscale, and saturation
  planes and deterministically retains the strongest correspondence set;
- spatial fit/held-out separation and the joint solver remain independent of
  channel selection;
- production publication still requires every configured held-out gate.

No OpenCV or filesystem capability is exposed to the React renderer.

## Diagnostic versus Production Output

The solver has two explicit outputs:

- `diagnostic_frame_to_reference_matrices`: available after a finite joint solve
  for a clearly labelled review preview;
- `frame_to_reference_matrices`: available only when every production gate
  passes.

A failed gate can therefore produce a useful commissioning preview but can
never be mistaken for production approval. The UI labels such output
`Validation required`.

## Real 20% Proof

The available lower-side 20% set contains 16 JPEGs at `6560 x 4948`.
The repeatable 2026-07-24 proof produced:

- all 16 neighbor registrations, including loop closure;
- median held-out residual: `0.4744 px`;
- 95th percentile: `0.8443 px`;
- maximum: `2.0291 px`;
- passing joins: `11 / 16`;
- uncropped source canvas: `31822 x 31988`;
- original proof preview: `3979 x 4000`;
- result: reviewable diagnostic, not production-approved.

The preview and copied proof inputs are runtime data under an ignored `temp`
location and are not source-controlled.

## Approved Side-Specific Center Completion

Offline reconstruction requires one checksum-validated reference for the
selected side. The original reference photographs are commissioning assets,
not source-controlled application files. A technical user imports them once
through the native desktop picker. The backend verifies the exact approved
SHA-256 value, decoded dimensions, and side before copying the file atomically
into `data/configuration/center-references/`.

The approved profiles are deliberately different:

- upper uses the calibrated black plate only and aligns its white marker to
  the image-1 acquisition start ray;
- lower uses the complete black assembly with ten real silver retainers and
  validates one cyclic pairing against the ten acquired flash positions, then
  applies the commissioned marker-to-image-1 rotation offset. Flash peak drift
  can reject a run but cannot move the steel retainers away from their approved
  alignment.

Every run independently recovers the fixed disc center and reference ray from
all 16 neighbor transforms. The completed preview then:

1. maps that native center into the selected output square;
2. finds the enclosed central no-data component;
3. rejects a component connected to the exterior or outside safe radius
   bounds;
4. solves the side-specific reference rotation;
5. fills only pixels inside both the central no-data component and approved
   reference mask;
6. verifies that zero acquired pixels changed before atomically replacing the
   preview.

The reconstruction report records profile and reference checksum, rotation,
scale, target center/radius, fill count, acquired-pixel change count, and lower
flash/residual evidence. Reference-filled pixels remain ineligible for AI
inference.

Real `5000 x 5000` validation on 2026-07-24 produced:

- lower 20% acquisition: `lower-center-approved-v1`, measured rotation
  `160.5 degrees`, `8,930,086` center pixels filled, and zero acquired pixels
  changed;
- upper 60% acquisition: `upper-center-approved-v1`, measured rotation
  `-65.400 degrees`, `8,864,750` center pixels filled, and zero acquired
  pixels changed.

The user UI check exposed a lower 60% peak-drift case where one flash maximum
was measured at `297 degrees` instead of the approved proof's `292 degrees`.
The earlier evidence-only policy moved the assembly to `162 degrees`. After
the commissioned-offset correction, the same real input produced
`160.095 degrees`, `8,945,916` filled pixels, zero acquired-pixel changes, and
the analysis display reports the corrected angle.

Both results visually match the approved proof constructions. Registration
remains honestly labelled `Validation required` when the independent one-pixel
gate fails; center completion never overrides that gate.

## Security and Portability

- source selection is available only through the narrow Electron bridge;
- paths are never hard-coded in application code;
- copied images and generated output stay below `ApplicationPaths.data_root`;
- the renderer receives job metadata, never arbitrary filesystem access;
- preview files are served by one typed loopback endpoint;
- Content Security Policy permits preview images only from the local backend
  origin;
- source folders are read-only and never modified.

## Remaining Acceptance Work

- user review of the real desktop workflow;
- profile commissioning until every held-out point satisfies the production
  gate;
- optional full-resolution BigTIFF publication after production validation;
- Run Mode automatic folder watching remains Task 17.
