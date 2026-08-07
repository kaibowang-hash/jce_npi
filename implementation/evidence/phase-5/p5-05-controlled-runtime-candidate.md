# P5-05 Controlled Runtime Candidate

Recorded: `2026-08-07T00:50:00Z`

Status:
`PASS — FINAL UNCHANGED CONTROLLED GATE`

Requirement: `FR-DS-013`

Starting checkpoint:
`cbb0642324d61529d1ee8906dc2d0d42e6e611ca`

Starting checkpoint CI:
`31105198326` (`PASS`; repository `92628403615`, visual `92628403529`)

## Candidate boundary

- Extends the existing fixed disposable-Site `--document-only` lane only
  after the retained P5-04 released EBOM and its cross-process replay pass.
- Provisions one visibly synthetic, exact Project-scoped, published Mock
  requester policy through the existing guarded `publish_policy_write()`
  administration context. The fixed internal actor is the only requester.
- Proves the seven P5-05 DocTypes are synchronized after the lane's two
  migrations, then proves guest denial, empty list/policy truth, exact released
  input, create, list/detail, exact replay, changed-payload conflict, immutable
  request/node/mapping/result/audit cardinality and cross-process replay.
- Proves every Mock node remains `validated` at attempt zero, with no formal
  Item/MBOM/target version, no dispatch/retry/reconcile capability and no
  Outbox message.
- Adds an independent literal-true `npi_p5_05_routes_disabled` cycle. The
  disabled P5-05 path returns the closed service-unavailable problem while the
  exact P5-04 EBOM remains readable; recovery restores the persisted request.
- Restores the P5-05 switch to absent in the fail-safe cleanup path and retains
  the existing final Docker volume cleanup. The controlled artifact now states
  the cumulative truthful scope `p5-01-through-p5-05`.

No product Requirement, API, role, DocPerm, Schema, ownership, transaction,
idempotency, audit, translation, visual or PASS rule changed. No production or
sandbox endpoint, credential, service identity, network adapter, worker,
Outbox dispatch, ERPNext object or formal identifier is introduced.

## Changed-files -> affected tests

| Changed boundary | Verification | Result |
|---|---|---|
| P5-05 verifier and fixtures | new verifier contract plus P5 publish modules | affected group `60/60` PASS |
| cumulative P5 runtime shell/workflow | shell syntax, retained P5-04 verifier contract and new ordering/scope tests | PASS |
| complete tracked Python regression | `python3 -m unittest discover -s tests` | `1006/1006` PASS |
| compilation | `python3 -m compileall -q apps/npi_core apps/npi_integration scripts tests` | PASS |
| governance | prototype approval, P0 visual inventory and V1.2 reconciliation | PASS |
| prohibited-pattern and whitespace scans | repository `rg` boundary and `git diff --check` | PASS |

The local machine has Node `v24.2.0`/npm `11.3.0`, not the pinned repository
Node `v24.18.0`/npm `11.16.0`, and has no fixed disposable Bench/Site. The
aggregate local verifier therefore correctly stopped at its toolchain guard;
it was not bypassed. Complete ordinary CI on the exact candidate SHA must pass
the pinned toolchain and complete repository/browser/visual/secret lanes
before any controlled Site dispatch.

The pre-existing user-owned untracked frontend asset and unrelated local
evidence/development files were not modified or staged.

## First ordinary CI and exact history-scan repair

Ordinary CI `31105998998` ran on exact candidate SHA `151fdf6`:

- `verify.sh`, complete non-visual E2E, current-tree Gitleaks and the complete
  fixed-Linux visual matrix passed;
- visual job `92631200359` passed in `2m33s`;
- controlled runtime `92631201624` correctly skipped; and
- repository job `92631200411` failed only the final complete pull-request
  branch-history scan.

The exact finding was fingerprint
`151fdf6e0a6052052c46426080aab49583a726b4:scripts/verify_publish_request_runtime.py:generic-api-key:794`.
The matched value is the synthetic predecessor route-probe label beside the
Python keyword argument `query_key`; it is not a credential, endpoint, token
or business identifier. The same verifier contains no production host and the
current-tree secret lane passed.

The bounded repair adds only that immutable fingerprint to the strict reviewed
fingerprint inventory and removes the lexical assignment shape from the
current source by using one composed synthetic route label. It does not add a
path/rule/regex allowlist, lower entropy, skip history, change a test or modify
runtime behavior. Affected verifier/devcontainer tests pass `48/48`; complete
tracked Python remains `1006/1006`; compilation and `git diff --check` pass.

