# P7-07 Plan — Immutable Released Trial Summary and Controlled Output

Recorded: `2026-08-15`

Status: `FROZEN — CHECKPOINT 3 PASS; CHECKPOINT 4 AUTHORIZED`

Starting controller checkpoint:
`b9dc2135e16e1b19d375bb29ab733e5e63ccef08`

Retained product checkpoint:
`563fff535bc46f3d0c216a68a555b61b32479a0d`

Primary requirements:

- `FR-PRN-002`;
- `FR-INT-015` NPI-side foundation; and
- `FR-TR-008` released output.

## 1. Audit decision

The bounded Requirement/domain/existing-capability audit is complete. Exact
controller SHA `b9dc213` passes ordinary pull-request CI `31832348527`:
repository `94870751889`, frontend `94870751782`, secret scan `94870751845`
and fixed-Linux visual `94870751727` at `112/112` all pass. Controlled jobs
`94873079174` and `94873079698` skip as expected because the closeout and
audit transition change no product or runtime truth.

P7-07 can proceed without a new business decision only as an NPI-owned
technical retention and controlled-output foundation. The repository has no
Released Trial Summary aggregate, DocType, repository, BFF route, source
adapter or workspace. P7-04 retains immutable comparison, reference and
conclusion truth plus a localized-neutral one-page summary input; that input
is not a released summary, rendered PDF or external event. P5-06 provides the
generic exact-source controlled-print registry, immutable snapshot/output,
private File, QR/hash, actor/time/language/watermark/copy-state and audited
download mechanics, but deliberately installs no production form mapping.

The audit does not approve a formal Trial release role, signer, wet or
electronic signature, retention period, numbered-copy policy, browser-print
claim, external event identity, payload version, redaction agreement, ERP/JCE
consumer or target receipt. `DR-REC-003/004/009` continue to hold those
dependent behaviors. P7-07 therefore calls the NPI command a technical
`retain` or `revise` action, accepts both exact current `approved` and
`rejected` Trial conclusions as decided technical truth, and never interprets
the summary or its controlled PDF as approval, signature, production
acceptance, G7 authority or external publication.

The current conclusion must be a unique decided tip. A `submitted` conclusion
still awaits its exact decision, while a `reopened` conclusion explicitly
returns the Round to analysis; neither can produce a newly retained summary.
This is a direct consistency boundary over the already frozen P7-04 state
machine, not a new formal release policy. A later decided conclusion creates
an append-only summary successor and never rewrites prior summary or output
history.

## 2. Frozen outcome

P7-07 delivers one minimum complete vertical slice:

> load one authorized exact Trial Round and its unique current approved or
> rejected conclusion -> revalidate the complete server-owned exact source
> graph for Plan, Round, locked input, Trial Actual parameters, Samples,
> cavity results, defects, embedded actions, independent verifications,
> comparison, controlled quality/approval references and conclusion -> derive
> one bounded URL-free canonical presentation projection and redaction
> manifest -> append one immutable NPI-owned Released Trial Summary revision
> and audit with actor-bound sealed replay -> retain a later correction only
> as the exact successor of a newly decided conclusion -> expose exact history
> in the dense trilingual Trial workspace -> resolve the summary through one
> server-owned P5-06 controlled-print source adapter -> when and only when an
> independently approved mapping exists, create/download the existing
> immutable controlled PDF without resolving any retained source to latest

P7-07 owns the immutable NPI summary revisions, their exact source manifest,
safe presentation projection, redaction manifest and server-owned controlled-
print adapter. P5-06 continues to own registry/mapping, print snapshot/output,
private File, QR/hash, actor/time/language/watermark/copy-state, download audit
and printer authority. Exact Trial sources retain their existing owners.

P7-07 creates no production Print Format mapping, signature, form owner,
retention rule, numbered copy, external event, Outbox/Inbox row, execution
request, ERP/JCE projection, target receipt, Gate evidence/input/decision,
Project lifecycle change, Work Item mutation, Tooling lifecycle change,
customer approval or formal quality result.

## 3. Domain invariants

### 3.1 Append-only Released Trial Summary revision stream

- `ReleasedTrialSummaryRevision` has one stable summary UUID per exact Project
  and Trial Round, immutable revision UUIDs, a positive `summaryVersion`, one
  exact predecessor revision/hash for every successor, a canonical
  `versionKeyHash`, snapshot hash and a unique current tip. The first revision
  is version 1 with no predecessor. Generic create/update/delete is denied.
