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

## P9-01D post-summary-ordering-repair combined boundary

Exact repair SHA `d7588537935aa600431c2f068e1d12370e1686dd` passes ordinary
`33468779480`. Level 3 `33469740238` passes frontend, repository, visual,
secret scan and controlled preflight; cumulative runtime `99739301277`
returns only the fixed Engineering Change failure label. Restricted response,
child and business content remains unread.

The prior lifecycle-ordering root is closed, while this all-off boundary is
nonunique. Freeze its cycle `1/1,1/1,1/1` without a guessed product repair.
The new independent product-zero cycle begins `0/1,0/1,0/1` and reuses exact
144 with one new-only activation, deterministic trace/scopes, first-wins
recording, strict reader and success-zero behavior. No contract, ownership,
permission, transaction or production behavior changes.

Level 1 passes focused `43/43`, full Python/formal repository `2826/2826`,
current/reconciliation `40/40`, generation/i18n, compile, shell and diff
checks. Exact-12/union-63 are bounded, unauthorized-13 is rejected and only
the three new activation declarations are true.

### Close diagnostic harness repair

Controlled `33472407245` on exact SHA `f1f4f154d669f620b1ff342b0d39bd6036ac1557`
returns only `P901_CHANGE_CLOSE_HTTP / RuntimeError /
trace-d238a503a469549e9301fbb514ed75e1`. The close request could not activate
the existing successor API/repository recorder because its header and exact
operation predicate were revise-only. The sole harness repair reuses those
bounded stages for exact close traffic under the new-only activation; writes,
transactions, permissions, contracts and production behavior are unchanged.

Level 1 passes focused `45/45`, full Python/formal repository `2828/2828`,
current/reconciliation `40/40`, generation/i18n, compile, shell and diff
checks. Exact-10/union-63 remain bounded and unauthorized-11 is rejected.

### Close root-save compatibility repair

Close diagnostic harness SHA `e7ec25df51a0c0e20734a0241eb8469a65001575`
passes ordinary `33473366675`. Its bounded controlled continuation
`33604786538` passes preflight `100166203654`; runtime `100166287249` returns
only `P901_CHANGE_REVISE_REPOSITORY_ROOT_SAVE / PermissionError /
trace-4e8170524143592caf9721192a5e6312`. Restricted integration output remains
unread.

The integration transaction and formal observation were already valid. The
failure was a local root-controller comparison mismatch between Frappe's
previous `datetime` object and the equal database string applied by the close
repository. Canonicalizing those two Datetime values only for the permission
comparison preserves ERP ownership, signed inbound facts, Inbox/Outbox,
idempotency, replay, summary projection, contracts and operation ordering.
There is no ERPNext or production change.

All 39 diagnostic declarations are off. The cycle is diagnostic `1/1`, harness
repair `1/1`, product repair `1/1`, final `0/1`; exact-SHA ordinary must pass
before the sole diagnostics-off Level 3. Level 1 passes focused `49/49`, full
repository `2828/2828`, current/reconciliation `40/40`, complete i18n and
security/diff checks. Exact-14/union-63 remain bounded and unauthorized-15 is
rejected.

### Post-formal-Datetime-repair integration diagnostic

Repair SHA `2d7a76d02893f36c004a064bff6c1a84c8c608e8` passes ordinary
`33607597980`. Its sole diagnostics-off Level 3 `33608430759` passes all base
lanes and preflight, then cumulative runtime `100181028119` emits only the
fixed Engineering Change outer label. Restricted integration output remains
unread.

The label cannot distinguish a later API, repository, Inbox, summary or
operation predicate, so no integration repair is inferred. The closed repair
cycle is `1/1,1/1,1/1,1/1`; an independent product-zero exact-144 diagnostic
starts at `0/1,0/1,0/1` with only three new declarations active across the
runtime/core/integration recorder chain. Signed facts, ownership, contracts,
permissions, queues, replay, reconciliation, CI and production behavior remain
unchanged.

### Implementation-summary diagnostic harness repair

The exact-144 diagnostic checkpoint
`f5d95e28aa64750e8cca9274af55bec9320a5015` passes ordinary
`33610959690`. Its controlled continuation `33612235309` passes preflight and
the close boundary, then returns only `P901_CHANGE_SUMMARY_HTTP /
RuntimeError / trace-41530fdeb7fd581d89d9a43c98fadb5c`. No restricted
response, status, business value, identifier, message, stack or failed child
output was read.

