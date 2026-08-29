# P8-07 Checkpoint 4 — Controlled Integration Operations Runtime

Status: **FRESH COMBINED DIAGNOSTIC LEVEL 1 PASS — AWAITS EXACT-SHA ORDINARY CI**

Date: 2026-08-29

Requirements: `FR-RP-009`, `UX-016`, `NFR-INT-001`

Checkpoint-3 Gate: `758bb222a1477474af50fc6b84d5d2c56e379adc` /
ordinary CI `33204451677` (**PASS**)

## Scope delivered

- Adds `scripts/verify_integration_operations_runtime.py`, a fixed Project-
  scoped verifier over the retained disposable P8-02 through P8-05 operation
  truth.
- Extends only `scripts/verify-frappe-runtime.sh --projection-only` with P8-07
  default-disable, fresh, cross-process replay, explicit disable, recovery,
  post-migration integrity and exact cleanup phases.
- Derives one deterministic Item `failed_retryable` fixture from the retained
  released source and seals it with the existing worker repository's
  before-adapter failure classifier. No adapter registry or target network is
  installed or called.
- Proves exact Project inventory, logical DLQ, cursor disjointness, foreign
  Project not-found, immutable attempts/results/actions, retryable replay,
  uncertain no-redispatch, reconciliation intent plus a non-authoritative
  trusted observation, stale rollback and action cardinality.
- Restarts the server before identical replay commands, expects sealed `200`
  idempotency responses and verifies no duplicate action/observation history.
- Runs the pinned migration twice before proving action/observation
  immutability and deleting only deterministic fixture rows.

## Safety boundary

- Runtime activation is exact: fixed marker, Project, requester and a distinct
  retained internal worker must all match. The P8-07 route is absent by default
  and restored to absent by the shell trap.
- The browser verifier sends only Project-first fixed BFF requests. It rejects
  restricted response keys recursively and checks request-ID echo plus
  `private, no-store` on every response.
- Failed Bench child stdout is never sought or iterated; stderr is
  `subprocess.DEVNULL`. A successful child must emit exactly one JSON object.
- Cleanup is guarded by the disposable Site, deterministic namespace, Project,
  actor and exact doctype filters. It performs no production action and cannot
  delete retained owner truth outside the P8-07 retryable fixture and its exact
  receipts/observation/audits.
- The log scan rejects deterministic fixture identity, synthetic target fault,
  synthetic adapter, target request/response and private-file markers.
- No production ERPNext/JCE endpoint, credential, data, SSH, connector, Site or
  traffic is used. The queued production fact check remains not effective.

## Verification status

- Focused runtime verifier tests pass `14/14`; the complete P8-07
  domain/contract/metadata/repository/security/API/runtime set passes `48/48`.
- The affected P8-02 through P8-05 API/runtime/security regression set passes
  `198/198`; the governed current-task/devcontainer/reconciliation set passes
  `59/59`; and repository verification passes `2620/2620` in the existing
  local tree (`2614` tracked-candidate tests plus six preserved unrelated local
  prerequisite tests).
- Frontend unit/coverage passes `1086/1086`, with `80.17%` statements,
  `79.98%` branches, `82.60%` functions and `82.79%` lines. The affected
  P8-07 non-visual E2E passes `3/3`; `8585` source strings remain `100%`
  translated in `zh` and `zh-TW`.
- Python compilation, governed shell syntax, current-task and reconciliation
  scripts, JSON/YAML/CSV parsing and `git diff --check` pass.
- The local cumulative runtime entrypoint fails closed before creating a Site
  because the pinned Frappe application is absent; this is an environment
  precondition, not a product/runtime assertion failure.
- The complete local frontend command reaches its final brand guard after all
  code, translation, unit, coverage and build checks pass; that guard rejects
  only a preserved unrelated untracked `frontend/public` image. The clean
  exact-SHA ordinary frontend lane remains authoritative for the candidate.
