# P5-03 Repository, BFF and OpenAPI Checkpoint

Recorded: `2026-07-31T22:22:10Z`

Status:
`PASS — LEVEL 1 REPOSITORY/BFF/OPENAPI CHECKPOINT`

Requirement:
`FR-DS-006`

Product checkpoint:
`ff4fb4d15da14d6ac04354ff63d7da1af34cacba`

Complete ordinary CI:
[`30669247503`](https://github.com/kaibowang-hash/jce_npi/actions/runs/30669247503)

## Delivered boundary

- Added Project-scoped document-baseline list/create repository commands under
  the independent `npi_p5_03_routes_disabled` fail-closed route switch.
- Baseline creation verifies internal transport, current Project membership
  and the exact published Project policy/actor binding before resolving any
  protected Document, revision or File identity.
- The command locks and revalidates the exact currently released Document
  Revision, lifecycle/release snapshots, complete revision-to-File
  associations and each live private File Revision/hash/size/MIME/scan fact.
- Actor-bound idempotency and payload conflict protection preserve the frozen
  transaction order: unsealed receipt, immutable baseline, ordered members,
  audit, authoritative response and final receipt seal.
- Added strict BFF and OpenAPI GET/POST schemas. Responses contain safe exact
  identity, lifecycle, release, policy, member, File and hash metadata only;
  raw URLs, caller-selected scan truth, generic CRUD and inferred impacts are
  absent.
- Added complete direct Simplified and Traditional Chinese catalog entries
  for every new literal-English source. No production baseline policy,
  G2/G5/G6/ECN content map or dependency matrix was installed.

Gate `release_baseline` attachment, dependency registration, successor impact,
Gate Review refresh, UI and controlled-Site runtime proof remain later P5-03
stages. The list response therefore exposes an honest empty `impacts` array
instead of inferred relationships.

## Changed-files to affected-tests

| Boundary | Evidence |
|---|---|
| baseline repository and exact persistence | `tests.test_phase5_document_baseline_repository` |
| BFF/API authorization, strict parsing and route recovery | `tests.test_phase5_document_api` |
| domain and immutable snapshot compatibility | `tests.test_phase5_document_baseline_domain` |
| closed OpenAPI schemas and prior route compatibility | `tests.test_phase5_document_contract` |
| direct translations and generated catalog | catalog generation plus i18n audit |
| shared catalog visual effect | complete fixed-Linux governed matrix |

The focused affected set passed `55/55`. Complete local Python discovery
passed `863/863`; six additional cases are protected user-owned untracked
local-prerequisite tests and were not committed. The clean repository suite in
CI passed `858/858`.

## Complete ordinary CI evidence

- repository job `91283194361`: `PASS`;
- fixed-Linux visual job `91283194245`: `PASS`;
- Python `858/858`;
- frontend unit `660/660` in `32/32` files;
- non-visual browser `286/286`;
- fixed-Linux visual `30/30`;
- i18n audit: `3,184` literal-English sources with direct `100%` `zh` and
  `100%` `zh-TW` coverage;
- frontend statements/branches/functions/lines coverage
  `82.31% / 79.52% / 85.22% / 84.26%`;
- both npm audits reported zero vulnerabilities;
- current-tree and complete pull-request-history secret scans passed; and
- the controlled-Site job was correctly skipped for the ordinary pull-request
  event.

The passing visual artifact is `r1-06-linux-visual-evidence`, artifact ID
`8808171724`, size `4,444,656` bytes and upload digest
`sha256:06d9d929ed571062d249f0c9f97d226e1cd7a50deef4b22f173b0dd9130a16c9`.

## Catalog visual baseline proof

The first clean product CI for `eab1692` passed the complete repository job
and failed only the fixed P0 `18`-image subset because the visible App Shell
footer catalog version changed from `06fbd2d21ff5d924` to
`e130c39d6bb06201`. Exact decoded-pixel comparison proved every changed pixel
was within the bottom status bar (`y >= 879`); ordinary language cases changed
only the catalog hash glyphs. Trial English and Simplified Chinese also had
eight identical one- or two-channel antialias changes at the four corners of
the final status selector. There were no content, density, overflow,
mixed-language, permission, state or accessibility differences.

The `18` stable Linux actual images from CI artifact `8807375720` were copied
byte-for-byte to their matching tracked baselines in isolated commit
`ff4fb4d`. No threshold, assertion, matrix member or PASS criterion changed.
The subsequent clean run passed all `30/30` governed images.

## Security and invariants review

- Authorization precedes protected resolution; transport role, Project
  visibility, Project ownership, RACI, `System Manager` and UI state do not
  grant baseline authority.
- The caller cannot supply a mutable URL, `latest`, File/scan truth, release
  fact, dependency target or response snapshot.
- Baseline and member records remain immutable, append-only and protected by
  the private baseline command write scope.
- P5-01/P5-02 Requirement, API, permissions, revision/lock/version,
  lifecycle/release integrity, audit, idempotency and transaction ordering are
  unchanged.
- No new production dependency, core patch, direct SQL, cross-database write,
  external request, credential, TODO fake success or destructive migration
  was introduced.

## Rollback and next stage

After retained baseline history exists, preserve every policy, baseline,
member, audit and receipt, disable only the independent P5-03 routes and use a
reviewed forward fix. P5-01/P5-02 reads remain available and ERPNext remains
untouched.

Next, add only the exact `release_baseline` Gate Template/evidence kind and
same-transaction dependency registration. Historical templates and Gate
evidence remain unchanged; successor impact and UI stay outside that focused
slice.