Requester role, support-DocType permissions, predecessor state, required
fields and exact Link targets pass static same-family preflight. The remaining
outer label is still nonunique across the summary API/repository transaction,
so no product fix is inferred. One bounded harness repair adds twenty-nine
fixed summary API/repository stages and exact initial/replay header admission
under the existing new-only activation. The safe set is exact 173 with 94
server stages; the writer remains exact-name, `O_EXCL`, mode `0600` and
code/type/trace-only.

Focused runtime/core/integration tests pass `52/52` and complete Python/formal
repository tests pass `2833/2833`. No event, API response, schema, permission,
transaction, ownership, worker, adapter, retry/replay, UI, CI or production
behavior changes. Exact-SHA ordinary PASS must precede the one bounded
controlled continuation.

Level 1 passes focused `38/38`, full repository `2828/2828`, current/
reconciliation `40/40`, complete i18n, security and diff checks. Exact-12/
union-63 remain bounded and unauthorized-13 is rejected.

## P9-01D Inbox replay identity repair

Post-datetime diagnostic SHA `dfea79d20844cbccbada9de342e7623624ab24c4`
passes ordinary `33462460736`. Sole Level 2 `33463349508` returns the strict
safe tuple `P901_CHANGE_INBOUND_REPOSITORY_INBOX_SQL_OTHER /
UniqueValidationError / trace-a78a62694fe55a8f9cfae7d9d761a3d7` from runtime
`99718091378`; restricted content remains unread.

The Inbox controller and metadata use `receipt_id` as the document name while
`event_id` is a separate unique idempotency field. Exact replay previously
looked up the event ID as a document name, guaranteeing a miss followed by a
duplicate unique-field insert. The repair performs a bounded exact
`event_id`-to-name lookup, rejects multiple results, and loads the original
receipt by its real name. The test fake now enforces both query filter and
document name, preventing this class of false replay success. No integration
contract, persistence schema, write authority, queue or target behavior is
changed. All diagnostics are off and the cycle is `1/1,1/1,0/1` pending final
Level 3.

Level 1 passes focused `49/49`, full Python/formal repository `2826/2826`,
current/reconciliation, frontend generation and complete `8774`-source i18n,
compile, shell and diff checks. Exact-14/projected union-60 are accepted,
unauthorized-15 is rejected and all 33 diagnostic declarations are false.

## Post-replay-identity-repair combined runtime boundary

Repair SHA `1e8b2a667adf4df510587edba6e50c43c2899e30` passes
ordinary `33464452876`. Its sole Level 3 `33465390683` passes base jobs and
preflight, while runtime `99726596791` emits only the fixed safe Engineering
Change failure label. Restricted raw, child, response and business content
remains unread. The repaired replay identity root is closed, but the all-off
label cannot select the remaining internal predicate; freeze the repair cycle
`1/1,1/1,1/1`.

The new product-zero combined cycle begins `0/1,0/1,0/1` and reuses exact 144
with one new-only activation, deterministic trace, exact request scopes,
`O_EXCL` exact-three record, strict reader and inner-first precedence. Event,
ownership, permission, idempotency, replay, queue, adapter and production
contracts do not change.

Level 1 passes focused `43/43`, full Python/formal repository `2826/2826`,
current/reconciliation, frontend generation and complete `8774`-source i18n,
compile, shell and diff checks. Exact-12/projected union-60 are accepted,
unauthorized-13 is rejected and only the three new declarations are active.

## Summary lifecycle ordering repair

Post-replay diagnostic SHA `292c0273397920fe0b5808caabe31b5a23306346`
passes ordinary `33467097198`. Sole Level 2 `33467957736` returns the strict
safe tuple `P901_CHANGE_SUMMARY_HTTP / RuntimeError /
trace-e7cfe8eb47fd594f805abcb8374ae8f5`; restricted content remains unread.

