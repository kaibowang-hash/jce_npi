# P8-07F Plan — Production ERPNext Compatibility Reconciliation

Date: `2026-08-30`

Controller tasks: `P8-07F-GOVERNANCE` then `P8-07F-FACTS`

Status: **EXPANDED COLLECTOR ACTIVATION AWAITS EXACT-SHA ORDINARY; P8-08 HELD**

## Purpose and baseline

P8-07F is a mandatory Phase 8 atomic bridge after P8-07 and before P8-08. Its
purpose is to understand and record the already-approved LaunchFlow ERPNext
integration, collect only the production facts needed to compare it with the
real installation, and decide whether the existing design is directly
compatible. The current architecture, data ownership, OpenAPI/event contracts
and P8-01 through P8-09 design/code are presumed correct.

This task is not a redesign, refactor, rebuild or implementation task. It must
not rename interfaces, merge or split domain objects, redo workflows, replace
the stack, rewrite permissions or introduce generalized abstractions. A
product/custom-app adjustment may be proposed only for one concrete,
proven incompatibility and must be implemented later as a separate minimal,
reversible atomic task.

## Two-Gate activation

1. `P8-07F-GOVERNANCE` records the user's 2026-08-29 scope and standing
   authorization, exact allowlist, redaction, provenance, stop conditions,
   rollback and release Gate. It performs zero SSH or ERP contact.
2. Only after the transition's exact-SHA ordinary CI and Level 3 both PASS may
   the controller activate `P8-07F-FACTS` with a separate exact manifest.
3. Only the active facts task may invoke SSH alias `JCE-Core`. It performs no
   product change, production write, replay, reconciliation action or ERP
   customization.
4. P8-08 remains inactive until the facts task, documentation, trace review
   and its applicable exact-SHA Gate all PASS or explicitly hold every unknown.

The governance checkpoint is
`d919d695972260fa86d5df7fa60033e6adb62f49`. Its ordinary CI `33279778063`
passes repository `99172860297`, frontend `99172860137`, secret
`99172860343` and visual `99172860279`; Level 3 `33280319184` passes those
four lanes plus preflight `99175743503` and cumulative runtime `99175763495`.
The transition made zero production contact. The separate facts activation
adds `scripts/collect_erpnext_production_facts.py`; no collector call is allowed
until that activation's own exact-SHA ordinary CI passes.

The activation exact SHA
`c8d3b3c0e9fd3f8d92a1679713ef8afc0157ff20` passes ordinary CI
`33281944546` (secret `99178460514`, repository `99178460580`, visual
`99178460608`, frontend `99178460653`). `ERP_VERSION` operations were attempted
at `2026-08-30T00:04:24Z` and, after a user-requested connection check, at
`2026-08-30T05:35:04Z` through the frozen transport. Both produced no accepted
output, so each collector invocation stopped without a later operation. No
private state file was created. Production versions,
apps, metadata, code and configuration therefore remain `UNVERIFIED`; P8-08 is
held and no product adjustment is authorized.

The subsequent fixed-root, status-token and NUL-framing repairs passed their
own exact-SHA ordinary CIs. At the final bounded epoch, Frappe `15.79.0`,
ERPNext `15.77.0`, twenty installed apps, all anonymous HEAD/status rows and all
twenty tracked-path inventories were accepted. Six clean custom apps yielded
bounded source summaries. ERPNext plus twelve custom apps have tracked drift;
two relevant DocType candidates stopped at sensitive-content preflight; and
runtime-only metadata remains outside this plan's source-only operations. The
private state was deleted and the collection window is closed.

## Fixed transport contract

Every connection must use the repository-governed launcher or an exact argv
equivalent with SSH alias `JCE-Core`, `BatchMode=yes`, `RequestTTY=no`,
`StrictHostKeyChecking=yes`, `ForwardAgent=no`, `ClearAllForwardings=yes`,
`ConnectionAttempts=1`, a short connect timeout and a bounded whole-command
timeout. No TTY, agent/port/X11 forwarding, interactive prompt, multiplexed
control master, fallback host, endpoint discovery or host-key acceptance is
allowed. All seven operations execute through the single fixed literal wrapper
`cd frappe-bench && exec <allowlisted-command>`. `frappe-bench` is the
user-confirmed relative root; it is not configurable at runtime. Alias
resolution and endpoint/user/key values remain outside Git and must never
appear in evidence.

## Remote operation allowlist

The facts manifest may activate only the following operation IDs and exact
argument shapes. All runtime path/site/app parameters are locally validated,
kept outside Git and represented in committed evidence only by a neutral label
and checksum. Apart from the fixed source wrapper documented above, dynamic
shell metacharacters, command substitution, pipelines, redirects and arbitrary
inline source are prohibited.

