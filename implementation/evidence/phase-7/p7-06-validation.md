# P7-06 Level 2 Validation — Production Handover and Observation Period

Recorded: `2026-08-14T18:54:42Z`

Decision: `PASS — LEVEL 2 TASK GATE`

Exact final product checkpoint:
`563fff535bc46f3d0c216a68a555b61b32479a0d`

Primary requirements: `FR-NP-014` and `FR-NP-015`.

## 1. Outcome

P7-06 delivers the frozen NPI-owned technical foundation for production
handover and observation:

- one same-tenant, no-default, immutable policy-version boundary;
- linear production-transition package revisions whose exact sources are
  closed over current immutable readiness, defect and Trial-conclusion tips;
- actor-slot acknowledgements bound to the current package without successor
  inheritance or approval semantics;
- independent immutable observation revisions with explicit unavailable
  external actuals;
- all five external providers returning identity-free unavailable truth;
- deterministic current-source reconstruction, actor-bound replay,
  append-only audit and receipt sealing; and
- a dense English, Simplified-Chinese and Traditional-Chinese Project
  production-transition workspace with explicit held authority.

No P7-06 command closes G7, approves a release, establishes bilateral or
receiving-organization authority, proves an actual SOP or external production
metric, or mutates a Gate, Project, Work Item, Tooling object, ERP record,
Outbox, external provider or production print state.

## 2. Requirement trace review

| Requirement | Level 2 disposition | Evidence boundary |
| --- | --- | --- |
| `FR-NP-014` | `TECHNICAL_VERIFIED_IMMUTABLE_HANDOVER_ACKNOWLEDGEMENT_FOUNDATION_FORMAL_ORGANIZATION_AND_G7_AUTHORITY_HELD` | Exact immutable handover packages, current actor-slot acknowledgements and reconstruction are proven; formal receiving organization, bilateral authority and G7 authority remain held. |
| `FR-NP-015` | `TECHNICAL_VERIFIED_OBSERVATION_REVIEW_FOUNDATION_ACTUAL_SOP_EXTERNAL_METRICS_AND_STABILITY_AUTHORITY_HELD` | Immutable observation review and explicit unavailable providers are proven; actual SOP, external metrics and stability-policy authority remain held. |

Neither truthful held disposition is approval, production actual, Gate close
or release authority.

## 3. Exact-SHA ordinary and controlled Gates

Ordinary pull-request CI `31828878511` passed exact SHA `563fff5`:

- repository `94859592477`: complete repository verification and `1,873`
  tracked Python tests PASS;
- frontend `94859592402`: `58/58` files, `908/908` unit tests and `399/399`
  non-visual E2E tests PASS; `7,307` direct English sources have `100%`
  Simplified- and Traditional-Chinese coverage; aggregate statement, branch,
  function and line coverage is `80.36%/80.24%/83.05%/83.00%`, with zero
  vulnerabilities;
- visual `94859592530`: the complete `112/112` fixed-Linux governed matrix
  PASS; artifact `9230002263` has upload digest
  `sha256:85d9a950afe2bf4d168007f0cf8c2905e993ee143a2086393f986652ab5426ef`;
  and
- secret scan `94859592400`: `26` pull-request first-parent commits and `462`
  full-history commits PASS with no leaks; artifact `9229888878` has upload
  digest
  `sha256:004638f284cd537f4c90d1c426c7a94cee0b78d5d6f84da660de797d8c163384`.

Independent exact-SHA controlled Gate `31829617671` then passed the same SHA:

- controlled preflight `94861911975` verified the exact repository, event,
  head SHA and successful required jobs in ordinary run `31828878511`;
- prior-Gate artifact `9230158705` has upload digest
  `sha256:c7daa59f5e28db999489a5660e2a15f36f98d2d42bd6af78e6818d805d97d917`;
- cumulative runtime `94862026482` passed scope `p5-01-through-p7-06` on
  pinned Frappe commit `a3d8090ba80cb91d3ed72ea90bec67df201db5c1`;
- runtime artifact `9230370526` has upload digest
  `sha256:0b68c53e2abea2ba11957134977b68ef507e9b22cc4bbd5e450718832fd573a0`;
  its `result.txt` payload hashes to
  `sha256:ec9b17ef86dc66e96dcdeac4b5b04d30c011f75020b815a237a2c598f2715559`
  and records `result=PASS`, the exact SHA, Level 2 mode, predecessor scope
  `p5-01-through-p7-05` and final scope `p5-01-through-p7-06`; and
- disposable MariaDB/Redis containers, volumes and network were removed by
  the successful always-run cleanup step.

