# P5-01 Controlled Runtime Extra Repair

Recorded: `2026-07-30T18:09:33Z`

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

`BLOCKED_EXTERNAL — OWNER REPAIR PASSED NORMAL CI AND ADVANCED THE CONTROLLED
SITE; NEW DATETIME PERSISTENCE FAILURE EXHAUSTED THE AUTHORIZED ROUND`

This is not a P5-01 Task Gate PASS, does not promote any requirement and does
not activate P5-02. The terminal result and next bounded action are recorded
in
`implementation/evidence/phase-5/p5-01-controlled-runtime-datetime-blocker.md`.

## Authority and fixed scope

After the five-round Hard Blocker was recorded, the user explicitly selected:

`Explicitly authorize one additional bounded P5-01 controlled-runtime repair round beyond the five-round limit.`

That authority is limited to the known disposable-owner fixture correction
and the unchanged affected checks, normal CI and controlled-Site Gate. It does
not authorize a product requirement, Project contract, permission,
architecture, data-ownership or PASS-criteria change.

## Root cause and repair

The fifth controlled run reached real Project creation and correctly rejected
the fixture's non-email `ownerUserId = Administrator` with HTTP `422`. The
Project command still requires a canonical email and an enabled User.

The repair:

- adds one run-namespaced
  `npi-document-<run>-owner@example.invalid` identity;
- proves the owner and unrelated IDOR user are distinct and absent before
  setup;
- creates and validates the owner as an enabled disposable Website User with
  no System Manager privilege;
- keeps `Administrator` only as the authenticated command actor;
- sends the disposable email as the Project `ownerUserId`;
- deletes that exact owner in the fresh verifier's bounded `finally` path on
  both success and downstream failure; and
- requires the separate `replay-only` process to prove the owner remains
  absent before replaying the retained document command.

The Project contract, enabled-owner check, Project persistence, authorization,
CSRF, idempotency, route switching, document behavior and runtime shell are
unchanged.

## Changed files → affected tests

| Changed file | Affected checks |
|---|---|
| `scripts/verify_document_runtime.py` | exact fixture namespace; canonical email owner payload; disposable-user privilege validation; success/failure cleanup; cross-process cleanup assertion; retained document runtime verifier group |
| `tests/test_phase5_document_runtime_verifier.py` | owner identity and separation; exact Project payload; cleanup on success/failure; replay fail-closed behavior; retained schema/file/security/shell/manual-lane contracts |
| controller, decision, risk and evidence records | YAML/state consistency; requirement status remains pending; no P5-02 activation; whitespace and diff-scope review |

## Local verification

| Check | Result |
|---|---|
| affected runtime/verifier modules | `PASS — 91/91` |
| complete tracked repository Python tests | `PASS — 774/774` |
| Python compilation | `PASS` |
| Bash syntax for the unchanged runtime shell | `PASS` |
| prohibited backend pattern scan | `PASS — no finding` |
| V1.2 reconciliation verifier and generated trace freshness | `PASS` |
| direct `Administrator` Project-owner domain reproduction | `PASS — retained VALIDATION_FAILED behavior` |
| `git diff --check` | `PASS` |

The local host has no fixed Bench/Docker runtime, so no real migration or
controlled-Site result is claimed here. The unchanged next validation is
normal CI followed by:

```text
bash scripts/verify-frappe-runtime.sh --document-only
```

## Terminal result of the authorized round

The candidate was committed and pushed at
`a2d98e23f7dd4d37cb66ae220beade32123bd567`. Normal CI run `30569830739`
passed the complete repository, browser, visual and both pull-request secret
lanes on that exact SHA.

Manual run `30570343315` used the same SHA. It passed exact runtime setup,
both app installations, both migrations, schema verification, the disposable
owner lifecycle, Project creation, and Document Policy root and draft
creation. Publishing the draft then returned HTTP `500`. The workflow removed
its ephemeral containers, volumes and network.

The owner correction is therefore effective, but the necessary Gate remains
failed at a new downstream Frappe Datetime persistence boundary. The single
authorized extra round is exhausted. Exact analysis, bounded solution and the
single required user action are preserved in the datetime blocker evidence
named above.

Only a newly authorized repair and a real PASS of the unchanged controlled
Site Gate may resume the final P5-01 reviews and Level 2 Task Gate.
