# R1-05 Stage 3 Validation — FR-UX-043 Bounded Icon Actions

Result:
`PASS — LEVEL 2 R1-05 STAGE 3 ICON-ACTION TASK GATE`

Date: 2026-07-30

Stage 3 starting checkpoint:
`0b485446ddde66ee0fe0a8ed7459bf191916a020`

Target requirements:

- `FR-UX-040`: remains `TECHNICAL_VERIFIED`
- `FR-UX-041`: remains `TECHNICAL_VERIFIED`
- `FR-UX-043`: `TECHNICAL_VERIFIED`

This checkpoint advances only `FR-UX-043` and completes R1-05. It does not
activate R1-07, resume P5-01, widen file authority, change a public contract or
approve any pending Decision Request. R1-06 is the only next bridge task.

## Delivered boundary

- Added a closed repository-owned action policy. Only familiar, low-risk,
  secondary and context-clear actions may become icon-only.
- Added a fail-closed local Siemens iX icon mapping. Unknown icon names are
  rejected; no GitHub, Primer, Octicons or direct vendor icon dependency is
  imported.
- Added `CompactAction` through the existing local NPI UI adapter. Icon-only
  actions retain a translated accessible name, translated title/tooltip,
  keyboard button semantics, visible focus, disabled behavior and a focusable
  non-hover discovery path.
- Kept primary, high-risk, irreversible and ambiguous actions visibly
  labelled. Icon shape and color do not carry the only meaning.
- Applied compact collapse/expand to the live My Work inspector and compact
  clear/retry to the Stage 2 attachment primitive. The primary file-selection
  action and ambiguous recovery/reload action remain visibly labelled.
- Preserved the Stage 1 pane preference contract and Stage 2 attachment state
  machine without API, schema, permission, translation-catalog or production
  dependency changes.
- Added square 32px, flat, bordered industrial geometry with bounded
  bottom-start/bottom-end tooltip placement so tooltips remain visible at
  narrow and docked edges.

## Changed-files to affected-tests

| Changed boundary | Required checks | Final evidence |
|---|---|---|
| `action-policy.ts`; `npi-ui.tsx`; test adapter | Closed allowlist, unknown-icon failure, eligible/ineligible action hierarchy, translated name/title/tooltip, disabled and keyboard behavior | Affected unit lane `58/58 PASS`; complete frontend unit lane `620/620 PASS` |
| My Work and attachment consumers | Compact collapse/expand, clear and retry; visible primary/ambiguous actions; Stage 1/2 state preservation | Focused browser behavior `14/14 PASS`; full non-visual CI browser matrix `265/265 PASS` |
| `app.css` | 32px square flat controls, visible focus, stable tooltip placement and no hover-only path | Style/industrial UI audits PASS; English/Simplified/Traditional visual review PASS |
| `verify-boundaries.mjs` | No Primer/Octicons/react-icons dependency or direct import; local adapter remains the only icon boundary | Boundary audit and complete repository verifier PASS |
| CI/devcontainer verifier | Required `rg`, exact scoped metadata token, redirect-safe token handling, digest-pinned visual container, bounded evidence and executing secret scans | Verifier unit lane `21/21 PASS`; pinned upstream metadata verification PASS; CI run `#64` |
| Trace generator/verifier/tests and this evidence | Exact verified FR-UX-043 evidence; 282 unique rows and unchanged 173/95/14 kinds | Reconciliation generator, unit lane and standalone verifier PASS |

## Action policy and accessibility review

An icon-only action must satisfy all of:

1. `secondary`;
2. `low-risk`;
3. `familiar`;
4. `context-clear`; and
5. an icon from the closed local allowlist.

Failing any condition renders a visible label. Primary, high-risk and
ambiguous actions cannot opt out through a caller flag. The rendered native
button retains its translated `aria-label`, `title`, focus ring, disabled
attribute and tooltip on both hover and keyboard focus. Status text, error
text, progress text and action availability remain visible independently of
the icon.

