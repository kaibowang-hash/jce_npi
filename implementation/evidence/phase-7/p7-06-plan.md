# P7-06 Plan — Production Handover and Observation Period

Recorded: `2026-08-14`

Status: `FROZEN — CHECKPOINT 1 PASS; CHECKPOINT 2 AUTHORIZED`

Starting controller checkpoint:
`75c67e6ffbe8b1cd113a7eac97c7878bce28e258`

Retained product checkpoint:
`418b3aab01c9aebbd0cd0001f58006de9c417f6f`

Primary requirements:

- `FR-NP-014`; and
- `FR-NP-015`.

## 1. Audit decision

The bounded Requirement/domain/existing-capability audit is complete. Exact
controller SHA `75c67e6` passes ordinary pull-request CI `31779635051`:
fixed-Linux visual job `94702372737`, repository job `94702372854`, frontend
job `94702372873` and secret-scan job `94702372905` all pass. Controlled jobs
`94704698686` and `94704699006` skip as expected because this controller-only
transition changes no product or runtime truth.

P7-06 can proceed only as an NPI-owned technical foundation. The repository
has no live production-handover or observation-period aggregate, DocType,
repository, BFF route or workspace. The current Project completion resolver
keeps its generic `handover` prerequisite explicitly unavailable, and P7-05
adds no automatic handover, Gate, Work Item, risk, Tooling or external effect.
Neither fact may be relabelled as formal production handover or G7 authority.

The requirements do not approve a production organization master, receiving-
department mapping, acknowledgement quorum, signature semantics, actual SOP
provider, production-metric provider, stability threshold, conclusion
vocabulary or G7 decision rule. P7-06 therefore places every variable rule in
an explicit published `ProductionTransitionPolicyVersion`. Metadata installs
no default policy, authority, organization mapping or business row. Until an
exact policy is deliberately published and bound, every dependent command
fails closed.

Formal organization identity, actual SOP, first-batch yield, customer
complaints, production cycle time, Tooling-stability actuals, stability
business authority and G7 authority remain held. The five external actual
provider kinds return identity-free `unavailable`, accept no caller-supplied
identity, status, value or conclusion, and perform zero network traffic.

## 2. Frozen outcome

P7-06 delivers one minimum complete vertical slice:

> publish one immutable no-default production-transition policy version with
> explicit NPI receiving-group definitions, sender/receiver acknowledgement
> slots, handover object requirements, unresolved-action rules, observation
> source requirements and conclusion rules -> create one append-only
> `HandoverPackageRevision` over exact Project, member, role-assignment,
> readiness, Work Item, Document, File, Tooling and Trial sources -> append
> acknowledgements by the exact frozen slot actors without copying them to a
> successor package -> derive `fullyAcknowledged` only on the server -> retain
> one independent `ObservationPeriodRevision` whose actual SOP and four
> production metric sources remain explicitly unavailable while their exact
> policy requirements, NPI evidence and retrospective references remain
> reconstructable -> display the same immutable history and holds in one dense
> trilingual Project workspace

P7-06 owns the versioned transition policy, NPI handover package revisions,
immutable acknowledgement facts, observation-period revisions and their
server-derived technical projections. It creates no formal organization,
production metric, ERP transaction, Outbox message, external projection,
approval, electronic signature, Gate evidence attachment, Gate input, G7
decision, Project lifecycle change, Work Item mutation, Tooling lifecycle
change or released output.

## 3. Domain invariants

### 3.1 No-default versioned transition policy

- `ProductionTransitionPolicyVersion` has a stable policy UUID, positive
  version, immutable published canonical snapshot/hash and explicit Project
  applicability. One exact current draft row may be saved only through the
  guarded repository with its expected optimistic version; publish freezes
  that business version permanently. A later correction creates the exact
  next draft business version. Generic DocType writes and every write to a
  published version are denied.
- The policy freezes ordered handover object requirements, NPI receiving-group
  keys, required sender/receiver acknowledgement slots, allowed Project role
  keys, unresolved-action validation, observation source requirements and
  server-evaluated conclusion rules. The package, not the reusable policy,
  freezes exact Project member and role-assignment identities. Neither object
  creates a formal HR or ERP department mapping.
