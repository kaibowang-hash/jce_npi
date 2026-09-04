# P6-02 Level 2 Validation — Customer-owned Intake and Physical Tooling Sets

Recorded: `2026-08-07T21:50:21Z`

Decision: `PASS — LEVEL 2 TASK GATE`

Exact task checkpoint:
`b80aae5efb88ad91a26857e65ff0fd6bf75cd950`

Requirements:
`FR-TX-003`, `FR-TL-004`

## 1. Outcome

P6-02 delivers the frozen minimum complete vertical slice:

- one immutable UUID record for each physical Tooling Set, with independent
  serial and Requirement provenance and no quantity collapse;
- exact customer reference, custody/repair/return provenance and immutable
  versioned arrival-intake snapshots;
- transport and accessory truth, all five frozen inspection categories,
  independently identified differences and optional customer-confirmation
  evidence;
- append-only, URL-free references to an exact existing clean private File
  Revision without uploading, releasing, overwriting, deleting or exposing
  that file;
- Project-first authorized closed BFF queries and commands, System
  Manager-only mutation, actor-bound idempotency, one transaction,
  append-only audit and an independent fail-closed route switch;
- a dense trilingual physical-Set workspace with exact collection/detail,
  history, evidence and honest unavailable states; and
- disposable-Site proof of two independent Sets, intake versions,
  differences, evidence, replay, conflict, rollback, IDOR denial and route
  disable/recovery.

Exact Set lifecycle states/transitions/authorities remain held by
`DR-REC-010`. Source Tooling Revision belongs to P6-03, formal Supplier to
P6-04, and production Asset/location/execution to ERPNext/P6-06/Phase 8.
Customer login/signature and every external mutation remain absent. No
production policy, mapping, adapter, endpoint, credential or dependency was
installed.

## 2. Requirement trace review

| Requirement | Level 2 result | Evidence boundary |
|---|---|---|
| `FR-TX-003` | `TECHNICAL_VERIFIED_FOUNDATION` | Two physical Sets retain independent UUID/serial/Requirement/customer/intake/evidence truth with no quantity collapse. Exact source Revision, formal Supplier, lifecycle, ERP location/Asset and later execution remain owned by P6-03/P6-04/P6-06/Phase 8. |
| `FR-TL-004` | `TECHNICAL_VERIFIED` | Customer owner, transport, arrival photo, accessories, five inspection categories, explicit differences and optional customer-confirmation evidence are retained, authorized and live. |

P6-02 also strengthens the existing `FR-TL-001`
`TECHNICAL_VERIFIED_FOUNDATION` with exact ownership/custody/repair/return
provenance; the held lifecycle/authority policy prevents a broader completion
claim.

`implementation/REQUIREMENT_TRACEABILITY.csv` is updated to these exact
results and cites the product, tests, controlled verifier and this report.

## 3. Controlled disposable-Site Gate

Complete ordinary CI `31220440401` passed exact SHA `b80aae5` before the Site
dispatch:

- repository `93003610445`: `1,140/1,140` clean-tree Python tests,
  `738/738` frontend unit tests, `315/315` non-visual E2E, zero-vulnerability
  audit, current-tree Gitleaks and complete PR-history Gitleaks PASS;
- visual `93003610420`: fixed-Linux governed matrix `76/76` PASS; and
- controlled `93003611017`: correctly skipped.

The one final diagnostics-closed workflow `31221016483` retained the exact
same SHA:

- repository `93005400488`: PASS;
- visual `93005400579`: PASS, `76/76`;
- controlled runtime `93005400541`: PASS, including pinned tools, disposable
  Site, two migrations, cumulative P5 predecessor, P6-01/P6-02 runtime,
  replay, independent route disable/recovery and cleanup; and
- runtime artifact `9010425982`, `p6-tooling-runtime-31221016483`, GitHub
  digest
  `sha256:3b2ec3b719094e2835c8cb6161031dfcd99baba5e32c2deef3dec846cf3a050a`.

The same run retains visual artifact `9010422081`, digest
`sha256:0fc1efab91fefefd33d4fc692128a92a31cac8de4bad4694bec22665a68a65ca`,
and Gitleaks artifact `9010488742`, digest
`sha256:3ba2397e45fef1bf398f06e955bb42b080e89cd3820d1a5c60c2754fb459676b`.