- Every revision freezes tenant, Project, Trial Plan, target Round and exact
  current conclusion identities, versions and snapshot hashes. Identity,
  Project, Plan and Round never drift across a stream. A successor must be
  previous version plus one and must reference the exact current predecessor.
- Initial retain is allowed only when no summary stream exists for the Round.
  Later retain uses the successor command. Parallel first-stream, duplicate-
  version, multiple-tip, fork, stale predecessor and new-key no-op successor
  attempts fail before any business row, receipt or audit write. An identical
  actor-bound same-key request replays only its exact sealed response.
- The repository locks and revalidates the Project, Round and summary stream.
  It requires the exact current Round and conclusion tips to agree on tenant,
  Project, Plan, Round, optimistic version and hash. The conclusion state must
  be exactly `approved` or `rejected`; submitted/reopened conclusions are not
  decided and fail closed.
- A rejected conclusion is retained as rejected technical truth. Retaining it
  does not turn it into a pass. An approved conclusion is still only the exact
  P7-04 policy-bound technical decision; summary retention adds no customer,
  production, Gate, signature or external authority.
- Reopening a conclusion never changes an existing summary. A newly submitted
  and decided conclusion may support a summary successor only after exact
  current-tip validation. Prior summaries and controlled outputs remain
  reconstructable and cannot be renumbered, overwritten or deleted.
- Each revision freezes server-supplied actor, UTC time, request UUID and trace
  ID. The browser cannot submit lifecycle state, summary version, predecessor
  inference, actor/time, snapshot, hash, redaction decision or output truth.

### 3.2 Closed exact source graph

- The summary source graph is server-enumerated from the exact current
  conclusion and its exact comparison/reference graph. The caller supplies no
  arbitrary source array and cannot omit, replace or add a source.
- The manifest is a closed ordered set of exact canonical references:

  | Source kind | Exact retained identity/version/hash |
  | --- | --- |
  | `trial_plan_revision` | conclusion/Round-bound exact Plan revision and snapshot hash |
  | `trial_round` | exact Round UUID, optimistic version and canonical snapshot hash |
  | `trial_input_lock_revision` | exact locked-input revision/version/hash or an explicit invariant-safe absence only where the P7-04 comparison itself lawfully permits it |
  | `trial_actual_revision` | exact Trial Actual revision/version/hash |
  | `trial_sample_batch_revision` | every exact Sample Batch tip referenced by the target comparison source |
  | `trial_cavity_result_revision` | every exact target-Round cavity-result tip |
  | `trial_defect_revision` | every exact target-Round defect tip, including its frozen action rows |
  | `trial_defect_verification_revision` | every exact independent verification revision required by retained defect/action truth |
  | `trial_round_comparison_snapshot` | the exact immutable comparison referenced by the conclusion |
  | `trial_review_reference_revision` | every exact controlled quality/internal/customer/deviation reference frozen by the conclusion |
  | `trial_conclusion_revision` | the exact unique current approved or rejected conclusion tip |

- Each loader replays the stored canonical snapshot and revalidates tenant,
  Project, Plan, Round, stable aggregate identity, exact version/hash and
  cross-reference closure. Duplicate identities, unknown kinds, missing
  required rows, orphan actions/verifications, source drift, cross-Project
  references or a latest-value substitution fail closed.
- Exact Sample, cavity, defect and verification collections are complete for
  the target Round under the already accepted P7-02/P7-03/P7-04 selectors.
  The server independently compares database IDs and canonical graph IDs so
  equal row counts cannot hide omission or replacement.
- Defect actions remain embedded immutable facts of their exact defect
  revision; independent verification revisions remain separate manifest
  facts. The summary never upgrades evidence, reference or verification
  presence into approval.
- Review references retain exact Part/Tooling/Set/File identities and hashes.
  Private evidence is represented by the exact clean File Revision identity,
  optimistic version and URL-free canonical hash; no live private path or
  direct File URL enters the summary or output.

### 3.3 Canonical summary and presentation projection

- One canonical summary snapshot contains the exact ordered manifest plus a
  localized-neutral `presentationProjection` derived only from those exact
  snapshots. The projection contains stable codes and safe values for Plan and
  Round identity, input changes, actual parameters, Samples, cavity rows,
  defects/actions/verifications, comparison states, controlled references,
  conclusion, blockers and explicitly unavailable external effects.
- The projection retains exact source identity/version/hash beside each
  displayed group. It does not contain translated enum values. Translation and
  locale formatting happen only at the UI or P5-06 render boundary, while the
  immutable business snapshot remains language-neutral.
- The server derives the projection once during retain/revise and stores it in
  the immutable revision. Detail, history and controlled reprint return that
  retained projection. They never rebuild it from current Plan/Round/File or
  other mutable truth.
