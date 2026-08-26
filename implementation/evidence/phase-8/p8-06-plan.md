# P8-06 Plan — Formal Quality Linkage Foundation

Status: **AUDIT-PLAN CI PASS — CHECKPOINT 1 BOUNDED AUTHORIZATION TRANSITION**

Audit date: 2026-08-26

Audit base and predecessor product checkpoint:
`f9c358018823f3af20aca38efb53f8fcbd13d406`

Requirements: `INT-007`, `FR-TR-006`, `FR-NP-006`

Audit-plan checkpoint:
`b3cf6ac722c71c4bdd95cddc16aed4e2544bb037`

Audit-plan ordinary CI: `32946799144` (`PASS`; secret `98109154354`, frontend
`98109154557`, repository `98109154561`, governed visual `98109154578`; both
controlled lanes correctly skipped).

Product-code authorization: **checkpoint 1 bounded only after this separate
controller-transition exact SHA passes ordinary CI**. The transition itself
contains no app, frontend or contract change. Checkpoint 1 remains behavior-free:
no route, persisted business row, writer, worker, adapter, target request, UI or
network behavior is authorized.

## 1. Requirement and source conclusion

The V1.2 requirements require NPI One to show the latest ERPNext formal
Quality Inspection, NCR or CAPA status without rewriting the formal result,
to link Trial and readiness quality evidence to that formal truth, and to let
a formal failed result block rather than pass the applicable readiness or Gate
decision. They do not approve an ERPNext method, DocType customization, field,
workflow, status mapping, approval actor or production endpoint.

The authoritative repository facts are:

- P8-01 already owns a read-only `formal_quality_status` projection. Its
  authenticated observation preserves exact Project and consumer scope,
  `recordKind`, raw `statusCode`, nullable raw `resultCode`, source identity,
  source version, source-modified time, observed time, payload hash, guarded
  head ordering, availability, freshness and conflict truth.
- `recordKind` is the existing closed technical vocabulary
  `quality_inspection | ncr | capa`. These values classify observed records;
  they do not prove that the current ERPNext v15 deployment implements three
  standard DocTypes with those exact names.
- P8-01 deliberately installs no quality pass/fail mapping, Gate invalidation
  policy, CAPA workflow, freshness threshold, production mapping or target
  command. Mock and synthetic observations are non-authoritative.
- P7-03 owns Trial cavity result, defect, action and independent verification
  truth. Its formal Quality Inspection, NCR, Gate and Tooling effects are
  explicitly unavailable and it emits no ERP command.
- P7-04 owns immutable Trial comparison, reference and conclusion snapshots.
  Formal ERP quality identity/result remains a distinct unavailable reference
  and evidence presence is not approval.
- P7-05 owns readiness source evaluation and controlled quality-report
  evidence. A controlled NPI report is not formal ERP quality; a required
  failed or unavailable ERP quality source blocks readiness and cannot be
  offset by a score.
- The checked-in target is Frappe v15 compatible, but the production ERPNext
  version, installed apps, custom DocTypes, Quality Inspection/NCR/CAPA fields,
  workflows, roles, webhooks and service scopes remain requested external
  facts in `implementation/REQUIRED_INPUTS.md`. No production contact is
  permitted.

Therefore P8-06 can freeze a technical read/link foundation, but it cannot
invent a formal target write or a business pass/Gate rule. The current
requirement statuses remain technical-foundation/held statuses until later
authenticated Sandbox and approved policy evidence exists.

## 2. In scope

After the frozen-plan CI passes, P8-06 may implement only:

1. a pure, versioned domain for one NPI-owned immutable link from an exact NPI
   quality context to one exact current P8-01 formal-quality observation;
2. closed source/context/record-kind/state/fault/config contracts and additive,
   guarded metadata with no route or row creation in checkpoint 1;
3. a fixed Project-first NPI command named
   `link_observed_formal_quality_reference` in a later checkpoint, provided
   the exact source-specific existing authority is proven server-side;
4. read-only Project/Trial/review/readiness projection of the exact linked
   observation and its unavailable/stale/conflict truth;
5. immutable command receipt, idempotency, audit and predecessor/current-head
   checks for that NPI link only; and
6. direct EN/zh/zh-TW presentation and accessibility evidence in the existing
   Trial quality/review/readiness contexts, with no ERP target control.

The command above links an already observed record. It does not create,
submit, pass, fail, close, cancel, reopen or edit a Quality Inspection, NCR or
CAPA and does not acknowledge an ERP workflow action.

## 3. Explicit non-scope

- production ERPNext/JCE endpoints, credentials, data, requests, responses or
  traffic;
- any caller-selected tenant, actor, target method, DocType, endpoint, formal
  document identity, status, result, disposition, target version or payload;
- any ERP write, submission, approval, failure, closure, cancellation,
  correction, waiver, NCR creation, CAPA action or compensating transaction;
- any inferred mapping from raw ERP status/result codes to formal pass/fail,
  Gate invalidation, waiver, release or readiness approval;
- any mutation of Trial, defect, review, conclusion, readiness, controlled
  report, Project, Gate, Work Item, Tooling, Item, MBOM or Asset truth;
- any generic operations center, DLQ, retry/replay/reconcile action or
  corrected-command flow allocated to P8-07;
- any P8-08/P8-09 or Phase 9 authority, new dependency, core patch,
  cross-database access, direct SQL, permission bypass or test weakening.

## 4. Ownership and authority

| Truth | Owner | P8-06 treatment |
|---|---|---|
| formal quality document identity/version/lifecycle | ERPNext | exact read-only P8-01 observation only |
| formal status/result/approval/submission/closure | ERPNext | raw observed codes; no interpretation or mutation |
| Trial cavity/result/defect/action/verification | NPI One | retained exact P7 revision; never promoted to ERP truth |
| Trial review/reference/conclusion | NPI One | retained exact P7 revision; evidence is not approval |
| readiness source/result/blocker | NPI One | derives only unavailable/failed blocker truth under an approved policy; never fabricates pass |
| controlled quality report | NPI One | evidence reference only; never formal ERP inspection |
| formal-quality observation/head/order | NPI One integration mirror of ERP-owned truth | P8-01 remains sole writer/ordering owner |
| formal-quality link identity/revision/audit | NPI One | append-only reference to exact source and exact observation |
| quality pass/Gate invalidation policy | future approved business policy | absent and fail-closed |
| generic replay/reconciliation operations | P8-07 | not implemented by P8-06 |

