# Last Run

- Timestamp: `2026-07-21T19:10:09Z`
- Branch: `codex/npi-v1.2-implementation`
- Starting HEAD: `2537937b7b32748d5e43bcc30fce5a313721de79`
- Starting upstream state: ahead 0 / behind 0
- Completed phase: `1.1 — Development Environment Remediation`
- Repair round: `4/5`
- Gate state: `PASS`
- Automatically activated phase: `3 — React App Shell, Siemens UI and i18n Foundation`

## Fresh-target evidence and repair

- A new Codespace successfully built the intended Debian 12 target image from
  the repaired branch; this is no longer an Alpine recovery container.
- Its automatic post-create invocation failed at `/usr/bin/env node` because
  privilege elevation stripped the Node Feature PATH from npm. The repository
  now installs fixed Vite through the verified writable remote-user npm prefix
  and statically rejects `sudo npm`.
- The target Moby package reports runtime `28.3.3-1`; the verifier now matches
  client/server against selected semantic version `28.3.3` and permits only a
  numeric packaging revision suffix. It requires Compose v2 and records observed
  package/Compose revisions without claiming installation pins the Feature does
  not provide.
- The repaired `bootstrap-dev.sh` completed as the remote user in the fresh
  target. No production service, credential, database or ERPNext endpoint was
  contacted.

## Commands and results

| Command | Result |
|---|---|
| `bash scripts/bootstrap-dev.sh` | `PASS` |
| `make verify-dev-environment` | `PASS` — complete pinned target toolchain printed |
| `make verify` | `PASS` — registry/configuration checks and 26/26 tests |
| `git diff --check` | `PASS` — exit 0, no output |

The Phase 1.1 `release-gate` result is `PASS`; exact evidence and rollback are in
`implementation/phase-1.1-gate.md`. The single recovery action is the first
Phase 3 task recorded in `NEXT_ACTION.md`.
