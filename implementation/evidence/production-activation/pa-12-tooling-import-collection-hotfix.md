# PA-12 Tooling import collection contract hotfix

Status: `IMPLEMENTATION_COMPLETE — DEPLOYED AND AUTHENTICATED-BROWSER VERIFIED`

## Incident and root cause

- Reported route:
  `/projects/0f7af44c-3859-58e4-83e2-d484dcae6941/tooling?workspace=import`.
- The page showed `The service returned an invalid response` although the
  ERPNext-test connection banner was healthy.
- The collection endpoint returned HTTP 200 with the original seven-field
  permission map. The frozen frontend validator requires the complete
  fourteen-field Tooling import execution permission contract and correctly
  failed closed.
- The detail endpoint already used the complete execution permission
  projection. Only the collection repository override was missing.

## Minimal repair and verification

- Repair/source SHA:
  `2e9fedaf18ab9d0cc74e3b509180e47a0f245f02`.
- The execution repository now projects the same complete permission contract
  for collection and detail responses. Collection-level calculation accepts
  no source and therefore does not invent mapping authority.
- Runtime and repository regressions assert the exact fourteen keys. The
  frontend strict validator is unchanged.
- Focused backend/current-task checks: `22/22` PASS.
- Focused Tooling import frontend checks: `19/19` PASS.
- Full repository Level 2: `3,174/3,174` PASS.
- Full frontend Level 2: `1,174/1,174` PASS with `9,502` literal English
  sources at 100% direct `zh`/`zh-TW` coverage and zero npm vulnerabilities.
- Exact-SHA ordinary CI `34030796525`: PASS.
- Exact-SHA Level 3 `34030817154`: PASS, including controlled disposable
  Frappe v15 runtime job `101480581559`.
- Runtime artifact `9988751417`, digest
  `sha256:55765b9dc3a887286a03dc9e3a768bfea4dcaf0bf5965fb4e663029472fbd124`.
- Release-gate review found no permission widening, schema/core change,
  production mapping activation, secret, data mutation or open P0/P1/P2 issue.

## Deployment and live proof

- Exact source archive:
  `sha256:d731cdf771262f29d1fcecf6915dfaa0699a9c2f9d423e556d6b1ecc8b790150`.
- Fresh encrypted full LaunchFlow backup was created and independently
  verified before the switch:
  `sha256:47f2ef02c4061ae60f38d9a9c5cb4b003a808a43a8d6f31dc055f77fdad44f10`.
- Guarded no-schema backend switch completed at
  `2026-09-06T12:35:53Z`. The prior environment copy, release, images and all
  named volumes remain retained; an automatic maintenance-off restoration was
  armed during the switch and was not needed.
- Backend, Frappe frontend, both queues, scheduler and websocket carry the
  exact repair revision. All ten services run, zero are unhealthy, scheduler
  and public HTTPS health pass.
- The SPA remains at
  `3fd0f084d8d63549affbecd2b1b8ccc07107e4c3` because the frontend source diff
  between that active predecessor and the repair SHA is empty. No unchanged
  browser artifact was replaced merely to change its label.
- The authenticated Chrome route renders the full eight-step Tooling import
  workspace, `0` registered batches and the registration entry instead of the
  invalid-response page. The ERPNext-test banner remains connected and fresh
  browser console errors are `0`.
- Browser verification did not register a workbook, upload a file, execute an
  import or create/change any business record.

## Retained authority boundary and rollback

Production mapping remains explicitly unavailable. `DR-REC-007` still needs
the approved meaning and ownership of customer-standard, estimate,
trial-actual and calculated-result columns; `DR-REC-008` still owns the
downstream-use rollback cutoff. This honest hold is separate from ERPNext
connectivity and does not prevent the workspace from rendering or controlled
test preparation.

No ERPNext-test change and no production ERPNext or `JCE-Core` contact occurred
for PA-12. If rollback is required, keep maintenance off, restore the retained
pre-PA-12 environment file and previous release pointer, recreate only the six
backend-image services, and run the production health gate. No schema downgrade
or business-data deletion is involved.
