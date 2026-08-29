# P8-07 Plan — Operations, DLQ, Replay and Reconciliation

Status: **CHECKPOINT 1 CI PASS — CHECKPOINT 2 AWAITS EXACT-SHA ORDINARY CI**

Audit date: 2026-08-28

Audit base: `6a82568329e2ec46eae02df76a9d697e26cdf61e`

Predecessor product checkpoint:
`547421a059911df6aeb90bbbf06e837f77a3e5e0`

Requirements: `FR-RP-009`, `UX-016`, `NFR-INT-001`

Audit-plan checkpoint: `2e573fa1757f7d9306f17bb47cb62c59e8493b7f`

Audit-plan ordinary CI: `33139628396` (**PASS**)

Checkpoint-1 product Gate:
`d45d1d560fedfed9d9791a5c08ccf9c1402f7ef8` / ordinary CI `33142594763`
(**PASS**)

Product-code authorization: **checkpoint 2 only**. Checkpoint 3 remains closed
until checkpoint 2 exact-SHA ordinary CI passes. Production ERPNext/JCE contact
remains prohibited throughout.

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

The plan Gate has passed. Checkpoint 1 adds only:

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

## 16. Checkpoint-1 Gate and checkpoint-2 candidate

Stable checkpoint-1 SHA `d45d1d560fedfed9d9791a5c08ccf9c1402f7ef8`
passes ordinary CI `33142594763`: repository `98756508685`, frontend
`98756508481`, secret `98756508634` and governed visual `98756508652` all
pass; controlled lanes correctly skip. Checkpoint 2 is therefore active and
its bounded candidate evidence is
`implementation/evidence/phase-8/p8-07-project-operations-checkpoint.md`.

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

## 15. Audit-plan Gate and checkpoint-1 candidate

Exact audit-plan SHA `2e573fa1757f7d9306f17bb47cb62c59e8493b7f`
passes ordinary CI `33139628396`: repository `98747332932`, frontend
`98747332845`, governed visual `98747332990` and secret scan `98747333064`
all pass; controlled lanes correctly skip.

Checkpoint 1 now contains only the authorized behavior-free foundation:

- closed five-operation, action, state, fault, replay and reconciliation
  domain values with raw-state preservation and fail-closed unknowns;
- exact immutable operation references, action receipts and trusted
  reconciliation observations with canonical hashes and bounded safe shapes;
- additive version-1 OpenAPI, internal event and data-ownership components,
  with no new route;
- two guarded append-only support DocTypes with zero default rows and no direct
  operator create/write/delete authority; and
- direct Simplified/Traditional Chinese metadata translations plus focused
  domain, metadata, security and contract tests.

No repository writer, persisted row, route, queue, adapter, target call or UI
behavior is activated. Checkpoint 2 remains closed until this candidate's own
exact-SHA ordinary CI passes.

Checkpoint-1 Level 1 passes `18/18` focused, `550/550` affected predecessor,
`2590/2590` local full Python (`2584` tracked CI tests plus six preserved
untracked local-prerequisite tests), `38/38` governance/reconciliation and `1073/1073`
frontend unit/coverage checks. Direct i18n covers `8496` English sources at
`100%` in `zh` and `zh-TW`; type/lint/format/style/boundary/UI, compile,
JSON/YAML, security, reconciliation, diff and exact `31`/unauthorized `32`
manifest checks pass. Detailed evidence is
`implementation/evidence/phase-8/p8-07-domain-metadata-checkpoint.md`.

Initial product SHA `25c8450` / ordinary CI `33141886949` passed the tracked
Python suite inside repository job `98754314346` before the final global
direct-SQL lexical scan matched only a prohibited token in the new negative
security-test inventory. Frontend `98754314466`, visual `98754314547` and
secret-scan `98754314478` all passed, leaving that repository scanner as the
sole ordinary-CI failure. The same-cycle tests-only repair splits that fixed
test token, preserves the negative assertion, changes no product/scanner/
threshold and makes the exact `verify.sh --repository` entrypoint pass locally.

## 17. Checkpoint-2 Gate and checkpoint-3 live workspace candidate

Stable checkpoint-2 SHA
`f7cf7c7ea490c10acfc044aaef236945e5118f01` passes ordinary CI
`33187660221`: repository `98904745085`, frontend `98904745277`, secret
`98904745231` and governed visual `98904744908` all pass; controlled lanes
correctly skip.