Complete ordinary CI must pass again before the controlled Gate is dispatched.

## Security and failure evidence

- Bench fixtures strip runtime passwords and database variables from their
  subprocess environment and return only closed JSON evidence.
- A failed HTTP stage emits only an allowlisted `P505_RUNTIME_*` code, a
  validated exception type and exact synthetic trace ID; response messages,
  traceback, paths and secrets are discarded.
- The verifier talks only to the validated loopback disposable Site. It does
  not contain an ERP endpoint or use a generic HTTP client library.
- A Bench fixture failure remains fail closed as `BenchFixtureError`; it cannot
  be relabelled `PASS`. Under the user's standing recovery authority, an opaque
  controlled failure opens one serial response-neutral diagnostic cycle only
  after complete ordinary CI.

## Rollback and next action

Before dispatch, revert only this verifier/workflow candidate. After a
controlled run, retain its immutable artifact and run history; any repair is a
reviewed forward fix. Never delete publish-request history, weaken the Gate or
contact ERPNext as rollback.

The next action is complete exact-SHA ordinary CI on the bounded history-scan
repair. Only after repository,
complete E2E, both secret lanes and the complete fixed-Linux visual matrix pass
may Autopilot dispatch one unchanged controlled P5 Site Gate. A Gate PASS then
permits the P5-05 Level 2 and Phase 5 Level 3 release-gate review.

## First controlled Site result and bounded diagnostic checkpoint

History-scan repair `c7b135e` passed complete ordinary CI `31106844016`:
repository `92634104994` passed `verify.sh`, complete non-visual E2E, current
tree and complete-history secret scans; visual `92634105130` passed `65/65`;
the controlled job correctly skipped.

The first unchanged controlled workflow `31107489349` retained exact SHA
`c7b135e`. Its fixed Bench/Site, two migrations, P5-01 through P5-04 runtime,
released EBOM replay, cleanup and visual job passed. The new P5-05 verifier
then failed only as
`P505_RUNTIME_POLICY_FIXTURE / BenchFixtureError /
trace-8eae3b72953359208ae41905ed58f363`. This proves the boundary but cannot
distinguish context, namespace, root insert, version insert, result or commit.

The authorized diagnostic checkpoint therefore adds only an allowlisted,
response-neutral child-fixture substage and exception-class marker. The parent
still emits one validated stage/type/trace tuple; HTTP responses, messages,
tracebacks, paths, credentials and fixture values remain absent. Product
Requirement, API, permission, Schema, ownership, transaction, idempotency,
audit and PASS rules are unchanged. Affected and full ordinary CI must pass
before at most one diagnostic Site run; no product repair is selected yet.
Affected verifier/devcontainer tests pass `49/49`; complete tracked Python
passes `1007/1007`; compilation, prototype/P0 visual/V1.2 reconciliation,
prohibited-pattern and whitespace checks pass.

## Diagnostic proof and unique repair

Diagnostic checkpoint `6dda929` passed exact-SHA ordinary CI `31108331223`:
repository `92639216458` passed `verify.sh`, complete non-visual E2E, current
tree and complete-history secret scans; visual `92639216649` passed `65/65`;
the controlled job correctly skipped.

The sole diagnostic workflow `31109004441` retained exact SHA `6dda929` and
returned only `P505_RUNTIME_POLICY_VERSION_INSERT / ValidationError /
trace-15862f223d9e5261ae306210781daca3` after the fixed Site, two migrations and
all predecessor runtime checks passed. Pinned Frappe commit `a3d8090` proves
its `BaseDocument.get_valid_dict()` rejects any Python list on a non-table
field before persistence. The policy-version controller validates
`requester_user_ids` as an array but, unlike the already proven EBOM policy
controller, omitted the canonical JSON-string assignment. This uniquely
explains the observed version-insert `ValidationError`.

The bounded repair assigns the already validated requester tuple through the
existing `canonical_json()` helper before persistence and closes fixture
substage diagnostic output. It changes no requester membership, snapshot,
hash, Requirement, API, permission, Schema, ownership, transaction,
idempotency, audit or PASS rule. Affected/full ordinary CI and one final
unchanged controlled Gate remain required.
Local affected publish tests pass `43/43`, EBOM regression passes `69/69`,
complete tracked Python passes `1008/1008`, and compilation,
prototype/P0-visual/V1.2 reconciliation, prohibited-pattern and whitespace
checks pass.

