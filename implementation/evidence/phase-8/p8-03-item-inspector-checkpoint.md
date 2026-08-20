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

## 6. C4 CI repair evidence (2026-08-20)

The repair was opened from PR #1 head
`1bd638c4c6a50182db3abae52bd477ee7d8ee4bd`, ordinary run `32351005738`.
The run had repository job `96369938498` successful; frontend job
`96369938694`, visual job `96369938724` and secret-scan job `96369938795`
failed; controlled jobs `96373363423` and `96373363833` were skipped as
expected. Frontend failure analysis was kept separate from visual analysis:
the frontend lane had exactly the three legacy P5-05 `renders exact Mock and
node truth` failures, while the six visual failures were the three legacy
P5-05 cases plus the three P8-03 cases.

The visual always-upload artifact was `r1-06-linux-visual-evidence`, artifact
`9399977792`, digest
`sha256:1e48b03cc5b6bcb9ad44cbc2168db6e8ea6397b5d76f5c50a03669abf9b4409a`.
The connector supplied a signed download URI, but this managed environment
could not resolve its host, so the zip SHA256 and actual/diff image byte
inspection could not be completed locally. The three old P5-05 expected
baselines were inspected and remain immutable. The three new P8-03 expected
baselines were inspected; no new baseline is accepted until CI actual bytes
are available and the six affected visual cases pass their structural checks.

Root cause and repair: the C4 inspector was mounted as soon as the existing
P5 detail loaded, and `itemPublishDataSource` demoted the P5 toolbar primary
even before an Item node was selected. The Item identifier now provides a
keyboard-accessible, visually neutral activation control. The inspector is
mounted only after that explicit activation and starts from the activated
immutable node; primary-action selection is based on the active inspector or
form, not merely data-source injection. This preserves the P5-05 baseline
surface while keeping the P8-03 inspector path explicit and single-primary.

The history secret scan reported one finding only:
`bfa9c9bb4fa70d0c66938b940b286c7f9bbb3d47:frontend/tests/unit/item-publish-data-source.test.ts:generic-api-key:26`.
The current-tree scan was clean; the finding is a synthetic fixture value,
not a credential, and the literal shape has already been removed from the
current tree. The exact fingerprint is the only new ignore entry. The
verifier and its tests accept that exact commit/path/rule/line tuple and
reject altered commit, path, rule or line values; no path, regex, rule or
history-scope allowlist was added.

Repair scope, risk and rollback: `.gitleaksignore`,
`scripts/verify_devcontainer.py`, `tests/test_devcontainer_verifier.py`,
`implementation/CURRENT_TASK.json`, this evidence file, the C4 workspace,
its P8-03 E2E test and the focused workspace unit test. The security verifier
paths were added to `CURRENT_TASK.allowed_paths` only after the exact CI
finding and current-tree scan established the C4 repair scope. Product risk
is limited to explicit Item-inspector activation and legacy P5 surface
restoration; rollback restores the prior C4 workspace/test pair and removes
the exact fingerprint entry while retaining all request/audit evidence.

Changed-files to affected-tests map:

| Changed boundary | Affected checks |
|---|---|
| C4 workspace and P8-03 E2E/unit tests | TypeScript, focused workspace unit tests, P8-03 non-visual/visual E2E, P5-05 regression visual and primary-action/a11y checks |
| Exact gitleaks fingerprint and verifier tests | devcontainer verifier unit tests, current-tree/history gitleaks lanes, exact positive/negative fingerprint validation |
| `CURRENT_TASK.json` and this evidence | current-task verifier, diff check and task evidence review |