Checkpoint 3 is therefore active only for the live Project-scoped integration
operations workspace. The strict browser data source consumes the frozen
Project-first list, logical-DLQ, detail and fixed command routes; the dense
industrial page covers all ten shared states, permission/read-only/unavailable
and command outcomes, and exposes exactly one server-authorized replay or
reconciliation action at a time. It does not add a server route, adapter,
target call, formal-result authority or production contact.

The current allowlist contains `70` exact patterns, including the shell/router
and their focused unit tests that are materially changed by replacing the old
prototype. Detailed checkpoint-3 evidence is recorded in
`implementation/evidence/phase-8/p8-07-integration-operations-ui-checkpoint.md`.
Checkpoint 4 remains inactive until this candidate passes exact-SHA ordinary
CI.

## 18. Checkpoint-3 Gate and checkpoint-4 runtime candidate

Stable checkpoint-3 SHA
`758bb222a1477474af50fc6b84d5d2c56e379adc` passes ordinary CI
`33204451677`: repository `98961818348`, frontend `98961818460`, secret
`98961818358` and governed visual `98961818084` all pass; controlled lanes
correctly skip. Checkpoint 4 is now the only active scope.

The checkpoint-4 candidate adds one standalone runtime verifier and composes it
into the existing `--projection-only` cumulative disposable Site. It:

- confirms the routes are default-disabled, then verifies explicit disable and
  recovery across fresh server processes;
- reuses retained P8-02 through P8-05 rows to prove Project-first inventory,
  logical DLQ, bounded cursor pagination and permission-safe foreign scope;
- creates one deterministic Item failure that stops before any adapter or
  target boundary, then proves exact retryable replay and immutable history;
- rejects uncertain replay before owner mutation or redispatch, records only a
  reconciliation intent, and appends one trusted `target_unavailable`
  observation that cannot claim authoritative success;
- proves stale action rollback and cross-process action-idempotency replay;
- runs the pinned migration twice, verifies action and observation history are
  immutable afterward, scans for fixture/target/private log markers and removes
  only deterministic runtime rows; and
- sends failed Bench stdout to an unread temporary file and stderr to
  `DEVNULL`; only a zero-exit child may be parsed as one JSON object.

No production profile, endpoint, credential, adapter registry, target call,
generic writer, target-success assertion or P8-08/P8-09 behavior is added.
The local workstation lacks the pinned Frappe application, so the guarded
runtime entrypoint correctly exits before Site creation; the exact-SHA
controlled runtime remains the applicable execution proof after ordinary CI.
Detailed candidate evidence is in
`implementation/evidence/phase-8/p8-07-controlled-runtime-checkpoint.md`.

## 19. Checkpoint-4 Level 3 default-disabled diagnostic boundary

Checkpoint-4 SHA `016be5292e48ac795a2b45f95b07db5555ccae3f`
passes ordinary CI `33208066878`. Its sole Level 3 `33209167283` passes all
four base lanes and controlled preflight, while runtime `98981226307` fails
after Site initialization. Fixed source-label filtering uniquely selects the
P8-07 default-disabled probe; all predecessors passed and no P8-07 fixture or
write was reached.

That label is not a safe repair boundary because it contains ordered login,
transport, response-policy and problem-contract predicates. The bounded
same-checkpoint diagnostic therefore changes only the runtime verifier and its
tests plus governance evidence. It emits one of twelve fixed value-free codes
only on failure, never the actual status, headers, body, identity, values,
message or stack. The activation requires a fresh exact-SHA ordinary PASS and
one Level 2 controlled run. No product/API/schema/frontend/workflow behavior,
target adapter, production profile, Site outside CI, P8-07F or P8-08 scope is
authorized.

Diagnostic Level 1 passes the focused verifier `17/17`, complete P8-07
`51/51`, affected P8-02-through-P8-05 `201/201`, governance/reconciliation
`59/59` and repository `2623/2623` checks in the preserved local tree. Python
compile, shell syntax, current/reconciliation scripts, diff hygiene and the
exact-five plus union-78 manifests pass; an unauthorized sixth path is
rejected. Product, API, schema, frontend and workflow diffs remain zero. The
existing checkpoint-4 frontend evidence is unchanged, and the diagnostic
candidate still requires its own exact-SHA ordinary frontend and repository
lanes before the single controlled diagnostic.

## 20. Default-disabled diagnostic result and UUID harness repair

Diagnostic SHA `3362f416782e05a3f21f0025cdf88730fdbafca1` passes
ordinary CI `33211692745` in all four lanes. Its sole controlled diagnostic
`33212760671` passes preflight `98989580926`, while runtime `98989686823`
fails at the same default-disabled boundary. Strict twelve-code filtering
returns zero safe records; no restricted output was read.

