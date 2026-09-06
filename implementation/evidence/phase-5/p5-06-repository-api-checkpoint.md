# P5-06 Repository, Render and API Checkpoint

Recorded: `2026-08-07T03:28:43Z`

Status:
`PASS — LEVEL 1 REPOSITORY, RETAINED RENDER AND CLOSED API`

Requirements:
`FR-PRN-001`, `FR-PRN-002`

Exact stable checkpoint:
`10963ddaa535f3fd335ca30031b3039b1da398c6`

## Delivered boundary

- Added an exact Frappe controlled-print repository that reuses the proven
  Project tenant/member authorization boundary before resolving any protected
  source, mapping, snapshot, output or File truth.
- Added a closed server-owned source-adapter registry. No browser-supplied
  DocType, method, template, source payload, actor, watermark, copy state,
  output identity or private File URL is accepted.
- Exact mapping resolution requires one enabled published mapping matching the
  tenant, source object type, Project type, optional Gate key, source state,
  language, retained-PDF delivery and copy-control state. Missing, ambiguous,
  stale or hash-drifted mappings fail closed; there is no Frappe Standard,
  latest-version or language fallback.
- The create transaction locks and reauthorizes the Project, binds the actor,
  Project, operation and canonical payload to one idempotency receipt, freezes
  the exact source and template, renders once, and persists the snapshot,
  private local File, immutable output, CREATED access event, audit and sealed
  receipt in the governed order.
- Replays return the sealed original result. Detail and content independently
  reauthorize the current Project and exact frozen printer authority. Content
  verifies the retained File identity, attachment, byte length, Frappe hash
  and SHA-256, returns the same retained bytes, and appends a DOWNLOADED access
  event/audit without source resolution or rerendering.
- Added the independent strict-boolean `npi_p5_06_routes_disabled` recovery
  switch and closed BFF capability/create/detail/content routes. Create
  requires the NPI API role, internal principal, CSRF and idempotency; all
  responses are private/no-store and URL-free.

## Deliberately unavailable

- The production source-adapter registry remains empty. No production Print
  Format, enabled mapping, exact form, signer, copy-number policy, retention
  policy, browser/device print or production default is installed.
- No ERPNext endpoint, credential or dispatch is present. No external QR or
  rendering service and no production dependency was added.
- The generic foundation does not satisfy `FR-PRN-003`; exact production form
  coverage and policy remain decision-held under `DR-REC-003` and
  `DR-REC-004` for P5-07.

## Requirement -> code -> proof

| Requirement | Code boundary | Direct proof |
|---|---|---|
| `FR-PRN-001` exact registry/capability selection | `controlled_print/frappe_repository.py`; `controlled_print_api.py`; BFF route table | exact/absent/ambiguous/drift/authority/route-disable tests |
| `FR-PRN-002` immutable source/template/output | repository transaction, renderer/QR foundation and retained content path | one-time render, source/template drift, private File identity/hash and retained-byte tests |
| `FR-PRN-002` actor-bound replay and audit | canonical payload/receipt helpers, create transaction and access append | replay/conflict, write-order, rollback and download-audit tests |

## Local affected and regression evidence

- focused P5-06 domain/contract/repository/API/transaction group: `56/56`
  PASS;
- complete tracked Python regression: `1,070/1,070` PASS;
- Python compilation, V1.2 reconciliation, prototype approval and P0 visual
  governance: PASS;
- generated catalog/i18n audit: PASS at `3,857` literal English sources with
  direct `100%` `zh` and `100%` `zh-TW` coverage;
- prohibited backend-pattern scan and `git diff --check`: PASS; and
- transaction-level fake-Frappe proof confirms exact write order, rollback
  cleanup registration and retained-byte reuse.

## Intermediate evidence and bounded repairs

- `e011cf0` preserved the established field-error response contract without
  changing the public controlled-print schema or business semantics.
- `fae7d63` added the deterministic repository-owned verification SVG and
  frozen-template PDF render foundation. Ordinary CI `31141683402` passed all
  product checks and isolated only the expected durable P0 catalog
  fingerprints.
- `46ceca1` synchronized only those exact reviewed fixed-Linux fingerprint
  bytes. No threshold, assertion, matrix member or PASS rule changed.
- `daea419` closed capability resolution. Ordinary CI `31142196974` passed
  repository `92754280885`, visual `92754280805` at `65/65`, complete E2E and
  both secret lanes; controlled runtime correctly skipped.
- `10963dd` then added the retained-output repository and complete closed API
  transaction without changing catalog or governed UI pixels.

## Exact-SHA ordinary CI

Ordinary pull-request CI `31144008180` passed at exact SHA
`10963ddaa535f3fd335ca30031b3039b1da398c6`:

- repository job `92759644660`: PASS in `7m10s`, including complete repository
  verification, complete non-visual E2E, current-tree Gitleaks and the complete
  pull-request-history secret scan;
- visual job `92759644740`: PASS in `2m30s`, complete governed fixed-Linux
  matrix `65/65`;
- controlled job `92759645318`: correctly skipped for the ordinary
  pull-request event;
- visual artifact `8980844734`, size `6,206,199` bytes, digest
  `sha256:f85a143df03444c3805561f3f9eafcd874b385ccc856d0d3ac7a2cc8918da262`;
  and
- Gitleaks artifact `8980926561`, size `6,760` bytes, digest
  `sha256:209451760ce9befc7b600501d9ab95a6ad2fad5d998d9287422433179ed95a0b`.

No Requirement, public API, permission, Schema intent, ownership,
transaction, idempotency, audit, baseline, threshold or PASS criterion was
weakened to obtain this PASS.

## Security, rollback and next checkpoint

Authorization remains server-side and precedes protected resolution. The
browser receives no raw private File URL and cannot inject template/source or
controlled provenance. Existing Frappe permissions and the independent exact
mapping printer authority remain mandatory.

Before retained history exists in an environment, this checkpoint may be
reverted and migrated fresh. After retained history exists, recovery disables
create/content routes and uses a reviewed forward fix while preserving every
registry version, snapshot, File, output, event, audit and receipt.

Checkpoint 2 is PASS. P5-06 continues with only the reusable SPA
controlled-print affordance/status boundary, direct English/`zh`/`zh-TW`
coverage and affected browser/visual evidence. It must remain visibly
unavailable when no approved mapping resolves. The controlled synthetic Site,
P5-06 Level 2 and Phase 5 Level 3 Gate remain inactive until that frontend
checkpoint and a subsequent complete ordinary CI pass.
