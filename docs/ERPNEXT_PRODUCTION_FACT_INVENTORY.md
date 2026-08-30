# ERPNext Production Fact Inventory

Status: **INCOMPLETE — READ-ONLY COLLECTION COMPLETE; SOURCE DRIFT AND RUNTIME METADATA BLOCKED**

Inventory task: `P8-07F-FACTS`

Inventory attempts: `2026-08-30T00:04:24Z`, `2026-08-30T05:35:04Z`, and
accepted fixed-root discovery `2026-08-30T06:10:50Z` /
`2026-08-30T13:10:50+07:00`, and checksum-confirming discovery
`2026-08-30T06:35:13Z` / `2026-08-30T13:35:13+07:00`

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

The narrow `APP_STATUS` token repair passed at exact SHA
`be03972abd13b60284a8f950eae7cdf7776781d7` / ordinary `33296694027`.
Checksum-confirming discovery then matched the accepted Bench and Site
inventories, and bounded `APP_HEAD` plus `APP_STATUS` completed for Frappe,
ERPNext and all eighteen anonymous custom apps. Frappe is clean; ERPNext has
one tracked drift; twelve custom apps have tracked drift. These facts prohibit
treating `git show HEAD` as actual runtime source for a dirty app.

`APP_TRACKED_PATHS` accepted bounded structure for `CUSTOM_APP_01` and
`CUSTOM_APP_02`. The next path inventory stopped locally when the line parser
could not safely represent one legitimate `CUSTOM_APP_03` tracked path. The
raw path was neither displayed nor committed, and no later path or file
operation ran. The closed repair changes only this operation to exact
`git ls-files -z` plus NUL-aware parsing; it requires a new exact-SHA ordinary
CI before path collection resumes.

The NUL-framing repair passed at exact SHA
`acbd6882869a4a8c27eb653019080354055f74a8` / ordinary `33297909199`:
repository `99220637261`, visual `99220637358`, frontend `99220637376` and
secret scan `99220637391` all passed. From `2026-08-30T07:07:57Z` through the
bounded collection close at `2026-08-30T07:14:52Z`, checksum-first discovery
remained unchanged and all twenty NUL-framed path inventories succeeded.

Bounded HEAD source summaries then ran only for the six anonymous custom apps
whose tracked status was clean. Two relevant DocType candidates independently
triggered the collector's sensitive-content preflight; neither path, source,
field nor matched value was emitted, and all later DocType reads stopped. The
remaining clean-app non-DocType summaries completed. The mode-0600 private
state was then deleted. ERPNext and twelve custom apps were not source-read
because their tracked worktrees are dirty; the fixed allowlist cannot prove
runtime-only Custom Fields, Property Setters, Scripts, Workflows, roles,
permissions, service scopes or Naming Series. These are evidence blockers, not
proven incompatibilities.

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
| 4 | `ERP_VERSION`, `INSTALLED_APPS` | Yes, checksum-first bounded reads | `ACCEPTED_UNCHANGED` | Same two accepted checksums | No version or Site-inventory drift |
| 4 | `APP_HEAD`, `APP_STATUS` | Yes, all twenty apps | `ACCEPTED_SANITIZED` | Anonymous commit/drift facts below | Frappe clean; ERPNext drift 1; custom drift 12/18 |
| 4 | `APP_TRACKED_PATHS` | Yes, three bounded calls | `PARTIAL_STOPPED_FAIL_CLOSED` | First two structures accepted; third raw path rejected locally | Replace line framing with NUL framing; require ordinary CI |
| — | `APP_FILE_HASH`, `APP_FILE_READ` | No | `NOT_INVOKED_AFTER_PATH_STOP` | Not available | Await NUL-framing ordinary PASS and safe path classification |
| 5 | `ERP_VERSION`, `INSTALLED_APPS` | Yes, checksum-first bounded reads | `ACCEPTED_UNCHANGED` | Same two accepted checksums | No version or Site-inventory drift |
| 5 | `APP_TRACKED_PATHS` | Yes, all twenty apps | `ACCEPTED_SANITIZED` | Anonymous checksums and counts below | NUL framing closed the prior parser boundary |
| 5 | `APP_FILE_HASH`, `APP_FILE_READ` | Yes, clean-app bounded subset only | `PARTIAL_ACCEPTED_WITH_TWO_SENSITIVE_PREFLIGHT_STOPS` | Anonymous object/content checksums and structures below | No dirty-app source promoted; no later DocType read after the second stop |
| 5 | `CLEANUP` | No production contact | `ACCEPTED` | Mode-0600 state removed | No custom identity/path/source retained locally |