- Every published handover object requirement freezes its requirement key,
  accepted closed source kinds, minimum count and controlled `manifestRole`.
  Different requirements may accept the same source kind. `manifestRole` is
  policy-owned assignment data and is never supplied or overridden by the
  browser.
- The policy must define at least one required sender slot and one required
  receiving slot. Exact production quorum, substitution, separation-of-duty,
  delegation and signature rules remain configuration/authority holds rather
  than hard-coded global rules.
- Observation rules configure the window rule for actual SOP plus units,
  comparators, thresholds and allowed derived technical dispositions for the
  four metrics in a server-fixed mandatory source set:
  `actual_sop`, `first_batch_yield`, `customer_complaint`,
  `production_cycle_time` and `tooling_stability`. A policy may add stricter
  requirements but cannot omit, rename or mark any of those five optional. It
  cannot contain an actual SOP, metric value, provider result or caller-
  selected conclusion.
- This is an NPI technical configuration boundary, not approved production-
  stability authority. Even a published rule and a future derived technical
  disposition cannot by themselves assert formal production stability,
  acceptance or G7 authority.
- Metadata installs no production policy or binding. No template, fixture or
  sample Project becomes a production default.

### 3.2 Immutable handover package and acknowledgements

- `HandoverPackageRevision` is an append-only stream with one stable handover
  UUID and immutable revision UUIDs. Every revision freezes its exact
  predecessor/hash, tenant, Project identity/version/hash, published policy
  version/hash and optional exact readiness-instance revision.
- The server derives the Project hash from one closed canonical transition
  projection containing tenant/Project UUID, optimistic version, business
  code, title, Project type, owner user, target-SOP date, lifecycle state,
  exact template reference, exact Work-policy reference and sorted Customer-
  reference keys. Target SOP remains explicitly planned context and is never
  reused as actual SOP. A member slot
  projection is exactly `{globalId, tenantId, projectGlobalId, userId,
  effectiveFrom, effectiveTo, optimisticVersion}`; a role-assignment slot
  projection is exactly `{globalId, tenantId, projectGlobalId, memberGlobalId,
  roleKey, effectiveFrom, effectiveTo, optimisticVersion}`. Their hashes are
  computed by the server from canonical JSON and the complete projections are
  frozen in the package.
- The package contains an ordered object manifest with exact source kind,
  identity, version, hash and role. Supported manifest sources are bounded to
  same-Project readiness, Domain Work Item, released Document/Baseline, clean
  private File Revision, Tooling capacity and retained Trial facts. Project,
  member and role-assignment context is frozen separately by the package and
  slot projections. A mutable latest pointer, name, filename or raw private
  URL is never a handover object.
- The closed manifest source registry is frozen as follows. Project, member
  and role-assignment context are package/slot snapshots and are not caller-
  constructed generic source rows.

  | Source kind | Exact record | Frozen version | Frozen hash |
  | --- | --- | --- | --- |
  | `readiness_instance_revision` | `NPI Readiness Instance Revision.global_id` | `instance_version` | canonical `snapshot_hash` |
  | `domain_work_item` | `NPI Domain Work Item.global_id` | `optimistic_version` | server canonical Work Item source projection hash |
  | `released_document` | exact `NPI Document Revision.global_id` joined to the unique `NPI Document Revision Lifecycle.revision_global_id` | lifecycle `lifecycle_version` | lifecycle `release_snapshot_hash`, with released state and the complete release event/cycle/policy/confirmation/live-File chain revalidated |
  | `release_baseline` | `NPI Document Baseline.global_id` | `baseline_version` | canonical baseline `snapshot_hash` |
  | `file_revision` | `NPI File Revision.global_id` | `optimistic_version` | SHA-256 of the complete canonical URL-free `file_revision_source_snapshot`, with private/clean/live identity revalidated |
  | `tooling_capacity_scenario` | `NPI Tooling Capacity Scenario Revision.global_id` | `scenario_version` | canonical scenario `snapshot_hash` |
  | `trial_defect_revision` | `NPI Trial Defect Revision.global_id` | `defect_version` | canonical defect `snapshot_hash` |
  | `trial_review_reference` | `NPI Trial Review Reference Revision.global_id` | `reference_version` | canonical reference `snapshot_hash` with transitive currentness revalidated |
  | `trial_conclusion` | `NPI Trial Conclusion Revision.global_id` | `conclusion_version` | canonical conclusion `snapshot_hash` |

  The server reuses or extracts the already governed canonical loaders for
  each tuple. Under the frozen Scheme A boundary, the browser may select only
  closed source options returned for the Project and submits the exact
  published-policy `requirementKey`, kind, ID and expected version only. It
  cannot submit a role, hash, projection, disposition or new kind. The server
  validates the requirement and its accepted kind, computes the canonical
  hash after exact authorization and currentness checks, and injects the
  requirement's frozen `manifestRole`. Different requirements may accept the
  same kind, but within one package an exact `(kind, ID)` belongs to exactly
  one requirement and counts exactly once. Duplicate, ambiguous or cross-
  requirement reuse of the same exact tuple fails before any write.
  Member and role slots freeze a server-derived canonical projection containing
  exact identity, optimistic version, user/member/role keys and effectivity.