The affected trilingual screenshots were reviewed at original resolution.
They retain the classic light industrial shell, one primary action, square
geometry, flat borders, dense work area and textual state expression. The
first host-platform review exposed a clipped tooltip at an edge; the repaired
placement was rerun before the canonical Linux baseline was accepted.

## Security, contract, schema and dependency review

- Public API/OpenAPI change: **none**.
- Database schema, DocType, migration, patch or backfill: **none**.
- Authentication, authorization or permission-model change: **none**.
- Translation source/catalog change: **none**. Existing literal English and
  direct `zh`/`zh-TW` translations are reused.
- Design-token or theme change: **none**.
- Production dependency or lockfile change: **none**.
- File upload, registered-revision mutation, scanner/viewer, raw private URL
  or external integration change: **none**.

CI repairs use only the workflow's repository-scoped read-only
`${{ github.token }}`. The metadata verifier attaches it only to exact HTTPS
`api.github.com` requests and rejects redirects outside that exact origin.
The same scoped token permits the PR secret scanner to enumerate the PR
commit range; no secret is stored in an artifact or repository file.

The complete branch scan surfaced three historical `generic-api-key` false
positives. They were reviewed at the introducing commits before exclusion:

- `p403-legacy-gate-ref` is a synthetic Phase 4 unit-test idempotency key in a
  fixture that also uses `SYNTHETIC-*` identifiers and an `.invalid` email;
- both other findings are the same internal boolean configuration name,
  `npi_p4_05_routes_disabled`, read by the disposable Frappe runtime verifier.

None can authenticate to a service. `.gitleaksignore` contains only their
exact commit/file/rule/line fingerprints. The repository verifier requires
that exact three-entry set and rejects path-only entries, wildcard line
numbers, additional fingerprints, comments and blank lines.

## Verification

### Static, unit, coverage, build and audit

Canonical Node: `24.18.0`; npm: `11.16.0`.

- generated-source freshness, TypeScript, ESLint, Prettier, Stylelint,
  boundary and industrial UI audits: PASS;
- affected unit lane after repair: `58/58 PASS`;
- complete frontend unit lane: `620/620 PASS` across `29/29` files;
- coverage: statements `85.41%` (`4597/5382`), branches `83.54%`
  (`5747/6879`), functions `89.23%` (`1310/1468`), lines `87.50%`
  (`4375/5000`);
- production build and display-brand guard: PASS;
- `npm audit` and `npm audit --omit=dev`: `0` vulnerabilities;
- complete repository Python lane: `754/754 PASS`;
- reconciliation and prohibited-pattern verifiers: PASS.

### Localization

`npm run lint:i18n` passed with `2,735` literal English sources and `100%`
direct `zh` and `zh-TW` coverage. No source string or catalog row was added by
Stage 3. Mixed-language, placeholder and controlled-terminology scans passed.

### Browser and canonical Linux visual evidence

Affected behavior:

```text
npx playwright test tests/e2e/r1-05-panes.spec.ts \
  tests/e2e/r1-05-field-attachments.spec.ts --grep-invert @visual
```

Result: `14/14 PASS`.

Canonical Linux visual command:

```text
npx playwright test tests/e2e/r1-05-panes.spec.ts \
  tests/e2e/r1-05-field-attachments.spec.ts --grep @visual
```

Result: `6/6 PASS` in the exact digest-pinned Debian devcontainer base on
GitHub Actions run `#64`, job `90858023160`. The four intentionally changed
baselines are:

```text
507e6363df1539e0b6be97c4467c1e09eba9e5b83fb96b70d8957ece0e6b19d3  r1-05-field-attachment-local-en-1366x768-100-linux.png
8d85a62ca78559e5546fc6e151b7afdd5c9c4139f5dc7854ebc71272c7994cd4  r1-05-inspector-en-1366x768-100-linux.png
ccb0ebc37d07f3dd58afc38b82094fa9deffee87df634333829b94febd26a637  r1-05-inspector-zh-1440x900-125-linux.png
e0d141b15f20557971be77cc67db224373eb2cdc75fe2617430a6da1a31daf36  r1-05-inspector-zh-TW-1920x1080-150-linux.png
```