P8-06 must never update a P8-01 observation or head. A link retains the exact
observation and head expectation that was reviewed; rendering latest truth is
separate from immutable historical evidence.

## 5. Frozen identities and fields

### 5.1 NPI source context

Every proposed link input must carry server-resolved, immutable identifiers
and hashes for:

- tenant and Project;
- context kind: `trial_round`, `trial_defect`, `trial_review`,
  `readiness_assessment` or `controlled_quality_report`;
- exact context global ID, current revision global ID, revision number and
  snapshot hash;
- the context's exact Project/Trial/Readiness containment; and
- an expected current context revision/hash so a stale link conflicts before
  any write.

These technical context kinds do not merge their domain authorities. Each
adapter must resolve its source through the owning P7 repository and must not
accept a generic DocType or arbitrary global ID.

### 5.2 Formal observed target

The link target is an existing P8-01 `formal_quality_status` observation with:

- exact observation global ID and immutable payload hash;
- exact guarded head global ID/version and currentness expectation;
- exact source system `ERPNEXT`, `sourceObjectType`, `sourceObjectId` and
  opaque `sourceVersion`;
- source modified time, observed time, disposition, availability and
  freshness truth;
- exact consumer scope kind/global ID and Project containment;
- closed `recordKind` and raw status/result codes.

Source IDs and codes are business data and must not be logged as diagnostic
context. Equal-time conflicts, superseded observations, stale/unknown
freshness, unavailable rows, Mock and synthetic rows are never linkable as
current authoritative formal truth.

### 5.3 Link revision and command receipt

The future link domain must freeze:

- stable link global ID plus append-only revision global ID/number;
- exact NPI source snapshot and exact formal observation snapshot;
- actor, trace ID, operation, created time and canonical payload hash;
- operation-bound idempotency key and immutable response hash;
- state `linked` or `superseded` only as NPI reference history, never a formal
  quality lifecycle state.

No formal pass boolean, target workflow action, approver or inferred
disposition belongs in the link record.

## 6. Operation and projection boundary

| Capability | Status | Contract |
|---|---|---|
| list exact formal-quality observations | existing P8-01 read-only | Project-first, exact consumer containment, permission filtered, raw codes only |
| view latest current formal-quality observation | existing P8-01 read-only | authenticated authoritative head only; unavailable/stale/conflict remains explicit |
| link observed formal-quality reference | planned NPI-only operation | fixed operation, exact source revision and exact current observation/head expectations, actor-bound idempotency, no ERP call |
| create/submit/update Quality Inspection | held | no approved target method/fields/authority/profile |
| create/update/close NCR | held | no approved target DocType/lifecycle/authority/profile |
| create/update/close CAPA | held | no approved target DocType/lifecycle/authority/profile |
| map raw code to pass/fail/Gate invalidation | held | requires approved versioned policy and business authority |
| manual retry/replay/reconcile | P8-07 | no P8-06 control or generic command |

The link command is not an ERP execution request and therefore does not use a
target adapter, attempt or formal-result mapping. If a later approved Sandbox
write is added, it must be a new operation-specific audited plan/checkpoint;
it cannot be smuggled into this link contract.

## 7. Permission and approval matrix

| Boundary | Required proof | Failure truth |
|---|---|---|
| list/detail | authenticated internal actor plus exact Project VIEW before secondary IDs | same not-found/unavailable result for absent, foreign and ambiguous context |
| link source | current active Project membership plus the owning P7 context's existing exact mutation/reference capability | forbidden; UI hiding is not authority |
| link target | exact Project and consumer-scope containment plus current authoritative P8-01 head | unavailable/conflict; no fallback to tenant-wide observation |
| write link | mutable Project, exact source revision/hash, exact head expectation, CSRF, trace and operation-bound idempotency | validation/conflict before write |
| ERP approval/submission | ERPNext-owned and not installed | unavailable; NPI actor cannot approve ERP truth |
| readiness/Gate effect | separately approved versioned policy and exact decision authority | unavailable/blocking; never implicit pass |

Because the exact role-to-link capability has not yet been proven across all
five source contexts, checkpoint 1 is behavior-free. Checkpoint 2 may activate
only the subset whose existing server capability can be reused without
inventing a role. Unproven contexts remain read-only/unavailable.

## 8. State and truth model

The user-facing aggregate remains closed and non-optimistic:

- `unavailable`: profile, source, permission-safe target, policy or current
  observation is unavailable;
- `stale`: an approved freshness policy marks the observation stale; without
  a policy freshness remains `unknown`, not fresh;
- `conflict`: equal-order divergent observation, changed source revision or
  changed head expectation;
- `observed`: exact authoritative ERP observation exists, with raw codes;
- `linked`: an immutable NPI reference points to that exact observation;
- `failed`: only when an approved policy classifies an exact raw target result;
- `partial` / `uncertain`: reserved for a separately approved future target
  operation and never formal pass;
- `mock` / `synthetic`: test truth only, never formal pass or formal ID.

P8-06 must not introduce a `passed` state before the exact status/result
mapping and Gate/readiness policy is approved. A formal source that cannot be
interpreted remains observed/raw and cannot satisfy a mandatory pass.

## 9. Idempotency, replay and reconciliation

For the NPI-only link operation:

1. idempotency scope is tenant + Project + operation + actor + key;
2. replay with identical canonical payload returns the original receipt and
   exact link revision;
3. the same key with a different payload hash conflicts;
4. source or head drift conflicts before persistence;
5. link revision, idempotency receipt and audit commit atomically;
6. no queue, adapter or target network is used;
7. retries never resolve a newer observation under an old request; and
8. reconciliation reports current-link versus current-head drift read-only.

P8-07 owns generic replay, DLQ and operational reconciliation controls. P8-06
may expose drift facts but no manual redispatch or target correction action.

## 10. Fault matrix

| Fault | Required result | Forbidden result |
|---|---|---|
| missing/foreign Project or source | permission-safe not found/unavailable | cross-Project identity disclosure |
| missing/foreign/ambiguous observation | unavailable | tenant-wide fallback |
| superseded/conflicted observation | conflict/unavailable | current linked truth |
| source revision or head changed | conflict before write | latest-value substitution |
| duplicate same key/same payload | exact replay | duplicate link revision |
| duplicate key/different payload | idempotency conflict | overwrite original receipt |
| raw status/result unknown | preserve raw observed value; interpretation unavailable | inferred pass/fail |
| required source unavailable | readiness blocker/unavailable | pass or score override |
| Mock/synthetic observation | non-authoritative, no formal ID | formal pass/link success |
| timeout/partial/uncertain future target | retained non-pass truth | blind redispatch or success |
| enqueue failure | not applicable to NPI link | hidden queue side effect |
| production endpoint/profile | reject configuration | fallback target contact |

