# P5-01 Resume Audit

Audited: `2026-07-30T13:52:00Z`

Atomic task:
`P5-01 — Document and design revision`

Requirements:

- `FR-DS-001`
- `FR-DS-003`
- `FR-DS-004`
- `FR-DS-007`
- `FR-DS-008`
- `FR-DS-009`
- `FR-DS-014`

Retained implementation checkpoint:
`930b5a28cb995df12f251994a36f7502525ed94a`

Audited current checkpoint:
`c980571b27be66e16f2ac57409f0ef72a986e741`

Result:
`PASS — RETAIN P5-01 BACKEND/DOMAIN/CONTRACT CHECKPOINT`

This is a bounded Level 1 resume audit. It does not mark any P5-01
requirement complete, substitute technical tests for business UAT, or pass the
P5-01 Level 2 Task Gate.

## 1. Authority and scope

The comparison used:

- `docs/DETAILED_REQUIREMENTS.md`;
- `docs/V1_2_RECONCILIATION_ADDENDUM.md`;
- `implementation/V1_2_RECONCILIATION_DECISIONS.md`;
- `implementation/phase-5-requirement-anchor.md`;
- `implementation/evidence/phase-5/p5-01-plan.md`;
- `implementation/evidence/phase-5/p5-01-reconciliation-hold.md`;
- `contracts/data-ownership.yaml`;
- `contracts/npi-api.openapi.yaml`;
- accepted ADR-005 localization facts; and
- the `frappe-safe-change`, `npi-domain-guard`, `industrial-ux` and
  `frappe-i18n` Skills.

The audit compares the exact retained 55-file checkpoint inventory with the
accepted reconciliation and every later R1 change. It does not reopen passed
R1 work or begin P5-02 review/release, P5-03 baseline, P5-04 EBOM or P5-05
formal publish behavior.

## 2. Requirement and domain comparison

| Requirement | Retained boundary | Reconciliation result |
|---|---|---|
| `FR-DS-001` | stable Controlled Document identity, exact versioned policy reference, server-generated unique policy-scoped number | Retain. No production type, prefix or numbering policy is installed. |
| `FR-DS-003` | immutable major/minor Document Revision with reason, effectivity, predecessor and metadata history | Retain. Revision and File Revision identities remain separate. |
| `FR-DS-004` | exact typed same-Project relationships and bounded reverse filtering for currently implemented resolvers | Retain. Future Tooling/Trial/change/CAD resolvers remain unavailable rather than guessed. |
| `FR-DS-007` | optimistic edit lease, check-out/check-in, administrative recovery and append-only lock history | Retain. A lock never grants approval or broader authorization. |
| `FR-DS-008` | Project/tenant authorization, confidentiality metadata, audited content retrieval and non-authorizing share-grant foundation | Retain. External retrieval remains unavailable pending identity/sharing policy. |
| `FR-DS-009` | exact file/hash/scan capability truth, native PDF/image eligibility and authorized audited content fallback | Retain. Office/CAD and unverified content are never represented as previewable. |
| `FR-DS-014` | connector-neutral provenance/capability contract with unavailable or isolated-failure states | Retain. No outbound CAD/PDM request or fabricated connector success exists. |

The retained aggregate still satisfies the frozen identities, ownership,
authorization-before-resolution, actor-bound idempotency, optimistic version,
append-only history, audit, no-raw-private-URL and fail-closed provider
invariants. No Class-B production fact was inferred.

## 3. Exact Git comparison

The retained checkpoint introduced exactly 55 files. The later R1 range
intersects that inventory at fourteen paths:

- five shared product/catalog paths:
  `apps/npi_core/npi_core/bff.py`,
  `apps/npi_core/npi_core/translations/zh.csv`,
  `apps/npi_core/npi_core/translations/zh-TW.csv`,
  `contracts/npi-api.openapi.yaml` and
  `frontend/src/generated/catalogs.ts`;
- two focused tests:
  `tests/test_phase5_document_contract.py` and
  `tests/test_phase5_document_repository.py`; and
- seven recovery/trace/plan paths.

There is no later commit in the comparison range for:

- `document_api.py`;
- `documents/domain.py`;
- `documents/frappe_repository.py`;
- `documents/frappe_validation.py`;
- any of the nine P5-01 DocType/controller directories;
- `contracts/data-ownership.yaml`; or
- the P5-01 domain, API, controller and metadata test implementations.

The shared intersections are compatible:

- BFF changes add the fixed R1 session/grid/inspector preference routes and
  request-ID/route-disable handling. The document route family and its method
  dispatch remain unchanged.
- OpenAPI changes are additive R1 contracts. No added or removed line in the
  range changes a Document path, operation, schema or error family.
- Both Frappe CSV catalogs and the generated React catalog add the accepted R1
  literal sources. Current direct-catalog coverage and generator freshness
  pass.
- The two focused tests split prohibited-token literals across adjacent Python
  strings so repository secret/prohibited-pattern scans do not match the
  tests themselves. Python concatenates those literals to the same assertions;
  product and test behavior is unchanged.