| Operation ID | Exact read-only purpose | Bounded output |
|---|---|---|
| `ERP_VERSION` | `bench version` | version rows only |
| `INSTALLED_APPS` | `bench --site <runtime-site> list-apps` | app/version rows only |
| `APP_HEAD` | `git -C <validated-custom-app-root> rev-parse HEAD` | one 40-character SHA |
| `APP_STATUS` | `git -C <validated-custom-app-root> status --short -uno` | bounded tracked-drift summary |
| `APP_TRACKED_PATHS` | `git -C <validated-custom-app-root> ls-files -z` | deterministic NUL-framed path inventory |
| `APP_FILE_HASH` | `git -C <validated-custom-app-root> hash-object -- <allowlisted-tracked-path>` | one object hash |
| `APP_FILE_READ` | `git -C <validated-custom-app-root> show HEAD:<allowlisted-tracked-path>` | one bounded tracked source/metadata file after local sensitive-content preflight |

The wrapper's `cd`, `&&` and `exec` tokens are fixed source literals. Dynamic
shell metacharacters, command substitution, pipelines, redirects, arbitrary
inline source and runtime Bench-root overrides remain prohibited. Every
dynamic operation token is independently allowlisted before SSH.

`APP_FILE_READ` is limited to tracked custom-app source and declarative
metadata needed for hooks, overrides, patches, fixtures, modules, DocTypes,
whitelisted methods, jobs, APIs, reports, prints, notifications, webhooks and
workspaces. It excludes every config/secrets path, private file, log, backup,
database, environment file, credential, cookie, token/key material and business
record export. If runtime Custom Fields, Property Setters, Scripts, Workflows,
roles/permissions, service scopes or Naming Series are not represented by
allowlisted tracked metadata or an already-installed side-effect-free
operation-specific read API, they remain `UNVERIFIED`; the task must not use
console, direct SQL, export-fixtures or an improvised method to obtain them.

The fixed-root harness repair exact fourteen passes at
`9ab9bd5199e5521f3a72e701c3fa4338d6e866db` / ordinary `33295753975`, and its
bounded discovery is accepted. The next exact-fifteen repair reuses inventory,
active goal, controller, blockers, current task, next action, phase status,
required inputs, risk register, this plan, validation evidence, collector,
collector test, current-task test and the reconciliation verifier's exact
accepted-inventory assertions. It changes only the fixed status token
from the locally rejected equals-form to equivalent `-uno`; no product,
contract, schema, ownership, frontend, workflow, operation or output authority
changes. Exact-SHA ordinary CI is mandatory before application reads resume.

The fixed-status-token repair passes at
`be03972abd13b60284a8f950eae7cdf7776781d7` / ordinary `33296694027`.
Complete anonymized HEAD/status inventory is accepted; Frappe is clean,
ERPNext has one tracked drift and twelve of eighteen custom apps have tracked
drift. The line-framed tracked-path parser then stopped on one legitimate
`CUSTOM_APP_03` path after accepting bounded structures for the first two
custom apps. The exact-fourteen repair changed only that command to
`git ls-files -z`, permits NUL bytes only for this operation and validates
ordered unique UTF-8 printable non-traversing paths. File operations retain
their stricter path gate. It passed at `acbd6882` / ordinary `33297909199`
before the final bounded reads described above.

## Fail-closed and redaction contract

Before each operation record task ID, purpose, UTC/local timezone timestamp,
operation ID, expected shape and inventory freshness decision. Validate shape
and size before accepting output. Redact before persistence, then record only a
neutral source label, version/mtime/hash/checksum, finding, unknown and impact.
Never commit endpoint, host, user, key, secret, business-sensitive value or raw
record. Permission failure, unexpected version, unknown shape, possible secret,
allowlist/path drift, excessive output or need for a write immediately stops
that fact area without privilege expansion.

Forbidden operations include `sudo`; any file/database write; core, config,
permission, service or queue change; migrate, update, restart, reload,
clear-cache, scheduler or console; DocType mutation; webhook/job/adapter/target
command; replay or reconciliation action; and collection of site configuration,
credentials, cookies, tokens, private keys or unrelated business rows.

## Fact and compatibility scope

The inventory must cover, to the extent safely observable: exact Frappe/
ERPNext versions, installed apps, non-sensitive topology/locale/storage facts;
independent custom apps and their source/hooks/overrides/patches/fixtures/
DocTypes/APIs/jobs/reports/prints/notifications/webhooks/workspaces; represented
custom fields/property setters/scripts/workflows/roles/permissions/service
scopes/naming; file policy; and necessary metadata/count/sanitized relationship
samples for Customer, Supplier, Project, Item, EBOM/MBOM, PO/cost, Quality/
NCR/CAPA, Asset/maintenance/movement/repair/spares and current contract objects.
Unknown runtime-only facts remain explicit rather than guessed.

