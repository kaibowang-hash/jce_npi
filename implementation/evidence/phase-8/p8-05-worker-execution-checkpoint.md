# P8-05 Checkpoint 3 — Tool Asset Worker Execution Candidate

Status: `IMPLEMENTED_AWAITING_EXACT_SHA_ORDINARY_CI`

Checkpoint 2 exact SHA `d20b4a3bba67ae333e161295fe1155211375f013`
passes ordinary CI `32664440277`: frontend `97255551972`, repository
`97255552087`, secret `97255552048` and visual `97255552051` pass. Controlled
jobs skip because checkpoint 2 installs no worker runtime.

The checkpoint 3 candidate adds one bounded worker path. A pending message, or
a processing message whose lease expired, is claimed under the frozen service
actor. The claim and immutable attempt commit before the adapter boundary; the
boundary commits before dispatch. An expired claim that already crossed the
boundary is sealed uncertain without redispatch. Terminal messages are never
claimed. Recovery only enqueues bounded pending/expired identifiers.

The adapter registry is closed by resolver, target mode and exact
`create_tool_asset` / `update_tool_asset` operation. Its default is empty. The
only repository fixture is explicitly marked, disposable and network-free;
it returns synthetic field truth without a formal Asset ID or target version.
Actual ERPNext method, fields, Company, Category, location, maintenance,
approval source, Sandbox and production remain unavailable and fail closed.

All five NPI-owned fields produce immutable field results. Aggregate truth
preserves partial, retryable, final, conflict and uncertain states. Only one
authenticated, authoritative, complete Sandbox result may advance the 0/1
physical-Set mapping head through exact prior-version and prior-observation
compare-and-set. Synthetic, partial, malformed, stale or uncertain results add
observed history but never formal mapping truth. P8-01 remains the owner of
read-only Asset status/location/maintenance projection.

Affected checks cover adapter binding/classification, operation-specific
registry, claim/lease/boundary commit order, service-actor restoration,
post-boundary no-redispatch, deterministic result identities, recovery bounds,
capability-guarded writes, request/outbox lifecycle, network-free runtime
configuration, translations, metadata/security and all P6/Item/MBOM peers.
Checkpoint 4 remains closed until the candidate exact SHA passes ordinary CI.

The cumulative controlled runtime is advanced from
`p5-01-through-p8-04` to `p5-01-through-p8-05`. It first proves the Tool Asset
profile and command context are independently default-disabled, then starts a
fresh process with the exact disposable marker and actors, creates one
synthetic request through the fixed Project/Master/Set route, exercises the
worker in a child Bench process, verifies five synthetic field results, zero
mapping heads, one adapter call, terminal replay not claimed and no recoverable
terminal message. Failed child stdout/stderr are not read or emitted.

## Level 1 evidence

Changed files map to affected checks as follows:

- adapter, worker, worker repository and execution capability changes map to
  operation/registry classification, claim/lease/boundary order, retained
  terminal replay, recovery, per-field/aggregate truth, mapping CAS and
  capability-bound write tests;
- request controller and public repository projection changes map to the real
  Frappe insert/save lifecycle and immutable persisted snapshot versus current
  execution-state projection tests;
- runtime fixture, shell verifier and workflow changes map to default-disabled,
  network-free synthetic, failed-child no-output and cumulative P8-05 scope
  tests, while preserving P8-03/P8-04 predecessor assertions;
- translations and generated catalog map to literal English extraction,
  direct `zh` / `zh-TW` symmetry and generated-catalog equality; and
- retained P6, Item, MBOM, Phase 2 and controller/reconciliation suites bound
  the predecessor ownership, Outbox, permission and workflow contracts.

The final affected Python run passes `422/422`: Tool Asset `63/63`, P6
acceptance `35/35`, retained P6 Tool Asset domain `4/4`, Item `146/146`, MBOM
`126/126`, Phase 2 `15/15`, and current-task/reconciliation `33/33`.
Compilation, shell syntax, current-task and reconciliation verifiers, exact
no-direct-SQL/network/TODO/permission-bypass scans and `git diff --check` pass.
The Frappe catalogs contain `8,294` literal English sources with `100%` direct
`zh` / `zh-TW` coverage; generation and i18n checks pass. JSON, YAML and CSV
parsing passes. Post-commit manifest simulation accepts exactly `30` candidate
paths and no product/UI/target path outside the checkpoint authorization.