The runtime artifact records `result=PASS`, head SHA `b80aae5`, run
`31221016483`, disposable Site `npi.localhost`, database
`npi_one_runtime`, pinned Frappe commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1`, runtime marker
`npi-one-local-runtime-disposable-v1` and cumulative scope
`p5-01-through-p6-02`.

The final Tooling runtime summary proves:

- `physicalToolingSets=2` and `immutableToolingIntakes=2`;
- `retainedEvidenceReferences=2`, including arrival photo and customer
  confirmation;
- `appendOnlyAudits=16`, `projects=2`, `sharedMasterCount=1` and
  `projectApplicabilities=3`;
- `crossProcessReplayReady=true`, replay PASS and
  `rollbackVerified=true`; and
- P6-01 and independent P6-02 route disable/recovery PASS without weakening
  the retained cumulative P5 predecessor.

## 4. Level 2 module and UI checks

Current-tree focused checks:

- P6-02 runtime-verifier suite: `8/8` PASS;
- affected cumulative P5/P6 runtime-verifier suites: `83/83` PASS;
- complete current workspace Python regression: `1,146/1,146` PASS, including
  the user's unrelated untracked local-prerequisite tests; the clean tracked
  CI count is `1,140/1,140`;
- complete frontend unit suite: `41` files and `738/738` PASS;
- P6-01/P6-02 browser and governed fixed-Linux matrix: `315/315` non-visual
  and `76/76` visual PASS in clean CI;
- i18n audit: `4,211` literal English sources with direct `100%` `zh` and
  `100%` `zh-TW` coverage;
- boundary, industrial UI, display-brand, TypeScript/build, package install,
  zero-vulnerability audit and secret scans: PASS; and
- shell syntax and `git diff --check`: PASS.

The local production compilation completed, but its final display-brand audit
correctly rejected the pre-existing untracked user asset
`frontend/public/images/npi-one-project-management-sketch.png`. The clean
exact-SHA ordinary and controlled repository jobs passed the same audit. The
user file was not changed or staged.

## 5. Changed-files to affected-tests

| Change surface | Required evidence |
|---|---|
| Set/intake/evidence domain and three guarded DocTypes | domain/metadata/contract suites, additive migrations and controlled Site |
| repository, API, request security and route switch | repository/API suites plus controlled containment, replay, conflict, rollback, audit and IDOR |
| OpenAPI and data ownership | closed schemas, subresource paths, ownership and no-fake-ERP assertions |
| Tooling data source, live workspace, styles and catalogs | `738/738` unit, `315/315` browser, i18n/UI/boundary audits and `76/76` Linux visual matrix |
| runtime verifier/workflow | affected verifier suites, complete ordinary CI and exact-SHA diagnostics-closed controlled Gate |
| runtime fixture repair | current-Revision regression assertion, affected/full Python and both CI boundaries |
| transitive security lock | strict clean install, build/style compatibility, full and production-only zero-vulnerability audits and complete ordinary CI |
| trace/controller/evidence plus canonical generator/verifier | CSV uniqueness, YAML parse, generated-form equality, V1.2 reconciliation, direct trace regression, Task Diff Review and `git diff --check` |

## 6. Task Diff Review and blocker analysis

The review covers `49a8931..b80aae5`: `89` task files across the frozen plan,
domain/metadata, repository/BFF, live workspace, governed Linux evidence,
runtime verifier and exact tests (`10,830` insertions, `97` deletions). Every
commit belongs to one planned checkpoint, evidence-only baseline sync or a
serial evidence-proved technical recovery. No unrelated user dirty or
untracked file appears in a task commit.

The final controlled boundary required two distinct repairs:

1. Controlled run `31219316958` passed every cumulative predecessor and failed
   the first P6-02 customer-intake Requirement. Exact code-path review proved
   the fixture had already advanced the Part from Revision A to current
   Revision B but still submitted obsolete Revision A. The repository
   correctly enforces the frozen current-Revision reference rule. Repair
   `8fe1730` changes only the two fixture references to Revision B and adds a
   regression assertion; product behavior is unchanged.
2. The next ordinary CI `31219948750` passed tests and build but GitHub's
   current vulnerability database newly classified transitive development
   package `nanoid <3.3.17` as high severity. Repair `b80aae5` updates only the
   lock record from `3.3.16` to compatible `3.3.18`. It adds no direct or
   production dependency and retains the existing fail-closed audit rule.

An earlier ordinary CI failed Gitleaks on a long synthetic query label that
matched `generic-api-key`; the just-created runtime commit was amended to
short response-neutral labels instead of adding an allowlist or weakening the
scan. Corrected ordinary CI `31218807211` passed before the first Site.

This history explains why multiple earlier attempts did not immediately clear
the Gate: each PASS or repair addressed the exact boundary then visible, while
the controlled Site later exposed the stale fixture reference and the external
advisory appeared only after the next push. No prior product root recurred,
and no guessed repair or repeated unchanged rerun was used.

No Requirement, public API semantics, permission, Schema intent, ownership,
transaction, idempotency, audit, baseline, threshold or PASS criterion was
weakened.

## 7. Security, migration, rollback and limitations

- Project authorization precedes protected Master/Set resolution; P6-02
  mutation remains same-tenant internal System Manager-only pending approved
  lifecycle policy.
- Generic Desk create/write/delete, cross-Project/tenant references, arbitrary
  customer/file references, raw URLs and unsealed replay fail closed.
- Migration is additive/idempotent and the controlled Site passed it twice.
- Before retained use, the task commits may be reverted. After retained rows,
  rollback disables only P6-02 routes and uses a reviewed forward repair; it
  never deletes, merges or rewrites a physical Set, intake, difference,
  evidence reference, audit or idempotency receipt and never mutates the
  referenced customer file.
- Node-20 deprecation annotations from upstream GitHub actions are warnings
  under the repository's forced Node 24 runner and did not affect any job.
- Exact lifecycle, source Revision, formal Supplier, ERPNext Asset/location,
  external signature and production integration behavior remain unavailable
  and must not be inferred from this PASS.

## 8. Decision and transition

P6-02 passes its Level 2 Task Gate. The next atomic task is P6-03 only:
`FR-TX-004..008`, `FR-TL-002`, `FR-TL-003` and `FR-TL-006` for immutable
Tooling Revision/specification structure, cavities, inserts/changeovers and
the multi-shot/overmold process chain. It begins with a bounded
Requirement/domain/existing-capability audit. Exact lifecycle
states/transitions/authorities remain held by `DR-REC-010`; no formal
Supplier, production Asset/location, external execution, credential or ERPNext
success may be invented.