- The exact changed-file manifest contains only the checkpoint-4 paths and an
  unauthorized extra path is rejected before commit.
- Exact-SHA ordinary CI must pass before a sole controlled Level 3 dispatch.
  That Level 3 must prove the full cumulative Site, result record, artifact and
  cleanup at the unchanged exact SHA.

## Rollback

Before any boundary, disable the P8-07 route/action/enqueue/UI and remove the
runtime activation; retain all product receipts and observations. After any
boundary may have been crossed, disable new commands/claims and use reviewed
forward repair. Never delete product history, blindly redispatch uncertain or
partial work, assert target success, change formal target identity or contact a
production target.

## Holds

Production ERPNext/JCE facts and traffic, Sandbox adapters, formal target
mapping, P8-08/P8-09 and deferred external portals remain held. This checkpoint
does not activate the later production fact-reconciliation task or alter any
future connection rule.

## Exact-SHA ordinary and Level 3 result

- Candidate SHA `016be5292e48ac795a2b45f95b07db5555ccae3f`
  passes ordinary CI `33208066878`: repository `98974133179`, secret scan
  `98974133439`, frontend `98974133485` and governed visual `98974133564` all
  pass; controlled lanes correctly skip.
- The sole Level 3 run `33209167283` at the same SHA passes visual
  `98977843502`, secret scan `98977843553`, repository `98977843582`, frontend
  `98977843672` and controlled preflight `98981169745`. Runtime job
  `98981226307` initializes the pinned Bench and fixed disposable Site, then
  fails in the cumulative verifier; result-record and artifact steps skip and
  cleanup succeeds.
- Source-literal allowlist filtering returns exactly one safe outer label:
  `Local Frappe integration operations default-disabled probe failed.` All
  P5-through-P8-06 and P8-02-through-P8-05 runtime predecessors therefore
  passed in this run; no P8-07 fixture, action, observation, replay, migration
  check or cleanup was reached. Failed child output and response status/body,
  business values, identities, messages and stack remain unread.

The outer label spans login, transport, request-ID, cache-control, recursive
safe-shape and problem status/body/code/media-type/trace/envelope predicates,
so it does not justify a product repair. A separate product-zero diagnostic
cycle adds only fixed value-free codes for those ordered boundaries. The code
is emitted only when this one default-disabled probe fails; it never emits an
actual status, header, body, identity, value, message or stack. The cycle is
frozen at diagnostic `0/1`, repair `0/1`, final `0/1`; it requires its own
exact-SHA ordinary PASS before one Level 2 controlled run. Production contact
and P8-07F remain inactive.

## Default-disabled diagnostic Level 1

- The focused runtime verifier passes `17/17`; complete P8-07 passes `51/51`;
  affected P8-02-through-P8-05 regression passes `201/201`; and governed
  current-task/devcontainer/reconciliation passes `59/59`.
- Repository verification passes `2623/2623` in the preserved local tree
  (`2617` tracked-candidate tests plus six unrelated local-prerequisite tests).
  Python compile, shell syntax, current/reconciliation scripts and diff checks
  pass.
- Exact-five and union-78 manifests are accepted and an unauthorized sixth
  path is rejected. Product/API/schema/frontend/workflow diffs are zero; the
  candidate's own exact-SHA ordinary CI remains the required frontend and
  repository proof before its one Level 2 controlled run.

## Diagnostic result and unique harness root

- Diagnostic SHA `3362f416782e05a3f21f0025cdf88730fdbafca1`
  passes ordinary CI `33211692745`: frontend `98986162628`, repository
  `98986162836`, secret scan `98986162870` and visual `98986162928` all PASS.
- Sole controlled diagnostic `33212760671` passes preflight `98989580926`.
  Runtime `98989686823` initializes the pinned Bench and fixed Site, then
  fails at the default-disabled probe; cleanup passes. Strict twelve-code
  filtering returns zero safe records, while the fixed outer allowlist still
  yields only the P8-07 default-disabled label. Child and response content,
  status, identity, values, messages and stack remain unread.
