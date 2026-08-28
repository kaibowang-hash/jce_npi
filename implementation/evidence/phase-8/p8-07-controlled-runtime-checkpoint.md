# P8-07 Checkpoint 4 — Controlled Integration Operations Runtime

Status: **LEVEL 1/2 CANDIDATE — AWAITING EXACT-SHA ORDINARY CI**

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
