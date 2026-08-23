# P8-04 Checkpoint 4 — MBOM Execution Inspector

Recorded: `2026-08-22`

Status: `FINAL LEVEL 3 NARROWING — SERVER CREATE DIAGNOSTIC ACTIVE`

## Scope and truth boundary

- Extends the existing Phase 5 released-EBOM workspace with one dense,
  direct-trilingual MBOM execution inspector for the exact selected Phase 5
  publish request. It does not add a generic operations screen or a second App
  Shell.
- The fixed Project-first list query is scoped by
  `phase5PublishRequestGlobalId`; list and detail projections revalidate tenant,
  Project, request, source/topology/mapping hashes, node manifest, attempt,
  aggregate Result, per-node Result and current mapping-head evidence. Missing,
  detached, duplicate or inconsistent evidence fails closed.
- A formal BOM ID and target version are rendered only from a current mapping
  that matches an authenticated `authoritative_sandbox` node result and only
  after Project/view authorization. Mock, synthetic, failed, conflict,
  uncertain and unauthenticated truth cannot carry formal identity. Partial
  truth remains per-node: an authoritative successful node may show its exact
  current mapping while sibling failure remains explicit; no aggregate success
  is invented.
- The one visible-text primary action opens Impact Review and sends only the
  exact Phase 5 request ID, four expected hashes and the literal governed
  acknowledgement through the NPI BFF. CSRF, actor-bound idempotency replay,
  request/trace echo and private-no-store remain required. The browser has no
  ERPNext/JCE endpoint, credential, target payload, retry, reconcile or submit
  path.

## Industrial UX and localization

- The inspector preserves the classic light App Shell, flat square borders,
  neutral dense evidence grid, compact four-column engineering table,
  non-color status shape/icon/text and stable right-side EBOM inspector. It
  adds no card wall, gradient, large radius, shadow or decorative asset.
- Covered states are loading, empty, unavailable, no permission, read-only,
  Mock, queued, processing, synthetic, partial, retryable/final failure,
  conflict, uncertainty, submitted immutability and authoritative Sandbox
  observation. Primary action eligibility is fail-closed for missing session,
  permission, profile, context, readiness, immutable/active/uncertain truth or
  submitted expectation.
- Every new source string is a literal English `t()` source with direct Frappe
  CSV entries for `zh` and `zh-TW`. The Frappe v15 no-header catalogs and
  generated catalog remain synchronized; retained `EBOM`, `MBOM`, `BOM`,
  `ERPNext`, `ID`, `CSRF`, hashes and business identifiers follow the governed
  terminology rules.
- Keyboard activation/focus return, Impact Review acknowledgement, WCAG axe,
  non-color status, single-primary, industrial computed-style, overflow and
  mixed-language checks are part of the browser cases.

## Fixed-Linux visual evidence

Only these three checkpoint baselines are governed; no Darwin baseline is in
task scope:

| Case | SHA256 |
|---|---|
| `p8-04-mbom-synthetic-en-1366x768-125-linux.png` | `c8e2801b96538eaf40b5011577ed0e9158ce0c53a586c9a8a6640898035e005e` |
| `p8-04-mbom-partial-zh-1920x1080-150-linux.png` | `2a73fbb89586c83553b8955454f294eaff85445131605fc4b7c8c89bc35efa4a` |
| `p8-04-mbom-authoritative-zh-TW-1920x1080-125-linux.png` | `1819e3878882e2dbf26d1c83e8a6aee9748016dd65d56f1537a0cc6e85a02ee2` |

The three baselines pass exact zero-diff Linux verification. They show
synthetic no-formal truth, mixed authoritative/failed partial truth and two
current authoritative formal BOM identities respectively. In the `zh` 150%
case, the narrow inspector stacks Impact Review vertically without truncating
the primary action, and the horizontally governed table position exposes the
complete per-assembly outcome phrase rather than an icon-only fragment.

## Changed-files to affected-checks map

