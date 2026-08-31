# P9-01C Reliable Engineering Change Integration Checkpoint

Status: `ACCEPTED — EXACT-SHA ORDINARY CI PASS`

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

Implementation exact SHA `0c11b1f378b1c962b6d05739f3c1f3cad18ad389`
passes ordinary CI `33363140068`: visual `99398340139`, secret
`99398340217`, frontend `99398340305` and repository `99398340322` all pass.
P9-01C is accepted at this exact default-disabled boundary. P9-01D UI,
production adapter/profile activation and any ERPNext change remain separate.

P9-01D governance exact SHA
`0e46d2d294176571fe620d6760151fb4df56fd13` and ordinary CI `33364478666`
accept the later UI/runtime manifest. The implemented workspace only consumes
this checkpoint's existing operation-specific boundaries; it does not change
the signed event, summary contract, worker/retry semantics or production
activation state. The fixed disposable-Site verifier adds cumulative proof,
not a new target adapter or an ERP success claim.

## P9-01D inbound-full diagnostic boundary

Post-optional-empty controlled run `33423616127` returned only
`P901_CHANGE_INBOUND_HTTP / RuntimeError /
trace-d75d7f003059503887df977d4602721a`. This proves the fresh lifecycle
reached the exact signed inbound request, but the outer code still spans HTTP
transport/response, signature/profile handling, repository receipt/audit,
commit and enqueue. Restricted values and failed-child output remain unread,
so no integration repair is authorized.

The independent inbound-full diagnostic keeps all production profiles and
targets disabled and adds only exact request-scoped safe stages. Its exact 134
allowlist combines the prior 100 with a complete inbound transport/status/
header/body family and ordered API/repository stages. Server-inner records win
over parent fallbacks through the existing exact-three `O_EXCL` writer. No
event, ownership, permission, write order, retry, replay, queue or target
behavior changes.

Level 1 passes focused current/API/repository/runtime `56/56`, affected
integration security/contract/domain/runtime `23/23`, full repository
`2821/2821`, current/reconciliation, repository verification, frontend
generation and i18n (`8774` literal English sources with `100%` zh/zh-TW
coverage), compilation, shell syntax, exact-16 and projected union-58
manifests, unauthorized-17 rejection, security and diff hygiene. Exact-SHA
ordinary PASS must precede the cycle's sole Level 2 diagnostic.

## Inbound raw-body binding repair

Inbound-full controlled run `33428760121` returned only
`P901_CHANGE_INBOUND_API_FIELDS / RequestValidationFailed /
trace-b2c50272c5e155e595791f7522df27f2`. The BFF's only synthetic form value is
the already-excluded `cmd` transport field; the remaining unexpected keys can
only arise because the raw signed JSON method admitted Frappe's parsed body as
`**request_fields`. This occurs before signature/profile/repository work and
is not an event-contract or ERP result failure.

The minimal repair matches the accepted P8-02 signed raw-body boundary: the
public handler accepts no keyword fields and authenticates the exact raw body.
Signature, schema, Project containment, profile/principal, repository write
order, commit/enqueue, replay and response semantics are unchanged. The
inbound-full cycle is `1/1,1/1,0/1`; all diagnostic activations are disabled
before exact-SHA ordinary CI and the sole Level 3.

Level 1 passes focused repair/current/runtime `41/41`, affected P8/P9
security/contract/domain/runtime `121/121`, full repository `2822/2822`,
current/reconciliation, repository verification, frontend generation and
i18n (`8774` literal English sources with `100%` zh/zh-TW coverage),
compilation, shell syntax, exact-12 and projected union-58 manifests,
unauthorized-13 rejection, all-diagnostics-off, security and diff hygiene.

## Post-raw-body combined runtime boundary

Raw-body repair SHA `20a3d7d1` passed ordinary `33430715697`, but its sole
diagnostics-off Level 3 `33432150853` failed only inside the Engineering
Change runtime after fixed Bench/Site initialization. Fixed-source filtering
matched exactly the Engineering Change runtime label; restricted raw,
response, business and child content remained unread. The repaired cycle is
frozen at `1/1,1/1,1/1`.

The independent product-zero post-raw-body cycle starts `0/1,0/1,0/1`. Its
new-only activation reuses exact 134 across the complete outer/revise/inbound
API/repository chain with the same exact request scope, deterministic trace,
`O_EXCL` exact-three record and inner-first precedence. Integration event,
ownership, permission, write order, retry, replay, queue and target behavior
remain unchanged.

Level 1 passes focused current/API/runtime `41/41`, affected P8/P9
security/contract/domain/runtime `121/121`, full repository `2822/2822`,
current/reconciliation, repository verification, frontend generation and
i18n (`8774` literal English sources with `100%` zh/zh-TW coverage),
compilation, shell syntax, exact-12 and projected union-58 manifests,
unauthorized-13 rejection, new-only activation, security and diff hygiene.
Exact-SHA ordinary PASS must precede the sole Level 2 diagnostic.
