# P9-01B Project-first Change Command/Query Checkpoint

Status: `IMPLEMENTED — EXACT-SHA ORDINARY CI PENDING`

## Accepted Gate

Governance exact SHA `07b869bcd88fa7406548e10edc42b07c6dadc8ed`
passes ordinary CI `33354760251`: secret `99374683091`, visual
`99374683231`, frontend `99374683273` and repository `99374683338` all pass.
Only the exact twenty paths in `implementation/CURRENT_TASK.json` are
authorized for this checkpoint.

## Implemented boundary

- Project-first list and detail queries.
- Version-locked create, revise, link-formal-observation and close commands.
- Closed request and response validation with exact UUID, hash, timestamp,
  collection and enum contracts.
- Internal NPI authority, Project containment, CSRF, request/trace IDs and
  actor-bound idempotency.
- Exact current global ID, revision number and revision hash predecessor.
- Ordered single transaction: command receipt, immutable revision, immutable
  event, current root, audit record and sealed receipt.
- Sealed replay with no new domain write; conflict, permission and validation
  failures remain explicit.
- Default-disabled fixed BFF routes and complete OpenAPI descriptions.

## Ownership and closeout rules

ERPNext remains owner of formal ECR identity, raw lifecycle state and
transaction-effective truth. Those values may enter only through the
privileged formal-observation command and cannot be supplied by ordinary
create, revise or close payloads. LaunchFlow remains owner of NPI impact,
affected versions, responsibilities, task/evidence links, disposition,
revalidation, cost and Gate consequences.

Closeout is fail-closed. It requires explicit immutable facts for affected
versions, ERP observation where required, old-version withdrawal, disposition,
revalidation and closure evidence. The server derives ready-to-close and closed
state from that evidence; the caller cannot force either state. The change
title is immutable after creation.

## Security and rollback

No permission bypass, direct SQL, network call, generic DocType writer,
background target, ERP write or production connection is added. Rollback keeps
the additive immutable records and disables the new routes through the existing
configuration boundary. Transaction failure rolls back the complete write
sequence; no optimistic success is returned.

## Verification

Focused API, repository, contract and pre-existing shared OpenAPI tests cover
six operations, closed shapes, Project containment, role/CSRF enforcement,
idempotency binding/replay, exact predecessor conflicts, ordered writes,
rollback, immutable title, formal-observation authority and no SQL/network/
permission-bypass regressions. Direct Simplified and Traditional Chinese
translations are complete and the generated frontend catalog is synchronized.

Final local evidence passes P9-01/current-task focused tests `50/50`, the full
repository suite `2760/2760`, current-task and V1.2 reconciliation scripts,
OpenAPI/YAML parsing, Python compilation, shell syntax, generated-catalog
freshness, i18n audit (`8664` governed English sources with `100%` zh/zh-TW)
and `git diff --check`.

P9-01C `INT-008`, every adapter/worker/event activation, production ERP
configuration and P9-01D UI are explicitly outside this checkpoint. This
checkpoint is not accepted until its implementation exact SHA passes ordinary
CI in repository, frontend, governed visual and secret lanes.