## Accepted application version inventory

Custom application identity remains private. Labels are deterministic only
within this inventory epoch and must not be interpreted as product names.

| Label | Version | Accepted HEAD | Tracked drift rows |
|---|---|---|---:|
| `FRAPPE` | `15.79.0` | `35b41c15636031dde4868315323594d0081de826` | 0 |
| `ERPNEXT` | `15.77.0` | `c86e95e52422d395c8a4c76a83f5cbf3a2f86c11` | 1 |
| `CUSTOM_APP_01` | `0.0.1` | `7d701e3cc4141f440e1be86590b604b5b6736952` | 1 |
| `CUSTOM_APP_02` | `15.0.41` | `0e575da2240cfd1ae531d76f5af342a7bafa22b9` | 4 |
| `CUSTOM_APP_03` | `15.0.45` | `463498faa3b948ac5fcd0d51386b4c0c1c5e0a06` | 3 |
| `CUSTOM_APP_04` | `0.0.1` | `ec478c73245f11b59f40ac43bc7a1b61b957fb15` | 5 |
| `CUSTOM_APP_05` | `1.0.2` | `b7283f611b34db06af81a1a20e710fd93d5fd7e4` | 4 |
| `CUSTOM_APP_06` | `0.0.1` | `4b6f0136cf156c891b740e0a603e293bc03fcc00` | 0 |
| `CUSTOM_APP_07` | `15.37.1` | `c4e536833d1723c8fa68181bdd6ec80be4bb2b4d` | 0 |
| `CUSTOM_APP_08` | `0.0.2` | `0e77af58b0ccf60bf2dc2d5b418b11fdbba9777c` | 2 |
| `CUSTOM_APP_09` | `0.0.1` | `a6d0845691f253bc3fb3798e816bd179f965d32d` | 0 |
| `CUSTOM_APP_10` | `0.0.1` | `9572b2bc6cd85705191f6aea14dbb9683a8a7c45` | 4 |
| `CUSTOM_APP_11` | `0.0.1` | `334e56c22671b08c4254c807bbef14e3fa388559` | 5 |
| `CUSTOM_APP_12` | `0.1.12` | `f8c30f10aa422213fd54288fe0c09f8be0dbc8ed` | 0 |
| `CUSTOM_APP_13` | `0.0.6` | `0c1678987ba17b3188e0f74ff47526c717d26401` | 39 |
| `CUSTOM_APP_14` | `1.6.5` | `fa16fba88adc55d85f29fdd8b183c29670863949` | 0 |
| `CUSTOM_APP_15` | `15.1.41` | `fc85ddeb8dc14b0873006ef69d7eec60d3a4bf78` | 2 |
| `CUSTOM_APP_16` | `0.0.3` | `23e44ff00bf51562a3aafa10952bc0246e29e777` | 2 |
| `CUSTOM_APP_17` | `15.0.24` | `ec33227d17fd4ceef913b5c355cf8647c91bf8c1` | 2 |
| `CUSTOM_APP_18` | `1.0.2` | `a564e59d5f63efe8d82916da8e30e4d154e0425f` | 0 |

## Accepted tracked-path inventory

Counts are lexical structure only; they do not prove that a capability is
configured, enabled, permitted or compatible. `D/F/A/J` means DocType JSON,
fixture paths, API-like paths and job/scheduler-like paths.