- The recorder is downstream of input validation. Approved
  `ProjectInstantiationService` derives the retained Project global identity
  with UUIDv5; P8-03 captures and passes that exact canonical identity. The
  diagnostic SHA required UUIDv4 in `_require_project_id`, so it necessarily
  exits before `run_disabled_probe` and before any of the twelve record sites.
  Same-run predecessors prove the shared local-runtime and secret guards were
  available. No product repair is implicated.

## UUID harness repair

- The verifier now requires the canonical UUIDv5 actually owned by the current
  Project domain. UUIDv4, noncanonical text and malformed identities remain
  fail-closed. The default-disabled diagnostic activation is false; localized
  tests retain the bounded mechanism without enabling it in a release run.
- The cycle freezes at diagnostic `1/1`, harness repair `1/1`, final `0/1`.
  Focused verifier passes `18/18`, complete P8-07 `52/52`, affected
  integration/security `72/72`, governance/reconciliation `59/59` and
  repository `2624/2624` in the preserved local tree. Compile, shell syntax,
  current/reconciliation scripts, diff, exact-five/union-78 manifests and
  unauthorized-six rejection pass.
- Product/API/schema/frontend/workflow diffs remain zero. A fresh exact-SHA
  ordinary PASS is required before the sole diagnostics-off Level 3 final.
  P8-07F, production/Sandbox contact and P8-08 remain inactive.

## UUID repair final and fresh-runtime diagnostic boundary

- Harness-repair SHA `570fb32b3f334f2b8da60509f00f3344d98a676d`
  passes ordinary CI `33213916241`: repository `98993187854`, frontend
  `98993188050`, secret scan `98993188074` and visual `98993188094` all PASS.
- Its sole diagnostics-off Level 3 `33214965485` passes repository
  `98996446271`, frontend `98996446246`, secret scan `98996446263`, visual
  `98996446089` and controlled preflight `98998860347`. Runtime
  `98998907735` initializes the pinned Bench and fixed disposable Site, then
  fails in the cumulative verifier; result-record and artifact steps skip and
  cleanup succeeds.
- Fixed source-label filtering returns exactly one safe label:
  `Local Frappe integration operations runtime verification failed.` The
  default-disabled probe therefore passed. The failure is inside `run_fresh`;
  cross-process replay, route disable/recovery, migration verification and
  post-migration cleanup were not reached. Runtime/child stdout and stderr,
  response status/body, business values, identities, messages and stack
  remain unread.

The fresh label spans input/environment, login/CSRF, the retryable seed child,
Project-scoped collection/DLQ/pagination/detail reads, uncertainty rejection,
reconciliation intent/observation, replay, stale conflict and final
cardinality. It cannot authorize a repair. Freeze the UUID-repair final at
`1/1`; open a separate product-zero fresh combined diagnostic at diagnostic
`0/1`, repair `0/1`, final `0/1`.

The bounded diagnostic changes only this verifier, its focused test and the
three P8-07 governance/evidence files. One deterministic trace and one
exclusive `0600` exact-three-key file cover `45` ordered parent stages and
`52` Bench-child stages (`97` exact codes). A child record wins before its
parent through `O_EXCL`; otherwise the nearest parent records. The strict
reader accepts only one allowlisted code, exception class and exact trace.
Failed child stdout remains unseekable/unread and stderr remains `DEVNULL`;
success writes no record. No status, header, body, business value, identity,
count, message or stack may be emitted. Product/API/schema/frontend/workflow
diffs stay zero. Exact-SHA ordinary PASS is required before one Level 2
controlled diagnostic. P8-07F, SSH/ERP contact and P8-08 remain inactive.

