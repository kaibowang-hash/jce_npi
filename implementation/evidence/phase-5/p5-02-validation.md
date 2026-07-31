# P5-02 Level 2 Task Gate

Recorded: `2026-07-31T20:15:18Z`

Task:
`P5-02 — Review and release workflow`

Product checkpoint:
`f088d70b00b54488587b2a83a311b636ef48cf78`

Result:
`PASS — LEVEL 2 REVIEW AND RELEASE WORKFLOW TASK GATE`

This is an atomic-task result, not the Phase 5 or release Gate. Phase 5
remains `IN_PROGRESS`; P5-03 is the next active task.

## Requirement result

| Requirement | Result at the P5-02 boundary |
|---|---|
| `FR-DS-002` | `TECHNICAL_VERIFIED` — submit, reject, resubmit, approve, release, supersede and obsolete transitions preserve immutable released content and append-only history |
| `FR-DS-005` | `TECHNICAL_VERIFIED_FOUNDATION` — exact review assignment, independent approval/release authority and immutable authenticated confirmation are proven; production authority, quorum, delegation and regulated-signature meaning remain held |
| `FR-DS-010` | `TECHNICAL_VERIFIED_FOUNDATION` — exact release-time private identity, bytes, SHA-256, MIME, size and scanner-owned `clean` state are proven; the production scanner provider remains held |

No production release policy, reviewer/approver mapping, signature standard,
scanner provider, retention/watermark/effectivity policy, external identity,
CAD/PDM connector or ERPNext connection was installed or inferred.

## Delivered vertical slice

- A Project-scoped immutable release-policy version supplies exact synthetic
  reviewer, approver and releaser bindings without deriving business authority
  from Project ownership, RACI, `System Manager`, assignment or transport role.
- Closed submit, reject, resubmit, approve, release, supersede and obsolete
  commands require exact lifecycle versions, actor-bound idempotency, trusted
  CSRF and independent server authorization.
- Review cycles, electronic confirmations and lifecycle events are append-only;
  the P5-01 revision and File association remain immutable.
- Every transition advances a guarded lifecycle projection only after its
  immutable command evidence is written, and seals the command receipt last.
- Release revalidates the live private File identity, bytes, length, SHA-256,
  MIME and scanner-owned `clean` observation before marking the exact File
  Revision released once.
- The underlying released Frappe `File` cannot be deleted while an exact
  released File Revision refers to it.
- The `/api/npi/v1` contract, data source and Project Documents workspace
  expose normal and non-normal workflow truth in literal English with direct
  Simplified and Traditional Chinese translations.
- The independent P5-02 route switch fails closed while retaining P5-01 reads
  and every immutable review/release record.

## Controlled-Site closure

The diagnostic boundary retained only closed stage codes, verified exception
types and exact trace IDs where present. No exception text, traceback, request,
Cookie or credential entered the evidence.

One product root was repaired: a server-generated draft policy snapshot/hash
was being treated as caller-owned conflict during the legal guarded
draft-to-published transition. Commit `c2b69d0` accepts only the exact prior
server-owned draft values, recomputes the canonical published snapshot, keeps
tampered values rejected and retains publish-once immutability.

The subsequent controlled runs exposed verifier-only preconditions rather
than additional product roots:

- `a4ca5ff` aligned a denied-submit assertion with the already correct
  independent review-assignment authority response;
- `7040dbc` resolved the tamper fixture through the immutable Document
  Revision/File association instead of comparing different ID namespaces; and
- `f088d70` applied the same exact association/hash resolution to the released
  File deletion precondition and added a guard against direct cross-namespace
  comparison.

These corrections changed no Requirement, public API schema, permission,
release authority, file-integrity rule, lifecycle rule, transaction order or
PASS criterion. Product-root repair accounting advanced from three to four;
the verifier-only corrections do not consume product-root rounds.