| Changed boundary | Affected evidence |
|---|---|
| Frappe MBOM read repository, BFF handler and OpenAPI | exact Phase 5 list containment, strict request/node/attempt/result/current-head integrity, IDOR/permission and no-write repository/API/contract tests |
| MBOM frontend data source | exact fixed routes/query, private trace/request contract, CSRF/idempotent command, detached evidence, aggregate mismatch, redacted no-view and no-formal synthetic validation tests |
| EBOM workspace composition and styles | complete state matrix, one primary action, Impact Review, no retry/reconcile/submit, keyboard/focus, non-color and industrial density checks |
| translations and generated catalog | Frappe CSV parsing, literal extraction, direct `zh`/`zh-TW` coverage, terminology and mixed-language audit |
| P8-04 browser fixture/E2E and three Linux images | trilingual state, zero target access, exact command headers/body, submitted guard, axe/overflow/single-primary/style and exact visual comparison |
| controller and checkpoint evidence | checkpoint 3 exact SHA/CI/jobs/artifact digests, checkpoint 4-only authority and retained production/Sandbox/P8-07/P8-05..09 holds |

## Pre-commit Level 1 evidence

- MBOM repository/API/domain/contract/config/metadata/security/adapter/worker/runtime:
  `88/88`; complete P8-03 Item publish regression: `146/146`; complete affected
  Phase 5 regression: `363/363`.
- Frontend MBOM data-source and workspace focus: `64/64`; complete frontend unit
  suite: `1,046/1,046`; browser behavior for `en`, `zh` and `zh-TW`: `6/6`.
- The three governed Linux visual cases pass exact zero-diff comparison after
  axe, overflow, single-primary, industrial-style and mixed-language checks.
  Their SHA256 values are the fixed values recorded above; no Darwin image is
  checkpoint evidence.
- TypeScript typecheck, ESLint, Prettier, Stylelint, frontend boundary/UI
  audits, generated artifact check and Frappe i18n audit pass. The i18n audit
  covers `8,183` literal English sources with `100%` direct `zh`/`zh-TW`
  coverage.
- Current-task and V1.2 reconciliation verifiers, controller/foundation tests
  (`47/47`), changed Python compilation and `git diff --check` pass. No
  production ERPNext/JCE endpoint, credential or request was used.

## Ordinary CI legacy-fixture remediation

- Candidate `a62d5ebaf28ffa4a8fd9482dadce4870e4669e77` reached ordinary CI
  `32514627234`. Repository `96873370223` and secret `96873370244` passed;
  frontend `96873370008` passed the full frontend verifier before `23` E2E
  failures, while visual `96873370234` reported `116` pass and `7` failures.
- The `30` failures are derived from one fixture-only root. The existing strict
  P5-05 and P8-03 route fixtures rejected the newly composed fixed MBOM list
  GET before those legacy pages could reach their assertions. No product API,
  UI, permission, transaction, response or visual-baseline defect was shown.
- The remediation admits only `GET` on the exact Project MBOM collection with
  the sole exact `phase5PublishRequestGlobalId` query. It reuses the validated
  MBOM fixture shape in a default-disabled, empty state with no formal IDs;
  every other request remains an unhandled-request failure. The response-
  neutral fixture remediation consumes no product repair round.
- Final Level 3 remains closed until a remediated exact-SHA ordinary CI passes.

The frozen checkpoint deliberately keeps the new MBOM inspector in the
existing released-EBOM workspace and reserves its visible-text request action
as the single primary action. Consequently, the following seven existing
fixed-Linux baselines receive an approved semantic migration; no Darwin image,
product behavior or visual threshold changes:

