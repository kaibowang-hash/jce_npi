# P7-05 Plan — Versioned NPI Readiness and Dominant Blockers

Recorded: `2026-08-11`

Status: `FROZEN — CHECKPOINT 1 AUTHORIZED`

Starting controller checkpoint:
`81b720487cface6ca78a9e77724223e61c766871`

Retained product checkpoint:
`02781c0c712c4d8c739114ead24545daa537329d`

Primary requirements:

- `FR-NP-001` through `FR-NP-003`;
- `FR-NP-006` through `FR-NP-013`.

Retained foundations:

- `FR-NP-004` and `FR-NP-005` from P7-02; and
- exact Project, Gate, Work Item, controlled-document, Tooling/capacity and
  P7-01 through P7-04 Trial facts.

## 1. Audit decision

The bounded Requirement/domain/existing-capability audit is complete. Exact
controller SHA `81b7204` passes ordinary PR CI `31491185573`: repository
`93777828829`, frontend/E2E `93777828858`, secret scan `93777829035` and the
unchanged `106/106` fixed-Linux visual matrix in `93777828744` all pass; the
controlled lanes skip as required for a controller-only transition. P7-05 can
proceed without inventing a production business rule because every
customer/industry applicability, score weight, evidence requirement, blocking
level and Gate target is explicit versioned configuration, and metadata
installs no default template, policy, authority or business row.

There is no live NPI readiness aggregate, DocType or BFF in the repository.
The `62%` value in the deterministic Project demo and the informational Gate
page are prototype copy only and are zero reusable backend capability. They
must not be read, migrated or treated as evidence.

Reusable exact facts are:

- immutable Project type/template/references and Project members;
- frozen Gate instances, requirements, exact evidence, review-input blockers
  and versioned Gate Review policy/decision behavior;
- versioned Domain Work Items and exact owner/due/state/blocking facts;
- immutable Released Documents and baselines;
- Tooling process/capacity scenario revisions, including explicit OEE, yield,
  cycle, cavity and demand assumptions;
- exact Trial input, Actual, Sample, cavity, defect/action/verification,
  comparison, controlled-reference and conclusion revisions; and
- clean private File Revisions and audited content access.

Those sources do not create formal ERP material/specification mappings,
Quality Inspection/NCR truth, production Run-at-rate actuals, HR qualification
records or formal supplier execution. Those projections remain explicit
`unavailable`. Tooling capacity is a governed scenario, not Run-at-rate actual.
NPI controlled evidence is not ERP approval.

The current Project aggregate has no governed industry field. P7-05 therefore
freezes an NPI-owned `industryKey` in the Project readiness instance context,
entered only by an authorized internal administrator and never represented as
ERP customer-master truth. Customer applicability resolves only against an
exact Customer reference already frozen on the Project. Changing project type,
customer applicability or industry classification requires a new readiness
instance; it never rewrites retained history.

## 2. Frozen outcome

P7-05 delivers one minimum complete vertical slice:

> publish one immutable readiness-template version with explicit Project-type,
> customer and industry selectors, categories, item weights, evidence/source
> rules, blocking levels and Gate keys -> initialize one Project instance from
> that exact version and freeze the Project/context/Gate/item identities ->
> append immutable item successors for owner, due date, progress, confirmation
> values and exact evidence references -> resolve every supported source on the
> server and mark missing formal sources unavailable -> derive category/total
> scores from exact applicable weights -> keep every applicable incomplete P0
> or failed mandatory result as a separately visible active blocker regardless
> of score -> supply those blockers and the exact readiness revision as input to
> the existing independently authorized Gate review without changing the Gate
> -> reconstruct the same dense English/zh/zh-TW Project workspace from the
> retained revision without latest-value substitution

P7-05 owns the versioned NPI checklist, Project readiness instance and derived
NPI score/blocker truth. It creates no ERP master/quality/production/HR/
supplier result, Gate decision, Gate close, Work Item close, project risk,
Tooling lifecycle change, production handover, external event, released Trial
Summary or print output.

## 3. Domain invariants

### 3.1 Immutable reusable template and independent Project instance

- `NpiReadinessTemplateVersion` has a stable template UUID, positive template
  version, immutable published canonical snapshot/hash and explicit Project
  type, optional exact Customer-reference and industry-key selectors.
