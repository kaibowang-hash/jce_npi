# P7-00 Validation — Phase 7 Trial and NPI Requirement Anchor

Validated: `2026-08-10T05:08:00Z`

Branch: `codex/npi-v1.2-implementation`

Starting controller checkpoint:
`e662684ffefd9d44c11a0e5e70e8801bd0a5f1e3`

Retained product/runtime checkpoint:
`68f230fee73b1b6ca95206346d128e1518613d82`

Result: **PASS — LEVEL 2 DOCUMENTATION/TRACE TASK GATE**

## Scope and non-scope

P7-00 allocates the complete reconciled Trial/NPI scope to P7-01 through
P7-08, freezes identities and NPI/ERPNext ownership, carries Phase 6's exact
`not_measured`/`unavailable` boundaries forward, records `DR-REC-009` and the
controlled-print decisions as scoped holds, audits the current repository and
defines task, test, migration and rollback order.

It creates no Python/TypeScript product behavior, DocType, Schema, migration,
route, OpenAPI/data-ownership row, translation, screenshot, print mapping,
event, adapter, credential, production policy or external mutation. It does
not claim any Trial/NPI requirement as implemented.

## Requirement allocation

| Requirement set | Primary task |
|---|---|
| FR-TR-001 | P7-01 |
| FR-TR-002/003/010, FR-NP-004/005, FR-TX-019 foundation | P7-02 |
| FR-TR-004/009, FR-TL-009/010 foundation | P7-03 |
| FR-TR-005..008 | P7-04 |
| FR-NP-001..003/006..013 | P7-05 |
| FR-NP-014/015 | P7-06 |
| FR-PRN-002, FR-INT-015 NPI-side foundation, FR-TR-008 output | P7-07 |
| UX-020 | P7-08 |

Anchored statuses mean allocation only. `FR-PRN-002` retains its Phase 5
technical verification; `FR-INT-015` retains its Phase 8 external-projection
status; `FR-TX-019` and the Tooling foundations retain their Phase 6 evidence.

## Existing-capability conclusion

- No live Trial or NPI backend aggregate, guarded metadata, repository, BFF or
  Released Trial Summary exists.
- The current Trial page is a deterministic in-memory prototype: the photo is
  not transported and the conclusion action persists neither snapshot nor
  audit.
- The coarse legacy ownership row and prototype values cannot be relabelled as
  a live Trial contract.
- Phase 6 exact Tooling/cavity/process/File/defect/capacity/acceptance truth is
  reusable predecessor evidence but intentionally leaves Trial Actual
  `not_measured`, Approved Baseline/official quality unavailable and all
  external execution inactive.
- Shared authorization, Gate, Work Item, idempotency/audit, private File,
  controlled print, industrial UI and Frappe i18n mechanisms are reusable but
  confer no Trial/quality/approval/Gate/ERP authority.

## Verification

- Phase 6 closure/controller checkpoint `e662684` passed exact-SHA ordinary CI
  `31356737236`: repository job `93357718684`, fixed-Linux visual job
  `93357718640` and both secret lanes passed; the controlled-Site job
  `93357718996` correctly skipped because product/runtime truth was unchanged;
- the repository retained `1,420` tracked Python tests, `809` frontend unit
  tests, `352/352` non-visual browser tests, `5,753` directly translated
  sources, statements `80.07%`, clean generation/type/lint/build and two
  zero-vulnerability audits;
- visual job `93357718640` passed the complete governed `94/94` matrix;
- visual artifact `9050946139` has digest
  `sha256:66ddac29acc24b757b49d8064c445d4e2638d7661e9c8dea218579893860902f`;
- Gitleaks artifact `9051062077` has digest
  `sha256:15f1cc52bfbfe106195d508938253a16f156ace340b07c126b013686325d6397`;
- canonical 282-row trace generation/verification, focused reconciliation
  tests, Phase status YAML, exact P7 task allocation, evidence paths and
  `git diff --check`: PASS; and
- no production endpoint/credential, external event, enabled print mapping,
  lifecycle/approval default, raw private URL or fake ERP/quality success
  claim was introduced.

## Migration and rollback

P7-00 has no runtime or data migration. Reverting its evidence before P7-01
would only restore the unanchored Phase 7 controller state. Once P7 tasks
retain business history, the route-disable and reviewed forward-fix rules in
the anchor apply; immutable Trial/NPI/audit/output history is never deleted.

## Exit

P7-00 passes. P7-01 is the sole active atomic task and begins with a bounded
Requirement/domain/existing-capability audit. No product mutation occurs until
that plan freezes the exact Trial Plan/Round identity and lifecycle-authority
boundary.
