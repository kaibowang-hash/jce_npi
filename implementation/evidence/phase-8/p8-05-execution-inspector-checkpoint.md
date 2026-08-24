# P8-05 Checkpoint 4 — Tool Asset Execution Inspector

Recorded: `2026-08-24`

Status: `IMPLEMENTED — AWAITS EXACT-SHA ORDINARY CI`

## Authorized predecessor

- Exact checkpoint 3 SHA:
  `17406118f2a771644c90ca00272a247f40b1b5b7`.
- Ordinary CI `32667224305` passes repository `97262446049`, frontend
  `97262445982`, secret `97262446040` and governed visual `97262446007`;
  controlled lanes correctly skip.
- This checkpoint changes no command, worker, adapter, target transport,
  transaction, permission, schema ownership or production configuration.

## Implemented boundary

- The Tool Asset detail read model now returns bounded attempts, aggregate and
  five-field result truth, mapping observation, exact current mapping and
  permission facts only after Project/tenant/source/hash containment checks.
- Result and observation views never expose formal Asset identifiers. The
  current formal Asset identifier/version is projected only when an
  authenticated `authoritative_sandbox` success, the exact current mapping
  head and a fresh permitted P8-01 Asset projection all agree.
- The existing Tooling acceptance/Asset workspace gains a compact, square,
  neutral Tool Asset execution inspector. It separates NPI acceptance evidence
  from business approval, displays aggregate and per-field truth, and retains
  exactly one visible primary `Impact Review` action for the applicable fixed
  create or update command.
- Loading, empty, unavailable, no-permission, read-only, conflict, queued,
  processing, Mock, synthetic, partial, failed, uncertain, authoritative and
  stale/mismatched states remain truthful. Retry, reconcile, submit, ERP
  approval, movement and maintenance controls are absent.
- Browser traffic is limited to fixed Project-first NPI BFF routes. Mock and
  disposable synthetic fixtures contain no formal Asset identifiers and make
  no target request.

## Localization, accessibility and visual governance

- Every new visible source is literal English through the existing `t()`
  adapter, with direct no-header `zh` and `zh-TW` catalog entries and generated
  catalog equality.
- Statuses use text plus icon/shape, the primary action keeps visible text,
  Impact Review owns acknowledgement, and keyboard/focus/accessibility tests
  cover the inspector without color-only meaning.
- Three canonical Linux/amd64 baselines cover English, Simplified Chinese and
  Traditional Chinese across `1366x768@125%` and `1920x1080@125/150%`.
  The inspector remains square, flat and dense; narrow effective width stacks
  Impact Review so the full primary action and field outcome phrases remain
  visible.

## Verification state

- Backend/controller affected suites pass `409/409`: Tool Asset `65/65`, P6
  acceptance `35/35`, retained P6 Tool Asset domain `4/4`, Item `146/146`,
  MBOM `126/126`, and current-task/reconciliation `33/33`.
- Focused frontend data-source/workspace tests pass `21/21`; the complete unit
  and coverage run passes `1,060/1,060` without changing the repository's
  thresholds. The complete non-visual browser run passes `454/454`; after the
  final strict P6 route fixture and authoritative-ID assertions, focused P6
  and P8-05 browser runs also pass `22/22` and `4/4`.
- The six affected canonical Linux/amd64 cases pass no-update verification
  twice consecutively. A clean, serial, exact-workflow Bookworm/x64 run with
  Node `24.18`, Playwright `1.61.1` and one worker passes the complete governed
  visual matrix `129/129` in `17.2m`.
- The P6-06 three-image change is an approved semantic composition migration:
  the existing acceptance/Asset context remains visible while the always-
  present default-disabled Tool Asset inspector and direct reason are added.
  A deterministic inspector scroll preserves the complete visible primary
  action at `1440x900@125%`; it changes no product behavior, baseline
  tolerance, threshold or Darwin evidence.
- Manual review confirms square neutral panels, dense tables, visible text and
  non-color status, one primary Impact Review action, retained prior context,
  no mixed language and usable `125%`/`150%` layouts. Only the authenticated,
  authoritative, exact-current P8-05 case shows the controlled fake formal
  identifier; synthetic, partial and all migrated P6 evidence show none.
- Localization audits cover `8,341` literal English sources with `100%` direct
  `zh` and `zh-TW` catalogs; TypeScript, generated-catalog, code/style/format,
  boundary, accessibility and zero-vulnerability audits pass.