| Existing governed case | SHA256 |
|---|---|
| `p5-05-publish-request-en-1366x768-100-linux.png` | `1c2a11edbd7a7d137fe29376b873cf7dc1478299cc76ed12f740434ecbf92ee3` |
| `p5-05-publish-request-zh-1440x900-125-linux.png` | `fb28b7e2468ce37ff08c471145bbfb21ba4b4cea2bfe1b5dd289348cf9bd93b7` |
| `p5-05-publish-request-zh-TW-1920x1080-150-linux.png` | `36cf14ad797bffcb550be429e6321b63cb2bbc2887bd3d0626703ff41596eaf0` |
| `p8-03-item-synthetic-en-1366x768-100-linux.png` | `c7b1e71c5c8f0147b0f34424a7e93b713f6b175fadb0a54a12ffc65ff3696a41` |
| `p8-03-item-uncertain-zh-1440x900-125-linux.png` | `8b237ec7b055467d33423228204c641a3a732d09c30a6a6b6d91dad26a300f14` |
| `p8-03-item-authoritative-zh-TW-1920x1080-150-linux.png` | `f6b0f629c7c9de215ea5d3fce250588221ccf29ea5c9ac0481364d8cbe913faf` |
| `p8-03-item-inactive-en-1366x768-100-linux.png` | `024b6d283919d7b33a3722ccf8b9284193dfb300335abc94290a55ae5866d88f` |

Manual review confirms the flat, square, neutral composition; retained EBOM
and Item context; secondary legacy actions; visible disabled MBOM reason; no
MBOM formal identity in the empty fixture; direct `en`/`zh`/`zh-TW` text with
no unapproved mixing; and usable 125%/150% layouts.

Canonical visual evidence is now generated only in the ordinary workflow's
exact Linux/amd64 bookworm, Node `24.18.0`, Playwright `1.61.1` environment.
All three P8-04 baselines are normalized to that canonical renderer after the
visual-only harness applies one deterministic final scroll anchor. Two
consecutive focused `10/10` no-update runs prove zero position drift. The
workflow governs all three P8-04 images, increasing the cumulative visual
matrix from `123` to `126`, and publishes them in the visual artifact.

The remediated canonical Level 1 evidence passes `29/29` affected nonvisual
browser cases and `126/126` governed visual cases. The complete frontend
suite passes `1,046/1,046` unit tests with coverage, production build, brand
audit and both dependency audits; source localization remains `8,183` direct
English literals at `100%` `zh`/`zh-TW` coverage. All `317` runtime-verifier
tests, the focused controller/reconciliation set, current-task verification,
JSON/YAML parsing, changed Python compilation and `git diff --check` pass.

The controlled runtime already executes the MBOM verifier's default-disabled
and network-free fresh Synthetic stages after the retained P8-03 source. Its
job/step/result attestation now records current
`scope=p5-01-through-p8-04` and
`predecessor_scope=p5-01-through-p8-03`; the prior P8-03 scope remains an
explicit predecessor contract rather than being deleted.

## Rollback

Remove the MBOM inspector/data source and disable its request action while
retaining every Phase 5 release, MBOM request, node, idempotency row, Outbox
event, attempt, aggregate/node result, uncertainty, observation, current
mapping head and audit. The read projection and UI may be rolled back without
target compensation. Never delete or rewrite observed truth, blindly
redispatch a crossed boundary, change a formal BOM identity, submit/overwrite a
BOM or contact production ERPNext/JCE.

Checkpoint 4 implementation has passed exact-SHA ordinary CI. Final Level 3
remains open only for the bounded controlled-runtime narrowing recorded below.

## Exact-SHA ordinary and first final Level 3 evidence

- Exact checkpoint SHA `4e9c8d6577e503087ec137a6b1144858c21e38fb`
  passes ordinary CI `32523149643`: repository `96899549039`, frontend
  `96899549122`, secret `96899549195` and canonical `126/126` visual
  `96899549250` pass.
- The only unchanged final Level 3 dispatch is `32524439660`. Visual
  `96903389857`, frontend `96903390151`, repository `96903390207`, secret
  `96903390224` and controlled preflight `96906520757` pass. Controlled
  runtime `96906588035` alone fails in the first fresh Synthetic MBOM create
  response at `verify_mbom_publish_runtime.py:180-188`, before worker exercise.
- That boundary combines five predicates: HTTP success status, response
  request shape, queued request state, canonical request identity and canonical
  Outbox identity. The job exposes neither a discriminating response predicate
  nor a safe trace-correlated server tuple, so it does not prove a product
  root and consumes no product repair.

