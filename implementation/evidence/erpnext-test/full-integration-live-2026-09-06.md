# NPI One to ERPNext Test Full Integration Evidence

Date: 2026-09-06 (Asia/Bangkok)

LaunchFlow Site: `launchflow.whjichen.cn`

ERPNext test Site: `jce.1` through `https://test.core.whjichen.cn`

LaunchFlow release: `1522d700f4f8675f91bd06d550522fa1e0106afa`

ERPNext connector app: `npi_erpnext_connector` `0.9.1`

The production ERPNext alias `JCE-Core` was not contacted or modified.

## Released integration boundary

- ERPNext owns User enablement, mapped roles, Project access, Customer,
  Supplier, Item Group, Item Code and formal manufacturing records.
- NPI One owns its engineering workflow and sends only approved execution
  commands to ERPNext over authenticated REST adapters.
- ERPNext Project, User authorization and master-data facts reach NPI One
  through fixed-schema, versioned and idempotent deliveries.
- NPI One Item, MBOM, Tool Asset, released Trial Summary and Engineering
  Change operations use project-bound profiles, bounded retries, replay,
  reconciliation and immutable receipts.
- The transport user remains separate from the business actor. ERPNext stores
  the NPI business actor as Created By/`owner` while retaining the service
  identity as `modified_by` and on the connector receipt.

## Release and recovery

- A full ERPNext-test backup was taken before installing the connector: database,
  public files, private files and Site configuration. The prior connector app was
  retained at `/home/ubuntu/npi-erpnext-connector-backups/0.9.0-before-final-24e592f1`.
- The immediately preceding `0.9.0` source was additionally retained at
  `/home/ubuntu/npi-erpnext-connector-backups/0.9.0-before-0.9.1-c6280c43`.
- The exact `0.9.1` ERPNext app archive checksum was
  `230b610431f4362aa9d3c7efcddcfd8874cda24a510ffdbb400351880ee4ddae`.
- ERPNext `bench migrate` and restart completed; web, Socket.IO, scheduler,
  short queue and long queue processes returned to `RUNNING`.
- A checksum-verified encrypted LaunchFlow backup was created before the final
  switch:
  `launchflow-launchflow.whjichen.cn-20260905T230837Z.tar.gpg`.
- The first switch failed closed only because the health script was invoked
  from the wrong working directory. It restored the retained release and passed
  its health gate. The corrected switch reused the verified images, migrated,
  and passed the final production health gate.
- All 10 required LaunchFlow services are running, none is unhealthy, and both
  backend and SPA OCI revision labels match the exact release SHA.

## Executable verification

- Exact repository release gate after the master-data freshness change:
  3,153/3,153 passed.
- Full non-visual browser suite: 472/472 passed; the three-language Project
  creation browser suite passed 3/3.
- Production image verification: 79 files and 1,165 tests passed.
- Frontend coverage passed at 80.04% statements, 79.43% branches, 82.06%
  functions and 82.65% lines.
- English-source i18n audit covered 9,468 literal sources with 100% Simplified
  and Traditional Chinese coverage.
- Production dependency audits reported zero vulnerabilities.
- The same custom app installed and migrated successfully on disposable
  ERPNext `15.121.0` / Frappe `15.120.0`, including two consecutive migrations,
  13 connector DocTypes and the `0.9.1` capability probe. The live target runs
  ERPNext `16.14.0` / Frappe `16.16.0`.

## Live connection and data exchange

The post-deployment connection endpoint returned:

```json
{
  "targetSystem": "ERPNEXT",
  "targetEnvironment": "test",
  "connectionState": "connected",
  "capabilities": {
    "authorizationSynchronization": true,
    "itemCommands": true,
    "projectSynchronization": true,
    "masterDataSynchronization": true,
    "reportingSynchronization": true
  }
}
```

ERPNext-test delivered these owned master catalogs to NPI One:

| Catalog | Records | Source version | Delivery |
| --- | ---: | ---: | --- |
| Customer | 13 | 2 | delivered |
| Supplier | 35 | 2 | delivered |
| Item Group | 24 | 2 | delivered |
| Item | 816 | 2 | delivered |

Unchanged delivered catalogs are reissued after one hour by the existing
15-minute reconciliation schedule. This keeps the two-hour LaunchFlow
connection freshness gate truthful without creating or modifying an ERPNext
business record. The post-delivery LaunchFlow status again reported all five
capabilities as `true` and `connectionState` as `connected`.

ERPNext-test Projects were seeded without creating replacement ERP records:

| ERP Project | NPI global ID | NPI owner | State |
| --- | --- | --- | --- |
| `PROJ-0027` | `0f7af44c-3859-58e4-83e2-d484dcae6941` | `kaibo_wang@whjichen.cn` | draft |
| `PROJ-0028` | `503e9075-c77b-5e16-b7b3-5375ce410ee6` | `kaibo_wang@whjichen.cn` | draft |

The latest `kaibo_wang@whjichen.cn` authorization delivery is source version
9, status `delivered`. Its NPI projection is enabled with roles `NPI API User`
and `System Manager`, and `administer` access to both Project global IDs.
Authorization projection enforcement and the inbound authorization,
master-data and Project routes are enabled.

The deployed session bootstrap exposes `canCreateProject` to this internal
System Manager. The application shell now provides `Quick create` ->
`Create project`, backed by the real `POST /api/npi/v1/projects` command. Its
creation context uses the published `ERPTEST-NEW-TOOL` template version 1 for
`new_tool` Projects and the authenticated actor as owner. No Project was
fabricated for this availability check.

LaunchFlow has two real Project-bound profiles for each outbound operation:
Item, MBOM, Tool Asset, released Trial Summary and Engineering Change. On
ERPNext-test, all five receiver families and all three outbound sender families
(authorization, Project and master data) are enabled.

The existing live Item proof remains stable after the final release: ERPNext
assigned Item Code `61000334`; `owner` is the NPI business actor
`npi-integration-test-user@erpnext-test.invalid`; `modified_by` is the transport
identity `npi-item-integration@erpnext-test.invalid`; exact replay did not create
a duplicate Item, mapping or receipt.

## Honest remaining external configuration

The integration itself is active. Microsoft Entra sign-in is not configured on
the LaunchFlow Site because the tenant application ID and credential are
separately owned and were not supplied to this task. Until that provider is
configured, users sign in through the existing Frappe session path; ERPNext
continues to own and synchronize their NPI authorization.

No synthetic EBOM, Tool acceptance, Trial conclusion or Engineering Change
business document was created merely to exercise a live command. Those paths
are installed, enabled, profile-bound and contract-tested; their first live
receipts will be created from the corresponding real approved NPI records.
