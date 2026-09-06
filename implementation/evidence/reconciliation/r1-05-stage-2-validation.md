# R1-05 Stage 2 Validation — FR-UX-041 Field and Attachment Truth

Result:
`PASS — LEVEL 2 R1-05 STAGE 2 FIELD/ATTACHMENT TRUTH TASK GATE`

Date: 2026-07-27

Stage 2 starting checkpoint:
`749665e5428208f0453832b7f394eddcb6deebca`

Target requirements:

- `FR-UX-040`: remains `TECHNICAL_VERIFIED`
- `FR-UX-041`: `TECHNICAL_VERIFIED`
- `FR-UX-043`: remains `PLANNED_SHARED_UX_REMEDIATION`

The exact Stage 2 field, attachment, state-machine, privacy, accessibility,
browser, localization and visual acceptance evidence passed the bounded Level
2 Task Gate. This checkpoint advances only `FR-UX-041`. R1-05 remains
`IN_PROGRESS`; only Stage 3 is ready next.

## Delivered boundary

- Added a reusable `FieldTruth` presentation contract for requiredness,
  editability, source and editable system, lock reason, validation, unit, exact
  version, effectivity, help and complete control accessibility metadata.
- Added a closed attachment workflow with explicit loading, empty, local
  selection, local validation failure, transport, registration, registered,
  failed, conflict and denied states.
- Kept actual transport injected. The primitive reports only callback-provided
  bytes, preserves unknown totals as indeterminate and never simulates upload
  progress, registration or scanner results.
- Made write truth monotonic across `none`, `unconfirmed` and `registered`.
  Registration, scan and registered-revision claims cannot be downgraded to a
  retryable local state. Null, malformed and contradictory transport results
  fail closed instead of leaving a busy state or reopening replacement.
- Kept the selected file name, media type and size visible during transport,
  registration, failure and conflict so the operator can identify the exact
  local file being processed.
- Supported local clear/reselection only before a confirmed or unconfirmed
  server write. No detach, delete or replacement control exists for a
  registered immutable revision.
- Rendered exact registered revision, SHA-256, scanner state, scanner
  observation, privacy, confidentiality key, provenance, attachment
  permission and preview/download capability truth. Missing facts remain
  visibly unavailable; non-clean scan states fail closed even if a source
  claims a capability is available.
- Integrated the primitive into the Trial photo field without adding a
  transport. The Trial surface truthfully states that selection remains local.
- Integrated the registered read-only primitive into the existing Gate
  evidence detail using only the URL-free File Revision facts already exposed
  by that view model. Broader Gate attach permission is not inferred as
  per-file permission.
- Added literal English source copy, complete direct `zh` and `zh-TW`
  translations, industrial square/flat styling, a dark-teal native progress
  accent and exact trilingual visual evidence.

## Changed-files to affected-tests

| Changed files / boundary | Required affected checks | Final evidence |
|---|---|---|
| `frontend/src/components/attachment-workflow.ts` | State transitions, stale callback/unmount guards, actual progress, registration monotonicity, retry limits, null/malformed/contradictory result handling | Attachment unit suite `37/37 PASS`; complete frontend unit suite `614/614 PASS` |
| `frontend/src/components/field-attachment-primitives.tsx` | Field metadata/accessibility, controlled/workflow source exclusivity, required native validity, local clear/drop, visible async file identity, scanner/write/capability truth, read-only/denied boundaries | Affected unit group `108/108 PASS`; focused browser suite `12/12 PASS` |
| `frontend/src/pages/trial-page.tsx`; `frontend/src/pages/gate-evidence-page.tsx` | Trial local-only/read-only behavior; Gate exact registered revision/hash/scan truth; no raw link or inferred capability | Affected unit group `108/108 PASS`; page behavior `20/20 PASS`; Gate visual matrix `23/23 PASS`; Trial visual matrix `24/24 PASS` |
| `frontend/src/styles/app.css`; `frontend/tests/e2e/support.ts` | Square flat industrial geometry, stable density, non-color state expression and actual-progress brand accent | Style/UI static audits PASS; focused computed-style assertion and exact visuals `3/3 PASS` |
| `frontend/tests/e2e/r1-05-field-attachments.spec.ts`; three focused snapshots | Keyboard picker/focus recovery, browser `File` drag/drop, language refresh, read-only boundary, exact scan facts, capability fail-closed behavior and three locale/viewport/zoom profiles | `12/12 PASS`, comprising nine behavior/computed-style cases and three exact visual cases |
| `frontend/tests/e2e/states-locales-accessibility.spec.ts`; nineteen affected Trial snapshots | Existing Trial field-tablet/phone, deterministic state, geometry and locale regressions | Affected behavior and final Trial exact-visual runs PASS at unchanged zero tolerance |
| `apps/npi_core/npi_core/translations/zh.csv`; `zh-TW.csv`; `frontend/src/generated/catalogs.ts` | Literal-source extraction, direct translation coverage, placeholders, controlled terminology and mixed-language scans | `2,735` literal English sources; direct `zh`/`zh-TW` coverage `100%` |
| `implementation/REQUIREMENT_TRACEABILITY.csv`; reconciliation generator/verifier/tests; this validation | Exact `FR-UX-041` verified evidence, unchanged 282-row inventory and inactive `FR-UX-043` | Generator freshness, reconciliation unit tests `12/12` and standalone verifier PASS |

