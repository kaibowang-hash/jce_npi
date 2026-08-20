# P8-03 Checkpoint 4 — Item Execution Inspector and Guarded Request

Recorded: `2026-08-20`

Decision: `CHECKPOINT 4 PRODUCT READY; ORDINARY CI PENDING`

Product commit: the exact SHA containing this evidence is reported with the
handoff after commit. This checkpoint does not advance the controller or enter
Level 3.

## 1. Scope delivered

This checkpoint adds only the dense, trilingual EBOM Item execution inspector
and its one guarded primary request action:

- the exact-source list now carries a server-parsed `mappingExpectation` for
  the selected Phase 5 request/node; the browser displays and submits that
  value and never guesses `expectedMappingVersion`;
- the OpenAPI list/detail contracts require the server expectation and bounded
  immutable attempts/result history;
- the repository re-resolves the exact released source and current mapping for
  the list preview, retains the existing bounded 100-attempt read, and fails
  closed on invalid persisted attempt/result bindings;
- mapping-conflict truth remains separate: the request is
  `mapping_conflict`, the persisted observed result is `succeeded` with
  `authoritative_sandbox` and authenticated response truth, and the current
  mapping head remains the prior version;
- Mock has no Outbox, attempt or result; queued/processing has no sealed
  result; synthetic proof remains non-authoritative; and formal Item identity
  is rendered only from the current authoritative mapping;
- attempt states and fault kinds use a closed display mapper with English
  literals and direct Simplified/Traditional Chinese translations. No raw
  wire enum is rendered as user copy; and
- the request action remains server-profile/permission/acknowledgement guarded,
  with no retry/reconcile control, target authority, target fields, production
  endpoint, credential or ERPNext/JCE contact.

## 2. Changed-files to affected-checks map

| Changed boundary | Affected evidence |
|---|---|
| `frappe_repository.py`, OpenAPI and repository/API tests | server mapping expectation, bounded detail history, persisted binding validation, request/result conflict semantics, Project/source containment |
| `item-publish-data-source.ts`, workspace prop drilling and inspector | exact-source response validation, no browser default mapping version, permissions, Mock/queued/processing/failed/uncertain/synthetic/authoritative states, closed display labels |
| item fixture, frontend unit/E2E tests and three Linux snapshots | mapping-conflict request/result distinction, formal-code authority, expected-version submission, closed attempt/fault copy, non-visual and fixed-Linux visual coverage |
| `zh.csv`, `zh-TW.csv`, generated catalog | complete direct trilingual source coverage and no mixed-language user copy |

## 3. Local Level 1 evidence

- `python3 -m unittest discover -s tests -p 'test_phase8_item_publish_*.py'`:
  `75/75 PASS`.
- Level 1 domain/configuration/metadata/contract matrix:
  `27/27 PASS`.
- `python3 -m unittest tests.test_phase8_item_publish_api
  tests.test_phase8_item_publish_worker_repository
  tests.test_phase8_item_publish_repository`: PASS.
- `npx vitest run tests/unit/item-publish-data-source.test.ts
  tests/unit/project-ebom-publish-workspace.test.tsx`: `28/28 PASS`.
- frontend TypeScript typecheck, targeted ESLint, Prettier and Stylelint:
  PASS.
- `npm run generate:check` and `npm run lint:i18n`: PASS; i18n audit reports
  `7,950` literal English sources with `100%` direct `zh`/`zh-TW` coverage.
- `python3 scripts/verify_current_task.py`,
  `python3 scripts/verify_v1_2_reconciliation.py`, runtime-verifier unit tests,
  shell syntax and `git diff --check`: PASS.
- The exact `bash scripts/verify.sh` Level 2 command stopped before product
  checks because this managed host has Node `v24.2.0`/npm `11.3.0` while the
  repository pins Node `v24.18.0`/npm `11.16.0`; the repository-only variant
  also cannot resolve its required `python` executable (only `python3` is
  present). Equivalent Python 3 checks and the affected frontend checks above
  passed.
- The single required impeccable detector run reported one pre-existing
  `tooling-acceptance__header` side-tab accent warning outside this C4 UI
  change; no C4 selector required adjustment.

## 4. Visual and environment evidence

The three fixed Linux P8-03 snapshots were manually inspected with
`view_image` and are the only P8-03 snapshot files in scope:

- `p8-03-item-synthetic-en-1366x768-100-linux.png`
- `p8-03-item-uncertain-zh-1440x900-125-linux.png`
- `p8-03-item-authoritative-zh-TW-1920x1080-150-linux.png`

No Darwin snapshot is staged. Local Playwright could not start its Vite server
because the managed sandbox denied listening on `127.0.0.1:4173`; the exact
non-visual and three visual cases remain required in ordinary CI. Local
repository verification also reached the existing devcontainer registry check
but the environment has no DNS access to `mcr.microsoft.com`; this is recorded
as an environment limitation, not a product or contract bypass.
The managed host has no local `gitleaks` binary; the ordinary CI `secret_scan`
lane remains the authoritative secret-scan evidence.

## 5. Review, rollback and transition

Task Diff Review confirms the browser owns no target authority, target fields,
formal success, mapping version default, retry/reconcile operation or target
network. The implementation retains exact source/profile/mapping hashes and
server permissions, and keeps result state distinct from request conflict
state.

Before any adapter boundary, rollback disables the Item route/action while
retaining request, idempotency, Outbox and audit history. After a boundary,
retained attempts/results/mapping observations are never deleted, blindly
redispatched or rewritten to success. No production ERPNext/JCE traffic is
authorized.

This evidence closes only P8-03 checkpoint 4 after exact-SHA ordinary CI PASS.
It does not perform the final Level 3 gate, controller transition or P8-04
activation.
