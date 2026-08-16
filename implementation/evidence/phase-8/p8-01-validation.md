# P8-01 Level 3 Validation — Read-only ERP Projections

Recorded: `2026-08-16T07:00:00Z`

Decision: `PASS — LEVEL 3 TASK GATE`

Exact final product checkpoint:
`b938926293c51c2e3ac1f63adab583c099a5c3ed`

Primary requirements: `INT-001`, `INT-006`, `INT-007`, `INT-010`,
`FR-PM-010`, `FR-TL-008`, `FR-TR-006`, `FR-NP-006`

## 1. Outcome

P8-01 delivers the frozen seven-kind, read-only ERP-owned observation slice:

- immutable Customer, Supplier, formal Item, Tooling procurement/cost,
  Project cost, formal quality-status and Tool Asset-status observations;
- one Project/context-contained guarded head per exact kind and source scope,
  with source version, modified time, canonical payload hash, availability,
  freshness, authority and application disposition retained independently;
- exact duplicate replay, older reorder, equal-time hash conflict, restart and
  cross-process replay truth without moving a current head backward;
- Project- and tenant-first authorization before every secondary identity,
  identical absence/foreign-object handling and bounded external-actor
  redaction;
- Mock unavailable by default, an explicitly allowlisted disposable sandbox
  seam and synthetic proof that can never become formal ERP truth; and
- a closed BFF plus dense direct-trilingual Project and existing Tooling
  consumers that expose a value only for exact available, fresh,
  authoritative, applied-current truth.

P8-01 performs no target write and installs no production endpoint,
credential, mapping, freshness/EAC/quality policy or background production
configuration. No production ERPNext or JCE Core system was contacted.

## 2. Checkpoint evidence

| Checkpoint | Result | Durable evidence |
|---|---|---|
| pure domains, contracts and guarded metadata | `PASS` at `6d88175582ac09fdc3ef542f1443e5213cb9a6d6` | `implementation/evidence/phase-8/p8-01-domain-metadata-checkpoint.md` |
| durable repository, refresh and read-only BFF | `PASS` at `fd4fc6a7383d43b92cf363cebc08b6c8c7faeb3c` | `implementation/evidence/phase-8/p8-01-repository-bff-checkpoint.md` |
| dense direct-trilingual projection truth | `PASS` at `71bd18a610b685894ab2ed84df4a51a4306eacae` | `implementation/evidence/phase-8/p8-01-product-ui-checkpoint.md` |
| cumulative disposable runtime verifier and exact contract repairs | `PASS` at `b938926293c51c2e3ac1f63adab583c099a5c3ed` | exact-SHA ordinary and Level 3 runs below |

The post-checkpoint-3 commits changed only the controlled runtime fixture,
workflow selection and verifier assertions needed to prove the already-frozen
contract on a real disposable Frappe Site. Each precursor failed closed on one
exact fixture/verifier boundary, cleaned up, received a bounded forward repair
and was followed by affected checks plus a new exact-SHA ordinary run. The
final Asset verifier correction asserts the actual closed payload version
`sandbox-asset-v1`; it changes no product payload or authority.

## 3. Exact-SHA ordinary Gate

Pull-request workflow `31925662056` passed at the exact final SHA:

- repository `95112716915`: `1,969/1,969` tracked Python tests and repository,
  current-task and reconciliation verification PASS;
- frontend `95112716888`: `60/60` files, `933/933` unit tests and `426/426`
  non-visual E2E PASS; coverage is `80.36%` statements, `80.20%` branches,
  `83.00%` functions and `82.99%` lines; all `7,641` literal English sources
  have direct `zh` and `zh-TW` translations; build and vulnerability audits
  PASS with zero findings;
- secret `95112716949`: `26` first-parent task commits and `510` complete
  branch commits contain no leak; and
- visual `95112716959`: the complete governed fixed-Linux matrix passes
  `119/119`; artifact `9257790117`, digest
  `sha256:aca93e114ae329fb31d347be2d4a1853f2d5968e1fc2bd772a7aca6faaf050b6`.

The host worktree is intentionally not cited for the production brand audit:
an unrelated user-owned untracked image under `frontend/public/` trips that
guard. It was not staged, changed or used as PASS evidence.

## 4. Final cumulative Level 3 Gate

Workflow `31926087732` passed every Level 3 lane at the unchanged exact SHA:

- repository `95113770531`: complete repository verification PASS;
- frontend `95113770530`: complete unit, E2E, translation, coverage, build and
  vulnerability verification PASS;