## Field and attachment truth contract

Field metadata is presentation truth, not a translated business key:

- `sourceSystem` remains the stable `SourceSystem` contract.
- `editableIn` reuses the authoritative
  `SourceStatus["editableIn"]` closed union and therefore cannot accept a
  computed or invented system.
- Translated labels are rendered only for the current locale; codes, file
  names, hashes, versions and units use the existing exact exemption
  boundaries.
- Requiredness is expressed through the visible field truth, native file-input
  validity and `aria-required`. Read-only and denied state remove all mutation
  paths rather than relying on a hidden or disabled visual approximation.

The attachment workflow preserves these state invariants:

1. A local file may be selected, validated, cleared or replaced only while no
   server write is claimed.
2. Transport progress is accepted only as non-negative monotonic safe-integer
   byte counts. A total is optional; an actual `<progress>` value is rendered
   only when the transport provides a valid total.
3. Once registration starts, later failure remains `unconfirmed` and cannot
   become retryable.
4. A scanner-stage failure implies a retained registered revision and permits
   no local retry, clear or replacement.
5. A malformed successful envelope implies an unconfirmed write; an
   out-of-contract registered-write failure retains the stronger registered
   truth.
6. Completion, failure and conflict remove `aria-busy`; callbacks from stale,
   aborted or unmounted operations cannot mutate the current state.
7. Registered file actions are never derived from scan cleanliness alone.
   Exact permission and exact preview/download capability facts must both be
   present; unavailable facts remain unavailable.

## Security, privacy and immutable-revision review

- Stage 2 adds no upload endpoint, generic file service, public API, DocType,
  role, permission, authentication behavior or external-system connection.
- The Trial integration has `transport: null`; selecting a file performs no
  network request and claims no upload, registration or scan.
- Gate evidence consumes only existing URL-free metadata. No `/private/files/`
  path, raw URL, `href` or `src` is emitted as file authority.
- A broad `canAttachEvidence` workspace permission is not treated as exact
  permission for an existing file revision.
- Privacy, confidentiality, provenance, scanner observation, permission and
  capability facts are never fabricated from adjacent fields. Missing facts
  use the explicit unavailable state.
- Registered, infected, scan-failed, scan-pending, unconfirmed and conflict
  states expose no local clear, replacement or transport-retry path.
- No file bytes, user identifiers, customer values, URL, token, credential or
  production data are stored in evidence artifacts.

## Schema, migration and dependency review

- Public API/OpenAPI change: **none**.
- Database schema, DocType, migration, patch or backfill: **none**.
- Authentication or permission-model change: **none**.
- Design-token or translation-framework change: **none**. The shared CSS and
  generated catalog changes are bounded consumers of existing tokens and the
  existing Frappe-compatible translation pipeline.
- Production dependency or lockfile change: **none**.
- Production ERPNext, JCE, CAD, PDM, scanner, viewer or file-provider access:
  **none**.

These bounded presentation and fixture integrations make Level 2 the
applicable final task gate. No Level 3 trigger was introduced.

## Rollback and recovery

- Revert the bounded Stage 2 commit to restore the prior Trial local file
  control and Gate detail rendering. No server or production data must be
  migrated or deleted.
- The attachment workflow has no persistent client storage and owns no
  registered revision. Removing the presentation cannot delete or mutate
  controlled evidence.
- Translation rows and generated catalog entries are additive and are removed
  with the same code rollback.
- Visual baselines roll back with their exact affected source surface.
- If a future approved transport is introduced, it must retain the injected
  contract and receive its own API, permission, idempotency, scanner and
  reconciliation review; this Stage 2 PASS does not authorize it.

## Level 2 evidence

### Static, unit, coverage, build and audit

Canonical Node 24 command:

```text
docker exec --workdir /workspaces/jce_npi/frontend ec8758984064 npm run verify
```

Result: `PASS`.

- generated policy labels, design tokens and catalogs: fresh;
- TypeScript, ESLint, Prettier, Stylelint, boundary and industrial UI audits:
  PASS;
- unit tests: `614/614 PASS` across `27/27` files;
- coverage: statements `85.51%`, branches `83.61%`, functions `89.33%`,
  lines `87.61%`;
