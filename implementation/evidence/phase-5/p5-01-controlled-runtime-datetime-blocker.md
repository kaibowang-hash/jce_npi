# P5-01 Controlled Runtime Datetime Persistence Hard Blocker

Recorded: `2026-07-30T18:36:25Z`

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

`BLOCKED_EXTERNAL — THE SINGLE USER-AUTHORIZED EXTRA REPAIR ROUND IS
EXHAUSTED AND THE NECESSARY CONTROLLED-SITE GATE STILL FAILS`

P5-01 is not `PASS`, none of its seven requirements is promoted, and P5-02
remains inactive.

## Exact candidate and retained PASS evidence

The disposable-owner repair candidate is:

`a2d98e23f7dd4d37cb66ae220beade32123bd567`

Normal pull-request CI run `30569830739` passed on that exact SHA:

- repository job `90963427176`: complete repository verification, browser
  E2E, current-tree Gitleaks and complete pull-request branch-history scan
  `PASS`;
- visual job `90963427174`: governed fixed-Linux visual matrix `PASS`; and
- the manual-only controlled runtime job was correctly skipped for the
  pull-request event.

The local affected runtime/verifier group remains `91/91 PASS`, and the exact
tracked repository Python suite remains `774/774 PASS`.

## Authorized controlled-Site result

Manual workflow-dispatch run `30570343315` used the same exact SHA and
read-only repository permissions.

- repository job `90965176387`: `PASS`;
- visual job `90965176301`: `PASS`;
- controlled runtime job `90965176352`: `FAIL`.

The controlled job passed:

1. exact Bench, uv and Yarn checks;
2. pinned Frappe Bench initialization;
3. guarded disposable MariaDB/Redis and fixed `npi.localhost` Site creation;
4. both NPI app installations;
5. both required migrations;
6. the controlled database identity guard;
7. the corrected nine-DocType schema fixture;
8. disposable canonical-email owner creation and validation;
9. Project creation using that owner;
10. Document Policy root creation; and
11. Document Policy Version draft creation.

The next operation, publishing that exact draft through `PUT
/api/resource/NPI%20Document%20Policy%20Version/<version-key>`, returned HTTP
`500`. The verifier stopped at
`ensure_document_policy`; no controlled Document, lock, revision or File
Revision result is claimed. The owner cleanup completed through the bounded
`finally` path, and the workflow cleanup removed both ephemeral containers,
both volumes and the runner-local network.

This progression proves the authorized owner repair worked. The failure is a
new downstream persistence defect, not a recurrence of the Project-owner
validation error and not hosted-runner setup drift.

## Code-backed root-cause analysis

The highest-confidence root cause is the P5 document controllers' use of a
canonical API timestamp string as a Frappe `Datetime` storage value:

- `NPIDocumentPolicyVersion._apply_policy()` assigns
  `utc_datetime_text(datetime.now(UTC), ...)` to `published_at`;
- that helper emits canonical ISO UTC text such as
  `2026-07-30T18:27:54.123456Z`;
- the pinned Frappe commit
  `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` defines database datetime text as
  `%Y-%m-%d %H:%M:%S.%f`;
- its `BaseDocument.get_valid_dict(convert_dates_to_str=True)` converts actual
  `datetime` objects but passes an already-string value through unchanged; and
- already runtime-proven policy controllers in this repository use
  `frappe.utils.now_datetime()` or the local
  `frappe_utc_datetime_text()` storage adapter.

The policy publication is the first P5 runtime path that writes one of these
values. The same canonical helper is also assigned to other P5 Frappe
`Datetime` fields, so a policy-only workaround would merely defer the shared
root cause to Document, revision, lock, share or idempotency persistence.

The HTTP helper currently reports only the status at this assertion and the
ephemeral server log did not retain the response exception body. Therefore
the forward repair must also expose a bounded, sanitized failure detail
(`exc_type` and controlled server message only) so the next run proves the
exact server failure without leaking request data, cookies or credentials.
The code and fixed-Frappe persistence path make Datetime formatting the
primary root cause; the next controlled run remains the authority for the
terminal runtime result.

## Bounded solution

The recommended repair is one root-cause batch:

1. split canonical API/snapshot UTC formatting from Frappe database datetime
   formatting;
2. persist every P5 Document DocType `Datetime` field through one reviewed
   Frappe-compatible adapter while retaining canonical `Z` timestamps in
   domain snapshots and API responses;
3. add exact controller tests for aware/naive round trips, storage format,
   immutable comparison and all affected datetime fields;
4. add fail-closed sanitized HTTP failure diagnostics to the runtime verifier;
5. run the affected checks, complete normal CI and the unchanged
   `bash scripts/verify-frappe-runtime.sh --document-only` Gate once; and
6. promote nothing until fresh execution, replay, route recovery and cleanup
   all pass.

A narrow change to only `published_at` is rejected because the same storage
root exists in the downstream controlled-document fields. Weakening MariaDB,
the document contract, immutable snapshots, permissions or the Gate is also
rejected.

## Exhausted authority and single unblock action

The user authorized exactly one extra repair round, limited to the disposable
owner correction and its unchanged Gate. That round was implemented, passed
normal CI and ran the real controlled Site; it is now exhausted. Starting a
new product-code repair or another dispatch would exceed the granted
authority and the controller's repair limit.

Single user action required:

`Explicitly authorize one additional bounded P5-01 controlled-runtime repair
round for the shared Frappe Datetime persistence root cause and sanitized
diagnostic hardening beyond the exhausted extra round.`

That authorization would permit only the bounded solution above and the
unchanged checks/Gate. It would not authorize a requirement, API contract,
permission, architecture, data-ownership, timestamp semantic or PASS-criteria
change.