- Current-task verification, reconciliation, changed Python compilation,
  JSON/YAML/Frappe-CSV parsing and `git diff --check` pass. Post-commit
  manifest simulation accepts exactly the authorized `32` task paths and
  rejects a thirty-third path.

Canonical Linux/amd64 SHA-256 evidence:

- P6-06 English: `04194f1cff8e05a86b06d45893756f7c8c59ed094a0a242880bddce155b29750`.
- P6-06 Simplified Chinese: `a6d398125f129126acce2556b3fd0e1f8e74a2ce3c847300cb0c183b763a0081`.
- P6-06 Traditional Chinese: `169dbbd09bf97a3ab6958fd3ff8421411b8ccce786df7240d7c03156f72b4403`.
- P8-05 authoritative Traditional Chinese: `6d3cf07ded6caf7965643930bc9967cc0b3c556d2aa21d868f8e467745a92e9b`.
- P8-05 partial Simplified Chinese: `8f6c272b7b045f9d4a091adc5b46ef75c0e789bc5e911edf23bc284f593179ee`.
- P8-05 synthetic English: `c3f5117bec0297d7dad20349760a9c5bee3b8b0fd0665be6ad15fdec8b7575f7`.

## Held scope

- No production ERPNext/JCE or Sandbox contact occurred.
- Actual ERPNext Asset method, fields, naming, Company, Category, Location,
  maintenance/depreciation, business-approval source and production mapping
  remain held.
- P8-06, P8-08/P8-09 and generic P8-07 retry/replay/reconciliation remain
  inactive. Final unchanged Level 3 remains closed until this checkpoint's
  exact-SHA ordinary CI passes.

## Controlled final recovery status

- Exact checkpoint 4 SHA `3d35d6860e63478bc12fde9a0426d0ea00c8b31e`
  passes ordinary CI `32680231720`.
- Final Level 3 run `32682520429` passes repository, frontend, secret,
  `129/129` visual and controlled preflight; controlled runtime job
  `97303507677` stops at the P6-06 predecessor Mock Asset-create HTTP 500.
- That P8-05 final cycle is frozen `1/1`. A separate predecessor narrowing
  cycle is diagnostic `0/1`, repair `0/1`, final `0/1`; its temporary
  response-neutral activation is not product repair evidence and grants no
  ERPNext, permission, transaction, Schema, ownership or Gate authority.

### P6-06 diagnostic reader harness remediation

- Diagnostic run `32686039575`, controlled job `97311234126`, is harness-only
  failure evidence: the parent reversed the existing strict reader's
  `(exception_type, code, trace)` tuple labels. It does not consume the
  predecessor product diagnostic or repair allowance and proves no product
  root.
- The minimal correction is verifier/test/evidence only. It preserves exact
  scope and trace correlation, single logical mirrored record acceptance,
  duplicate/divergent/invalid fail-closed behavior and the no-leak boundary.
  Server/product/API/permission/transaction/Schema/ownership code is unchanged.

### P6-06 predecessor receipt-seal product repair

- With the reader labels corrected, diagnostic run `32687547589`, controlled
  job `97315303938`, emits the sole tuple
  `P805_P606_ASSET_RECEIPT_SEAL / PermissionError /
  trace-094ac4bd2cf15cac884914224d752ba1`.
- The first-source cross-proof is deterministic: the legacy P6 insert leaves
  additive Int `schema_version` absent on the same in-memory receipt, Frappe
  v15 serializes that value as database `0`, and the seal save reloads `0` as
  its before-document. P8-05 had added `schema_version` to a raw immutable
  tuple, so `None != 0` raised before sealed-response validation. The receipt
  insert already passed; the seal remains inside the same legacy write scope,
  and DocType permissions are unchanged, excluding capability and permission
  drift.
- Product repair `1/1` normalizes only the immutable schema comparison through
  `int(value or 0)`. It does not change persisted values, Schema, API,
  permission, ownership, transaction order, raw comparison of every other
  immutable field or the one-way seal. Pinned lifecycle coverage locks the
  same-object `None` to database-`0` insert/seal path, nonzero schema tampering
  and the closed write scope. Repository coverage retains receipt, request,
  audit and one-save seal ordering with no manual commit or rollback.
- The predecessor cycle is diagnostic `1/1`, repair `1/1`, final `0/1`.
  `P606_ASSET_CREATE_DIAGNOSTICS_ENABLED` is false; the safe mechanism remains
  dormant. The earlier reader run remains harness-only history and no prior
  P8-05 cycle counter is reopened.

### Final retained-Master verifier remediation

