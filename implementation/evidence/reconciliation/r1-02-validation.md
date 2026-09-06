# R1-02 Validation — LaunchFlow Display Brand Adapter

Result: `PASS — LEVEL 2 SHARED-SHELL/I18N TASK GATE`

Date: 2026-07-26

Starting synchronized bridge checkpoint:
`0955dca7a6776734d4d864a3b5db6ef44b676ec4`

Primary requirement: `FR-BR-001`

## Delivered boundary

- Added one local display-brand adapter that imports the five exact supplied
  LaunchFlow SVGs from the sole-source brand directory and maps each asset only
  to its CSV-authorized context.
- Replaced the dark Shell text mark with the white LaunchFlow wordmark and
  added the standard LaunchFlow wordmark plus Company logo to the persistent
  neutral-light footer.
- Added the LaunchFlow icon as the pre-React favicon and as compact
  `NPI_ONE` platform/source identity with translated accessible names and a
  keyboard-reachable tooltip.
- Added the supplied Loading asset only to the full-surface localization
  bootstrap. The bootstrap is cancellable, has an exact 15-second timeout,
  retains an honest production error/retry state and uses an explicit
  development-only fallback.
- Migrated user-facing product-name copy to LaunchFlow while retaining
  `NPI_ONE`, `ERPNEXT`, `/api/npi/v1`, package, DocType, database, storage and
  integration identities.
- Added direct English-source, Simplified Chinese and Traditional Chinese
  catalog coverage without fallback or translated contract values.
- Added a production-output asset verifier plus adversarial tests. The verifier
  locks the five exact SVG hashes and contexts, scans source/config/public and
  every built output, rejects exact Core bytes and any `Core.*` stem, and fails
  closed on every non-manifest static/binary asset in `src`, `public` or
  `dist`. It does not claim general visual-similarity detection.
- Registered the subsequently supplied `Core.png` and strict PNG/CSV safety
  checks as the resolved DR-REC-006 input while keeping runtime activation
  allocated exclusively to `FR-BR-002`/Phase 8/M7-09.

No public API, event schema, DocType, database migration, permission model,
data-ownership contract, external integration behavior or production
connection changed. R1-03, P5-01 and later product behavior remain outside this
task.

## Changed-files to affected-tests

| Change family | Evidence and checks |
|---|---|
| exact display-brand adapter and five governed SVG contexts | `display-brand.test.tsx`, `display-brand.spec.ts`, production `verify:brand`, exact SVG hash/context scan |
| pre-React favicon and localization bootstrap | static HTML/build inspection; session/i18n unit timeout, abort, fallback, error, retry and unmount cases; browser entry-state cases |
| shared header/footer/source identity and CSS | Shell/component unit tests; Axe and keyboard tooltip cases; complete 234-case browser run; complete 195-case zero-tolerance visual run |
| displayed product copy and catalogs | generation freshness; 2,482-source i18n audit; direct `zh`/`zh-TW` coverage; three-language DOM/shadow mixed-language scans |
| deferred `Core.png` source input and guard | reconciliation verifier; eight focused Python tests; five Node negative/positive guard tests; strict source/public/output static-asset manifests |
| trace/controller/evidence | generated trace freshness; exact `FR-BR-001` verified-state/evidence assertion; YAML parse; `git diff --check`; historical evidence preservation |

## Complete frontend Task Gate

The final frontend command ran in the repository's fixed Node 24 development
container:

```text
docker exec \
  --env NPI_EVIDENCE_SCOPE=reconciliation/r1-02 \
  --workdir /workspaces/jce_npi/frontend \
  ec8758984064 npm run verify
```

Result: `PASS`.

- generation and generated-catalog freshness: `PASS`;
- TypeScript, ESLint, Prettier, Stylelint, module boundary and industrial UI
  static checks: `PASS`;
- i18n extraction: `2,482` literal English sources with `100%` direct
  `zh`/`zh-TW` coverage;
- Vitest: `499/499 PASS`;
- aggregate coverage: `84.98%` statements, `84.02%` branches, `89.71%`
  functions and `86.93%` lines;
- production Vite build: `PASS`, emitting exactly the five supplied LaunchFlow
  SVGs and no `Core.png`/`Core.*` output;
- deferred-Core guard tests: `5/5 PASS`;
- reviewed install scripts: none pending; and
- full and production-only npm audits: `0` vulnerabilities.

Portable coverage evidence:

```text
implementation/evidence/reconciliation/r1-02/coverage/coverage-summary.json
SHA-256 ff1e02895e502d3cc47857a99012b3d84b7c5968201134e07731985ee8b24896
```

## Browser, accessibility and visual evidence