## 11. Checkpoints

### Checkpoint 1 — behavior-free domain and contracts

- pure source/link/config/state/fault/idempotency domains;
- additive versioned ownership/event/OpenAPI components and guarded metadata
  only if their exact schemas are approved in the checkpoint;
- default-disabled profile and direct trilingual labels;
- no route, row creation, worker, adapter, UI behavior or network.

### Checkpoint 2 — Project-first link repository and BFF

- fixed list/detail and `link_observed_formal_quality_reference` routes;
- source-specific repository adapters only for proven existing authorities;
- exact source/head locks, atomic link/idempotency/audit and replay/conflict;
- no ERP Outbox, target call, worker or formal pass interpretation.

### Checkpoint 3 — read-only consumers and bounded reconciliation facts

- project/trial/review/readiness read projections of linked/current/drift truth;
- unavailable/failed blocking integration only where an existing P7 policy
  already supports it and no new pass/Gate mapping is inferred;
- network-free disposable proof and no generic operations controls.

### Checkpoint 4 — industrial UI and Level 3

- compact read-only formal-quality inspector in existing Trial/readiness
  workspaces, one guarded link action only where server capability is true;
- loading, empty, unavailable, no-permission, read-only, stale, conflict,
  observed, linked and held-policy states;
- direct EN/zh/zh-TW, keyboard, accessibility, responsive and governed visual
  evidence; no ERP approval/submit/retry/reconcile control;
- complete exact-SHA ordinary CI and Level 3 cumulative runtime.

Every checkpoint starts only after the previous exact product SHA passes
ordinary CI. Checkpoint-1 product paths remain closed until this separate
controller-transition exact SHA passes ordinary CI; later checkpoint paths
remain unauthorized.

### Independent formal-quality runtime-stage diagnostic

Checkpoint-4 harness SHA `f382e708564e7b82cb54ac54280fbf722249e0b0`
passes ordinary CI `32989038683`, including native Bookworm/x64 `132/132`
visuals. Its sole Level-3 run `32990691540` passes every normal and preflight
job and then fails only at the withheld formal-quality-link verifier boundary.
The checkpoint-4 final is frozen at `1/1`; no rerun or product repair is
authorized.

The independent `p8-06-quality-link-runtime-stage` cycle starts at diagnostic
`0/1`, repair `0/1`, final `0/1`. It is verifier-only and has exactly seventeen
ordered codes from bootstrap, retained readiness and disposable projection
setup through create, replay, stale, list and cleanup. One run-scoped trace,
innermost-one-record and same-exception/finally rules apply. A failed verifier
exclusively creates at most one exact-three-key safe record. The cumulative
shell discards failed-child stdout/stderr and exposes only a strict-reader-
validated code/type/trace tuple; missing, duplicate, malformed, unknown or
mismatched records expose no tuple.

The exact diagnostic paths are `scripts/verify_quality_link_runtime.py`,
`scripts/verify-frappe-runtime.sh`,
`tests/test_phase8_quality_link_runtime_verifier.py`, this plan, the phase-8
checkpoint evidence and `implementation/AUTOPILOT_CONTROLLER.md`. There is no
product, app, API, repository, contract, metadata, migration, UI, translation,
visual or network change. FR-CO-003/004 deferral and every B/C hold remain
immutable.

## 12. Planned product paths and tests

Checkpoint 1 is frozen to the following exact product paths; no wildcard is
authorized:

- `apps/npi_integration/npi_integration/quality_link/__init__.py`;
- `apps/npi_integration/npi_integration/quality_link/config.py`;
- `apps/npi_integration/npi_integration/quality_link/domain.py`;
- `apps/npi_integration/npi_integration/quality_link/doctype_base.py`;
- `apps/npi_integration/npi_integration/quality_link/frappe_validation.py`;
- the exact `__init__.py`, JSON and Python controller beneath each of
  `npi_formal_quality_link_head`, `npi_formal_quality_link_revision` and
  `npi_formal_quality_link_command_idempotency` in the integration app's
  DocType directory;
- `contracts/data-ownership.yaml` and `contracts/npi-api.openapi.yaml` only;
- `apps/npi_core/npi_core/translations/zh.csv`,
  `apps/npi_core/npi_core/translations/zh-TW.csv` and
  `frontend/src/generated/catalogs.ts`; and
- `tests/test_phase8_quality_link_config.py`,
  `tests/test_phase8_quality_link_domain.py`,
  `tests/test_phase8_quality_link_contract.py`,
  `tests/test_phase8_quality_link_metadata.py` and
  `tests/test_phase8_quality_link_security.py`.

`contracts/integration-event.schema.json`, any API/BFF path, repository,
Outbox, scheduler, worker, adapter, runtime fixture, browser source and visual
baseline are deliberately absent. The checkpoint may define only reusable
OpenAPI components, never a route or command response.

The exact changed-files-to-tests map is:

| Checkpoint-1 boundary | Required proof |
|---|---|
| pure domain/config | closed source/context/record/state/fault/idempotency values; exact canonical hashes; disabled default; no endpoint/credential/network |
| guarded metadata | install/migrate twice; zero fixture/default rows; internal write capability; append-only revision; exact head +1 CAS; one-way receipt seal; update/delete/tamper denial |
| ownership/OpenAPI components | ERP formal identity/status/result remains read-only; NPI link history remains NPI-owned; components have closed shapes; zero new path/event/Outbox |
| translations/catalog | English source; exact direct `zh`/`zh-TW`; generated catalog symmetry; placeholder and mixed-language scans |
| regression/security | P8-01 projection domain/contract/metadata; P7 Trial quality/review/readiness domain/contract/metadata; Item/MBOM/Tool Asset config/domain/contract/metadata/security; zero SQL, `ignore_permissions`, whitelisted route, worker, adapter, request library, production literal or fixture row |
| governance | current-task and reconciliation units; exact manifest; JSON/YAML/CSV parse; Python compile and diff hygiene |

