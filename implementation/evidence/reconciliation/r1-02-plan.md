# R1-02 Plan — LaunchFlow Display Brand Adapter

Status: `COMPLETE — see r1-02-validation.md`

Date: 2026-07-26

Starting synchronized checkpoint:
`0955dca7a6776734d4d864a3b5db6ef44b676ec4`

Primary requirement: `FR-BR-001`

## Scope

- introduce one local display-brand adapter that maps the five exact supplied
  LaunchFlow SVGs to their CSV-authorized contexts;
- set the LaunchFlow document title and favicon through that adapter;
- show the supplied Loading asset only during the pre-Shell localization
  bootstrap/full-surface entry state;
- replace the Shell text mark with the supplied white wordmark on the dark
  header;
- place the supplied standard wordmark and Company logo in the persistent
  neutral-light website footer;
- use the supplied square icon for compact `NPI_ONE` platform/source identity
  while retaining a translated accessible name;
- migrate user-visible product copy from NPI One to LaunchFlow where it names
  the displayed product, without changing technical identities; and
- add direct English-source/`zh`/`zh-TW` catalog coverage plus affected unit,
  browser, visual, accessibility and exact-scope assertions.

## Non-scope

- no redraw, recolor, crop, optimization or byte change to a supplied asset;
- no inferred palette or change to industrial teal/neutral design tokens;
- no Company-logo use outside the persistent footer;
- no Loading-logo use for route, table, object or inline loading;
- no early `Core.png`/JCE Core runtime activation and no invented ERP/JCE mark
  or external brand lookup;
- no rename of `NPI_ONE`, `ERPNEXT`, `/api/npi/v1`, packages, Apps, DocTypes,
  database identities, storage keys or integration contract values;
- no backend behavior, public API, schema, migration, ownership or production
  connection change; and
- no R1-03, P5-01 or later-task work.

## Facts, assumptions and decisions

- `docs/Brand Asset/Brand Asset Instruction.csv`, its five adjacent LaunchFlow
  SVGs and the subsequently supplied `Core.png` are the sole brand source.
  R1-02 consumes only the five LaunchFlow SVGs; the user-approved JCE Core
  input resolves DR-REC-006 and remains allocated to Phase 8/M7-09.
- The existing header is a dark Shell surface. The existing status bar is the
  persistent footer and may become a neutral-light surface without changing
  its status/control function.
- `LaunchFlow` is the displayed product name evidenced by the supplied asset
  filenames and accepted ADR-012. It is added as a retained product name with
  identical direct `zh` and `zh-TW` translations.
- Existing route/object loading remains a skeleton/text pattern. Only the
  initial Frappe localization bootstrap receives the full-surface Loading
  asset.
- Asset URLs are bundled directly from the sole-source directory. No copied
  frontend asset directory is introduced.

## Risks

- a copied or scattered asset path could drift from the sole source;
- the blue detail inside an immutable asset could be mistaken for a new UI
  token;
- the persistent footer could become crowded at zoom/responsive widths;
- replacing source text with an icon could remove provenance from assistive
  technology;
- startup gating could accidentally hide localization failure recovery; and
- shared Shell changes could disturb existing screenshots beyond the bounded
  brand surfaces.

## Planned change surface

- `frontend/src/ui-adapters/display-brand.tsx`;
- Shell/bootstrap/provenance call sites under `frontend/src/`;
- `frontend/index.html` and token-only rules in
  `frontend/src/styles/app.css`;
- canonical Frappe `zh` and `zh-TW` catalogs plus the generated React catalog;
- the retained-term registry;
- focused unit/E2E/visual tests; and
- R1-02 evidence, trace and recovery/controller state after validation.

No product backend, contract schema, DocType or migration file is in scope.

## Changed-files to affected-tests map

| Change family | Required checks |
|---|---|
| adapter and exact context map | unit assertions for all five LaunchFlow assets, filenames, DOM roles and no copied asset package; R1 brand hash/CSV verifier also locks the deferred `Core.png` input |
| document/bootstrap brand | title/favicon and initial full-surface loading unit/browser checks; translated accessible name; no Loading asset after Shell entry |
| header/footer brand | Shell unit assertions; English/`zh`/`zh-TW` browser assertions; representative 1366×768, 1440×900 and 1920×1080/zoom visual evidence |
| `NPI_ONE` source identity | NPI icon/accessibility tests; ERPNext/computed text fallback tests; stable-code scans |
| display copy/catalogs | extraction, direct catalog coverage, placeholder, hard-coded-copy, terminology and three-language mixed-language scans |
| shared CSS | Stylelint/UI-token checks, responsive overflow, one-primary-action, Axe and visual diffs |

## Task Gate

R1-02 uses a Level 2 affected shared-Shell/i18n Task Gate:

- generation freshness, TypeScript, ESLint, Prettier, Stylelint, boundary,
  industrial-UI and i18n checks;
- complete frontend unit coverage;
- focused brand browser/accessibility and representative affected visual
  matrix;
- frontend build and dependency audit;
- R1 reconciliation/asset integrity verification;
- stable technical-identity and prohibited-asset-use scans;
- `git diff --check`, requirement trace and Task Diff Review.

The complete shared Shell/design/i18n Level 3 bridge Gate remains cumulative
and runs only at the R1 exit boundary.

## Rollback

Before downstream branded history exists, revert the R1-02 implementation and
catalog changes while retaining the exact supplied brand package and ADR-012.
No schema, data or external system rollback is required. After branded outputs
exist, use a reviewed forward display configuration rather than rewriting
historical evidence.
