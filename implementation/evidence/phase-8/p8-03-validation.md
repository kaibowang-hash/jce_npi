# P8-03 Item Publish Execution — Level 3 Validation

Date: `2026-08-21`

Status: **PASS — LEVEL 3**

Requirement disposition:

- `INT-003`: **TECHNICAL VERIFIED — ITEM EXECUTION FOUNDATION; PRODUCTION AND
  SANDBOX MAPPING HELD**.
- `FR-DS-013`: **ITEM EXECUTION PORTION TECHNICALLY VERIFIED; MBOM AND
  PRODUCTION/SANDBOX MAPPING HELD**. This does not complete the whole
  requirement.

## Exact reviewed boundary

- Final product checkpoint:
  `c11d97cc4e26cd3961d7927608eb2510f6411269`.
- Task base / predecessor product checkpoint:
  `260ed2ef865180f33edfca0e8fe1daf4a0a4e771`.
- The task diff contains `100` committed paths across the four frozen product
  checkpoints and bounded final-Gate recovery. `scripts/verify_current_task.py`
  and `scripts/verify_v1_2_reconciliation.py` pass against that exact tree.
- No dependency manifest, Frappe/ERPNext core, cross-database access, test
  deletion, threshold reduction, production endpoint, credential or target
  write was added.

The release-gate review found no P0, P1 or P2 issue. P8-03 therefore closes at
this exact checkpoint. Unrelated local development files and untracked local
evidence are not part of this validation.

## Acceptance and contract evidence

- The fixed Project-first list/detail/create BFF exposes only the
  operation-specific `publish_released_item` request. It derives tenant,
  Project, actor, trace, released source/profile, expected mapping version and
  target version server-side; it is not generic DocType CRUD.
- ERPNext retains ownership of formal Item code, master state, stock UOM,
  naming and target version. NPI One owns the exact released source, approval,
  request, Outbox, immutable attempt, audit and read-only result/mapping
  observation.
- Mock creates no Outbox, attempt, target identity, mapping or network effect.
  Disposable synthetic execution is network-free and non-authoritative. Only
  an authenticated authoritative non-production Sandbox result could advance
  a formal mapping, and no Sandbox profile is installed.
- Request and Outbox commit before enqueue. A pre-call attempt is durable;
  timeout or crash after the adapter boundary becomes uncertain and is never
  blindly redispatched. Duplicate, active-stream, retained-stream, stale
  mapping, restart and replay cases remain fail closed without rewriting
  immutable truth.
- Additive Item support DocTypes are read-only to the NPI API role. Project-
  first authorization, CSRF, actor containment, capability-checked internal
  writes, audit, redaction and exact semantic permission tests pass.
- Migration is additive. The cumulative Site applies migrations at setup and
  twice after synthetic legacy seeding; legacy request/Outbox truth remains
  readable, is not promoted or claimed, and is removed only by the disposable
  fixture cleanup.
- Before an adapter boundary, rollback disables the Item route, enqueue and
  worker while retaining committed request/Outbox/audit history. After a
  crossed boundary, rollback is forward-only: retain every attempt, result,
  uncertainty, observation, mapping head and audit; never delete, rewrite to
  success, blindly redispatch or compensate the target automatically.

## Incremental and task evidence

- Final inspect-verifier remediation Level 1: `25/25` runtime-verifier tests
  plus `44/44` repository/API/security tests, Python compile, current-task
  verification and `git diff --check` all pass.
- Checkpoint 4 Level 2 retains `75/75` focused Python tests, `28/28` focused
  frontend tests, type/lint/style/direct-i18n checks and the complete affected
  Item inspector E2E/visual evidence.
- The four response-neutral diagnostic activations are closed:
  `ITEM_CREATE_DIAGNOSTICS_ENABLED=False`,
  `REPLAY_TERMINAL_DIAGNOSTICS_ENABLED=False`,
  `LEGACY_COLLECTION_DIAGNOSTICS_ENABLED=False`, and
  `LEGACY_QUERY_SERVER_DIAGNOSTICS_ENABLED=False`. Dormant fail-closed/no-leak
  contracts remain tested.