Checkpoint 2 repository/permission/IDOR/idempotent link behavior, checkpoint 3
consumer/reconciliation projection and checkpoint 4 UI/runtime/visual evidence
remain closed and are not inherited by checkpoint 1.

## 13. Migration and rollback

The audit and controller transition have no runtime or data migration.
Checkpoint 1 may add only the three guarded, additive, versioned support
DocTypes above; install/migrate twice must pass with no row creation. Before
rows exist, rollback removes only those additive metadata definitions and pure
components on a disposable Site. Checkpoint 2 may create NPI link history only
after exact authorization.

Rollback before product activation reverts this controller/trace plan and
restores the P8-05 product checkpoint while preserving all P8-01 observations
and P7/P8 history. After link rows exist, disable the P8-06 route and UI and
retain link revisions, idempotency receipts and audit. Repair is forward-only:
never delete a formal reference, rewrite raw ERP truth, retarget an immutable
link to latest, mutate ERP, or turn unavailable/failed truth into pass.

## 14. Unresolved Class B and Class C facts

### Class B — held without blocking the technical foundation

1. exact ERPNext v15/custom-app DocTypes corresponding to NCR and CAPA;
2. exact Quality Inspection/NCR/CAPA fields, naming, versions, workflows,
   submit/fail/close events and service-user scopes;
3. raw status/result-to-pass/fail/closed mapping and its versioned owner;
4. exact Gate invalidation, waiver/reopen and readiness-blocking policy;
5. exact role/capability allowed to create each source-context link;
6. link cardinality and mandatory-source rules for each Trial/readiness stage;
7. approved Sandbox endpoint/profile/operation and authenticated result proof;
8. freshness threshold and reconciliation ownership.

These facts remain `unavailable` or raw/read-only. No convenient default is
permitted.

### Class C — prohibited

- production credentials, endpoints, records, network contact or mutation;
- irreversible migration, backfill, deletion or compensation;
- Frappe/ERPNext core modification, permission bypass or cross-database write.

## 15. Exit criteria

This audit passes when the plan, controller, risk/decision/blocker state,
Phase 8 anchor, trace CSV and reconciliation checks agree that:

- P8-01 remains the sole formal-quality observation owner;
- the only frozen NPI operation is exact-observation linking, not ERP write;
- formal pass and Gate/readiness interpretation remain held;
- product code remains bounded to checkpoint 1 only after the controller-
  transition exact-SHA ordinary CI passes;
- production ERPNext and generic P8-07 operations remain inactive; and
- every unresolved B/C fact is explicit and fail-closed.

## 16. Checkpoint-1 implementation status — Level 1 PASS

The bounded authorization transition at exact SHA
`675c28a15133b9937ccac6af492db7c537a17946` passed ordinary CI
`32949383911`. Checkpoint 1 now implements only the frozen behavior-free
foundation: pure closed link/source/observation/idempotency/fault values;
default-empty disabled configuration; three guarded zero-row support
DocTypes; ownership and OpenAPI components; direct `zh`/`zh-TW` plus the
generated catalog; and five focused test modules.

P8-01 remains the only observation/head/order/freshness owner. A link accepts
only exact `formal_quality_status`, `ERPNEXT`, `available`, `fresh` and
`applied_current` observation truth and retains raw status/result codes. No
formal-pass, Gate or readiness interpretation is installed. Integration
events, API/BFF paths, repository writes, Outbox, worker, adapter, runtime,
UI, network and seeded rows remain absent. Detailed Level-1 evidence is in
`implementation/evidence/phase-8/p8-06-domain-metadata-checkpoint.md`.

## 17. Checkpoint-2 controller transition

Checkpoint-1 exact product SHA
`64b59f219f4a5687865e6b27670e3bd11d186b88` passes ordinary CI
`32953275865`: frontend `98129304814`, repository `98129305104`, secret
`98129305097` and governed visual `98129305261` pass. OpenAPI paths remain
unchanged, the integration-event schema is unchanged, and no BFF, route,
repository, worker, adapter, fixture or network behavior exists in checkpoint
1.

This governance-only transition authorizes checkpoint 2 only after its own
exact-SHA ordinary CI passes. The exact fourteen product paths are:

- `apps/npi_core/npi_core/bff.py`;
- `apps/npi_core/npi_core/translations/zh.csv` and
  `apps/npi_core/npi_core/translations/zh-TW.csv`;
- `apps/npi_integration/npi_integration/quality_link/frappe_repository.py`;
- `apps/npi_integration/npi_integration/quality_link/problems.py`;
- `apps/npi_integration/npi_integration/quality_link/frappe_validation.py`;
- `apps/npi_integration/npi_integration/quality_link_api.py`;
- `contracts/npi-api.openapi.yaml`;
- `frontend/src/generated/catalogs.ts`; and
- `tests/test_phase8_quality_link_api.py`,
  `tests/test_phase8_quality_link_repository.py`,
  `tests/test_phase8_quality_link_security.py`,
  `tests/test_phase8_quality_link_contract.py` and
  `tests/test_phase8_quality_link_metadata.py`.

Checkpoint 2 exposes fixed Project-first list/detail and the sole NPI-owned
`link_observed_formal_quality_reference` command. Project VIEW is checked
before secondary identities. A link command requires mutable Project context,
CSRF/trace, one exact current source revision/hash, one exact current P8-01
observation/head and an existing source-specific server capability. The only
proved active mappings are `trial_defect` -> `manageDefects`, `trial_review`
-> `manageReviewReferences` and `readiness_assessment` -> `canRevise` from
their owning current Project-first responses. `trial_round` has no exact link
capability and `controlled_quality_report` has distinct retain/revise
capabilities rather than one approved link authority, so both remain
unavailable without role fallback.

One transaction appends the immutable Link Revision, advances the Link Head by
exact `+1`, seals the operation-bound actor/idempotency receipt and appends the
audit. Same-key/same-payload returns the exact original result; same-key/
different-payload, source drift, head drift, foreign/ambiguous containment or
optimistic-version drift conflicts before write. List/detail remain
permission-safe and never reveal foreign identities.

No ERP Outbox, enqueue, scheduler, target method, worker, adapter, target
network, runtime fixture, UI, generic replay/reconciliation control or formal
pass mapping is authorized. P8-01 remains the only observation/head/order/
freshness owner; raw ERP status/result remains uninterpreted. Existing Class-B
source authority, mapping, lifecycle, approval and freshness facts and all
Class-C production boundaries remain held.

