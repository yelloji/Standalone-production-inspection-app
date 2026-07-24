# User Modes and UI/UX

## Design Objective

Provide a premium, calm production interface for operators and a powerful protected commissioning interface for technical users. Complexity must exist where required without being exposed during routine online production.

## Application Navigation

```text
Application start
      |
      v
Run Mode (default, operator)
  - Current production run
  - Latest completed cycle
  - Previous inspections
  - Small protected Configuration entry
                 |
                 v
Configuration Mode (technical)
  - Pipeline Builder
  - Model Library
  - Offline Validation
  - System Status
  - Return to Run Mode
```

Run Mode and Configuration Mode are separate workspaces, not equal sections in
one common navigation. Opening the application always enters Run Mode.
Operators do not see the technical navigation. Entering Configuration Mode
replaces the Run workspace completely and will use protected technical access
when authentication is implemented. A persistent, obvious action returns to
Run Mode.

## Production Run Mode

### Operator responsibility

The operator performs one primary action:

```text
[ START RUN ]
```

After start:

```text
System: Running
Pipeline: Brake Disc Inspection v1
Model: Crack Detection v4
Online connection: Ready
Current state: Waiting for acquisition signal

[ STOP RUN ]
```

The operator does not edit:

- model or provider;
- confidence/IoU;
- slice, overlap, or batch;
- reconstruction calibration/thresholds;
- upper/down strategy details;
- input/output/database paths;
- online connector settings.

### Production states

```text
Not Ready -> Ready -> Starting -> Running -> Processing -> Alert/Result
                  \-> Stopping -> Stopped
Any active state -> Faulted
```

For an automatic folder pipeline, the waiting/receiving portion is shown in
plain language:

```text
Waiting for acquisition -> Receiving 1/16 ... 16/16
 -> Verifying files -> Validating order -> Processing
```

The operator never browses for production images. Technical configuration owns
the filename template and station folder mapping.

Every state must show a plain-language explanation and permitted next action.

### Readiness panel

Before Run is enabled, the UI checks:

- active approved pipeline;
- active validated ONNX model;
- GPU/provider readiness;
- database readiness;
- storage space/readiness;
- reconstruction profile/reference readiness;
- online connector readiness when online mode is selected;
- absence of another station/run lock conflict.

### Result behavior

Confirmed future behavior:

- one production cycle represents one complete ordered acquisition, currently
  16 source images for one disc side;
- clear pass/alert state;
- crack count and location visualization;
- reconstructed-disc overlay;
- original-image evidence link;
- saved run identity and timestamp.

Exact audible/visual alert policy remains pending user guidance.

## Setup & Validation Mode

Protected technical workspace for:

- manual ONNX bundle import and verification;
- pipeline creation/versioning;
- reconstruction-profile configuration;
- offline test acquisitions;
- model/parameter comparison;
- SAHI slice/overlap/batch configuration;
- confidence/IoU/NMS configuration;
- GPU and performance validation;
- online connector commissioning;
- logs, diagnostics, storage, and recovery;
- approval and activation.

Technical settings are grouped by responsibility rather than placed on one large form.

### Configuration navigation

- **Pipeline Builder** is the first page because reconstruction-only products
  must not be forced to select a model.
- **Model Library** imports and manages validated ONNX bundles independently.
- **Offline Validation** owns controlled saved-image execution, evidence,
  accuracy, and performance checks.
- **System Status** owns health and diagnostics.

Pipeline Builder presents reconstruction and AI inference as independent
stage cards. Disabling a stage also disables and excludes its settings from
the saved contract. Prediction mapping becomes applicable only when both
stages are enabled.

Saved versions are shown beneath the builder with explicit lifecycle actions:
`Validate`, `Approve & activate`, and `Used by Run Mode`. Activation requires a
confirmation and never edits the active snapshot in place.

### Offline acquisition preparation

The first functional Offline Validation step is acquisition preparation:

- select a saved pipeline revision;
- select a folder through the desktop application;
- show all 16 ordered images before copying;
- allow explicit Up/Down correction when filenames do not implement the
  pipeline naming contract;
- show the calculated `0` through `337.5` degree positions;
- validate and copy in the background;
- present success or an actionable technical error.

Offline preparation never requires Run Mode and never changes the active
production pipeline.

## Inspection History

For operators this is named **Previous inspections** and remains inside Run
Mode. It is a secondary action, not a permanent technical navigation section.
The current/latest cycle remains the primary Run view.

Each history entry is one completed acquisition cycle and owns:

- the 16 original ordered acquisition images;
- one reconstructed disc;
- final deduplicated predictions/defects;
- pass/alert result and disc side;
- model/pipeline identity and timestamps.

Configuration controls will determine which evidence layers operators may see,
such as reconstructed image, prediction overlay, defect list, confidence, and
original source images.

Planned capabilities:

- indexed/paginated run list;
- filter by date, result, side, pipeline/model, status, or identity;
- reconstruction preview;
- prediction overlay and source evidence;
- technical stage timing and failure diagnostics based on role;
- safe export/report actions.

Full-resolution BigTIFF data is never loaded into one browser canvas. Use navigation previews and on-demand tiles.

## System Status

Show concise readiness for:

- application/backend;
- external online connector;
- GPU and inference provider;
- active model/pipeline;
- database;
- production storage and free space;
- worker health;
- current version.

Technical users may open detailed diagnostics. Operators receive only useful production messages.

## Visual Architecture

### Application shell

- Run Mode has no technical left navigation;
- Run Mode shows only production/station status, current run, latest cycle,
  previous inspections, and a small protected Configuration entry;
- Configuration Mode has its own stable technical left navigation;
- Configuration Mode never shows the live Run workspace;
- both modes retain clear application/backend and active pipeline identity;
- Run Mode resolves and displays the exact active pipeline name and revision
  from the backend rather than using placeholder text;
- Configuration Mode has a persistent Return to Run Mode action;
- non-blocking notification/alert areas remain mode appropriate.

### Design system

- semantic design tokens for color, spacing, typography, radius, elevation, and motion;
- reusable buttons, inputs, cards, tables, dialogs, status badges, progress, alerts, viewers, and empty/error states;
- light/dark capability without using color as the only status signal;
- accessible contrast, focus, keyboard navigation, and readable production distances;
- consistent loading, disabled, warning, fault, confirmation, and recovery behavior.

### Performance rules

- no full-resolution image transfer through Electron IPC;
- no giant DOM tables;
- paginated/virtualized history and defect lists;
- lazy routes and viewers;
- tiled image loading by viewport;
- bounded prediction overlay rendering;
- rate-limited progress/status updates;
- no unnecessary production animations.

## Safety UX

- Destructive cleanup is explicit and never combined with normal Run actions.
- Activating a pipeline requires validation and confirmation.
- Importing a model never activates it automatically.
- Changing settings creates a new draft version.
- Settings cannot mutate the active running pipeline.
- A fault is not displayed as an empty successful result.
- Stop and emergency/fault behavior are visually different and documented with the external control team.

## Pending UI Decisions

- Final branding, logo, color system, and typography.
- Exact operator/admin authentication method.
- Touch-screen versus mouse/keyboard production use.
- Required screen resolution and multi-monitor behavior.
- Audible alert requirements.
- Localization/language requirements.
- Final report and review interactions.
