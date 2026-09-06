# P8-03 Checkpoint 2 — Project-first Item Command and Durable Outbox

Recorded: `2026-08-16`

Decision: `PASS — CHECKPOINT 2; CHECKPOINT 3 AUTHORIZED`

Final product checkpoint:
`6e11a86048983f87c9d54e0fc3e3544e7e9a05f0`

Primary implementation checkpoint:
`34fa2e5740860d0c1cc5eb4d16c48374cf95dfd3`

Ordinary pull-request CI: `31953799677`

## Scope delivered

- Added the fixed Project-first list, detail and create BFF routes. Session
  authentication, canonical route identities, CSRF for POST, internal
  `NPI API User`, tenant/Project membership and secondary containment are
  enforced on the server before Item request details are returned or changed.
- Added exact Phase 5 source resolution. The command reloads the immutable
  Mock publish request, published policy, released EBOM revision, lifecycle,
  release event and approval evidence under the Project lock and rejects any
  identity, version or hash drift.
- Added complete occurrence grouping for the selected exact engineering
  identity. Description, engineering UOM and attributes must agree across all
  occurrences; quantity, hierarchy, alternates and effectivity remain excluded
  MBOM facts. No arbitrary occurrence or cross-Project identity is chosen.
- Added server-owned execution-profile and current-mapping resolution. Missing,
  invalid, wrong-scope or unauthorized profiles fail closed; current mapping is
  integrity-checked under lock and stale expectations create no request or
  Outbox row. No profile, endpoint, credential or target mapping is installed.
- Added actor-bound command idempotency. An exact actor/key/payload replay
  returns the retained request without enqueueing again, including after the
  Project becomes terminal; the same actor/key with different content is an
  audited conflict and never overwrites the first command.
- Added one atomic request boundary. Request, optional version-1 Item Outbox,
  structural audit and immutable idempotency receipt are written in one
  controlled transaction. The API explicitly commits before responding and
  calls only the queue seam after commit; enqueue failure leaves the durable
  pending Outbox available for checkpoint-3 recovery.
- Mock creates only `validated_mock` with no Outbox, attempt, result, mapping,
  enqueue or network effect. An explicitly injected valid synthetic/Sandbox
  profile may create one queued Outbox message, but this checkpoint installs no
  resolver hook, worker or adapter and invokes no target.
- Added closed OpenAPI request/list/detail contracts, direct Simplified and
  Traditional Chinese problem translations and the regenerated Frappe-backed
  React catalog. No end-user workspace or visual behavior changed.

## Changed-files to affected-checks map

| Changed boundary | Affected evidence |
|---|---|
| `item_publish/frappe_repository.py` | exact Phase 5 release/source checks, complete grouping, profile/permission/current-mapping lock, replay/conflict, atomic row set, rollback and bounded list/detail tests |
| `item_publish_api.py` and BFF routes | authentication, CSRF, Project-first IDOR, exact request fields, `201`/`200` replay, commit-before-enqueue, commit failure, Mock no-enqueue and route/method closure tests |
| Item domain/problem and OpenAPI contracts | terminal non-Mock reconstruction, exact acknowledgement, closed create/list/detail fields, no caller target authority and response-shape tests |
| both Frappe translation CSVs and generated catalog | direct `zh`/`zh-TW` symmetry, generation check, type check and complete mixed-language audit |
| focused Phase 8 tests | Mock zero effect, synthetic one Outbox, replay, conflicts, missing/drifted source, stale mapping, missing/denied profile, partial-write rollback and no worker/adapter/network activation |

## Local Level 1 and task evidence

- Focused P8-03 domain/configuration/metadata/contract/API/repository matrix:
  `48/48 PASS`; API `10/10` and repository `11/11` are included.
- Full local repository Task Gate: `2,075/2,075 PASS`; six pre-existing
  untracked local-prerequisite tests explain the difference from the clean CI
  count. Development-container, prototype approval, P0 visual governance and
  V1.2 reconciliation verification also pass.
- Generated catalog check, direct i18n audit and TypeScript type check pass.
  The audit reports `7,879` literal English sources with `100%` direct
  `zh`/`zh-TW` coverage.
- Python compilation, JSON/YAML parsing, current-task verification,
  reconciliation, prohibited backend/network scans, staged and exact-commit
  Gitleaks and `git diff --check`: PASS.
- Task Diff Review confirms no worker module, adapter registry/call, profile
  hook installation, scheduler, target endpoint, credential, formal mapping,
  generic retry/replay/reconciliation or production traffic.

## Exact-SHA ordinary CI evidence

- Repository job `95181224022`: PASS; `2,069` tracked Python tests plus
  repository and V1.2 reconciliation verification.
- Frontend job `95181224027`: PASS; `60/60` files, `933/933` unit tests,
  `426/426` E2E, generation/type/lint/build/audit, `7,879` complete direct
  trilingual sources, zero vulnerabilities and coverage `80.36%` statements,
  `80.20%` branches, `83.00%` functions and `82.99%` lines.
- Secret job `95181224003`: PASS; `26` first-parent task commits and `530`
  complete branch commits contain no leak. Artifact `9265383694`, digest
  `sha256:295f6b7a0f296e28171e667a6b0a0a4e327c3e5ded01aa8318d5f1bf0b0508cc`.
- Visual job `95181224081`: PASS; unchanged `119/119` fixed-Linux matrix.
  Artifact `9265436848`, digest
  `sha256:8e0845d6b712169f3b72f1ed3ac106b85ea8589a9bcfb8a5bceb5b13417075a7`.
- Controlled preflight and cumulative runtime skip as expected because this
  checkpoint installs no worker, adapter, disposable fixture or target call.
- Initial diagnostic CI `31953679922` identified only the omitted generated
  React catalog after seven new translated backend messages. Repair checkpoint
  `6e11a86` regenerated the catalog without changing product behavior,
  thresholds, tests or visual baselines; the final exact-SHA CI above passes.

## Review and rollback

The Task Diff Review found no secondary lookup before Project authorization,
first-occurrence-wins grouping, Phase 5 history rewrite, caller-selected
tenant/actor/mode/method/target/success, MBOM leakage, Mock dispatch,
pre-commit acknowledgement, replay re-enqueue, optimistic target success,
default profile, target network access, secret persistence or production
fallback.

Before an adapter boundary exists, rollback disables the three Item routes and
enqueue seam, retains every committed request/idempotency/Outbox/audit row and
uses reviewed forward repair. It never deletes durable history, promotes a
legacy Outbox, rewrites Mock/queued truth to success, changes a formal Item
code, mutates the released Phase 5 source or contacts production ERPNext/JCE.

This is checkpoint 2 PASS. It is not P8-03 completion or Phase 8 Level 3.