Changed-files-to-tests must cover API shape and BFF routing, Project-first
IDOR/permission denial, every allowed and unavailable source kind, exact
source/head locks, canonical payload/idempotency replay and conflict, atomic
revision/head/receipt/audit ordering and rollback, capability/finally restore,
zero Outbox/enqueue/network, closed OpenAPI responses, direct trilingual
messages, P8-01/P7 source regressions and Item/MBOM/Tool Asset peers.

Before any checkpoint-2 row exists, rollback removes only the BFF/API/
repository/problem/i18n/OpenAPI additions and retains checkpoint-1 metadata.
After link history exists, disable the P8-06 route and retain immutable link
revisions, heads, receipts and audits for forward repair. Never delete or
retarget a link, mutate ERP truth or reinterpret unavailable/raw evidence as
pass.

## 18. Checkpoint-2 authorization restoration after portal scope decision

The original exact-fourteen checkpoint-2 boundary is accepted at controller
SHA `bc6095c1ba23580dc3eec3ace4fe9798fc3c160c`, ordinary CI
`32955709358`. The intervening governance-only FR-CO-003/004 decision passes
exact SHA `51c552a0863d7c2cdb818585aa7017e5996501b3`, ordinary CI
`32957762888`. That decision keeps both portal requirements P1
`REMAPPED_PHASE_9`, marks only external login/identity/self-service portal
surfaces `USER_APPROVED_POST_V1_2_DEFERRED`, and retains all internal V1.2 and
Phase-9/final-gate obligations.

This separate restoration changes no product path. Only after its own
exact-SHA ordinary CI may the unchanged fourteen product paths in section 17
resume. Project-first authorization, exact source/head locks, supported source
capabilities, one atomic revision/head/idempotency/audit transaction, replay,
conflict, ownership, permission, rollback and all external holds remain
bit-for-bit the same boundary. The portal decision is not reverted or included
in P8-06 product scope.

## 19. Checkpoint-2 acceptance and checkpoint-3 controller transition

Checkpoint 2 passes exact accepted tip
`9983a8d0b6ff87d6bc8a9891c428f1790b83d91f` and ordinary CI
`32964612981`: frontend `98164272727`, repository `98164272787`, governed
visual `98164272829` and secret scan `98164272855` pass. Product commit
`2e4ace358c734b36eb72203108cadc8db425f503` is the unchanged exact-fourteen
implementation. Initial ordinary `32962969595` passed all product tests and
the other three lanes, then the direct-SQL zero-match scanner found only two
negative-test literals. Exact tests-only remediation `9983a8d` retains the
same product-symbol assertion without modifying product, scanner or allowlist;
this is a harness root and product root count is zero.

Checkpoint 3 is a read-only extension of the existing Project-first
quality-link list/detail responses, not a new operation. For each immutable
link it may expose one closed reconciliation fact:

- `current` requires exact Project containment, exact current source identity,
  version and snapshot hash, plus exact current P8-01 formal-quality head and
  observation identity, version and hash;
- `drifted` requires a valid contained source or P8-01 head advancement and
  reports no substituted identity or interpreted result; and
- `unavailable` covers missing, ambiguous, foreign, malformed or corrupt
  source/head truth without disclosing a secondary identity.

There is no tenant-wide latest lookup, caller-provided state, reconciliation
write, link mutation or automatic successor. Raw ERP status/result remains
uninterpreted. P7 Trial quality, Trial review and readiness repositories are
regression consumers only: checkpoint 3 does not alter their source state,
policy, score, blocker, Gate or mutation behavior. In particular, no existing
approved policy maps formal raw quality codes, so link currentness cannot
satisfy readiness or produce formal pass/fail.

The frozen exact-nine product paths are:

- `apps/npi_integration/npi_integration/quality_link/domain.py`;
- `apps/npi_integration/npi_integration/quality_link/frappe_repository.py`;
- `apps/npi_integration/npi_integration/quality_link_api.py`;
- `contracts/npi-api.openapi.yaml`;
- `tests/test_phase8_quality_link_api.py`;
- `tests/test_phase8_quality_link_contract.py`;
- `tests/test_phase8_quality_link_domain.py`;
- `tests/test_phase8_quality_link_repository.py`; and
- `tests/test_phase8_quality_link_security.py`.

Changed-files-to-tests must prove the closed reconciliation enum/shape,
exact current and one-sided source/head drift, missing/foreign/ambiguous/
malformed fail-closed behavior, stable Project-first IDOR containment, no
additional write or query authority, zero SQL/permission bypass/Outbox/
enqueue/worker/adapter/network/runtime/UI, exact OpenAPI shape, and full P8-01
projection plus P7 Trial quality/review/readiness regressions. Item, MBOM and
Tool Asset security/contract peers, current/reconciliation governance and task
manifest/diff checks remain required.

Before checkpoint-3 response activation, rollback reverts only its exact-nine
response/domain/contract/test changes. If a client has observed the read-only
shape, disable that projection through a forward fix while retaining every
immutable link revision, head, receipt, audit and P8-01 observation. No data
migration or deletion is authorized. Checkpoint 4 UI, runtime, target effects,
generic P8-07 operations, production/Sandbox contact and deferred external
portal surfaces remain closed. Checkpoint 3 product work starts only after
this governance transition passes exact-SHA ordinary CI.

## 20. Checkpoint-3 acceptance and checkpoint-4 controller transition

Checkpoint 3 passes exact product SHA
`f09f7baed565b232f37530ede3df0a13fb466a1e` and ordinary CI
`32971175544`: frontend `98185026209`, repository `98185025979`, governed
visual `98185026270` and secret scan `98185026147` pass. The exact-nine
product change adds only `current`, `drifted` and `unavailable` read facts to
the existing list/detail response; it creates no route, write or migration.

Checkpoint 4 remains one bounded UI/runtime slice:

- a compact formal-quality inspector appears only in the existing Trial
  quality and Project readiness workspaces;
- it reuses the existing Project-first P8-01 projection, quality-link query
  and `link_observed_formal_quality_reference` routes;
- P8-01 may expose only authenticated exact observation/head identity,
  version and hash already required by the link command; P8-01 remains the
  only observation/head/order/freshness owner;
- the only visible primary action is a link Impact Review and appears only
  when both the quality-link query permission and exact source workspace
  capability are true. Trial defect uses `manageDefects`; readiness assessment
  uses `canRevise`; no generic or client-inferred authority is accepted;
