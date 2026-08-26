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
