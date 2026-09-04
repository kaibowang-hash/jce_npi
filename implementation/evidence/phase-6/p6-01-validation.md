# P6-01 Level 2 Validation — Part, Requirement, Master, Applicability and Cockpit

Recorded: `2026-08-07T16:50:49Z`

Decision: `PASS — LEVEL 2 TASK GATE`

Exact product checkpoint:
`d0a9258c03d687b24e62ed3b80c4d60c4fe2cdac`

Requirements:
`FR-TX-001`, `FR-TX-002`, `UX-004`, `FR-TL-001`, `FR-TL-003`

## 1. Outcome

P6-01 delivers the frozen minimum complete vertical slice:

- distinct tenant-stable Part, immutable Part Revision, Project-scoped Tooling
  Requirement, logical Tooling Master and immutable versioned/effective
  Tooling Applicability identities;
- one shared Master reused by multiple Project relationships without cloning;
- Project-first authorized, closed BFF queries and commands with same-tenant
  reference checks, actor-bound idempotency, one transaction, append-only
  audit and fail-closed route control;
- a server-backed dense Tooling cockpit with exact identity/applicability truth,
  capability-driven actions and honest unavailable downstream sections; and
- disposable-Site proof of create, reuse, exact revision, Applicability,
  replay, conflict, rollback, IDOR denial and route disable/recovery.

No production lifecycle, numbering, ownership/custody policy, Tooling Revision,
physical Set, Trial, workbook mapping, adapter, ERPNext endpoint, credential or
external mutation is installed. `DR-REC-010` continues to hold exact Tooling
Requirement/Revision/Set lifecycle states, transitions and authorities.

## 2. Requirement trace review

| Requirement | Level 2 result | Evidence boundary |
|---|---|---|
| `FR-TX-001` | `TECHNICAL_VERIFIED_FOUNDATION` | Distinct Part/Revision, Requirement, Master and Applicability are live and non-collapsed. Tooling Revision, physical Set and Trial remain later tasks. |
| `FR-TX-002` | `TECHNICAL_VERIFIED` | One Master is reused across two Projects through three immutable Applicabilities with exact version/effectivity and no clone. |
| `UX-004` | `TECHNICAL_VERIFIED_FOUNDATION` | The live dense Tooling identity/applicability cockpit passes states, accessibility, trilingual and visual checks; later Tooling sections remain honestly unavailable. |
| `FR-TL-001` | `TECHNICAL_VERIFIED_FOUNDATION` | Requirement and logical development record foundation is live; ownership/custody/repair/return truth belongs to P6-02. |
| `FR-TL-003` | `TECHNICAL_VERIFIED_FOUNDATION` | Multi-Project/Part/Master Applicability is live; cavity and Trial traceability belongs to P6-03 and Phase 7. |

`implementation/REQUIREMENT_TRACEABILITY.csv` is updated from anchored status
to these exact results and cites this report plus the product/test surfaces.

## 3. Controlled disposable-Site Gate

Complete ordinary CI `31197968661` passed exact SHA `d0a9258` before the Site
dispatch:

- repository `92930758119`: complete repository verification, non-visual E2E,
  current-tree and complete PR-history Gitleaks PASS;
- visual `92930757760`: fixed-Linux governed matrix `73/73` PASS; and
- controlled `92930758895`: correctly skipped.

Final diagnostics-closed workflow `31198574475` retained the exact same SHA:

- repository `92932746371`: PASS;
- visual `92932746394`: PASS, `73/73`;
- controlled runtime `92932746437`: PASS, including pinned tools, disposable
  Site, two migrations, cumulative P5 predecessor, P6-01 runtime, replay and
  cleanup; and
- artifact `9001947238`, `p6-tooling-runtime-31198574475`, GitHub digest
  `sha256:4f4fa8d5884e71fc2b3388b23c45b55509f0482ad4e937fbbd7396a615130a65`.

The artifact records `result=PASS`, head SHA `d0a9258`, run `31198574475`,
disposable Site `npi.localhost`, database `npi_one_runtime`, pinned Frappe
commit `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` and cumulative scope
`p5-01-through-p6-01`.

The final Tooling runtime summary proves:

- `projects=2`, `sharedMasterCount=1`, `projectApplicabilities=3`;
- `immutablePartRevisions=3`, `appendOnlyAudits=8`;
- `crossProcessReplayReady=true` and replay PASS;
- `rollbackVerified=true`; and
- route disable/recovery PASS without weakening the retained P5 predecessor.

## 4. Level 2 module and UI checks

Current-tree focused checks:

- six Phase 6 Tooling Python suites: `45/45` PASS;
- Tooling data-source, live-page and router unit suites: `33/33` PASS;
- P6-01 non-visual browser matrix: `8/8` PASS across English, Simplified
  Chinese and Traditional Chinese plus exact Master navigation, capability-
  driven command, processing/conflict/validation and indistinguishable IDOR;
- i18n audit: `4,059` literal English sources, direct `100%` `zh` and
  `100%` `zh-TW` coverage;
- generated-source, industrial UI and source-boundary audits: PASS;
- complete tracked Python regression: `1,130/1,130` PASS; and
- compilation, prototype approval, P0 visual governance, V1.2 reconciliation,
  YAML parsing, prohibited-pattern and diff checks: PASS.

The first local browser attempt was blocked by the filesystem sandbox from
binding `127.0.0.1:4173`; the identical command passed `8/8` when run with the
approved local-loopback permission. Two earlier focused invocations used the
wrong working directory and were rerun unchanged from the correct repository
and frontend roots; these were command setup errors, not product failures.

## 5. Changed-files to affected-tests

| Change surface | Required evidence |
|---|---|
| Tooling domain and six guarded DocTypes | Phase 6 domain/metadata/contract suites, additive migrations and controlled Site |
| repository, API, request security and errors | repository/API suites plus controlled authorization, replay, conflict, rollback and IDOR |
| OpenAPI and data ownership | closed-schema/ownership tests and reconciliation |
| Tooling data source, routes, page, styles and translations | `33/33` unit, `8/8` browser, i18n/UI/boundary audits and `73/73` Linux visual matrix |
| runtime verifier/workflow | runtime-verifier suite, complete ordinary CI and final exact-SHA controlled Gate |
| recovery fixes | affected/full Python, complete ordinary CI and diagnostics-closed unchanged Gate after each uniquely proved root |
| trace/controller/evidence | CSV uniqueness, YAML parse, V1.2 reconciliation, Task Diff Review and `git diff --check` |

## 6. Task Diff Review

The review covers `6b5d034..d0a9258`: `135` task files across the frozen
domain/metadata, repository/BFF, live cockpit, exact tests, governed Linux
evidence and controller reports. Every commit belongs to one of the four
planned checkpoints or a serial evidence-proved recovery. Artifact-proved
catalog fingerprint changes and the five first P6-01 Linux baselines change no
assertion, threshold or PASS rule.

The recovery history explains why repeated ordinary PASS results did not
initially clear the controlled boundary:

1. Frappe Select defaults falsely bound the pending Part receipt;
2. the same behavior falsely supplied optional Product/Model source systems;
3. the first version-key repair omitted the validator's `tenant_id` namespace,
   and its test mirrored the incomplete helper instead of cross-checking the
   DocType formula.

The final correction hashes
`tenant_id:relationship_global_id:applicability_version` and adds a cross-file
contract assertion. It is the first checkpoint to produce a complete
diagnostics-closed controlled PASS. No Requirement, public API semantics,
permission, Schema intent, ownership, transaction, idempotency, audit,
baseline, threshold or PASS criterion was weakened.

Every unrelated user dirty or untracked file was excluded from all task
commits and remains untouched.

## 7. Security, migration, rollback and limitations

- Project authorization precedes protected Tooling resolution; mutation stays
  same-tenant internal System Manager-only pending approved lifecycle policy.
- Generic Desk create/write/delete, cross-tenant references, arbitrary source
  systems, raw DocTypes/URLs and unsealed replay fail closed.
- Migration is additive/idempotent and the controlled Site passed it twice.
- Before retained use, the task commits may be reverted. After retained rows,
  rollback disables the P6-01 route and uses a reviewed forward repair; it
  never deletes or rewrites Part/Revision, Requirement, Master, Applicability,
  audit or idempotency history.
- Node-20 deprecation annotations from upstream GitHub actions are warnings
  under the repository's forced Node 24 runner and did not affect any job.
- Later lifecycle, ownership/custody, Revision/Set/Trial and ERP behavior stays
  explicitly unavailable and must not be inferred from this PASS.

## 8. Decision and transition

P6-01 passes its Level 2 Task Gate. The next atomic task is P6-02 only:
`FR-TX-003` and `FR-TL-004` customer-owned intake and one identity per physical
Tooling Set. It begins with a bounded Requirement/domain/existing-capability
audit. Exact lifecycle states/transitions/authorities remain held by
`DR-REC-010`; no Asset success, production ERPNext behavior or customer-file
mutation may be invented.
