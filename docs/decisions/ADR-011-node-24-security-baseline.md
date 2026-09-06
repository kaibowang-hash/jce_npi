# ADR-011: Node 24 LTS security baseline

- Status: Accepted
- Date: 2026-07-25
- Decision owner: NPI One V1.2 continuous-delivery controller
- Related task: Phase 4 `P4-04` release-gate repair

## Context and facts

The P4-04 Level 3 gate initially failed `npm audit` after
[GHSA-mh99-v99m-4gvg](https://github.com/advisories/GHSA-mh99-v99m-4gvg)
was published on 2026-07-23 and updated on 2026-07-24. The advisory rates
`brace-expansion <=5.0.7` High severity and identifies `5.0.8` as the only
patched release. The patched package requires Node `20 || >=22`, while the
repository still pinned end-of-life Node 18.20.8.

The official [Node.js release schedule](https://github.com/nodejs/Release#release-schedule)
lists Node 18 and Node 20 as end-of-life and Node 24 `Krypton` as Active LTS.
The official Node distribution index records Node 24.18.0 with bundled npm
11.16.0. The pinned Frappe v15 package requires Node `>=18`, so Node 24 remains
within its declared engine range.

The vulnerable lock graph included production and development paths:

- Siemens iX React through `ts-morph` and `minimatch` 10;
- ESLint 9 through `minimatch` 3;
- typescript-eslint through `minimatch` 9; and
- Vitest coverage through `test-exclude`, `glob` and multiple minimatch majors.

A global override from old `brace-expansion` majors to version 5 is unsafe
because their module APIs are not compatible.

## Decision

1. Pin the authoritative development and CI runtime to Node 24.18.0 and its
   bundled npm 11.16.0. Retain the existing digest-locked Node Feature 2.1.0,
   Docker Feature, Python image, Frappe commit and all non-Node tool pins.
2. Upgrade only the direct development tools required to remove the vulnerable
   legacy graph: ESLint 10.7.0, `@eslint/js` 10.0.1,
   typescript-eslint 8.65.0, React Hooks lint 7.1.1, React Refresh lint 0.5.3,
   Vitest and V8 coverage 4.1.10, and Node types 24.13.3.
3. Keep Vite, TypeScript, jsdom, Playwright test, React and Siemens iX product
   dependencies unchanged. Pin `playwright-core` 1.61.1 explicitly so npm 11
   satisfies Axe and Playwright with one type-compatible instance.
4. Require the regenerated npm 11 lock to contain only
   `brace-expansion@5.0.8`. Both complete and production-only audits must pass.
5. Use npm 11's install-script policy to allow only the exact application
   `esbuild@0.25.12` postinstall. The application policy denies `fsevents` by
   package name, including the lock's optional 2.3.2 and 2.3.3 install hooks;
   npm 11 reviews those lock entries before omitting them on Linux. For the
   global Vite 5.4.14 smoke tool, strict mode permits exact esbuild 0.21.5 and
   its exact optional macOS-only fsevents 2.3.3 hook; esbuild is pinned directly
   and fsevents remains absent on Linux.
   The application `.npmrc`, Make target and CI command all enforce
   `strict-allow-scripts`; a read-only pending-script verifier must report no
   unreviewed package. No unreviewed install script may remain.
6. Preserve coverage scope under Vitest 4 with an explicit
   `src/**/*.{ts,tsx}` include. Existing coverage thresholds are unchanged.

This is a development/CI security baseline change. It does not change the
approved product architecture, UI system, localization strategy, data
ownership, business policy, production ERPNext boundary or runtime
dependencies shipped by the SPA.

## Alternatives considered

- **Keep Node 18 and suppress the advisory:** rejected because Node 18 is
  end-of-life and cannot install the patched package within its engine
  contract.
- **Move to Node 20:** rejected because Node 20 is also end-of-life.
- **Force a global `brace-expansion` override:** rejected because it would
  replace legacy function exports with the version 5 named-export API and
  could break consumers.
- **Use Node 26 Current:** rejected because an Active LTS line is the more
  stable supported baseline.
- **Disable or weaken `npm audit`:** rejected because the release gate must
  report real security failures.

## Impact

- Development containers and CI must be rebuilt with the new exact Node/npm
  pair.
- The lockfile changes substantially because the vulnerable ESLint and Vitest
  dependency families are replaced, but product dependencies stay fixed.
- ESLint 10 findings are repaired in source/tests; no rule is disabled.
- Vitest 4 measures all source files explicitly, which strengthens coverage
  completeness without lowering thresholds.
- All changed packages retain their existing permissive or already accepted
  licenses; no production package is added.

## Risks and mitigations

- **Fresh-target drift:** registry verification checks the exact bundled npm,
  Feature options and immutable Feature digest; a fresh target must pass
  `make verify-dev-environment`.
- **Tool migration regressions:** run full type, lint, unit/coverage, build,
  E2E, visual and trilingual gates under Node 24.
- **Supply-chain scripts:** keep one exact allowlist entry and require
  `npm approve-scripts --allow-scripts-pending` to report none.
- **Lock drift:** require clean `npm ci`, inspect the resolved minimatch/brace
  graph and run both npm audits.

## Rollback and replacement

Reverting the toolchain and lockfile is mechanically possible, but Node 18
must not be restored while the advisory remains unresolved. If Node 24 proves
incompatible in a fresh target, choose another supported even-numbered LTS
line and repeat the same registry, lock, audit and full-gate evidence. No
database or production rollback is involved.

## Verification

- official Node/npm and Dev Container registry verification;
- clean npm 11 `ci`;
- exact dependency-tree and install-script review;
- complete and production-only npm audits;
- whole-repository Level 3 validation; and
- actual fresh-target development-environment verification.