- Every receiving-group and acknowledgement-slot row freezes the NPI policy
  group key plus exact Project member and role-assignment identities. It does
  not claim that the key is a formal production department.
- The unresolved selector is server-fixed as canonical
  `{"mode":"all_non_terminal","kinds":["action","decision_request","issue","risk"]}`;
  neither policy nor caller can remove a kind or filter by severity, blocking,
  owner or arbitrary IDs. After locking and validating the exact Project
  version/hash, the repository enumerates every same-tenant, same-Project,
  non-terminal Work Item in UUID order inside the package transaction, with a
  bounded maximum of 10,000. Every row passes the canonical Work Item loader
  and freezes exact identity/version/hash, then-current state, owner and due
  date. Missing owner/due date, duplicate/drifted/missing row or overflow fails
  before package/receipt/audit writes. A successor re-enumerates the complete
  set; retained snapshots never change. P7-06 neither creates nor changes a
  Work Item, and a caller cannot submit or omit unresolved IDs.
- `HandoverAcknowledgement` is an immutable fact bound to one exact package
  revision/hash and one required slot. The authenticated actor must be the
  frozen enabled same-Project member; the browser cannot submit an actor or
  acknowledge for another person.
- Only the unique current package revision may receive a new acknowledgement;
  the repository locks and revalidates the current tip before insert. A
  successor makes its predecessor ineligible for later acknowledgement while
  preserving every acknowledgement already recorded against that historical
  revision. The closed request carries only exact package revision/hash, slot
  key and an explicit acknowledgement intent; actor/time and all projections
  are server-derived.
- Package creation accepts only an enabled User whose original Project member
  and role assignment are currently effective, then freezes both exact
  projections. Substitution, delegation and administrator proxy signing do
  not apply in P7-06. At acknowledgement time the server re-reads the same
  User/member/role rows, requires the session principal to equal the frozen
  user, requires the User enabled and both effectivity intervals current, and
  requires their optimistic versions and canonical hashes unchanged. Drift,
  expiry or disablement fails closed and requires a package successor.
- A package successor never inherits acknowledgements. Prior acknowledgements
  remain historical facts and cannot satisfy the successor. Duplicate slot
  acknowledgement is idempotent only for the identical actor-bound payload.
- `fullyAcknowledged` is a query-time projection derived on the server only
  when all exact required slots on the selected revision have immutable
  acknowledgements. It is never stored in or used to recalculate the package
  snapshot/hash. It is not an approval, signature, production acceptance, Gate
  result, G7 closure or Project completion.

### 3.3 Independent observation-period truth

- `ObservationPeriodRevision` has a stable observation UUID and immutable
  append-only revision UUIDs, exact predecessor/hash, Project/policy context
  and an optional exact handover-package reference. It is never embedded in or
  substituted for the handover aggregate.
- Only the unique current observation tip may accept a successor. The
  repository locks the Project/observation stream and revalidates the exact
  current revision, predecessor and snapshot hash in the same transaction;
  stale, ambiguous-tip, reused-predecessor and fork attempts fail before any
  revision, receipt or audit write.
- Actual SOP is the first server-fixed mandatory read-only external provider
  kind and is distinct from the Project target SOP. Until an approved adapter
  exists it is identity-free `unavailable`; the browser or policy cannot omit
  it or submit its date or status. A planned policy window never becomes an
  observed post-SOP period without an actual source.
