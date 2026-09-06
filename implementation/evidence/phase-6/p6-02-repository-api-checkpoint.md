# P6-02 Repository and BFF Checkpoint

Recorded: `2026-08-07T19:05:22Z`

Status:
`PASS — LEVEL 1 AUTHORIZED REPOSITORY AND CLOSED BFF`

Requirements:
`FR-TX-003`, `FR-TL-004`

Exact stable checkpoint:
`39fe0e8445079bb7a811ca2f24910ba96624a0ac`

## Delivered boundary

- Added Project-first authorized, bounded physical Tooling Set collection and
  exact Set detail projections. Protected Set, intake, Requirement, customer
  and File Revision identities are never exposed outside the authorized
  Project and tenant boundary.
- Activated only the five frozen closed paths: two private/no-store GET
  projections and three narrow POST commands for one physical Set, one
  immutable intake version and one append-only exact File Revision evidence
  reference.
- Mutation remains internal `System Manager` only. Commands reauthorize and
  lock the exact Project, require an exact same-Project Requirement/customer
  boundary and accept only an existing clean private File Revision.
- Commands bind idempotency to tenant, Project, actor, operation, key and
  canonical payload. Replay requires a sealed target and response hash;
  receipt, object, immutable projection, append-only audit, response and seal
  remain in one Frappe request transaction and every non-2xx path rolls back.
- Added exact intake-version and evidence-identity conflicts plus an
  independent fail-closed `npi_p6_02_routes_disabled` switch. Missing
  configuration is disabled; no Site or production default was enabled.

## Deliberately unavailable

- No live SPA data source or Tooling workspace activation is delivered by
  this checkpoint. The prototype remains isolated until checkpoint 3 passes
  its state, accessibility, trilingual and visual evidence.
- No Set lifecycle, source Tooling Revision, formal Supplier, ERP Asset or
  location, customer account/signature, file upload/delete/release, external
  mapping, adapter, endpoint, credential or mutation was installed.
- The API does not invent lifecycle, revision, Supplier, Asset, location,
  signature or external-file authority. It references only exact existing
  governed objects already inside the Project boundary.
- This is not P6-02 Level 2. Disposable-Site runtime and the final Task Gate
  remain checkpoint 4 after the live workspace passes ordinary CI.

## Local affected and regression evidence

- initial focused domain/metadata/contract/repository/API suite: `53/53`
  PASS;
- post-correction metadata/repository/API/contract suite: `39/39` PASS;
- complete tracked Python regression: `1,145/1,145` PASS;
- complete frontend unit coverage: `730/730` PASS; generation, typecheck,
  lint, formatting, production bundle and i18n audit passed;
- i18n audit: `4,133` literal English sources with direct `100%` `zh` and
  `100%` `zh-TW` coverage;
- OpenAPI response references, DocType JSON, compilation, V1.2
  reconciliation, prototype approval, P0 visual governance and
  `git diff --check`: PASS.

The workspace-wide local brand command remains intentionally blocked by the
pre-existing untracked user asset
`frontend/public/images/npi-one-project-management-sketch.png`. It was
preserved and excluded from every commit. Clean exact-SHA repository jobs
passed the same brand guard and every complete verification lane.

## Changed-files -> affected-tests

| Change surface | Direct evidence |
|---|---|
| `tooling/frappe_repository.py` | Project-first scope, bounded Set queries, exact Requirement/customer/File Revision containment, transaction order, immutable intake versions, evidence identity, sealed replay and rollback cases in `test_phase6_tooling_repository.py` |
| `tooling_api.py`, `bff.py`, request security and errors | route/method/CSRF/admin/IDOR/unavailable/closed-field/replay/conflict/rollback/route-switch cases in `test_phase6_tooling_api.py` |
| OpenAPI closed paths and schemas | exact five-path activation, response-reference resolution, private/no-store and forbidden server-truth assertions in `test_phase6_tooling_contract.py` |
| command-receipt DocType/controller | exact operation-to-target whitelist and real-Frappe Select metadata assertions in `test_phase6_tooling_metadata.py` |
| translations/generated catalog | complete catalog generation and i18n audit while runtime values remain the literal English contract enums |
| shared footer catalog fingerprint | exact eighteen fixed-Linux P0 baselines from the failed exact-SHA artifact, followed by `73/73` final visual PASS |