The prior final dispatch is retained as immutable `final 1/1` history. A new
opaque create-response cycle starts at `diagnostic 0/1`, `repair 0/1`,
`final 0/1`. The bounded checkpoint changes only the parent verifier and its
tests. In fixed first-failure order it can emit one of:

1. `P804_CREATE_RESPONSE_STATUS`
2. `P804_CREATE_RESPONSE_SHAPE`
3. `P804_CREATE_REQUEST_STATE`
4. `P804_CREATE_REQUEST_IDENTITY`
5. `P804_CREATE_OUTBOX_IDENTITY`

The tuple contains only the fixed diagnostic code,
`exception_type=RuntimeError` and the exact shared `HttpResult.trace_id` after
the stricter `^trace-[a-f0-9]{32}$` check. It does not parse headers or body for
trace and does not expose actual status, response body, identifiers, business
values, hashes, actor, target, exception message or stack. Disabled activation
or missing/invalid trace falls back to the unchanged constant; a conforming
success is silent. The activation is temporary for this checkpoint and must
be disabled immediately after the single diagnostic tuple is recovered. No
API, repository, permission, transaction, Schema, response, production target
or Gate standard changes.

## Parent response tuple and server narrowing

The parent-verifier checkpoint SHA
`f1c59bb6000a37a5427522c559130112eb560adb` passes ordinary CI
`32526910040`: frontend `96910769884`, visual `96910769942`, repository
`96910769972` and secret `96910770018` pass. The one bounded controlled
diagnostic run `32528181842` passes preflight `96914641053`; runtime
`96914756808` returns one and only one safe tuple:

`P804_CREATE_RESPONSE_STATUS / RuntimeError /
trace-4928b75518d75155a4fe459cb419dc98`

This establishes only the failed response-status predicate. It neither exposes
the actual status/body nor uniquely identifies a server symbol, so no product
repair is authorized or consumed. The parent response cycle is immutable at
`diagnostic 1/1`, `repair 0/1`, `final 0/1`.

The new server-narrowing cycle starts at `diagnostic 0/1`, `repair 0/1`,
`final 0/1`. Its independent exact scope is `p804-mbom-create-v1`; only the
fixed runtime Synthetic POST can add it. An exact validated request trace
activates a request-local `{trace_id, recorded}` state. API and repository
contexts record only the first innermost allowlisted stage and actual exception
class through the existing safe three-key log format, then rethrow the same
exception and restore prior flags in `finally`. The enqueue call remains
unwrapped because its existing response-neutral post-commit diagnostic and
recoverable queued Outbox semantics are unchanged.

Before the POST the parent captures both controlled log cursors. On a failed
create predicate it reads only the existing bounded strict mirrored-log helper
with the exact shared `HttpResult.trace_id` and `P804_CREATE_*` allowlist. A
single source record or two identical handler mirrors is accepted. Missing,
duplicate, divergent, wrong-trace, disallowed, extra-field, invalid-type,
oversized, symlink or out-of-root evidence falls back to the unchanged constant.
The parent never renders actual status, body, headers, IDs, hashes, actor,
profile, target, exception message or stack. Server diagnostics do not change
API response, permission, transaction, Schema, production target or Gate
behavior.

The first server-checkpoint candidate `43bf869891bf99f62f0cfbddeb56b42bd6b2a9af`
reached ordinary CI `32529961407`: frontend `96919848835`, repository
`96919848850` and visual `96919848904` passed. Secret job `96919848666` alone
reported one branch-history `generic-api-key` finding on a negative verifier
fixture combining the `idempotency_key` test key with a deliberately wrong
synthetic-looking value. It is not a credential. The history-clean remediation
uses the low-entropy literal `wrong`, which still proves exact synthetic
idempotency matching and changes no product, scope, response, permission,
transaction, diagnostic or Gate behavior. No diagnostic or product repair
round is consumed.

The amended server checkpoint
`a35aae1b63becb39e6185babc001e7fb90d0a35c` passes ordinary CI
`32531248862` (visual `96923518724`, repository `96923519012`, secret
`96923519013`, frontend `96923519086`). Its sole controlled diagnostic run
`32532396488`, preflight `96926841397` and runtime `96926902427` yields the
single safe tuple `P804_CREATE_REQUEST_INSERT / ValidationError /
trace-7b774b6d5f8f5df6853b4b5917f645d1`.

