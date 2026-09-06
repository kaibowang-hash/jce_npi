# P5-06 Controlled Print Foundation Validation

Recorded: `2026-08-07T09:16:14Z`

Status:
`PASS — LEVEL 2 CONTROLLED PRINT FOUNDATION TASK GATE`

Requirements:
`FR-PRN-001`, `FR-PRN-002`

Final exact product checkpoint:
`6ba2763cc14b3a044e2225d7a960ce02175f88a7`

Complete ordinary CI:
[`31163598955`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31163598955)
(`PASS`, exact checkpoint, diagnostics closed)

Final unchanged controlled-Site Gate:
[`31164225729`](https://github.com/kaibowang-hash/jce_npi/actions/runs/31164225729)
(`PASS`, exact checkpoint, all diagnostics closed)

## Delivered vertical slice

- Added a generic, versioned controlled-print registry with exact tenant,
  source type, Project type, Gate/state, language, effective version,
  delivery/copy capability and frozen Frappe Print Format identity/hash.
- Added a closed server-owned source-adapter boundary. Browser requests contain
  only exact Project/source identity, optimistic source version, language and
  idempotency identity; they cannot submit template HTML, source data or
  controlled provenance.
- Added canonical immutable source/template snapshots, deterministic
  repository-owned verification SVG, native server PDF rendering from frozen
  data, private retained Frappe File/output identity and independent SHA-256.
- Added actor/Project-bound idempotency, changed-payload conflict, atomic
  snapshot/File/output/event/audit/receipt persistence and sealed replay.
- Added exact capability/create/detail/content BFF routes with independent
  route disable/recovery. Retained content is reauthorized and hash-verified,
  returns the same bytes and never reloads live source or rerenders.
- Added the reusable dense Project-context action/status surface, strict data
  source, complete direct three-language coverage and governed visual proof.

No production controlled-print form, enabled mapping, source adapter, signer,
copy-number/retention policy, browser/device print, external QR/render service,
runtime dependency, ERPNext endpoint or credential was installed. Exact forms
and policy remain `FR-PRN-003` under `DR-REC-003/004`.

## Why the serial repairs were necessary and effective

The final Gate deliberately kept diagnostics closed, so a newly reached
server failure initially collapsed to the public HTTP 500 contract. Each
bounded diagnostic run exposed only one response-neutral stage/type/trace
tuple, and each repair advanced execution beyond that stage:

1. valid runtime identities and request identity were corrected before the
   create transaction could execute;
2. the closed native PDF backend replaced an invalid runtime assumption;
3. snapshot data was explicitly thawed before Frappe JSON serialization;
4. pinned Frappe private-file normalization was accepted without inventing an
   `is_remote_file` database field;
5. the already consumed Administrator password was passed to the later route
   probe rather than reread from a pop-on-read secret helper; and
6. the final verifier used the authorized predecessor `/documents` route
   instead of treating the Project cockpit as accessible to a baseline actor
   who is intentionally not a Project owner.

Earlier roots never recurred. The later two failures appeared only after the
controlled-print create/render/replay proof had already passed and were
verifier defects, not permission relaxations. The final exact-SHA run proves
the complete path with diagnostics closed.

No repair changed a Requirement, public API, DocPerm/role, Schema intent,
ownership, transaction order, idempotency, audit, baseline, threshold or PASS
criterion.

## Level 2 and full-repository verification

### Local affected checks

- focused controlled-print/runtime repair group: `71/71 PASS`;
- complete tracked local Python regression after the final repair:
  `1,085/1,085 PASS`;
- compilation, reconciliation, controlled-print metadata/contract/security,
  trace uniqueness and `git diff --check`: PASS.

### Exact-SHA ordinary CI

Run `31163598955` passed at exact SHA `6ba2763`:

- repository job `92819270517`: complete repository verification, non-visual
  E2E, current-tree and complete-history Gitleaks and zero-vulnerability audit;
- visual job `92819270398`: complete governed fixed-Linux matrix; and
- controlled runtime correctly skipped for the ordinary run.

Gitleaks artifact `8988269069` has digest
`sha256:af122fdf9c24bded235931936b0fdddd4f64bc42216f1d9f9b17e4adfb9790e7`.
Visual artifact `8988128694` has digest
`sha256:278739e1cbdb7954b88a4954b8af9aefb64c8106355ef75006d5a270a94480cb`.

### Final unchanged controlled-Site Gate

Run `31164225729` retained exact SHA `6ba2763` and passed:

- repository job `92821257912`: `1,079/1,079` tracked Python tests, `38`
  frontend files with `719/719` unit tests, generated artifacts/type/lint/
  coverage/build, `3,889` literal English sources with direct `100%` `zh` and
  `zh-TW`, zero-vulnerability audits, `303/303` non-visual E2E cases and no
  current-tree secret leak. Complete branch-history Gitleaks was already
  proved by the immediately preceding exact-SHA ordinary run; the manual
  workflow correctly skips that pull-request-only lane.
- fixed-Linux visual job `92821257937`: `68/68`, including the exact three
  P5-06 English/Simplified Chinese/Traditional Chinese cases; and
- controlled job `92821257859`: pinned Bench/Frappe, fixed disposable
  Site/database guards, both app installations and two migrations, unchanged
  P5-01 through P5-05 runtime, synthetic format/mapping/source setup, exact
  controlled-print create and sealed replay, retained File/PDF/hash truth,
  source/template mutation resistance, route-disable/recovery, cross-process
  replay and bounded cleanup.

Controlled artifact `8988384460` is
`p5-document-ebom-runtime-31164225729` (`363` bytes). GitHub records digest
`sha256:6d77c9357dfd6c1fa354c93dd1a6773dfc20837246a9a37bc0edfd9cd4ee6bee`.
Its extracted `result.txt` has SHA-256
`aa84e488856c0eab31aa226a29169515de3097ef2655a544716a9eaf9b4155ff`
and records `result=PASS`, exact head SHA `6ba2763`, run `31164225729`, fixed
disposable runtime marker, pinned Frappe commit
`a3d8090ba80cb91d3ed72ea90bec67df201db5c1` and
`scope=p5-01-through-p5-06`.

Visual artifact `8988376911` has digest
`sha256:c2cb4f00f931f4ac2fd1fccc8b6d183c842d694c6322411a107cbce15993157f`.
Secret-scan artifact `8988488690` has digest
`sha256:fc080aa5301dea32cc8536a3ec3865c0b298077c70bf663230ddedb254170dd5`.

The runner annotated that maintained `actions/*@v4` actions were forced from
Node 20 to Node 24. All jobs passed; this is a hosted-runner compatibility
notice, not a product or Gate failure.

## Requirement, ownership, permission and rollback review

- `FR-PRN-001` is technically verified for exact registry/capability
  resolution; absence, ambiguity, drift or unauthorized access fail closed.
- `FR-PRN-002` is technically verified for one immutable source/template
  snapshot and the exact retained private output. Replay/download never
  substitutes newer live data.
- Authorization precedes protected resolution. Guest, external, unrelated
  Project/tenant and unbound actors fail closed. Independent printer authority,
  CSRF and actor-bound idempotency remain server-side.
- There is no Frappe/ERPNext core patch, unrestricted permission bypass,
  cross-database access, production secret/endpoint, accepted-path stub or
  optimistic external success.
- All DocTypes are additive and repeat migration passed. Before retained
  history, a disposable environment may revert and migrate fresh. After
  retained history, rollback disables create/content routes, preserves every
  registry version/snapshot/File/output/event/audit/receipt and uses a reviewed
  forward fix.

## Changed-files to affected-tests

| Change boundary | Affected evidence |
|---|---|
| registry/snapshot/output domain and six DocTypes | domain, metadata, guard, migration and runtime tests |
| resolver, frozen renderer, QR and private File | source/template drift, PDF/hash/vector and retained-byte tests |
| authority/idempotency/audit transaction | guest/IDOR, exact authority, replay/conflict, write-order and rollback tests |
| BFF/OpenAPI/ownership | strict schema, CSRF, URL-free content and ownership scans |
| Project SPA action/data source/catalogs | complete unit/E2E/i18n/accessibility and three governed visuals |
| controlled verifier and bounded diagnostics | verifier tests, exact-SHA ordinary CI and final diagnostics-closed Site |

## Task conclusion

`PASS — LEVEL 2 P5-06`.

`FR-PRN-001` and `FR-PRN-002` advance to `TECHNICAL_VERIFIED`. P5-06 exhausts
the planned Phase 5 product scope; the independent Phase 5 Level 3 decision is
recorded in `implementation/phase-5-gate.md`.
