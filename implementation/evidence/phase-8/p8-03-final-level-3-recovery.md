# P8-03 Final Level 3 Recovery

- Captured at: `2026-08-21T05:14:45Z`
- Branch: `codex/npi-v1.2-implementation`
- Failed exact revision: `a9ac0b5e96024642eeb9918b44aac35bb861cde6`
- Failed controlled Level 3 run: `32448049882`
- Failed cumulative Site job: `96673329957`
- Recovery classification: one bounded response-neutral diagnostic checkpoint; no
  product root has yet been claimed or repaired.

## Observable stop

The exact-revision controlled Level 3 run passed secret scanning, repository,
frontend, visual, preflight, both migration passes, and every cumulative runtime
predecessor through P8-01. The P8-03 default-disabled probe also passed. The first
P8-03 Item create then stopped at
`scripts/verify_item_publish_runtime.py:322` with
`RuntimeError: P8-03 Item command did not create one queued request`.

The response and retained logs did not distinguish input parsing, project/source
resolution, mapping/profile resolution, transaction writes, commit, or enqueue.
Therefore the failure did not uniquely prove a product root and no product
behavior was changed.

## Bounded diagnostic checkpoint

The checkpoint enables a fixed `p803-item-create-v1` diagnostic header only on
the first disposable synthetic Item create. The server records at most one
allowlisted `P803_CREATE_*` stage, validated exception type, and exact trace ID.
It records no request body, business value, actor, secret, transport target, or
stack trace; the diagnostic never enters the HTTP response and cannot alter the
original exception, transaction, authorization, or enqueue behavior. A governed
problem response is reduced to its closed uppercase problem code and trace ID.

Local validation before commit:

- P8-03 Item module tests: `118/118` PASS.
- Repository verification: `2145/2145` tests PASS, prototype approval check PASS,
  P0 visual governance PASS, V1.2 reconciliation PASS.
- `git diff --check`: PASS.

## Serial recovery budget

- Exact unchanged final Level 3 dispatches consumed: `1`.
- Diagnostic checkpoints consumed: `0/1` before this checkpoint is pushed.
- Uniquely proven product repair batches consumed: `0/1`.
- Next action: push this checkpoint, require ordinary CI on its exact SHA, then
  run the sole controlled diagnostic Site pass. Do not dispatch another final
  unchanged Level 3 run until the diagnostic root is uniquely classified and
  any authorized minimal repair has passed its affected checks and ordinary CI.

No production ERPNext or JCE endpoint, credential, or data is used by this
recovery path.

## First diagnostic Site result

- Diagnostic checkpoint SHA: `5fe1bd2afef27cdbfd7ebe4cb9a219eec812be92`.
- Exact-SHA ordinary CI: `32449902174` PASS; secret `96676311461`, repository
  `96676311381`, frontend `96676311389`, visual `96676311258`.
- Controlled diagnostic run: `32450566995`; preflight `96680418565` PASS;
  cumulative Site job `96680463723` failed only at the first P8-03 create.
- Governed response: HTTP `500`, problem code `INTERNAL_SERVER_ERROR`.

The diagnostic reader did not return a server stage because
`item_publish_request` returned the lower-level `HttpResult` without the fixed
request and trace IDs. The request did send and the server did echo the exact
`X-Trace-ID`, but the verifier then called the allowlisted log reader with the
unpopulated optional `created.trace_id`, producing `trace_id=None`. Peer EBOM
and P5-05 runtime helpers already preserve these generated IDs in their
returned `HttpResult`; P8-03 alone omitted that response-neutral wrapper.

This uniquely proves a verifier diagnostic-plumbing root, not a product root.
The initial `fc2ab92` remediation preserved the request-generated trace inside
the P8-03 helper. Ordinary CI `32452130327` was cancelled before completion and
is not evidence because that ad-hoc direction was superseded before another
Site dispatch.

The corrected remediation resolves trace identity once at the shared
`verify_frappe_runtime.request` / `HttpResult` boundary. It prefers the real
`X-Trace-ID` response header, permits a body fallback only for a governed
`application/problem+json` 4xx/5xx response, validates the existing platform
trace shape, and requires header/body equality when both exist. Missing trace
evidence, including an untrusted trace-like value in a non-problem body, closes
the optional diagnostic path with `None`; mismatched or invalid governed trace
evidence fails closed with a constant message. P8-03 no longer parses or
fabricates trace identity locally.