Symbol-level cross-proof against pinned Frappe 15.115.4 identifies the first
failing predicate without reading an exception message: `db_insert()` invokes
`get_valid_dict()`, which rejects a Python list in any non-Table field before
serializing JSON dictionaries. The repository supplied
`item_readiness_snapshot` as the first list-valued JSON field; its preceding
`source_snapshot` dictionary is accepted, while the later
`mbom_expectation_snapshot` has the same representation defect. The only
product repair canonicalizes those two arrays to JSON strings and leaves the
source dictionary, write order, transaction and all external behavior intact.
The historical parent response cycle stays `diagnostic 1/1`, `repair 0/1`,
`final 0/1`; the server cycle is `diagnostic 1/1`, `repair 1/1`, `final 0/1`.
Parent and server diagnostic activation are both disabled after recovery; the
strict response-neutral mechanism remains dormant.

Product-repair candidate `fde8505b478eb83f6e74ff6a9d8197246e79029e`
reached ordinary CI `32533729907`. Visual `96930635920` and secret
`96930636093` pass. Repository `96930636035` runs `2,277` tests with one
deterministic test-harness error: the new pinned-Frappe simulation referenced
a `ValidationError` attribute on a shared fake `frappe` module whose exact
full-suite import order does not define that optional attribute. A private
test-local `PinnedValidationError` removes the import-order dependency without
changing the simulated Frappe predicate or product.

Frontend `96930636054` passes its complete verifier and `449/450` E2E; only
the old P8-01 loading-state case misses its transient spinner after navigation
already completes. The exact repair diff has no frontend path and all P8-04
E2E pass. No timeout, retry, baseline or product behavior changes. This is
harness evidence only and consumes no new diagnostic/product repair round.

## Post-array-create downstream diagnostic cycle

The deterministic harness repair exact SHA
`8ffd881f81fd26731c41edea545689ed6e0d4917` passes ordinary CI
`32534726775` after its one authorized same-run failed-job-only attempt 2:
repository `96936025915`, frontend `96936009997`, secret `96936009966` and
canonical `126/126` visual `96936008811` pass. Visual artifact `9465410732`
has SHA-256
`3fbbf0e47e7f10edffe3202b1744179d1039d3a3a1faccb7e76ce4e5deec06c6`.
Attempt 1 had passed all nonvisual jobs; visual `96933374410` alone observed
the pre-existing R1-05 loading-position transient.

The only unchanged final Level 3 dispatch `32536066784` passes secret
`96937128093`, repository `96937128315`, frontend `96937128212`, canonical
`126/126` visual `96937128296` and controlled preflight `96939235660`.
Controlled runtime `96939285384` stops at the first Synthetic POST composite
verifier boundary after the array-serialization repair. No safe tuple, result
artifact or retained Site log identifies which ordered response predicate
failed, so no product root is proven. The historical server/create cycle is
frozen at `diagnostic 1/1`, `repair 1/1`, `final 1/1`.

The independent post-array-create downstream cycle starts at `diagnostic 0/1`,
`repair 0/1`, `final 0/1`. This verifier-only checkpoint temporarily enables
the existing exact Synthetic POST scope, shared validated `HttpResult.trace_id`,
strict mirrored-log reader and 29-code `P804_CREATE_*` allowlist. It changes no
server, product, API, permission, transaction, Schema or Gate behavior and
does not consume a product repair. Missing, invalid or absent safe evidence
still returns the original constant; the activation must be disabled after
the single bounded tuple is recovered.

The verifier checkpoint SHA
`abbdfdb441fea0709726475e326d1e267d5a2b07` passes ordinary run
`32537827926` attempt 2. Frontend `96944176937` passes `450/450`; visual
`96944177556`, repository `96944177886` and secret `96944193213` pass. The
first attempt's sole old P7-05 loading miss is confirmed as an unaffected
transient without changing any frontend standard.

