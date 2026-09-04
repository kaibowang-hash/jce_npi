# PA-09 Frappe Desk boot hotfix

Status: `IMPLEMENTATION_COMPLETE — PRODUCTION DEPLOYED AND BROWSER-VERIFIED`

## Reproduced production facts

- Time: `2026-09-04T15:02:24Z` through `2026-09-04T15:07:37Z`.
- Scope: LaunchFlow production only; no ERPNext connection or production write.
- All ten containers and the system service were healthy.
- Authenticated `/app` and `/app/setup-wizard` returned HTTP 200.
- The browser showed only the Frappe splash shell. Its first inline script
  raised `SyntaxError: Invalid or unexpected token`; `frappe.boot` was absent,
  so later Desk/list/form/report/telemetry failures were consequential.
- Bounded chunked parsing of the existing inline script identified the first
  unterminated string at the NPI translation source
  `Parameter {{index}} category`. The double-curly placeholder was expanded to
  multiline markup inside the server-rendered JavaScript string.

No password, cookie, CSRF value, user identity, endpoint configuration or
business data was read into evidence.

## Minimal repair

Use Frappe's supported `extend_bootinfo` hook to remove only `__messages`
entries whose source or translation contains `{{` or `}}`. Those messages are
React SPA catalog entries served independently by the existing authenticated
NPI BFF, so this filter does not change LaunchFlow copy, translation coverage
or interpolation. It changes no Frappe core, schema, permission or ERP behavior.

## Exact deployment and live proof

- Repair/source SHA: `788ea1e1d9e13ebd3a91a382932fdce34347adad`.
- Exact-SHA pre-deploy ordinary CI: `33888820576` — PASS.
- Source archive:
  `sha256:64202c0a356e9d2c20024ee0cfdc756bc2ca614d4634bd007d22ed9687693fef`.
- Fresh encrypted full backup, independently verified at
  `2026-09-04T15:51:27Z`:
  `sha256:ab14d9321d33d2f24be4be0abcc1d90fadb5332a676dcf5058a70403d95b1c53`.
- Guarded exact image switch completed at `2026-09-04T16:00:20Z`; the active
  release pointer and both image revision labels equal the repair SHA.
- Post-switch server proof: ten running services, zero unhealthy services,
  repository production healthcheck PASS and public HTTPS ping PASS.
- Authenticated Chrome first rendered `/app/setup-wizard/0` with the Welcome
  heading, required language/country/timezone/currency controls and Next action.
  A clean reload then followed the completed setup state to `/app/users`, which
  rendered the Users administration workspace. Fresh console error count after
  that reload was zero. Codex did not fill, change or submit setup data.

## Recovery observation

The first switch attempt stopped safely because the existing rollback helper
enables Frappe maintenance before starting containers while the backend
healthcheck requires an HTTP 200 ping. That makes both the target and restored
backend appear unhealthy during maintenance even when their processes are
otherwise sound. The previous release was explicitly recovered at
`2026-09-04T15:58:48Z` by disabling maintenance and restoring the prior image,
environment and release pointer; all ten services passed without data loss.

Because this hotfix has no schema or migration, the final switch used a guarded
no-maintenance image replacement with an automatic failure trap. The prior
image pair, pre-target environment copy, release and encrypted backups remain
retained. The current generic rollback helper must not be represented as
automation-ready until a separate atomic task resolves its maintenance/health
contract. The proved manual maintenance-off/image/environment/pointer recovery
is the bounded fallback for this release.

## Required proof

1. Focused source/translation filtering regression.
2. Current-task, repository and direct i18n verification.
3. Exact-SHA ordinary CI PASS before production mutation.
4. Fresh encrypted backup and incremental exact-SHA deployment with named
   volumes and the prior image pair retained.
5. Authenticated Desk and Setup Wizard render without console errors.
6. Final exact-SHA ordinary CI, Level 3 and release-gate PASS on this sanitized
   completion checkpoint before release closure.

## Rollback

Before deployment, revert only this task. After deployment, retain the fresh
backup, disable maintenance, switch both images plus the environment and release
pointer to the previous PA-08 pair without schema downgrade, then run the
production health gate. Do not use the current generic rollback helper until
its maintenance/health conflict is repaired. No migration is introduced by
this hotfix.