## Prevented controlled-Site blocker

Product commit `c8f2ebcd7c5cb36f1a81d9436c07d19b2eabaac7` contained the
closed repository/BFF implementation. Its ordinary CI `31207891174` passed
visual job `92963352257` and the repository `verify.sh`, then was superseded
and cancelled during non-visual E2E when the corrective commit was pushed. It
is retained as `SUPERSEDED/CANCELLED`, never reported as PASS.

A pre-controlled-Site source/metadata cross-check then proved one unique
runtime root: the reused `NPI Tooling Command Idempotency` DocType Selects and
controller whitelist allowed only P6-01 operation/target pairs. The new P6-02
receipt insert would therefore fail Frappe validation even though the
in-memory ordinary repository tests did not execute DocType Select validation.
Corrective commit `d339da58487f46a767b62a6ead6b11c99ed8431c`
adds only the three exact operation/target pairs, their administrator-visible
translations and direct metadata assertions. Contract values remain literal
English and no permission, transaction, idempotency or API rule changed.

This explains the earlier pattern of apparently effective fixes followed by a
later controlled blocker: each ordinary test double covered repository
semantics but could not exercise a previously unreachable Frappe metadata
boundary. Here the cross-layer check found that boundary before any controlled
Site dispatch, so no diagnostic cycle or Site mutation was needed.

## Exact-SHA ordinary CI and bounded visual proof

Corrective commit `d339da5` ran ordinary CI `31208510139`:

- repository job `92965418919` passed complete repository verification,
  complete non-visual E2E and both current-tree/history Gitleaks lanes;
- controlled runtime job `92965419812` correctly skipped; and
- visual job `92965418903` passed all 55 non-P0 cases and failed only the
  eighteen durable P0 screenshots. Artifact `9005792248`, digest
  `sha256:8f02d8093e2b2306bf8d79890a21558515c5711fa197cc00e0d74f799c1bd5d6`,
  proved the catalog fingerprint changed from `220fdc2cf42779bb` to
  `957013df4ef08130`. Each failure contained only `300` or `306` changed
  pixels, and every threshold-significant delta was confined to the bottom
  status-bar fingerprint at `y=882..891`.

The eighteen exact Linux actuals were synchronized byte-for-byte only to their
matching tracked fixed-Linux targets in isolated baseline commit
`39fe0e8445079bb7a811ca2f24910ba96624a0ac`. No product component, layout,
state, assertion, matrix, threshold or PASS rule changed. User-owned Darwin
screenshots and every unrelated dirty/untracked file were preserved.

Final ordinary CI `31209234574` passed at exact stable checkpoint `39fe0e8`:

- repository job `92967755668`: PASS, including complete verification, E2E
  and both secret lanes;
- visual job `92967755547`: PASS, `73/73`;
- controlled runtime job `92967756711`: correctly skipped;
- visual artifact `9006061034`, digest
  `sha256:02a6db63a056cf03b4e5f3261c0a1d05ae7b16f49b7bf44d8c5d80fdee098991`;
  and
- Gitleaks artifact `9006216901`, digest
  `sha256:7c2051e7809b5b17c8c0aa3691a3dec0513b1e52dffefbad50709091d7ed1397`.

The preceding P6-02 checkpoint-1 evidence commit
`a78c91d2e58ed9b746d2f0d9cb8cb6b1c6b2deba` also passed exact-SHA
ordinary CI `31205863774`: repository `92956626704`, visual `92956626544`
and controlled runtime `92956627373` correctly skipped.

## Review, rollback and next checkpoint

Checkpoint 2 is PASS. The independent route switch remains closed by default,
so rollback disables the five P6-02 routes and preserves every additive Set,
intake, evidence reference, audit and receipt row. Once rows exist, repair is
forward-only; no table removal, history rewrite, evidence deletion or Set
identity collapse is permitted.

Autopilot next implements only P6-02 checkpoint 3: a strict server-backed Set
and intake data source, dense live Tooling workspace, exact governed File
Revision picker, honest downstream unavailable states, capability-driven
actions, complete English/`zh`/`zh-TW`, accessibility and affected visual
matrix. A controlled Site still must not be dispatched until that live
checkpoint passes affected checks and complete ordinary CI.
