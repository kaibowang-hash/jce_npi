# P5-01 Level 2 Task Gate

Recorded: `2026-07-31T07:00:05Z`

Task:
`P5-01 — Document and design revision`

Product checkpoint:
`5a9cd3d85885895819a730dd0da4e7abe86c2646`

Result:
`PASS — LEVEL 2 DOCUMENT AND DESIGN REVISION TASK GATE`

This is an atomic-task result, not the Phase 5 or release Gate. Phase 5
remains `IN_PROGRESS`; P5-02 is the next active task.

## Requirement result

| Requirement | Result at the P5-01 boundary |
|---|---|
| `FR-DS-001` | `TECHNICAL_VERIFIED_FOUNDATION` — stable unique document identity and exact versioned synthetic policy are proven; production type/prefix/numbering policy remains held |
| `FR-DS-003` | `TECHNICAL_VERIFIED` — immutable exact revision identity, predecessor/successor, reason, effectivity and history are proven |
| `FR-DS-004` | `TECHNICAL_VERIFIED_FOUNDATION` — exact currently implemented same-Project resolvers and reverse lookup are proven; later-domain resolvers remain unavailable |
| `FR-DS-007` | `TECHNICAL_VERIFIED_FOUNDATION` — optimistic lease, check-in, recovery and append-only history are proven; production role/lease policy remains held |
| `FR-DS-008` | `TECHNICAL_VERIFIED_FOUNDATION` — confidentiality, Project authorization, audited retrieval and non-authorizing grant records are proven; external identity/retrieval remains disabled |
| `FR-DS-009` | `TECHNICAL_VERIFIED_FOUNDATION` — exact file/hash/scan capability and audited safe fallback are proven; unsupported Office/CAD rendering remains unavailable |
| `FR-DS-014` | `TECHNICAL_VERIFIED_FOUNDATION` — connector-neutral provenance and isolated unavailable/failure truth are proven; no provider or outbound connector is activated |

No production document policy, external identity, scanner provider, Office/CAD
viewer, CAD/PDM connector or ERPNext connection was installed or inferred.

## Delivered vertical slice

- Stable Project-scoped Controlled Document identity remains distinct from
  immutable Document Revision, exact private File Revision and their
  association.
- Nine additive guarded DocTypes retain append-only history and controlled BFF
  writes; generic CRUD cannot replace the normal-user workflow.
- Create, query, check-out, check-in, lock recovery, new-revision,
  capability and audited content paths remain under `/api/npi/v1`.
- Authorization precedes protected resolution; Guest, external,
  tenant-mismatched and unrelated access remains opaque.
- CSRF, actor-bound idempotency, optimistic versions, transaction rollback,
  exact file identity/hash/scan truth and audited binary content remain
  enforced.
- The Project Documents workspace retains strict closed parsers, URL-free Blob
  handling, real dirty-navigation protection, dense industrial layout,
  accessible commands and complete direct English/`zh`/`zh-TW` copy.
- External retrieval and CAD/PDM remain explicitly unavailable instead of
  reporting fabricated success.

## Controlled-Site closure

The recovery preserved the three-field diagnostic boundary:
`code / exceptionType / traceId`. No exception message, traceback, request,
Cookie or credential was accepted into evidence.

1. Diagnostic checkpoint `c4e94a3` passed normal CI `30607746148`.
2. Controlled diagnostic run `30608055245` proved exactly
   `DOCUMENT_REVISION_PRIVATE_FILE_SAVE / PdfStreamError /
   trace-2adf5e0e29df533e9c2ceda04f2dbc19`.
3. The unique cause was a synthetic runtime fixture containing only a PDF
   signature instead of a structurally valid document. Checkpoint `1b596a8`
   replaced only that fixture with a deterministic one-page, JavaScript-free
   PDF. Product file-integrity validation was not changed.
4. The resulting unchanged Gate `30608963778` passed the entire
   revision/private-file/scanner/content path and exposed a later reverse
   relationship HTTP assertion.
5. Behavior-neutral checkpoint `30c285f` retained the same product behavior
   and added only closed HTTP/cardinality/identity assertion diagnostics.
   Normal CI `30609495441` passed.
6. Controlled diagnosis `30609830735` proved exactly
   `P5_RUNTIME_RELATIONSHIP_FILTER_HTTP / RuntimeSubstageFailure /
   trace-1e82a74de2b756faa623b48896176fb6`.
7. Frappe transports GET query parameters as strings, while the relationship
   filter reused a JSON-body-only integer parser. Repair `5a9cd3d` adds one
   strict canonical positive query parser: `"2"` and `2` normalize to the
   same integer, while signs, leading zeros, decimals, whitespace, booleans
   and overflow fail closed. JSON body parsing and the public contract remain
   unchanged.

