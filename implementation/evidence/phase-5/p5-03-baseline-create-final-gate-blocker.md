# P5-03 Baseline-Create Final Gate Blocker

Recorded: `2026-08-03T02:08:59Z`

Status:
`BLOCKED_EXTERNAL — NO P5-03 PASS`

Requirement:
`FR-DS-006`

Recovered base:
`a1d84294641cb0b8cf71002c3d3557cb6b485ce7`

Repaired candidate:
`15abf26834027045ccb98e5167a45390e94cb32b`

## Bounded diagnostic sequence

The recovery checkpoint retained ordinary CI `30761151383`, diagnostic run
`30761455482` and its safe phase-level tuple without claiming a P5-03 `PASS`.
The user then authorized at most two additional diagnostic-only controlled
Sites and one extra strictly bounded baseline-create repair exception without
changing the controller's global five-round rule.

The executed sequence was:

1. Diagnostic checkpoint `6b354be` passed affected tests and complete ordinary
   CI `30776232703`. Diagnostic-only run `30776554186` returned only
   `P503_BASELINE_CREATE_MEMBER_RESOLVE /
   DocumentBaselineInputUnavailable /
   trace-ed19a08e78a2589bb6251a09a7af5a17`.
2. Behavior-neutral refinement `10a889e` passed affected tests and complete
   ordinary CI `30777077077`. The second and final diagnostic-only run
   `30777405187` returned only
   `P503_BASELINE_CREATE_MEMBER_RELEASE_LINEAGE /
   DocumentBaselineInputUnavailable /
   trace-0e5e8f157cb05c66935396e6bdae896f`.

No exception text, traceback, request, response, Cookie, credential, business
data or storage path was used as evidence.

## Unique root and bounded repair

The second tuple isolated the release-lineage predicate group. Static
cross-validation uniquely resolved its inconsistent comparison:

- `FR-DS-006` and the Phase 5 Requirement anchor require an immutable exact
  released-revision/File/hash package.
- OpenAPI defines `expectedReleaseSnapshotHash` as the exact release-transition
  snapshot and explicitly distinguishes it from the original reviewed File
  evidence snapshot.
- `NPI Document Lifecycle Event.evidence_snapshot_hash` and
  `NPI Document Revision Lifecycle.release_snapshot_hash` are real retained
  fields; the release domain constructs the `released` event with the release
  snapshot.
- `NPI Document Review Cycle.review_evidence` independently freezes the exact
  reviewed revision/File evidence.
- Existing DocType permissions, NPI ownership, Project scope, locks and the
  receipt → baseline → member → audit → response → receipt-seal transaction
  order require no change.

The resolver compared the released event's release snapshot with the
independent review-evidence snapshot. Repair `15abf26` changed only that one
comparison to the lifecycle release snapshot. It did not change any
Requirement, API, permission, Schema, ownership, lock, version, audit,
idempotency, transaction order or PASS criterion.

Affected P5 Document tests passed `167/167`. Complete ordinary CI
`30777828197` passed repository, E2E, security and fixed-Linux visual lanes on
the exact repaired candidate. The final verifier path no longer sent the
baseline-create diagnostic header.

## Final unchanged controlled-Site Gate

The single reserved final workflow was `30778190537`, exact SHA `15abf26`.
The repository, E2E, security and visual jobs passed. The controlled job
passed exact runtime-tool verification, pinned Bench initialization, the fixed
disposable Site, both app migrations and bounded cleanup. Its normal verifier
failed and emitted only the existing closed tuple:

- stage code: `P503_BASELINE_CREATE_RESPONSE_CONTRACT`
- verified exception type: `RuntimeError`
- exact trace ID: `trace-062ce39fc49457a384bc1acba7afd785`

The response-contract stage contains multiple exact identity, policy, member,
File, privacy and replay predicates. This tuple does not uniquely prove which
predicate failed. The authorized two diagnostic dispatches, one extra bounded
product-root exception and one final unchanged Gate are exhausted. A second
final dispatch or a speculative response repair is not authorized.

## Controller conclusion

P5-03 is `BLOCKED_EXTERNAL`, not `PASS`. Its Level 2 Task Gate was not run.
P5-04, P5-05 and Phase 6 remain inactive. The global five-product-root rule is
unchanged, with `2b067c1` still recorded as the fifth ordinary product-root
repair and `15abf26` recorded only as the exhausted extra bounded exception.

The only safe resume path is new explicit authority limited to closed
response-contract predicate diagnostics, with affected tests and complete
ordinary CI before at most one diagnostic-only controlled Site, repair of only
one uniquely proved predicate, and one new final unchanged Gate. All frozen
product and transaction invariants remain in force.

The pre-existing dirty `implementation/LAST_RUN.md` and all other user workspace
changes remain protected and are not part of this evidence checkpoint.