- The template contains ordered categories and ordered item definitions. Every
  item has a stable key/title source, positive integer weight, explicit
  applicability selector, blocking level, exact Gate key, allowed source/
  evidence kinds and completion rule. PFMEA, Control Plan, MSA, CPK, PPAP and
  other industry deliverables are ordinary configured item definitions, never
  global hard-coded requirements.
- Drafts may be edited only by creating the exact next optimistic draft state;
  a published version is immutable. A later template change creates a new
  version and never changes a Project instance.
- `NpiReadinessInstanceRevision` is an append-only stream with one stable
  instance UUID and immutable revision UUIDs. Revision 1 freezes the exact
  Project identity/version/type/references, NPI-owned industry key, published
  template version/hash, resolved Gate identities and all item/category
  definitions. It does not point to a latest template.
- Item identity is deterministic inside the instance. Every successor preserves
  category, weight, applicability, blocking level and Gate identity; owner,
  due date, status, confirmation and evidence changes require the exact current
  instance revision/hash and append a full successor.

### 3.2 Exact item status, evidence and unavailable truth

- The closed item states are `not_started`, `in_progress`, `complete`,
  `failed` and `not_applicable`. `not_applicable` is derived from the frozen
  applicability selector, not selected later to suppress a blocker.
- Owner resolves to one enabled same-Project member. Due date and owner remain
  explicit even when evidence is unavailable. The browser cannot submit an
  arbitrary user, score, blocker flag or translated status.
- Completion rules are closed and versioned. A confirmation item requires a
  retained normalized NPI confirmation plus its required exact evidence; a
  source-result item requires an exact supported source identity/version/hash
  and acceptable server-resolved disposition. Missing, drifted, unsafe or
  unsupported mandatory evidence cannot complete an item.
- Supported exact NPI sources are bounded to Project/Work Item, Released
  Document/Baseline, clean private File Revision, Tooling capacity scenario and
  the retained Trial input/Actual/Sample/cavity/defect/action/verification/
  comparison/reference/conclusion revisions. Every source is reauthorized,
  checked for same Project/tenant containment and re-resolved by exact version
  and hash. A filename, raw URL or latest pointer is never evidence.
- Formal ERP material/specification mapping, Quality Inspection/NCR result,
  Run-at-rate/production actual, HR qualification and supplier execution are
  read-only provider kinds. Until Phase 8 supplies an approved provider they
  return `unavailable`, accept no caller status and perform no network call.
- A controlled quality report can satisfy its configured NPI evidence rule,
  but it is labeled `controlled_report`, not ERP formal quality. A failed
  exact quality-result source is always incomplete and blocking when applicable.

### 3.3 Deterministic score and blocker dominance

- An applicable complete item earns its frozen positive integer weight; every
  other applicable state earns zero. Non-applicable items are excluded from
  the denominator. Category score and total score are deterministic integer
  basis points derived from exact earned/applicable weights with one fixed
  `readiness-score.v1` formula and half-even rounding.
- The snapshot returns numerator, denominator, basis points and textual state
  for every category and total. A zero-denominator category is `not_applicable`,
  not `100%`. The browser never sends or overrides score values.
- Every applicable P0 item not `complete`, every failed mandatory quality
  result and every template-defined mandatory unavailable source is an active
  blocker. Blocker rows remain separately identified with item, reason, Gate,
  source state and exact revision even when the total score is high.
- `ready=true` only when every applicable required item is complete and there
  are zero active blockers. Score alone never sets readiness. The UI must lead
  with blocker count/state before percentage and use text/icon as well as color.
- The Project readiness revision has no Gate transition method. For an exact
  Gate, the existing Gate Review input builder may add current readiness P0
  blockers and one exact readiness-revision dependency. A later readiness
  successor causes existing review-input drift handling; the Gate must be
  reopened/re-evaluated under its own versioned policy. P7-05 never decides,
  passes, closes or changes a Gate.

### 3.4 Cross-domain effects remain proposals or links

- Trial/production issues may bind exact existing Domain Work Item identities;
  readiness does not silently create, complete or close them. A missing active
  action required by the template is itself an incomplete readiness item.
- Supplier high-risk evidence is visible as a blocker and may bind an exact
  existing Project risk/work identity. P7-05 does not create a project risk or
  claim ERP supplier status.
- Released work, inspection, packaging, parameter and maintenance documents
  count only through exact released revision/baseline state. Working drafts do
  not satisfy release checks.
- Training and qualification are controlled NPI confirmation/report evidence
  in this task. Formal HR/qualification projection remains unavailable.

## 4. Authorization, ownership and transaction boundary

