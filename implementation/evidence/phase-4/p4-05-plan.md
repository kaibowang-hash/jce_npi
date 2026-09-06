# P4-05 Implementation Boundary — Live My Work, Activity, and Project Controls

Status: **ACCEPTED — see `p4-05-validation.md`**

Recorded: 2026-07-25

Starting checkpoint: `71d628e028a7ac225df562e21ad44cd11beddb3d`

Atomic task: `P4-05 — Live My Work, activity, and Project controls`

Requirement allocation: `FR-PM-008`, `FR-PM-011`, `FR-PM-012`,
`FR-CO-001`, `FR-CO-002`, and `FR-CO-006`

## 1. Repository facts

- P4-01 through P4-04 are accepted. The live Project, Project Work, Gate
  Evidence, and Gate Review aggregates already provide exact Project/tenant
  identity, current-user authorization, controlled file revisions, persisted
  Domain Work Items, frozen Gate assignments, immutable Gate decisions, and
  exact invalidation/successor-cycle history.
- `/api/npi/v1/me/work` and its OpenAPI projection exist only as an unserved
  Phase 3 contract placeholder. `/work` still reads in-memory prototype data.
  It must not be represented as a live queue until the BFF, strict client, and
  runtime evidence are complete.
- Project health, Project control policy, lifecycle history, contextual
  activity, followers, and reusable Project learning have no accepted
  persistence or command path.
- Project cockpit/work-context/Gate Evidence access remains limited to the
  Project owner and internal System Manager, while Gate Review separately
  permits a current active Project member to view its authorized workspace.
  RACI, a Gate Evidence reviewer field, or Domain Work Item ownership does not
  independently widen the former routes or grant approval authority. P4-05
  will preserve these source-specific boundaries rather than invent one global
  Project-access rule.
- No production Project health formula, thresholds, lifecycle authority,
  completion prerequisite policy, ERPNext cost actual, notification service,
  external-user policy, DMS/file-upload path, or production learning/template
  governance has been supplied.

## 2. Selected minimum complete vertical slice

P4-05 will implement:

> bind one explicit published synthetic Project Control Policy to an
> authorized Project with exact frozen member/authority-slot assignments →
> evaluate and persist an honest health assessment →
> execute only policy-authorized pause/cancel/resume controls while completion
> remains fail-closed when its server-owned prerequisites are unavailable →
> append contextual internal comments/follow state/activity and reusable
> learning records → project the current actor's exact authorized Domain Work
> Items, Gate assignments, and invalidated Gate responsibilities into a live
> My Work queue → operate the complete path in the trilingual industrial SPA

No policy or sample business data is installed by migration. Synthetic policy
and Project records exist only in tests and disposable runtime/browser
fixtures.

## 3. Live My Work projection

`GET /api/npi/v1/me/work` becomes a current-actor, read-only BFF query. It will
project only allowlisted, server-resolved source types:

- a non-terminal Domain Work Item whose exact owner is the current actor;
- a frozen Gate Review cycle step or authority whose exact selected assignee is
  the current actor and whose current membership/capability permits the safe
  target workspace; and
- a Gate in `requires_review` projected only to an exact current-cycle
  assignee with an actually available server capability, without fabricating a
  Domain Work Item or falling back to the Project owner.

The projection never writes its category back into a Domain Work Item or Gate.
Explicit mappings are:

- `risk → risk`;
- `issue → issue`;
- `action → task`;
- `decision_request → decision`;
- selected Gate Review work → `approval`; and
- exact invalidation responsibility → `blocker`.

Unknown source kinds, incomplete identity, cross-tenant records, an
inaccessible target under that source's own authorization rule, stale
assignments, and ambiguous responsibility fail closed. Frozen Gate Evidence
owner/reviewer fields are not projected until their normal-user target access
is explicitly authorized. System Manager status does not make every Project
item "my work"; an exact source assignment and available capability are still
required.

The server uses a controlled, rebuildable normalized assignment index
maintained by source transactions and revalidates every source at query time.
This avoids scanning unindexed Gate JSON and permits stable keyset pagination
and complete counts. The index is a projection only; it never becomes the
business status or authority source.

The server supplies a fixed `asOf`, the resolved user time zone, counts,
explicit source identity/version, why-assigned code, next action code, safe
target route, Project identity, and due state. Priority retains its exact
source vocabulary and value, such as Domain Work Item severity or Gate
requirement priority; P4-05 does not invent one cross-domain ranking. Filters
select an explicit priority vocabulary/value pair.