Level 1 passes focused verifier `26/26`, complete P8-07 `60/60`, affected
P8-02-through-P8-05 plus P8-07 security/API `80/80`, governed current-task/
devcontainer/reconciliation `59/59` and the full local Python repository
`2632/2632`. Frontend unit/coverage passes `1086/1086` (`80.18%` statements,
`80.00%` branches, `82.60%` functions, `82.79%` lines); the focused P8-07
Playwright matrix passes `6/6`. Generate, typecheck, full lint/format/style/
boundary/UI and i18n checks pass with `8585` English source strings at `100%`
`zh`/`zh-TW`. Python compilation, shell syntax, current/reconciliation scripts,
JSON/YAML/CSV governance checks and diff hygiene pass. Exact-five and
post-commit union-78 manifests are accepted; an unauthorized sixth path is
rejected. App, contract, frontend and workflow diffs are zero, and preserved
unrelated workspace state is untouched.

## Fresh-combined diagnostic result

- Exact SHA `0d5ea573f9d9e981674157e23c3b175afa56ece8` passes
  ordinary CI `33217741527` in all four lanes: visual `99005066818`, frontend
  `99005066999`, secret scan `99005067008` and repository `99005067058`.
- Its only Level 2 controlled run `33218657373` passes preflight
  `99007832827`. Runtime `99007879572` initializes the pinned Bench and fixed
  disposable Site, then fails in the cumulative verifier; cleanup passes.
- Strict exact-97 filtering yields one safe tuple:
  `P807_FRESH_COLLECTION_SHAPE / RuntimeError /
  trace-5f309e82918c5bd2bdd54526bd7dd1b0`. Failed-child output, response
  status/body, business values, identities, messages and stack were not read.
- The tuple proves the fresh environment, login, CSRF, retryable seed and
  collection transport completed, but the shape helper still contains five
  independent ordered predicates. Fresh-combined freezes at diagnostic `1/1`,
  repair `0/1`, final `0/1`; no product repair is authorized.

## Collection-shape diagnostic candidate

The next product-zero exact-five candidate sets only
`COLLECTION_SHAPE_DIAGNOSTICS_ENABLED=True` and turns the previous activation
off. Five ordered collection subpredicate codes extend the retained `97`
outer/fixture codes to exact `102`. The test locks exact code equality and
lexical uniqueness, mutual-exclusion fail-closed behavior, each first
subpredicate boundary, exact-three-key `O_EXCL` inner precedence, strict
reader rejection, parent-owned child environment, failed-child unread and
success-zero behavior. No product/API/repository/schema/frontend/workflow or
production behavior changes. Its own exact-SHA ordinary CI must pass before
one Level 2 controlled run. P8-07F/SSH/ERP and P8-08 remain closed.

Collection-shape Level 1 passes focused verifier `28/28`, complete P8-07
`62/62`, affected contract/security/API `82/82`, governance/reconciliation
`59/59`, full local Python `2634/2634`, frontend unit/coverage `1086/1086`
and focused nonvisual P8-07 E2E `3/3`. Generate, typecheck, full lint/format/
style/boundary/UI, `8585`-source `100%` `zh`/`zh-TW` i18n, compile, shell
syntax, current/reconciliation, JSON/YAML/CSV, exact-102 lexical equality,
diff hygiene, exact-five/union-78 and unauthorized-six rejection pass.
Product/API/repository/contract/frontend/workflow diff remains zero.

## Collection-shape diagnostic result

- Exact SHA `ef6ad3a6be46cd6d23409f7f37eb37f4eb7c7edd` passes
  ordinary CI `33220082395`: secret scan `99012088629`, frontend
  `99012088793`, repository `99012088842` and visual `99012088925` all pass.
- The sole Level 2 controlled run `33220922811` passes preflight
  `99014580690`. Runtime `99014619374` initializes the fixed Bench and
  disposable Site, then fails in the cumulative verifier; cleanup completes.
- Strict exact-102 filtering returns one safe tuple:
  `P807_COLLECTION_STATUS / RuntimeError /
  trace-070a0c335c8553aaa6204d1ccbf25a46`. No child output, actual status/body,
  business value, identity, message or stack was read.
