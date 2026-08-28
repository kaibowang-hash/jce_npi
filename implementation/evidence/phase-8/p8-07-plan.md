# P8-07 Plan — Operations, DLQ, Replay and Reconciliation

Status: **AUDIT PASS — CHECKPOINT 1 AWAITS EXACT-SHA ORDINARY CI**

Audit date: 2026-08-28

Audit base: `6a82568329e2ec46eae02df76a9d697e26cdf61e`

Predecessor product checkpoint:
`547421a059911df6aeb90bbbf06e837f77a3e5e0`

Requirements: `FR-RP-009`, `UX-016`, `NFR-INT-001`

Product-code authorization: **false until this audit-plan transition itself
passes exact-SHA ordinary CI**. After that Gate, only checkpoint 1 is
authorized. Production ERPNext/JCE contact remains prohibited throughout.

## 1. Audit conclusion

P8-02 through P8-05 already retain durable, operation-specific integration
truth, but they deliberately expose no shared operator job center and no
manual retry/reconciliation authority:

- P8-02 owns signed inbound event identity, payload/source hashes, Inbox
  state, bounded claim recovery, Project result and audit. It has no generic
  replay route.
- P8-03 Item publish owns one immutable source-bound request, Outbox, attempts,
  terminal result and mapping observation/head. Its fault policy never grants
  redispatch authority; an after-boundary timeout is uncertain.
- P8-04 MBOM publish adds exact node truth and per-node results while retaining
  the same no-redispatch rule and submitted-BOM hold.
- P8-05 Tool Asset create/update retains request, Outbox, attempts, aggregate
  and field results and mapping truth. Partial and uncertain outcomes cannot
  advance the formal mapping.
- P8-06 is an NPI-local immutable link to observed quality truth. It is not a
  target execution operation and is excluded from replay/DLQ mutation.

The existing `/execution` page is a prototype backed by in-memory fixtures.
It does not persist audit and cannot be promoted as operational truth.

P8-07 therefore adds one Project-scoped read model over fixed existing
operation kinds, plus operation-specific replay and reconciliation commands.
It does not create a caller-selected operation/target/payload writer. A DLQ is
a truthful classification of existing terminal rows, not a second mutable
copy of business truth.

## 2. Closed operation inventory

| Operation kind | Current durable source | Replay boundary | Reconciliation boundary |
|---|---|---|---|
| `receive_project_submission` | P8-02 Inbox Message | only exact `failed_retryable` event identity; original payload/hash retained | compare exact source/event/Project result; never fabricate Project creation |
| `publish_item` | P8-03 request/Outbox/attempt/result | only exact `failed_retryable` before an uncertain target boundary, same request and target idempotency | exact request/latest attempt/result/mapping comparison |
| `publish_mbom` | P8-04 request/nodes/Outbox/attempt/result | only exact `failed_retryable` with no uncertain node/boundary, same request and idempotency | exact aggregate plus node results and mapping comparison |
| `create_tool_asset` | P8-05 request/Outbox/attempt/result | only exact `failed_retryable` with no partial/uncertain target truth | exact request/attempt/field-result/mapping comparison |
| `update_tool_asset` | P8-05 request/Outbox/attempt/result | same closed rule as create, with exact current mapping/version expectation | exact request/attempt/field-result/mapping comparison |

No other operation kind can be supplied by a browser or added through data.
P8-06 formal-quality links may be displayed as related read-only evidence but
are not replay or reconciliation targets in this task.

## 3. Truth and ownership

| Truth | Owner | P8-07 treatment |
|---|---|---|
| inbound source event/payload | source system plus P8-02 immutable receipt | reference exact identity/hash; never edit payload |
| outbound request/source snapshot | owning P8-03/04/05 domain | read only; replay reuses it exactly |
| Outbox delivery state | owning integration worker | operation-specific CAS only |
| attempt/transport result | owning integration worker | append-only attempt/result history |
| formal Item/BOM/Asset/quality truth | ERPNext | observed result/projection only; never operator asserted |
| replay request and outcome | NPI One P8-07 | actor-bound immutable action receipt |
| reconciliation request | NPI One P8-07 | immutable operator intent, not target truth |
| reconciliation observation | trusted operation-specific adapter/service | append-only evidence with source/hash; human input cannot confirm success |
| job-center projection | NPI One P8-07 | derived permission-safe view, never a second owner |

## 4. State and DLQ classification

The shared view normalizes presentation only. Original state codes remain
available and authoritative in their owning operation.