The zero record is statically unique before `run_disabled_probe`. The approved
Project instantiation service deterministically creates Project identities as
UUIDv5, and the retained P8-03 capture returns that canonical value unchanged.
The P8-07 verifier instead required UUIDv4 before any diagnostic recorder could
run. Same-run predecessors crossed the shared local runtime and secret guards.
The bounded harness repair therefore changes only that verifier assertion to
canonical UUIDv5, adds focused v5/v4/noncanonical/malformed coverage and turns
the diagnostic activation off. It does not change product/API/schema/frontend/
workflow behavior, ownership or an ERP contract.

The cycle is diagnostic `1/1`, harness repair `1/1`, final `0/1`. Repair Level
1 passes focused verifier `18/18`, complete P8-07 `52/52`, affected
integration/security `72/72`, governance/reconciliation `59/59` and repository
`2624/2624`. Compile, shell syntax, current/reconciliation scripts, diff and
exact-five/union-78 manifests pass; unauthorized-six is rejected. A fresh
exact-SHA ordinary PASS is required before the sole diagnostics-off Level 3.
P8-07F, SSH/ERP contact and P8-08 remain inactive.

## 21. UUID-repair final result and fresh combined diagnostic

Repair SHA `570fb32b3f334f2b8da60509f00f3344d98a676d` passes ordinary
CI `33213916241` in all four lanes. Its only Level 3 `33214965485` passes
repository `98996446271`, frontend `98996446246`, secret scan `98996446263`,
visual `98996446089` and preflight `98998860347`. Runtime `98998907735`
initializes the exact Bench/Site and then fails at the cumulative step; cleanup
passes. A fixed source-label allowlist yields only
`Local Frappe integration operations runtime verification failed.` No runtime
or child output, response/business value, identity, message or stack was read.

The safe label proves the default-disabled probe passed and `run_fresh`
failed before cross-process replay or later route/migration phases. It remains
nonunique across the ordered fresh verifier and its four Bench fixture methods,
so product repair is prohibited. Freeze the UUID-repair final at `1/1` and
start an independent fresh combined cycle at `0/1,0/1,0/1`.

That diagnostic is product-zero and exact-five: runtime verifier/test plus
`AUTOPILOT_CONTROLLER.md`, this plan and the controlled-runtime checkpoint.
Only `FRESH_COMBINED_DIAGNOSTICS_ENABLED` is true. Its active set is exactly
`97` fixed codes: `45` outer fresh stages plus `52` fixture bootstrap/seed/
snapshot/observation/count stages. The parent supplies one deterministic trace
and owns the exact child environment. Both processes can create only one
absolute exact-name, `0600`, `O_EXCL` JSON record with exactly `code`,
`exceptionType` and `traceId`; child/inner wins and parent fallback cannot
overwrite it. The reader is exact-code/type/trace and one-line fail-closed.
Failed child stdout is not sought or iterated and stderr is `DEVNULL`; success
creates no record. No product, contract, schema, frontend, workflow, adapter,
target or production behavior changes. The candidate needs its own ordinary
PASS before one Level 2 controlled run. P8-07F and P8-08 remain closed.

Diagnostic Level 1 passes focused verifier `26/26`, complete P8-07 `60/60`,
affected integration/security/API `80/80`, governance/reconciliation `59/59`
and full local Python `2632/2632`. Frontend unit/coverage is `1086/1086`, the
focused P8-07 Playwright matrix is `6/6`, and generate/typecheck/full lint plus
`8585`-source `100%` `zh`/`zh-TW` i18n pass. Compile, shell syntax, current and
reconciliation scripts, JSON/YAML/CSV checks, diff hygiene, exact-five,
union-78 and unauthorized-six rejection all pass. Product/API/schema/frontend/
workflow diff remains zero. Only exact-SHA ordinary CI can activate the one
controlled diagnostic.

## 22. Fresh-combined result and collection-shape diagnostic

Exact-five SHA `0d5ea573f9d9e981674157e23c3b175afa56ece8` passes
ordinary CI `33217741527`: visual `99005066818`, frontend `99005066999`,
secret scan `99005067008` and repository `99005067058` are all successful.
The sole controlled diagnostic `33218657373` passes preflight `99007832827`;
runtime `99007879572` initializes the fixed Bench/Site and fails in the
cumulative verifier. Strict exact-code/type/trace filtering yields exactly:
`P807_FRESH_COLLECTION_SHAPE / RuntimeError /
trace-5f309e82918c5bd2bdd54526bd7dd1b0`.

