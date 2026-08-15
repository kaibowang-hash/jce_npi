# P8-00 Validation — Phase 8 ERPNext Reliable Integration Anchor

Validated: `2026-08-15T18:47:39Z`

Branch: `codex/npi-v1.2-implementation`

Retained predecessor product checkpoint:
`31114021cf18cf5e32c22902de5150ed2922e7ba`

Exact anchor/controller checkpoint:
`1da93f4d21dd434c99cfdc778ac1e63c4668d114`

Exact ordinary CI: `31901621310` (`PASS`)

Result: **PASS — LEVEL 2 DOCUMENTATION/TRACE TASK GATE**

## Scope and non-scope

P8-00 allocates the approved Phase 8 integration scope to P8-01 through
P8-09 and freezes the reliable-integration safety boundary before product
code. It records ERPNext field ownership, stable technical system codes,
operation-specific request/result contracts, signed webhook and durable Inbox
rules, Outbox/attempt/result truth, retry/replay/reconciliation semantics,
Mock/sandbox modes, environment rejection, fault cases and forward rollback.

It creates no Python or TypeScript product behavior, route, DocType, Schema,
migration, worker, webhook, adapter, projection, UI, translation or external
message. It installs no endpoint, credential, target mapping or production
policy and contacts no ERPNext/JCE system. Anchored statuses mean allocation,
not implementation, sandbox verification, target acceptance or production
readiness.

## Requirement allocation

| Requirement set | Primary task or truthful hold |
|---|---|
| INT-001, INT-006, INT-007 read-only foundation, INT-010, FR-PM-010 | P8-01 |
| INT-002, FR-PM-002 | P8-02 |
| INT-003; FR-DS-013 carried foundation | P8-03 |
| INT-004; FR-DS-013 carried foundation | P8-04 |
| INT-005; FR-TL-011..016 carried foundations | P8-05 |
| INT-007 quality-linkage slice; FR-TR-006 and FR-NP-006 carried foundations | P8-06, retaining the P8-01 read-only projection as predecessor truth |
| FR-RP-009, NFR-INT-001; UX-016 carried foundation | P8-07 |
| FR-INT-015 carried NPI summary-source foundation | P8-08 |
| FR-BR-002 | P8-09 |
| INT-008 | Phase 9 Change-domain hold |
| INT-009, INT-011, INT-012, INT-013 | Explicit consumer/mapping/provider scoped holds |
| INT-014 | Phase 9 reporting/BI hold |

Carried Phase 5/6/7 foundations retain their prior truthful technical status
and gain only the P8-00 allocation evidence. No existing technical foundation
is relabelled as an authenticated ERP observation or execution result.

## Frozen integration truth

- ERPNext remains formal owner of customer/supplier master, formal Item and
  MBOM/routing, purchasing/inventory/production, formal quality, Asset and
  financial truth. NPI One retains engineering collaboration and immutable
  source authority declared by the ownership contract.
- Browsers call only the NPI BFF. No cross-database access, generic target
  DocType write, caller-selected target method or Frappe/ERPNext core patch is
  allowed.
- Approval, queued request, transport acceptance, timeout and Mock completion
  are not target business success. Only an authenticated observed target result
  may create a target mapping or `succeeded` truth.
- Webhooks verify algorithm/key/signature/timestamp/replay window and raw-body
  hash before durable landing. Duplicate, hash-conflict, reorder and restart
  behavior remains explicit and asynchronous.
- Retries are failure-classified. A possible target commit after timeout is
  uncertain and reconciled before redispatch. Replay retains the immutable
  request and creates an audited attempt; reconciliation is forward-only.
- `mock` is the default and emits no formal target identity or confirmation.
  `sandbox` is explicit, operation-scoped and allowlisted. Production hosts,
  credentials, data and traffic are rejected.
- `NPI_ONE` and `ERPNEXT` remain stable internal codes. `JCE Core` and the
  approved Core asset are presentation-only P8-09 facts.

## Existing-capability conclusion

The repository contains reusable reliability primitives, guarded Inbox/Outbox
metadata, Mock-only EBOM and Tool Asset request foundations, read-only or
unavailable ERP-owned fields, and one immutable Released Trial Summary source.
It does not yet contain the complete durable signed webhook, target-observed
projection, operation worker, sandbox adapter, DLQ/replay/reconciliation job
center, approved Trial Summary external contract or JCE Core display adapter.
Those missing capabilities remain assigned to their exact atomic tasks and
cannot be inferred from the anchor.

## Exact-SHA verification

The exact checkpoint `1da93f4d21dd434c99cfdc778ac1e63c4668d114`
passed ordinary pull-request CI `31901621310`:

- repository job `95053171972`: `1,922/1,922` tracked Python tests,
  current-task and canonical reconciliation checks PASS;
- frontend job `95053172010`: generation, type, lint, `59/59` test files and
  `918/918` unit tests PASS; coverage is statements `80.31%`, branches
  `80.16%`, functions `82.81%`, lines `82.96%`; `7,471` literal English
  sources have direct `100%` `zh` and `100%` `zh-TW` coverage; build,
  install-script policy and both zero-vulnerability audits PASS; and
  `421/421` browser E2E tests PASS;
- secret job `95053172009`: current-task verification, current-tree Gitleaks
  and complete pull-request branch-history scan PASS; and
- visual job `95053172077`: the governed fixed-Linux matrix passes
  `119/119` and uploads artifact `9251286410` with digest
  `sha256:970524654b68f57fc023c54ef3520cb000838dd74a7ea728a495bce7a8834b6c`.

Gitleaks artifact `9251237713` has digest
`sha256:73a6d5203457ecadea0c7673392e56292f707652a2eb81e0281e702c4f44e820`.
Controlled preflight/runtime jobs correctly skip for this documentation-only
ordinary pull-request Gate. A separate local clean-worktree run with the exact
Node `24.18.0`, npm `11.16.0` and `npm ci --strict-allow-scripts` also passed
the complete repository/frontend verification with zero vulnerabilities and
no unreviewed install scripts.

## Migration and rollback

P8-00 has no runtime, data or external migration. Reverting its controller and
trace evidence before P8 product work would restore the unanchored Phase 8
state while preserving the sealed Phase 7 evidence. Once future integration
history exists, rollback follows endpoint/worker/route disable plus reviewed
forward repair; it never deletes Inbox/Outbox/request/attempt/result/audit
history, rewrites observed target truth or blindly redispatches an uncertain
operation.

## Exit

P8-00 passes. P8-01 is the sole active atomic task and begins with a bounded
Requirement/domain/existing-capability audit of read-only ERP-owned master and
status projections. No product mutation occurs until that audit freezes exact
projection identities, ordering/staleness/unavailable states, adapter modes,
fault tests, metadata/migration and rollback. Production ERPNext remains
prohibited.
