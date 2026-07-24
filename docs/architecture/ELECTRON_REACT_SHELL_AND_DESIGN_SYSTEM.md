# Electron/React Shell and Design System

## Status and Scope

Task 15 establishes the secure desktop boundary and the professional interface
foundation. It provides navigation, shared visual language, backend connection
state, and error handling without implementing commissioning forms, production
run commands, result visualization, or online integration.

The milestone was accepted by the user on 2026-07-24 after the two-mode shell
revision. Task 16 may now extend Configuration Mode without mixing technical
controls into Run Mode.

## Desktop Security Boundary

The Electron renderer remains a sandboxed web application:

- context isolation is enabled;
- Node integration is disabled;
- the renderer sandbox and web security are enabled;
- all permission requests and webview attachments are denied;
- navigation is restricted to the exact development origin or packaged file;
- new windows are denied and only valid HTTPS links may open externally;
- developer tools are disabled in a packaged build;
- one application instance owns the production window.

The preload exposes one frozen `productionInspection` object. It contains
platform/package identity and one backend request function. It does not expose
filesystem access, processes, Electron objects, IPC primitives, arbitrary
channels, or arbitrary URLs.

The main-process backend adapter:

- always targets `http://127.0.0.1:8000`;
- accepts only `GET` and `POST`;
- validates requests against explicit versioned API route patterns;
- rejects request bodies on `GET`;
- applies a 10-second timeout;
- returns structured, sanitized unavailable responses.

Development browser mode uses the same typed client through the explicit
loopback CORS boundary. Packaged mode automatically uses preload IPC, so the
backend does not need broad `file:` CORS access.

## Application Routes

Hash routing is used so the same route model works in Vite and packaged
`file:` loading:

| Route | Current Task 15 responsibility |
|---|---|
| `/run` | default operator shell, current run, latest cycle, safely locked action |
| `/run/history` | operator-facing Previous inspections inside Run Mode |
| `/configuration/setup` | separate protected commissioning workspace |
| `/configuration/system` | technical liveness/readiness and manual refresh |

Unknown paths and application startup always return to `/run`. Run Mode has no
technical left navigation. It contains production/station identity, backend
and pipeline status, current run, latest completed cycle, Previous
inspections, and a small Configuration entry.

Configuration Mode replaces the Run view completely. It owns a technical left
navigation and a persistent Return to Run Mode action. The two modes are not
presented as equal sections in one shared menu.

One saved inspection/history entry represents one complete acquisition cycle:
the current brake-disc contract uses 16 ordered source images, one
reconstructed disc, final deduplicated predictions, result, side, and durable
model/pipeline identity. Later configuration controls determine which evidence
layers operators may view.

Task 15 deliberately labels unfinished areas rather than displaying fake
working controls. Setup workflows belong to Task 16, Start/Stop behavior to
Task 17, and history/viewer behavior to Task 18.

## Typed Client and State

Frontend contracts mirror the Task 14 API for health, readiness, models,
pipelines, runs, and sequenced events. `InspectionApiClient` selects the
desktop bridge when available and otherwise uses loopback fetch.

Transport and API failures become stable `ApiClientError` values without
leaking raw network details. A shared backend-status provider:

- checks liveness and readiness separately;
- keeps liveness connected when production services are not configured;
- refreshes every 15 seconds;
- permits an explicit refresh;
- aborts stale requests during cleanup;
- supplies one consistent connection state to the shell and pages.

## Design System

The initial dark production theme uses semantic tokens for:

- background, surface, border, text, accent, warning, danger, and information;
- spacing through component layout;
- small, medium, and large radii;
- elevation and focus rings;
- reduced-motion behavior.

Reusable foundations include:

- typed line icons;
- semantic status badges with text and color;
- primary and secondary buttons;
- raised surfaces;
- consistent page headings;
- empty, readiness, diagnostic, and safety-information states.

Keyboard focus is visible. Navigation uses semantic links and active state,
status does not rely on color alone, disabled production actions explain why,
and layouts avoid horizontal overflow at supported desktop widths. Only the
Configuration left rail collapses for compact desktop widths. Run Mode remains
free of technical navigation at every size. A minimal small-screen fallback
keeps both shells renderable without defining final touchscreen requirements.

## Verification

Task 15 verification covers:

- frontend and Electron lint and strict TypeScript checks;
- React route, readiness, desktop transport, and stable error tests;
- Electron backend allow-list acceptance and rejection tests;
- frontend production build and Electron compilation;
- dependency audit with zero known vulnerabilities;
- the complete 148-test backend regression suite plus Python formatting,
  linting, typing, and dependency checks;
- Playwright navigation through all four routes at 1440x900;
- compact 1024x768 rendering;
- no horizontal overflow at either viewport;
- live loopback status and refresh;
- keyboard focus availability;
- zero browser console errors and zero uncaught page errors.

Playwright screenshots are stored only under ignored local `temp/` for review;
they are not source artifacts and must never be committed.