Repeated repository/frontend/visual/secret jobs were skipped by the controlled
dispatch only after fail-closed exact-SHA attestation passed. This is the
P7-06 Level 2 Task Gate. Phase 7, PR and release boundaries still require the
applicable complete Level 3 Gate.

## 4. Controlled truth and negative matrix

The cumulative disposable Site retains exactly `4` acknowledgements, `11`
audits, `9` exact sources, `2` package revisions, `2` observation revisions,
`1` policy version, `5` provider results and `11` receipts. It proves:

- current readiness, defect and conclusion chain tips override historical
  candidate inputs, and predecessor version drift fails closed;
- package succession and observation succession are independent, immutable
  and exactly reconstructable without latest-value substitution;
- acknowledgements are bound to the frozen package and actor slot, remain
  fact-only, and do not inherit into a successor package;
- all five offline providers expose explicit unavailable truth without
  persisting a fabricated external identity or actual;
- same-process and cross-process replay, altered-payload conflict, stale/fork
  denial and transaction rollback preserve receipts, audits and responses;
- Project-first guest, external, unrelated-reader, acknowledgement-actor and
  manager authority levels preserve the Project/actor invariant before
  secondary-ID handling;
- all `11` routes independently disable and recover; additive migrations,
  clean-log redaction and the sensitive-persistence sentinel pass; and
- `sensitivePersisted=false`, `zeroDownstreamEffects=true`, zero ERP/network/
  Outbox/provider mutation and complete disposable-resource cleanup hold.

## 5. Task Diff Review and diagnostic attempts

The bounded P7-06 range is
`75c67e6ffbe8b1cd113a7eac97c7878bce28e258..563fff535bc46f3d0c216a68a555b61b32479a0d`:
`11` commits, `80` paths, `34,596` insertions and `105` deletions. The exact-
SHA current-task guard accepted all committed paths. They belong to the four
frozen checkpoints, direct evidence, generated trilingual catalogs, reviewed
fixed-Linux visuals or bounded controlled-runtime forward fixes. User-owned
dirty files and `implementation/LAST_RUN.md` are outside this closeout.

Two controlled attempts are diagnostic failures, not PASS evidence:

- `31823927177` at `23403286bb662c83af115f977dbc76988a0ee5d2`
  exposed the production-transition current-source bridge defect. It produced
  no runtime result or runtime artifact; cleanup passed. The bounded forward
  fix selected current readiness, defect and conclusion chain tips and made
  the retained P7-05 rejected file tuple truthful.
- `31827177095` at `bfac3f0fd9219940a591e2afd48f3bb9ef37003c`
  exposed an IDOR actor-fixture defect: the acknowledgement actor legitimately
  had second-Project authority while the workspace probe expected denial. It
  produced no runtime result or runtime artifact; cleanup passed. The bounded
  forward fix separated the unauthorized reader, frozen acknowledgement actor
  and manager roles and added executable authority-level coverage.

Each forward fix preserved the Requirement, API, permission, ownership,
transaction, idempotency, audit and PASS rules, passed affected tests, and was
followed by a new independent exact-SHA ordinary plus controlled attempt.

## 6. Security, migration, rollback and limitations

- Authentication precedes parsing; Project authority precedes protected
  secondary IDs; mutations enforce CSRF, internal authority, exact hashes,
  predecessor state and actor-bound idempotency.
- Policy, package, acknowledgement, observation, receipt and audit history is
  append-only. Unknown fields, altered replay, stale sources, corrupt
  provenance and cross-Project references fail closed.
- Additive/idempotent migrations and the complete cumulative runtime passed on
  a fresh disposable Site.
- Before retained data, rollback may disable the independent P7-06 route and
  workspace switches. After retained history exists, rollback is switch
  disable plus reviewed forward repair; exact history is never deleted,
  edited or renumbered.
- Formal organization/bilateral/G7 authority, electronic signature or
  approval, actual SOP, external yield/complaint/cycle/Tooling metrics,
  stability business policy, ERP effects, external Released Trial Summary
  projection and production print remain explicit scoped holds.

## 7. Decision and transition

P7-06 passes its Level 2 Task Gate with the two truthful per-row dispositions
in section 2. The final evidence-based release review records `P0=0` and
`P1=0`; this review does not replace the required Level 3 workflow at a Phase,
PR or release boundary.

Standing continuous-delivery authority activates only the bounded P7-07
Requirement/domain/existing-capability audit for `FR-PRN-002`, `FR-INT-015`
and `FR-TR-008`. Product implementation may begin only after that audit
freezes the immutable Released Trial Summary and controlled-output boundary.
External event/projection remains held under `DR-REC-009`; form mapping,
signature, retention and copy policy remain held under `DR-REC-003` and
`DR-REC-004`; G7, ERP and production print authority remain held.