The queue supports `today`, `overdue`, `project`, and priority filters required
by `FR-CO-002`; approval/blocker views remain explicit. Every count carries
availability as well as a value. Integration is `unavailable` until Phase 8
has real owned sources and is never represented by a misleading zero or fake
exception.

## 4. Versioned Project Control Policy and honest health

An independent Project Control Policy aggregate will have a stable UUID/code
root and contiguous immutable published versions. A canonical snapshot holds:

- `schemaVersion`;
- reusable authority slots and their purposes;
- one closed rule for each required dimension: progress, cost, quality, and
  risk;
- a closed overall-health aggregation rule;
- exact lifecycle action/source/target transitions and authority slots; and
- exact server-owned prerequisite keys for every transition.

Binding a policy to one Project explicitly maps every required authority slot
to an effective internal member of that Project and freezes member UUID, user
ID, display identity, policy version/hash, and binding version. The reusable
policy never embeds concrete production users or infers authority from RACI,
Project role, ownership, or substitution.

Health rules use an allowlisted data-only evaluator:

- `manual` permits an explicit `green`, `yellow`, or `red` assessment;
- `higher_is_better` and `lower_is_better` derive status from explicit numeric
  thresholds and a measurement;
- `unavailable` records that a dimension cannot currently be assessed; and
- unknown modes, properties, dimensions, thresholds, or source systems fail
  publication/evaluation.

Every health view includes overall status plus progress, cost, quality, and
risk. Missing policy or input is `unassessed`; unsupported or unavailable
sources are `unavailable`. Cost never claims an ERPNext actual unless a later
owned projection supplies it. A red dimension or red overall result requires
a complete reason and recovery plan. Assessments are append-only and retain
the exact policy version/hash, inputs, results, actor, time, Project version,
audit, and trace identity.

No production thresholds or default-green assessment are installed.

## 5. Policy-driven Project lifecycle

Project lifecycle commands accept only `pause`, `cancel`, `resume`, or
`complete`, require a complete reason, exact expected Project version, and the
bound published policy. The actor must be an exact authority for the exact
source/action/target transition. The server, not the browser, resolves every
prerequisite.

- `pause`, `cancel`, and `resume` may execute only when the explicit policy,
  current state, authority, and server-owned prerequisites permit them.
- Each successful action records the reason, approving actor, exact policy,
  old/new state, version, audit, trace, and append-only lifecycle event.
- `complete` checks non-terminal blocking work, controlled files, handover,
  and cost readiness. Because authoritative handover/cost readiness sources
  are not yet available, completion remains visibly unavailable and cannot set
  `completed` in this task.
- A missing policy, missing authority, unknown prerequisite, stale version, or
  unsupported transition fails closed without partial mutation or optimistic
  UI success.
- Every existing Project Work, Gate Evidence, and Gate Review mutation receives
  the same server-side terminal-state guard. A cancelled or completed Project
  cannot continue changing team, WBS, Work Items, evidence, or review history
  through an older command path.

Cancelled/completed records remain protected history. P4-05 does not invent a
production recovery or archive policy.

## 6. Contextual internal activity

The Project collaboration boundary will provide:

- append-only internal comments with complete text;
- exact `@` mention identities limited to enabled internal members of the same
  authorized Project;
- current-actor follow/unfollow state without notification delivery;
- attachment references to exact, private, same-Project controlled File
  Revisions, returning URL-free metadata only;
- allowlisted same-Project object links with exact type, global ID, version,
  and safe SPA target; and
- a chronological activity timeline covering comments, follow-state changes,
  health assessments, lifecycle actions, and learning entries.

Comments and activity retain Project/tenant identity, actor, occurrence time,
trace, immutable payload/hash, and referenced-object snapshots. Unsupported,
mutable, cross-Project, cross-tenant, external, raw-URL, or ambiguous
references fail closed. Mentions are context only; no in-app, email, webhook,
or external-chat delivery is claimed.

## 7. Retrospective, lessons, and template feedback

Append-only Project Learning records use the closed kinds `retrospective`,
`lesson`, and `template_improvement`. They retain complete content,
recommendation, tags, source Project, exact source Project Template
version/hash, author, time, version, and audit/trace identity.