- direct EN/zh/zh-TW loading, empty, no-permission, read-only, current,
  drifted, unavailable, conflict and error states must pass keyboard, axe,
  responsive, mixed-language and fixed-Linux governed visual checks; and
- a disposable network-free cumulative runtime proves link, actor-bound
  replay, stale/conflict rejection, current/drift/unavailable, permission,
  zero ERP target traffic and cleanup before the final Level 3 Gate.

The exact checkpoint-4 product manifest is forty-four paths: the existing CI
workflow; two translation CSVs; P8-01 projection repository/response;
quality-link repository/API; OpenAPI; projection and formal-quality browser
data sources; generated catalog; one inspector; existing Trial quality and
readiness workspaces and style sheet; P7-03/P7-05 and P8-06 E2E plus their
exact nine Linux baselines; two fixtures; five focused frontend unit tests;
the runtime shell and verifier; and nine focused projection/quality-link
backend/runtime tests. `implementation/CURRENT_TASK.json` enumerates every
path without wildcard. No BFF route, integration event, metadata, migration,
Outbox, worker, adapter, target client, Darwin baseline or threshold is in the
manifest.

Changed-files-to-tests must prove strict shapes, Project containment, query
and source capability intersection, exact candidate/head binding, all named
states, one Impact Review, replay, no-leak errors, no browser target network,
three-language completeness, keyboard/axe/responsive behavior, affected nine
Linux baselines, the complete governed visual matrix and disposable runtime
through P8-06. Item, MBOM, Tool Asset, P8-01 and P7 regressions, security
scans, current/reconciliation units and exact manifest/diff remain mandatory.

Before UI exposure, rollback reverts the exact forty-four checkpoint-4 paths.
After link history or client observation exists, disable the inspector/action
through a reviewed forward fix while retaining every immutable link revision,
head, receipt, audit and P8-01 observation. Never delete or retarget history,
reinterpret raw codes, change P7 readiness/Gate truth or contact ERPNext.
Product work starts only after this governance transition passes exact-SHA
ordinary CI.

## 21. Checkpoint-4 same-cycle harness remediation

Checkpoint-4 product SHA `0bc2687f9541fb14fa348614c16968c182aafcbb`
reached ordinary CI `32983850058`. Repository `98227122886`, frontend
`98227123050` and governed visual `98227123047` identify harness contracts
that predate the accepted checkpoint-4 surface; secret scanning passes and
there is no product root.

The bounded exact-fourteen changed-path remediation preserves all product
semantics:

- three runtime tests keep every historical P8-03/P8-04/P8-05 assertion and
  update only the current P8-06 scope and P8-05 predecessor contract;
- one readiness unit test awaits the exact asynchronously loaded empty result
  and proves one exact source-bound load;
- one current-task verifier assertion pins the resulting legal allowlist
  cardinality while retaining every negative manifest check;
- P7-04 and P7-07 mock the exact formal-quality collection plus the exact
  `kind=formal_quality_status` projection request, then wait for the terminal
  inspector before scrolling; and
- all six corresponding Linux Bookworm/x64 cases are exercised after
  text/layout-only manual review, two focused no-update passes and the full
  governed 132-case no-update matrix. Only P7-04 Traditional Chinese and
  P7-07 English/Simplified Chinese require file changes; P7-04 English/
  Simplified Chinese and P7-07 Traditional Chinese are bit-identical to their
  existing canonical files once the terminal gate is applied.

The remaining four changed paths are this plan, checkpoint evidence,
controller and CURRENT_TASK. No product, workflow, API, permission, route, translation,
threshold or Darwin baseline changes. Run `32983850058` is not rerun; the
repair requires a new exact-SHA ordinary PASS before one Level-3 execution.

## 22. Independent prepare-projection substage diagnostic

Exact checkpoint `71b3ee9276c6078175682ffdc7528e84ccdc7249`
passes ordinary CI `32994361662`. Its sole controlled diagnostic run
`32995898417` reaches runtime job `98265034895` and emits only
`P806_QUALITY_PREPARE_PROJECTION / RuntimeError /
trace-d41bef28f3675f2287359d7258a83015`. The previous runtime-stage cycle is
immutable at diagnostic `1/1`, repair `0/1`, final `0/1`.

The tuple is the parent Bench return-code guard and therefore cannot select a
child first source. The independent
`p8-06-quality-link-prepare-projection` cycle starts at diagnostic `0/1`,
repair `0/1`, final `0/1`. It disables the previous activation and enables one
exact environment-gated child scope only. Four ordered parent stages cover
spawn, child status, result parse and result shape. Thirty-nine unique
child/repository stages cover Site setup, actor, principal, target/result,
Readiness containment, head/event/replay/classification/freshness, immutable
observation/head values, transaction writes, audit, collection, commit and
response.

The existing safe diagnostic logger receives only code, exception class and
the exact trace. The parent snapshots controlled log cursors, accepts only one
logical exact-three-key mirrored record, prefers that trusted child tuple and
otherwise uses one fixed parent fallback. Duplicate, malformed, unknown or
wrong-trace records yield no server tuple. The child subprocess retains
`stderr=DEVNULL`; nonzero child stdout is never sought or read. One record,
innermost-wins, same-exception and finally rules apply. Default execution has
no scope and no record. No projection value, validation, permission,
transaction, write order, API response, rollback or cleanup semantics change.

The exact eight paths are the projection Frappe repository, the quality-link
runtime verifier and cumulative shell, their two focused tests, this plan,
the checkpoint evidence and `implementation/AUTOPILOT_CONTROLLER.md`. The
cycle adds no controller predicate instrumentation in advance. A later exact
insert/save predicate checkpoint is permitted only if this one uniquely stops
at such a boundary without identifying the controller predicate.

## 23. Independent prepare-projection bootstrap diagnostic

Exact prepare-projection SHA
`cf4f431e4ca3d74f50716bfbaa8e7c2d66e3d83e` passes ordinary CI
`32998865737`. Its one controlled run `33000193191` passes preflight
`98279700208`; runtime `98279799344` emits only
`P806_QUALITY_PREPARE_PARENT_CHILD_STATUS / RuntimeError /
trace-9996bb78f674578fae7afed049451082`. No child output, business value, ID,
message or stack was read.