- The request itself returned and had already passed request-ID echo,
  `private, no-store` and recursively safe dictionary-body checks. The tuple
  proves only that status was not `200`; its class and root remain nonunique.
  Freeze this cycle at diagnostic `1/1`, repair `0/1`, final `0/1`.

## Collection-response diagnostic candidate

The next product-zero exact-five candidate enables only
`COLLECTION_RESPONSE_DIAGNOSTICS_ENABLED`. Seven fixed codes classify the
non-`200` response as invalid, informational, other-success, redirection,
client error, server error or out of range without exposing its value. The
active set is exact `104`: retained `45` outer plus `52` fixture stages and
seven response classes. Prior flags are false; mutual activation fails closed.
The existing exact trace, parent-owned child environment, exact-three-key
`0600` `O_EXCL` file, nearest-inner precedence, strict reader, failed-child
unread and success-zero contracts remain unchanged. Product, API, repository,
schema, contract, frontend, workflow and production behavior remain unchanged.
P8-07F/SSH/ERP and P8-08 stay closed until P8-07 reaches Level 3 PASS.

Collection-response Level 1 passes focused verifier `29/29`, complete P8-07
`63/63`, affected integration/security/API `83/83`, governance/reconciliation
`59/59`, full local Python `2635/2635`, frontend unit/coverage `1086/1086`
and focused nonvisual P8-07 E2E `3/3`. Generate/typecheck/full lint,
`8585`-source `100%` `zh`/`zh-TW` i18n, compile, shell syntax, current/
reconciliation, JSON/CSV, exact-104 lexical equality, diff, exact-five/
union-78 and unauthorized-six rejection pass. Product/API/repository/contract/
frontend/workflow diff remains zero.

## Collection-response result and mock-only operation boundary repair

- Collection-response candidate `48871b94ae9bee7dda5e9d6fe6171d772b75ab4b`
  passes ordinary CI `33221910716`. Its sole Level 2 controlled run
  `33222456752` passes preflight `99019233634`; runtime `99019272929` fails
  after fixed Bench/Site initialization and cleanup completes.
- The strict reader accepts one safe tuple only:
  `P807_COLLECTION_STATUS_SERVER_ERROR / RuntimeError /
  trace-2fcaaa171b4f51fba5bafa3c447f1a73`. Actual response status/body,
  failed-child output, business values, identities, message and stack were not
  read or emitted.
- The retained P8-03 `validated_mock` Item publish row has no dispatch and no
  target idempotency key by design. P8-07's derived collection incorrectly
  treated it as an ERP operation, whose closed reference contract requires the
  target key. The repair returns no operation only for that exact mock-only
  combination. Non-mock rows without a key remain rejected, and rows with a
  valid key retain their existing projection.
- This is a minimal compatibility adjustment to the P8-07 read model. It does
  not redesign/refactor domains, contracts, ownership, APIs, workflow,
  permissions or ERP integration; it does not fabricate a key or make one
  nullable. The response diagnostic is off by default and focused tests alone
  activate its exact-104 machinery.
- Freeze collection-response at diagnostic `1/1`, repair `1/1`, final `0/1`.
  The exact-seven repair comprises repository/test, verifier/test and the
  three governance/evidence paths. Its exact-SHA ordinary CI must pass before
  the sole all-diagnostics-off Level 3. P8-07F, SSH/ERP contact and P8-08 stay
  closed.
- Repair Level 1 passes focused verifier/repository `40/40`, complete P8-07
  `64/64`, governance/reconciliation `59/59`, full Python `2636/2636`,
  frontend unit/coverage `1086/1086` and focused nonvisual P8-07 E2E `3/3`.
  Generate/typecheck/full lint, `8585`-source `100%` `zh`/`zh-TW` i18n,
  compile, shell syntax, current/reconciliation, JSON/YAML, security scans,
  exact-104 localized diagnostics, diff, exact-seven/union-78 manifests and
  unauthorized-eight rejection pass. Product API, contracts, schema,
  frontend and workflow remain unchanged beyond the exact derived-read filter.

