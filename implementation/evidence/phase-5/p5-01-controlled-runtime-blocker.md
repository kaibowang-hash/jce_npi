# P5-01 Controlled Runtime Hard Blocker

Recorded: `2026-07-30T17:32:55Z`

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

`BLOCKED_EXTERNAL — NECESSARY GATE STILL FAILS AFTER FIVE COMPLETE REPAIR ROUNDS`

P5-01 is not `PASS`, none of its seven requirements is promoted, and P5-02
remains inactive.

## Fixed candidate and retained PASS evidence

The latest pushed candidate is
`56e1b75d6b34fd000df34d0ab70016d9163143f4`. Its normal pull-request CI run
`30565607707` passed the complete repository, `285/285` non-visual browser,
fixed-Linux visual, current-tree secret and complete branch-history secret
lanes. The affected local runtime/static regression group passed `91/91`.

These results remain reusable. They do not substitute for the required real
controlled-Site document round trip.

## Five complete controlled-runtime repair rounds

1. Run `30562284484` failed before Bench/Site/Compose/database work because
   an unnecessary Yarn global install violated npm's strict script policy.
2. Run `30563106063` installed the exact packages but failed before
   initialization because a CLI presentation string was treated as canonical
   package metadata.
3. Run `30564025523` passed tool/Bench/database guards and created the fresh
   Site, then an unterminated Bench app registry joined `frappe` and
   `npi_core`.
4. Run `30565065165` installed both apps and completed both migrations, then
   the schema fixture named obsolete `response_payload` metadata instead of
   the retained sealed `response_snapshot` and `response_sealed` contract.
5. Run `30566120000` passed the schema fixture, both migrations and all fixed
   runtime guards, then Project creation returned HTTP `422`.

Every run used only the exact development branch SHA, read-only repository
permissions and fresh disposable runner-local MariaDB/Redis state. Every
stateful run completed bounded cleanup of its containers, volumes and network.
No production Site, ERPNext, CAD/PDM or external file service was contacted.

## Fifth-round root cause

The failing fixture sends:

```text
ownerUserId = Administrator
```

The retained Project command contract requires `ownerUserId` to be a
canonical email address. The already passing Phase 4 runtime creates a
disposable email user before Project creation. Therefore the HTTP `422` is a
real fail-closed validation result, not infrastructure drift and not a reason
to weaken the Project contract.

The bounded forward repair is known: create a namespaced disposable owner
email user, use that identity in the synthetic Project command, clean it in
the verifier's bounded `finally` path, and rerun the unchanged complete
document-only Gate.

## Exhausted repair budget and single unblock action

`implementation/AUTOPILOT_CONTROLLER.md` permits up to five genuine repair
rounds and defines a necessary Gate still failing after five complete rounds
as an exhaustive Hard Blocker. Starting a sixth round without new authority
would violate that controller.

Single user action required:

`Explicitly authorize one additional bounded P5-01 controlled-runtime repair round beyond the five-round limit.`

That authority permits only the disposable-owner fixture repair described
above and the unchanged affected checks, normal CI and controlled-Site Gate.
It does not authorize a requirement, contract, permission, architecture or
PASS-criteria change.

## Authorized recovery

On 2026-07-31 local time, the user explicitly selected the exact authorization
above. The Hard Blocker remains truthful historical evidence, but its required
user action is satisfied. The single extra repair is now active and is tracked
in:

`implementation/evidence/phase-5/p5-01-controlled-runtime-extra-repair.md`

P5-01 remains incomplete. No controlled-Site PASS or P5-02 activation is
claimed by the authorization or local checks.
