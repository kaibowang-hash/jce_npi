# P4-01 Validation and Release Evidence

Execution date: 2026-07-23

Atomic task: `P4-01 — Project template and live cockpit vertical slice`

Technical outcome: **PASS**

Controller outcome: **P4-01 PASS; P4-02 ACTIVE; Phase 4 remains IN_PROGRESS**

This record proves the bounded P4-01 vertical slice. It does not claim that the
whole Project-management requirement family or Phase 4 is complete. In
particular, production template contents, project deliverables and roles,
charter fields, a formal G1 baseline, production reference-completeness rules,
RACI, Gate decisions, and lifecycle transitions remain in their allocated
later tasks or scoped Class-B holds.

## Delivered vertical slice

- Nine additive Frappe DocTypes persist generic Project templates and immutable
  published versions, Gate/reference definitions, Engineering Projects,
  instantiated Gate shells, governed Project references, idempotency records,
  and business-code reservations.
- Framework-independent domain validation and the Frappe repository share the
  same template, reference, stable UUID, business-code, exact-snapshot,
  optimistic-version, and publication rules.
- `POST /api/npi/v1/projects` atomically creates one draft Project and its G0/G1
  shells from an explicit published template version. The command is
  idempotent for an identical actor/key/payload and rejects a changed payload.
- `GET /api/npi/v1/projects/{projectId}/cockpit` returns the strict live Project
  Cockpit ViewModel without exposing raw DocType CRUD.
- A per-Site `npi_tenant_id` is mandatory. Missing or invalid configuration
  fails closed as a retryable 503; tenant mismatch is 403; unrelated or hidden
  objects return 404. Owners receive a bounded read-only projection; internal
  System Managers alone use the explicit create/contribute/administrative
  path in this slice.
- The accepted Project route now uses the live BFF. The prior fixture remains
  only on the explicit demo path. Loading, empty, read-only, not-found,
  no-permission, validation, conflict, retryable/final error, invalid response,
  and success surfaces are implemented in English, Simplified Chinese, and
  Traditional Chinese.

No production Project template, ERPNext endpoint, production credential, or
production rule package was installed or contacted.

## Final command and review results

| Command / gate | Result | Evidence summary |
|---|---|---|
| `make verify` | PASS | 120/120 Python tests; generated-artifact, TypeScript, ESLint, Prettier, Stylelint, boundary, industrial-UI, and i18n checks; 153/153 frontend unit/component tests; coverage; production build; and both npm audits |
| `npm --prefix frontend run test:e2e` | PASS | 103/103 non-visual Chromium tests in 3.7 minutes |
| `npm --prefix frontend run test:visual:update` | PASS | 141/141 screenshots force-regenerated with `--update-snapshots=all` in 4.8 minutes |
| `npm --prefix frontend run test:visual -- --workers=2 --shard=1/2` | PASS | 71/71 screenshots matched at `maxDiffPixelRatio: 0` in 2.3 minutes |
| `npm --prefix frontend run test:visual -- --workers=2 --shard=2/2` | PASS | Remaining 70/70 screenshots matched at `maxDiffPixelRatio: 0` in 1.9 minutes |
| Three-image manual live-Project review | PASS | Representative `en`, `zh`, and `zh-TW` normal states were inspected at original resolution |
| `make frappe-site-init` | PASS | App installation/migration and an idempotent rerun passed against Frappe 15.115.4 at `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` |
| `make frappe-runtime-verify` | PASS | Existing session/i18n runtime proof plus live Project create/query, authorization, mutation guards, sequential idempotent replay/conflicts, audit, and cleanup passed |
| `git diff --check` and prohibited-pattern review | PASS | No whitespace error, core patch, direct SQL, `ignore_permissions`, raw browser `/api/resource`, production ERP endpoint, accepted-path TODO/FIXME, or non-catalog Chinese source was introduced |

The zero-tolerance comparison was split only to keep each browser process
within the execution container's resource envelope. The two native Playwright
shards are disjoint and together cover all 141 cases. The resulting
`implementation/evidence/phase-4/playwright-results/.last-run.json` records
`passed` with no failed tests, and the HTML report is retained beside it.

## Coverage, build, and dependency security

The portable aggregate in
`implementation/evidence/phase-4/coverage/coverage-summary.json` contains no
workspace-specific absolute paths:

| Metric | Covered / total | Result |
|---|---:|---:|
| Statements | 5,101 / 5,448 | 93.63% |
| Branches | 999 / 1,095 | 91.23% |
| Functions | 173 / 190 | 91.05% |
| Lines | 5,101 / 5,448 | 93.63% |

