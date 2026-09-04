# ERPNext Production Fact Inventory

Status: **COMPLETE FOR P8-07F — BOUNDED PRODUCTION FACTS ACCEPTED; EXPLICIT NON-BLOCKING UNKNOWNS RETAINED**

Inventory task: `P8-07F-FACTS`

Inventory attempts: `2026-08-30T00:04:24Z`, `2026-08-30T05:35:04Z`, and
accepted fixed-root discovery `2026-08-30T06:10:50Z` /
`2026-08-30T13:10:50+07:00`, and checksum-confirming discovery
`2026-08-30T06:35:13Z` / `2026-08-30T13:35:13+07:00`, and final locale
read `2026-08-30T13:07:50.798302Z` / `2026-08-30T20:07:50.798302+07:00`

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

## Accepted current-worktree and runtime metadata overlay

This section supersedes the provisional `UNVERIFIED` entries in the earlier
chronological matrix while preserving that ledger as audit history. The user
authorized dirty tracked worktrees as current source truth and authorized the
two stopped DocType sources plus fixed application-layer metadata reads. No
production file or database record was changed.

| Fact area | Accepted P8-07F status | Sanitized production fact | Provenance / checksum | Compatibility consequence |
|---|---|---|---|---|
| Platform and Site | `VERIFIED` | Frappe `15.79.0`, ERPNext `15.77.0`, twenty Bench apps and the private Site subset | Bench `sha256:bc5f2b2653647c21c6cee66e357951831f4e1e512ca9bcb641f8b017fef9b815`; Site `sha256:cec7d8128c63e6b79bc6fcf9da558378d2c134a9f96a9a5a8b36a585b319c0fd` | Supported v15 application-layer contracts; no version-driven LaunchFlow change |
| Current source truth | `VERIFIED_WITH_TRACKED_DRIFT` | Frappe clean; ERPNext has one tracked change; twelve of eighteen custom apps have tracked changes. Current tracked files, not HEAD alone, were used for authorized structural summaries | Anonymous HEAD/status/path inventory plus current Git-object reconstruction | Dirty state is accepted as current evidence, never promoted as a clean release or modified by P8-07F |
| Runtime customization metadata | `VERIFIED_STRUCTURE_ONLY` | Fixed sanitized Custom Field, Property Setter, Workflow/state/transition, Role/custom permission, Client Script, Server Script, Webhook, scheduled-job, report, print-format, notification and naming-rule metadata completed | Client Scripts: 98 rows/five pages, `sha256:49a8951fc934b064368bc1dc22f0def7f766a04901170c79792629b31faf9dbb`; other families remain checksum-bound in the closed collector ledger | No evidence of a contract-breaking customization; exact business activation remains owner/Sandbox work |
| Relevant DocTypes and fields | `VERIFIED_WITH_ONE_EXPLICIT_ABSENCE` | 27 of 28 frozen relevant DocTypes exist. `Injection Molding Condition` is absent. DocField projection completed for all 27 present parents | DocTypes `sha256:8506387ca0f59657110860127c360d45311038bf4b922ba6552774552e6b3db0`; DocFields `sha256:ae102d77b9116b1e81cc21da18f3d6ffd5bdcdbbf379e1fed811681e4979e449` | Existing Customer/Supplier/Project/Item/BOM/PO/Quality/DMR/Asset/Mold families support configuration/mapping; the absent optional condition DocType is not a P8 architecture conflict |
| Permissions | `VERIFIED_STRUCTURE_ONLY` | 120 sanitized DocPerm rows across the 27 present relevant parents | `sha256:61b485438675708641d5c03c448a9862f70b93f917f2ba4bfb1809c8f7f8a451` | Production roles exist, but an operation-specific least-privilege NPI service scope still requires owner approval and Sandbox verification |
| Mold domain current source | `VERIFIED_CURRENT_DIRTY_TRACKED_SOURCE` | Mold, Mold Management Settings, Mold Outsource, Mold Repair and Mold Trial Report structures were read from the actual tracked worktree. Mold exposes ownership/customer/Asset/status/version/location/shot/product/material/condition links; repair covers issue, external supplier/PO/finance, execution, acceptance and trial; trial report covers Mold/Item/trial result/machine/material/sample/issues/condition sheet/repair | Mold `sha256:8782b281648d9e45b87b7169272b1d51a03880a8c9f04f9216a5c1ff011f3845`; settings `sha256:45ef0124a421f7040ef21753f00456092780032d56dcc082c057068b5b4eecd4`; repair `sha256:462bdc6d4db7bdfa7b38c5b9054b4d606bf0f7664a463b11addf79146e9a5ee2`; trial report `sha256:453a96925430005a739f6a3f4317b58ff6bd5ed28523a573a6ae137db77308fd` | P8-05 and P8-08 have concrete production object seams; reuse plus configuration/mapping is preferred, with no domain redesign |
| Locale | `VERIFIED` | Country `Thailand`, System language `en-GB`, timezone `Asia/Chongqing` | Result `sha256:cc94b21fbc7a0556244ef71b117359ab7ee38022e8b32e5999d5b417fdcbe355`; raw envelope `sha256:c554853696236992c4209f30796a39a41e434d4b066f92d52bc24d9532737945` | LaunchFlow keeps Frappe-compatible locale parsing; timezone/country are deployment configuration, not a product redesign |
| File URL shapes | `VERIFIED_AGGREGATE_ONLY` | 47,376 File rows: 1,632 local public, 45,470 local private, 272 external HTTP | `sha256:64812dc22706aa9b7886eb9b34e37b80eeeaf9d53da3e1a6c3f527c3fa08a785` | References must preserve private/local/external distinctions; no file bytes or URLs were collected |