This same-run boundary proves environment, login, CSRF, retryable seeding and
the collection HTTP helper completed. It does not distinguish the collection
status, Project identity, permissions, items container or item element shape.
No response status/body, business value, identity, child output, message or
stack was read. Freeze fresh-combined at diagnostic `1/1`, repair `0/1`, final
`0/1`; do not infer a product repair.

The next independent product-zero cycle retains the same exact five paths.
Only `COLLECTION_SHAPE_DIAGNOSTICS_ENABLED` is true. It adds five ordered
subpredicate codes to the existing `45` outer and `52` fixture codes for an
exact active set of `102`; the prior activation is false and mutual activation
fails closed. The trace, parent-owned child environment, exact-name `0600`
`O_EXCL` exact-three-key record, inner-before-outer precedence, strict reader,
failed-child unread rule and success-zero behavior remain unchanged. Product,
API, repository, contract, schema, frontend and workflow diffs stay zero.
Exact-SHA ordinary PASS is required before the cycle's one Level 2 controlled
run. P8-07F, SSH/ERP contact and P8-08 remain inactive.

Collection-shape Level 1 passes focused verifier `28/28`, complete P8-07
`62/62`, affected contract/security/API `82/82`, governance/reconciliation
`59/59` and full local Python `2634/2634`. Frontend unit/coverage passes
`1086/1086`; focused nonvisual P8-07 E2E passes `3/3`; generate, typecheck,
full lint/format/style/boundary/UI and `8585`-source `100%` `zh`/`zh-TW` i18n
pass. Compile, shell syntax, current/reconciliation, JSON/YAML/CSV, exact-102
lexical equality, diff hygiene, exact-five/union-78 and unauthorized-six
rejection pass. Product/API/repository/contract/frontend/workflow diff is zero.

## 23. Collection-shape result and collection-response diagnostic

Exact-five SHA `ef6ad3a6be46cd6d23409f7f37eb37f4eb7c7edd` passes
ordinary CI `33220082395`: secret scan `99012088629`, frontend
`99012088793`, repository `99012088842` and visual `99012088925` are all
successful. The sole controlled diagnostic `33220922811` passes preflight
`99014580690`; runtime `99014619374` initializes the fixed Bench/Site and
fails in the cumulative verifier. Strict exact-code/type/trace filtering yields
exactly `P807_COLLECTION_STATUS / RuntimeError /
trace-070a0c335c8553aaa6204d1ccbf25a46`.

The same run proves the collection request returned and passed request-ID,
cache-control and recursively safe dictionary-response checks, but its status
was not `200`. The actual status, body, business value, identity, failed-child
output, message and stack were not read. Because that predicate still covers
multiple status classes, no product repair is authorized. Freeze the
collection-shape cycle at diagnostic `1/1`, repair `0/1`, final `0/1`.

The next independent product-zero exact-five cycle enables only
`COLLECTION_RESPONSE_DIAGNOSTICS_ENABLED`. Seven fixed value-free codes classify
invalid, informational, other-success, redirect, client-error, server-error or
out-of-range status without recording the actual value. They combine with the
retained `45` outer and `52` fixture codes for exact `104`; prior activations
are false and multiple activations fail closed. Exact trace, parent-owned child
environment, exact-name `0600` `O_EXCL` exact-three-key record, inner
precedence, strict reader, failed-child unread and success-zero remain
unchanged. Product/API/repository/contract/schema/frontend/workflow behavior is
unchanged. P8-07F, production contact and P8-08 remain inactive pending the
P8-07 Level 3 PASS.

Collection-response Level 1 passes focused verifier `29/29`, complete P8-07
`63/63`, affected integration/security/API `83/83`, governance/reconciliation
`59/59` and full local Python `2635/2635`. Frontend unit/coverage passes
`1086/1086`, focused nonvisual P8-07 E2E passes `3/3`, and generate, typecheck,
full lint plus `8585`-source `100%` `zh`/`zh-TW` i18n pass. Compile, shell
syntax, current/reconciliation, JSON/CSV, exact-104 lexical equality, diff,
exact-five/union-78 and unauthorized-six rejection pass. Product/API/
repository/contract/frontend/workflow diff is zero.

## 24. Collection-response result and minimal mock-only compatibility repair