## Exact ordinary CI

Pull-request run `32479492064`, attempt `1`, passes at the exact final product
checkpoint:

- secret scan `96762610233` — PASS;
- frontend `96762610332` — PASS (`1,018` unit tests and `444` E2E tests);
- visual `96762610399` — PASS;
- repository `96762610789` — PASS;
- controlled jobs correctly skip in ordinary CI.

## Final unchanged Level 3

Controlled run `32480568505`, attempt `1`, passes at the same exact SHA:

- secret scan `96765813580` — PASS;
- frontend `96765813706` — PASS;
- repository `96765813720` — PASS (`2,172` tracked Python tests and complete
  prototype/P0/V1.2 reconciliation);
- visual `96765813721` — PASS (`123/123` fixed-Linux cases);
- controlled preflight `96768967388` — PASS (`124` tests);
- cumulative disposable Site `96769017531` — PASS.

Artifacts:

- runtime artifact `p8-integration-runtime-32480568505`, ID `9446493624`, ZIP
  SHA-256
  `3206cbe1c263a40c88f88f6c9dedf0e42bede597c3d123958fbe37269bff448e`;
- runtime `result.txt` SHA-256
  `7da7a1b27d7df031efad8ff2131a49e2d163efdebf5a8b4adc930231eea7d991`;
- visual artifact ID `9446001929`, ZIP SHA-256
  `241ee2da5387626b94e0f1c3883963912ccf2e8d774ccf949f8336b044a3cb5d`;
- Gitleaks artifact ID `9445882686`, ZIP SHA-256
  `3a36f0eef868a807f0eb8a2dccf060549b47bdc8e17ed269acee7b8c8e7eb6e7`.

The runtime result records `result=PASS`, `gate_mode=level_3`,
`scope=p5-01-through-p8-03`, disposable Site `npi.localhost`, database
`npi_one_runtime` and marker `npi-one-local-runtime-disposable-v1`. Fresh and
replay processes prove caller-session restoration, same-stream active and
retained conflicts, cross-process replay, zero Mock mapping, two terminal
not-claimed rows and zero recoverable rows. Legacy proof confirms queued
version-1 truth, read-only detail/list, reconciliation-required command,
guarded zero worker claim, unchanged timestamps/state and cleanup. Containers,
volumes and the disposable network are removed.

## UI, i18n, visual and security disposition

- `7,985` literal English sources have complete direct `zh` and `zh-TW`
  coverage. No new mixed-language fallback is accepted.
- The dense EBOM Item execution inspector covers Mock, queued, processing,
  failed, uncertain, synthetic and authoritative mapping truth with one
  guarded primary request action. Status is not color-only; formal Item
  identity is withheld without current authoritative mapping.
- `123/123` fixed-Linux visuals pass. Reviewed English synthetic, Simplified
  Chinese uncertain and Traditional Chinese authoritative states retain the
  square, flat, high-density industrial hierarchy and accessibility boundary.
- Gitleaks scans `578` commits without a leak. TODO/FIXME/NotImplemented,
  fake-success, backdoor, core-patch and cross-database scans find no release
  blocker; intentional test names and query placeholders are not executable
  bypasses.

## Holds and next task

Production ERPNext/JCE contact, current Item field/naming/UOM/service-scope
mapping, an installed authenticated Sandbox profile, cross-Project engineering
identity, formal mapping from Mock/synthetic/HTTP acceptance/timeout and
generic retry/DLQ/replay/reconciliation remain held. P8-04 activates only as a
planning/audit task for `INT-004` and the MBOM portion of `FR-DS-013`; no P8-04
product code is authorized until its requirement/domain/existing-capability/
security audit is frozen and the resulting transition passes its required
ordinary CI.