- First-batch yield, customer complaints, production cycle time and Tooling
  stability are the other four server-fixed mandatory external actual provider
  kinds. In P7-06 all five providers are injected by the server as identity-
  free `unavailable`, make no network request, and cannot be omitted or accept
  caller/policy values, source identities, observed-window dates, zero
  imputations or pass flags.
- Exact NPI-owned Work Item, Document/Baseline, clean File, Tooling and Trial
  references may provide review context or retrospective evidence, but cannot
  be relabelled as any external production actual. Observation references are
  independent of handover requirement assignment: the browser submits only
  closed exact kind, ID and expected version with usage fixed to `context` or
  `retrospective`; it cannot submit a handover `requirementKey`,
  `manifestRole`, hash or projection. The server uses the applicable closed
  source registry and canonical loader, enforces same-Project/current-version
  checks, and freezes exact kind, ID, resolved version, canonical hash and
  usage. If the same `(kind, ID)` tuple occurs across the context and
  retrospective lists, its resolved version and hash must be identical;
  drift or conflicting duplicates fail before any write. Each successor
  freezes the complete exact reference set anew without a latest lookup.
- Source availability, observation state and conclusion are server-derived
  from the exact published policy and resolved sources. While any mandatory
  provider is unavailable, every missing source has state `unavailable`,
  observed start/end and metric identities/values remain absent, and the
  aggregate technical disposition is exactly `not_evaluable`, never `0`,
  success or stable. The browser cannot submit a metric state, value, score,
  stability conclusion or translated enum. A future approved adapter can add
  exact actuals only in an immutable successor under separately authorized
  provider rules.
- The five unavailable projections use closed provider-specific reason codes;
  an arbitrary caller/policy reason or free-form provider payload is rejected.
- Retrospective notes and exact evidence references remain separate from the
  conclusion. Correction, extension or later provider truth creates an exact
  successor revision; it never overwrites the retained observation.

### 3.4 Gate, lifecycle and external effects remain separate

- The statement that both sides must confirm before G7 can close is a
  necessary evidence condition only. Exact G7 identity, other prerequisites,
  reviewer/quorum, exception, reopen and close authority remain governed by
  the existing versioned Gate policy and separate Gate commands.
- P7-06 does not change the Gate-review input builder, Gate evidence hooks,
  Gate instances/cycles/decisions, Project completion prerequisite resolver or
  Project lifecycle. It exposes no Gate mutation or automatic evidence-
  attachment path.
- Readiness status does not automatically start handover, and handover status
  does not automatically start or conclude observation. Any ordering beyond
  the frozen exact references remains an explicit policy decision.
- No command contacts ERPNext, resolves a production organization or metric,
  writes an Outbox/Inbox/Execution Request, publishes an event or claims an
  external projection. The future `update_project_handover_status` example is
  not activated by P7-06.

## 4. Authorization, ownership and transaction boundary

- Authentication precedes request parsing. Project visibility is checked
  before resolving a policy, package, acknowledgement, observation, member,
  role assignment, readiness, Work Item, Document, File, Tooling or Trial ID.
  Every secondary reference is reauthorized for exact tenant/Project scope.
- Until production responsibility and organization policies are approved,
  only an enabled same-tenant System Manager may create/edit/publish policies
  or create/supersede package and observation revisions. Read-only access
  follows the existing Project policy.
- An acknowledgement is not an administrator proxy action: only the exact
  frozen slot member can acknowledge that slot. External users, service
  identities and portal actors receive no default acknowledgement authority.
- Every command uses a closed canonical payload, CSRF, exact optimistic
  version/predecessor/hash, actor-bound idempotency, one transaction,
  append-only audit and sealed replay. Same key with a different payload fails;
  a failed transaction leaves no revision, acknowledgement, receipt or audit.
- Generic DocType create/update/delete is denied outside guarded repositories.
  Snapshot, acknowledgement and audit rows cannot be physically deleted.
- NPI One owns policy, package, acknowledgement and observation snapshot truth.
  Each exact NPI source retains its owner. ERPNext/customer providers retain
  formal actual SOP and production-metric truth; no field becomes dual-master.
- Audit records exact actor/time/request/trace, policy and predecessor hashes,
  source-resolution summaries, package supersession, acknowledgement slot,
  observation revision and derived disposition. Raw private URLs, tokens and
  sensitive external payloads never enter persisted snapshots or ordinary
  logs.

## 5. Closed BFF boundary