- Project visibility is checked before resolving an instance, template,
  member, Gate, Work Item, document, Tooling, Trial, File or external-provider
  reference. Every secondary ID is rechecked for same tenant/Project.
- Until a production responsibility policy exists, only an enabled same-tenant
  System Manager may create/edit/publish readiness templates or initialize and
  revise the technical slice. Read-only Project access follows the existing
  Project policy. Metadata installs no production authority row.
- Every command uses a closed canonical payload, CSRF, exact optimistic
  version/predecessor/hash, actor-bound idempotency, one transaction,
  append-only audit and sealed replay. Same key/different payload fails.
- Template publish and each instance successor insert their immutable record,
  receipt and audit atomically. Failure leaves no partial tip. Generic DocType
  create/update/delete is denied outside the guarded repository path.
- NPI One owns template/instance/derived readiness truth. Each evidence source
  retains its own master. ERPNext remains master for formal material, quality,
  production, HR and supplier facts. No field becomes dual-master.

## 5. Closed BFF boundary

The audit authorizes these paths only after their checkpoint tests:

| Method and path | Purpose |
| --- | --- |
| `GET /npi-readiness/templates?projectId={projectId}` | exact published versions eligible for the authorized Project |
| `POST /npi-readiness/templates` | create one internal-admin draft with no business default |
| `PUT /npi-readiness/templates/{templateId}/versions/{templateVersion}` | edit the exact current draft only |
| `POST /npi-readiness/templates/{templateId}/versions/{templateVersion}:publish` | publish one immutable validated version |
| `GET /projects/{projectId}/npi-readiness` | exact current instance/history, sources, scores, blockers, permissions and unavailable projections |
| `POST /projects/{projectId}/npi-readiness` | initialize one exact independently frozen Project instance |
| `POST /projects/{projectId}/npi-readiness/{instanceId}/revisions` | append one exact item/owner/due/status/confirmation/evidence successor |

Score calculation happens during initialize/revision and is reverified during
read; there is no caller-triggered score or blocker-suppression route. Existing
Gate review routes remain the only Gate decision boundary. No ERP, Work Item,
risk, Tooling, handover, release, projection or print mutation route is added.

## 6. Additive persistence

Checkpoint 1 adds only four guarded DocTypes:

- `NPI Readiness Template`;
- `NPI Readiness Template Version`;
- `NPI Readiness Instance Revision`; and
- `NPI Readiness Command Idempotency`.

Category/item/source/evaluation content is retained in canonical bounded JSON
inside immutable version/revision records. Existing Project, Gate, member,
Work Item, controlled-document, Tooling, Trial, File and audit objects are
reused. New objects use UUID identity, exact version/predecessor/hash fields,
System Manager/NPI API create-only DocPerms and denied generic update/delete.
Metadata creates no template, instance, fixture, ERP adapter or external call.

## 7. Checkpoints

1. **Domain/contract/additive metadata** — pure template publication,
   applicability, immutable Project instance/successor, exact evidence-source,
   score/blocker and Gate-separation invariants; closed OpenAPI/ownership; four
   guarded DocTypes; receipt values, direct translations and focused tests. No
   route, row, Gate-input change, UI or runtime fixture.
2. **Repository/BFF and Gate-input boundary** — internal-admin template
   commands, Project-first instance read/initialize/revision, exact source
   resolvers, actor-bound replay, one transaction/audit, independent
   default-closed P7-05 switch, and bounded existing Gate-review input inclusion
   of readiness blockers/dependency only. No Gate decision/transition, UI or
   runtime fixture.
3. **Live Project readiness workspace** — add the dense Project workspace
   section with category/item table, exact owner/due/evidence/source state,
   blocker-first summary, score detail and history; cover loading, empty,
   read-only, permission, validation, conflict, processing, retry, drift and
   unavailable external sources in English/`zh`/`zh-TW`, accessibility and
   affected fixed-Linux visuals.
4. **Controlled runtime and Level 2** — disposable-Site template publish,
   independent frozen instance, exact supported/unavailable sources,
   incomplete/complete/failed items, deterministic scores, P0 dominance,
   Gate-review blocking/dependency drift, replay/conflict/rollback/IDOR/route
   recovery/migrations/redaction, zero ERP/network/downstream effects and
   cleanup; then trace, Task Diff Review and Task Gate.

