# LaunchFlow to ERPNext Test Live Connectivity

Date: 2026-09-05

LaunchFlow Site: `launchflow.whjichen.cn`

ERPNext test Site: `jce.1` through `https://test.core.whjichen.cn`

Active LaunchFlow release: `bdf74153fbb96d420a4e5bb009d496f3a4177c08`

ERPNext connector app: `npi_erpnext_connector` `0.5.0`

Production ERPNext alias `JCE-Core` was not contacted or modified.

## Release and recovery evidence

- The LaunchFlow Item Sandbox adapter and actor propagation were introduced by
  `0430d0a64afa17cd103f95dfb2bb44c24b1c15e5`.
- Backend verification passed 1155/1155 frontend tests, translation coverage,
  build budgets, brand checks and dependency audits. Targeted Item and
  deployment suites also passed.
- A full encrypted LaunchFlow backup was created and checksum-verified before
  deployment:
  `launchflow-launchflow.whjichen.cn-20260905T124017Z.tar.gpg`.
- The first switch failed closed because the root-only Docker secret was not
  readable by the unprivileged worker. The switch automatically restored
  release `788ea1e1d9e13ebd3a91a382932fdce34347adad`.
- Commit `bdf74153fbb96d420a4e5bb009d496f3a4177c08` added a bounded startup wrapper:
  it reads the root-only secret and immediately drops to UID/GID 1000 before
  starting the worker. Its deployment test passed 9/9.
- The second switch passed the production health gate: 10/10 required services
  running and zero unhealthy. Backend and SPA OCI revision labels both match
  the active release SHA.

## ERPNext-owned user and permission projection

- LaunchFlow transport user:
  `erpnext-authorization-integration@launchflow.invalid`; enabled System User,
  roles `NPI API User` and `NPI Integration Transport`, without System Manager.
- ERPNext business test user:
  `npi-integration-test-user@erpnext-test.invalid`; enabled System User with
  ERPNext role `NPI Integration Test User`.
- Exact role mapping:
  `NPI Integration Test User` -> `NPI API User`.
- ERPNext authorization sender is enabled and targets
  `https://launchflow.whjichen.cn`. Its worker-only token is stored outside Site
  config at `/etc/npi-erpnext-connector/authorization_token`, mode `0640`, owned
  by `root:ubuntu`.
- LaunchFlow authorization ingress is enabled with allowlist
  `NPI API User` and a 3600-second maximum TTL. The API secret is absent from
  LaunchFlow and ERPNext Site configuration.
- Delivery `e50eec4d-c838-5976-987c-bf5cbd674c28` completed as `delivered`,
  source version 1, local state `enabled`, disposition `created`.
- LaunchFlow created the same canonical System User identity and stored one
  enabled authorization projection with role `NPI API User`.
- Re-enqueue returned the same delivery ID. Direct exact replay returned
  `exactReplay=true`, `localUserDisposition=exact_replay` and did not create a
  second user or projection version.

Authorization projection enforcement remains false. This permits controlled
ingress proof without locking out existing LaunchFlow users before the complete
ERPNext role/user mapping and the separately managed Entra login are ready.

## Live Item command

The deployed LaunchFlow queue-short image executed its configured Item Sandbox
adapter over HTTPS to `erpnext-test`. The command used:

- business actor: `npi-integration-test-user@erpnext-test.invalid`;
- request: `8779ca66-e631-4cf0-af17-0c2acaf6da02`;
- attempt: `a34cbdb4-f729-4eac-bd26-8e6ae0c4a8c3`;
- engineering identity: `LF-ERP-CONNECT-20260905-01`;
- intent: `create_item` with expected mapping version 0.

The authenticated response passed the v2 response contract and returned the
ERPNext-assigned formal Item Code `61000334`. ERPNext state is:

- `Item.name` and `Item.item_code`: `61000334`;
- standard `owner` / Created By:
  `npi-integration-test-user@erpnext-test.invalid`;
- `modified_by`: `npi-item-integration@erpnext-test.invalid`;
- Item Group: `Plastic Part`;
- stock UOM: `Pcs` (mapped from engineering UOM `Nos`);
- receipt `service_user`: `npi-item-integration@erpnext-test.invalid`;
- mapping version: 1.

Replaying the identical command returned `61000334` again. Post-replay counts
remained exactly one Item, one operation receipt and one Item mapping.

The ERPNext capabilities endpoint reports app version `0.5.0`, Item installed
and enabled, and supported Frappe majors 15 and 16. Live target execution here
used ERPNext/Frappe 16; the separate rollback verifier evidence covers the same
business-creator contract on Frappe/ERPNext 15 and 16.

## Deliberately open boundaries

- LaunchFlow currently has zero Projects, Project Templates, EBOMs and EBOM
  policies. To avoid inventing business documents, the connectivity proof ran
  the deployed adapter directly rather than fabricating an end-user BFF flow.
  The exact Sandbox profile must be rebound to a real Project global ID when a
  governed Project and released EBOM exist.
- Entra authentication is not configured by this change; it remains the
  user's separately managed login configuration.
- MBOM and Tool Asset execution remain disabled.
- Item Group and customer-like master-data synchronization are follow-up scope;
  this proof only consumed the currently configured ERPNext Item Group.
