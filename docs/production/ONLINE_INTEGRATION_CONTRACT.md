# Online Integration Contract

## Status

External signalling/acknowledgement integration remains `PENDING`. A same-PC
automatic folder intake based on a configured filename contract is now a
confirmed production requirement.

## Principle

Offline and online intake must produce the same validated acquisition-manifest contract. Reconstruction, inference, projection, database, and reporting must not know which connector supplied the run.

```text
Offline Folder Connector ---+
                            +--> Acquisition Manifest --> Common Pipeline
Future Online Connector ----+
```

## Confirmed Automatic Folder Intake

The production pipeline stores a portable naming contract, not a
machine-specific absolute folder:

```text
template: {cycle}_{position}.jpg
position width: 2
expected positions: 01 through 16
side: configured by pipeline
```

The station configuration separately maps the acquisition source to a local
approved folder. This prevents moving a pipeline bundle to another PC from
silently monitoring the wrong absolute path.

Run Mode requires no file selection. Once started, it reports:

```text
Waiting for acquisition
Receiving 1/16 ... 16/16
Verifying files are stable
Validating ordered acquisition
Processing
Completed / Rejected
```

The filename template must contain exactly one `{cycle}` token and one
`{position}` token. Position is parsed from the configured token, never from
filesystem sorting or timestamps. Unknown names, duplicate positions,
different cycle identities, incomplete sets, and files that continue changing
are not processed.

## External Information Required

Ask the acquisition-software team:

1. Does their C++ software run on the same PC or another PC?
2. Where are the 16 images saved?
3. How are filenames and numeric order defined?
4. How is a completely written acquisition signaled?
5. Can it atomically rename a folder or create `READY.json`?
6. Can it call a local REST endpoint?
7. What run ID, disc serial, side, product, and timestamp metadata are available?
8. What acknowledgement is required?
9. What result fields must be returned?
10. Can another acquisition arrive while processing is active?
11. What timeout/retry behavior is required?
12. What happens if either application is unavailable or restarts?
13. What is the maximum permitted response time?
14. Are stop/fault/emergency states controlled by their software, a PLC, or this application?

## Candidate Protocols

- Atomic folder plus `READY.json`.
- Local REST API.
- Named pipe.
- TCP socket.
- Message queue.
- PLC-mediated integration through the external C++ application.

The initial technical preference is atomic folder plus READY metadata because it is observable, recoverable, and easy to simulate, but the external contract decides.

## Connector Interface Requirements

Any connector must support:

- discover/receive signal;
- validate metadata;
- prove files are final;
- claim exactly once;
- acknowledge acceptance/rejection;
- expose external identity;
- report progress if required;
- report completion/failure;
- retry idempotently;
- recover after restart;
- quarantine malformed/partial acquisitions;
- simulate without production hardware.

## Safety Rules

- Never process a folder merely because the first file appeared.
- A complete naming match is discovery evidence, not proof that bytes are
  finished; every file must remain size/mtime stable for the configured
  interval and pass full decoding before claim.
- Never modify the external software's source files.
- Never claim the same external run twice.
- A duplicate signal returns the existing run/result identity.
- An incomplete acquisition receives a clear rejection/failure state.
- External absolute paths are validated against an approved root or copied through a controlled intake boundary.
- Connector loss does not corrupt an already claimed run.
- The online Start button enables listening/processing; it does not expose technical connector settings to operators.
