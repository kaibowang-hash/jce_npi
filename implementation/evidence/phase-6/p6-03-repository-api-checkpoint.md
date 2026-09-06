# P6-03 Repository, BFF and API Checkpoint

Recorded: `2026-08-08T06:03:05Z`

Status:
`PASS — LEVEL 1 PROJECT-FIRST REPOSITORY, CLOSED BFF AND ROUTE SWITCH`

Requirements:
`FR-TX-004..008`, `FR-TL-002`, `FR-TL-003`, `FR-TL-006`

Exact stable checkpoint:
`07ae9860e9be37f991f9995b52d8e790e3fe901d`

## Delivered boundary

- Added Project-first bounded collection/detail reads for immutable Tooling
  Revisions, exact current-Part controlled specifications and ordered Tooling
  process-chain revisions.
- Added narrow create commands for the next exact Tooling Revision, the one
  immutable current-Part specification, a new or successor process-chain
  revision and the initial exact physical-Set source binding.
- Every command authorizes and locks the Project before protected reference
  resolution, binds replay to actor/operation/Project/payload, validates exact
  Master/Part Revision/Applicability/Document Revision/Set containment and
  effectivity, writes in one transaction, appends audit and seals the receipt.
- Added the frozen exact BFF paths and an independent fail-closed
  `npi_p6_03_routes_disabled` switch. Missing or non-false configuration keeps
  only P6-03 routes unavailable without weakening P6-01 or P6-02.
- Cockpit Revision capability and physical-Set source projection become exact
  only when that switch is explicitly open. The OpenAPI response union is
  closed and the immutable insert response preserves its exact model-source
  provenance.
- Added literal English business errors with direct `zh` and `zh-TW`
  translations. The generated catalog contains `4,316` governed sources at
  complete direct coverage.

## Deliberately unavailable

- The live SPA and disposable controlled Site remain inactive at this
  checkpoint. No production config, fixture, credential, endpoint, adapter or
  external mutation is introduced.
- `DR-REC-010` continues to hold lifecycle states, transitions, approval,
  release, supersession and authority. Revision creation is not approval or
  authorization for manufacturing or Trial execution.
- Formal Supplier, ERP Asset/location/execution, combined Trial truth,
  automatic impact action and production Tooling-list mapping remain explicit
  unavailable capabilities.
- Set source binding is one-time and append-only. It does not rewrite a P6-02
  Set snapshot, intake or evidence row.
- This is checkpoint 2, not the P6-03 Level 2 Task Gate. The live workspace,
  controlled runtime and cumulative Task Gate remain required.

## Local affected and regression evidence

- focused P6-03/P6-01/P6-02 API, repository, security, contract, metadata and
  domain tests: `63/63` PASS;
- complete tracked Python regression: `1,170/1,170` PASS;
- frontend generation, typecheck, ESLint, Prettier, style, boundary, industrial
  UI and i18n audits: PASS;
- frontend unit suite: `738/738` PASS;
- OpenAPI YAML parse, Python compilation, P0 governance, V1.2 reconciliation
  and `git diff --check`: PASS;
- dependency audit: zero vulnerabilities in all and production dependency
  graphs; and
- complete clean exact-SHA CI below supersedes local environment limitations.

The local production build compiled successfully through Vite and failed only
its final approved-static-asset guard because the workspace contains three
pre-existing user-owned untracked `frontend/public/images` files. The local
npm binary also does not provide the repository's `approve-scripts` command.
Neither file nor environment condition exists in clean CI; both corresponding
clean-CI checks passed. All user-owned development, evidence and Darwin files
were preserved and excluded from the checkpoint commits.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| `tooling/revision_repository.py` and `frappe_repository.py` | static Project-first/atomic/no-raw-SQL assertions plus API tests for exact containment, replay, version conflict and response boundary |
| `tooling_api.py`, `bff.py`, `request_security.py` and errors | exact route map, independent disabled response, CSRF/auth-before-body, System Manager mutation, request/idempotency validation and protected-not-found behavior |
| OpenAPI | YAML parse, closed response/create schemas, exact routes, no browser-supplied server truth, exact insert provenance and exact-or-unavailable Revision/Set projections |
| translation and generated catalogs | generation plus `4,316` literal English sources at complete direct `zh`/`zh-TW` coverage |
| fixed-Linux P0 baselines | artifact-reviewed footer-only catalog fingerprint delta and `76/76` clean visual matrix |

## Exact-SHA CI and bounded visual repair

Product commit `8cc04a9eb821bda654c6095ded18069132430069` ran ordinary CI
`31242202985`. Repository job `93064940926` passed the complete product,
contract, i18n, non-visual E2E and secret checks. Visual job `93064940904`
failed only the eighteen durable P0 screenshots after the four new translated
sources changed the bottom status-bar catalog fingerprint.

Artifact `9017410069`, digest
`sha256:232f0139e999dd85765d76432d0462703bf53c1d5e86c0650eab985a47416d7c`,
contained exactly eighteen actual/diff pairs. Pixel comparison against the
tracked baselines proved all `18/18` business workspaces unchanged. English
deltas were confined to half-open box `x=560..677, y=882..892`; Chinese deltas
to `x=497..613, y=882..892`. One Traditional-Chinese Trial image additionally
contained twenty 1–2 RGB anti-alias edge pixels in the bottom status controls;
no changed pixel entered the product workspace.

Isolated repair commit `07ae9860e9be37f991f9995b52d8e790e3fe901d`
copied only those eighteen reviewed Linux actuals to their exact governed
targets. It changed no component, state, assertion, matrix, threshold or PASS
rule and staged no Darwin image.

Final ordinary CI `31242679688` passed at exact stable checkpoint `07ae986`:

- repository job `93066134884`: PASS — `1,170/1,170` Python tests,
  `738/738` frontend unit tests, `315/315` non-visual E2E, `4,316` literal
  English sources with complete direct `zh`/`zh-TW`, zero dependency
  vulnerabilities and no secret leaks;
- visual job `93066134855`: PASS — `76/76` fixed-Linux cases;
- controlled runtime job `93066135083`: correctly skipped;
- visual artifact `9017540844`, digest
  `sha256:2d054f405b72316eb815afd4a3759365e153ccd586aa748e89352dd0bcb96fe6`;
  and
- Gitleaks artifact `9017596549`, digest
  `sha256:9449cd6e23e09e429b4c2e3fe778de8e110404d36b11611969c08f48e948daea`.

## Review, rollback and next checkpoint

The checkpoint is additive and fail closed. Before retained rows exist, a
disposable environment may restore the starting checkpoint and migrate fresh.
After retained rows exist, rollback disables only P6-03 routes/projections and
uses a reviewed forward repair while preserving every immutable Revision,
specification, cavity, insert, external identity, process chain, Set binding,
audit and receipt.

Checkpoint 2 is PASS. P6-03 remains in progress. Autopilot next implements
only checkpoint 3: a strict live data source and dense Project/Master-scoped
Revision/specification/cavity/insert/process-chain workspace, exact Set source
binding, complete loading/empty/read-only/unavailable/validation/conflict/
processing/retry states, accessibility, direct trilingual coverage and the
affected visual matrix. The controlled Site remains inactive until that
checkpoint passes complete ordinary CI.
