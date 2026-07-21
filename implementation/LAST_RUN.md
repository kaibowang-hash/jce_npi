# Last Run

- Timestamp: `2026-07-21T18:28:15Z`
- Branch: `codex/npi-v1.2-implementation`
- Starting HEAD: `3b3c965876ad5b4254fc5a1fe28e55169020a1b4`
- Starting upstream state: ahead 0 / behind 0
- Phase: `1.1 — Dev Container Root-Cause Repair`
- Repair round: `2/5`
- Gate state: `BLOCKED_FRESH_CODESPACE_DYNAMIC_VALIDATION`

## Root-cause evidence

- This is a fresh Codespace in an Alpine 3.23.5 recovery container. Codespaces
  persisted error `1302 (UnifiedContainersErrorFatalCreatingContainer)` and set
  `CODESPACES_RECOVERY_CONTAINER=true`.
- The complete creation log at
  `/workspaces/.codespaces/.persistedshare/creation.log` proves the repository
  Dockerfile was selected with repository-root build context. The pinned base
  image was found, but its inherited Yarn APT source failed signature
  verification with `NO_PUBKEY 62D54FD4003F6525`; `apt-get update` exited 100,
  Docker build failed and Codespaces launched recovery.
- Both configured Features resolved before the failure. The target image never
  completed and its post-create command did not run. The incident was therefore
  not caused by Feature installation, Bench, Vite or Docker readiness waiting.
- VS Code Server and Codespaces logs independently record `Container build
  failed` and `Running recovery container`.

## Repository repair

- The Dockerfile removes the unused Yarn APT source before package refresh while
  retaining the MCR-verified immutable Python image digest.
- Node and Docker-in-Docker official Feature artifacts are locked to verified
  OCI digests. Configured options were checked against each artifact's own
  `devcontainer-feature.json`.
- The base metadata supplies `vscode` plus common remote-user utilities, and the
  root-owned Bench venv is explicitly readable/executable by that user.
- npm is exactly pinned to the 10.8.2 version bundled with Node 18.20.8.
- Post-create bootstrap validates prerequisites, installs only a missing/mismatched
  Vite, waits up to 120 seconds for Docker and emits diagnostics before a real
  timeout failure.
- A standard-library verifier now rejects invalid JSON, missing Dockerfile or
  context, unavailable base images, invalid Feature references/options/digests,
  missing or non-executable scripts, wrong remote user and inconsistent or
  unavailable toolchain pins.

## Commands and results

| Command | Result | Evidence |
|---|---|---|
| `make verify-dev-config` | `PASS` | MCR base/digest/user, GHCR Feature locks/options and official tool metadata verified |
| `make verify-devcontainer` | `PASS` | standalone registry and semantic verifier passed |
| Dev Containers CLI `upgrade --dry-run` | `PASS` | generated Feature lock exactly matched the committed lockfile |
| Dev Containers CLI `read-configuration` | `NOT EXECUTABLE IN RECOVERY` | bundled CLI attempted `docker ps` and returned `spawn docker ENOENT`; creation log supplies actual creation-path evidence |
| `make verify` | `PASS` | configuration/registry gate and 18/18 repository tests passed |
| `git diff --check` | `PASS` | exit 0, no output |
| `make verify-dev-environment` | `EXPECTED FAIL IN RECOVERY` | `Required development command is missing: node` (make exit 2) |

The `release-gate` review is `PASS` for this root-cause repair checkpoint and
`BLOCKED` for the Phase 1.1 milestone until fresh-container dynamic evidence is
available.

The pre-existing unstaged `.gitignore` duplicate entry remains user-owned and is
not part of this checkpoint. `REQUIREMENT_TRACEABILITY.csv` remains unchanged
because it has no Phase 1.1 runtime row. No production endpoint, credential,
database, ERPNext system or product/UX/localization/domain requirement was
changed.

Phase 1.1 is not `PASS`. The single next action is recorded in
`NEXT_ACTION.md`.