Complete ordinary CI passes before each controlled-Site dispatch. The optimized
`level_2_controlled` path may reuse only the exact successful prior PR Gate
after machine verification. Repair loops run affected checks first and batch
failures with one root; no test, threshold, matrix or PASS criterion is
removed. The complete Phase 7 / PR / release boundary still requires Level 3.

## 8. Requirement acceptance map

| Requirement | P7-05 truthful evidence boundary |
| --- | --- |
| `FR-NP-001` | versioned reusable configuration plus independently frozen exact Project instance |
| `FR-NP-002` | exact category/owner/due/status/evidence/blocking/Gate and P0 blockers in independent Gate-review input |
| `FR-NP-003` | NPI confirmations and exact evidence; formal ERP material/specification mapping remains held |
| `FR-NP-006` | exact controlled-report/Trial quality evidence and failed-result blocker; formal ERP quality remains held |
| `FR-NP-007` | configurable industry deliverables and applicability with no hard-coded automotive rule |
| `FR-NP-008` | exact Tooling capacity-scenario evidence; production Run-at-rate actual remains held |
| `FR-NP-009` | exact Trial/action foundation and readiness effect; production small-batch record remains held |
| `FR-NP-010` | exact released document/baseline checks |
| `FR-NP-011` | controlled training/qualification confirmation foundation; formal HR projection remains held |
| `FR-NP-012` | NPI supplier evidence/blocker/link foundation; formal ERP supplier truth and automatic risk mutation remain held |
| `FR-NP-013` | deterministic total/category scores, blocker count and blocker-dominant ready state |

Expected truthful Task-Gate dispositions are:

- `TECHNICAL_VERIFIED` for `FR-NP-001`, `FR-NP-002`, `FR-NP-007`,
  `FR-NP-010` and `FR-NP-013`;
- `TECHNICAL_VERIFIED_NPI_CONFIRMATION_FOUNDATION_FORMAL_ERP_MAPPING_HELD`
  for `FR-NP-003`;
- `TECHNICAL_VERIFIED_CONTROLLED_REPORT_FOUNDATION_FORMAL_ERP_QUALITY_HELD`
  for `FR-NP-006`;
- `TECHNICAL_VERIFIED_CAPACITY_SCENARIO_FOUNDATION_RUN_AT_RATE_ACTUAL_HELD`
  for `FR-NP-008`;
- `TECHNICAL_VERIFIED_TRIAL_ACTION_FOUNDATION_PRODUCTION_RECORD_HELD` for
  `FR-NP-009`;
- `TECHNICAL_VERIFIED_CONTROLLED_CONFIRMATION_FOUNDATION_FORMAL_HR_PROJECTION_HELD`
  for `FR-NP-011`; and
- `TECHNICAL_VERIFIED_NPI_SUPPLIER_FOUNDATION_FORMAL_ERP_AND_RISK_MUTATION_HELD`
  for `FR-NP-012`.

No aggregate PASS may hide those holds.

## 9. Changed-files to affected-tests

| Surface | Required evidence |
| --- | --- |
| domains/contracts/ownership | immutable template/instance, explicit selectors, exact evidence, deterministic score and blocker dominance |
| DocTypes/controllers | additive migration, immutable projections, exact containment, generic update/delete denial and no seeded rows |
| repository/BFF | Project-first IDOR, stale/version/hash/fork conflict, source drift/unavailable truth, actor replay, transaction/audit and switch independence |
| Gate review | P0 blocker/dependency inclusion, changed-revision drift, no automatic decision/close and retained Gate policy tests |
| retained domains | exact Project/member/Work/Document/Tooling/Trial/File references and no latest substitution/source mutation |
| frontend | unit/state/keyboard/Axe, direct English/zh/zh-TW, mixed-language scan, industrial density and affected Project/Gate visuals |
| runtime | cumulative predecessor, exact replay/reconstruction, high-score blocker dominance, unavailable ERP truth, route recovery, migrations, zero traffic/effects and cleanup |
| trace/controller | eleven Requirement rows, current-task manifest, Task Diff Review and `git diff --check` |

## 10. Rollback

- Before a Project instance exists, disable only the independent P7-05 switch
  and remove additive empty metadata with the reviewed migration rollback.
- After any template or instance revision exists, never delete, edit or
  renumber retained history. Disable new P7-05 routes/workspace and Gate-input
  inclusion, keep records/audit readable to administrators, and deliver a
  reviewed forward repair.
- Rollback never changes Gate decisions, Work Items, source evidence, Project
  risk, Tooling, ERPNext or external systems because P7-05 never owns those
  mutations.
