# P8-04 Checkpoint 2 — Project-first Command and Atomic Durable Outbox

Recorded: `2026-08-21`

Decision: `PASS — CHECKPOINT 2; CHECKPOINT 3 AUTHORIZED`

Final product checkpoint:
`197a59f9ecf41daa486e84d75ac6007af38fa423`

Ordinary pull-request CI: `32500465488`

## Scope delivered

- Added the fixed Project-first MBOM publish collection/detail/create boundary.
  Unsupported verbs, detail commands, retry and reconcile routes stay closed;
  tenant, Project, requester and secondary containment are server-derived.
- Resolves one exact released Phase 5 EBOM topology plus current authenticated
  P8-03 Item mappings and locked MBOM expectations. Caller-selected target,
  topology, formal BOM identity, version, submission or mapping truth is never
  accepted.
- Persists actor-bound idempotency, one request, its assembly nodes, the
  schema-version-2 Outbox event and audit in one transaction. Response follows
  commit; enqueue follows commit. A post-commit enqueue failure returns the
  committed request, records only a safe diagnostic and leaves the pending
  Outbox recoverable.
- Mock remains validation-only with no Outbox, attempt, mapping or target
  effect. No worker, adapter, result execution, network transport or UI was
  activated in checkpoint 2.

## Exact-SHA ordinary CI evidence

- Repository job `96828715143`: PASS; `2,221/2,221` tracked Python tests,
  current-task/repository rules and V1.2 reconciliation. The preceding run
  `32499141551` passed the same tests before a negative repository test literal
  self-triggered the direct-SQL scanner; the response-neutral AST test-harness
  remediation changed no product or Gate rule.
- Frontend job `96828715126`: PASS; `61/61` files and `1,018/1,018` unit tests,
  `444/444` E2E and `8,108` complete direct trilingual sources.
- Secret job `96828715130`: PASS; `582` branch commits contain no leak.
  Artifact `9453278724`, digest
  `sha256:4370cc7963ed58e099f2a2c29d33d5a46259c79509dd254498bcd214142b1626`.
- Visual job `96828715029`: PASS; unchanged `123/123` fixed-Linux matrix.
  Artifact `9453418895`, digest
  `sha256:f53a660832d633cd36da12a38eaf58bfb92c7a5e5ef049693c09c019e26b6803`.
- Controlled lanes skipped as required because checkpoint 2 installs no
  worker, adapter or disposable runtime behavior.

## Review and rollback

Task Diff Review found no browser-to-DocType CRUD, caller target authority,
direct SQL, cross-database access, permission bypass, pre-commit response,
pre-commit enqueue, fake Mock success, target call or formal mapping. Before
an adapter boundary, rollback disables the route/enqueue/worker and retains
every committed request, node, idempotency row, Outbox event and audit for
forward repair.

This is checkpoint 2 PASS. It is not P8-04 completion or a Level 3 Gate.