The final Vite build transformed 392 modules. The main JavaScript asset is
789.33 kB minified / 199.73 kB gzip; CSS is 225.79 kB minified / 22.86 kB
gzip. Route-level business pages are split, but the shared entry still exceeds
Vite's 500 kB warning. The warning remains visible as risk R-010 and was not
suppressed. `npm audit` and `npm audit --omit=dev` both found zero
vulnerabilities.

## Frappe runtime and transaction proof

The disposable local Site used loopback only. The Project verifier returned:

```json
{"auditEvents":1,"businessCodeConflict":409,"disabledOwnerReplay":true,"disabledTemplate":422,"gateShells":2,"genericCrudDenied":true,"historyDeleteDenied":7,"idempotentReplay":true,"idor":404,"ownerReadOnly":true,"projectId":"289e399d-e093-5d0f-b318-bb13b41cbfb1","standaloneChildMutationsDenied":9,"templateGlobalId":"54be6b80-1534-54b9-97e6-9314cb8d69af","templateInstalledByMigration":false,"tenantMismatch":403,"versionConflict":409}
```

The retained session/localization verifier also proved 738 catalog messages per
locale, Administrator language isolation, guest/CSRF/malformed/unknown-route
problem contracts, and exact disposable-user cleanup.

Runtime and unit evidence together proves:

- published template versions and Project/Gate/idempotency/reservation/audit
  history cannot be overwritten or deleted through ordinary controller paths;
- all nine direct standalone child create/save/delete attack paths are denied,
  and the parent template/Project snapshot remains unchanged;
- `business_code` uniqueness is tenant-scoped and reserved before Project
  persistence;
- an idempotency unique-key race rolls back the losing transaction before
  reading the winner, avoiding a stale REPEATABLE READ snapshot;
- identical replays return the original Project, changed-payload reuse returns
  conflict, and disabling the designated owner after a committed
  administrator command does not invalidate that command's valid replay;
- a failure during Project/G0/G1 instantiation leaves no partial Project, Gate,
  reservation, idempotency, or audit result;
- caller-supplied request fields are closed and typed, commands require Frappe
  CSRF, and successful and Problem Details responses carry correlated request
  and trace identifiers; and
- canonical lowercase UUIDs, including the nil UUID allowed by the contract,
  round-trip consistently through backend and frontend validators.

## Localization, accessibility, and visual evidence

The canonical Frappe CSV catalogs contain 738 literal English sources with
complete direct `zh` and `zh-TW` translations. The generated browser catalog
version is `b72ab77e6d608019`. Static checks cover literal-source use,
placeholders, controlled terminology, retain terms, mixed-language output, and
catalog parity. React user copy continues to enter through the shared `t()`
adapter.

The 103-case browser suite covers the live Project normal path plus every
required non-normal state in all three locales, response fail-closed behavior,
traceable conflict/retry actions, keyboard focus, accessible panel scroll
regions, axe WCAG A/AA checks, computed industrial tokens, 125%/150%
zoom-equivalent layouts, field tablet, and field phone.

The visual baseline contains the retained 129 Phase 3 matrix cases plus 12 new
live Project cases (four per locale). All 129 shared-shell images were
intentionally regenerated because the complete catalog changed the visible
catalog hash and shared shell copy changed; they were not accepted as
incidental binary churn. All 141 then passed a clean zero-difference
comparison. The historical files under `implementation/evidence/phase-3`
remain byte-clean.

Manual review of these live images passed:

- `live-project-normal-en-1366x768-100-linux.png`
- `live-project-normal-zh-1920x1080-125-linux.png`
- `live-project-normal-zh-TW-1366x768-150-linux.png`

They retain the fixed industrial shell, compact object identity, table and
inspector density, square one-pixel boundaries, neutral surfaces, single teal
accent, textual status, one-primary-action discipline, and language-pure UI
copy without Frappe Desk chrome.

## Migration, rollback, and remaining boundary

Schema changes are additive and migration installs no synthetic or production
template. Before retained Project history exists, the slice can be hidden and
the disposable development Site restored to the pre-P4-01 checkpoint. Once
history exists, rollback is a forward fix with commands/routes disabled; the
immutable Project, Gate, audit, and idempotency records must not be deleted.
ERPNext is unaffected because this slice performs no ERP write.

The following requirements remain explicitly partial:

- FR-PM-001 still needs production deliverables, roles, and standard duration
  in approved template versions.
- FR-PM-003 still needs the complete production
  customer/product/part/tooling/order submission policy.
- FR-PM-004 still needs the full charter field set and immutable G1 baseline.
- FR-CO-006 is proven for the P4-01 UI/API slice only; later Phase 4 surfaces
  and P4-05 delivery/renderer scope remain outstanding.

P4-01 therefore passes as a complete technical foundation and live vertical
slice, not as completion of those broader requirements. P4-02 owns Team, RACI,
WBS/dependencies/baseline comparison, and the distinct
risk/issue/action/decision-request records.
