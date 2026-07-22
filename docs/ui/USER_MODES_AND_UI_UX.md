# User Modes and UI/UX

## Design Objective

Provide a premium, calm production interface for operators and a powerful protected commissioning interface for technical users. Complexity must exist where required without being exposed during routine online production.

## Application Navigation

```text
Production Run
Setup & Validation
Inspection History
System Status
```

Access is role-aware. An operator primarily uses Production Run. Technical/admin users may access Setup & Validation.

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

## Inspection History

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

- stable left navigation;
- top production/station status bar;
- central task workspace;
- non-blocking notification/alert area;
- persistent identity of active pipeline/model;
- clear distinction between production and technical mode.

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