The diagnostic run `32450566995` remains a diagnostic harness failure within
the same recovery cycle. Product repair rounds consumed remain `0/1`; it is not
represented as a Gate PASS or a new product root.

## Shared-harness ordinary CI manifest repair

- Shared trace parser checkpoint SHA:
  `9532dc6f1fc52672974cdad38df2f4bd068b58d0`.
- Exact-SHA ordinary CI: `32452695822` FAILURE; repository `96683966535`,
  frontend `96683966261`, and visual `96683966454` PASS.
- Secret job `96683966433` failed before gitleaks in
  `scripts/verify_current_task.py` because the newly authorized shared harness
  path `scripts/verify_frappe_runtime.py` was not in the P8-03 manifest.

This is a controller-manifest harness failure, not a secret finding or product
root. The minimal remediation adds only the exact shared helper and exact
contract-test paths to `CURRENT_TASK.allowed_paths`; it does not broaden a
wildcard, change product behavior, or weaken the Gate. Product repair rounds
consumed remain `0/1`.

## Shared trace optionality harness repair

- Manifest repair SHA: `65c5ae8ba8dda4524acba5d834e0d785f8ea6fa8`.
- Exact-SHA ordinary CI: `32453738832` PASS.
- Diagnostic controlled-Site run: `32454484126`; cumulative job
  `96690632429` failed before P8-03 in
  `verify_document_runtime.verify_fresh_namespace`.
- The exact predecessor response was a raw Frappe resource `404` with neither
  an `X-Trace-ID` header nor a governed problem body. The shared helper treated
  the intentionally absent optional diagnostic identity as an exception.

This is the same response-neutral diagnostic harness remediation, not a
product failure or a new product root. The parser keeps the governed-body
allowlist and constant-message fail-closed behavior for malformed or
conflicting evidence while restoring `HttpResult.trace_id` optionality for
raw Frappe responses. Product repair rounds consumed remain `0/1`.

## Diagnostic result and bounded product repair

- Shared trace optionality repair SHA:
  `6a1801527511225d3f72639754d462bf180141be`.
- Exact-SHA ordinary CI: `32455525411` PASS.
- Diagnostic controlled-Site run: `32456460755`; preflight job `96694600008`
  PASS and cumulative job `96694682993` FAILURE at the first P8-03 create.
- The only emitted tuple was `P803_CREATE_STREAM_GUARD` / `NameError` /
  `trace-50d0538b2f0f53d68118a0b3ce3edc4d`. The verifier withheld response-body,
  business-value, target-identity, exception-message, and server-stack data.
- Read-only cross-location inspection maps that tuple uniquely to
  `frappe_repository._locked_stream_guard`: its first-create timestamp called
  `_aware_utc` even though that private name was neither defined nor imported
  in the module. The same undefined name guarded the active and clear update
  timestamps.

The bounded repair adds the missing module-private aware-UTC normalizer and a
real first-guard-create regression covering all three call sites. Automatic
synthetic diagnostic activation is disabled after obtaining the unique root;
the response-neutral diagnostic mechanism remains dormant. Product repair
rounds consumed are now `1/1`.

## Final unchanged Gate and new downstream replay cycle

- Product repair checkpoint:
  `d71cd7e5b1ff2ffec89f301f63d8d4f9c2751211`.
- Exact-SHA ordinary CI `32457541575` passed on attempt 2 after the single
  permitted same-run failed-frontend-job rerun; the replacement frontend job
  `96700401878` passed all `444` E2E cases. No code, baseline, threshold, or
  product behavior changed for that rerun.
- The sole diagnostics-closed final Level 3 run `32459531850` retained the
  exact checkpoint. Repository `96703501236`, secret `96703501254`, frontend
  `96703501098`, visual `96703501232`, and controlled preflight `96706283836`
  passed. Cumulative Site job `96706331478` failed only in the first
  cross-process terminal replay fixture.
- The only exposed failure was the constant outer `RuntimeError`:
  `P8-03 Bench fixture replay_terminal failed with a withheld diagnostic`.
  No inner exception class, governed stage, or trace was available, so this
  run does not uniquely prove another product repair.