Static cross-proof proves the absent server tuple is a harness lifecycle
blind spot. `run_local_bench_fixture` enters the repository diagnostic scope
before `frappe.init`, while pinned Frappe creates `local.flags` only during
init. The first diagnostic `getattr(frappe.flags, ...)` therefore raises on
the unbound Werkzeug local proxy and the response-neutral context yields
without state. The prior fake test supplied a flags object in advance. This
uniquely explains why every child/repository stage was dormant, but it does
not select the underlying product failure.

Freeze `p8-06-quality-link-prepare-projection` at diagnostic `1/1`, repair
`0/1`, final `0/1`. The independent harness-only
`p8-06-quality-link-prepare-bootstrap` cycle starts diagnostic `0/1`, repair
`0/1`, final `0/1`. Its exact-five paths are this plan, the checkpoint
evidence, `implementation/AUTOPILOT_CONTROLLER.md`,
`scripts/verify_quality_link_runtime.py` and
`tests/test_phase8_quality_link_runtime_verifier.py`.

The old activation is false and one new activation is true. A verifier-owned
exact-scope context records only five pre-context stages: Frappe import,
repository import, exact argument validation, `frappe.init` and active
repository-context proof. It uses the existing O_EXCL exact-three-key file,
same exception and finally rules. Only after init succeeds does the existing
repository context begin. No coarse verifier stage encloses later product
work, so the existing thirty-nine server stages remain innermost and the
strict mirrored reader still wins for post-context failures. Failed-child
stdout/stderr remain unread; malformed, duplicate, wrong-scope or wrong-trace
records remain fail-closed.

Changed-files-to-tests must prove fresh unbound flags, init-before-context,
pre-init exact3 recording, active-context shape, old-off/new-only mutual
exclusion, exact lexical allowlists, server-inner preference, strict reader,
default-off/no-leak and unchanged cleanup. Full affected quality-link,
projection, P7 and integration security regressions, current/reconciliation,
Python compilation, direct-SQL/network scans, diff hygiene and an exact-five
manifest with an unauthorized sixth path rejected remain required.

This cycle changes no product/app repository, shell, route, API, metadata,
migration, permission, transaction, projection value, UI, target, external
network or portal decision. The separately requested production read-only
fact audit and final-DoD documentation remain queued under current production
access prohibitions and are not included.

Level 1 passes focused bootstrap/projection `25/25`, complete affected
quality-link/projection/P7/Item/MBOM/Tool Asset `297/297`, full repository
Python `2528/2528` and current/reconciliation `36/36`. Current-task and both
reconciliation scripts, compilation, shell syntax, exact activation,
direct-SQL/network/leak scans and diff hygiene pass. The exact-five manifest
and simulated base-to-tip union are accepted; a synthetic unauthorized sixth
path is rejected fail-closed.

## 24. Same-cycle P7-05 loading-harness remediation

Prepare-bootstrap SHA `9b5e092e70506a0f4739f92359c845829e23807f`
reaches ordinary `33002560114`. Repository `98287882871`, secret scan
`98287882833` and visual `98287882946` pass; frontend `98287882578` passes
`454/455` E2E cases and fails only the unchanged P7-05 readiness loading
locator. The exact-five prepare-bootstrap diff has no frontend path, and the
controlled diagnostic is not dispatched.

The fixture's fixed 450 ms response delay begins at route interception and can
expire before a loaded CI worker mounts React's loading state. This is the
same deterministic race already governed for the P8-01 projection fixture.
The minimal same-cycle remediation replaces only that delay with an explicit
pending Promise, starts navigation, asserts loading while the response is
provably pending, releases it in `finally`, and then asserts the loaded
summary. It changes no product, response, route, timeout, retry, visual
baseline, threshold or diagnostic counter. CURRENT_TASK already allows the
P7-05 test and all three governance paths, so no manifest expansion is needed.

Level 1 passes five consecutive complete P7-05 nonvisual repetitions
(`50/50`), all five affected P7/P8-06 nonvisual specs (`33/33`), the five
affected unit files (`68/68`), frontend generate/format/lint/type checks,
current/reconciliation (`36/36`) and diff hygiene. The exact-four manifest is
accepted and a synthetic unauthorized fifth path is rejected. Product, app,
API, contract and visual-baseline diffs remain zero.

## 25. Prepare-bootstrap projection-support repair

Exact harness SHA `0534f5152e1c1e071aff42f56d7159edbc70c8b2`
passes ordinary `33004880719`. The sole controlled diagnostic
`33006282463` passes preflight `98300758405`; runtime `98300904817` exposes
only `P806_QUALITY_PROJECTION_OBSERVATION_INSERT / PermissionError /
trace-5f2cdd805fd15e1b8f9458abaa566e69`. Failed-child output, business values,
IDs, messages and stacks remain unread.

The ordered stage proves the exact non-Administrator runtime actor already
passed Project-first authorization, source/result validation, Readiness
containment and immutable projection value construction, then failed at the
Observation insert. Existing request-local write flags do not confer Frappe
DocType permission. The actor has `NPI API User`, while Observation and Head
metadata intentionally grant no create/write permission. Audit Event remains
role-permitted. This uniquely selects the missing bounded service capability;
it does not authorize fixture elevation or metadata permission expansion.

The exact-eleven repair introduces a frozen capability containing the exact
session actor and exact allowed operations: Observation insert, Head insert
and Head save. Entry rejects empty, trimmed, Guest, Administrator, session-
mismatched or non-`NPI API User` actors. Each helper revalidates the active
request-local capability, actor, DocType, action and matching existing write
flag before the only two pinned permission-bypass call sites. Capability and
flags are restored in `finally`. Audit keeps its ordinary insert; Project
scope, ownership, source/result values, optimistic head rules, transaction,
write order, hooks, API response and rollback do not change.

Changed-files-to-tests require repository lifecycle and failure injection,
forged/wrong-actor/role/action/DocType/session/exception cases, the full-app
permission AST scanner with exactly nine controlled calls, runtime default-off
and dormant reader coverage, current-task legal-cardinality regression, full
projection/quality-link/P7/Item/MBOM/Tool Asset affected tests, compilation,
shell syntax, security scans, current/reconciliation and an exact-eleven
manifest with an unauthorized twelfth path rejected.

Level 1 passes focused capability/security/runtime/current `38/38`, complete
affected projection/quality-link/P7/Item/MBOM/Tool Asset `310/310`, full
repository Python `2530/2530` and current/reconciliation `36/36`. Current and
both reconciliation scripts, compilation, shell syntax, exact diagnostics-off,
direct-SQL/network scans, JSON validation and diff hygiene pass. The exact-
eleven task manifest and 65-path post-commit union pass; a synthetic
unauthorized twelfth path is rejected fail-closed.