## Mock-only repair final and post-mock combined diagnostic candidate

- Exact-seven repair SHA `5117bd67359517c21bf4a4824245103c83d675cd`
  passes ordinary CI `33223526404` in all four lanes. Its only diagnostics-off
  Level 3 `33224261629` passes secret scan `99024629237`, repository
  `99024629338`, visual `99024629353`, frontend `99024629452` and preflight
  `99026648007`; runtime `99026682189` fails in the cumulative verifier after
  fixed Bench/Site initialization. Cleanup completes.
- Fixed-label classification returns only
  `Local Frappe integration operations runtime verification failed.` No
  child/runtime output, response status/body, business values, identities,
  message or stack was read. The label is internal to P8-07 but nonunique with
  all diagnostics disabled, so repair is prohibited. Freeze the repair final
  at `1/1`.
- The next product-zero exact-five candidate enables only
  `POST_MOCK_COMBINED_DIAGNOSTICS_ENABLED`; all historical flags are false.
  It reuses exact `104` safe codes and the established exact trace,
  parent-owned child environment, exact-name `0600` `O_EXCL` exact-three-key
  record, inner precedence, strict reader, failed-child unread and success-zero
  contracts. Product/API/repository/contracts/schema/frontend/workflow remain
  unchanged. Its exact-SHA ordinary PASS must precede one Level 2 controlled
  diagnostic. P8-07F/SSH/ERP and P8-08 stay closed.
- Diagnostic Level 1 passes focused verifier `29/29`, complete P8-07 `64/64`,
  governance/reconciliation `59/59`, full Python `2636/2636`, frontend
  unit/coverage `1086/1086` and focused nonvisual E2E `3/3`. Generate,
  typecheck, full lint and `8585`-source `100%` `zh`/`zh-TW` i18n, compile,
  shell syntax, current/reconciliation, JSON/YAML, exact-104 lexical/
  precedence/reader checks, diff, exact-five/union-78 manifests and
  unauthorized-six rejection pass. Product/API/repository/contracts/schema/
  frontend/workflow diff remains zero.

## Post-mock result and collection-server candidate

- SHA `3f368e8e81a9e65b7cfae4170b2e49edc240a0ed` passes ordinary CI
  `33225677222` in all four lanes. Its only Level 2 controlled run
  `33226329198` passes preflight `99030708674`; runtime `99030741831` fails
  in the cumulative verifier after fixed Bench/Site initialization.
- The strict exact-104 reader accepts only
  `P807_COLLECTION_STATUS_SERVER_ERROR / RuntimeError /
  trace-071c347ba3605530b0cc92efb4f6ccd9`. Actual response status/body,
  child output, business values, identities, message and stack were not read.
  This proves a collection 5xx but not one product first source. Post-mock is
  frozen at diagnostic `1/1`, repair `0/1`, final `0/1`.
- The next exact-nine candidate enables only
  `COLLECTION_SERVER_DIAGNOSTICS_ENABLED`. Exact `150` equals retained `104`
  plus `46` value-free API/repository stages. Activation requires one exact
  first collection GET, fixed scope/header, deterministic trace, exact route,
  empty query and fixed command. Strict log cursors precede the request;
  trusted mirrored server evidence wins over the response-class fallback.
  Diagnostics rethrow the same exception, restore scope in `finally`, never
  record values, and remain dormant for every ordinary request.
- Product response, permissions, queries, sorting, ownership, contracts,
  schema, frontend and workflow semantics are unchanged. P8-07F, `JCE-Core`,
  production ERPNext and P8-08 remain inactive. Exact-SHA ordinary PASS must
  precede one controlled Level 2 run.