Final unchanged controlled-Site workflow
[`30661586342`](https://github.com/kaibowang-hash/jce_npi/actions/runs/30661586342)
matched exact product SHA
`f088d70b00b54488587b2a83a311b636ef48cf78` and passed:

- repository job `91258836437`;
- controlled document runtime job `91258836459`;
- fixed-Linux visual job `91258836421`;
- exact pinned Bench/runtime tool verification;
- fixed disposable Site/database/user guards;
- two additive/idempotent migrations;
- exact synthetic release-policy publication and independent authority denial;
- submit replay/conflict, rejection, immutable prior cycle, resubmission,
  approval, tamper rejection/restoration, release and cross-process replay;
- released Frappe `File` deletion rejection;
- independent P5-02 route disable/recovery while P5-01 reads remain active;
- bounded result artifact upload and cleanup; and
- no production or external connection.

The bounded runtime artifact is `p5-document-runtime-30661586342`, size `349`
bytes, digest
`sha256:a387b8e34326f6db035ff9be81517c8f7b00a82ac30d6b59b691f9bb0b3ef660`.

## Level 2 verification

| Boundary | Evidence |
|---|---|
| Complete clean Python suite | `830/830 PASS` in ordinary CI |
| Complete current workspace Python discovery | `836/836 PASS`; the additional `6` tests are pre-existing untracked local-prerequisite checks and are not part of this checkpoint |
| Runtime-verifier focused suite | `23/23 PASS` locally before final dispatch |
| Complete frontend unit suite | `660/660 PASS` in `32/32` files |
| Complete non-visual browser suite | `286/286 PASS` |
| Fixed-Linux visual matrix | `30/30 PASS`, including exact P5-02 English `1366×768@100%`, Simplified Chinese `1440×900@125%` and Traditional Chinese `1920×1080@150%` evidence |
| Complete ordinary pull-request CI | [`30661086073`](https://github.com/kaibowang-hash/jce_npi/actions/runs/30661086073), head SHA `f088d70`, repository and visual jobs `PASS`; controlled job correctly skipped for the PR event |
| Final unchanged controlled workflow | [`30661586342`](https://github.com/kaibowang-hash/jce_npi/actions/runs/30661586342), exact SHA `f088d70`, all three jobs `PASS` |
| i18n | `3,055` literal-English sources with direct `100%` `zh` and `100%` `zh-TW`; generated-catalog, placeholder, terminology and mixed-language checks `PASS` |
| Security/dependencies | both npm audits, prohibited-pattern checks, current-tree secret scan and ordinary-CI complete PR-history secret scan `PASS`; no new production dependency |
| Reconciliation/trace | `282` unique IDs = `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`; exact P5-02 statuses and evidence paths verified |
| Compilation/format/diff | Python compilation, Bash syntax, JSON/YAML parsing, frontend type/lint/format/style/boundaries/build and `git diff --check` all `PASS` |

## Task Diff Review

The bounded P5-02 range from its approved plan parent through product
checkpoint `f088d70` changes `90` tracked files with `14,618` insertions and
`117` deletions. It contains the release domain/repository/DocTypes, guarded
BFF/OpenAPI/ownership additions, Project Documents workflow, direct
translations, focused tests, runtime verifier and task evidence.

Review found no new or weakened Requirement, public operation/schema,
data-ownership declaration, permission, P5-01 revision/lock/version rule,
audit, idempotency, transaction ordering, file-integrity rule or PASS
criterion. There is no normal-user Desk path, `ignore_permissions`, direct SQL,
cross-database write, dual-master field, raw private URL, external request,
production secret, TODO fake success or destructive migration.

## Domain, UI and localization review

- A transport role and UI visibility grant no review, approval, release,
  supersede or obsolete authority.
- Released content identity remains the exact P5-01 revision/File/hash; review
  state lives only in append-only P5-02 records plus a guarded projection.
- Scanner state cannot be selected by a browser command, and release remains
  unavailable unless exact current integrity and scanner-owned policy pass.
- The dense Project Documents workspace retains square controls, stable
  toolbar/inspector layout, a single industrial-teal primary action and
  text-plus-shape state truth under the Siemens iX Classic Light baseline.
- User-visible sources remain literal English through the local `t()`/Frappe
  catalog chain with direct `zh` and `zh-TW`; stable API/status codes remain
  untranslated contract values.
- Keyboard, focus, translated labels/tooltips, non-color-only status,
  processing/conflict/retry/final-failure and authoritative-refresh paths are
  covered by the passing unit/browser evidence.

## Migration and rollback

Both real migrations passed on the fixed disposable Site and install no
production release policy or business record. Before retained P5-02 history
exists, the bounded commits are revertible. After review/release history
exists, rollback is the tested `npi_p5_02_routes_disabled` switch plus a
reviewed forward fix. Revisions, Files, review cycles, confirmations, lifecycle
events, releases, audits and idempotency receipts must not be deleted,
rewritten or reopened.

## Decision

P5-02 passes its Level 2 Task Gate. Scoped production/external/provider holds
remain explicit and do not convert to fake completeness. Phase 5 remains open,
and standing automatic-transition authority activates only
`P5-03 — Baseline and impact invalidation` with `FR-DS-006`, beginning at its
bounded Requirement/domain audit.
