# P5-05 Controlled Runtime Candidate

Recorded: `2026-08-06T13:56:00Z`

Status:
`UNIQUE POLICY-VERSION REPAIR READY FOR AFFECTED/FULL ORDINARY CI`

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