- Complete safe presentation is bounded by the existing P5-06 source-snapshot
  limit of `524288` canonical UTF-8 bytes. The summary and adapter reuse the
  same maximum. Overflow, invalid JSON, non-finite values or incomplete
  presentation fails before write; no row is truncated, sampled or silently
  summarized merely to fit a print.
- Large upstream Trial collections therefore remain valid Trial history but
  may truthfully report Released Summary output unavailable until a complete
  bounded projection is possible. P7-07 does not increase the shared P5-06
  limit or weaken upstream collection limits.
- `ReleasedTrialSummaryRevision.snapshotHash` hashes its complete canonical
  summary payload. The P5-06 adapter exposes the exact retained
  `presentationProjection` with summary revision ID/version/hash embedded;
  its independent `sourceSnapshotHash` is the canonical projection hash. A
  controlled-print snapshot therefore binds both the summary revision and the
  exact bytes rendered without pretending the two hashes are interchangeable.

### 3.4 Redaction manifest and sensitive-data boundary

- Every revision contains a closed server-derived redaction manifest. It
  records the schema version, applied rule codes, excluded sensitive field
  classes and explicit external-projection status `unavailable`. The caller
  cannot supply or weaken a redaction rule.
- The structural rules exclude raw private URLs/paths, File content, access
  tokens, passwords, secrets, cookies, authorization headers, credentials,
  provider payloads, production hostnames and unapproved external-consumer
  fields. Safe business values already accepted in immutable Trial snapshots
  are not silently erased or replaced.
- The summary parser, metadata validator, repository, response validator,
  controlled-print adapter, renderer inputs, audit summaries and logs all
  recursively reject forbidden keys and values. The runtime uses exact
  sentinels to prove persisted summary, sealed response, audit, PDF-facing
  projection and logs remain clean.
- `DR-REC-009` still owns consumer-specific redaction and event payload rules.
  P7-07 records that external projection is unavailable and never invents a
  dotted event type, payload envelope, delivery route or receipt contract.

### 3.5 Reuse of controlled-print mechanics

- The server-owned source kind is exactly `released_trial_summary`. Its
  adapter resolves one exact retained revision by Project, source UUID and
  expected summary version, replays the canonical summary and returns only its
  frozen presentation projection. Unknown, stale, forked, cross-Project or
  hash-mismatched revisions are unavailable.
- Registering the source adapter grants no print authority. Outside the fixed
  disposable runtime, the default P5-06 mapping registry still has no
  Released Trial Summary mapping. Capability remains unavailable until an
  independently approved published mapping matches exact tenant, Project
  type, state, language, delivery and copy policy.
- P7-07 reuses `controlled_pdf` and `not_numbered` only. It does not enable
  browser print, numbered copies, production signatures, retention claims or
  any form mapping under `DR-REC-003/004`.
- When a mapping exists, the existing P5-06 command creates one immutable
  controlled-print snapshot/output from the adapter projection, records exact
  actor/time/language/watermark/copy state/QR/hash and audits download/reprint.
  Reprinting an existing snapshot uses retained source/output truth and never
  refreshes the summary or its sources.
- Disposable controlled runtime may install one synthetic mapping over this
  real source adapter to prove the mechanics. That fixture is marked
  disposable, creates no production default and is fully removed with the
  Site.

## 4. Authorization, ownership and transaction boundary

- Authentication and the independent P7-07 route switch are checked before
  request parsing. Project visibility is checked before resolving any Round,
  conclusion, summary or source identity. Every secondary ID is reauthorized
  for exact tenant/Project scope.
- Until a production responsibility/release policy exists, only an enabled
  same-tenant internal System Manager may technically retain or revise a
  summary. This follows the already accepted P7-04 technical management
  boundary and is not a formal production-role, signer or release decision.
- Read-only summary history follows the existing Project view policy. External
  users, portal actors and service identities receive no default create,
  revise, print or download authority. P5-06 independently rechecks exact
  mapping printer authority for controlled output.
- Each retain/revise command uses a closed body, CSRF, exact expected Round,
  conclusion and predecessor versions/hashes, actor-bound idempotency, one
  database transaction, append-only audit and sealed replay. Same key with a
  different payload fails. A failed insert, source validation or audit leaves
  no summary, receipt or audit row.
- P7-07 reuses the guarded `NPI Trial Command Idempotency` receipt with new
  closed operations `released_trial_summary.retain` and
  `released_trial_summary.revise`; it does not add a second overlapping Trial
  receipt owner. Sealed replay binds tenant, Project, actor, operation,
  request hash, target summary revision and canonical response.
