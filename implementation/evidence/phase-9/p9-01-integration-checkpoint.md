# P9-01C Reliable Engineering Change Integration Checkpoint

Status: `IMPLEMENTED — EXACT-SHA ORDINARY CI PENDING`

## Accepted governance Gate

Exact SHA `83f35dde9d9ecc4f6d7f7a82c35559e8903bad4d` passes ordinary CI
`33358374034`: repository `99384778320`, secret `99384778406`, frontend
`99384778467` and governed visual `99384778501` all pass. That Gate authorizes
only the operation-specific, default-disabled P9-01C seam frozen here.

## Implemented boundary

- Signed inbound `npi.erp-engineering-change.v1` with exact tenant/key,
  timestamp, nonce, Project, formal ECR ID, source version/hash, actor, trace
  and idempotency validation.
- Dedicated immutable Inbox receipt and one privileged formal-observation link
  into the existing P9-01 change aggregate.
- Versioned `npi.change-implementation-summary.v1` request with dedicated
  request, Outbox, attempt and sealed result records.
- Explicit duplicate, reorder, identity conflict, partial, 429, 5xx,
  pre-boundary failure and timeout-after-commit uncertainty behavior.
- Read-only Project-first P8-07 operation list/detail/history projection for
  `receive_engineering_change_event` and
  `publish_change_implementation_summary`; no replay action is exposed.

## Ownership and safety

ERPNext remains owner of the formal ECR identifier, raw lifecycle and
transaction-effective truth. LaunchFlow remains owner of impact assessment,
affected engineering versions, revalidation evidence, Gate effects and the
immutable integration ledger. Profiles and adapters are disabled by default.
Synthetic disposable-Site execution is `synthetic_verified`, not formal
success. Partial and uncertain outcomes are terminal and never automatically
redispatched.

The slice adds no production endpoint or credential, production call, direct
SQL, permission bypass, generic DocType writer, browser-direct ERP access,
cross-database write, ERP/Frappe core change or dual-master field. Actor-bound
capabilities guard every support-record insert/save; forged flags fail closed.
Rollback disables routes, scheduler/profile/adapter configuration and preserves
the immutable audit/integration history for forward repair.

## Contract and verification evidence

OpenAPI, event schema and data-ownership contracts describe the exact routes,
events, operation kinds and owner fields. Tests cover closed shapes, signature
and replay, nonce/timestamp/key failures, Project containment, service actor,
idempotency, transaction order/rollback, result authentication/contract
validity, lease recovery, response classes and no-leak diagnostics.

Level 1 passes:

- focused P8/P9 integration tests: `108/108`;
- full repository Python: `2789/2789`;
- frontend unit/coverage: `1086/1086`;
- TypeScript, complete lint and i18n: `8708` governed sources, `100%` zh/zh-TW;
- generated catalog freshness and production bundle compilation;
- current-task/V1.2 reconciliation, Python compilation and diff checks.

The implementation is not accepted until its exact-SHA ordinary CI passes all
four repository, frontend, secret and governed visual lanes. P9-01D UI,
production adapter/profile activation and any ERPNext change remain out of
scope.
