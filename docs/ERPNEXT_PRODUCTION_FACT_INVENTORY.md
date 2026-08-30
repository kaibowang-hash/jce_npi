# ERPNext Production Fact Inventory

Status: **INCOMPLETE — VERSION/SITE INVENTORY ACCEPTED; APP METADATA HELD**

Inventory task: `P8-07F-FACTS`

Inventory attempts: `2026-08-30T00:04:24Z`, `2026-08-30T05:35:04Z`, and
accepted fixed-root discovery `2026-08-30T06:10:50Z` /
`2026-08-30T13:10:50+07:00`

Source label: `JCE_CORE_PRODUCTION_REDACTED`

## Safety and provenance

The P8-07F governance transition passed ordinary CI `33279778063` and Level 3
`33280319184` at exact SHA
`d919d695972260fa86d5df7fa60033e6adb62f49`. The separate facts activation
passed ordinary CI `33281944546` at exact SHA
`c8d3b3c0e9fd3f8d92a1679713ef8afc0157ff20`.

The collector then attempted exactly one allowlisted remote operation,
`ERP_VERSION`, through SSH alias `JCE-Core`. It stopped with
`UNVERIFIED_OPERATION_FAILED_WITHOUT_ACCEPTED_OUTPUT`. No remote output was
accepted, persisted or displayed; no endpoint, host, user, key, secret,
business value or raw stderr/stdout is recorded here. The private state file
was not created. No retry, alias probe, command substitution, allowlist
expansion, REST fallback, Site command or later operation occurred.

After the user requested a connection check, the same governed `ERP_VERSION`
operation was attempted once more at `2026-08-30T05:35:04Z` from exact SHA
`5b72a85503ba77f6d55b94255f1d805bbcf5475d` after ordinary CI `33283299773`
passed. It again stopped with
`UNVERIFIED_OPERATION_FAILED_WITHOUT_ACCEPTED_OUTPUT`. The collector did not
accept or expose SSH stderr, so the failure cannot be safely classified as
transport, authentication, authorization, remote PATH or Bench availability.
No private state file was created and no later operation ran.

The user then confirmed that the deployment uses the default relative Bench
root `frappe-bench` and supplied the runtime Site privately. The Site value is
not repeated in this inventory. Repository inspection proved the collector had
executed its seven commands from the SSH login directory rather than binding
the Bench root. Therefore the two failed operations do not prove that SSH is
unreachable. Fixed-root repair SHA
`9ab9bd5199e5521f3a72e701c3fa4338d6e866db` then passed ordinary CI
`33295753975`. Its bounded `ERP_VERSION` and private-Site `INSTALLED_APPS`
operations succeeded and created a mode-0600 temporary state. The accepted
sanitized inventory contains Frappe `15.79.0`, ERPNext `15.77.0`, twenty Bench
apps and a verified Site-app subset. No Site value or custom app name is
committed.

Three subsequent `APP_HEAD` calls completed through the same fixed wrapper.
Before the first `APP_STATUS` SSH process could start, the local collector
rejected its fixed `--untracked-files=no` token because `=` is excluded by the
remote-token grammar. No status, tracked-path or file operation followed. The
equivalent fixed Git token `-uno` must pass a new exact-SHA ordinary CI before
application metadata reads resume.

An earlier local invocation rejected an invalid private-state path before any
SSH process was started. It is a local preflight fact, not a production
operation.

