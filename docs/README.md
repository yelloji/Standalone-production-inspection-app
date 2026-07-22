# Documentation Index

## Status

- Documentation foundation: `APPROVED`
- Application code started: No
- Database started: No
- Frontend started: No
- Focused documentation commit authorized: Yes

## Authority

These documents are the authoritative design reference for the standalone production application. The copied `brake-disc-production-transfer-*` folder is local historical/reference material and is not authoritative production architecture.

Requirements use three labels:

- `CONFIRMED CURRENT`: approved for the current milestone.
- `CONFIRMED FUTURE`: required later, but not permission to implement now.
- `PENDING`: requires user guidance, measurement, or external-team information.

When documents conflict, use this priority:

1. the newest explicit user decision;
2. an accepted architecture decision;
3. the current implementation task ledger;
4. supporting technical documents;
5. copied historical/reference material.

## Documents

### Product

- [Product Requirements](product/PRODUCT_REQUIREMENTS.md)

### Architecture

- [System Architecture](architecture/SYSTEM_ARCHITECTURE.md)
- [Architecture Decisions](decisions/ARCHITECTURE_DECISIONS.md)

### User Interface

- [User Modes and UI/UX](ui/USER_MODES_AND_UI_UX.md)

### Data and Configuration

- [Pipeline and Model Lifecycle](data/PIPELINE_AND_MODEL_LIFECYCLE.md)

### Production

- [Performance Architecture](production/PERFORMANCE_ARCHITECTURE.md)
- [Online Integration Contract](production/ONLINE_INTEGRATION_CONTRACT.md)

### Execution

- [Implementation Tasks](tasks/IMPLEMENTATION_TASKS.md)

## Documentation Rule

Before implementing a task:

1. confirm its requirement and acceptance criteria;
2. update affected design documents if the decision changed;
3. explain planned files and risks;
4. implement only that task;
5. verify it;
6. mark it `READY FOR USER REVIEW` and stop;
7. update status and commit only after explicit user approval.
