# P8-04 Checkpoint 1 — MBOM Domains, Contracts and Guarded Metadata

Recorded: `2026-08-21`

Decision: `PASS — CHECKPOINT 1; CHECKPOINT 2 AUTHORIZED`

Final product checkpoint:
`97cdfbb843aeac422c71f57434a4a39f22c1954a`

Ordinary pull-request CI: `32495121120`

## Scope delivered

- Added dependency-free exact released-topology, Item-readiness, immutable
  request/profile/state/fault/result and MBOM mapping compare-and-set domains.
  Direct-parent lines are assembly nodes, leaves remain component-only, and
  every Sandbox-bound node requires an exact current authenticated P8-03 Item
  mapping. Mock exposes explicit not-ready truth and synthetic references are
  source-derived, disposable and non-authoritative.
- Added closed MBOM-only event, OpenAPI and field-ownership contracts. The
  immutable command binds the exact Phase 5 release, topology, Item-mapping
  set, MBOM expectation set and profile hashes; submitted BOM mappings block
  overwrite, and formal MBOM mapping can advance only from an authenticated
  authoritative Sandbox observation under exact per-node compare-and-set.
- Added an isolated schema-version-2 MBOM branch to the shared Outbox and nine
  read-only support DocTypes. Existing Item version-1 and legacy rows retain
  their exact behavior. Narrow internal capabilities guard all writes;
  request/node/idempotency records are insert-only and terminal/result/
  observation history is append-only or immutable as specified.
- Added direct Simplified and Traditional Chinese translations and regenerated
  the Frappe-backed frontend catalog. No BFF route, persistent command or
  Outbox row, worker, adapter, target call, mapping observation or UI behavior
  was activated.

## Changed-files to affected-checks map

| Changed boundary | Affected evidence |
|---|---|
| `mbom_publish/domain.py` and `config.py` | exact topology/hashes, Item readiness, Mock/synthetic/Sandbox isolation, submitted blocking, state/fault/partial/uncertain and mapping-CAS tests |
| event/OpenAPI/ownership contracts | closed MBOM-only schemas, exact ownership, no generic CRUD, caller target authority, routing/submission or secret fields |
| Outbox and nine support DocTypes/controllers | version-2 isolation, Item/legacy non-regression, exact permissions, lifecycle capability, immutable history and zero default execution |
| both translation CSVs and generated catalog | Frappe v15 no-header CSV parsing, literal-English symmetry, direct `zh`/`zh-TW`, generated-catalog equality and mixed-language audit |
| focused Phase 8 tests | no route, row, worker, adapter, scheduler, network, formal mapping or target effect activation |

## Local Level 1 and task evidence

- Focused new checkpoint tests and affected Item/Phase 2 regression: `107/107
  PASS`; real Frappe insert lifecycle ordering proves insert-only request/node/
  idempotency controllers accept only the insert capability while stream and
  mapping heads retain their real save capability.
- Python compilation, JSON/YAML/CSV parsing, current-task verification,
  reconciliation, direct translation checks and `git diff --check`: PASS.
- Local Gitleaks `8.24.3` exact `origin/main..HEAD` history scan: `580`
  commits, no leaks. The earlier `32493590200` finding was only a synthetic
  configuration fixture in the checkpoint tip; the tip-only amend replaced it
  with an already governed test value and changed no product contract, secret,
  permission, threshold or Gate rule.

## Exact-SHA ordinary CI evidence

- Repository job `96811612041`: PASS; `2,206` tracked Python tests plus
  repository and V1.2 reconciliation verification.
- Frontend job `96811612188`: PASS; `61/61` files and `1,018/1,018` unit
  tests, `444/444` E2E, generation/type/lint/build/audit and `8,095` complete
  direct trilingual sources.
- Secret job `96811612042`: PASS; full branch history contains no leak.
  Artifact `9451286203`, digest
  `sha256:5013c191ac9fca8871f5a7c8950d905650a1578097fb58c89b6371a9c44ab4ab`.
- Visual job `96811611815`: PASS; unchanged `123/123` fixed-Linux matrix.
  Artifact `9451427672`, digest
  `sha256:3ae4a5d048f500524676fddfb73a21a3bc54f69c174d74854ca528668ea79011`.
- Controlled preflight and cumulative runtime skipped as expected because the
  checkpoint activates no route, repository row, worker, adapter, fixture or
  external transport.

## Review and rollback

Task Diff Review found no latest-value topology, missing Item-mapping
prerequisite, combined Item/MBOM command, caller-selected target authority,
Mock or synthetic formal mapping, submitted overwrite, optimistic acceptance,
legacy/Item Outbox promotion, generic retry/replay, production fallback,
network call or target effect.

Before an adapter boundary exists, rollback disables later MBOM routes and
retains every committed request, node, idempotency, Outbox and audit record for
forward migration. Later rollback remains forward-only after any adapter
boundary: never delete or blindly redispatch uncertain history, rewrite
partial/failure/Mock/synthetic truth to success, change a formal BOM identity,
mutate released source, submit or overwrite a BOM, or compensate a target
automatically.

This is checkpoint 1 PASS. It is not P8-04 completion or Phase 8 Level 3.