## Final Gate progression and second bounded diagnostic checkpoint

Repair checkpoint `c61654c` passed complete ordinary CI `31109664009`:
repository `92643838183` passed `verify.sh`, complete non-visual E2E, current
tree and complete-history secret scans; visual `92643838306` passed `65/65`;
the controlled job correctly skipped.

The final unchanged workflow `31110350103` retained exact SHA `c61654c`. Its
fixed Bench/Site, two migrations, P5-01 through P5-04 runtime, released EBOM
replay and visual job passed. The candidate retained the repaired policy field
serialization, but the policy fixture still failed behind its closed parent
boundary as `P505_RUNTIME_POLICY_FIXTURE / BenchFixtureError /
trace-376ca4d931515968986afb62e0706987`. With the child marker closed, this
tuple cannot prove whether the remaining failure is context, namespace,
root/version insert, result or commit.

The user's standing Hard Blocker recovery authority therefore reactivates
only the existing allowlisted, response-neutral fixture substage and exception
class marker. HTTP responses, exception messages, tracebacks, paths,
credentials and fixture values remain absent. Product Requirement, API,
permission, Schema, ownership, transaction, idempotency, audit and PASS rules
are unchanged. Affected/full ordinary CI must pass before at most one
diagnostic Site run; no second product repair is selected yet.

## Second diagnostic proof and unique Datetime repair

Diagnostic checkpoint `de4f327` passed complete ordinary CI `31110928691`:
repository `92648223678` passed `verify.sh`, complete non-visual E2E, current
tree and complete-history secret scans; visual `92648223627` passed `65/65`;
the controlled job correctly skipped.

The sole diagnostic workflow `31111511594` retained exact SHA `de4f327` and
returned only `P505_RUNTIME_POLICY_VERSION_INSERT / OperationalError /
trace-f71914ae558753a1b2889bf1f6747700` after its fixed Site, migrations and
all predecessor runtime checks passed. Root insertion therefore succeeded,
and controller rule failures would be `ValidationError`, not the observed
database `OperationalError`. After canonical requester and snapshot fields,
the version fixture's only non-Frappe database value is the timezone-aware
Python `published_at` value.

Pinned Frappe commit `a3d8090` preserves Python Datetime values through
`BaseDocument.get_valid_dict()` rather than converting them to database text.
The controlled P5-01 runtime already proved that Frappe/MariaDB Datetime
persistence requires the shared space-separated, timezone-naive database
format. The publish-policy controller only validated `published_at` and
discarded the canonical return value, unlike the proven Document and EBOM
policy controllers. This uniquely explains the version-insert
`OperationalError`.

The bounded repair assigns only the existing shared
`frappe_utc_datetime_text()` result to `published_at` before persistence and
closes fixture diagnostic output. UTC meaning is unchanged. No Requirement,
API, permission, Schema, ownership, transaction, idempotency, audit or PASS
rule changes. Affected/full ordinary CI and one final unchanged controlled
Gate remain required.

## Create boundary progression and response-neutral diagnostic checkpoint

Datetime repair `25fa93e` passed complete repository ordinary CI
`31111959654`: repository job `92651747310` passed `verify.sh`, complete
non-visual E2E, current-tree and complete-history secret scans. The first
visual attempt had one isolated, frontend-unaffected 210-pixel antialiasing
difference in the legacy R1-05 Traditional Chinese 1920x1080/150% case while
the other `64/65` cases passed. A same-SHA failed-job-only rerun
`92654292840` passed the unchanged `65/65` matrix, proving a transient render
variation without changing code, snapshots or thresholds. The controlled job
remained skipped.

Final unchanged workflow `31112969969` retained exact SHA `25fa93e`. Its fixed
Bench/Site, migrations, policy fixture and all predecessor runtime boundaries
passed, proving both policy-version repairs. The first create command then
returned only `P505_RUNTIME_CREATE / HttpStatusError /
trace-900c2129c31a5b16b0e872c6f674246d`. That HTTP boundary cannot distinguish
command context, policy/released-input loading, domain construction, receipt,
request/mapping/node/result insertion, audit, seal or response reconstruction.