The audit authorizes these paths only after their checkpoint tests:

| Method and path | Purpose |
| --- | --- |
| `GET /production-transition/policies?projectId={projectId}` | list exact published versions eligible for the authorized Project |
| `POST /production-transition/policies` | create one internal-admin draft with no business default |
| `PUT /production-transition/policies/{policyId}/versions/{policyVersion}` | edit the exact current draft only |
| `POST /production-transition/policies/{policyId}/versions/{policyVersion}:publish` | publish one immutable validated version |
| `POST /production-transition/policies/{policyId}/versions` | create one draft version successor from the exact current published version/hash |
| `GET /projects/{projectId}/production-transition` | return exact handover/observation current revisions, history, permissions, acknowledgements, unresolved actions and unavailable providers |
| `POST /projects/{projectId}/production-handover` | create one exact independently frozen handover package |
| `POST /projects/{projectId}/production-handover/{handoverId}/revisions` | append one exact successor package without inheriting acknowledgements |
| `POST /projects/{projectId}/production-handover/{handoverId}/revisions/{handoverVersion}/acknowledgements` | acknowledge one exact frozen actor slot |
| `POST /projects/{projectId}/observation-periods` | create one independent observation-period revision from an exact policy |
| `POST /projects/{projectId}/observation-periods/{observationId}/revisions` | append exact review/evidence context while external actuals and conclusion remain server-derived |

There is no route for caller-supplied `fullyAcknowledged`, external source
identity/status/value, stability conclusion, approval/signature, G7/Gate,
Project lifecycle, Work Item, Tooling, ERP, event or external projection
mutation. Checkpoint 2 activates only the independent default-closed
`npi_p7_06_routes_disabled` boundary; it adds no Gate-input hook.

## 6. Additive persistence

Checkpoint 1 adds only six guarded DocTypes:

- `NPI Production Transition Policy`;
- `NPI Production Transition Policy Version`;
- `NPI Handover Package Revision`;
- `NPI Handover Acknowledgement`;
- `NPI Observation Period Revision`; and
- `NPI Production Transition Command Idempotency`.

Policy definitions, manifests, frozen member/role bindings, unresolved-action
snapshots and exact source states are retained as canonical bounded JSON in
their immutable versions/revisions. Acknowledgement-derived projections such
as `fullyAcknowledged` are never written back into a package. New objects use
UUID identities and exact version/predecessor/hash fields. The policy-version
DocType permits only guarded optimistic draft saves and becomes immutable on
publish; package, acknowledgement and observation records are create-only and
append-only. Controllers deny generic create/update/delete and never use an
unscoped permission bypass. Metadata creates no policy, package, observation,
organization mapping, provider, adapter, endpoint, credential, fixture, Gate
binding or business truth.

## 7. Checkpoints

1. **Pure domain/contract/additive metadata** — no-default policy publication,
   published-requirement-owned `manifestRole`, Scheme A handover selection,
   immutable package/successor, actor-slot acknowledgement, independent exact
   observation references, identity-free unavailable-provider invariants;
   closed OpenAPI/ownership; six guarded DocTypes; receipt values, direct
   translations and focused tests. No live route, row, Gate hook, UI or runtime
   fixture.
2. **Repository/BFF boundary** — internal-admin policy commands, Project-first
   workspace/package/observation commands, exact source resolvers,
   actor-bound replay, one transaction/audit and independent default-closed
   `npi_p7_06_routes_disabled`. No Gate input/evidence/mutation, Project/Work/
   Tooling mutation, external provider or runtime fixture.
3. **Live trilingual Project workspace** — dense handover manifest,
   receiving-group/slot acknowledgement, unresolved-action, immutable history,
   observation source/state and retrospective views; complete loading, empty,
   read-only, permission, validation, conflict, processing, retry, superseded
   and external-unavailable states in English/`zh`/`zh-TW`, accessibility and
   affected fixed-Linux visuals.
4. **Controlled runtime and Level 2** — disposable-Site policy publish,
   package supersession, exact actor acknowledgements, independent observation
   revisions, identity-free offline providers, immutable reconstruction,
   replay/conflict/rollback/IDOR/route recovery/migrations/redaction, zero
   Gate/Project/Work/Tooling/ERP/network/Outbox effects and cleanup; then trace,
   Task Diff Review and Task Gate.