- secret `95113770561`: current-tree Gitleaks PASS with zero results; artifact
  `9257862865`, digest
  `sha256:5b9de73adbe5ccc43fa88a5e6b458bb098863567b74f5e639694ecdac602fb2a`;
- visual `95113770550`: `119/119` PASS; artifact `9257914385`, digest
  `sha256:4506f23ef40499791d7aa9536ebc85564f53e407b4f671f482409fc00b00aadc`;
- controlled preflight `95115031258`: exact-SHA, task and Gate-mode checks
  PASS; and
- cumulative disposable runtime `95115065221`: P5 through P7-07 plus P8-01
  projection runtime PASS; artifact `9258083274`, digest
  `sha256:86007c9e5fece16c3a0b01eeca608cbb5845ae50f976feb8c4c1da8aff2aab43`.

The runtime result file hashes to
`sha256:ef234bee4a16da922511b88487994a08b793d35051de53d141ad3a2383f12320`
and records `result=PASS`, exact head SHA, `gate_mode=level_3`, disposable Site
`npi.localhost`, database `npi_one_runtime`, scope `p5-01-through-p8-01`,
pinned Frappe commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1` and command
`bash scripts/verify-frappe-runtime.sh --projection-only`.

## 5. Runtime truth and fault closure

The final fresh state contains exactly seven guarded heads, seven projection
kinds and twenty-five immutable observations. The exact dispositions are:
seven `synthetic_retained`, eight `unavailable_current`, eight
`applied_current`, one `superseded` and one `conflicted`. Customer advances to
source version `v7`; the other six heads retain source version `v3`.

The controlled Site proves:

- initial zero truth; seven synthetic retained observations; seven Mock
  unavailable heads; seven sandbox-style applied heads; and same-process
  duplicate replay without new observations;
- one older superseded observation, one additional unavailable observation,
  one equal-time different-version/hash conflict and one recovery advance;
- identical Inbox and Outbox counts before and after projection processing;
- exact confirmed-current P6-04 cost and P6-06 Asset consumer closure;
- guest `401`, identical internal absent/foreign `404`, bounded external
  redaction, and `422` for invalid or extra query input;
- independent route disable/recovery and cross-process replay with identical
  before/after counts and heads;
- additive migrations run twice; and
- disposable cleanup with zero target write and zero production traffic.

The only configured adapter proof uses `https://erp.sandbox.example.test`, an
explicit hostname allowlist, a fake secret reference, non-production
attestation and redirects disabled. The controlled reader is local and sends
no network request. Production is never a fallback.

## 6. Requirement and release disposition

The release review covers shared ownership, event/OpenAPI Schema, two additive
DocTypes, repository/worker/BFF, existing Tooling consumers, frontend/i18n,
migration, rollback, runtime, secrets and the complete visual matrix. It finds
no P0, P1 or P2 issue and accepts P8-01 at Level 3.

`INT-001`, `INT-006`, `INT-007` and `INT-010` now have a technically verified
read-only projection foundation. Inbound signed-webhook creation remains
P8-02; formal quality linkage remains P8-06; operator replay and full
reconciliation remain P8-07. `FR-PM-010`, `FR-TL-008`, `FR-TR-006` and
`FR-NP-006` advance only for the exact read-only projection slice. Budget/EAC,
quality/Gate interpretation and unapproved production mappings remain held.

Task Diff Review over `046dba1..b938926` covers `17` commits, `67` files,
`13,608` additions and `117` deletions. Changed files map directly to domain,
contract, metadata, repository, BFF, consumer, frontend, i18n, E2E, visual and
controlled runtime tests. No accepted-path TODO, FIXME, fake success, test
deletion or threshold reduction remains.

## 7. Rollback and transition

Before retained use, the independent P8-01 feature may return to its audit
checkpoint. After observation or audit history exists, rollback disables only
the projection route, worker and UI surfaces, reports truth unavailable and
uses a reviewed forward repair. It never deletes an observation, changes a
hash/version, moves a head backward or compensates in ERPNext.

P8-01 passes Level 3. Standing continuous-delivery authority may activate only
the bounded `P8-02 — signed webhook and Inbox processing` requirement/domain/
existing-capability audit. P8-02 product behavior waits for its frozen plan
and exact-SHA ordinary CI. Production ERPNext/JCE contact and P8-03 through
P8-09 remain prohibited.