- The write order is receipt reservation -> immutable summary revision ->
  append-only audit -> response seal. Repository and API failures roll back
  the complete transaction. Audit records actor/time/request/trace, exact
  predecessor, Round/conclusion, manifest digest, redaction rule set and
  presentation hash without raw sensitive values.
- NPI One owns the Released Trial Summary. Exact Trial, File and controlled-
  print objects retain their existing owners. ERPNext/JCE owns no P7-07 field
  and receives no write or projection. No field becomes dual-master.

## 5. Closed BFF boundary

The audit authorizes only these Released Trial Summary operations:

1. `GET /api/npi/v1/projects/{projectId}/trial-rounds/{trialRoundId}/released-trial-summaries`
   returns the bounded exact summary history, unique current tip, permissions,
   controlled-output source identity and explicit external/form/print holds;
2. `POST /api/npi/v1/projects/{projectId}/trial-rounds/{trialRoundId}/released-trial-summaries`
   technically retains the first exact current decided conclusion;
3. `POST /api/npi/v1/projects/{projectId}/trial-rounds/{trialRoundId}/released-trial-summaries/{summaryId}:revise`
   appends the exact successor for a later current decided conclusion.

The retain body is closed to expected Round optimistic version/hash, exact
current conclusion revision ID/version/hash and a bounded reason. The revise
body additionally carries exact predecessor summary revision ID/version/hash.
The browser cannot submit tenant, actor, state, source manifest, projection,
redaction, language, watermark, copy state, mapping, output, event or external
truth.

P7-07 reuses the existing P5-06 capability/create/detail/content routes for
controlled output; it adds no duplicate PDF transport. Released-summary
responses and generic controlled-print responses each remain closed and bind
route Project/Round/source identities. Every direct handler repeats route
switch, authentication, CSRF where applicable, Project-first authorization,
closed parsing and response validation rather than trusting only the BFF.

No generic DocType CRUD, raw private File URL, Desk form, external projection,
event, provider or ERP endpoint is exposed.

## 6. Additive metadata and migration boundary

- Checkpoint 1 may add only `NPI Released Trial Summary Revision` plus the two
  closed operations/target type on the existing Trial receipt. The revision
  DocType is append-only, read-only outside the guarded repository, delete-
  denied and contains no default row, mapping, signer or business authority.
- Indexed scalar fields support tenant, Project, Round, stable summary ID,
  version, predecessor, conclusion and snapshot-hash checks. Canonical JSON
  columns retain source manifest, presentation projection, redaction manifest
  and complete summary snapshot. Scalar fields must exactly match parser-
  replayed canonical truth.
- Schema creation is additive. Checkpoint runtime migrates a fixed disposable
  Site twice, validates metadata/controller guards and requires zero retained
  production rows before any schema rollback consideration. No patch infers a
  summary, release authority or mapping from historical Trial data.
- Before retained rows, rollback may remove the isolated route/workspace and
  fresh disposable schema. After any retained summary/output history, rollback
  disables only P7-07 routes/workspace and uses a reviewed forward repair; it
  never deletes or rewrites summary, receipt, audit, controlled-print snapshot,
  output or private File history.

## 7. Checkpoints and changed-files-to-tests map

### Checkpoint 1 — domain, contracts and additive metadata

- Implement the pure immutable summary domain, exact parsers, lineage/source/
  projection/redaction validation, OpenAPI/ownership contract, one guarded
  DocType, Trial receipt operations and direct translations.
- Tests: domain lifecycle and decided-state eligibility; exact manifest and
  complete-source closure; predecessor/fork/hash/tamper/extra-secret failure;
  524288-byte boundary and no truncation; redaction; metadata guards; receipt
  seal/replay target binding; OpenAPI/ownership closure; translation symmetry.
- No BFF route, repository write path, UI, mapping, PDF or runtime activation.

### Checkpoint 2 — Project-first repository, BFF and source adapter

- Implement exact source graph loaders, Project/Round/stream locks, retain and
  revise transactions, sealed replay, history query, response validation,
  independent route switch and the production source adapter registration.
- Tests: auth-before-body; same-tenant technical authority; Project-first IDOR
  with real/absent secondary IDs; exact graph enumeration; current decided
  conclusion; stale/fork/no-op/overflow/redaction conflicts; receipt -> row ->
  audit -> seal ordering and rollback; adapter exact version/hash/project;
  capability unavailable without mapping; no Gate/Project/Work/Tooling/ERP/
  integration/Outbox mutation.