Under the user's standing Hard Blocker recovery authority, the diagnostic
checkpoint reuses the already proven P5-04 pattern: one exact-scope request
header enables allowlisted substage context managers that record only stage
code, validated exception class and exact synthetic trace in the server log.
The HTTP status, problem body, response headers, transaction and rollback
behavior remain unchanged. The verifier reads only a bounded tail under the
resolved disposable Bench and accepts only the exact three-key JSON record for
the request trace. Requirement, API response contract, permission, Schema,
ownership, transaction, idempotency, audit and PASS criteria are unchanged.
Affected/full ordinary CI must pass before at most one diagnostic Site; no
product repair is selected.

## Create diagnostic proof and unique receipt-seal repair

Create diagnostic checkpoint `abbfade` passed complete exact-SHA ordinary CI
`31113883296`: repository job `92658369228` passed `verify.sh`, complete
non-visual E2E, current-tree and complete-history secret scans; visual job
`92658369260` passed the unchanged `65/65` matrix; the controlled job correctly
skipped.

The sole diagnostic workflow `31114594791` retained exact SHA `abbfade`. Its
fixed Bench/Site, migrations, policy fixture and every create substage through
receipt insertion, request/mapping/node/result insertion, audit append and
response construction passed. The server emitted only
`P505_CREATE_RECEIPT_SEAL / PermissionError /
trace-2c7c41e0a54e53efb306c9117e6e280f`.

The synthetic internal actor retained the required `NPI API User` role, and
the receipt insert had already passed under the same request and write scope.
The receipt metadata explicitly grants that role both create and write, so the
observed seal-only `PermissionError` is not a missing role or a reason to widen
permissions. On the first seal, the persisted `sealed` value is still `0`,
leaving the controller's raw immutable-identity comparison as the only active
permission denial. Its sole Frappe representation-sensitive identity field is
`created_at`: the inserted document retains database text while
`get_doc_before_save()` loads a Datetime value. Comparing those raw Python
representations rejects an unchanged instant.

The bounded repair compares both `created_at` values through the existing
`utc_datetime_text()` normalization while preserving the original immutable
field set and denial message. It also closes create diagnostic activation.
There is no Requirement, API, role/permission, Schema, ownership,
transaction, idempotency, audit or PASS-rule change. Affected and complete
ordinary CI plus one final unchanged controlled Gate remain required.

## Final convergence, security advisory repair and Gate PASS

Receipt-seal repair `5dabc02` passed complete ordinary CI `31115316755`:
repository `92663220768` passed `verify.sh`, complete E2E and both secret
lanes; visual `92663220631` passed `65/65`; controlled runtime correctly
skipped.

Workflow `31115995065` then failed only while GitHub Actions was in an official
major outage. Both controlled attempts stopped in `Set up job` before checkout
with `Failed to resolve action download info` and `Service Unavailable`;
repository and visual companions passed. No product or Gate code executed in
those failed attempts.

After GitHub Actions returned to operational/monitoring, exact-SHA workflow
`31133548117` retained `5dabc02`. Controlled job `92727766901` passed the full
P5-01-through-P5-05 Site runtime and visual job `92727766890` passed `65/65`.
Repository job `92727766915` failed only because the live npm audit feed now
reported CVE-2026-59870 against transitive development dependency
`js-yaml@4.3.0`; every preceding repository test/build check passed.

The bounded security repair `7624497` changes only the lock entry to the
compatible patched `js-yaml@4.3.1`. Local audit reports zero vulnerabilities.
Exact-SHA ordinary CI `31134844746` then passed repository `92731803737`,
complete non-visual E2E/history scan and visual `92731803668` at `65/65`.

The final unchanged workflow `31135330539` retained exact SHA `7624497` with
all diagnostics closed. Repository `92733288503`, visual `92733288492` and
controlled Site `92733288519` passed. Controlled artifact `8977753018` has
GitHub digest
`sha256:bccec9800be67c9194c18508d3627839db4f7e67d0ece154b2fbe566cdb45e60`;
its extracted `result.txt` SHA-256 is
`ce1e67fa1626b730be409281b5f0421bcea6817e7043364c19456f075491f17f`
and records exact SHA `7624497`, `result=PASS` and
`scope=p5-01-through-p5-05`.

P5-05 therefore passes Level 2. `FR-DS-013` is
`TECHNICAL_VERIFIED_FOUNDATION`; real ERPNext execution and reconciliation
remain Phase 8 scope. Durable validation is
`implementation/evidence/phase-5/p5-05-validation.md`.