Authorized users can search accessible learning by text, kind, tag, source
Project, and exact source template identity. Every result exposes a stable
learning UUID that a later Project Template workflow can reference. A
`template_improvement` is only a proposed feedback record; it never edits,
publishes, or silently supersedes an immutable template version.

## 8. BFF and security boundary

The strict same-origin surface will include:

- `GET /me/work`;
- `GET /projects/{projectId}/controls`;
- `POST /projects/{projectId}:bind-control-policy`;
- `POST /projects/{projectId}:assess-health`;
- `POST /projects/{projectId}:transition`;
- `GET /projects/{projectId}/activity`;
- `POST /projects/{projectId}/comments`;
- `POST /projects/{projectId}:follow`;
- `POST /projects/{projectId}:unfollow`;
- `GET /projects/{projectId}/learning`;
- `POST /projects/{projectId}/learning`; and
- `GET /learning`.

Every protected query authenticates and authorizes before resolving secondary
identifiers or cursors. Every command requires Frappe CSRF, request/trace
identity, actor-bound sealed idempotency, closed fields, exact expected
versions where applicable, explicit permission metadata, one Project-root
transaction, audit, and rollback. Unavailable, unauthorized, tenant-mismatched,
and cross-Project identities share the same non-disclosing 404 representation.
Generic DocType create/update/delete/rename and physical history deletion stay
denied.

## 9. Live industrial SPA

- `/work` replaces `PrototypeWorklistTransport` with a strict live data source.
  It retains the dense engineering table, one primary row action, saved views,
  Project and priority filters, server pagination, loading/empty/no-permission/
  invalid/conflict/retryable/final states, keyboard operation, and safe target
  navigation.
- The live Project workspace adds compact `Controls`, `Activity`, and
  `Learning` tabs. Health dimensions use a dense field table rather than KPI
  cards. Lifecycle actions use a review step that displays object, current and
  target state, policy/authority, blockers, unavailable prerequisites, reason,
  and audit outcome.
- Activity uses a docked inspector/timeline and explicit comment context.
  Mentions, exact attachments, and object links are labeled and never rely on
  color or hover alone.
- Learning uses a compact searchable table and editor for the three controlled
  kinds; template feedback is visibly proposed, not applied.
- Every source string remains literal English and goes through the shared
  Frappe-compatible `t()`/`_()` chain with complete direct `zh` and `zh-TW`
  coverage. No external notification/mail/print copy is claimed before those
  surfaces exist.

## 10. Non-scope and Class-B holds

- Production health formulas, thresholds, weighting, cost actuals, quality
  truth, and risk aggregation.
- Production pause/cancel/resume/complete authorities, approval separation,
  recovery rules, retention rules, and completion prerequisites.
- Marking a Project complete while file, handover, or cost readiness is
  unavailable.
- Production learning taxonomy, template-maintainer workflow, automatic
  template improvement, or publication.
- Widening Project cockpit/work-context/Gate Evidence access from membership,
  RACI, Work Item ownership, evidence review fields, or System Manager
  convenience; existing source-specific Gate Review membership access remains
  unchanged.
- In-app/email/SMS/Teams/Slack/webhook notification delivery, unread badges,
  external users/portal, external chat, print, or mail templates.
- Normal-user upload/download, raw private File URLs, DMS/scanner/provider
  integration, or attachment replacement/deletion.
- ERPNext actual cost, formal quality, execution, or any production ERPNext
  connection.
- Integration-exception My Work sources before Phase 8.

These holds remain in `REQUIRED_INPUTS.md`; they pause only their production
rule packages and do not block the bounded generic infrastructure, synthetic
tests, live internal UI, or truthful unavailable states.

## 11. Expected change surface and changed-files → affected-tests

