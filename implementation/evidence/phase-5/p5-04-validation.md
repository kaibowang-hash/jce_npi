# P5-04 EBOM Revision and Comparison Validation

Recorded: `2026-08-06T09:57:00Z`

Status:
`PASS — LEVEL 2 EBOM REVISION AND COMPARISON TASK GATE`

Requirements:

- `FR-DS-011` (`TECHNICAL_VERIFIED`); and
- `FR-DS-012` (`TECHNICAL_VERIFIED`).

Product checkpoint:
`2c0734a4201ac5ee4b53eae913ce01172634da3f`

Complete ordinary CI:
[`31089637022`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31089637022)
(`PASS`, exact product SHA)

Final unchanged controlled-Site Gate:
[`31090154694`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31090154694)
(`PASS`, exact product SHA, diagnostic activation closed)

## Delivered vertical slice

- Added an NPI-owned, Project-scoped EBOM aggregate with explicit published
  synthetic policy versions, caller-supplied stable line keys, validated
  parent hierarchy, canonical positive quantities, engineering UOM,
  alternates, effectivity and bounded attributes.
- Added immutable canonically hashed working revisions and lines with exact
  predecessor identity/hash, append-only draft/review/approved/released
  lifecycle history and independent exact actor authorities. Released history
  cannot be edited or deleted through a normal path.
- Added deterministic comparison of two explicit revisions of the same EBOM.
  Stable line identity produces typed added, removed, quantity, substitution
  and attribute differences in deterministic order.
- Added actor-bound command idempotency, changed-payload conflict detection,
  sealed replay, optimistic root/lifecycle versions, atomic rollback, audit
  history and an independent fail-closed P5-04 route switch.
- Added strict Project BFF/OpenAPI list, detail, create, revise, compare,
  submit-review, review and release operations. Browser clients do not use
  generic DocType CRUD and cannot supply tenant, actor, lifecycle result,
  formal Item Code, MBOM identity or ERP execution result.
- Added the dense Project EBOM workspace with honest loading, empty,
  no-permission, read-only, validation, conflict, processing, retryable/final
  failure, unavailable-source, lifecycle and exact comparison states.
- Added literal-English sources and direct Simplified/Traditional Chinese
  catalogs through the accepted Frappe v15 CSV and local React `t()` chain.

No production EBOM numbering, quantity/UOM conversion, alternate/effectivity
policy, approval authority, Item Code, stock UOM, formal MBOM/routing,
ERPNext endpoint, credential, external dispatch or optimistic ERP success was
installed or inferred.

## Controlled-runtime convergence

The append-only candidate record preserves every classified run. Recovery
used one response-neutral, closed diagnostic per independently opaque stage,
ordinary CI before every Site boundary and only a uniquely proved repair:

1. The synthetic policy fixture was corrected without opening the guarded
   policy API. The later published-policy transition was repaired only for an
   exact retained server-owned draft snapshot; caller tampering remains
   rejected.
2. Closed create-stage evidence then isolated, in order, a synthetic namespace
   fixture drift, missing policy hydration fields, a UUID-only lifecycle event
   boundary and the existing internal audit-append flag. Each final Gate
   advanced beyond the repaired stage.
3. The submit-review-only diagnostic finally emitted
   `P504_TRANSITION_LIFECYCLE_PROJECTION_SAVE / ValidationError` after receipt
   and lifecycle-event insertion. The controller had already canonicalized
   and exact-parent-validated the event ID as text but passed it to a
   UUID-only domain field. Checkpoint `2c0734a` converts only that validated
   non-null value during hydration and closes all diagnostic activation.

No recovery changed a Requirement, public API, DocPerm, Schema, ownership,
state transition, transaction order, idempotency, audit or PASS criterion.
The exact repair checkpoint passed ordinary CI `31089637022`, followed by the
single final unchanged controlled-Site Gate `31090154694`.

## Level 2 verification

### Local affected checks

| Boundary | Command/result |
|---|---|
| P5-04 controller and runtime-verifier boundary | focused tracked tests — `29/29 PASS` |
| complete EBOM domain, metadata, repository, API, contract, security and runtime modules | `69/69 PASS` |
| complete tracked Python regression | `959/959 PASS` |
| static integrity | Python compilation, V1.2 reconciliation, `282` unique trace rows, prototype approvals, P0 visual governance, YAML parse and `git diff --check` — PASS |

The affected frontend, i18n and browser checks were already sealed by the
exact P5-04 frontend checkpoint and were rerun by complete ordinary CI and the
final Gate.

### Exact-SHA complete ordinary CI

Run `31089637022` passed against exact SHA `2c0734a`:

- repository job `92577257354` passed complete `verify.sh`, compilation,
  tracked tests, frontend generation/type/lint/unit/coverage/build, audits,
  complete non-visual E2E, current-tree and complete branch-history Gitleaks;
- fixed-Linux visual job `92577257429` passed the governed matrix; and
- controlled job `92577258111` was correctly skipped for the ordinary
  pull-request event.

### Final unchanged controlled-Site Gate

Run `31090154694` retained exact SHA `2c0734a` with diagnostic activation
closed. Repository job `92578962756`, fixed-Linux visual job `92578962797`
and controlled job `92578962766` passed. The controlled job proved:

- exact pinned Bench/Frappe tools and disposable Site/database guards;
- installation and two migrations of both NPI Apps;
- unchanged P5-01, P5-02 and P5-03 runtime compatibility;
- published synthetic EBOM policy, object-hiding authorization, create,
  sealed replay/payload conflict, invalid-successor rollback, valid exact
  successor, deterministic comparison, review/reject/resubmit/approve/release,
  lifecycle/audit/replay truth, route disable/recovery and bounded cleanup;
  and
- PASS-only artifact generation.

Artifact `8963145655` is
`p5-document-ebom-runtime-31090154694` (`362` bytes). GitHub records digest
`sha256:04bccbcb01a1028075c1472cf02d7b4bffa41362de2804ebaf2892890ae898df`.
Its extracted `result.txt` has SHA-256
`4d84b4992ea8264ec1b12599ce7c7ae508f98b41925de2f32b07ccf3adc2d7a7`
and records `result=PASS`, exact head SHA `2c0734a`, run `31090154694`, fixed
disposable runtime marker, pinned Frappe commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1` and
`scope=p5-01-through-p5-04`.

The GitHub runner annotated that maintained `actions/*@v4` JavaScript actions
were forced from Node 20 to Node 24. All jobs passed; this is a hosted-runner
compatibility notice, not a P5-04 Gate failure.

## Requirement, domain, permission and security review

- `FR-DS-011` is satisfied for the approved Phase 5 technical scope:
  immutable NPI-owned EBOM working revisions preserve exact hierarchy,
  quantity, engineering UOM, alternate/effectivity and lifecycle truth.
- `FR-DS-012` is satisfied for the approved Phase 5 technical scope: two
  explicit immutable revisions produce stable, typed, deterministic change
  evidence suitable for review and P5-05 request preparation.
- Formal Item fields, Item Code, stock UOM, MBOM, routing, manufacturing
  transactions and ERP mappings remain ERPNext-owned. EBOM and MBOM are not
  conflated and no dual-master field was introduced.
- Authorization precedes protected resolution. Guest, external, unrelated
  Project/tenant and unbound actors fail closed without object-existence
  disclosure. Create, revise, review and release remain independent server
  decisions.
- There is no core patch, unrestricted `ignore_permissions`, direct SQL,
  cross-database access, raw browser CRUD, production secret/endpoint,
  destructive migration, TODO/stub or fake success.
- Additive DocTypes and repeat migrations passed. After retained EBOM history
  exists, rollback is a reviewed forward fix plus the independent P5-04 route
  switch; revisions, lines, lifecycle events, audits and receipts are never
  deleted or rewritten.

## UX, accessibility and i18n review

The exact fixed-Linux Gate passed the P5-04 English/Simplified Chinese/
Traditional Chinese evidence:

- `p5-04-ebom-workspace-en-1366x768-100`;
- `p5-04-ebom-workspace-zh-1440x900-125`; and
- `p5-04-ebom-workspace-zh-TW-1920x1080-150`.

Original-resolution review remains sealed in the frontend checkpoint. Neutral
surfaces dominate, industrial teal is the single main accent, panels and
controls are square/flat and dense, status uses text plus shape, and the
stable toolbar/list/revision/line/inspector hierarchy contains no card wall,
gradient, glass or Desk-form treatment. The 125% and 150% cases preserve the
engineering context and scrollable table boundary.

All user-visible sources use literal English and direct catalog entries.
Ordinary Chinese copy is translated; retained English is limited to allowed
product/engineering terms, identifiers, synthetic business data and units.
Keyboard/focus, non-hover paths, dirty-leave confirmation, labels, Axe WCAG
A/AA and non-color-only state checks passed.

## Changed-files to affected-tests

| Change boundary | Affected evidence |
|---|---|
| EBOM policy/domain and additive DocTypes | domain, metadata, Frappe and delete-guard tests; two controlled migrations |
| persistence, lifecycle, audit and idempotency | repository/controller/security/runtime tests; exact controlled create/review/release/replay |
| BFF/OpenAPI/ownership | API/contract, CSRF, IDOR and authorization-before-resolution tests |
| exact comparison | domain/repository/API tests plus browser comparison state |
| Project EBOM workspace and data source | affected unit suite, complete E2E and three exact trilingual visual cases |
| catalogs | extraction, direct coverage, placeholders, terminology and mixed-language scan |
| response-neutral diagnostics and fixture repairs | closed-stage verifier/controller tests, complete ordinary CI and final diagnostic-closed Site |

## Task conclusion and next task

`PASS — LEVEL 2 P5-04`.

`FR-DS-011` and `FR-DS-012` advance to `TECHNICAL_VERIFIED`. Production EBOM
numbering, conversion, approval and ERPNext manufacturing facts remain
explicit Class-B/scoped holds and are not overclaimed.

Phase 5 remains `IN_PROGRESS`. Standing automatic-transition authority
activates only `P5-05 — Formal publish request stub and contract` at its
Requirement/domain/integration audit for `FR-DS-013`. Real ERPNext execution,
retry/replay/reconciliation and production connectivity remain Phase 8 and
inactive.