| Shared class | Meaning | Operator action |
|---|---|---|
| `queued` | durable work not yet claimed | observe only |
| `processing` | current bounded lease/attempt | observe only |
| `succeeded` | authoritative owning result says success | no replay |
| `failed_retryable` | owning fault decision says retryable and no uncertainty boundary exists | operation-specific replay may be requested |
| `failed_final` | correction/new owning command required | no replay |
| `uncertain` | target boundary may have been crossed or response truth is incomplete | reconciliation only; redispatch prohibited |
| `partial` | mixed authoritative field/node outcomes | reconciliation/correction only; no generic replay |
| `conflict` | source, mapping, target version or identity conflict | correction/new owning command only |
| `quarantined` | inbound authenticity/identity policy prevents processing | security review; no replay |
| `unavailable` | profile, adapter, permission-safe object or evidence unavailable | no inferred success |

`failed_retryable`, `failed_final`, `uncertain`, `partial`, `conflict` and
`quarantined` form the logical DLQ worklist. Classification never moves or
duplicates the underlying row.

## 5. Replay authority

Replay is a new, append-only operator action over one exact existing source.
It must enforce all of the following server-side before any state transition:

1. authenticate the session actor and reject Guest/Administrator fallback;
2. authorize the exact Project before resolving secondary identifiers;
3. resolve a fixed operation-specific capability and exact source containment;
4. lock the current request/Inbox, latest attempt/result/mapping and Outbox;
5. require the owning state to be replayable and explicitly non-uncertain;
6. reuse the original immutable payload/source hash and target idempotency;
7. append an actor/trace/idempotency-bound action receipt and audit;
8. perform only the owning worker's reviewed CAS transition; and
9. enqueue after commit, with duplicate operator idempotency returning the
   sealed original response.

No replay command accepts a payload, target endpoint/method, target ID,
desired status, retry policy or formal result. `failed_final`, `partial`,
`uncertain`, mapping conflict and after-boundary timeout always fail closed.

## 6. Reconciliation authority

An operator may request reconciliation for one exact operation/request/
attempt. This records intent only. The request cannot assert target success,
formal identity or a replacement business value.

A trusted operation-specific reconciler may later append one closed
observation: `confirmed_succeeded`, `confirmed_failed`, `still_uncertain` or
`target_unavailable`, together with exact source/attempt/evidence hashes,
observed time, adapter/profile identity and trace. Any forward state or mapping
change remains in the owning P8-03/04/05 repository and requires its existing
authenticated target-result/CAS rules. Without a configured Sandbox adapter,
the truthful result is unavailable; Mock and synthetic proof never establish
formal ERP success.

## 7. API boundary

Read routes are Project-first and use fixed filters only:

- list Project operations with closed state/operation/time cursors;
- read one operation detail with immutable attempt/result/action history; and
- list the Project logical DLQ projection.

Mutation routes are operation-specific. The browser never sends an operation
code as authority:

- replay inbound Project submission;
- replay Item publish;
- replay MBOM publish;
- replay Tool Asset create;
- replay Tool Asset update;
- request reconciliation for each of those same fixed operations.

Every command requires CSRF, trace ID, exact Project, action idempotency key and
expected current state/version. Missing, foreign and ambiguous secondary IDs
return the same permission-safe not-found result. Response bodies contain no
raw inbound payload, target request/response body, credential or secret.

## 8. Permission matrix

| Boundary | Required authority | Failure behavior |
|---|---|---|
| list/detail/DLQ | authenticated internal actor plus Project `VIEW` | permission-safe not found/empty; no tenant-wide fallback |
| inbound replay | existing exact inbound Project processing authority plus mutable Project containment | forbidden/conflict before write |
| Item replay/reconcile | existing Item publish capability for exact Project/source | forbidden/conflict before write |
| MBOM replay/reconcile | existing MBOM publish capability for exact Project/source | forbidden/conflict before write |
| Tool Asset replay/reconcile | existing create/update capability matching original operation | forbidden/conflict before write |
| trusted reconciliation observation | server-selected operation adapter/profile and exact request/attempt | unavailable/fail closed; no human success field |

Direct DocType read/write is not an operator API. Support DocTypes deny delete,
remain hidden from normal product navigation and use narrow request-local
capabilities rather than unrestricted permission bypass.

## 9. Checkpoints

### Checkpoint 1 — pure domain, contracts and guarded metadata

After this plan's exact-SHA ordinary CI passes, add only:

- closed operation/action/state/fault/replay/reconciliation domain values;
- pure classifiers that preserve every owning raw state;
- additive versioned OpenAPI/event/ownership components with no active route;
- guarded zero-row action-receipt and reconciliation-observation metadata;
- direct EN/zh/zh-TW metadata translations and focused tests.

No API route, repository writer, existing state transition, queue enqueue,
adapter call, target network, UI behavior or persisted row is authorized.

### Checkpoint 2 — Project-scoped read model and operation-specific commands

Only after checkpoint 1 exact-SHA ordinary CI passes:

- add the Project-first list/detail/DLQ repository and BFF routes;
- add fixed replay and reconciliation-request commands;
- integrate each command with the existing owning repository/worker using
  exact locks, action idempotency, action receipt and audit;