| Label | Tracked paths | D/F/A/J | Hooks/modules/patches | Path checksum |
|---|---:|---|---|---|
| `FRAPPE` | 3176 | 297/33/6/8 | 1/1/174 | `sha256:fe62534f3d045932fca83ca09faa06c8b00015e8a9ec8262a1a0b36253496991` |
| `ERPNEXT` | 4587 | 652/4/0/2 | 1/1/376 | `sha256:508022c308a8b4aec9efe9302175e7dee940969572528a9bfcfac75db56e84b1` |
| `CUSTOM_APP_01` | 16 | 0/0/0/0 | 1/1/1 | `sha256:9e385ca9d51e64a5aeea09d6990702289bb521150a32bf44d415250219d7099d` |
| `CUSTOM_APP_02` | 42 | 2/1/0/0 | 1/1/1 | `sha256:c22ce2d68f50f3b5941c0657df95c71732896243abddb21eb3f38bb77140276a` |
| `CUSTOM_APP_03` | 131 | 7/2/1/0 | 1/1/2 | `sha256:cd618a17321f653bf1d70e051d9f482c15aeddb8b5016edd10311e1dd1d46cb9` |
| `CUSTOM_APP_04` | 17 | 0/0/0/0 | 1/1/1 | `sha256:7835816d5d9d651a87bd0f77d8eb5067c89ea169adfc6d6eb288a4c65a8f87a3` |
| `CUSTOM_APP_05` | 229 | 25/1/0/0 | 1/1/13 | `sha256:aab54fd5b1e51d8474706d7ea42deb3510e258e271fcb2db30e35bd929fadc5a` |
| `CUSTOM_APP_06` | 49 | 2/3/0/0 | 1/1/1 | `sha256:d674a6908cb2232f3c1a2014f56ba026715d889c2de137457d292fde671aae62` |
| `CUSTOM_APP_07` | 1437 | 156/1/3/5 | 1/1/40 | `sha256:ec868781f738c40989c52a0150f71dd2fd48ddb99f1f158c1cb7b38d3698e28f` |
| `CUSTOM_APP_08` | 357 | 39/3/2/0 | 1/1/17 | `sha256:906020dd5b7fa85c918c3248f3fbb62899633a47c96e847108f8767994be2b33` |
| `CUSTOM_APP_09` | 114 | 14/0/3/0 | 1/1/6 | `sha256:316e8cf08baa1e7007956aa9f78582c15f185d65d23812227ca0da3eaf0984c1` |
| `CUSTOM_APP_10` | 53 | 3/0/5/0 | 1/1/1 | `sha256:8c72ad66bc61e2010ce0ee66fae972407968a804b7d5962e60598bd3c7f80233` |
| `CUSTOM_APP_11` | 237 | 32/0/7/0 | 1/1/6 | `sha256:24a8467bdc853101c4958da48eeb98b97c7b524337a1c8c4353a40746e98059b` |
| `CUSTOM_APP_12` | 145 | 21/2/1/0 | 1/1/1 | `sha256:df1f29e6452098bd2a4ddb46f25ee870c10b0d18dbc5f00c469a4df76a839f34` |
| `CUSTOM_APP_13` | 173 | 22/0/2/0 | 1/1/6 | `sha256:30c20a4ecbaee174cfeacc467eda91b3974d5b24f11dfc022a54f22badb1dda9` |
| `CUSTOM_APP_14` | 158 | 0/0/0/0 | 1/1/19 | `sha256:556781de65e0df75c99ca0f76e460e32c75efcd88f78eecda9a50843217cdb96` |
| `CUSTOM_APP_15` | 214 | 37/4/1/0 | 1/1/1 | `sha256:146e6b68b99ad22c4595151a1527855ee2facf4783ee8ef2ecee6d3633a0fe5e` |
| `CUSTOM_APP_16` | 24 | 1/0/1/0 | 1/1/1 | `sha256:c10f1095b309ec2733c90c340cab16c30272c9cb92053dc204d070872d0e3128` |
| `CUSTOM_APP_17` | 102 | 9/2/1/0 | 1/1/1 | `sha256:96995f515ce5ef9fbc6d820053a5819b73d9dd027e5be17854fc531c37873a28` |
| `CUSTOM_APP_18` | 27 | 0/2/1/0 | 1/1/1 | `sha256:717183d4ea65f8c171d2d3cb8b27c4b8fc57efb9720ae63671be9ef6211fd14d` |

## Bounded clean-app source findings