The integration repository requires summary source truth to be the exact
closed current revision. Runtime had revision 3 `ready_to_close` and placed
close after summary, although close produces the revision-4 predecessor already
used by summary API tests. Move only the disposable verifier's close proof
before summary and preserve all subsequent worker, replay and operations
checks. Integration product code, event contracts, persistence, permissions,
idempotency and queues are unchanged. Diagnostics are all off; cycle state is
`1/1,1/1,0/1` pending final Level 3.

Level 1 passes focused `43/43`, full Python/formal repository `2826/2826`,
current/reconciliation, frontend generation and complete `8774`-source i18n,
compile, shell and diff checks. Exact-12/projected union-60 are accepted,
unauthorized-13 is rejected and all 36 diagnostic declarations are false.

## Post-loopback-repair combined runtime boundary

Loopback repair SHA `c49a8e3ef84194eab1ea10b82acfefbd33f50321`
passes ordinary `33445857640`. Its sole diagnostics-off Level 3
`33446974525` passes four base jobs and controlled preflight `99671412959`;
runtime `99671491574` fails only at the cumulative Engineering Change
boundary. The source-derived allowlist matches exactly the fixed Engineering
Change runtime failure label; restricted content remains unread.

Freeze the repaired loopback cycle at `1/1,1/1,1/1`. A new independent
product-behavior-neutral cycle starts `0/1,0/1,0/1`; only the new
post-loopback-repair runtime/API activations are true. Exact 134 safe codes,
deterministic trace, exact scopes, `O_EXCL` exact-three recording, strict
reader, inner-first precedence, failed-output-unread and success-zero
contracts are unchanged. Integration ownership, event, permission,
idempotency, replay, queue, adapter and production contracts do not change.

Level 1 passes focused current/API/runtime `42/42`, affected P8/P9
security/contract/domain/runtime `122/122`, full repository `2823/2823`,
current/reconciliation and formal repository verification, frontend
generation and i18n (`8774` literal English sources with `100%` zh/zh-TW
coverage), compilation, shell syntax, exact-12 and projected union-60
manifests, unauthorized-13 rejection, new-only activation, security and diff
hygiene.

## Readiness service-actor harness repair

Diagnostic SHA `8986d71394611f085585fd6f228b15556ea25de0` passes
ordinary `33449264009`; sole Level 2 `33450160475` returns the unique safe
tuple `P901_CHANGE_INBOUND_REPOSITORY_WRITE_SCOPE / PermissionError /
trace-292218cf3a9e51489ad3b550542cffb5`. The restricted failure content remains
unread.

The bound worker was the retained P8-02 inbound actor, whose fixture contract
requires `NPI API User` and excludes `System Manager`. P9's actor-bound write
scope intentionally requires both roles before any write. Bind the P9
synthetic worker instead to the retained P7 readiness manager already proven
as an enabled System User with both roles in the same cumulative Site. No
permission relaxation, product contract, event, queue, adapter or production
change is authorized. All diagnostics are false; cycle state is
`1/1,1/1,0/1` pending the sole Level 3.

Level 1 passes focused repair/current/API/runtime `43/43`, affected P8/P9
security/contract/domain/runtime `123/123`, full repository `2824/2824`,
current/reconciliation and formal repository verification, frontend
generation and i18n (`8774` literal English sources with `100%` zh/zh-TW
coverage), compilation, shell syntax, exact-13 and projected union-60
manifests, unauthorized-14 rejection, all-24-diagnostics-off, security and
diff hygiene.

## Post-service-actor-repair combined runtime boundary

Repair SHA `513e7e86c55220ef461cd324f746c9bfe660b6d1` passes
ordinary `33451200775`. Sole diagnostics-off Level 3 `33452193414` passes
four base jobs and preflight, then runtime `99686520697` returns only the
fixed Engineering Change failure label. Restricted content remains unread.
The role mismatch root is closed; the remaining first source is nonunique, so
freeze the repair cycle `1/1,1/1,1/1` without inference.

Open an independent product-behavior-neutral cycle at `0/1,0/1,0/1`. Only
the new post-service-actor-repair runtime/API activations are true; exact 134,
trace, scope, exact-three record, strict reader and inner-first precedence are
unchanged. Integration ownership, permissions, events, queue, adapter and
production behavior remain unchanged.

