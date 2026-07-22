# Last Run

- Timestamp: `2026-07-22T15:31:38Z`
- Branch: `codex/npi-v1.2-implementation`
- Starting HEAD: `f9319fa0e2c4758c40ac4c2722c97ac9d68cefd8`
- Starting upstream state: ahead 0 / behind 0
- Gate candidate: `3 — React App Shell, Siemens UI and i18n Foundation`
- Repair round: `1/5`
- Release-gate technical decision: `PASS`
- Phase acceptance: `TECHNICAL_PASS_PENDING_UAT`
- Next phase: `4 — Project Work Items and Stage Gates (active)`

## Phase 3 outcome

Repair round 1 is complete. It closes the formal localization and Worklist
error/trace/retry contracts, Frappe CSRF path, unexpected-error ProblemDetails
boundary, finite telemetry route allowlist, exact BFF route boundary,
transaction rollback, and request-locale atomicity findings. The full aggregate,
runtime, browser, and visual evidence was rerun after the fixes. Independent
final release review returned `PASS` with no release-blocking findings.

- Delivered the independent React/TypeScript industrial App Shell, local
  Siemens iX Classic Light adapter, company-owned tokens, reusable dense
  engineering page/state primitives, six explicitly labelled prototype paths,
  and the Frappe-compatible `en`/`zh`/`zh-TW` localization chain.
- The local Frappe 15.115.4 Site install/migrate path and authenticated BFF were
  exercised without ERPNext or production access. A disposable normal Website
  User received 556 direct catalog entries per locale, persisted both Chinese
  language choices across fresh sessions, left Administrator language unchanged,
  and was deleted exactly after verification.
- The visual baseline was force-regenerated after the final UI changes, then
  compared without update mode at `maxDiffPixelRatio: 0`; both runs passed
  129/129. Six representative images were reviewed at original resolution and
  contain the zero-notification state and catalog version prefix
  `12e5adf665b2cd30`.
- Business UAT by Project Management, Engineering/Tooling and Quality plus
  provenance-backed sanitized representative data remains unsigned/open. It is
  not represented as completed by technical fixtures and is not a global
  blocker.

## Commands and results

| Command | Result |
|---|---|
| `npm ci` | `PASS` — 432 packages installed; 433 audited from the lockfile |
| `npm run verify` | `PASS` — 110/110 unit/component tests plus coverage/build/static/i18n/dependency gates |
| `npm run test:e2e -- --reporter=line` | `PASS` — final clean standalone 63/63 non-visual Chromium run in 2.6 minutes |
| `npm run test:visual:update` | `PASS` — exact configuration, 129/129 force-regenerated in 4.3 minutes |
| `npm run test:visual` | `PASS` — 129/129 clean comparison at zero pixel tolerance in 3.9 minutes |
| `make frappe-site-init` | `PASS` — disposable Frappe Site install/migrate path |
| `make frappe-runtime-verify` | `PASS` — normal-user locale/session/permission/error/CSRF/cleanup proof |
| `make verify` | `PASS` — 58/58 repository/Python tests plus the complete frontend gate |
| final standalone production build | `PASS` — 390 modules; JS 761.17/190.88 kB gzip; CSS 225.79/22.86 kB gzip |
| `git diff --check` | `PASS` — exit 0, no output |

Frontend aggregate coverage is 4,319/4,646 statements and lines (92.96%),
784/863 branches (90.84%), and 144/160 functions (90.00%). Both npm audits
reported zero known vulnerabilities. Exact scope, evidence, rollback and
acceptance boundaries are in `implementation/phase-3-gate.md` and
`implementation/evidence/phase-3/`. Phase 3 is recorded as
`TECHNICAL_PASS_PENDING_UAT`; Phase 4 atomic task `P4-00` is active under the
automatic-transition authorization.