- Level 1 passes focused API/repository/verifier `51/51`, complete P8-07
  `69/69`, affected integration/security/API `89/89`, governance/
  reconciliation `59/59` and full Python `2641/2641`. Frontend unit/coverage
  passes `1086/1086`; generate/typecheck/full lint and `8585`-source `100%`
  `zh`/`zh-TW` i18n pass. Compile, current/reconciliation, exact-150
  cross-file equality, no-leak, diff, exact-nine/union-78 and unauthorized-ten
  rejection pass.

## Collection-server result and canonical global-ID repair

- Exact-nine SHA `0ad8a586605440b4ab0f19bbbc150c3893161997`
  passes ordinary CI `33227714991`: secret scan `99034556661`, visual
  `99034556721`, frontend `99034556725` and repository `99034556802` all pass.
  The sole controlled run `33228195619` passes preflight `99035925803`;
  runtime `99035958214` fails after fixed Bench/Site initialization and
  cleanup completes.
- Strict exact-150 filtering returns one safe tuple:
  `P807_COLLECTION_ITEM_VALUE / IntegrationOperationsContractError /
  trace-28d37423125450c2a8a4c09833a31ba6`. Failed-child output, response
  status/body, business values, identities, messages and stack remain unread.
- The stage enters `IntegrationOperationReference` for a retained Item row.
  Its first global identity check is the owning Project identity. The current
  Project service deterministically creates canonical UUIDv5 identities, but
  the P8-07 validator required UUIDv4. Later operation/source/state/version/
  hash predicates therefore were not reached. The API contract specifies a
  UUID without a version restriction, and UUIDv4/UUIDv5 are both established
  repository identity forms.
- The same-cycle repair accepts canonical UUIDv4 and UUIDv5 in the P8-07
  global-ID validator and keeps UUIDv1/malformed values fail-closed. Focused
  domain and repository tests use a UUIDv5 Project and retain the prior UUIDv4
  path and version-one rejection. Collection-server diagnostics are disabled
  in release code; mechanism tests activate them only locally and prove the
  request header/trace is dormant by default.
- Freeze this cycle at diagnostic `1/1`, repair `1/1`, final `0/1`. The repair
  is exact-eight: domain, domain/repository tests, verifier/test and the three
  governance/evidence files. No contract, schema, frontend, workflow,
  ownership, permission or production ERP change is included. Exact-SHA
  ordinary PASS is required before the sole all-diagnostics-off Level 3.
  P8-07F/SSH/ERP and P8-08 remain inactive.
- Repair Level 1 passes focused domain/repository/verifier `49/49`, complete
  P8-07 `69/69`, affected integration/security/API `89/89`, governance/
  reconciliation `59/59` and full repository Python `2641/2641`. Frontend
  unit/coverage passes `1086/1086`; focused P8-07 functional and three-locale
  visual E2E passes `6/6`. Compile, shell syntax, current/reconciliation,
  all-diagnostics-off, diff, exact-eight/union-78 manifests and unauthorized-
  nine rejection pass.

## UUID-repair Level 3 and post-UUID diagnostic checkpoint

- UUID repair SHA `56a934806f4a96bc92a553c00c702405232f622f`
  passes ordinary `33229220619`: visual `99038866816`, secret scan
  `99038866907`, repository `99038866926` and frontend `99038866932` all pass.
  The sole Level 3 `33229719467` passes those four lanes and preflight
  `99041766715`; runtime `99041789934` passes Bench and disposable Site setup,
  fails only in the cumulative verifier, skips result/artifact steps and
  completes cleanup.
- Fixed allowlist filtering yields exactly
  `Local Frappe integration operations runtime verification failed.` P8-01
  through P8-06 therefore completed, P8-07 fresh returned nonzero, and later
  P8-07 replay/route recovery/cleanup were not reached. All diagnostic flags
  were false, so no unique inner predicate follows. No raw/child output,
  response body/status, business value, identity, message or stack was read.