```text
docker exec \
  --env NPI_EVIDENCE_SCOPE=reconciliation/r1-02 \
  --workdir /workspaces/jce_npi/frontend \
  ec8758984064 npm run test:e2e
```

Result: `PASS — 234/234`.

The complete non-visual suite covers English, Simplified Chinese and
Traditional Chinese, keyboard focus, accessible tooltip linkage, Axe, exact
asset placement, bootstrap/error/retry truth, stable source identity and all
existing live shared-Shell flows.

```text
docker exec \
  --env NPI_EVIDENCE_SCOPE=reconciliation/r1-02 \
  --workdir /workspaces/jce_npi/frontend \
  ec8758984064 npm run test:visual
```

Result: `PASS — 195/195`, clean comparison at unchanged zero tolerance.

The shared Shell change intentionally updated 198 baseline PNGs: seven new
LaunchFlow-specific Shell/focus cases and 191 existing affected Shell cases.
The final comparison ran after the tooltip-anchor geometry fix and keyboard
focus-state baseline were added, and used no snapshot update flag. The outer
command channel disconnected after the container test had started; the
container process was monitored to completion before the result was accepted.
The final Playwright result is:

```text
{"status":"passed","failedTests":[]}
```

Durable evidence:

```text
implementation/evidence/reconciliation/r1-02/playwright-results/.last-run.json
SHA-256 91d1c43004802cd49950d78eb11c8fa7d05da8ffffe219a8b13b2f561bc00903

implementation/evidence/reconciliation/r1-02/playwright-report/index.html
SHA-256 172774c4851694519e4c3089d235e3f9f981c7b8b776f852779bf433b8d600d8
```

## Reconciliation, trace and repository checks

```text
PYTHONDONTWRITEBYTECODE=1 \
  python3 -m unittest tests.test_v1_2_reconciliation -v
python3 scripts/verify_v1_2_reconciliation.py
git diff --check
git diff --exit-code HEAD -- \
  implementation/evidence/phase-3 \
  implementation/evidence/phase-4
```

Result: `PASS`.

The checks lock:

- 229/43/281 reconciliation cardinalities and 173/95/13 trace-kind counts;
- exact brand filenames, hashes, self-contained SVGs and strict CSV parsing;
- bounded, structurally valid non-animated PNG input with verified chunks/CRC;
- `FR-BR-001` as `TECHNICAL_VERIFIED` with the complete R1-02 runtime evidence
  set;
- `Core.png` as a Phase 8-only approved input, not an R1 runtime asset; and
- unchanged historical Phase 3 and Phase 4 evidence.

## Task Diff and release-blocker review

- Scope is limited to the approved LaunchFlow display boundary, the
  user-supplied deferred Core input, direct translations, affected shared-Shell
  call sites/tests/baselines and reconciliation/controller evidence.
- No dependency was added, no Siemens/Frappe/ERPNext core was patched, no Desk
  product path was introduced, no cross-database access or dual-master field
  appeared, and no production identifier, credential or test backdoor was
  added.
- Bootstrap failure remains visible and retryable; no asynchronous or ERP
  outcome is represented as successful before confirmation.
- Exact-byte/name checks plus strict source/public/output manifests reject
  changed-byte renamed binaries through the governed static-asset path. The
  evidence makes no unprovable claim about arbitrary perceptual derivatives.
- Independent code review findings on bounded bootstrap failure, keyboard
  tooltip access, pre-React favicon and asset-guard bypasses were repaired and
  retested. Final code review has no blocker or major finding.
- Independent original-resolution visual review inspected all seven new
  brand/focus baselines plus eight active shared-Shell cases across all three
  languages and 100/125/150% profiles: `PASS — 0 blocker / 0 major / 0 minor`.
- The UI remains square, flat, dense, neutral and single-primary. Brand colors
  stay inside the immutable supplied marks and do not change component tokens.
- All touched user-visible copy uses literal English translation sources with
  complete direct Simplified/Traditional Chinese coverage.

Release-gate Skill decision for this atomic Level 2 boundary:
`PASS`. This does not claim the cumulative R1 Level 3 bridge Gate, a controller
Phase PASS, PR merge approval or production readiness.

## Rollback and transition

Before branded history is retained, revert the R1-02 frontend/catalog/trace
implementation while preserving the exact user-supplied brand package and
ADR-012. There is no schema, business-data, external-system or production
rollback. After branded outputs exist, make a reviewed forward display change
instead of rewriting historical evidence.

R1-02 is complete. Activate only:

`R1-03 — App Shell collapsed navigation command and contextual quick-create`

P5-01 remains checkpointed/held. R1-07 remains scoped to DR-REC-001. P5-01
cannot resume until R1-03 through R1-06 and the shared Shell/design/i18n
Level 3 bridge Gate pass.