- Exact repair SHA `735992c1971c258089ab596ed20663606908f1f7`
  passes ordinary CI `32688638775`. Final run `32689595411` passes every lane
  except controlled runtime job `97322480056`, whose first boundary is the
  Tool Asset default-disabled probe's inherited P6-03 unfiltered Master
  cardinality assertion. No P8-05 command, worker or product write ran.
- P6-08 deliberately retains its formula-neutralization Master for governed
  export evidence. The original P6-01 Master is still unique by exact fixture
  title and originating Project; P8-01 already uses that bounded selection.
  The Tool Asset repository only reads and locks the selected Master/Set.
- The verifier-only correction filters to the exact original fixture identity
  before `exact_single`. It does not remove retained export evidence. Missing
  or duplicate originals, malformed rows and wrong-Project rows fail closed
  without row-value leakage. This is harness remediation and consumes no
  product repair or diagnostic allowance. Product, runtime profile and all
  diagnostic activations remain unchanged and closed.

### Final retained-Part verifier remediation

- Exact Master harness checkpoint
  `154a70058011727b3585f81f3c800aaae77804c0` passes ordinary CI
  `32691391426`. Final run `32692105056` passes every job except controlled
  runtime `97329247216`, which proceeds past the repaired Master selector and
  stops at the inherited P6-03 retained-Part cardinality assertion during the
  default-disabled probe. P8-05 fresh/product execution has not started.
- P6-07 deliberately retains imported engineering Part targets for its
  successful execution, retry, replay and reconciliation proof. P8-01 already
  distinguishes the original P6-01 Part by exact revised fixture title,
  originating Project and current-revision self/version/label predicates.
- The verifier-only correction applies those same predicates before the
  unchanged uniqueness check. It preserves every P6-07 target; missing,
  duplicate, malformed, wrong-Project and revision-mismatched originals fail
  closed with no row-value disclosure. Product code, profile, diagnostics,
  permission, transaction, Schema, ownership and target behavior are unchanged.

### Initial-projection retained-Part harness correction

- Final run `32694547012`, controlled runtime `97335728724`, fails during the
  initial P6-03 fresh context rather than a later P8-05 boundary. The newly
  added direct Part `originatingProjectGlobalId` predicate cannot match because
  that field is not present in the workspace Part response. This is a verifier
  harness regression and changes no cycle counter or product conclusion.
- The corrected selector derives Project containment from the exact
  Project/Master applicability edge already proven by P8-01, then applies the
  exact original title and current-revision self/version/label predicates.
  Initial no-origin projection and later retained-target projection are both
  covered; P6-07 targets remain intact and every missing, duplicate,
  malformed, wrong-edge or revision mismatch stays fail-closed and value-safe.

### Retained ERP-projection temporal harness correction

- Exact stable-Part checkpoint `3181d3b4a023ecd4aae31e16fcf0a84ebdbed483`
  passes ordinary CI `32696041807`. Same-cycle final run `32697236054` passes
  all non-runtime jobs and controlled preflight; controlled runtime
  `97344193455` reaches the P8-05 default-disabled probe after fresh synthetic
  execution and stops at the inherited P6-04 unavailable ERP-projection
  assertion.
- P6 fresh/replay occurs before P8-01 and correctly sees unavailable truth.
  P8-01 then installs and replay-verifies a confirmed read-only ERPNEXT cost
  projection for the exact retained Project and Master. P8-05 synthetic
  execution creates no mapping head and cannot mutate that projection. The
  later unavailable expectation is therefore uniquely a temporal verifier
  compatibility defect, not a product write or ownership violation.
- A closed expected-mode enum keeps unavailable as the default across all P6
  callers. The P8-05 retained context alone explicitly requires available
  truth, with exact outer and nested keys, ERPNEXT read-only authority, the
  exact Master and nonempty typed supplier/row/summary facts. Malformed,
  missing, extra or mismatched truth remains constant-safe and value-free.
  This same-cycle harness remediation changes no diagnostic, product-repair or
  final counter and no product, permission, transaction, Schema, ownership,
  runtime-profile or target behavior.

### Retained Asset-projection temporal harness correction

- Exact cost-mode checkpoint `43f442ce9eb6e72b237b013eeedcb869c4271a76`
  passes ordinary CI `32699651339`. Same-cycle final `32700730677` passes all
  non-runtime jobs and controlled preflight; controlled runtime
  `97353390700` crosses the repaired cost-projection assertion and stops at
  the P6-06 compound acceptance-context boundary in the P8-05 disabled probe.