Under the controller's standing serial recovery rule, this is a new opaque
downstream cycle. The completed create cycle remains immutable at diagnostic
`1/1`, product repair `1/1`, and final unchanged Gate `1/1`. The new
`replay_terminal` cycle starts at diagnostic `0/1`, product repair `0/1`, and
final unchanged Gate `0/1`.

The verifier-only diagnostic checkpoint correlates the child fixture to the
already validated trace from the controlled replay-list HTTP response. It may
record and render exactly one allowlisted `P803_REPLAY_*` stage, with each
stage code bound to exactly one failure context, plus the validated
exception class name, and exact trace. The child records through the existing
safe diagnostic hook and re-raises the original exception. The parent reads
only bytes appended to the two exact controlled `npi_core.log` candidates
during that child process and accepts exactly one strict three-field logical
record. Each source may contain at most one record, and identical bench/site
handler mirrors fold to that one logical tuple. Missing, same-source duplicate,
cross-source drift, wrong-trace, disallowed, malformed, oversized, symlinked,
or out-of-root evidence keeps the existing constant withheld failure.

The parent never reads or renders failed-child stdout/stderr, exception text,
response bodies, Project/Request/Outbox identities, actors, payloads, hashes,
formal Item or target values, or filesystem paths. The old create activation
remains `ITEM_CREATE_DIAGNOSTICS_ENABLED = False`; no product worker,
repository, API, permission, transaction, claim, replay, ownership, Schema, or
external behavior changes in this checkpoint. No production ERPNext or JCE
system is contacted.

## Replay diagnostic dual-handler harness remediation

- Diagnostic checkpoint SHA:
  `618cabe56491245422753f7e8d370acff5aa237d`.
- Exact-SHA ordinary CI `32462506234` passed all lanes, including `1018`
  frontend unit cases and `444` E2E cases.
- The sole replay diagnostic run `32463671893` passed controlled preflight job
  `96715653312`; cumulative Site job `96715708429` failed with the constant
  withheld replay message and exposed no governed tuple.

Read-only inspection proved a verifier harness root. With a Site initialized,
Frappe's `npi_core` logger installs one bench and one site rotating-file
handler. One logical `record_safe_diagnostic` call therefore writes the same
safe record once to each exact candidate. The parent reader combined both
physical records and rejected them as a duplicate before logical mirror
folding. Isolated simulation reproduced two physical records and a `None`
reader result. The run published no runtime-log artifact, so it does not prove
which replay stage failed and does not authorize a product repair. The replay
cycle remains product repair `0/1` and final unchanged Gate `0/1`.

The bounded remediation groups records by source. Each candidate may contain
at most one strict, allowlisted, exact-trace record; one or both candidates may
supply it, and two candidates are folded only when their complete safe tuples
are identical. A same-source duplicate, cross-source drift, missing record,
wrong trace, disallowed stage, extra or invalid field, or every existing unsafe
filesystem/log boundary retains the constant fail-closed result. The `64 KiB`
append limit and all product behavior remain unchanged.

## Replay diagnostic result and bounded product repair

- Dual-handler remediation SHA:
  `84975ce736036e4fd6df21ef40f29a5e3b37ab47`.
- Exact-SHA ordinary CI `32464920564` passed all lanes, including `1018`
  frontend unit cases and `444` E2E cases.
- The sole post-remediation controlled diagnostic run `32466064108` passed
  preflight job `96722793060`; cumulative Site job `96722848851` emitted the
  unique safe tuple `P803_REPLAY_PROCESS_OUTBOX` / `RuntimeError` /
  `trace-006eda5a7f6d5546b5ce130ecb77aed4`.

The stage maps only to the retained terminal `process_outbox_message` calls.
Read-only symbol tracing proved `FrappeItemPublishWorkerRepository.claim`
required an active stream-guard binding before reading the Outbox state. A
properly completed terminal request has already moved that guard to retained
truth, clearing active fields and freezing the matching request, target and
last state, so the active check raised before the existing terminal
`not_claimed` return.