Exact-five SHA `48871b94ae9bee7dda5e9d6fe6171d772b75ab4b` passes
ordinary CI `33221910716` in all four lanes. Its sole controlled diagnostic
`33222456752` passes preflight `99019233634`; runtime `99019272929`
initializes the fixed Bench/Site and fails in the cumulative verifier. Strict
exact-104 filtering returns exactly
`P807_COLLECTION_STATUS_SERVER_ERROR / RuntimeError /
trace-2fcaaa171b4f51fba5bafa3c447f1a73`. The response class is recorded without
its actual value; status/body, failed-child output, business values,
identities, message and stack were not read.

The cumulative P8-03 fixture intentionally leaves one `validated_mock` Item
publish validation in the disposable Site. That state proves validation only:
dispatch is false and there is no target idempotency key. P8-07 nevertheless
enumerated every matching Item publish row and constructed a formal operation
reference whose existing contract requires a valid target key. The absent key
therefore deterministically fails the collection. This is a narrow derived-read
compatibility defect, not evidence for changing the approved contract,
ownership, workflow or integration architecture.

The minimal repair excludes only an exact `publish_item` row whose state is
`validated_mock` and whose target key is absent. It does not invent a target
identity or relax the operation contract. A missing target key in any non-mock
state still fails closed, while a queued row with a valid key retains the
unchanged operation reference. The collection-response diagnostic activation
is false in release code and is activated only inside its focused mechanism
tests. The exact-seven task changes repository/test, verifier/test and the
three governance/evidence files. Product behavior outside this derived
collection filter, API, contracts, schema, frontend, workflow and production
ERP remain unchanged.

Freeze the cycle at diagnostic `1/1`, repair `1/1`, final `0/1`. A new
exact-SHA ordinary PASS must precede the sole diagnostics-off Level 3. P8-07F,
SSH/ERP contact and P8-08 remain closed until that Level 3 passes.

Repair Level 1 passes focused verifier/repository `40/40`, complete P8-07
`64/64`, governance/reconciliation `59/59`, full Python `2636/2636`, frontend
unit/coverage `1086/1086` and focused nonvisual P8-07 E2E `3/3`. Generate,
typecheck, full lint/format/style/boundary/UI, `8585`-source `100%` `zh`/
`zh-TW` i18n, compile, shell syntax, current/reconciliation, JSON/YAML,
direct-SQL/network/permission scans, exact-104 localized diagnostics, diff,
exact-seven/union-78 manifests and unauthorized-eight rejection pass. Product
API, contracts, schema, frontend and workflow diffs remain zero outside the
minimal derived-read change.

## 25. Mock-only repair final and post-mock combined diagnostic

Repair SHA `5117bd67359517c21bf4a4824245103c83d675cd` passes ordinary
CI `33223526404` in all four lanes. Its sole diagnostics-off Level 3
`33224261629` passes secret scan `99024629237`, repository `99024629338`,
visual `99024629353`, frontend `99024629452` and preflight `99026648007`.
Runtime `99026682189` fails in the cumulative verifier after fixed Bench/Site
initialization; cleanup completes.

Only the fixed source label
`Local Frappe integration operations runtime verification failed.` is present.
This proves earlier cumulative verifiers passed and P8-07 returned nonzero,
but does not identify one internal predicate while all diagnostics are off.
Runtime/child output, response status/body, business values, identities,
message and stack were not read. Freeze the repair final at `1/1`; no further
product change is authorized from that label.

The next independent exact-five cycle is product-zero and enables only
`POST_MOCK_COMBINED_DIAGNOSTICS_ENABLED`. Historical flags remain false. The
new activation reuses exact `104`: `45` ordered outer stages, `52` fixture
stages and seven value-free collection-response status classes. Exact trace,
parent-owned child environment, exact-name `0600` `O_EXCL` exact-three-key
record, nearest-inner precedence, strict reader, failed-child unread and
success-zero behavior remain unchanged. Product/API/repository/contracts/
schema/frontend/workflow behavior is unchanged. Exact-SHA ordinary PASS is
required before one controlled Level 2 diagnostic. P8-07F, SSH/ERP contact
and P8-08 remain closed.

Diagnostic Level 1 passes focused verifier `29/29`, complete P8-07 `64/64`,
governance/reconciliation `59/59`, full Python `2636/2636`, frontend
unit/coverage `1086/1086` and focused nonvisual E2E `3/3`. Generate,
typecheck, full lint/format/style/boundary/UI, `8585`-source `100%` `zh`/
`zh-TW` i18n, compile, shell syntax, current/reconciliation, JSON/YAML,
exact-104 lexical/precedence/reader checks, diff, exact-five/union-78 and
unauthorized-six rejection pass. Product/API/repository/contracts/schema/
frontend/workflow diff remains zero.