Level 1 passes focused `43/43`, affected integration/P9 `123/123`, full
Python `2824/2824`, the formal repository verifier, current/reconciliation,
frontend generation and complete `zh`/`zh-TW` i18n, compile, shell and diff
checks. Exact-12 remains within projected union-60 and an unauthorized
thirteenth path is rejected.

## Inbox insert SQL-class boundary

Post-service-actor SHA `3453ef66a9b49f160dcb54cde6ab7e52be36f8dd`
passes ordinary `33453886007`. Controlled run `33454878580` returns only
`P901_CHANGE_INBOUND_REPOSITORY_INBOX_INSERT / OperationalError /
trace-915a7a055a4159b4b892e22b4c552d9b`; no restricted output is read. The
actor/permission root is closed, while the database first source remains
nonunique, so that cycle freezes `1/1,0/1,0/1`.

One new-only product-neutral activation classifies a bounded numeric database
error into ten fixed labels (or `OTHER`) and re-raises it. Exact 144 keeps
inner-first recording and all existing trace/O_EXCL/strict-reader contracts;
integration ownership, payload and write order do not change.

Level 1 passes focused `48/48`, affected integration/P9 `124/124`, full
Python and formal repository verification `2825/2825`, governance,
reconciliation, generation, i18n, compile, shell and diff checks. Exact-14
and projected union-60 are accepted; an unauthorized fifteenth path is
rejected.

SQL-class SHA `fbaa7b17af389955e9a33ed664f331ed91be7459` passes ordinary
`33456066308`; controlled `33456992129` falls back to outer `WRITE_SCOPE /
OperationalError / trace-b64cfa8266de5dea8b317b4916e9cfb6`. The mapper and
reader contain all ten new safe codes, but the core recorder fixed allowlist
does not, so the child record is intentionally rejected. This is a
product-neutral diagnostic harness defect; add the exact ten recorder codes
and keep the diagnostic counter at zero until a trusted SQL-class tuple is
obtained.

Recorder-repair Level 1 passes focused `60/60`, affected `124/124`, full
Python/formal repository `2825/2825`, current/reconciliation,
generation/i18n, compile, shell and diff checks. Exact-8 remains bounded by
projected union-60; unauthorized-9 is rejected.

## Physical Datetime repair

Exact recorder SHA `33d017ec09fd82fa8a397abf47c5d44fa5e8cd2d`
passes ordinary `33457876877`; controlled `33458827576` returns only
`INBOX_SQL_DATETIME / OperationalError /
trace-9e7b667c34ab5adfbfd86417e0cf6c5c`. Fixed class `1292` and lexical order
prove the first physical Inbox insert received unnormalized aware datetimes.

Normalize the two Inbox and two same-root Summary Request physical Datetime
fields with the existing repository seam. Canonical payloads, UTC snapshots,
hashes, roles, transaction order, replay, Inbox/Outbox semantics and external
behavior do not change. Diagnostics are all false; cycle state is
`1/1,1/1,0/1`.

Level 1 passes focused `61/61`, affected `125/125`, full Python/formal
repository `2826/2826`, current/reconciliation, frontend generation and
`8774`-source complete i18n, compile, shell and diff checks. Exact-14 remains
within projected union-60, unauthorized-15 is rejected and all thirty
Engineering Change diagnostics are off.

## Post-datetime-repair combined boundary

Repair SHA `2326b977754b78ebce6a39766c937a7cb8d12cab` passes ordinary
`33459791960`. Diagnostics-off Level 3 `33460716573` passes the base jobs and
preflight, then runtime `99712852126` returns only the fixed Engineering
Change outer failure label. No restricted content was read. The repaired
Datetime root remains closed, while the later first source is nonunique.

Freeze the repair cycle `1/1,1/1,1/1` and open an independent product-zero
exact-144 cycle `0/1,0/1,0/1`. One new-only post-datetime activation enables
the existing bounded runtime/core/integration recorder chain; ownership,
event contracts, permissions, writes and production behavior do not change.

Level 1 passes focused `43/43`, affected `125/125`, full Python/formal
repository `2826/2826`, governance/reconciliation, frontend generation and
complete i18n, compilation, shell and diff checks. Exact-12/projected
union-60 are accepted, unauthorized-13 is rejected and activation is
new-only across runtime/core/integration.

## Disposable loopback transport repair

