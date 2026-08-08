# P6-04 Domain, Contract and Metadata Checkpoint

Recorded: `2026-08-08T12:41:00Z`

Status:
`PASS — LEVEL 1 DOMAIN, CLOSED CONTRACT AND GUARDED METADATA`

Requirements:
`FR-TL-005`, `FR-TL-006`, `FR-TL-007`, `FR-TL-008`

Exact stable checkpoint:
`00956b45e5bc7408d856b9e2a416d6f0f6d4b88e`

## Delivered boundary

- Added immutable internal manufacturing-plan revisions with direct predecessor
  lineage, exact Tooling Revision/hash binding, make/buy/hybrid planning,
  current Project-member responsibility, one-currency estimate/budget facts,
  released planning-document evidence and a bounded ordered acyclic milestone
  schedule.
- Added immutable internal-user milestone observations with exact plan/milestone
  hashes, direct observation lineage, progress and actual dates, bounded risk/
  note text, and exact clean private File Revision evidence.
- Added exact controlled-document release evidence and two separate capability
  truths: design evidence can be satisfied only by the full exact released
  design-document set, while Tooling manufacturing authorization remains
  unavailable under `DR-REC-010`.
- Added a closed read-only ERPNext procurement/cost projection domain. The
  production-default branch is explicitly unavailable; the available branch
  requires target-confirmed Supplier/source/version truth and deterministic
  exact-code aggregation.
- Added two guarded additive DocTypes, two command-receipt operation/target
  pairs, exact ownership rows and closed OpenAPI component schemas. No P6-04
  route or projection adapter is active at this checkpoint.
- Added literal English sources with complete direct `zh` and `zh-TW`
  translations. The generated catalog contains `4,528` governed sources.

## Deliberately unavailable

- No repository, BFF route, live SPA command, controlled-Site execution,
  business row, production policy, fixture, default milestone template,
  endpoint, credential or ERPNext connection is activated by this checkpoint.
- A released controlled Document proves only that exact evidence revision's
  lifecycle/event/hash truth. It does not release the Tooling Revision,
  authorize manufacturing, approve funding, pass G3 or create PO readiness.
- Formal Supplier, PO, receipt, invoice, payment and actual-cost truth remain
  ERPNext-owned and read-only. No supplier account, portal, external actor,
  supplier-submitted observation or ERP write/retry/replay claim exists.
- Production Tooling-list mapping/import, automatic health/impact action,
  Trial truth, ERP Asset/location/execution and P6-05 or later behavior remain
  outside this checkpoint.
- This is checkpoint 1, not the P6-04 Level 2 Task Gate. Repository/BFF, live
  workspace and controlled runtime evidence remain required.

## Local affected and regression evidence

- focused Phase 6 Tooling domain/metadata/contract regression: `117/117` PASS;
- complete local Python discovery: `1,204/1,204` PASS, including six
  pre-existing user-owned untracked local-prerequisite tests; the clean tracked
  exact-SHA CI independently passed `1,198/1,198` below;
- frontend unit suite: `744/744` PASS;
- catalog generation/check, TypeScript, ESLint, formatting, style, boundary,
  industrial UI and i18n audits: PASS;
- OpenAPI/YAML/JSON parsing, Python compilation, P0 visual-governance verifier
  and its `7/7` unit suite, full reconciliation and `git diff --check`: PASS;
- byte comparison against the failed exact-SHA artifact: all `18/18` reviewed
  Linux baseline targets match their corresponding actuals; and
- complete clean exact-SHA CI evidence below supersedes bounded local results.