- keep reconciliation observation writes behind an operation-specific trusted
  adapter capability; and
- prove IDOR denial, rollback, concurrency, replay, uncertainty and no-leak
  behavior in repository/API tests.

### Checkpoint 3 — industrial trilingual job center

Only after checkpoint 2 exact-SHA ordinary CI passes, replace the in-memory
`/execution` prototype with the live Project-scoped data source and dense
industrial worklist/detail inspector. It must cover loading, empty, no
permission, read-only, queued, processing, success, retryable, final,
uncertain, partial, conflict, quarantined, unavailable, command-in-flight,
command-conflict and error states. One operation-specific allowed action is
visible at a time; risky actions require confirmation and show impact.

All user-visible source text is English and passes direct EN/zh/zh-TW,
mixed-language, keyboard, focus, label, tooltip, contrast and non-color-only
tests plus governed screenshots.

### Checkpoint 4 — disposable runtime and final Gate

After checkpoint 3 exact-SHA ordinary CI, extend only the fixed disposable,
network-free runtime to prove Project containment, immutable history,
retryable replay, uncertain no-redispatch, reconciliation intent/observation,
cross-process idempotency, rollback, route disable/recovery, migration twice,
redaction and cleanup. Then close diagnostics and run Level 3.

## 10. Migration and rollback

Both new DocTypes are additive and initially zero-row. Migration must be
idempotent and preserve all existing P8-02 through P8-06 rows. No patch rewrites
historical state.

Before any external boundary, rollback disables P8-07 routes, action capability,
enqueue and UI while retaining every action receipt, reconciliation request,
observation and audit. After a boundary may have been crossed, disable new
commands and claims and use reviewed forward repair. Never delete history,
blindly redispatch, rewrite uncertain/partial/final truth to success, or
compensate a target automatically.

## 11. Frozen implementation paths

The governed manifest enumerates the only eligible product, contract, UI,
runtime, evidence and test paths. Each checkpoint must narrow its actual
changed-file manifest further. Unlisted production profiles, endpoints,
credentials, ERP core, migrations, generic CRUD adapters and P8-08/P8-09 paths
remain unauthorized.

## 12. Verification map

| Changed area | Required evidence |
|---|---|
| pure domain/config | closed enums, raw-state preservation, replay eligibility, uncertain/partial/final fail-closed unit tests |
| metadata/controllers | zero-row migration, mandatory/hash/immutable/deny-delete/controller-context tests |
| ownership/OpenAPI/events | exact operation-specific schemas, no payload/target/status authority, compatibility tests |
| repository/API/worker | Project-first IDOR, capability, locks/CAS, action idempotency, transaction order, rollback, enqueue-after-commit, no-leak tests |
| UI/i18n/a11y | live data-source/component/E2E, EN/zh/zh-TW, loading/empty/permission/read-only/all states, action confirmation/focus/keyboard/visual tests |
| runtime | disposable network-free cross-process replay/reconciliation/no-redispatch/redaction/migration/cleanup proof |
| governance | current-task manifest, reconciliation, requirement status/evidence and task-diff checks |

Level 1 is changed-file focused. Each completed checkpoint requires exact-SHA
ordinary CI. Checkpoint 2 and later require Level 2 affected integration/API/
security tests. Checkpoint 4 and Phase exit require full Level 3 and the
`release-gate` skill. No test deletion, threshold reduction, update-all visual
snapshot or production contact is permitted.

## 13. Holds

Production ERPNext topology, installed customizations, methods, fields, roles,
workflows, service scopes, retry semantics and reconciliation queries remain
external facts in `docs/ERPNEXT_CUSTOMIZATION_REQUIREMENTS.md` and the sole
request `implementation/REQUIRED_INPUTS.md`. Their absence does not block pure,
Mock or disposable technical work and cannot be guessed.

P8-08, P8-09, Phase 9, external FR-CO-003/004 portals and every production
connection remain inactive. The queued production read-only fact check is not
effective authorization under current repository rules.

## 14. Audit-plan Level 1 evidence

The uncommitted exact-fifteen transition passes:

- `38/38` current-task and V1.2 reconciliation unit tests;
- current-task, reconciliation generation and independent reconciliation
  verification;
- JSON, YAML and `282`-row unique requirement CSV parsing;
- Python compile, governed shell syntax and `git diff --check`;
- exact-fifteen manifest acceptance and rejection of an unauthorized
  sixteenth path; the frozen future allowlist contains `66` exact patterns; and
- exact comparison proving all `282` requirement statuses unchanged from
  accepted base `6a82568329e2ec46eae02df76a9d697e26cdf61e`.

The task changes only the fifteen frozen governance, evidence, trace script and
test paths. App, frontend, contract and workflow diffs are zero. Existing
unrelated tracked and untracked workspace state remains untouched.
