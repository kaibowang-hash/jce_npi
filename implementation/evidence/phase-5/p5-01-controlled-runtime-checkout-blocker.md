# P5-01 Controlled Runtime Checkout Diagnostic Hard Blocker

Recorded: `2026-07-30T19:18:48Z`

Task:
`P5-01 — Document and design revision`

Requirements:

- `FR-DS-001`
- `FR-DS-003`
- `FR-DS-004`
- `FR-DS-007`
- `FR-DS-008`
- `FR-DS-009`
- `FR-DS-014`

Result:

`BLOCKED_EXTERNAL — THE AUTHORIZED DATETIME REPAIR DISPATCH IS EXHAUSTED AND
THE NECESSARY CONTROLLED-SITE GATE FAILS AT DOCUMENT CHECKOUT`

P5-01 is not `PASS`, none of its seven requirements is promoted, and P5-02
remains inactive.

## Exact candidate and reusable PASS evidence

The bounded shared-Datetime repair candidate is:

`7aa14edbdd2e484784cee6a8ec52adef4f6bf328`

Normal pull-request CI `#98`, run `30573186630`, passed on that exact SHA:

- repository job `90974843950`: complete repository verification, `778/778`
  tracked Python tests, `285/285` non-visual browser checks, `2,860` direct
  English sources with complete `zh`/`zh-TW`, both zero-vulnerability audits,
  current-tree Gitleaks and complete pull-request history scan `PASS`;
- visual job `90974843881`: fixed-Linux `24/24 PASS`; artifact
  `8771657987`, digest
  `334073ee8ccce3eb9ccffdd9ad005e70b477673fb27df1ccdf0b83e799aa315d`;
  and
- the manual-only controlled runtime job was correctly skipped.

Local affected evidence remains reusable: focused controller/runtime
diagnostics `23/23 PASS`, complete P5 document group `77/77 PASS`, complete
tracked Python `778/778 PASS`, compilation, reconciliation, YAML structure,
prohibited-pattern and whitespace checks `PASS`.

## Single authorized controlled-Site result

Manual workflow dispatch `#99`, run `30573778175`, used the same exact SHA.

- controlled runtime job `90976852494`: `FAIL`;
- visual job `90976852555`: `PASS`; and
- repository job `90976852567`: `PASS`; and
- overall workflow conclusion: `FAIL`, solely because the required controlled
  runtime job failed.

The controlled runtime job passed:

1. exact Bench, uv and Yarn checks;
2. pinned Frappe Bench initialization;
3. guarded disposable MariaDB/Redis and fixed `npi.localhost` Site creation;
4. both NPI app installations;
5. both required migrations;
6. the exact database identity and nine-DocType schema guards;
7. disposable canonical-email owner, Project and Document Policy setup;
8. Document Policy publication, which was the previous failure;
9. controlled document creation; and
10. immediate document command idempotency replay.

The next operation, `POST
/api/npi/v1/projects/<project>/documents/<document>:check-out`, returned HTTP
`500`. The verifier stopped at `validate_document_workspace`; no active-lock,
revision, private-file, route-recovery or second-process replay result is
claimed.

The job cleanup succeeded and removed both ephemeral containers, both volumes
and the runner-local network.

## Reconciled blocker analysis

The prior shared Frappe Datetime persistence root is closed. The same
controlled Gate now passes policy publication and reaches document checkout.
This is a new downstream failure, not the old policy publication defect,
Project-owner validation, schema inventory or runner setup drift.

The checkout request has four relevant server boundaries:

1. append the immutable acquisition `NPI Document Lock Event`;
2. apply and save the current-lock projection on `NPI Controlled Document`;
3. append the acquisition audit; and
4. rebuild and seal the document-workspace response.

The current log proves only that one of these boundaries produced an
unexpected server exception. The runtime verifier's sanitized diagnostic
helper was added to policy publication but the generic
`validate_document_workspace` assertion still reports only the HTTP status.
The ephemeral server state was correctly destroyed, so no retained log can
now distinguish the four candidates.

It would be evidence drift to claim that lock projection or a remaining
Datetime field is the proven root. It would also be unsafe to weaken the
transaction, immutable event, exact projection, audit, idempotency or response
requirements to make the Gate pass.

## Bounded solution

The next safe repair must:

1. reuse the existing whitelist and length bounds to expose only the
   controlled response exception type/message at the document-workspace
   assertion;
2. run affected verifier tests and normal CI;
3. execute one unchanged controlled-Site Gate to obtain the exact checkout
   exception;
4. fix only the proven checkout root, with direct controller/repository tests;
5. rerun affected checks and complete normal CI; and
6. execute one final unchanged controlled-Site Gate.

If the first diagnostic execution can be combined with a deterministic
pre-Gate reproduction inside the same fresh Site and the proven fix, only one
final Gate dispatch is needed. In all cases, no response may expose traceback,
request payload, cookies, credentials, raw exception objects or unbounded
server text.

No Requirement, API contract, permission, architecture, data ownership,
schema, timestamp semantic or PASS criterion may change.

## Exhausted authority and single unblock action

The user authorized exactly one additional shared-Datetime repair and one
unchanged controlled-Site dispatch. That repair passed normal CI, and its
single dispatch produced the checkout failure above. The authorization is now
exhausted.

Single user action required:

`Explicitly authorize one additional bounded P5-01 controlled-runtime repair
round for the post-Datetime document checkout HTTP 500, including extending
sanitized diagnostics to the document-workspace boundary, one diagnostic-only
controlled-Site dispatch, fixing only the proven checkout transaction root
cause, affected tests and normal CI, and one final unchanged controlled-Site
Gate.`

Until then the controller status is `BLOCKED_EXTERNAL`.