The reconciliation covers P8-01 through P8-09: read-only projections; signed
webhook/Inbox/ERP-source Project draft; Item and MBOM publish; Tool Asset
create/update/status projection; formal quality links; operations/DLQ/replay/
reconciliation; Released Trial Summary projection/adapter seam; and JCE Core
display identity while the internal system code remains `ERPNEXT`.

## Required facts-task deliverables

- Update `docs/ERPNEXT_CUSTOMIZATION_REQUIREMENTS.md` from blocked facts to
  `Required`, `Optional`, `Already Present`, `Not Required` or still unknown,
  retaining provenance.
- Add `docs/ERPNEXT_PRODUCTION_FACT_INVENTORY.md` with only sanitized metadata,
  versions, sources, checksums, unknowns and risks.
- Add `docs/LAUNCHFLOW_ERPNEXT_INTEGRATION_BLUEPRINT.md` as the executable
  compatibility/minimal-adjustment matrix.
- Add a gap/decision register. Any contract, ownership, API, workflow or
  architecture conflict stops affected implementation and requests ADR/business
  decision; the facts task does not silently adapt or alter product code.
- Update `REQUIRED_INPUTS`, roadmap/DoD/controller/phase/trace/risk/decision
  evidence without weakening existing holds.

Each comparison row states current LaunchFlow behavior, actual ERP object/
field/state/method/permission, evidence and one result:
`DIRECT_MATCH`, `CONFIG_OR_MAPPING_ONLY`, `MINOR_LAUNCHFLOW_ADJUSTMENT`,
`MINOR_ERPNEXT_CUSTOM_APP_ADJUSTMENT`, `BUSINESS_DECISION_REQUIRED` or
`NOT_APPLICABLE`. `DIRECT_MATCH` must explicitly say `NO_CHANGE`. Any proposed
adjustment must name the single proven difference, minimal files/field/config,
tests, rollback and why configuration alone cannot solve it.

The blueprint retains exact direction, trigger, version, idempotency, actor,
trace/hash, Inbox/Outbox/webhook, retry/replay/reconciliation, permission/audit,
normal/fault/timeout-after-commit/partial/stale/conflict tests, rollout,
Sandbox/UAT, monitoring, rollback/forward-fix, owner, status and evidence. It
also freezes the no-change list: no ERPNext/Frappe core change, browser-to-ERP
access, generic DocType writer, dual-master field or Mock/HTTP fake success.

## Persistent authorization and final Gate

After P8-07F's two Gates, later ERP-dependent atomic tasks may reuse this
read-only boundary without asking again. They must check inventory freshness
first and prefer version/mtime/hash deltas to full collection. Each invocation
records its task-scoped provenance and impact; any drift or missing fact stops
only the affected implementation.

Before final implementation/release closeout, run one complete production
ERPNext↔LaunchFlow read-only compatibility reconciliation over all accepted
facts and all ERP-related features. Each row is `STILL_MATCHES`,
`PRODUCTION_DRIFT`, `LAUNCHFLOW_DRIFT`, `BOTH_DRIFTED` or `UNVERIFIED`, with
evidence/checksum/owner/impact/remediation. Unresolved drift or unverified
required dependency blocks `IMPLEMENTATION_COMPLETE` and production-ready.
Actual ERP customization, migration or production change always requires a
separate approved task.

## Rollback

Before any connection, rollback is deletion/reversion of this governance
activation while retaining P8-07 evidence. After a read-only operation, stop
all further operations, retain only already-redacted provenance and mark
affected facts stale/unverified. Because no remote mutation is authorized,
there is no production rollback command. Any later implementation uses its own
reviewed rollback or forward-fix plan.

## Closed read and recovery evidence

The bounded read at `cfd093055` is closed and its accepted facts remain
immutable. On 2026-08-30 the user authorized current tracked worktree source,
read-only structural summaries for the two stopped DocType candidates and
fixed application-layer runtime metadata collection. This supersedes the need
for an immediate owner-supplied bundle, but not the Gate sequence.

Do not resume SSH in the governance transition. First obtain its exact-SHA
ordinary CI and Level 3; then implement the expanded source/runtime operations
under a separate facts activation and obtain its exact-SHA ordinary CI.
Reconciliation must reuse version/HEAD/status/path checksums first, distinguish
HEAD from current worktree, preserve only redacted structure/checksums and
retain direct SQL, console, generic method/query and all writes as prohibited.
Until those Gates pass and the facts are accepted, no `DIRECT_MATCH`,
adjustment task, facts-task Level 3 or P8-08 activation is allowed.

## 2026-08-30 expanded collector activation

The zero-contact current-worktree/runtime-metadata transition is now accepted
at exact SHA `fccf62feaba2d3ed092efcd06174f16f66193540`, ordinary CI
`33304191319` and Level 3 `33304710306`. All six Level 3 jobs pass. The separate
`P8-07F-FACTS` activation must still obtain its own exact-SHA ordinary CI before
reconnecting to production.

