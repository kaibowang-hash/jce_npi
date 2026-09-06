# P8-05 Validation — Tool Asset Execution

Status: **PASS — LEVEL 3**

Validated exact product SHA:
`f9c358018823f3af20aca38efb53f8fcbd13d406`

Requirements: `INT-005`, `FR-TL-011`, `FR-TL-012`, `FR-TL-013`,
`FR-TL-014`, `FR-TL-015`, `FR-TL-016`

## Release disposition

P8-05 technically verifies the bounded Tool Asset execution foundation only.
It preserves one physical Tooling Set to zero-or-one formal ERP Asset,
separate `create_tool_asset` and `update_tool_asset` operations, immutable
request/Outbox/attempt/result truth, exact mapping compare-and-set, and
read-only observed Asset/location/maintenance truth. NPI acceptance evidence
remains separate from business approval, ERP approval and target success.

Production ERPNext/JCE traffic, an authenticated Sandbox adapter, current
ERPNext Asset method and field mapping, naming/category/company/location/
maintenance rules, business-approval source and formal production mapping
remain held. This validation does not mark the full production requirements
complete.

## Exact-SHA ordinary CI

Workflow `32937395289` passed at the exact validated SHA:

- frontend: `98081218670`;
- repository: `98081218777`;
- governed visual: `98081218786`;
- secret scan: `98081218842`.

The ordinary workflow changed no controlled-Site state and introduced no
diagnostic activation.

## Final Level 3

Workflow `32938622250` passed once at the same exact SHA while reusing ordinary
run `32937395289`:

- repository: `98084790776`;
- frontend: `98084790857`;
- secret scan: `98084790876`;
- governed visual: `98084790917`;
- controlled preflight: `98087726984`;
- cumulative controlled runtime: `98087768879`.

The controlled runtime used scope `p5-01-through-p8-05`, predecessor scope
`p5-01-through-p8-04`, Frappe commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1`, and the disposable
`bash scripts/verify-frappe-runtime.sh --projection-only` path. It completed
with zero production ERPNext/JCE traffic and successful cleanup.

## Artifacts

| Artifact | ID | SHA-256 | Size |
|---|---:|---|---:|
| controlled runtime | `9596248305` | `11554463405c3165891e23bbd522e9c6093ef00f95d34d221d182efebfea8c41` | 480 bytes |
| governed visual | `9595833757` | `0a9712c3bf082a52a59ac04344a6e1ba2837ae831bf15994745b8950a06dd9b8` | 15,165,988 bytes |
| Gitleaks | `9595725822` | `25e68fa800f44f5927120e472245707ee1abb5e6fc6b453d165a4fdbd7de5f58` | 6,760 bytes |

## Domain and integration proof

- ERPNext retains formal Asset identity, lifecycle, version, location,
  movement, maintenance, repair, spare, inventory and cost ownership.
- NPI One retains Tooling development/revision/acceptance evidence and the
  request, Outbox, attempt, result, audit and read-only association truth.
- Project, tenant, actor, permission, trace, idempotency, operation, profile,
  approval and secondary containment are server-resolved and fail closed.
- Create requires an exact unmapped expectation. Update requires an exact
  current mapping and target version. Partial or uncertain results never
  advance the mapping head.
- Request, idempotency, Outbox, audit and receipt commit atomically before the
  enqueue boundary. Replay and terminal truth never blindly redispatch.
- Default profiles are empty. Mock and network-free Synthetic evidence create
  no formal Asset ID, mapping or authoritative target success.
- The P8-01 projection remains the only read-only Asset status/location/
  maintenance owner. P8-05 does not rewrite projection truth.

## API, schema, migration and rollback

The fixed Project-first list/detail and operation-specific create/update API
surfaces have closed input, CSRF, idempotency and permission contracts. Tool
Asset request/result event payloads are additive and versioned; the shared
Outbox schema-3 Tool Asset branch retains earlier Item, MBOM and legacy rows.
Support DocTypes are additive and install no fixture/profile/endpoint/
credential/business-approval row.

Rollback before an adapter boundary disables the v2 routes, enqueue and worker
while retaining committed request, idempotency, Outbox and audit truth for
forward migration. After a boundary, new commands and claims are disabled and
all request/event/lease/attempt/result/uncertain/observation/mapping/audit
truth is retained for reviewed forward repair. Rollback never deletes or
blindly redispatches, rewrites partial/failed truth to success, changes a
formal Asset ID, mutates Tooling/acceptance/P8-01 projection truth or performs
movement, maintenance, repair or automatic target compensation.

## Permission and security proof

- Exact Project authorization precedes business parsing and every secondary
  identity is contained in the authorized Project.
- Capability-bound Frappe support writes are narrowly authorized; product
  repositories contain no unrestricted `ignore_permissions` path.
- Product scans find no direct SQL, cross-database access, target-network
  client, production endpoint/credential seam or core Frappe/ERPNext patch.
- Gitleaks and repository secret boundaries pass.
- Every Item, MBOM, P6-06 and Tool Asset diagnostic activation is `False` in
  the final exact SHA.

## UI, accessibility and localization

The existing Tooling acceptance/Asset workspace contains one compact square,
neutral execution inspector and at most one visible-text primary Impact Review
action. It separates acceptance evidence from unavailable business approval,
withholds formal identity unless authenticated authoritative evidence,
permission, exact current mapping and fresh permitted projection all agree,
and exposes no retry, reconcile, submit or ERP approval control.

Loading, empty, unavailable, no-permission, read-only, conflict, queued,
processing, Mock, Synthetic, partial, failed, uncertain and authoritative
states pass keyboard, focus, non-color, accessibility, responsive and browser
target-network-zero checks. Frontend evidence passes `1,060/1,060` unit tests
and `454/454` nonvisual E2E cases.

The V1.2 DOCX requirements and the established catalog uniquely establish
Tool Asset as `模具资产` / `模具資產`. The terminology allowlist, direct
catalogs, generated catalog and regression test agree; user-visible/generated
sources contain zero `工装资产` / `工裝資產` alternation. The i18n audit
covers `8,341` literal English sources with complete direct zh and zh-TW
coverage.

The governed Bookworm/amd64 visual matrix passes `129/129`. The four affected
canonical Chinese images were reviewed as text-only changes:

- P8-05 partial zh:
  `edaa671ab3b5979a6965877dc955a0c495b773c16957191be712b079fd3fb6da`;
- P8-05 authoritative zh-TW:
  `0ead4911f3714ef9843d10a75efa14c712b3ca98b3887ebabd9581379cecff21`;
- P6-06 zh composition:
  `5fa065d0aea158149ce3d0c82c760d531adbbf73b7291acacdf0802fd3c9793c`;
- P6-06 zh-TW composition:
  `53c9ebb99c4d26726d6b341c49d5c9f06d1547d3b81c14a3ea43ffb1da986f66`.

The English P8-05 Synthetic baseline remains unchanged at
`c3f5117bec0297d7dad20349760a9c5bee3b8b0fd0665be6ad15fdec8b7575f7`.

## Scope limitations and next task

No approved production or Sandbox Asset operation, current ERPNext method/
field/location/maintenance mapping, business approval source or target
credential is installed. Generic retry, replay, DLQ and reconciliation remain
P8-07. P8-06 is activated only as an audit of read-only formal Quality
Inspection/NCR/CAPA linkage for `INT-007`, `FR-TR-006` and `FR-NP-006`;
P8-06 product code remains unauthorized until its separately frozen audit plan
passes exact-SHA ordinary CI.