Exact diagnostic SHA `48dcd3d9007d91f95c1d95ad4d2ba3e4d917d0df`
passes ordinary `33442412785`. Sole Level 2 `33443753239` returns only the
strict safe tuple `P901_CHANGE_INBOUND_API_AUTHENTICATE / NpiProblem /
trace-c1e7e74e4289536e8b4ee897d06a2cdf`; restricted content remains unread.

The fixed verifier uses `http://127.0.0.1:8003`, and the API deliberately
does not trust `X-Forwarded-Proto`. The repair therefore remains inside the
guarded synthetic harness: exact enabled environment, shared disposable Site
marker, POST, webhook path, empty query, loopback peer and fixed host are all
required before local HTTP can satisfy transport. All other traffic still
requires the server's secure-request fact. No Sandbox or production profile,
secret, adapter, contract, permission, ownership, write, replay or queue
behavior changes. The cycle is `1/1,1/1,0/1`, diagnostics off, final Level 3
pending.

Level 1 passes focused repair/current/API/runtime `48/48`, affected P8/P9
security/contract/domain/runtime `122/122`, full repository `2823/2823`,
current/reconciliation and repository verification, frontend generation and
i18n (`8774` literal English sources with `100%` zh/zh-TW coverage),
compilation, shell syntax, exact-14 and projected union-60 manifests,
unauthorized-15 rejection, all 21 diagnostics off, security and diff hygiene.
Exact-SHA ordinary PASS must precede the sole Level 2 diagnostic.

## Disposable runtime marker repair

Exact diagnostic SHA `cc17b5ffd38801abb07f564d6671777af7bf4a6b` passes
ordinary `33435386410`. Sole Level 2 `33436775999` passes preflight and the
strict exact-134 reader returns only
`P901_CHANGE_INBOUND_API_AUTHENTICATE / NpiProblem /
trace-7f19d6ce03cf5328ac2cd1d17b379d39`; restricted content remains unread.

Static cross-proof identifies the synthetic fixture's stale marker as the
first source: it required `npi-one-engineering-change-disposable-v1`, while
the fixed Site and cumulative runtime use
`npi-one-local-runtime-disposable-v1`. Profile activation therefore failed
before secret/signature verification. The repair aligns only the network-free
synthetic fixture with the existing shared disposable marker, adds a negative
stale-marker assertion, and turns all diagnostics off. Integration event,
ownership, permission, idempotency, replay, queue, adapter and production
contracts remain unchanged. Cycle state is `1/1,1/1,0/1` pending the sole
Level 3.

Level 1 passes focused repair/current/API/runtime `44/44`, affected P8/P9
security/contract/domain/runtime `121/121`, full repository `2822/2822`,
current/reconciliation, repository verification, frontend generation and
i18n (`8774` literal English sources with `100%` zh/zh-TW coverage),
compilation, shell syntax, exact-14 and projected union-60 manifests,
unauthorized-15 rejection, all eighteen diagnostic activations off, security
and diff hygiene.

## Post-marker-repair combined runtime boundary

Marker repair SHA `b28e7cd276fe1fe2774c2539edbb521b17bcd172` passes
ordinary `33438745063`. Its sole Level 3 `33439824471` passes the ordinary
lanes and preflight, while runtime `99649098941` emits only the fixed safe
Engineering Change failure label. Restricted raw/child/response/business
content remains unread. The repaired marker root is closed, but the all-off
label cannot safely select a later integration predicate, so that cycle is
frozen `1/1,1/1,1/1` without a guessed repair.

The new product-zero post-marker-repair cycle begins `0/1,0/1,0/1` and
reuses exact 134 with one new-only activation, deterministic trace, exact
request scopes, `O_EXCL` exact-three record, strict reader and inner-first
precedence. Event, ownership, permission, idempotency, replay, queue, adapter
and production contracts remain unchanged.

Level 1 passes focused current/API/runtime `41/41`, affected P8/P9
security/contract/domain/runtime `121/121`, full repository `2822/2822`,
current/reconciliation, repository verification, frontend generation and
i18n (`8774` literal English sources with `100%` zh/zh-TW coverage),
compilation, shell syntax, exact-12 and projected union-60 manifests,
unauthorized-13 rejection, new-only activation, security and diff hygiene.