The sole downstream diagnostic dispatch `32539503692`, preflight
`96946568519` and runtime `96946604608` returns one safe tuple:
`P804_CREATE_OUTBOX_INSERT / LinkValidationError /
trace-d8e26cfe8f525d188a45d723f57c3b42`. The exact MBOM-v2 Outbox constructor
set both the correct `mbom_request_global_id` and legacy Item-v1
`request_global_id`. Pinned Frappe checks metadata Links before controller
lifecycle methods; the latter targets `NPI Item Publish Request` and is the
only invalid nonempty Link. Project and MBOM request bindings exist, and all
attempt/result Links are empty.

The repair deletes only the erroneous persisted legacy binding. It retains the
logical event request identity, correct MBOM Link, event hash, strict Link
validation, capability and atomic transaction, and adds no Link bypass,
DocType, API, permission, Schema or ownership change. Historical cycles remain
immutable; this post-array cycle is `diagnostic 1/1`, `repair 1/1`,
`final 0/1`. Temporary MBOM diagnostics are disabled after tuple recovery.

The repaired exact SHA `23621f7ef2bf659a9deeb3c4a310f9730e159083`
passes ordinary run `32546035801` with repository `96964496188`, frontend
`96964496090`, secret `96964496159` and visual `96964496184`. The cycle's sole
unchanged final dispatch `32546776248` passes repository `96966501556`,
frontend `96966501557`, secret `96966501473`, visual `96966501591` and
preflight `96967752866`; controlled runtime `96967779592` alone fails at the
opaque `exercise_worker` child after the create response has passed all fixed
parent predicates. Failed child output remains withheld and no runtime artifact
exists. Multiple worker, read, truth, replay, recoverability, summary and
commit contexts remain reachable, so no product symbol is uniquely proven.
The post-array cycle is frozen at `diagnostic 1/1`, `repair 1/1`, `final 1/1`.

The separate worker-downstream cycle begins at `diagnostic 0/1`,
`repair 0/1`, `final 0/1`. Its four-path verifier-only checkpoint temporarily
activates one controlled `exercise_worker` diagnostic. It passes only the exact
validated Synthetic POST `HttpResult.trace_id` to the child, records at most
one allowlisted `P804_WORKER_*` stage plus exception class and trace, rethrows
the same exception, and preserves the existing product and transaction call
order. The parent reads neither failed-child stdout nor stderr and accepts only
one logical exact-three-key record through the already hardened mirrored-log
reader. Every unsafe, absent or ambiguous record returns the original constant.
All create, Item, replay and legacy diagnostic activations remain closed; no
worker, repository, adapter, response, permission, transaction, Schema,
ownership or Gate semantics are modified.

The exact checkpoint SHA `0991fadac593293edfdbf400ead389cea87912a2`
passes ordinary run `32551563566`. Its one controlled diagnostic dispatch
`32627638792` passes preflight `97165352387`; runtime `97165383949` emits one
safe tuple: `P804_WORKER_RESULT_OUTCOME / RuntimeError /
trace-8581818caa345745a9538106039fefed`. The worker call, requester-session
restore and raw request and node-result reads completed before the sole returned
state predicate failed. No request-state, node-truth, replay, recoverability or
count assertion ran. Because the worker's response-safe contract has several
non-throwing states, no product symbol is uniquely proven. This worker cycle is
frozen at `diagnostic 1/1`, `repair 0/1`, `final 0/1`.

The separate outcome-predicate subcycle begins at `diagnostic 0/1`,
`repair 0/1`, `final 0/1`. A verifier-only four-path checkpoint maps each fixed
return state and each non-mapping, missing-state, wrong-type or unknown-state
shape to one mutually exclusive allowlisted code. Synthetic verification
success records nothing. Exact trace correlation and the existing strict
mirrored-log reader permit only code, `RuntimeError` and trace; no actual state,
identifier, count, response body, exception message or stack is read or
displayed. Worker, repository, runtime fixture and adapter product paths remain
unchanged.