Complete ordinary CI passes before each controlled-Site dispatch. The exact-
SHA optimized Level 2 path may reuse only a machine-verified successful prior
ordinary Gate. Affected failures are repaired and checked in batches without
removing a test, threshold, matrix or PASS criterion. The complete Phase 7,
PR or release boundary still requires Level 3.

## 8. Requirement acceptance map

| Requirement | P7-06 truthful evidence boundary |
| --- | --- |
| `FR-NP-014` | technical immutable NPI handover-package and acknowledgement foundation; formal organization mapping and G7 authority remain held |
| `FR-NP-015` | technical immutable observation/review/retrospective foundation; actual SOP, external production metrics and stability business authority remain held |

Expected truthful Task-Gate dispositions are:

- `TECHNICAL_VERIFIED_IMMUTABLE_HANDOVER_ACKNOWLEDGEMENT_FOUNDATION_FORMAL_ORGANIZATION_AND_G7_AUTHORITY_HELD` for `FR-NP-014`; and
- `TECHNICAL_VERIFIED_OBSERVATION_REVIEW_FOUNDATION_ACTUAL_SOP_EXTERNAL_METRICS_AND_STABILITY_AUTHORITY_HELD` for `FR-NP-015`.

Neither aggregate disposition means formal production handover, production
acceptance, G7 close or post-SOP production stability has occurred.

## 9. Changed-files to affected-tests map

| Change boundary | Minimum affected evidence |
| --- | --- |
| policy/domain/ownership/OpenAPI/metadata | guarded optimistic draft write, publication immutability, no-default policy, exact applicability/hash, required sender/receiver slots, each published handover requirement's accepted kinds/minimum count/`manifestRole`, closed Scheme A request without caller role/hash/projection, closed source table, object/action rules, external provider closed schema, six-DocType metadata and generic mutation denials |
| handover package and acknowledgement repository/BFF | exact Project/source containment, published `requirementKey` membership and accepted-kind validation, different requirements accepting the same kind, one exact `(kind, ID)` assigned to one requirement and counted once, server-injected `manifestRole`, paired identity/version/hash drift, no-latest substitution, complete server-enumerated unresolved items, owner/due freeze, current-tip-only acknowledgement, successor non-inheritance, unchanged package hash after acknowledgement, User/member/role effectivity/version/hash and no substitution/proxy, duplicate/replay/conflict/rollback, CSRF/IDOR and no approval/signature/Gate effect |
| observation repository/BFF | aggregate independence, unique current tip and concurrent fork rejection, target-SOP/actual-SOP distinction, mandatory non-omittable five-provider identity-free offline set, absent observed dates/values/identities, exact `not_evaluable` derivation, independent closed-registry references with fixed `context`/`retrospective` usage and no handover `requirementKey`/`manifestRole`, identical resolved version/hash when one tuple occurs across both lists, no latest lookup, no caller value/status/conclusion, no zero/pass/stable imputation, exact review/evidence successor and zero network/Outbox traffic |
| Project workspace and translations | unit/state/accessibility, English/`zh`/`zh-TW`, mixed-language scan, permission/read-only/error/conflict/superseded/unavailable states and affected fixed-Linux visual matrix |
| controlled runtime and controller evidence | fresh install/migrate, same/cross-process replay, retained reconstruction, route disable/recovery, no Gate/Project/Work/Tooling/ERP mutation, cleanup, current-task diff, trace and reconciliation |

## 10. Migration and rollback

- P7-06 metadata is additive and installs no production organization,
  acknowledgement, observation, conclusion, Gate, ERP or integration policy;
  no external provider, adapter, endpoint, credential or business fixture is
  added.
- Before retained P7-06 history, a disposable environment may restore the task
  checkpoint and migrate fresh.
- After any policy, package, acknowledgement, observation, idempotency or audit
  history exists, rollback disables only the independent
  `npi_p7_06_routes_disabled` route boundary and Project workspace, then uses a
  reviewed forward fix. There is no Gate hook or external side effect to undo.
- Retained revisions and acknowledgements are never deleted, rewritten,
  renumbered or copied to simulate reversal. Correction, revocation, extension
  and later external truth create explicit successors.
- Because P7-06 performs zero ERP/network/Outbox work, it defines no production
  compensation or cross-system destructive rollback path.
