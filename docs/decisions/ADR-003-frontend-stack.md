# ADR-003: Frontend stack and dependency lock

Status: Accepted

## Decision

React 18, TypeScript and Vite form the SPA. Server state and routing are
isolated behind typed modules. `frontend/src/ui-adapters/npi-ui.tsx` is the only
production import boundary for Siemens iX packages, so business screens do not
bind directly to vendor APIs.

Phase 3 fixes these production versions exactly in both `package.json` and
`package-lock.json`:

| Package | Version | License | Purpose |
|---|---:|---|---|
| `react` / `react-dom` | 18.3.1 | MIT | Component runtime and DOM renderer |
| `@siemens/ix` | 3.2.0 | MIT | Classic industrial web components and theme runtime |
| `@siemens/ix-react` | 3.2.0 | MIT | React bindings used only by the local adapter |
| `@siemens/ix-icons` | 3.1.1 | MIT | Approved industrial icons used by the local adapter |

The installed package manifests identify the public React and Siemens iX
repositories and do not mark these versions deprecated. The lockfile records
registry URLs and integrity hashes. On 2026-07-22, both the complete dependency
audit and the production-only audit reported zero known vulnerabilities. This
is point-in-time evidence; upgrades still require a lockfile review and the
complete quality gate.

## Bundle and operational impact

The final repaired Phase 3 production build contains a 761.17 kB minified entry
module (190.88 kB gzip) and 225.79 kB of CSS (22.86 kB gzip). Each of the six
screen modules is lazy-loaded and is 4.65–10.96 kB before gzip. The larger
shared entry is the accepted cost of the iX runtime at this foundation stage
and is recorded as a performance budget baseline, not hidden by increasing
Vite's warning threshold. Later growth must be measured against this baseline.

## Alternatives and rollback

- Frappe Desk widgets were rejected because Desk is not the normal-user
  product and would violate the approved browser/BFF boundary.
- Another enterprise design system was rejected because Siemens iX Classic
  Light is the sole Pack visual baseline.
- Hand-built controls without iX were rejected as the default because they
  would duplicate accessibility and interaction behavior; small local
  primitives remain permitted behind the same adapter.

Rollback is adapter-scoped: replace the implementation behind `npi-ui`, remove
the Siemens packages and regenerate the lockfile without changing domain view
models or page contracts. No Siemens logo, proprietary font, Corporate Brand
Theme or restricted asset is included.
