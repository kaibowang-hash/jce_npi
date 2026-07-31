# P5-02 Controlled-Metadata Checkpoint

Recorded: `2026-07-31T07:36:49Z`

Starting plan checkpoint:
`05a68445139b9684582bf14d6427b4271e7a0e0c`

Result:
**PASS — CONTROLLED-METADATA FOUNDATION; REPOSITORY COMMANDS READY**

Requirements in progress:

- `FR-DS-002`;
- `FR-DS-005`; and
- `FR-DS-010`.

## Delivered boundary

- Added the closed `draft`, `in_review`, `approved`, `released`,
  `superseded`, `obsolete` domain state family.
- Added one Project-scoped administrative release-policy root and immutable
  publish-once version. The policy freezes explicit submitter, reviewer-slot,
  approval-count, release, supersede and obsolete user bindings.
- Enforced reviewer/release separation and non-disableable live-private-file,
  SHA-256, `clean` scanner and exact released/later/effective successor rules.
- Added immutable exact review evidence for revision, association, File
  Revision, Frappe File identity/content hash, name, MIME, size, SHA-256,
  scanner observation, uploader and upload time.
- Added append-only Review Cycle, authenticated electronic Confirmation and
  Lifecycle Event DocTypes/controllers.
- Added a separate guarded Revision Lifecycle projection. It can advance only
  through an exact event and optimistic lifecycle version; the P5-01
  `NPI Document Revision` snapshot and `NPI Document Revision File`
  association remain unchanged.
- Added an independent P5-02 release-command write scope and Site switch seam.
- Added a server-side Frappe `File.on_trash` guard before the retained Gate
  dependency hook. It rejects deletion when an exact referring
  `NPI File Revision.released` is true.
- Updated data ownership for the new exact versioned policy, append-only
  history and guarded projection. No production authority was installed.

## Scope protection

- No P5-01 API, revision, file association, lock, retrieval, permission,
  idempotency or transaction rule was changed.
- No production policy, user binding, scanner/provider, external route,
  CAD/PDM or ERPNext endpoint was created.
- `System Manager`, Project owner/RACI/membership, edit-lock ownership and
  `NPI API User` remain non-authoritative unless explicitly frozen in a
  published synthetic policy; policy publication accepts only enabled
  internal System Users.
- Confirmations are described as authenticated electronic confirmations, not
  certificate-backed or regulated digital signatures.
- All new persistence is additive. There is no fixture, default production
  row, data rewrite or destructive migration.

## Level 1 verification

- release domain plus existing P5 document domain: `26/26` PASS;
- release metadata plus existing P5 document metadata/domain:
  `37/37` PASS;
- complete `test_phase5_document*.py`: `110/110` PASS;
- all new/affected Python compiles: PASS;
- all fourteen document-family DocType JSON files parse: PASS;
- new release-domain and DocType-controller Python files contain no line over
  88 characters: PASS;
- `git diff --check`: PASS.

## Ordinary-CI follow-up

Ordinary CI run `30613731273` for checkpoint commit `c895bd4` found two
additive coverage gaps:

- the new English metadata and domain source strings were not yet present in
  both Frappe Chinese catalogs, so catalog generation and the governed visual
  job failed closed; and
- the retained Phase 4 File-hook test still asserted the old single-callback
  tuple shape even though the release-deletion guard correctly changed
  `on_trash` to an ordered callback list.

The follow-up keeps every product and gate rule unchanged. It adds complete
Simplified/Traditional Chinese translations and regenerates the React
catalog; strengthens the existing hook test to require the deletion guard
before the still-present dependency callback; and adds pure-domain coverage
for partial/final review approval, rejection, separated final-release
authority and exact-cycle terminal transitions.

Post-fix affected verification:

- complete `test_phase5_document*.py`: `114/114` PASS;
- Phase 4 File-hook metadata tests: `7/7` PASS;
- generated catalog freshness: PASS;
- all affected Python compiles: PASS; and
- `git diff --check`: PASS.

The three guarded Frappe error calls retain their complete English source
strings on one physical line because the repository's translation extractor
requires one literal. This is the only affected Python line-length exception;
it preserves complete extractable messages rather than weakening i18n.

The host does not provide standalone `ruff` or `black`; the complete ordinary
CI remains the canonical pinned formatter/linter proof for the exact commit.

## Remaining task work

P5-02 is not complete. The next slice is the repository command path:

1. load exact published release policies and revision/file evidence;
2. implement submit, review approve/reject, resubmit, release, supersede and
   obsolete transactions;
3. extend the existing actor-bound document idempotency operations;
4. append audit and preserve event/projection/receipt ordering and rollback;
5. revalidate live private bytes/hash/scan before release and mark the exact
   File Revision released once; and
6. add repository/controller transaction tests before BFF/OpenAPI work.
