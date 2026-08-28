# P8-07 Checkpoint 4 — Controlled Integration Operations Runtime

Status: **UUID HARNESS REPAIR LEVEL 1 PASS — FINAL AWAITS EXACT-SHA ORDINARY CI**

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