| Label | Accepted clean HEAD summary | Compatibility consequence |
|---|---|---|
| `CUSTOM_APP_06` | Hooks expose Desk JS plus DocType JS/class overrides; one module, six patch-list lines and two fixture files (6 and 0 rows) were checksumed | No P8 operation-specific API or target binding was observed; `NO_CHANGE`, mapping remains unverified |
| `CUSTOM_APP_07` | Hooks include doc events, overrides, scheduler and workflow-aware HR APIs; one module and 27 patch-list lines | HR/workflow functions do not prove an NPI integration target. First relevant DocType candidate stopped at sensitive preflight |
| `CUSTOM_APP_09` | Hooks include doc events, whitelisted overrides and scheduler; APIs expose APS/MRP, stock-buffer, proposal/release and barcode functions | Existing manufacturing-planning extension is not an Item/MBOM/Asset/quality target contract. First relevant DocType candidate stopped at sensitive preflight |
| `CUSTOM_APP_12` | Hooks include fixtures, DocType/list JS and method/class/dashboard overrides; APIs expose tracking-number, workstation employee and work-order-operation helpers; fixtures contain 88 and 3 rows | Existing execution helpers do not prove any P8 target operation; DocType content was not read after the global DocType stop |
| `CUSTOM_APP_14` | Hooks expose request lifecycle, print/PDF generators, DocType/page JS, scheduler and class overrides; one module and 19 patch-list lines | Print/PDF extension is not evidence for a P8 target contract |
| `CUSTOM_APP_18` | Hooks expose fixtures, DocType JS and method/class/dashboard overrides; one whitelisted purchase-invoice creator; fixtures contain 3 and 1 rows | Purchase-invoice behavior is outside the currently implemented P8-01..09 target operations; no direct-match claim |

No bounded clean-app summary proved the exact production methods, payloads,
permissions or lifecycle expected by P8-01 through P8-09. This is not evidence
that those capabilities are absent: most app worktrees are dirty and runtime
metadata is outside the fixed source-only allowlist.

## Production fact matrix

`UNVERIFIED` means no accepted production evidence exists. It does not mean
absent, incompatible or defective.

| Fact area | Status | Accepted production fact | Evidence/checksum | Impact |
|---|---|---|---|---|
| Frappe and ERPNext exact versions/builds | `VERIFIED_WITH_DRIFT_HOLD` | Frappe `15.79.0` clean at accepted HEAD; ERPNext `15.77.0` at accepted HEAD with one tracked drift | Accepted Bench checksum and HEAD/status rows above | ERPNext HEAD source cannot represent the dirty runtime tree until the drift is separately reconciled |
| Installed apps and app versions | `VERIFIED_IDENTITIES_REDACTED` | Twenty Bench apps; private Site subset verified; custom identities redacted | Accepted Bench and Site checksums above | Capability compatibility remains held pending bounded source facts |
| Topology, database/storage type and locale | `UNVERIFIED` | Bench-root and private Site membership only; database/storage/locale not exposed | Fixed allowlist intentionally excludes Site config and runtime queries | Deployment and locale compatibility held |
| Custom app identities and commit state | `VERIFIED_WITH_DRIFT_HOLDS` | Eighteen anonymous version/HEAD rows; twelve have tracked drift | Accepted HEAD/status table above | Dirty app HEAD source cannot be promoted as runtime truth; no capability decision yet |
| Hooks, overrides, patches, fixtures and modules | `PARTIALLY_VERIFIED_STRUCTURE_ONLY` | `CUSTOM_APP_01`: 16 tracked paths with hooks/modules/patches; `CUSTOM_APP_02`: 42 tracked paths with hooks/modules/patches, 11 DocTypes, fixtures and overrides | Bounded path classifications before parser stop | Contents and all other apps remain unverified; no extension decision authorized |
| Whitelisted methods, operation APIs and schemas | `PARTIALLY_VERIFIED_NO_P8_BINDING` | Clean-app samples expose HR, APS/MRP, stock-buffer, tracking/work-order, barcode and purchase-invoice methods; none proves a P8 target contract | Anonymous clean-app object/content checksums above | P8-01 through P8-09 target bindings remain unavailable; no adjustment proven |
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

The accepted Bench/Site checksums, HEAD/status table and tracked-path checksums
are the freshness baseline. This bounded collection is closed and its private
state removed. A future task must compare version/HEAD/status/path checksums
first and may read only changed necessary facts. Dirty applications remain
held unless their actual tracked worktree state is restored to clean or supplied
as a separately accepted sanitized evidence bundle. Do not repeat full
discovery unless a version/checksum delta requires it. The standing
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
activation stay held. Required recovery evidence is either (a) clean tracked
ERPNext and custom-app worktrees at declared commits plus a new checksum delta,
or (b) an owner-supplied sanitized, checksummed drift/source bundle; and a
separately gated side-effect-free source for runtime-only metadata. The two
sensitive-preflight DocType candidates also require sanitized owner evidence,
not a weaker scanner. Permission insufficiency, version/shape drift,
sensitive-output risk, allowlist drift or a write need stops the affected part
without privilege expansion. A concrete contract/ownership conflict must be
recorded as an ADR or business decision before any implementation task.