Final unchanged controlled-Site workflow `30610747931` matched exact product
SHA `5a9cd3d85885895819a730dd0da4e7abe86c2646` and passed:

- repository job `91092739800`;
- P5 controlled document runtime job `91092739857`;
- fixed-Linux visual job `91092739882`;
- exact pinned Bench/runtime tool verification;
- fixed disposable Site/database/user guards;
- both additive/idempotent migrations and the exact nine-DocType inventory;
- fresh synthetic policy, Project, document, lock, revision and private-file
  round trip with server-observed hash and scanner state;
- CSRF, optimistic version, idempotency replay/conflict, audit, Guest, IDOR,
  route-disable/recovery and second-process replay;
- result artifact upload; and
- bounded cleanup with no production or external connection.

The bounded runtime artifact is
`p5-document-runtime-30610747931`, size `348` bytes, digest
`sha256:af771b1a71bfca5c8ae5fcee2ce202584ff47c2fe31ff4201e2a9d9d9c0d410f`.

## Level 2 verification

| Boundary | Evidence |
|---|---|
| P5 document/API/controller/metadata/repository/runtime/controller/trace group | `112/112 PASS` |
| Complete tracked Python suite | `798/798 PASS` |
| Complete current workspace Python discovery | `804/804 PASS`; the additional `6` tests are pre-existing untracked local-prerequisite checks and are not part of this checkpoint |
| Retained complete frontend unit suite | `658/658 PASS` in `32/32` files |
| P5 live browser slice | `6/6 PASS` |
| P5 exact trilingual task visuals | `3/3 PASS`: English `1366×768@100%`, Simplified Chinese `1440×900@125%`, Traditional Chinese `1920×1080@150%` |
| Complete normal pull-request CI | run `30610355829`, exact SHA `5a9cd3d`, repository/complete E2E/fixed-Linux visual/current-tree and complete-history secret scans all `PASS` |
| Final unchanged controlled workflow | run `30610747931`, exact SHA `5a9cd3d`, all three jobs `PASS` |
| i18n | `2,860` literal-English sources with direct `100%` `zh` and `100%` `zh-TW`; generated-catalog, placeholder, terminology and mixed-language checks `PASS` |
| Security/dependencies | both npm audits, prohibited-pattern checks, current-tree and complete PR-history secret scans `PASS`; no new production dependency |
| Reconciliation/trace | `282` unique IDs = `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`; exact P5-01 allocation and evidence paths verified |
| Compilation/format/diff | Python compilation, Bash syntax, JSON/YAML parsing, frontend type/lint/format/style/boundaries/build and `git diff --check` all `PASS` |

## Task Diff Review

The P5-01 product inventory is the retained 55-file
backend/domain/DocType/BFF/API/contract slice plus the bounded
frontend/runtime-ready extension and subsequent controlled-runtime recovery.
The intervening R1 shared bridge is independently passed evidence and is not
relabelled as P5-01 work.

The final recovery range changes only:

- closed diagnostic/controller/evidence guards;
- deterministic synthetic runtime fixtures;
- behavior-neutral runtime assertion diagnostics;
- the strict relationship query parser and focused tests; and
- current execution evidence.

Review found no new or weakened Requirement, OpenAPI operation/schema,
data-ownership declaration, DocType schema, permission, lock, version, audit,
idempotency, transaction ordering, file-integrity rule or PASS criterion.
There is no normal-user Desk path, `ignore_permissions`, direct SQL,
cross-database write, dual-master field, raw private URL, external request,
production secret, TODO fake success or destructive migration.

## Domain, UI and localization review

- Document, revision, file and relationship identities remain separate and
  exact; a lock grants no review/release authority.
- Published/released lifecycle behavior is not implemented early; it belongs
  to P5-02.
- Panels, controls, table density, stable toolbar/inspector layout and the
  single industrial-teal/neutral token system remain within the Siemens iX
  Classic Light baseline. No new UI or visual baseline changed during the
  controlled recovery.
- User-visible sources remain literal English through the local `t()`/Frappe
  catalog chain. API/status codes remain stable untranslated values.
- Keyboard, focus, labels, non-color-only state, dirty-leave confirmation and
  no-hover-only action paths remain covered by the retained units and browser
  evidence.

## Migration and rollback

Both real migrations passed twice on the fixed disposable Site and install no
policy or business records. Before retained document history exists, the
bounded task commits are revertible. After history exists, rollback is the
tested `npi_p5_01_routes_disabled` switch plus a reviewed forward fix;
documents, revisions, private files, lock events, audits and idempotency
receipts must not be deleted or rewritten.

## Decision

P5-01 passes its Level 2 Task Gate. Its scoped production/external/provider
holds remain explicit and do not convert to fake completeness. Phase 5 remains
open, and standing automatic-transition authority activates only
`P5-02 — Review and release workflow` with `FR-DS-002`, `FR-DS-005` and
`FR-DS-010`.
