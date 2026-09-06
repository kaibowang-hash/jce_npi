# P5-03 Baseline and Impact Invalidation Plan

Recorded: `2026-07-31T20:25:22Z`

Status:
`PASS — BOUNDED REQUIREMENT/DOMAIN AUDIT; DOMAIN/METADATA FOUNDATION ACTIVE`

Task:
`P5-03 — Baseline and impact invalidation`

Requirement:
`FR-DS-006`

## 1. Scope and authority

P5-03 delivers one generic NPI-owned technical mechanism:

1. an exact Project-scoped policy that explicitly binds who may create a
   release package/baseline;
2. an immutable package containing server-resolved released Document Revision,
   File Revision and hash snapshots;
3. exact baseline attachment through the existing Gate evidence boundary;
4. dependency registration only for the members of that explicit attachment;
5. append-only old/new impact lineage when a registered input gains an exact
   successor; and
6. existing Gate Review invalidation and successor-cycle resolution without
   rewriting the baseline, evidence reference or prior decision.

The standing V1.2 automatic-transition authority covers this bounded task.
The Phase 5 anchor expressly authorizes generic immutable baselines with
synthetic fixtures and explicit dependency registrations while production
rules remain unavailable. No new business decision is invented.

## 2. Sources audited

- `FR-DS-006` in `docs/DETAILED_REQUIREMENTS.md`;
- `implementation/phase-5-requirement-anchor.md` sections 2, 3.1, 3.3, 4,
  6 and 7;
- `implementation/REQUIRED_INPUTS.md` section 3;
- passed P5-01 and P5-02 evidence;
- P5-01 Document Revision/File association and successor transaction;
- P5-02 lifecycle, release snapshot, confirmation and released-File guard;
- Phase 4 Gate Template, Gate Evidence and Gate Review domain/repository/API,
  exact evidence reference DocType and dependency refresh path;
- `contracts/npi-api.openapi.yaml` and `contracts/data-ownership.yaml`;
- Project Documents and Gate workspace data sources/UI; and
- applicable repository discovery, domain, safe-change, industrial UX and
  i18n constraints.

## 3. Repository facts

### Existing exact inputs

- `NPI Document Revision` supplies immutable revision identity, predecessor,
  canonical snapshot and hash.
- `NPI Document Revision File` supplies the exact revision-to-File Revision
  association; its File Revision namespace is distinct from the Controlled
  Document namespace.
- `NPI Document Revision Lifecycle` and its release event supply exact current
  `released` state, lifecycle version and release snapshot hash.
- P5-02 release revalidates the live private File identity, bytes, length,
  SHA-256, MIME and scanner-owned `clean` state and marks the exact File
  Revision released once.
- The Frappe `File.on_trash` guard retains the physical released binary.

### Existing Gate boundary

- `NPI Gate Evidence Reference` is append-only, exact-version/hash based and
  never exposes a raw URL.
- Gate Templates currently publish only `wbs_item` and `file_revision` kinds.
- Gate evidence attachment currently freezes an exact source snapshot and
  refreshes the current Gate Review when its input hash changes.
- Gate Review already owns the closed `active/decided/invalidated/superseded`
  cycle history, `requires_review` projection, frozen authority bindings,
  immutable decisions and old/new input hashes.

### Confirmed gaps

- There is no document release-package/baseline aggregate, member record,
  baseline policy, baseline command receipt, Gate dependency or baseline
  impact event.
- `NPI WBS Plan Baseline` is a Project scheduling snapshot and is not a design
  release package; it must not be reused or relabelled.
- The existing ControlledDocument `baseline_membership` ownership row is only
  an unimplemented placeholder.
- No OpenAPI route/schema, UI capability or runtime proof exists for a document
  baseline.
- The repository contains no approved production baseline contents/authority,
  replacement/retention rules or complete dependency matrix.

## 4. Frozen domain design

### 4.1 Exact policy

Add `DocumentBaselinePolicy` and immutable
`DocumentBaselinePolicyVersion` values/DocTypes.

- The root provides only stable Project-scoped policy identity/title/enabled
  administration.
- A version is `draft` or publish-once `published` and freezes exact
  `baselineAuthorityUserIds` plus a canonical snapshot/hash.
- Publication installs no default record. Tests and controlled runtime use
  namespaced synthetic policies only.
- Baseline authority is not derived from Project ownership, RACI,
  `System Manager`, assignment, release authority, transport role or UI state.
- The actor must additionally be an enabled internal current Project member
  and hold the existing normal-user command transport role.

No production baseline contents, Gate mapping, quorum, signature,
replacement, effectivity or retention rule is encoded in this policy.

### 4.2 Immutable package

Add `DocumentBaseline` and `DocumentBaselineMember` values/DocTypes.

- A create command supplies a bounded ordered set of exact revision IDs,
  expected lifecycle versions and expected release snapshot hashes.
