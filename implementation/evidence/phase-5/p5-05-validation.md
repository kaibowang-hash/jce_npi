# P5-05 Formal Publish Request Validation

Recorded: `2026-08-07T00:50:00Z`

Status:
`PASS — LEVEL 2 FORMAL PUBLISH REQUEST TASK GATE`

Requirement:
`FR-DS-013` (`TECHNICAL_VERIFIED_FOUNDATION`).

Final exact checkpoint:
`7624497acf19ca280d7331c41d4fc2eedb69e12e`

Complete ordinary CI:
[`31134844746`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31134844746)
(`PASS`, exact checkpoint)

Final unchanged controlled-Site Gate:
[`31135330539`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31135330539)
(`PASS`, exact checkpoint, all diagnostics closed)

## Delivered vertical slice

- Added an operation-specific, Project-scoped formal Item/MBOM publish-request
  aggregate from one exact released EBOM and one exact published requester
  policy. The browser cannot supply tenant, actor, lifecycle result, formal ERP
  identifier or ERP success.
- Added independent requester authority, authorization-before-resolution,
  actor-bound command idempotency, changed-payload conflict, canonical request
  hashing, optimistic input identity, atomic request/node/mapping/result/audit
  persistence and sealed replay.
- Added strict list, create and detail BFF/OpenAPI operations. Mock is the only
  enabled Phase 5 target; every node remains `validated` or an explicit failure
  state and cannot report `succeeded`, Item Code, BOM identity or target
  version.
- Added immutable per-node mapping/result truth, partial/manual-intervention
  representation, no-Outbox/no-network enforcement and an independent P5-05
  route-disable/recovery switch.
- Added the dense Project EBOM publish workspace with exact input/policy,
  request, node, mapping and result truth; one primary action; honest loading,
  empty, denied, read-only, validation, conflict, processing, retryable/final,
  partial and unavailable-source states.
- Added literal-English sources and direct Simplified/Traditional Chinese
  catalogs through the accepted Frappe v15 CSV and React `t()` chain.

No production or sandbox ERPNext endpoint, credential, service identity,
network adapter, worker, Outbox dispatch, retry/replay worker, webhook,
reconciliation mutation, formal Item/MBOM identifier or optimistic ERP success
was installed or inferred. Real execution and reconciliation remain Phase 8.

## Controlled-runtime convergence

The append-only candidate record preserves every serial failure and bounded
repair. Each cycle used an exact response-neutral stage/type/trace tuple,
ordinary CI before every Site boundary and only the uniquely proved root:

1. The requester list was stored as canonical JSON rather than a Python list
   in a Frappe non-table field.
2. The published policy timestamp was stored in the shared Frappe/MariaDB UTC
   database-text form rather than as a timezone-aware Python Datetime.
3. Receipt sealing compared the retained `created_at` instant through the
   shared UTC normalizer rather than comparing DB text to a reloaded Frappe
   Datetime object.

These were sequential latent representation boundaries. Earlier repairs were
effective: each later controlled run advanced beyond the repaired stage and
exposed the next previously unreachable boundary. No repair changed a
Requirement, public API, role/DocPerm, Schema, ownership, transaction order,
idempotency, audit or PASS criterion.

The first post-repair controlled run `31133548117` at `5dabc02` proved both the
P5 runtime and unchanged `65/65` visual matrix PASS. Its repository companion
failed only because GitHub's current npm advisory feed newly classified
transitive development dependency `js-yaml@4.3.0` under CVE-2026-59870. The
minimal follow-up `7624497` changed only the lock entry to compatible patched
`4.3.1`; local audit returned zero vulnerabilities and the complete ordinary
and final Gate passed. This security repair did not alter product behavior.

The earlier final-Gate setup failures in workflow `31115995065` occurred before
checkout during the official GitHub Actions major outage (`Failed to resolve
action download info` / `Service Unavailable`). They are retained as external
platform evidence and are not product or Gate-code failures.

## Level 2 and full-repository verification

### Local affected checks

| Boundary | Command/result |
|---|---|
| P5-05 controller/runtime and receipt-seal repair | focused publish-request checks — `47/47 PASS` |
| bounded changed-file regression | affected checks — `18/18 PASS` |
| Python/static integrity | complete tracked regression, compilation, V1.2 reconciliation, prototype approvals, P0 visual governance and `git diff --check` — PASS before the final Site boundary |
| lockfile security repair | exact three-line `js-yaml 4.3.0 -> 4.3.1` change; JSON/integrity check, `21/21` devcontainer tests and npm audit — `0 vulnerabilities` |

The local Mac has Node `24.2.0`/npm `11.3.0`, not the pinned
Node `24.18.0`/npm `11.16.0`. Exact-engine installation and the complete
install-script policy therefore remain CI evidence and were not bypassed.

### Exact-SHA ordinary CI

Run `31134844746` passed against exact SHA `7624497`:

- repository job `92731803737` passed complete `verify.sh`, tracked tests,
  frontend generation/type/lint/unit/coverage/build, zero-vulnerability audit,
  `298` non-visual E2E cases, current-tree and complete-history Gitleaks;
- fixed-Linux visual job `92731803668` passed the unchanged `65/65` matrix; and
- controlled job `92731804178` was correctly skipped for the ordinary
  pull-request event.

### Final unchanged controlled-Site Gate

Run `31135330539` retained exact SHA `7624497` and passed:

- repository job `92733288503`: `1007/1007` tracked Python tests,
  `705/705` frontend unit tests, build and brand checks, `3759` literal English
  sources with `100%` direct `zh`/`zh-TW` coverage, zero-vulnerability audits,
  `298/298` non-visual E2E cases and no current-tree/history secret leaks;
- fixed-Linux visual job `92733288492`: `65/65`, including all three P5-05
  English/Simplified Chinese/Traditional Chinese cases; and
- controlled job `92733288519`: pinned Bench/Frappe tools, fixed disposable
  Site/database guards, both App installations and two migrations, unchanged
  P5-01 through P5-04 runtime, synthetic published requester policy, released
  EBOM input, guest/empty/list/detail truth, Mock create, exact replay,
  changed-payload conflict, immutable request/node/mapping/result/audit truth,
  cross-process replay, no Outbox/network/formal target identity,
  route-disable/recovery and bounded volume cleanup.

Controlled artifact `8977753018` is
`p5-document-ebom-runtime-31135330539` (`363` bytes). GitHub records digest
`sha256:bccec9800be67c9194c18508d3627839db4f7e67d0ece154b2fbe566cdb45e60`.
Its extracted `result.txt` has SHA-256
`ce1e67fa1626b730be409281b5f0421bcea6817e7043364c19456f075491f17f`
and records `result=PASS`, exact head SHA `7624497`, run `31135330539`, fixed
disposable runtime marker, pinned Frappe commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1` and
`scope=p5-01-through-p5-05`.

Visual artifact `8977747657` has GitHub digest
`sha256:1078db219b03338bbcf7f2014a512e6ca26c5ce799f2a1eed03cc707314feb13`.
Secret-scan artifact `8977871452` has digest
`sha256:c92cca40bbdc7586d8f0808b88d09dd5463d01a2cf25d9583d7c094de22a30c8`.

The runner annotated that maintained `actions/*@v4` JavaScript actions were
forced from Node 20 to Node 24. All jobs passed; this is a hosted-runner
compatibility notice, not a P5-05 failure.

## Requirement, ownership, permission and security review

- `FR-DS-013` is technically verified for the approved Phase 5 foundation:
  one exact released EBOM produces an operation-specific controlled request
  with immutable per-node mapping/result truth and no fake ERP success.
- Actual creation/update of ERPNext Item and MBOM is not claimed. ERPNext
  retains formal identity, MBOM, routing, stock UOM and execution ownership;
  Phase 8 owns the real adapter, retry/replay and reconciliation.
- Authorization precedes protected resolution. Guest, external, unrelated
  Project/tenant and unbound actors fail closed without object-existence
  disclosure. Request permission is independent from review/release authority.
- There is no core patch, unrestricted `ignore_permissions`, direct SQL,
  cross-database access, raw browser CRUD, production secret/endpoint,
  destructive migration, accepted-path TODO/stub or fake success.
- Additive DocTypes and repeat migrations passed. After retained request
  history exists, rollback is a reviewed forward fix plus the independent
  P5-05 route switch; requests, nodes, mappings, results, audits and sealed
  receipts are not deleted or rewritten.

## UX, accessibility and i18n review

The exact fixed-Linux Gate passed:

- `p5-05-publish-request-en-1366x768-100`;
- `p5-05-publish-request-zh-1440x900-125`; and
- `p5-05-publish-request-zh-TW-1920x1080-150`.

The workspace retains the approved square, dense industrial shell, neutral
surfaces, one restrained teal primary and one primary action. Status is text
plus shape, the inspector retains exact request evidence, and the 125%/150%
cases preserve usable table/inspector boundaries. Keyboard/focus, labels,
non-hover paths, Axe WCAG A/AA and non-color-only state checks pass. Ordinary
Chinese copy is direct-catalog translated; retained English is limited to
allowed product/engineering terms, identifiers, synthetic business data and
units.

## Changed-files to affected-tests

| Change boundary | Affected evidence |
|---|---|
| publish policy/domain and seven additive DocTypes | domain/metadata/security tests and two controlled migrations |
| repository, authority, audit and idempotency | repository/controller/permission/runtime tests plus exact create/replay/conflict proof |
| BFF/OpenAPI/ownership | API/contract, CSRF, IDOR and authorization-before-resolution tests |
| Project publish-request workspace and catalogs | complete frontend unit/E2E, direct i18n audit and three governed visuals |
| controlled verifier and response-neutral diagnostics | verifier/controller tests, complete ordinary CI and final diagnostics-closed Site |
| receipt timestamp normalization | focused receipt/controller regression and two exact controlled PASS runs |
| `frontend/package-lock.json` security update | lock integrity, install, audit, complete repository/E2E/visual and final controlled Gate |

## Task conclusion and next task

`PASS — LEVEL 2 P5-05`.

`FR-DS-013` advances to `TECHNICAL_VERIFIED_FOUNDATION`; production ERPNext
execution remains an explicit Phase 8 hold and is not overclaimed.

The amended Phase 5 anchor still assigns `FR-PRN-001` and `FR-PRN-002` to the
generic controlled-print registry and immutable snapshot foundation. Therefore
Phase 5 remains `IN_PROGRESS`; the complete final CI above is reusable full-
repository readiness evidence, but it is not mislabelled as a terminal Phase
Gate while planned P0 work remains. Standing automatic-transition authority
activates `P5-06 — Controlled Frappe print registry and immutable snapshot
foundation`. Exact forms, signers and copy policy (`FR-PRN-003`) remain held by
`DR-REC-003/004` and are not invented.