Remaining unknowns are deliberate and do not block P8-08 design work: database
engine/storage topology, representative business rows, exact production
service-principal identity, business-owner approval of raw status/code mappings,
and Sandbox/UAT/deployment facts. They remain release/activation inputs, not
evidence of incompatibility. No endpoint, host, user, key, Site value, secret,
raw Script, raw source, URL or business record is retained.

The final bounded locale reader is exact SHA
`77b4258f3b086420e0ae7769bd95830bf9dabfaa`, ordinary CI `33312664804`:
secret `99260395010`, visual `99260395168`, repository `99260395171` and
frontend `99260395257` all pass. The private mode-0600 state was removed after
the read.

## P9-01 Engineering Change exact metadata delta

P9-01 collector repair exact SHA
`28ff94de1ffb62f9f6b5763d00f0ce5a2c15c069` passes ordinary CI
`33350269304`: visual `99362120673`, frontend `99362120797`, repository
`99362120857` and secret scan `99362120983` all pass. At
`2026-08-31T02:33:29.141168Z` the fixed `change-metadata` operation completed
against the private production Site. Result checksum:
`sha256:fe112a1500899602db2a9585a38258b005b0052efaac0ee2bfdbec8c18d95276`.
The temporary result remained mode `0600`; no Site, endpoint, user, key,
secret, raw Script, business row or production write was recorded.

| Fact area | Sanitized accepted fact | Checksum | Compatibility consequence |
|---|---|---|---|
| Formal object identity | `Engineering Change Request` is present; `Engineering Change Order` and `Engineering Change Notice` are absent | DocTypes `sha256:65c4b0d03947d3c736cc2015d44523da1b118aff24b6d87ec4d0df34e3ab7c38` | Use the production ECR as the only formal change master. Do not create or emulate separate ECO/ECN masters in LaunchFlow |
| Formal numbering and lifecycle | ECR uses `ECR-.YYYY.-.#####`; it is not submittable and has one active Workflow over `status`: Draft, Impact Review, Pending Validation, Pending Approval, Approved, Implementing, Effective, Closed and Cancelled, with revision paths | Workflow list `sha256:144181dee8bd795452acc17868db30aa6a5c11e41dead24af1eb3d8f0bd3fded`; document `sha256:1e8b185ea69ee0e709470d03aa22e67eb30b34a73d32914f9668352ec87a07c5` | `DIRECT_MATCH` for formal ID/status/effectivity truth. LaunchFlow stores raw ERP status plus a versioned display map; it never drives the ERP Workflow directly |
| ECR mapping fields | 53 fields include customer, project, main Item, current/proposed Approval Form and version, reason/description, customer/TPR/sample/QIT/BOM/Item/process/packaging/supplier impact flags, impact rows, effectivity method/date/lot, customer approval reference, validation/implementation summaries and current/new baselines | DocFields `sha256:0a3e6d40cd2e9dd33ffca652508d854448d95423e6c1af45de3fd83d71ac29e4` | `DIRECT_MATCH` or `CONFIG_OR_MAPPING_ONLY`; keep NPI impact/version/task/evidence truth in LaunchFlow and map only explicit ERP-owned fields |
| Permissions | Five DocPerm rows: Manufacturing roles read only, Quality roles have the existing edit boundary, and System Manager has administration; there is no accepted dedicated integration role | DocPerm `sha256:1f278d73214aaa4ad6613ee2a1f6c3d41a1ab54781ffb43c7b57749a2d24ec8a` | Production activation remains held on a separate least-privilege operation-specific principal and owner/Sandbox approval; no permission widening in P9-01 |
| Declarative customization | No Custom Field, Custom DocPerm, Client Script, Server Script, Webhook, Notification or Document Naming Rule matches the exact three-name scope. One Property Setter selects a default print format; its value is retained only as a hash | Empty families `sha256:37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`; Property Setter `sha256:82ae76886c2c1f47179ed1f7b8d31ce37ad46db5cb28419cd450ff617109b60f` | No existing signed event or operation-specific API is proved. Implement only the approved default-disabled LaunchFlow seam; any ERP event/API addition is a separate minimal custom-app task |
| Audit and approval hardening | ECR `track_changes` is disabled and all accepted approval transitions allow self approval | Bound in the DocType and Workflow checksums above | Concrete production activation gap. Prefer configuration to enable change tracking and disable self approval; if configuration is insufficient, use one additive independent-app guard. Do not silently reinterpret this as LaunchFlow authority |