The bounded product repair reads the locked Outbox state after validating its
immutable request binding. Only the two retained terminal Outbox states may
return `None` before active validation, and only after the request state and
retained guard's exact request, target and last-state binding agree. Pending,
processing, retryable, uncertain and unknown states retain the prior active
binding and lease behavior. Replay diagnostic activation is closed after the
unique root; the response-neutral mechanism remains dormant. The replay cycle
has consumed product repair `1/1` and final unchanged Gate remains `0/1`.

## Replay repair final Gate and new legacy-collection cycle

- Replay product repair checkpoint:
  `59e74814b7c8d5cdeb2e0d08ed0fbbddbdf92c0d`.
- Exact-SHA ordinary CI `32467712811` passed repository, secret scan, governed
  visual and frontend lanes, including the complete E2E suite.
- The sole diagnostics-closed final Level 3 run `32468617016` passed repository
  `96730489147`, secret scan `96730488896`, visual `96730489034`, frontend
  `96730489037`, and controlled preflight `96733570954`. Cumulative Site job
  `96733614493` passed the repaired fresh and cross-process terminal replay
  boundary, seeded the marker-gated legacy row, ran both migrations, and then
  failed in the subsequent migrated-legacy collection check.

The outer failure was the existing constant `RuntimeError` at the compound
collection predicate. Response body, HTTP status, actual cardinality, business
values and identities were withheld, so the run cannot uniquely distinguish a
non-success response, response-shape drift, or collection-cardinality drift.
It therefore does not authorize another product repair. The completed create
and replay cycles remain immutable at diagnostic `1/1`, product repair `1/1`,
and final unchanged Gate `1/1`. This new `legacy-collection` cycle starts at
diagnostic `0/1`, product repair `0/1`, and final unchanged Gate `0/1`.

The parent-verifier-only diagnostic checkpoint classifies that one predicate
as exactly one of `P803_LEGACY_COLLECTION_STATUS`,
`P803_LEGACY_COLLECTION_SHAPE`, or `P803_LEGACY_COLLECTION_CARDINALITY`. It
renders only the allowlisted diagnostic code, fixed outer
`exception_type=RuntimeError`, and the exact validated response trace. It
never renders the status, response body, actual count, Project/Request/Outbox
identities, actor, request path, or business values. A disabled activation or
missing/invalid trace retains the original constant failure. The existing
create and replay diagnostic activations remain closed; no server log is read
and no product, API, permission, transaction, migration, query projection,
Schema, ownership, claim, lease, or external behavior changes.

## Legacy collection parent result and legacy-query server subcycle

- Parent diagnostic checkpoint SHA:
  `ae81cfe66dc38482a0093387567300b300ef8eb7`.
- Exact-SHA ordinary CI `32470972890` passed all required lanes.
- Controlled diagnostic run `32472011299` passed preflight job `96740580834`;
  Site job `96740634515` emitted the unique parent tuple
  `P803_LEGACY_COLLECTION_STATUS` / `RuntimeError` /
  `trace-6c5d7fc706da502d8406b9aacfb1ff3a`.

That tuple proves only a non-success response at the fixed legacy collection
request. It does not identify the server-side query failure and therefore does
not authorize a product repair. The historical parent cycle is immutable at
diagnostic `1/1`, product repair `0/1`, and final unchanged Gate `0/1`. The new
`legacy-query-server` subcycle starts at diagnostic `0/1`, product repair
`0/1`, and final unchanged Gate `0/1`.

The response-neutral server checkpoint is enabled only by the verifier for the
exact GET collection request with query key `legacy-list` and a fixed scope
header. The list handler installs an independent request-local state and each
allowlisted `P803_LEGACY_QUERY_*` code names one innermost query context. At
most one safe three-key record is written, and the original exception object
is re-raised; request flags are restored in `finally`. The parent accepts only
one logical record correlated to the exact HTTP response trace, folding only
identical bench/site handler mirrors. Missing, duplicate, drifting, wrong-
trace, disallowed, malformed, oversized, symlinked, or out-of-root evidence
retains the original constant failure.

No status, response body, count, identity, actor, path, query value, exception
message, stack, target, payload, or hash is recorded or rendered. The earlier
parent classifier and create/replay activations are closed. This checkpoint
does not alter API responses, authentication, permissions, transactions,
queries, projections, Schema, migrations, ownership, or external behavior.