| Attempt | Operation | Production contact | Result | Accepted checksum | Follow-up |
|---|---|---:|---|---|---|
| Local preflight | state-path validation | No | Rejected before SSH | Not applicable | Corrected to the operating-system temporary root |
| 1 | `ERP_VERSION` | Yes, one bounded attempt | `UNVERIFIED_OPERATION_FAILED_WITHOUT_ACCEPTED_OUTPUT` | `NOT_AVAILABLE_NO_ACCEPTED_OUTPUT` | Stopped fail closed; no retry |
| 2 | `ERP_VERSION` | Yes, one user-requested bounded attempt | `UNVERIFIED_OPERATION_FAILED_WITHOUT_ACCEPTED_OUTPUT` | `NOT_AVAILABLE_NO_ACCEPTED_OUTPUT` | Stopped fail closed; no probe, fallback or later operation |
| 3 | `ERP_VERSION` | Yes, fixed-root bounded read | `ACCEPTED_SANITIZED` | `sha256:bc5f2b2653647c21c6cee66e357951831f4e1e512ca9bcb641f8b017fef9b815` | Frappe/ERPNext versions and twenty anonymous app rows accepted |
| 3 | `INSTALLED_APPS` | Yes, private-Site bounded read | `ACCEPTED_SANITIZED` | `sha256:cec7d8128c63e6b79bc6fcf9da558378d2c134a9f96a9a5a8b36a585b319c0fd` | Site app subset verified; Site value not recorded |
| 3 | `APP_HEAD` | Yes, three bounded reads | `ACCEPTED_TRANSIENT_NOT_PROMOTED` | Retained only in private execution context | Rerun only after the next harness Gate when producing the complete app inventory |
| Local stop | `APP_STATUS` token construction | No | `REJECTED_BEFORE_SSH` | Not applicable | Replace only the fixed equals-form with `-uno`; require ordinary CI |
| — | `APP_TRACKED_PATHS`, `APP_FILE_HASH`, `APP_FILE_READ` | No | `NOT_INVOKED_AFTER_LOCAL_STOP` | Not available | Await fixed-token ordinary PASS |

## Accepted application version inventory

Custom application identity remains private. Labels are deterministic only
within this inventory epoch and must not be interpreted as product names.

| Label | Version |
|---|---|
| `FRAPPE` | `15.79.0` |
| `ERPNEXT` | `15.77.0` |
| `CUSTOM_APP_01` | `0.0.1` |
| `CUSTOM_APP_02` | `15.0.41` |
| `CUSTOM_APP_03` | `15.0.45` |
| `CUSTOM_APP_04` | `0.0.1` |
| `CUSTOM_APP_05` | `1.0.2` |
| `CUSTOM_APP_06` | `0.0.1` |
| `CUSTOM_APP_07` | `15.37.1` |
| `CUSTOM_APP_08` | `0.0.2` |
| `CUSTOM_APP_09` | `0.0.1` |
| `CUSTOM_APP_10` | `0.0.1` |
| `CUSTOM_APP_11` | `0.0.1` |
| `CUSTOM_APP_12` | `0.1.12` |
| `CUSTOM_APP_13` | `0.0.6` |
| `CUSTOM_APP_14` | `1.6.5` |
| `CUSTOM_APP_15` | `15.1.41` |
| `CUSTOM_APP_16` | `0.0.3` |
| `CUSTOM_APP_17` | `15.0.24` |
| `CUSTOM_APP_18` | `1.0.2` |

## Production fact matrix

`UNVERIFIED` means no accepted production evidence exists. It does not mean
absent, incompatible or defective.

