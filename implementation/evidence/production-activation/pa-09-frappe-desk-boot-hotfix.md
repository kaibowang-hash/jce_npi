# PA-09 Frappe Desk boot hotfix

Status: `IN_PROGRESS — LOCAL REPAIR AND EXACT-SHA ORDINARY CI`

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

## Required proof

1. Focused source/translation filtering regression.
2. Current-task, repository and direct i18n verification.
3. Exact-SHA ordinary CI PASS before production mutation.
4. Fresh encrypted backup and incremental exact-SHA deployment with named
   volumes and the prior image pair retained.
5. Authenticated Desk and Setup Wizard render without console errors.
6. Final ordinary CI, Level 3 and release-gate PASS before closure.

## Rollback

Before deployment, revert only this task. After deployment, retain the fresh
backup and switch both images to the previous PA-08 pair without schema
downgrade, then run the production health gate. No migration is introduced by
this hotfix.
