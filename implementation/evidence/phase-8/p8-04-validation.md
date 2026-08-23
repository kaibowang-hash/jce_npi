# P8-04 MBOM Publish Execution — Level 3 Validation

Date: `2026-08-23`

Status: **PASS — LEVEL 3**

Requirement disposition:

- `INT-004`: **TECHNICAL VERIFIED — MBOM EXECUTION FOUNDATION; PRODUCTION
  AND SANDBOX MAPPING HELD**.
- `FR-DS-013`: **ITEM AND MBOM EXECUTION PORTIONS TECHNICALLY VERIFIED;
  PRODUCTION/SANDBOX MAPPING AND THE WHOLE REQUIREMENT REMAIN HELD**. This does
  not claim complete production acceptance or complete the whole requirement.

## Exact reviewed boundary

- Final product checkpoint:
  `ca72deceab4b8e899d0da1207883887c9d30077a`.
- Task base and predecessor product checkpoint:
  `c11d97cc4e26cd3961d7927608eb2510f6411269`.
- The exact task diff contains `111` committed paths across the four frozen
  product checkpoints, governed visual integration and bounded final-Gate
  recovery. Every path passes `implementation/CURRENT_TASK.json`.
- No dependency manifest, Frappe/ERPNext core, cross-database access,
  destructive patch, test deletion, threshold reduction, production endpoint,
  credential or target write was added.

The evidence-based release review found no P0, P1 or P2 issue. P8-04 therefore
closes at this exact product checkpoint. Unrelated local development files,
Darwin screenshots and untracked local evidence are not part of this
validation.

## Acceptance and contract evidence

- The fixed Project-first collection/detail/create BFF exposes only the
  operation-specific `publish_released_mbom` request. It derives tenant,
  Project, actor, trace, exact released topology, current Item readiness,
  profile and target expectations server-side; it is not generic DocType CRUD.
- ERPNext retains ownership of formal BOM identity, target version, submitted
  state, routing and manufacturing lifecycle. NPI One owns the exact released
  source, approval, request, Outbox, immutable attempt, audit and read-only
  result/mapping observation.
- Every Sandbox-bound assembly requires exact current authenticated Item
  mapping truth. Mock creates no Outbox, attempt, target identity, mapping or
  network effect. Disposable synthetic execution is network-free and
  non-authoritative. Only an authenticated authoritative non-production result
  can advance a formal per-assembly mapping by exact compare-and-set, and no
  Sandbox profile is installed.
- Request, nodes, actor-bound idempotency, stream guard, Outbox and audit commit
  atomically before enqueue. Enqueue failure retains a recoverable pending
  Outbox row. A pre-call attempt is durable; a timeout or crash after the
  adapter boundary becomes uncertain and is never blindly redispatched.
- Aggregate and per-node truth remain distinct. A partial result cannot become
  aggregate success; stale or conflicting mapping heads remain visible and do
  not overwrite current truth. Submitted BOM truth is immutable and P8-04
  invents no successor policy.
- The additive schema-version-2 MBOM Outbox branch and nine support DocTypes
  retain the P8-03 Item and legacy branches. Support metadata denies normal
  create, update and delete; internal writes require narrow operation-specific
  capabilities.
- The cumulative disposable Site applies migrations during setup and twice in
  the controlled fixture, proves claim/recovery/replay and removes all
  ephemeral containers, volumes and its network.
- Before an adapter boundary, rollback disables the MBOM route, enqueue and
  worker while retaining committed request/node/idempotency/Outbox/audit
  history. After a crossed boundary, rollback is forward-only: retain every
  lease, attempt, result, uncertainty, observation, mapping head and audit;
  never delete, rewrite to success, blindly redispatch, submit or overwrite a
  BOM or compensate a target automatically.

## Incremental and task evidence

- Final bounded repair Level 1 passes the complete affected MBOM, Item,
  shared-trace, controller and reconciliation suites, Python compilation,
  generated-contract checks, direct i18n verification and `git diff --check`.
- The complete ordinary repository verifier passes `2,299` tracked Python
  tests. The frontend verifier passes `62/62` files and `1,046/1,046` unit
  tests; nonvisual Playwright passes `450/450`.
- `8,183` literal-English sources have `100%` direct `zh` and `zh-TW`
  coverage. Industrial UI, boundary, style, accessibility and mixed-language
  audits pass.
- All response-neutral Item and MBOM diagnostic activations are closed:
  `ITEM_CREATE_DIAGNOSTICS_ENABLED=False`,
  `REPLAY_TERMINAL_DIAGNOSTICS_ENABLED=False`,
  `LEGACY_COLLECTION_DIAGNOSTICS_ENABLED=False`,
  `LEGACY_QUERY_SERVER_DIAGNOSTICS_ENABLED=False`,
  `MBOM_CREATE_DIAGNOSTICS_ENABLED=False`,
  `MBOM_WORKER_DOWNSTREAM_DIAGNOSTICS_ENABLED=False`,
  `MBOM_NOT_CLAIMED_DIAGNOSTICS_ENABLED=False`,
  `MBOM_POST_DATETIME_WORKER_DIAGNOSTICS_ENABLED=False`,
  `MBOM_POST_MANIFEST_WORKER_DIAGNOSTICS_ENABLED=False`,
  `MBOM_POST_COMMAND_HASH_WORKER_DIAGNOSTICS_ENABLED=False`, and
  `MBOM_PROCESS_VALIDATION_DIAGNOSTICS_ENABLED=False`. Dormant strict
  trace/no-leak contracts remain tested.