- Retained identity, permissions and business approval are fixed and already
  proven. P8-01 has created and replayed the exact physical Tooling Set's
  confirmed read-only ERPNEXT Asset projection, while P8-05 Synthetic truth
  has zero mapping heads. The only first-false subcheck is the initial-only
  unavailable Asset projection equality; this is temporal harness
  compatibility, not product pollution.
- An independent closed expected Asset projection mode leaves all P6
  fresh/replay callers strict unavailable. Only P8-05 retained selects dual
  available cost and Asset truth. Available Asset validation is exact-shape,
  read-only ERPNEXT, exact-Tooling-Set, 0/1-cardinality and type strict, with
  constant no-leak failures. Project/Master identity, permissions, approval
  and retained cardinalities remain exact and are never OR-relaxed. No
  product, API, permission, transaction, Schema, ownership, profile, external
  contact or Gate standard changes; historical cycle counters remain
  immutable.

### Tool Asset requester export harness correction

- Exact Asset-projection checkpoint
  `3e4b57f39267577911fa0d69a9f2d17e2e91ae8b` passes ordinary CI
  `32704209380`. Same-cycle final `32705616597` passes repository, frontend,
  secret, governed visual and controlled preflight; controlled runtime
  `97368465747` stops before the first Tool Asset command at the exact runtime
  actor-binding guard.
- The retained Project binding and distinct internal worker are statically
  correct. The sole false subpredicate is the shell's requester export, which
  reused the P8-03 Document/Item actor rather than the retained enabled P6
  manufacturing actor already required by the Tool Asset verifier and
  profile. Earlier fixture stages do not mutate that actor.
- The correction changes only that environment binding to the exact P6 actor
  formula. Wrong Project/requester/worker bindings still fail before command
  access; exact profile membership and product session/enabled/role checks are
  unchanged. No product, user, role, permission, transaction, Schema,
  ownership, adapter, external contact or Gate standard changes. Same-cycle
  counters remain immutable.

### Enabled collection query harness correction

- Exact requester checkpoint `aaa433239166e63fcf5420fc2cc003cd0bcd5680`
  passes ordinary CI `32708092916`; final `32709548912` passes all non-runtime
  jobs and controlled preflight. Controlled runtime `97380802057` passes the
  default-disabled and actor predicates, then stops at the enabled disposable
  command-context guard before the first Tool Asset command.
- The preceding disabled GET proves status 200 and exact empty items, and the
  restart plus profile activation introduces no execution row. Product
  repository code only exposes command contexts for an explicit acceptance
  revision. The verifier's enabled GET omitted that query, making the create
  context deterministically absent while leaving the Synthetic profile valid.
- The harness now URL-encodes exactly one retained
  `acceptanceRevisionGlobalId` query. Focused tests require status 200, exact
  empty items, a dictionary create context and exact Synthetic profile
  independently, and prove POST is reached only after all pass. This changes
  no product/API/permission/transaction/Schema/ownership/profile/adapter/
  target behavior and consumes no diagnostic, product-repair or final counter.

### Independent command-context diagnostic checkpoint

- Exact enabled-query SHA `bbc787c78601e97c91a54cb5f81216a61fc7e0f3`
  passes ordinary CI `32713228802`. Final `32714624286` passes every
  non-runtime job and controlled preflight; controlled runtime
  `97396526892` crosses the exact acceptance query and stops at the same
  compound disposable command-context predicate before the first command.
- The four ordered response predicates and eight possible server query/build
  boundaries are not statically unique, so repair remains forbidden. A new
  bounded cycle starts diagnostic `0/1`, repair `0/1`, final `0/1`; historical
  cycle counters remain immutable.
- Only the versioned exact-scope GET with the sole retained acceptance query
  activates observation. Parent output is restricted to one of four fixed
  response codes or, for create-shape only, one of eight strict mirrored-log
  server codes, plus a class name and exact validated trace. It emits no
  response/body/status value, business value, ID, count, actor, profile,
  exception message or stack. Server observation is innermost-one-record,
  same-exception and request-local/finally restored. Success and all default,
  wrong-scope or invalid-trace paths are response-neutral. Product, write
  order, permission, transaction, Schema, ownership, adapter and Gate code are
  unchanged.

### Command-context STATUS reader harness remediation

- Checkpoint `940f792543db8c5aae5539a5adabc1f11f14d6c9`
  passes ordinary `32719211351`. Diagnostic run `32720631772`, controlled
  runtime `97411186933`, emits only
  `P805_TOOL_ASSET_CONTEXT_STATUS / RuntimeError /
  trace-c9c0846a767a5981b43b83212f43a5b8`.