- No frontend action, production mapping, external contract or runtime Site.

### Checkpoint 3 — live trilingual Trial workspace

- Add a dense Released Summary section to the existing live Trial workspace,
  with exact history/current inspector, source manifest, safe presentation,
  redaction/authority holds, retain/revise review and reused controlled-print
  action. One primary action is visible only for the exact current decided
  conclusion and permitted actor.
- Cover loading, empty, read-only, unavailable mapping, overflow, no permission,
  processing, conflict/reload, replay, accepted-command refresh failure and
  historical inspection. Navigation cannot replace an in-flight command key.
- Tests: strict data-source validation; unit behavior; keyboard/focus/Axe;
  English/Simplified-Chinese/Traditional-Chinese mixed-language and overflow;
  route-intercept E2E; reviewed governed Linux visuals. No new design token or
  generic controlled-print behavior is introduced.

Checkpoint 2 passed at exact product SHA
`b6a50b9c1fb6bd38bc7cb1099c8744d57e4e96e6` and exact-SHA ordinary PR CI
`31874165243`. Complete repository/BFF/source-adapter evidence is
`implementation/evidence/phase-7/p7-07-repository-bff-source-adapter-checkpoint.md`.
Checkpoint 3 was then activated.

Checkpoint 3 passed at exact product SHA
`9a2ed86fb3780d5d8cdcda023a76d647d384ca63` and exact-SHA ordinary PR CI
`31877039560`. Complete live-workspace evidence is
`implementation/evidence/phase-7/p7-07-live-released-summary-workspace-checkpoint.md`.
Only checkpoint 4 is active.

### Checkpoint 4 — controlled runtime and Level 2

- Extend the cumulative disposable Trial runtime through P7-07. Retain an
  approved summary, reopen/redecide, append the exact successor and prove the
  first revision/output never changes. Also retain a rejected technical
  summary without turning it into a pass.
- Install only a disposable synthetic mapping, render/download the exact
  controlled PDF, prove same/cross-process replay, stale/fork/IDOR/route-
  recovery/migrate-twice/rollback/redaction and clean teardown.
- Digests prove zero Gate, Project, Work Item, Tooling, Trial source,
  production-transition, ERP/integration/Outbox/Inbox/provider mutation.
  Runtime logs and persisted snapshots/receipts/audits/output projection are
  scanned for exact sentinels, private paths and sensitive keys.
- Run Task Diff Review and Level 2. Level 3 remains at the latest retained
  Phase gate and is not weakened or relabelled by P7-07 Level 2.

## 8. Verification gates

Level 1 is changed-files-based: focused Python/domain/metadata/contract/
repository/API tests, frontend unit/type/lint/i18n where applicable, targeted
E2E/visual cases and `git diff --check`.

Each product checkpoint requires exact-SHA ordinary PR CI: repository,
frontend/non-visual E2E, secret scan and governed visual lanes. Controlled
lanes skip until checkpoint 4.

Level 2 requires:

- all P7-07 unit/metadata/contract/repository/API/frontend/E2E/visual tests;
- direct English, Simplified-Chinese and Traditional-Chinese coverage with no
  ordinary-language mixing;
- exact Requirement trace and Task Diff Review;
- controlled preflight bound to the same ordinary-CI SHA;
- cumulative disposable runtime scope `p5-01-through-p7-07`, predecessor
  `p5-01-through-p7-06`, result artifact, redaction scan and cleanup; and
- independent evidence that every formal/external hold and zero-mutation
  invariant remains true.

No test, threshold, visual assertion, route switch, permission check or
redaction rule may be weakened to obtain PASS.

## 9. Rollback and retained holds

Before any retained summary row, restore the starting controller checkpoint
and fresh-migrate only a disposable Site. After retained rows or controlled
outputs, independently disable the P7-07 routes and workspace and deliver a
reviewed forward repair. Never delete, rewrite, renumber, rehash or silently
re-render retained summaries, receipts, audits, controlled-print snapshots,
outputs, access events or private File identities.

The following remain held after P7-07:

- exact Released Trial Summary external event type, payload/version,
  redaction agreement, routing, delivery, consumer projection and receipt;
- production form mapping, owner, signer, wet/electronic signature, retention,
  browser print, numbered-copy and copy-destruction policy;
- customer approval, formal ERP quality, production acceptance, G7/Gate,
  Project, Work Item and Tooling lifecycle authority;
- production ERPNext/JCE access, Outbox/integration execution and provider
  traffic; and
- P7-08 mobile field actions and all later Phase 8/9 work.