- The server authorizes before protected resolution and locks the Project and
  exact inputs.
- Each input must be same-tenant/same-Project, currently exactly `released`,
  bound to the expected P5-02 release event/snapshot and have at least one
  exact Document Revision File association.
- Every associated File Revision is server-resolved and revalidated for exact
  live private identity, released flag, bytes, length, SHA-256, MIME and
  scanner-owned `clean` truth. The caller cannot select scan state, file URL or
  a partial association snapshot.
- Duplicate revision identities and empty/oversized sets fail closed.
- The member snapshot freezes document/revision identity and revision hash,
  lifecycle/release identity/hash and a sorted complete File Revision/hash
  array.
- The baseline snapshot freezes the exact policy reference, ordered members,
  actor, time, request and trace and is canonically SHA-256 hashed.
- Baseline/member records are append-only, non-renamable and non-deletable.
  A later revision creates no mutation of their snapshot.

### 4.3 Actor-bound idempotency and transaction

Add an independent `BaselineCommandIdempotency` receipt because baseline
creation has no pre-existing Document identity and must not misuse a Document,
Gate or Project receipt namespace.

The exact create transaction is:

1. authenticate, authorize Project view/command transport and exact policy;
2. lock Project, input revisions/lifecycles/associations/File Revisions and
   check replay/payload conflict;
3. revalidate exact release and live private-file truth;
4. insert an unsealed actor/Project/operation/payload receipt;
5. insert the immutable baseline and ordered members;
6. append one audit event;
7. build the authoritative response; and
8. seal the receipt last.

Any failure rolls back every baseline, member, audit and receipt. No external
request occurs.

### 4.4 Exact Gate evidence and dependency registration

Add `release_baseline` as a new publishable Gate evidence kind without changing
historical template snapshots.

- A new Gate Template may explicitly allow the kind; no existing or production
  template is rewritten or installed.
- The attach request remains the existing strict exact-source command and must
  provide baseline global ID, immutable source version `1` and snapshot hash.
- The server revalidates the same tenant/Project baseline, canonical snapshot,
  member rows and hash before appending the existing exact Gate evidence row.
- The response contains safe baseline/member identity/hash metadata only.
- In the same Gate attach transaction, append one
  `BaselineGateDependency` per exact baseline member. Each row freezes the
  input revision/hash, affected baseline/hash, Gate/requirement/evidence
  identities, actor/time/request/trace and a deterministic key.
- Gate evidence authority remains independent from baseline creation
  authority. Generic CRUD, raw URLs and caller-selected dependency targets are
  rejected.

### 4.5 Successor impact and existing review resolution

Add append-only `BaselineImpactEvent` records and a private successor hook.

- The hook runs only after an exact new Document Revision and its complete File
  association exist in the existing atomic successor transaction.
- It selects only same-tenant/same-Project dependency rows whose exact input is
  the declared predecessor revision. No filename, type, screenshot, sample or
  inferred relationship is consulted.
- One deterministic event per dependency/new revision freezes old/new revision
  IDs and snapshot hashes, affected baseline/hash, Gate/requirement/evidence
  IDs, actor/time/request/trace and canonical event hash.
- The event is included in the current Gate input/dependency-change snapshot.
  The already locked Gate is refreshed through the private existing Gate Review
  dependency capability.
- An active/decided review therefore follows its existing invalidation,
  `requires_review`, immutable prior-cycle and successor-cycle rules. A Gate
  without a review records visible impact for its future review input but does
  not invent a decision.
- Review decision under the already frozen Gate policy is the owning resolution
  path. P5-03 adds no second impact status, waiver, role or replacement rule.

If any impact insert, Gate input refresh, review event, audit or downstream
response fails, the entire new revision transaction rolls back, including its
private File, File Revision and association under the existing cleanup guard.

## 5. API and UI boundary

Planned normal-user BFF routes:

- `GET /api/npi/v1/projects/{projectId}/document-baselines`;
- `POST /api/npi/v1/projects/{projectId}/document-baselines`.

The GET response returns exact baselines/members, available exact published
synthetic policies, impact rows and server capability truth. The POST command
requires trusted CSRF, actor-bound idempotency and a closed body containing
label, exact policy reference and exact released-revision preconditions.

The existing Gate evidence attach route gains only the closed
`release_baseline` source kind. The Project Documents workspace gains a dense
baseline table and released-revision selection; the Gate workspace gains the
exact baseline source option and visible impact lineage. Every write reloads
authoritative state and covers processing, stale/conflict, permission,
integrity, replay uncertainty, retryable/final failure and success.

All user-visible sources remain literal English through the local Frappe
catalog/React `t()` chain with direct `zh` and `zh-TW`. The affected screens
retain square controls, dense tables, stable toolbars/inspectors, one primary
action, translated accessible names, keyboard/focus paths and text-plus-shape
status. Exact trilingual visuals are required.