## Exact ordinary CI

Pull-request run `32651139504`, attempt `1`, passes at the exact final product
checkpoint:

- secret scan `97222817515` — PASS;
- repository `97222817676` — PASS (`2,299` tracked Python tests);
- frontend `97222817695` — PASS (`1,046` unit and `450` E2E tests);
- visual `97222817696` — PASS (`126/126` fixed-Linux cases);
- controlled jobs correctly skip in ordinary CI.

Ordinary artifacts:

- visual artifact `r1-06-linux-visual-evidence`, ID `9496273440`, ZIP SHA-256
  `ba8afa9c55dcd788e1c07408de6f643fcf56e6f82b5cf5168eec495ce02742f7`;
- Gitleaks artifact `gitleaks-results.sarif`, ID `9496209836`, ZIP SHA-256
  `e79cae1b26201da5a6002f8747aab91b8cbb4b386bc5d4815f9c3c5042b30975`.

## Final unchanged Level 3

Controlled run `32651903846`, attempt `1`, passes at the same exact SHA:

- frontend `97224725000` — PASS;
- visual `97224725065` — PASS (`126/126` fixed-Linux cases);
- repository `97224725099` — PASS;
- secret scan `97224725138` — PASS;
- controlled preflight `97226433521` — PASS;
- cumulative disposable Site `97226462865` — PASS.

Artifacts:

- runtime artifact `p8-integration-runtime-32651903846`, ID `9496708366`,
  size `477` bytes, ZIP SHA-256
  `b681b8fc70b8be0bd8887f323d5d914139e61635eca0e2b28d32b32d87170f35`;
- visual artifact `r1-06-linux-visual-evidence`, ID `9496465159`, size
  `14,656,583` bytes, ZIP SHA-256
  `e38676ac10cc45934e67e171a84f2ddb241922d5250d22bfe8054e4bafb445db`;
- Gitleaks artifact `gitleaks-results.sarif`, ID `9496416881`, size `6,760`
  bytes, ZIP SHA-256
  `afbcd2f1ff759c9af139f51a31599bf415bce765d2a5e5a73683d1a3c0a02346`.

The runtime result records `result=PASS`, `gate_mode=level_3`,
`scope=p5-01-through-p8-04`,
`predecessor_scope=p5-01-through-p8-03`, disposable Site `npi.localhost`,
database `npi_one_runtime` and marker
`npi-one-local-runtime-disposable-v1`. The pinned Frappe Site proves migrations,
exact source and Item/MBOM expectation binding, request/Outbox/attempt/result/
mapping separation, lease recovery, terminal replay, uncertain no-redispatch,
submitted protection, zero formal mapping from Mock/synthetic truth, zero
production traffic and cleanup.

## UI, i18n, visual and security disposition

- The existing dense released-EBOM workspace contains one docked MBOM
  inspector and one visible-text primary MBOM request action with exact Impact
  Review. It adds no retry, reconcile or submit command.
- Loading, empty, unavailable, no-permission, read-only, conflict, queued,
  processing, Mock, synthetic, partial, failed, uncertain, submitted and
  authoritative truth remain explicit and non-color-only. Formal BOM identity
  is shown only from a current authenticated authoritative mapping to an
  authorized viewer.
- The complete `126/126` Linux/amd64 governed visual matrix passes. The three
  P8-04 canonical cases cover English synthetic, Simplified Chinese partial at
  150% and Traditional Chinese authoritative at 125%, while retaining square,
  flat, dense industrial hierarchy, complete action text and keyboard/focus
  usability.
- Full-history Gitleaks, TODO/FIXME/NotImplemented, fake-success, backdoor,
  core-patch, direct-SQL and cross-database scans find no release blocker.

## Holds and next task

Production ERPNext/JCE contact, an installed authenticated Sandbox profile,
actual BOM method/field/UOM/alternate/effectivity/routing/service-scope facts,
submitted-BOM successor policy, formal mapping from Mock/synthetic/HTTP
acceptance/partial/timeout and generic retry/DLQ/replay/reconciliation remain
held. `INT-004` and only the MBOM technical portion of `FR-DS-013` are
technically verified; production/Sandbox mapping and the whole FR-DS-013
requirement are not complete.

P8-05 activates only as a planning/audit task for `INT-005` and
`FR-TL-011..016`. It must freeze one physical Tooling Set to zero-or-one formal
ERP Asset mapping, operation-specific create/update authority, immutable source
and expected version, read-only Asset/location/maintenance observations and the
rule that NPI acceptance evidence is not ERP approval. No P8-05 product code is
authorized before its audit plan and transition ordinary CI pass.