The local production build compiled through Vite and stopped only at its final
approved-static-asset guard because the workspace contains the pre-existing
user-owned untracked
`frontend/public/images/npi-one-project-management-sketch.png`. The file was
preserved and excluded from every checkpoint commit. Other user-owned
development, evidence and Darwin files were also preserved.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| `tooling/manufacturing_domain.py` | plan/observation predecessor and hash lineage, member/money/evidence/milestone graph, exact design release capability and strict ERP projection/aggregation cases in `test_phase6_tooling_manufacturing_domain.py` |
| two guarded DocTypes/controllers and receipt values | exact fields/options, snapshot consistency, current member, exact Master/Revision/document lifecycle/event/File containment, immutability and generic CRUD/delete/export/print denial in `test_phase6_tooling_manufacturing_metadata.py` and existing Tooling metadata regression |
| OpenAPI and data ownership | closed component schemas, ownership, inactive-route boundary and no fake manufacturing/Supplier/ERP claim in `test_phase6_tooling_manufacturing_contract.py` |
| translation catalogs/generated catalog | generation plus `4,528` literal English sources at complete direct `zh`/`zh-TW` coverage and mixed-language audit |
| shared footer fingerprint baselines | exact eighteen fixed-Linux screenshots, byte equality to reviewed CI actuals and P0 visual-governance verifier |

## Exact-SHA CI and bounded visual repair

Product commit `7aa26a4f27d3e02a47ecdd385b61aa037845a476` ran ordinary CI
`31256971673`. Repository job `93101716038` passed the complete product,
contract, i18n, non-visual E2E and secret checks. Visual job `93101716079`
passed `61/79` and failed only the eighteen durable P0 screenshots after the
new translated sources changed the bottom status-bar catalog fingerprint.

Artifact `9021697529`, digest
`sha256:3483707a0096f197d13123e7088d849d157642f09ca70c17863e62c94f923da9`,
contained exactly eighteen actual/diff pairs. Pixel comparison against the
tracked baselines proved all `18/18` product workspaces unchanged. English
deltas were confined to half-open box `x=560..677, y=882..892`; Simplified-
and Traditional-Chinese deltas were confined to
`x=496..613, y=882..892`.

Isolated repair commit
`00956b45e5bc7408d856b9e2a416d6f0f6d4b88e` copied only those eighteen
reviewed Linux actuals byte-for-byte to their exact governed targets. It
changed no component, state, assertion, visual matrix, threshold or PASS rule
and staged no user-owned or Darwin file.

Final ordinary CI `31257408124` passed at exact stable checkpoint `00956b4`:

- repository job `93102812133`: PASS — `1,198/1,198` tracked Python tests,
  `744/744` frontend unit tests, `321/321` non-visual E2E, `4,528` literal
  English sources with 100% direct `zh`/`zh-TW`, statements `80.07%`, zero
  dependency vulnerabilities and no secret leaks;
- visual job `93102812149`: PASS — `79/79` fixed-Linux cases;
- controlled runtime job `93102812647`: correctly skipped;
- visual artifact `9021818155`, digest
  `sha256:206a46f4564b9d4345d22645aaf57fb9f22bf09c9214547ed650993d43769fd1`;
  and
- Gitleaks artifact `9021878830`, digest
  `sha256:a9ff059a0afabedafc6cccc24acaa550fde109ae333e6b1b1187acd597da76af`.

## Review, rollback and next checkpoint

The checkpoint is additive, creates no business rows and activates no route.
Before retained rows exist, a disposable environment may restore the starting
checkpoint and migrate fresh. After retained rows exist, rollback disables
only later P6-04 routes/projections and uses a reviewed forward repair while
preserving every immutable plan revision, milestone, observation, evidence,
audit and receipt.

Checkpoint 1 is PASS. P6-04 remains in progress. Autopilot next implements
only checkpoint 2: Project-first bounded plan/observation reads and narrow
append commands; exact Master/Revision/member/document/lifecycle/event/File
containment; System Manager-only mutation; actor-bound idempotency; one
transaction; append-only audit; a closed injected read-only ERP projection
boundary; an independent fail-closed route switch; and exact API/IDOR/no-ERP-
write tests. The live SPA and controlled-Site runtime remain inactive until
that checkpoint passes affected checks and complete ordinary CI.
