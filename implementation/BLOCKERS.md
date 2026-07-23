# Blockers

## Active hard blockers

None.

## User-requested delivery pause

Continuous feature implementation was paused by the user on 2026-07-23 after
the current P4-02 work was made internally consistent. This is not a Hard
Blocker and does not change Phase 3 or Phase 4 status. P4-02 remains
`IN_PROGRESS`; its final aggregate, browser, exact visual, evidence, and
release-gate steps remain open. P4-03 has not started. Resume only on explicit
user direction and from the exact checklist in `NEXT_ACTION.md`.

## Open external acceptance and reconciliation inputs

`implementation/REQUIRED_INPUTS.md` is the single complete request for external
material. Its open Phase 3 UAT/sanitized-data items keep final business
acceptance at `TECHNICAL_PASS_PENDING_UAT`; its ERPNext facts pause only work
that would otherwise guess existing customization, numbering, state, field
ownership, mapping, sandbox behavior or a real-data result. These are partial
dependencies, not a global Hard Blocker. Production ERPNext credentials and
activation remain prohibited and are not requested.

## Scoped Phase 4 rule holds

Phase 4 `P4-00` reconciled the controller/M3 Project-and-Gate boundary with Pack
trace rows that also mention portfolio, external collaboration, notifications,
ERP-owned cost, ERP-triggered creation, or external scheduling. The affected
requirements are explicitly remapped without losing their original acceptance.
Production project numbering/source rules, template/skip/duration content,
RACI-to-approval mapping, per-kind Domain WorkItem lifecycle, health/cost
thresholds, Gate waiver/invalidation authority, and project lifecycle approvals
remain Class-B holds until authoritative facts exist. Only those ambiguous
rules are held.
Generic/versioned NPI-owned Project/Gate infrastructure, explicit synthetic
fixtures, contracts, automated tests, localization, UI and documentation can
continue.

## Resolved checkpoints

- Phase 1.1 fresh target-container validation passed on 2026-07-21 after repair
  round 4.
- The first Phase 3 gate candidate had passing visual, localization, runtime,
  permission, migration and test evidence, but independent review correctly
  returned it for error, CSRF, and privacy repair before a final decision.
- Phase 3 repair round 1 closed error/trace/retry, CSRF, unexpected
  ProblemDetails, telemetry route, transaction and request-locale atomicity
  defects. Independent final review returned technical `PASS` on 2026-07-22;
  Phase 3 is `TECHNICAL_PASS_PENDING_UAT` and Phase 4 is active.
- The P4-02 checkpoint review found a forgeable unsigned Domain WorkItem cursor
  and positional backend translation placeholders. The checkpoint now signs
  every cursor field with a Site-bound domain-separated HMAC, fails closed when
  secure signing is unavailable, rejects forged/tampered/cross-Site cursors,
  uses named placeholders, and statically rejects positional translation
  placeholders. Focused tests and the repaired real Frappe runtime passed.
