# ERPNext-test authorization synchronization hotfix 0.5.1

Date: 2026-09-05

Status: **IMPLEMENTATION COMPLETE — LEVEL 3, DEPLOYMENT AND LIVE DELIVERY PASS**

The canonical ERPNext-test user update was saved, but the authorization source
job rejected the valid Unicode role `品管` before applying the explicit role
mapping. After the sender repair, delivery reached LaunchFlow and returned 403
because the same canonical internal User already held System Manager. Separate
unmapped-user deliveries returned 500 because a disabled absent target was
modeled as a required Link to User.

The bounded repair accepts valid Unicode ERPNext source-role names while still
emitting only explicit mapping values, permits the ERPNext authorization owner
to adopt an existing canonical internal User, protects the built-in and
transport service identities, and stores absent target identity as Data so a
disabled projection remains durable and auditable.

Production ERPNext is not contacted. Authorization enforcement remains off.
Project, Customer, Supplier and Item Group synchronization are not part of this
hotfix and no mapping is guessed.

The first exact-SHA Level 3 run identified only two unregistered synthetic
credential fingerprints from the predecessor Item adapter test. Both are fixed
test values bound to `.invalid` configuration; their exact historical
fingerprints were added to the existing reviewed allowlist before the unchanged
gate was repeated.

## Verification and release evidence

- Exact product SHA: `118fb6b90aa47aca8a2e790f9c834cd5b74ee843`.
- Exact-SHA Level 3 run `33975755695`, attempt 2: PASS. Repository, secret
  scan, frontend, both E2E shards, governed visual matrix, controlled preflight
  and controlled disposable-Site runtime all passed. Controlled runtime job
  `101334148062` passed and cleaned its ephemeral resources.
- Focused LaunchFlow authorization receiver tests: `70/70` PASS. Full
  repository tests: `3033/3033` PASS. Frontend tests: `1155/1155` PASS with
  zero dependency vulnerabilities and complete Simplified/Traditional Chinese
  coverage. Local E2E: `472/472` PASS.
- ERPNext-test connector sender version `0.5.1`: `18/18` sender tests and
  `47/47` combined authorization tests PASS, including Python 3.10 compatibility
  required by ERPNext v15. The prior `0.5.0` connector was retained at
  `/home/ubuntu/npi-erpnext-connector-backups/0.5.0-before-unicode-role-fix`.
- Immutable LaunchFlow release and both active image revisions are the exact
  product SHA. All ten runtime services are running and the post-deployment
  health check passed.
- Encrypted pre-deployment backup:
  `/var/backups/launchflow/encrypted/launchflow-launchflow.whjichen.cn-20260905T163647Z.tar.gpg`,
  SHA-256 `54fbedc54ffe94e3baedd28cd932e045c9ed95eba45e5c5f28180f97fe12518c`.
- The existing deployment helper's known maintenance-mode/HTTP-200 probe
  conflict appeared only after migration had succeeded. Maintenance mode was
  turned off, the unchanged exact images completed startup, and no rollback or
  data loss occurred.

## Live authorization result

- The pre-repair delivery was correctly rejected as expired when retried after
  its authorization window elapsed; it was not forced through.
- A fresh source-version-2 ERPNext-test authorization event was delivered on
  its first attempt. Delivery ID and source event ID:
  `ef5c30f0-5608-59d0-b5ba-8c48bfcdebf4`.
- Canonical target: `kaibo_wang@whjichen.cn`; projection state: `enabled`;
  projected roles: `NPI API User`; Project access: empty; organization scopes:
  empty. Projection hash:
  `01d66d27133d156ac1ceb6e904ab3e161cf6bd5f5d49c1f987c7623813f188a0`.
- Authorization ingress is enabled. Enforcement remains disabled because the
  complete business-approved role and Project mappings do not yet exist.
- ERPNext-test has no Project User Permission row for this user, and the sender
  has no configured Project map or role-derived Project access. Project master
  synchronization is not implemented by this hotfix, so Projects created in
  ERPNext-test do not appear in NPI One yet.
- The ERPNext-test migration reported three orphan custom Reports. Their
  `Deleted Document` records exist and remain unrestored; no obsolete Report was
  revived during this repair.

Production ERPNext/JCE-Core contact: **false**. Final release-gate decision for
this bounded hotfix: **PASS**. This does not mark the product production-ready
and does not authorize permission enforcement or Project/master-data rollout.