The outcome checkpoint exact SHA
`493e22e98c0793b20a802891f28a4eec83d42059` passes ordinary run
`32628503647`. Its one controlled dispatch `32629226416` passes preflight
`97169285669`; runtime `97169314833` emits only
`P804_WORKER_OUTCOME_NOT_CLAIMED / RuntimeError /
trace-7314ff51f535533bb66d04fbf6bbd0f7`. The tuple identifies a fixed
response-safe return but does not distinguish the route reader's internal
read, contract, binding and actor predicates. Product repair remains
unauthorized, and this outcome cycle is frozen at `diagnostic 1/1`,
`repair 0/1`, `final 0/1`.

The independent not-claimed precondition subcycle begins at `diagnostic 0/1`,
`repair 0/1`, `final 0/1`. Fourteen mutually exclusive verifier-only stages
check the fresh Outbox, Request, route, actor scope and active guard facts in
order before the unchanged first worker invocation. They perform no insert,
save, commit, enqueue, adapter or network operation; the service actor scope is
always restored. The prior worker/outcome activation is closed and only this
subcycle is temporarily active. Exact-trace strict mirrored-log handling and
constant-safe failure behavior remain unchanged, and no actual state, shape,
identifier, actor, hash, count, response, message or stack is rendered.

The not-claimed checkpoint exact SHA
`ac2d2e8b36e6a5e7aa5817faca2d879034d41c5e` passes ordinary run
`32630270492`. Its sole controlled dispatch `32630817041` passes preflight
`97173249724`; runtime `97173286086` emits only
`P804_NOT_CLAIMED_REQUEST_REBUILD / RuntimeError /
trace-fbfede24d1325b39a960553485dcb297`. Earlier stages prove the Outbox,
request Link and request read. The Request writer uses the approved shared
Frappe database datetime adapter, which deliberately persists a timezone-naive
MariaDB value; the MBOM private reader uniquely rejected that value before
domain construction or scope validation. Canonical source topology remains an
object, and all other reconstruction contract predicates raise `ValueError`
subclasses rather than the observed `RuntimeError`. The prior unit roundtrip's
identity storage stub explains why this exact database boundary was absent
locally.

The bounded repair only aligns the private reader with the verified Item and
worker persistence rule: naive database datetime is interpreted as UTC, aware
datetime is normalized to UTC, and invalid input remains fail closed. The
pinned roundtrip locks exact source, arrays, topology, hashes and profile; no
write, API, permission, transaction, Schema, ownership or worker order changes.
The not-claimed cycle is `diagnostic 1/1`, `repair 1/1`, `final 0/1`, all
historical counters are immutable, and
`MBOM_NOT_CLAIMED_DIAGNOSTICS_ENABLED=False` leaves the safe mechanism dormant
with every other diagnostic activation also closed.

The repaired exact SHA `0c791527aff847dcf22d54397b387b0f83595e5a`
passes ordinary run `32631727051`. Its sole unchanged Level 3 dispatch
`32632309098` passes repository `97176820194`, frontend `97176820204`, secret
scan `97176820250`, governed visual `97176820219` and preflight `97178317375`.
Runtime `97178343650` passes create and the repaired Request reconstruction
boundary before the response-safe `exercise_worker` constant fails. The
runtime artifact is not produced, the disposable Site is cleaned, and the only
run artifacts are visual evidence and secret-scan SARIF. No safe tuple can
distinguish the remaining pre-process or worker contexts. The not-claimed
cycle is therefore immutable at `diagnostic 1/1`, `repair 1/1`, `final 1/1`.

The separate post-datetime worker cycle begins at `diagnostic 0/1`,
`repair 0/1`, `final 0/1`. A four-path verifier-only checkpoint activates an
exact union of existing codes: seventeen fixed worker stages, fourteen outcome
classifiers and the nine precondition stages after Request reconstruction. It
adds no diagnostic code and excludes the five closed Outbox/Request stages.
All earlier diagnostic flags remain false; only the new post-datetime flag is
temporarily true. Exact trace correlation, mirrored-log fail-closed rules,
same-exception propagation, reversible actor scope and unread failed-child
stdout/stderr are unchanged. Product worker, repository, runtime fixture,
adapter, API, permission, transaction, Schema, ownership and Gate paths remain
untouched.