- Recovery, trace and plan changes preserve the checkpoint while replacing
  the completed R1 hold with this explicit resume audit.

No retained implementation file requires correction.

## 4. Permission, API, ownership and localization review

- Browser access remains through explicit `/api/npi/v1` document queries and
  commands, not raw DocType CRUD.
- Guest, external, tenant-mismatched, unrelated and unavailable scope remains
  opaque before protected validation detail.
- Create, revise, lock, recover, preview and download remain independent
  server permissions; share/review/release remain false.
- Content access revalidates the exact Project/document/revision/file
  association and live private-file identity before an audited binary
  response.
- `ControlledDocument`, `DocumentRevision`, `DocumentRevisionFile` and
  `FileRevision` ownership remains consistent with
  `contracts/data-ownership.yaml`.
- The stable English API/status codes remain untranslated.
- Frappe v15.115.4 continues to use direct headerless `zh` and `zh-TW` App CSV
  catalogs under ADR-005; React continues to consume their generated catalog.

No core patch, Desk normal-user flow, `ignore_permissions`, direct SQL,
cross-database write, dual-master field, production policy, external identity,
CAD/PDM connection or ERPNext connection was introduced.

## 5. Changed-files to affected-tests

| Audited surface | Affected checks | Result |
|---|---|---|
| retained document domain/repository/controllers/API/metadata/contracts | six focused P5-01 Python suites | `PASS — 63/63` |
| shared BFF/OpenAPI/catalog additions | current complete repository verifier and affected regressions | `PASS — CI #73` |
| translation and generated catalog | extraction, placeholder/context, direct locale coverage, generator freshness and mixed-language gates | `PASS — 2,782 sources; 100% zh/zh-TW` |
| resume trace/controller/evidence | reconciliation verifier/tests, YAML/CSV truth and whitespace review | local checks pass; this checkpoint receives fresh CI after commit |

The focused command was:

```text
python3 -m unittest \
  tests/test_phase5_document_api.py \
  tests/test_phase5_document_contract.py \
  tests/test_phase5_document_controllers.py \
  tests/test_phase5_document_domain.py \
  tests/test_phase5_document_metadata.py \
  tests/test_phase5_document_repository.py
```

It ran `63` tests in `0.209s` and passed.

## 6. Fresh current-checkpoint verification

GitHub Actions CI `#73`, run `30548142786`, passed on exact head
`c980571b27be66e16f2ac57409f0ef72a986e741`:

- repository job `90889525337`: Python `764/764`, frontend unit `634/634`
  across `30/30` files, frontend coverage
  `85.46% / 83.63% / 89.01% / 87.53%`, i18n `2,782` literal sources with
  `100%` direct `zh`/`zh-TW`, non-visual browser `279/279`, both npm audits
  with `0` vulnerabilities, a `22`-commit action scan and a `59`-commit full
  branch scan with no leaks;
- visual job `90889525478`: fixed-Linux affected matrix `24/24`;
- visual artifact `8761649289`, size `3,725,955` bytes, digest
  `sha256:bb9add0a69b9c61fb2908ff0f6e75f779a8a207a538fd1e1a100a235c403b2de`;
  and
- Gitleaks artifact `8761804431`, size `6,760` bytes, digest
  `sha256:79524d0c3ca399ed528e659242db3779c3aa13bf179d34e8f1aa4dde0f518974`.

The CI checkout is the pull-request merge of this exact head into the current
base, as expected for the repository workflow. Both jobs and every declared
step completed successfully.

## 7. Retained and unfinished scope

Retained without reimplementation:

- pure document policy/revision/relationship/lock domain;
- nine additive guarded DocTypes;
- repository, permission, idempotency, audit and binary safety behavior;
- BFF/API/OpenAPI/data-ownership contracts;
- direct backend catalog sources; and
- focused backend/contract tests.

Still unfinished:

- additive/idempotent metadata synchronization and real controlled Frappe
  runtime/rollback/replay proof;
- strict frontend document data source, closed response parsers and view
  models;
- live Project Design/Documents engineering workspace;
- real form dirty-state registration with App navigation, history, tab and
  `beforeunload` guards;
- complete normal, empty, loading, no-permission, read-only, validation,
  conflict, processing, retryable, final and unavailable states;
- new literal-English copy with direct `zh` and `zh-TW`;
- affected component, E2E, accessibility and exact visual evidence; and
- P5-01 Level 2 Task Gate.

## 8. Resume decision and rollback

Decision:
retain the complete bounded `930b5a2` backend/domain/contract slice and start
only the unfinished P5-01 runtime/frontend vertical slice.

No migration or product data changed during this audit. Reverting the audit
checkpoint changes only recovery/evidence state; it must not delete or rewrite
the retained document implementation or any controlled history.

The next atomic action is to add the smallest complete frontend/runtime
extension over the existing contract, beginning with strict data-source/view
model parsing and real workspace dirty-state registration, while preparing
the additive metadata/runtime proof. P5-02 remains inactive.