| Fact area | Status | Accepted production fact | Evidence/checksum | Impact |
|---|---|---|---|---|
| Frappe and ERPNext exact versions/builds | `PARTIALLY_VERIFIED` | Frappe `15.79.0`; ERPNext `15.77.0`; exact public HEAD promotion pending | Accepted Bench checksum above | Version-specific source compatibility remains held until app HEAD/source inventory |
| Installed apps and app versions | `PARTIALLY_VERIFIED` | Twenty Bench apps; private Site subset verified; custom identities redacted | Accepted Bench and Site checksums above | Custom-app capability compatibility still held pending source facts |
| Topology, database/storage type and locale | `UNVERIFIED` | None | No allowlisted accepted source | Deployment and locale compatibility held |
| Custom app identities and commit state | `PARTIALLY_VERIFIED` | Eighteen anonymous custom-app version rows; complete HEAD/status evidence pending | Three HEAD reads transient; status not invoked | No capability may yet be classified Already Present or Missing |
| Hooks, overrides, patches, fixtures and modules | `UNVERIFIED` | None | APP operations not invoked | No extension decision authorized |
| Whitelisted methods, operation APIs and schemas | `UNVERIFIED` | None | APP operations not invoked | P8-02 through P8-07 target bindings remain unavailable |
| Scheduler/jobs, webhooks and service integrations | `UNVERIFIED` | None | No accepted source | No job or delivery contract inferred |
| Reports, print formats, notifications and workspaces | `UNVERIFIED` | None | No accepted source | No UI/report customization inferred |
| DocTypes and declarative metadata | `UNVERIFIED` | None | No accepted tracked source | Field and lifecycle mappings remain held |
| Custom Fields and Property Setters | `UNVERIFIED` | None | Runtime-only facts not available through accepted source | No field addition/removal recommendation |
| Client Script and Server Script | `UNVERIFIED` | None | Runtime-only facts not available through accepted source | No script compatibility conclusion |
| Workflows, states, actions and Naming Series | `UNVERIFIED` | None | Runtime-only facts not available through accepted source | Business mapping remains owner decision |
| Roles, Role Profiles, DocPerm, User Permissions and sharing | `UNVERIFIED` | None | Runtime-only facts not available through accepted source | Permission/service-scope activation held |
| Service principals and operation scopes | `UNVERIFIED` | None | No accepted source | No production adapter profile can be enabled |
| File/attachment policy, storage and retention | `UNVERIFIED` | None | No accepted source | File-copy/reference behavior remains held |
| Customer and Supplier | `UNVERIFIED` | None | No metadata or bounded sample accepted | P8-01 projections remain production-unbound |
| Project, Quotation and Sales Order source lifecycle | `UNVERIFIED` | None | No metadata or webhook/API fact accepted | P8-02 remains production-unbound |
| Item, variants, UOM and naming | `UNVERIFIED` | None | No metadata or API fact accepted | P8-03 remains production-unbound |
| EBOM/MBOM/BOM, routing and submission lifecycle | `UNVERIFIED` | None | No metadata or API fact accepted | P8-04 remains production-unbound |
| PO, receipt, inventory and cost | `UNVERIFIED` | None | No metadata or API fact accepted | Cost/procurement projections remain held |
| Quality Inspection, NCR and CAPA | `UNVERIFIED` | None | No metadata or lifecycle fact accepted | P8-06 keeps raw formal truth unavailable |
| Asset, maintenance, movement, repair and spares | `UNVERIFIED` | None | No metadata or API fact accepted | P8-05 remains production-unbound |
| Released Trial Summary consumer seam | `UNVERIFIED` | None | No target consumer/method fact accepted | P8-08 cannot activate |
| JCE Core display identity context | `UNVERIFIED` | None | Production display surface not inspected | P8-09 keeps technical code `ERPNEXT` unchanged |

## Freshness and delta policy

The accepted Bench/Site checksums are the freshness baseline. Resume only after
the fixed `APP_STATUS` token repair passes exact-SHA ordinary CI, then use
HEAD/status/path/hash deltas before any bounded tracked-file read. Do not repeat
full discovery unless a version/checksum delta requires it. The standing
authorization removes the need for another user prompt; it does not remove the
fail-closed checks or grant write authority.

## No-change boundary

- No production ERPNext or Frappe state was changed.
- No ERPNext/Frappe core change is proposed.
- No browser-to-ERP connection, generic DocType writer, cross-database access,
  dual-master field or Mock/HTTP fake success is permitted.
- No LaunchFlow contract, ownership, domain, adapter or UI adjustment is
  justified by this incomplete inventory.
- M9-04 and M9-05 real-project pilots remain user-approved post-V1.2 deferrals;
  controlled non-production UAT is not a real-pilot or adoption claim.

## Open risks and stop condition

Production compatibility remains unverified. P8-08 and every production-bound
activation stay held. If a later attempt encounters the same failure,
permission insufficiency, a version or shape mismatch, sensitive-output risk,
allowlist drift or a need for a write, the affected collection stops again
without privilege expansion. A concrete contract/ownership conflict must be
recorded as an ADR or business decision before any implementation task.