The pending and clean attachment baselines remained exact. A diagnostic
all-visual invocation on the fresh container matched `108/213` historical
images and exposed environment-wide package/font drift in `101` unrelated
images. Those unrelated baselines were not rewritten. The accepted Stage 1
complete `210/210` matrix and Stage 2 affected evidence remain reusable;
R1-06 owns the additive 1440×900 governance and final cumulative bridge
matrix.

### CI and secret scan

GitHub Actions run `#64`, repository job `90858023163`, executes:

- the complete repository verifier;
- the complete `265`-case non-visual browser matrix;
- the exact affected `6`-case Linux visual matrix;
- the digest/metadata/toolchain verifier; and
- `gitleaks` with the repository-scoped read-only PR token.

The action-owned scan covered `22` additions-bearing commits and `6.32 MB`;
the explicit complete branch scan covered `50` commits and `11.67 MB`.
Both reported `no leaks found` after applying only the three exact reviewed
historical fingerprints.

The earlier CI diagnostics did not weaken a test or acceptance threshold:
missing `rg`, anonymous metadata rate limiting, an obsolete Yarn APT source,
host-renderer drift and a new `gitleaks-action` token requirement were
repaired explicitly. The later complete-branch findings were reviewed at their
introducing commits and limited by a strict fingerprint-set validator. Failed
invocations are not represented as security, visual or repository PASS
evidence.

### Trace and artifacts

```text
python scripts/reconcile_v1_2_traceability.py --apply
python -m unittest tests.test_v1_2_reconciliation -v
python scripts/verify_v1_2_reconciliation.py
python scripts/reconcile_v1_2_traceability.py
```

Result: PASS.

- current unique rows: `282/282`;
- kinds: `173 PACK_CANONICAL / 95 DOCX_RECONCILED /
  14 ADDENDUM_DIRECT`;
- `FR-UX-040`, `FR-UX-041`, `FR-UX-043`: `TECHNICAL_VERIFIED`;
- historical 281-row and accepted Phase/R1 evidence: unchanged.

Canonical task artifacts:

- `implementation/evidence/reconciliation/r1-05/stage-3/coverage/coverage-summary.json`
  - SHA-256:
    `d8fc69c8795f0e576a6187f01b5806ef9c463ea2d2e0de77d174332b788e1b39`
- `implementation/evidence/reconciliation/r1-05/stage-3/playwright-results/.last-run.json`
  - SHA-256:
    `91d1c43004802cd49950d78eb11c8fa7d05da8ffffe219a8b13b2f561bc00903`
- GitHub Actions run `#64` Linux visual artifact `8757774496`
  - ZIP SHA-256:
    `ecdf3780fef0f56fbb9432668819bb8fcb3d57337a8de9d537338a311463a3b5`
- GitHub Actions run `#64` Gitleaks SARIF artifact `8757922008`
  - ZIP SHA-256:
    `ba3c4705c72cb77f6da7ab4c7ccbe98e79369b8b6440469f96736e710936d50d`

## Rollback and transition

The local action mapping and consumers are reversible presentation changes.
No persistent user/business data, schema or external message is created.
Reverting the Stage 3 product commits restores visible labels and the prior
screenshots; no migration or data deletion is required. CI hardening is
independent of product behavior and should not be rolled back to a state where
required verification silently fails to execute.

`PASS — LEVEL 2 R1-05 STAGE 3 ICON-ACTION TASK GATE`

R1-05 is complete. Only
`R1-06 — Controlled undo prototype gate and 1440 visual governance` becomes
active. R1-07 remains disabled under DR-REC-001, and P5-01 remains held until
R1-06 plus the cumulative R1 Level 3 bridge Gate pass.