| Change surface | Direct checks before the final task gate |
|---|---|
| Project Control Policy, health/lifecycle domain, immutable snapshots | Domain tests for publication, canonical hash, exact rule evaluation, red reason/recovery, unavailable dimensions, transition authority, unsupported completion, and policy immutability |
| Control, activity, follower, learning, and idempotency DocTypes/controllers | Metadata/controller tests for controlled writes, generic CRUD/delete denial, exact identities, immutable history, and additive migration compatibility |
| Frappe repositories and BFF commands | API/repository tests for auth-before-resolution, tenant/Project isolation, expected versions, CSRF, actor-bound replay/conflict, row locks, audit, trace, and injected rollback |
| My Work source resolvers and cursor | Mapping/query tests for current actor, Domain Work Items, Gate assignments, invalidation, today/overdue/Project/priority filters, stable cursor/as-of/time zone, duplicate suppression, and unknown-source fail-closed behavior |
| OpenAPI, route registry, ownership/contracts | OpenAPI validation; route/closed-schema tests; public response/header/error metadata; ownership and no-raw-CRUD audits |
| Strict frontend data sources/view models | Parser/request tests for closed keys, bounded arrays/text, enum/UUID/date/time/cursor validation, stale-response suppression, command receipt reconciliation, and safe paths |
| Live Work and Project pages | Component/router tests for complete states, filters/pagination, review dialogs, disabled/unavailable controls, no optimistic success, XSS safety, keyboard/focus, and accessible labels |
| Live browser and visual paths | Affected non-visual E2E plus exact English/`zh`/`zh-TW` snapshots at representative viewports/scales; original-resolution trilingual review |
| Shared catalogs | Extraction, literal-English source, direct `zh`/`zh-TW` coverage, placeholder/terminology/mixed-language scans, and affected-page visual matrix |
| Migration/runtime/rollback | Two Site migrations; fresh and compatibility runtime lanes for My Work/control/activity/learning; cross-process sealed replay; route-disable/forward-fix recovery review |

Level 1 repair loops run only the directly affected checks. The completed
atomic slice runs one cumulative Level 2 Task Gate. Because P4-05 changes
public OpenAPI, DocType Schema, controlled history, permissions, shared
catalogs, and completes Phase 4, its exit runs one Level 3 Full Release Gate
and the `release-gate` Skill.

## 12. Migration and rollback

Schema changes are additive. Existing Projects receive nullable policy/current
health references and no guessed values; their control view is
`unassessed`/unavailable. Existing Project, Work Item, Gate, File, evidence,
review, decision, and audit history is not rewritten. New controlled history
tables start empty. A reviewed idempotent migration patch rebuilds only the
derived My Work assignment index from exact existing source records and
revalidates each source; it does not create or alter business assignments. No
migration installs a policy, follower, comment, learning record, health result,
or lifecycle transition.

Before retained P4-05 data exists, the disposable development Site may restore
the prior task checkpoint. After retained activity, health, lifecycle, or
learning history exists, rollback disables the new BFF/live routes, leaves
additive tables and history intact, and deploys a reviewed forward fix.
Controlled history is never physically deleted and the App is not uninstalled.
ERPNext is unaffected because P4-05 performs no ERP read or write.

The reversible route-disable procedure is concrete and Site-scoped:

1. set `npi_p4_05_routes_disabled` to JSON boolean `true` in the affected
   Site configuration and restart the web workers;
2. verify `/api/npi/v1/me/work`, global/project learning, Project controls,
   activity, comments, follow/unfollow, health and lifecycle commands return
   `503 PROJECT_COLLABORATION_ROUTES_DISABLED`, while prior Project/Gate routes
   remain registered and available;
3. retain all additive DocTypes and append-only history, deploy the reviewed
   forward fix, run migrate and the affected runtime/replay probes; and
4. set the flag to JSON boolean `false`, restart, and verify the same live
   routes plus sealed replay before reopening traffic.

A string value such as `"true"` does not activate the switch; only the exact
JSON boolean does, preventing an ambiguous configuration value from silently
disabling routes.

## 13. Exit rule

P4-05 may be marked `PASS` only when the bounded live vertical slice, complete
task acceptance, migration/runtime/replay, trilingual UI, browser/visual,
security/diff/trace review, Level 2, Phase 4 Level 3, and independent release
review all pass.

Trace rows remain truthful:

- `FR-PM-008` may be technically verified only for configurable versioned
  rules, honest unavailable dimensions, and enforced red recovery data;
- `FR-PM-011` remains a foundation while production authorities and supported
  completion readiness are held;
- `FR-PM-012` may be technically verified for searchable/referenceable
  learning and proposed template feedback, not automatic template changes;
- `FR-CO-001` may be technically verified for internal contextual
  collaboration only;
- `FR-CO-002` may be technically verified for the live owned-source center and
  required filters, while Phase 8 integration sources remain open; and
- `FR-CO-006` remains a foundation for later notification, external-user,
  email, print, and delivery surfaces even when every P4-05 source has complete
  direct trilingual coverage.