- Freeze the prior cycle at diagnostic `1/1`, repair `1/1`, final `1/1`.
  Independent `p8-07-checkpoint-4-post-uuid-collection-server` starts at
  `0/1,0/1,0/1`. Only its new flag is true; all historical P8-07 flags are
  false. Exact `150`, fixed request scope/trace, cursors, exact-three-key
  `0600` `O_EXCL` record, server-inner precedence, fallback, same exception,
  finally restoration, failed-child unread and success-zero remain locked.
- The exact-five candidate changes verifier/test and the three governance
  files only. Product/API/repository/contracts/schema/permissions/ownership/
  frontend/workflow remain unchanged. This is compatibility diagnosis, not a
  redesign. One exact-SHA ordinary PASS is required before its sole Level 2
  controlled diagnostic. P8-07F, SSH/ERP contact and P8-08 stay closed.
- Level 1 passes focused verifier `31/31`, complete P8-07 `69/69`, affected
  integration/security/API `89/89`, governance/reconciliation `59/59`, full
  Python `2641/2641`, frontend unit/coverage `1086/1086` and P8-07 functional
  plus three-locale visual E2E `6/6`. Generate/type/lint/i18n/build,
  compile/shell/current/reconciliation, exact-150/new-only/dormancy, diff,
  exact-five/union-78 and unauthorized-six rejection pass. A preserved
  unrelated untracked public image is the sole final-brand-guard rejection in
  the optional local frontend wrapper; the task has no frontend diff and clean
  exact-SHA ordinary CI remains required.

## Post-UUID collection result and membership checkpoint

- Exact-five SHA `ce5c5f9f0bdd0fa6ad9401c7049d5e7c0328ec8b` passes ordinary
  `33231249944` in all four lanes. The sole controlled diagnostic
  `33231872946` passes preflight `99045986038`; runtime `99046014591` passes
  fixed Bench/Site initialization, fails in the cumulative verifier and
  completes cleanup.
- Strict exact-150 reading yields exactly
  `P807_FRESH_COLLECTION_KINDS / RuntimeError /
  trace-3ed958513004503cb3dc0380225c731d`. No response status/body, returned
  kind set, count, identity, child output, business value, message or stack was
  read. The boundary proves the collection HTTP and shape passed but only that
  at least one required kind is absent.
- Same-run predecessor contracts retain Project-scoped inbound, Item, MBOM and
  Tool Asset records, while zero-row per-kind queries are normal and emit no
  server exception. The aggregate membership assertion is therefore
  nonunique. Freeze the prior diagnostic at `1/1,0/1,0/1`; do not guess a
  product repair.
- Independent exact-five
  `p8-07-checkpoint-4-post-uuid-collection-membership` starts at
  `0/1,0/1,0/1`. Its sole new activation is true and all seven historical
  flags are false. Exact `154` comprises the retained `150` plus four ordered,
  value-free required-kind codes. Exact scope/trace/cursors, mirrored strict
  reader, exact-three-key `0600` `O_EXCL`, inner precedence, original
  exception, finally restoration, failed-child unread and success-zero are
  unchanged.
- Runtime verifier/test and the three governance files are the complete task.
  Product/API/repository/contracts/schema/permissions/ownership/frontend/
  workflow remain unchanged. Exact-SHA ordinary PASS must precede the sole
  Level 2 controlled diagnostic. P8-07F, SSH/ERP contact and P8-08 stay closed.
- Level 1 passes focused verifier `32/32`, complete P8-07 `70/70`, affected
  integration/security/API `90/90`, governance/reconciliation `59/59`, full
  Python `2642/2642`, frontend unit/coverage `1086/1086` and focused P8-07
  functional plus three-locale visual E2E `6/6`. Generate/type/lint/i18n,
  compile/shell/current/reconciliation, exact-154/new-only/dormancy, diff,
  exact-five/union-78 and unauthorized-six rejection pass. Product and
  frontend diffs remain zero.