- The parent STATUS proves no unique product source and previously skipped the
  strict reader even though the exact scoped server request could already have
  produced one safe allowlisted record. Product repair remains forbidden.
- STATUS now shares CREATE_SHAPE's existing strict mirrored reader. A trusted
  exact tuple wins; absent or rejected log evidence falls back to the known
  parent STATUS without server attribution. Missing/invalid HttpResult trace
  stays constant-safe and ITEMS/TARGET_MODE remain zero-reader. This is a
  verifier-only same-cycle correction; product/server stages and diagnostic
  `1/1`, repair `0/1`, final `0/1` counters are unchanged.

### Independent command-context STATUS-stage subcycle

- STATUS-reader SHA `3412feb1d00ceb81f6102541bb51175ce973e14b`
  passes ordinary `32722130405`, including frontend `97415589215`, visual
  `97415589078`, repository `97415589218` and secret `97415589327`.
- The valid earlier parent STATUS tuple freezes its historical cycle at
  diagnostic `1/1`, repair `0/1`, final `0/1`. It is not harness-failure
  evidence and the consumed dispatch is not reopened.
- A separate `command-context-status-stage` subcycle begins at diagnostic
  `0/1`, repair `0/1`, final `0/1`, reusing the unchanged activation, exact
  scope, eight-code allowlist and strict reader. A valid exact mirrored tuple
  wins; `None` falls back to parent STATUS and cannot authorize repair.
- A caught CREATE-stage tuple proves a safe failure in command-context
  construction, but is not automatically the cause of a later non-success
  response. Symbol-level execution-order proof remains mandatory. Product,
  runtime, tests, permission, transaction, Schema, ownership and target
  behavior remain unchanged.

### Independent command-context HTTP-boundary subcycle

- Durable status-stage SHA `a7a74ac19e8a57092a27a4c6d9bb8cfc69db2172`
  passes ordinary `32723750666`. Controlled run `32724859319`, runtime job
  `97423819933`, yields only the parent
  `P805_TOOL_ASSET_CONTEXT_STATUS / RuntimeError /
  trace-73d2232109735af5a2bae6b434ee3c6e`; no strict mirrored server tuple is
  trusted.
- The status-stage cycle freezes at diagnostic `1/1`, repair `0/1`, final
  `0/1`. Because no tuple cannot uniquely separate pre-handler/scope-log
  activation from unstaged read boundaries, repair remains prohibited.
- A distinct `command-context-http-boundary` cycle begins at diagnostic
  `0/1`, repair `0/1`, final `0/1`. Parent output uses only fixed HTTP class
  codes with `RuntimeError` and the exact validated trace. All non-success
  classes consult the strict mirrored reader; a valid server tuple wins and
  absent evidence falls back to the parent class.
- New server codes each guard one lexical API/query/repository/response
  context with the unchanged exact scope, innermost one-record behavior,
  same-exception rethrow and finally restoration. No status value, body,
  business value, identifier, count, actor, message or stack is exposed; no
  product write/order, permission, transaction, API contract, Schema,
  ownership, adapter, target or Gate semantics change.

### Command-context HTTP-boundary repair

- Exact diagnostic checkpoint `b38f3cf9f419c82b3552bdd5fd4dd58e5c182632`
  passes ordinary `32727690270`. Controlled run `32729074121`, runtime job
  `97437071555`, emits only
  `P805_TOOL_ASSET_CONTEXT_REQUEST_FIELDS / RequestValidationFailed /
  trace-606876fcd3af5fe2bd258f8c8a8c94df`.
- Pinned Frappe preserves the named collection query field in `form_dict` as
  it binds the same field to the whitelisted handler argument. The unique
  stage then passed an empty allowed set to the shared unexpected-field
  checker. The BFF keeps route parameters outside `form_dict`, the framework
  transport field is already handled centrally, and verifier tests lock the
  sole exact query, eliminating verifier, route, header and extra-field roots.
- Product repair `1/1` permits only `acceptanceRevisionGlobalId` on this list
  wrapper. The detail wrapper remains empty-query, unknown fields remain
  `RequestValidationFailed`, and shared request security is unchanged.
- `TOOL_ASSET_CONTEXT_DIAGNOSTICS_ENABLED=False`; no scope is sent and no log
  reader is used in normal runtime. Dormant response-neutral diagnostics stay
  covered. The cycle is diagnostic `1/1`, repair `1/1`, final `0/1` pending
  exact-SHA ordinary and unchanged Level 3 proof.