## 6. Ownership

- Baseline policy identity/drafts: `NPI_ONE_ADMIN`.
- Published exact baseline policy: `VERSIONED_DOCUMENT_BASELINE_POLICY`.
- Baseline command and actor-bound receipt: `NPI_ONE_DOCUMENT_BASELINE_COMMAND`.
- Canonical membership/snapshot/hash: `NPI_ONE_RULE_ENGINE`.
- Gate evidence reference/registration: existing `NPI_ONE_GATE_EVIDENCE_COMMAND`.
- Impact event generation: private `NPI_ONE_BASELINE_DEPENDENCY_SYSTEM`.
- Review invalidation/resolution: existing versioned Gate Review policy and
  private dependency capability.
- ERPNext/CAD/PDM: no ownership or connection change.

## 7. Held facts and non-scope

The following remain unavailable rather than guessed:

- production baseline authority, contents for G2/G5/G6/ECN, naming/numbering,
  replacement, effectivity, retention and destruction;
- complete Project/product/part/Tooling/Trial/quality/change dependency matrix;
- automatic dependency inference or completeness claims;
- external baseline sharing/retrieval, production scanner/viewer or CAD/PDM;
- EBOM revision/comparison (`P5-04`);
- formal Item/MBOM publish request or ERP success (`P5-05`/Phase 8); and
- production ERPNext endpoints, credentials or data.

## 8. Expected change surface

Planned additive product files include:

- new baseline domain/Frappe/repository modules;
- seven guarded DocTypes: policy root/version, baseline/member, command receipt,
  Gate dependency and impact event;
- controlled-write/delete guards and hooks;
- `document_api.py`, `bff.py`, OpenAPI and data ownership;
- Gate Template/Evidence/Review exact-source extensions;
- the existing successor transaction hook with one closed impact stage;
- Project Documents and Gate workspace data sources/UI/styles/translations;
- focused domain/metadata/repository/API/contract/controller/runtime/browser/
  visual/reconciliation tests; and
- P5-03 evidence/controller documents.

No new production dependency, core patch, direct SQL, cross-database write,
raw private URL, external request, credential, destructive migration or normal
user Desk workflow is authorized.

## 9. Changed-files to affected-tests

| Change boundary | Required checks |
|---|---|
| Baseline domain and policy | deterministic hash/order, policy publication, exact actor, duplicate/limit/state/hash/tamper tests |
| DocTypes and guards | JSON shape, permissions, command flags, immutable update/delete, association and canonical-snapshot tests |
| Repository/BFF/OpenAPI | authorization-before-resolution, CSRF, exact fields, replay/conflict, stale lifecycle, transaction rollback, route switch and contract tests |
| Gate evidence kind/resolver | old-template compatibility, exact baseline snapshot, wrong Project/hash/version, duplicate reference and dependency-row rollback tests |
| Successor impact | unregistered no-op, exact predecessor only, deterministic dedupe, old/new lineage, Gate review invalidation/successor cycle and full rollback tests |
| UI/i18n | unit/component, non-normal states, accessibility, mixed-language, direct catalog coverage and trilingual browser/visual cases |
| Runtime | two migrations, synthetic policy, released inputs, baseline replay/conflict, Gate attach, registered/unregistered successors, impact/review lineage, route recovery, cross-process replay and cleanup |

## 10. Gate strategy

- Level 1 after domain/metadata and after each bounded repair batch.
- Level 2 after the complete P5-03 vertical slice: focused module suites,
  affected API/permission/integration/E2E/i18n/visual/runtime, exact
  `FR-DS-006` trace, Task Diff Review and all acceptance criteria.
- Complete ordinary CI on the exact product candidate.
- One final controlled-Site workflow only after ordinary CI passes.
- No Phase 5 Level 3 Gate until P5-05 completes the Phase boundary.

The controller has four completed uniquely proved product-root repairs out of
five. Environment/bootstrap/verifier/synthetic-precondition corrections remain
fail-closed but are not product-root rounds. Any product repair must be based
on a unique root and batched through affected checks before another full Gate.

## 11. Rollback

Before retained P5-03 history exists, remove the additive DocTypes/routes and
restore the checkpoint parent. After any baseline, member, Gate reference,
dependency, impact event, review history, audit or receipt is retained, never
delete or rewrite it. Activate an independent `npi_p5_03_routes_disabled`
switch, fail baseline creation/attachment/use closed, preserve P5-01/P5-02
reads and deploy a reviewed forward fix. Production ERPNext remains unaffected
because no production connection is permitted.

## 12. Audit decision

The bounded audit is `PASS`. `FR-DS-006` advances from `ANCHORED_P5_03` to
`IN_PROGRESS_P5_03_PLANNED`. The only active implementation stage is the
domain/metadata foundation; repository, API, Gate integration, successor hook
and UI remain inactive until that focused checkpoint passes.
