# P5-01 Frontend and Runtime-Ready Checkpoint

Recorded: `2026-07-30T15:09:42Z`

Starting synchronized checkpoint:
`9198dc9c54d314c9927ff5aa68ce17253f6f4afe`

Task:
`P5-01 — Document and design revision`

Requirements:

- `FR-DS-001`
- `FR-DS-003`
- `FR-DS-004`
- `FR-DS-007`
- `FR-DS-008`
- `FR-DS-009`
- `FR-DS-014`

Result:

`IN_PROGRESS CHECKPOINT — FRONTEND/BROWSER/STATIC RUNTIME PASS; CONTROLLED
FRAPPE SITE PROOF PENDING`

This is not the P5-01 Level 2 Task Gate, does not mark any requirement
complete and does not activate P5-02.

## Delivered vertical slice

- Added one strict browser data source for the retained Project-scoped
  document list, detail, create, lease, revision, capability and binary
  content contracts. Closed response parsing rejects additive or malformed
  success data.
- Added a dense Project Documents workspace showing the exact document,
  policy, immutable revision, File Revision/hash/scan, typed relationship,
  lock history and external-provider truth.
- Added create, checkout, check-in, administrative recovery and multipart
  revision interactions over the existing BFF. The multipart client does not
  claim browser-owned MIME, size, hash, privacy, scan, release, actor, tenant,
  File identity or URL truth.
- Added reauthorized URL-free native preview/download. A binary response is
  accepted only with exact private/no-store, sandbox CSP, no-referrer,
  nosniff, content-disposition, length and MIME headers; the browser receives
  a transient Blob and no stable private URL.
- Replaced the prototype route-dirty assumption with registered workspace
  dirty state shared by App navigation, Project tabs, browser history and
  `beforeunload`. Cancel preserves input and restores focus.
- Covered normal, empty, loading, no-policy, read-only, unavailable,
  malformed response, conflict, processing, retryable/final error and
  provider-unavailable truth without optimistic success.
- Added only literal-English sources plus direct `zh` and `zh-TW`
  translations. `PDM` remains the retained technical abbreviation; ordinary
  interface language is fully translated.
- Added a fail-closed controlled-Site verifier for the exact nine retained
  DocTypes, two additive/idempotent migrations, disposable synthetic
  policy/Project/document identities, exact CSRF/idempotency/replay,
  immutable revision/private File Revision, live pending-to-clean scanner
  observation, binary integrity, locks, typed relationships, audit traces,
  Guest/IDOR denial and route-disable recovery.

No production policy, role mapping, scanner/provider, external connector,
CAD/PDM, sharing, review/release, baseline, EBOM, ERPNext connection,
dependency or schema was added.

## Requirement → code → test → evidence

| Requirement | Code | Tests and evidence |
|---|---|---|
| `FR-DS-001` | `frontend/src/api/document-data-source.ts`; `frontend/src/pages/project-document-workspace.tsx` | strict data-source units; live workspace browser normal/empty/read-only/error states; three-language visuals |
| `FR-DS-003` | retained document domain/repository plus live revision/file workspace | retained `63/63`; document data-source and workspace units; controlled-Site verifier ready |
| `FR-DS-004` | retained relationships plus typed relationship UI | retained backend/contract checks; browser exact relationship truth; controlled-Site typed query |
| `FR-DS-007` | registered dirty state in `workspace-navigation.ts`, `app.tsx` and Project tabs | App/navigation units; real App dirty-guard browser case |
| `FR-DS-008` | retained lock commands plus workspace checkout/check-in/recovery | retained repository/API checks; workspace units; controlled-Site lock/audit lane ready |
| `FR-DS-009` | retained URL-free capabilities plus strict Blob response path | HTTP/data-source units; native-preview browser case; controlled-Site binary integrity lane ready |
| `FR-DS-014` | explicit unavailable external/CAD/PDM capability presentation | workspace units and trilingual browser truth; no connector activation |

## Changed files → affected tests

| Changed boundary | Affected verification |
|---|---|
| strict HTTP/FormData/Blob handling | `api-and-telemetry.test.ts`; `document-data-source.test.ts`; complete frontend unit coverage |
| document data source and workspace | `document-data-source.test.ts`; `project-document-workspace.test.tsx`; Project workspace units; P5-01 browser suite |
| App/Project dirty navigation | shell/page/workspace units; real App dirty-guard browser case |
| translations/generated catalog/styles | generated check; ESLint/Prettier/Stylelint/boundary/UI/i18n; build; three exact visual cases |
| controlled runtime shell/verifier | `test_phase5_document_runtime_verifier`; retained Phase 4 runtime safety/verifier suites; R1 runtime contract suites |

## Passing evidence

- P5-01 retained backend/domain/DocType/repository/API/contract:
  `68/68` after adding the five verifier contract tests.
- Shared runtime safety and retained Phase 4/R1 verifier regression:
  `85/85`.
- Affected frontend unit group:
  `124/124`.
- Complete frontend unit coverage:
  `658/658` in `32/32` files.
- Coverage:
  statements `83.23%`, branches `81.43%`, functions `86.46%`, lines
  `85.25%`.
- Generated artifacts, TypeScript, affected ESLint, Prettier, Stylelint,
  module boundaries and industrial UI static audit:
  `PASS`.
- Frappe-compatible i18n:
  `2,860` literal-English sources with direct `100%` `zh` and `100%`
  `zh-TW` coverage.
- Production frontend build and display-brand guard:
  `PASS`.
- P5-01 non-visual browser:
  `6/6`.
- P5-01 exact zero-tolerance visual comparison:
  `3/3` for English `1366×768@100%`, Simplified Chinese
  `1440×900@125%` and Traditional Chinese `1920×1080@150%`.
- Original-resolution industrial/accessibility/mixed-language/overflow
  inspection:
  `PASS`.
- `git diff --check`:
  `PASS`.
- The preceding controller-only checkpoint passed CI `#75`, run
  `30550637406`.

## Pending controlled-Site proof

The required command is:

```text
bash scripts/verify-frappe-runtime.sh --document-only
```

It failed closed before migration or fixture writes because the fixed
physical repository Bench does not exist. The repository preflight then
confirmed that this host has no Docker CLI, Docker daemon or Compose v2.
No production Site or external integration was contacted.

The verifier and shell contract are tested, but static proof cannot replace
the required real Site result. Before P5-01 can pass:

1. restore the repository's fixed disposable runtime without deleting or
   resetting retained volumes;
2. run the document-only command, including two migrations, fresh execution,
   route-disable/recovery, second-process exact replay and cleanup;
3. rerun the affected checks if runtime repair changes source;
4. finish the P5-01 Task Diff/domain/permission/security/UX/i18n review; and
5. only then mark the seven requirements verified and activate P5-02.

The unavailable local runtime is a scoped environment gap, not an
`AUTOPILOT_CONTROLLER.md` Hard Blocker. The Goal remains active and the task
remains fail closed at P5-01.

## Rollback and recovery

Before retained P5-01 business history exists, revert the bounded P5-01
frontend/runtime-ready checkpoint. Once controlled document history exists,
disable only the tested P5 document route switch, preserve document, File
Revision, lock, audit and idempotency history, and deploy a reviewed forward
fix. Never delete or rewrite retained revisions or audit evidence.