The accepted result is a compatibility delta, not a production configuration
approval. It proves no need to redesign LaunchFlow, rename current contracts,
make ERP and NPI dual masters or add a generic ERP writer. Status-option text
and operation-principal approval remain explicit Sandbox/owner inputs.

## P9-04 authorization compatibility delta

The fixed `security-metadata` operation completed at
`2026-09-03T07:07:46+07:00` after exact-SHA ordinary CI `33697388327`
passed on collector SHA `76d40c2aed74716943eeefabb1b4162e8ba994f9` (the single
historical P6-08 loading-state flake passed when its failed job was rerun at
the same SHA; no source or test changed). The aggregate sanitized result
checksum is
`sha256:0919d57016166b07899a3a0648ef975755413027e6e2d29606720308df84afb8`.
No identity, email, permission value, provider client identifier, endpoint,
secret, business row or production write was collected.

| Fact area | Sanitized accepted fact | Checksum / provenance | Compatibility consequence |
|---|---|---|---|
| Internal-user availability | 28 System Users: 21 enabled and 7 disabled | Aggregate counts in the accepted result envelope | ERPNext can own enabled/disabled internal-user truth. Stable Entra-to-Frappe identity matching remains an activation input because identities were intentionally excluded |
| Role Profiles | Six profiles cover Accounts, HR, Inventory, Manufacturing, Purchase and Sales role groups; no NPI-specific Role Profile was present | Bound by aggregate result checksum; family checksum prefix `9272abca` is retained only as a correlation hint, not an independent checksum claim | `CONFIG_OR_MAPPING_ONLY` for NPI role/profile creation if existing roles suffice; otherwise a separate minimal additive ERP custom-app/config task. LaunchFlow must not invent a default role |
| User Permissions | 14 aggregate rows: Company 7; Project 0; Customer 0; Supplier 0 | Aggregate-only fixed operations in the accepted envelope | Company scope has a reusable source family. Project/Customer/Supplier scope sources are not established, so production activation stays held until an owner-approved mapping or minimal additive source field exists |
| Federated login | Office 365 and Wework Social Login providers are enabled | Bound by aggregate result checksum; family checksum prefix `fa7410ea` is a correlation hint; non-secret provider metadata only | Office 365 is a `DIRECT_MATCH` for the approved Entra/Frappe session design. Provider-secret and tenant configuration remain outside Git and outside this read |
| Self signup | Disabled; source storage shape is `DIGIT_STRING` | Bound by aggregate result checksum; family checksum prefix `0764eea` is a correlation hint | `DIRECT_MATCH`, `NO_CHANGE`; unknown/unprovisioned users still require fail-closed local authorization projection enforcement |
| Operation-specific authorization projection | No accepted P8-07F source or P9-04 metadata fact proves an existing NPI-specific sender/API or least-privilege NPI Role Profile | P8-07F custom-app/runtime inventory plus this delta | Concrete smallest gap: LaunchFlow adds one default-disabled, versioned full-replacement projection ingress; ERP sender/role/scope configuration remains a separate minimal task and no production change is authorized here |

The abbreviated family prefixes above are correlation hints only; the exact
aggregate checksum binds the complete sanitized result. The production service actor,
identity match key, NPI role names, Project/Customer/Supplier source mapping,
delivery SLA and revocation/reconciliation schedule remain explicit
Sandbox/owner/activation inputs. They are not guessed and do not justify a
security-model redesign.

## Freshness and delta policy

The accepted Bench/Site checksums, HEAD/status table and tracked-path checksums
are the freshness baseline. This bounded collection is closed and its private
state removed. A future task must compare version/HEAD/status/path checksums
first and may read only changed necessary facts. Dirty applications remain
distinct from clean HEAD/release truth; their accepted exact tracked state may
be reused only while its version/mtime/hash remains fresh, otherwise the
affected fact is held until another bounded delta summary is accepted. Do not repeat full
discovery unless a version/checksum delta requires it. The standing
authorization removes the need for another user prompt; it does not remove the
fail-closed checks or grant write authority.

## No-change boundary

- No production ERPNext or Frappe state was changed.
- No ERPNext/Frappe core change is proposed.
- No browser-to-ERP connection, generic DocType writer, cross-database access,
  dual-master field or Mock/HTTP fake success is permitted.
- No LaunchFlow contract, ownership, domain or UI redesign is justified by
  this inventory; only explicit configuration/mapping work may proceed inside
  its existing atomic task.
- M9-04 and M9-05 real-project pilots remain user-approved post-V1.2 deferrals;
  controlled non-production UAT is not a real-pilot or adoption claim.

## Open risks and stop condition

P8-07F compatibility evidence is complete for the bounded pre-P8-08 Gate.
Production activation remains separately held on service-principal, owner,
Sandbox/UAT, deployment and the explicit unknowns above. Permission
insufficiency, version/shape drift, sensitive-output risk, allowlist drift or a
write need still stops the affected part without privilege expansion. A
concrete contract/ownership conflict must be recorded as an ADR or business
decision before any implementation task.