The expanded source operations add safe tracked-file mode, immutable HEAD
object, current worktree Git object and a bounded `--no-ext-diff --no-renames`
single-file delta. Reconstruction occurs only in private local memory and must
match both Git objects. Symlinks, binary or multi-file patches, path/mode/
rename/copy/delete drift, malformed or truncated hunks and excessive bytes
stop the affected read. Only structural summaries and checksums are accepted.

Runtime collection uses one fixed Frappe application-layer method,
`frappe.client.get_list`. Each operation family hardcodes its DocType, safe
field list, filters, `name asc` ordering, 200-row page size and 25-page maximum.
Families cover Custom Fields, Property Setters, Workflow structure, roles and
DocPerm structure, Client/Server Script structure with script text hashed,
required DocType/DocField/DocPerm structure, Webhooks, Scheduled Jobs, Reports,
Print Formats, Notifications and Document Naming Rules. No caller can select a
method, DocType, field, filter, order or page. Direct SQL, console, arbitrary
execute, business rows, raw source/Script/path persistence and all writes remain
prohibited.

Before using this activation for production, retain path identities entirely
inside the mode-0600 state. `APP_TRACKED_PATHS` may emit only private-cache
index, structural category and path checksum. HEAD/current file reads select
that cached index and emit only its checksum plus structural summary; the raw
path is neither a CLI argument nor an accepted result.

Activation SHA `c879fbce7a19edf4006d781a24cf710662edf37b` passes ordinary CI
`33306873040` (frontend `99244887012`, repository `99244887120`, secret
`99244887145`, visual `99244887178`). Its first expanded collection window
accepts the unchanged Frappe `15.79.0` / ERPNext `15.77.0` and twenty-app
inventory, the Site app-set checksum, all anonymous HEAD/status rows and all
tracked-path inventories. Frappe is clean, ERPNext has one tracked change, and
twelve of eighteen custom apps have tracked changes. The current-worktree
authority remains active for those tracked paths.

The same window rejects direct `DocField`, `DocPerm` and Workflow child-table
reads at the application permission boundary and rejects several valid parent
families because database collation order differs from Python raw lexical
order. It records no rejected rows and deletes the private state. A bounded
collector compatibility repair is required before reconnecting: preserve the
fixed database `name asc` query and duplicate/page ceilings without imposing a
second local collation; read children only through fixed `frappe.client.get`
parent documents for the fifteen frozen ERP DocTypes and parent names obtained
from the already-fixed Workflow/Naming Rule families; and allow the two
user-authorized DocType JSON files to reach the structural JSON summarizer.
Raw parent documents, source, paths, Script text and sensitive values remain
memory-only and unaccepted; direct SQL, console, arbitrary execute and every
write remain prohibited.

## 2026-08-30 accepted initial collection and remaining fixed reads

Parent/current-source collector repair SHA
`085e9124328afdb13668de452cd8cba21e282c28` passes ordinary CI
`33307715636`. The next bounded production window accepts the current tracked
worktree as source truth, including authorized uncommitted tracked changes,
and structurally summarizes the two formerly protected DocType candidates.
It also accepts sanitized/checksummed Custom Field, Property Setter,
Workflow/state/transition, role, permission, Server Script, Webhook,
scheduled-job, report, print, notification and naming-rule evidence. The
private state is removed at window close.

Before the final remaining read, the collector must obtain another exact-SHA
ordinary PASS with four fail-closed fixes: use the actual Frappe v15 Client
Script field set and hash its Script; hash protected multiline DocType JSON
scalars; freeze the expanded P8-relevant quality/DMR/mold DocType parent set;
and query only exact System Settings locale fields plus aggregate File URL
shapes through hard-coded `frappe.client.get_value`/`get_count` operations.
No direct SQL, console or generic method is needed or allowed. After that Gate,
collect only the missing families, delete private state and proceed to the
compatibility/minimal-adjustment reconciliation; P8-08 remains held.

## Bounded Client Script paging correction

SHA `573fdd4b61fae2d968933272bd9f9f3e87b2b8c0` passes ordinary CI
`33309768019`, then verifies the unchanged accepted inventory. Its first
remaining Client Script query fails closed because a 200-row page containing
Script bodies exceeds the fixed per-call byte budget. No row is accepted, no
later family is queried and the local private state is deleted.

Do not increase that budget. Fix only Client Script to 20 rows per page under
the existing 25-page ceiling, retaining exact fields, filters, order,
checksum-only Script representation and duplicate/page checks. Obtain a new
exact-SHA ordinary before reconnecting; direct SQL, console and generic method
surfaces remain unnecessary and prohibited.
