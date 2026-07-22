# Next Action

Status: `IN_PROGRESS`

Current phase: `4 — Project Work Items and Stage Gates`.

Implement atomic task `P4-01 — Project template and live cockpit vertical
slice` from `implementation/phase-4-requirement-anchor.md`:

- add generic, versioned Project Template persistence and immutable published
  versions without installing a production template;
- atomically create an Engineering Project draft and G0/G1 Gate shells from an
  explicit published template version;
- require an explicit unique business code and typed object references while
  keeping ERP/customer/order authority honest;
- enforce stable UUID identity, expected version, retry-safe idempotency,
  tenant/project authorization, external-user restrictions, Frappe CSRF, strict
  request schemas, transaction rollback, audit, and trace identity;
- add strict Project create/query/cockpit contracts under `/api/npi/v1`; and
- replace the accepted Project cockpit fixture path with the live BFF while
  covering all required states in English, Simplified Chinese, and Traditional
  Chinese.

Use only explicit synthetic templates in tests and fixtures. Do not propose or
activate a Project, assign production RACI, decide a Gate, fabricate clean file
scans or health/cost, claim ERP-created provenance, contact production ERPNext,
or implement any Class-B rule held by the Phase 4 anchor.