The prepare-bootstrap cycle is diagnostic `1/1`, repair `1/1`, final `0/1`.
All diagnostic flags are false. FR-CO-003/004 deferral, all ERPNext/Sandbox/
production and approval holds, raw-code-no-pass behavior and every B/C hold
remain unchanged. The separate production read-only fact/DoD governance task
remains queued and outside this repair.

## 26. Independent post-permission runtime diagnostic

Exact projection-support repair SHA
`88716e48972f16064c56f60ca067845b7df0f681` passes ordinary CI
`33008613712`. Its sole Level-3 run `33009962578` passes repository, secret,
frontend, governed visual and controlled preflight, then runtime job
`98317534667` fails at the cumulative P5-through-P8-06 verification boundary.
Failed-child output, business values, IDs, messages and stacks remain unread.

The prior exact tuple proved every ordered prepare stage through transaction
entry and selected only Observation insert permission enforcement. The repair
now binds the same retained Readiness actor and active Frappe session to a
request-local capability, requires `NPI API User`, and allows only Observation
insert and Head insert/save through the two pinned permission helpers. This
closes that exact PermissionError root. It does not prove which later or
non-permission predicate failed in the new Level-3 run. Remaining independent
boundaries include Observation lifecycle validation, Head persistence, Audit,
outcome, collection, commit/response, current truth, create/replay/stale/list
and cleanup. Selecting any product repair would be speculative.

Freeze `p8-06-quality-link-prepare-bootstrap` at diagnostic `1/1`, repair
`1/1`, final `1/1`. Independent
`p8-06-quality-link-post-permission` starts diagnostic `0/1`, repair `0/1`,
final `0/1`. Runtime-stage, prepare-projection and prepare-bootstrap flags are
false; only the post-permission verifier flag is true. Its active allowlist is
exactly sixty unique stages: seventeen cumulative runtime stages, four
prepare-parent stages and thirty-nine repository/server stages. Bootstrap's
five historical stages are excluded from this cycle.

The cycle reuses the deterministic trace, exact path, O_EXCL exact-three-key
record, pre-child log cursors and strict mirrored reader. One valid server
tuple wins over the parent fallback. Duplicate, malformed, unknown or
wrong-trace data is rejected. The same exception is re-raised, `finally` is
preserved, nonzero child stdout/stderr are never read and only a successful
child result is parsed. Dormant execution creates no record and changes no
behavior.

The exact-five paths are this plan, the checkpoint evidence,
`implementation/AUTOPILOT_CONTROLLER.md`,
`scripts/verify_quality_link_runtime.py` and
`tests/test_phase8_quality_link_runtime_verifier.py`. Changed-files-to-tests
must cover flag mutual exclusion, exact-sixty AST/lexical equality, scope,
trace, cursor, server-win, parent fallback, innermost one-record behavior,
same-exception/finally, malformed/missing/duplicate/wrong-trace rejection,
no-leak, success and dormant paths. Full affected projection/quality-link/P7
and Item/MBOM/Tool Asset regressions, current/reconciliation, compilation,
shell syntax, security scans, diff hygiene and exact-five manifest with an
unauthorized sixth path rejected remain required.

This is verifier/evidence only. Product, API, schema, permission, transaction,
ownership, migration, UI, translation, visual, target-network, FR-CO-003/004
deferral and B/C holds do not change. Production read-only fact gathering and
final-DoD documentation remain queued outside this exact-SHA chain.

Level 1 passes focused runtime `18/18`, complete affected P8-06/P8-01/P7 and
Item/MBOM/Tool Asset `300/300`, full repository Python `2531/2531` and
current/reconciliation `36/36`. Current and reconciliation scripts,
compilation, shell syntax, exact activation, strict-reader/no-leak checks,
product-zero-diff and diff hygiene pass. The exact-five manifest is accepted
and an unauthorized sixth path is rejected.

## 27. Independent P8-01 projection-fresh predecessor diagnostic

Post-permission checkpoint `9853c23208305e4ece10e38749896bd90297127f`
passes ordinary `33012596539`. Controlled run `33013828908` passes preflight
`98326755117`; runtime `98326824448` contains no P8-06 tuple. Whitelist-only
inspection of fixed shell labels identifies the unique P8-01 fresh projection
failure branch. That branch exits before formal-quality verification and all
P8-02/Item/MBOM/Tool Asset downstream work. The post-permission cycle therefore
remains `0/1`, `0/1`, `0/1`; no quality-link product inference is permitted.

The independent `p8-01-projection-fresh-predecessor` cycle starts at
diagnostic `0/1`, repair `0/1`, final `0/1`. Sixteen ordered verifier-owned
codes cover bootstrap/login/CSRF, retained context, seed spawn/status/parse/
shape, collection and kind closure, invalid-query and guest authorization,
internal/external access and cleanup, and Tooling consumers. Its exact scope,
deterministic trace, O_EXCL exact-three-key file and strict reader admit only
one code/type/trace tuple. Failed Bench child stderr is discarded and stdout
is never read; successful child JSON alone is parsed. Default/no-scope paths
remain behaviorally dormant and successful diagnostics produce no record.

The exact-eight governed paths are `scripts/verify_projection_runtime.py`,
`scripts/verify-frappe-runtime.sh`,
`tests/test_phase8_projection_runtime_verifier.py`,
`implementation/CURRENT_TASK.json`, `tests/test_current_task_verifier.py`,
this plan, the checkpoint evidence and `implementation/AUTOPILOT_CONTROLLER.md`.
The manifest adds only the two exact projection verifier/test paths and their
focused/runtime-preflight commands; it adds no pattern or product path.
Product semantics, repositories, APIs, permissions, transaction order,
projection truth, target traffic, UI, FR-CO-003/004 deferral and all B/C holds
remain unchanged. Production read-only fact/DoD governance remains queued.

Level 1 passes focused projection/current `23/23`, complete affected P8-01/
P8-06/P7 and Item/MBOM/Tool Asset `316/316`, full repository Python
`2536/2536` and current/reconciliation `36/36`. Current/reconciliation scripts,
generated-source check, compile, shell syntax, exact lexical stages, strict
reader/no-leak checks and diff hygiene pass. The exact-eight post-commit union
manifest is accepted and an unauthorized ninth path is rejected; product/app
diff is zero.
