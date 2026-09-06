# P8-07 Checkpoint 1 — Domain, Contracts and Guarded Metadata

Status: **EXACT-SHA ORDINARY CI PASS**

Date: 2026-08-28

Requirements: `FR-RP-009`, `UX-016`, `NFR-INT-001`

Audit-plan Gate: `2e573fa1757f7d9306f17bb47cb62c59e8493b7f` /
ordinary CI `33139628396` (**PASS**)

Checkpoint-1 Gate: `d45d1d560fedfed9d9791a5c08ccf9c1402f7ef8` /
ordinary CI `33142594763` (**PASS**)

Predecessor product checkpoint:
`547421a059911df6aeb90bbbf06e837f77a3e5e0`

## Scope delivered

- fixed operation inventory: `receive_project_submission`, `publish_item`,
  `publish_mbom`, `create_tool_asset`, `update_tool_asset`;
- closed raw-state classification, derived logical DLQ and exact replay
  eligibility that rejects unknown, final, partial, uncertain, quarantined and
  conflict truth;
- immutable operation references, actor-bound action receipts and trusted
  reconciliation observations with exact safe response/evidence shapes and
  canonical hashes;
- additive version-1 OpenAPI schemas, internal event definitions and ownership
  declarations only; no route or generic target command;
- guarded append-only `NPI Integration Action Receipt` and
  `NPI Integration Reconciliation Observation` metadata with zero default rows;
  and
- direct English-source `zh` and `zh-TW` metadata translations.

## Security and ownership evidence

- Project, tenant, operation, source, version, raw/shared state, source hash and
  target-idempotency hash remain exact immutable references to their owning
  P8-02 through P8-05 repository truth.
- Action response and reconciliation evidence reject extra fields, drifted
  identities/hashes, unsafe transport material and noncanonical hashes.
- Confirmed reconciliation truth requires authenticated authoritative Sandbox
  evidence from the trusted operation service. Human intent alone cannot assert
  target success or formal identity.
- The request-local support-write capability rejects Guest, Administrator,
  wrong actor, wrong role, wrong DocType/action and expired scope. It does not
  install a repository writer or broad permission bypass.
- Both support DocTypes are read-only, append-only, delete-denied and grant no
  direct create/write/delete/export/print/email permission to `NPI API User`.
- Production ERPNext/JCE contact, profiles, credentials, data and traffic remain
  prohibited. No Site, connector, queue, adapter or target call was used.

## Changed-files to affected-tests map

| Area | Evidence |
|---|---|
| operation domains | `tests/test_phase8_integration_operations_domain.py` |
| guarded controllers and metadata | `tests/test_phase8_integration_operations_metadata.py` |
| capability and permission boundary | `tests/test_phase8_integration_operations_security.py` plus the global permission scanner |
| OpenAPI/events/ownership | `tests/test_phase8_integration_operations_contract.py` and P8-02 through P8-06 contract regressions |
| direct translations | repository catalog generation, direct translation and mixed-language checks |
| governance | current-task and V1.2 reconciliation tests/scripts, exact manifest and task diff |

## Verification

Level 1 passes:

- P8-07 focused domain/metadata/security/contract: `18/18`;
- affected P8-02 through P8-06 backend regressions: `550/550`;
- full local Python workspace: `2590/2590` (the tracked CI collection is
  `2584`; six preserved unrelated local-prerequisite tests are untracked);
- current-task and V1.2 reconciliation units: `38/38`, plus current-task,
  reconciliation generation and independent reconciliation scripts;
- frontend unit/coverage: `1073/1073`, with aggregate statement/branch/function/
  line thresholds retained;
- generated catalog check, TypeScript, ESLint, Prettier, Stylelint, boundary,
  industrial UI and direct i18n audits; `8496` literal English sources have
  `100%` direct `zh`/`zh-TW` coverage and zero unapproved mixed-language token;
- Python compile, JSON/YAML parsing, global permission/security regressions,
  direct-SQL/permission-bypass/network/production scan and `git diff --check`;
  and
- exact `31`-path candidate manifest accepted; an unauthorized thirty-second
  path rejected. The governed post-commit union remains inside the fixed `66`
  allowed patterns.

The checkpoint modifies no workflow, route, API handler, repository writer,
worker, adapter or existing P8-02 through P8-06 product owner.

### Ordinary-CI scanner remediation

Initial checkpoint SHA `25c845066ecc5f000d35ecd0209f60f01dd21055`
entered ordinary CI `33141886949`. Repository job `98754314346` passed the
tracked `2584` Python tests and every earlier verification step, then failed
only because the fail-closed direct-SQL lexical scan found the prohibited
token in this checkpoint's own negative security-test inventory. Product code
contained no direct SQL. Frontend `98754314466`, visual `98754314547` and
secret-scan `98754314478` passed; no second CI failure boundary was present.

The same-cycle repair keeps the negative assertion but constructs the token
from fixed fragments, so the test still rejects a future product occurrence
while the repository-wide scanner returns zero matches. Focused security is
`3/3`; the exact CI entrypoint `scripts/verify.sh --repository` then passes
locally with all `2590` workspace tests and the direct-SQL scan. No product,
scanner, allowlist or threshold changes.

## Non-scope and next gate

This checkpoint creates no route, repository writer, persisted row, queue,
adapter, target call, UI behavior or production contact. Its exact-SHA Gate is
now closed. Checkpoint 2 is limited to Project-first read/DLQ projections and
fixed operation-specific replay and reconciliation-request commands under the
frozen plan.