- production build: PASS;
- supplied display-brand asset guard: PASS;
- package install-script policy: PASS;
- `npm audit` and `npm audit --omit=dev`: `0` vulnerabilities.

The host Node 18 preflight reached coverage and failed to load
`node:inspector/promises`, which is unavailable in that non-canonical
toolchain. It is not a product failure. The repository-approved Node 24
container command above completed the entire gate.

Affected unit command:

```text
npx vitest run tests/unit/field-attachment-primitives.test.tsx tests/unit/gate-evidence-page.test.tsx tests/unit/pages-and-shell.test.tsx
```

Result: `108/108 PASS`.

### Localization

```text
npm run lint:i18n
```

Result:
`PASS — 2,735 literal English sources; 100% direct zh/zh-TW coverage`.

No ordinary English appears in the Simplified or Traditional Chinese
acceptance surfaces, and no Chinese source copy was introduced into TSX.

### Focused browser, accessibility and visual evidence

Terminal focused command:

```text
NPI_EVIDENCE_SCOPE=reconciliation/r1-05/stage-2/field-attachment npx playwright test tests/e2e/r1-05-field-attachments.spec.ts
```

Result: `12/12 PASS`.

The browser suite covers:

- keyboard-visible picker, clear and focus recovery;
- an actual browser `File` through drag/drop;
- retained-validation retranslation after in-page language change;
- read-only mutation removal;
- actual progress `accent-color` equality to
  `--npi-color-brand-primary`;
- exact pending, clean, infected and failed scanner truth without inferred
  per-file permission;
- Axe, overflow, mixed-language and square/flat industrial checks; and
- three exact screenshots: English `1366×768 @100%`, Simplified Chinese
  `1440×900 @125%`, Traditional Chinese `1920×1080 @150%`.

The affected page behavior replay passed `20/20`; the Gate visual replay
passed `23/23`; and the final clean Trial visual replay passed `24/24` at the
unchanged `maxDiffPixelRatio: 0`. Nineteen existing Trial baselines were
reviewed and updated for the new explicit field/attachment truth layout. The
three new focused snapshots are:

- `r1-05-field-attachment-local-en-1366x768-100-linux.png`
- `r1-05-field-attachment-pending-zh-1440x900-125-linux.png`
- `r1-05-field-attachment-clean-permission-unavailable-zh-TW-1920x1080-150-linux.png`

### Trace and reconciliation

```text
python scripts/reconcile_v1_2_traceability.py --apply
python -m unittest tests.test_v1_2_reconciliation -v
python scripts/verify_v1_2_reconciliation.py
python scripts/reconcile_v1_2_traceability.py
```

Result: `PASS`.

- unique current rows: `282/282`;
- trace kinds: `173 PACK_CANONICAL / 95 DOCX_RECONCILED /
  14 ADDENDUM_DIRECT`;
- `FR-UX-040`: `TECHNICAL_VERIFIED`;
- `FR-UX-041`: `TECHNICAL_VERIFIED`;
- `FR-UX-043`: `PLANNED_SHARED_UX_REMEDIATION`;
- reconciliation unit tests: `12/12 PASS`;
- historical 281-row and Phase 3/4/P5/R1 Gate evidence: unchanged.

### Independent review

The first independent audit returned five blockers: malformed transport
results, impossible failure-state combinations, hidden async file identity,
an over-wide `editableIn` type and missing progress-theme evidence. The repair
added fail-closed runtime validation, a discriminated failure union plus
normalization, visible file facts, the authoritative source-system type and a
computed progress-color assertion.

The independent post-repair audit returned:
`PASS — all five blockers closed`, with TypeScript, ESLint, Prettier, unit
`37/37`, i18n, Playwright `12/12` and `git diff --check` independently
confirmed.

## Canonical artifacts

- `implementation/evidence/reconciliation/r1-05/stage-2/coverage/coverage-summary.json`
  - SHA-256:
    `6818d25ce02154a7551681bcbe0d2d23b465218a70515568ad67dec5fe4f77f6`
- `implementation/evidence/reconciliation/r1-05/stage-2/playwright-results/.last-run.json`
  - SHA-256:
    `fff6299efb51ba9ef550e500ecc967e972c83e86be387042c360caea7fdbae29`

HTML reports, traces and failure screenshots are working artifacts and are
ignored. Historical Phase 4 evidence was restored byte-for-byte before the
task diff.

## Final gate and transition

`PASS — LEVEL 2 R1-05 STAGE 2 FIELD/ATTACHMENT TRUTH TASK GATE`

`FR-UX-041` is `TECHNICAL_VERIFIED`. R1-05 remains `IN_PROGRESS`; only
`R1-05 Stage 3 — FR-UX-043 bounded icon-action foundation` becomes `READY`.
This result does not complete R1-05, activate R1-06/R1-07, resume P5-01,
widen file authority or authorize a production upload/scanner policy.
