# Phase 3 Frontend Dependency Review

Review date: 2026-07-22

Decision: `docs/decisions/ADR-003-frontend-stack.md`

Lock: `frontend/package-lock.json`

## Reproducible install and audit

- `npm ci`: **PASS**; 432 packages were installed and 433 packages were
  audited from the committed lockfile.
- Runtime dependencies remain fixed to React 18.3.1, React DOM 18.3.1,
  Siemens iX 3.2.0, Siemens iX React 3.2.0, and Siemens iX Icons 3.1.1.
- The installed package manifests identify MIT licenses and public upstream
  repositories for those runtime packages.
- `npm audit`: **PASS**, zero known vulnerabilities.
- `npm audit --omit=dev`: **PASS**, zero known production-dependency
  vulnerabilities.

These audit results are point-in-time registry evidence, not a claim of future
support or complete supply-chain assurance.

## Build and boundary result

`npm run build` transformed 390 modules and emitted the production assets. The
current shared bundle measurements are:

| Asset | Minified | Gzip |
|---|---:|---:|
| Main JavaScript | 761.17 kB | 190.88 kB |
| CSS | 225.79 kB | 22.86 kB |

The main JavaScript warning above 500 kB remains visible. It is recorded as the
Phase 3 foundation baseline and must be addressed or explicitly re-evaluated
when later phases add production data access and business modules; the warning
threshold was not raised to hide it.

`npm run lint:boundaries` passed and proves Siemens imports remain inside the
local UI adapter. `npm run lint:ui` passed and checks the Classic Light root
attributes, company-token boundary, restricted-brand-asset ban, and baseline
style constraints.

## Maintenance, upgrade, and rollback

The pinned packages pass the repository's current type, lint, unit, build,
dependency, post-fix browser, accessibility, and exact visual gates in the
fixed Node/npm environment. Any version change must update the ADR and
lockfile, review license/deprecation/security metadata, compare bundle output,
and rerun all applicable Phase 3 gates.

The rollback boundary is `frontend/src/ui-adapters/`: the adapter can be
reimplemented and the vendor packages removed without changing page-level
domain view models. Frappe Desk or another design system is not an acceptable
normal-user fallback under the approved architecture.
