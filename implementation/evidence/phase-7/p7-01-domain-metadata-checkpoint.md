# P7-01 Domain, Contract and Metadata Checkpoint

Recorded: `2026-08-10T06:30:36Z`

Status:
`PASS — PLAN/ROUND IDENTITY, IMMUTABLE REVISION CONTRACT AND GUARDED ADDITIVE METADATA`

Primary requirement: `FR-TR-001`

Exact stable checkpoint:
`87c2ab011d3699af20cb64dbf097c02cfec1ca57`

Product and bounded visual commits:

- `3d3f510` — pure Trial Plan/Revision, planned Trial Round, lifecycle event,
  Work-link and actor-bound command-receipt domains; corrected Project-first
  closed contract; guarded additive metadata and direct tests; and
- `87c2ab0` — promote only the reviewed fixed-Linux catalog-footer actuals
  caused by the new controlled translation sources.

## Delivered boundary

- Established a stable `TrialPlan` identity with immutable, exactly ordered
  `TrialPlanRevision` snapshots, predecessor identity/hash, canonical snapshot
  hash and bounded change reason.
- Established a separate `TrialRound` UUID and planned-state projection bound
  to one exact Plan revision. A Round cannot be relabelled as its Plan or moved
  by a later Plan revision.
- Frozen the controlled purpose vocabulary, aware UTC interval, positive sample
  quantity, exact Project-member responsibility, Tooling Master identity,
  measurement-plan intent and proposed machine/material resources.
- Resource proposals expose only server-owned booking state `unavailable`.
  Callers cannot claim availability, conflict-free status or reservation.
- Added immutable Trial lifecycle-event and Plan/Round-to-Domain-Work link
  identities without creating a second action lifecycle.
- Added five guarded additive DocTypes with UUID identity, exact parent and
  tenant fields, immutable/create-only controller boundaries, denied generic
  delete/rename/print/export and exact ownership declarations.
- Replaced the unimplemented Round-collapsing placeholder contract with closed
  Project-first Plan, revision, Round and action-generation schemas. The
  contract exposes no prepare, run, actual, defect, conclusion, approval,
  quality, Gate, ERP or resource-confirmation command.
- Added complete English-source, Simplified Chinese and Traditional Chinese
  catalog coverage for every new user-visible controlled source.

## Deliberately unavailable

- This checkpoint creates no route, repository command, business row, Work
  Item, File, runtime fixture, browser action, external mapping or adapter.
- `System Manager` is only the conservative future technical command authority;
  no Trial business-role or approval policy is invented.
- Planned state is the only activated lifecycle truth. Input lock, physical Set
  and cavity, actual values, evidence, defects, conclusion, approval, readiness
  and formal quality remain allocated to later Phase 7 tasks.
- No production ERPNext endpoint, credential, network call, Outbox event,
  availability reader or reservation policy is present.

## Changed-files to affected-tests

| Change surface | Direct evidence |
|---|---|
| Trial pure domains and metadata validation | identity separation, immutable revision/predecessor/hash, interval, purpose, resource-unavailable, member and label invariants |
| guarded DocTypes/controllers | exact fields/options/defaults, UUID identity and generic CRUD/rename/delete denial |
| OpenAPI and data ownership | closed Project-first additive schemas, exact NPI/Project Work/ERP ownership and absence of later commands |
| translation catalogs/generated catalog | generation plus complete direct `zh`/`zh-TW` coverage and mixed-language audit |
| fixed-Linux visual baselines | reviewed catalog-fingerprint-only actuals; complete final governed matrix |

## Local and exact-SHA CI evidence

- Direct checkpoint domain/contract/metadata/localization tests passed `30/30`.
- Catalog generation, OpenAPI YAML parse, Python compilation, V1.2
  reconciliation, P0 visual governance and `git diff --check` passed locally.
- Ordinary CI run `31361586261` passed exact SHA `87c2ab0`:
  - repository job `93371344429`: PASS;
  - visual job `93371344404`: PASS at `94/94`; and
  - controlled runtime job `93371345366`: correctly skipped because no runtime
    product boundary was ready for controlled-Site proof.

## Review, rollback and next checkpoint

Task Diff Review confirms that checkpoint 1 is additive and activates no
route, business row or external behavior. Before retained Trial rows exist,
the foundation can be reverted. After activation, rollback must disable only
the independent Trial routes and use reviewed forward repair; immutable Trial,
receipt, Work-link and audit truth must never be deleted.

Checkpoint 1 is PASS. P7-01 remains in progress. The next proven boundary is
the Project-first repository/BFF checkpoint; the live Trial workspace and
controlled-Site runtime remain separate checkpoints.
