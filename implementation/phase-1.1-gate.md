# Phase 1.1 Gate — BLOCKED PENDING FRESH-CONTAINER VALIDATION

The root cause of the failed target-container creation is repaired in repository
configuration, but Phase 1.1 is not `PASS`. The corrected image has not yet been
built and dynamically verified by a fresh Codespace.

## Scope

This repair changes only development-container configuration, bootstrap and
verification scripts, their tests, development documentation and Phase 1.1
evidence. It does not change React/UI, localization, product behavior, domain
rules, Frappe business modules, DocTypes, APIs, schemas, migrations, ERPNext
integration or production dependencies.

## Fresh-Codespace failure evidence

- The current environment is a newly created Codespace, not an old container
  awaiting a rebuild. `/workspaces/.codespaces/.persistedshare/RECOVERY-REASON-FILE`
  records `1302 (UnifiedContainersErrorFatalCreatingContainer)`, and the merged
  runtime config sets `CODESPACES_RECOVERY_CONTAINER=true` with the Alpine base.
- The complete creation log is available at
  `/workspaces/.codespaces/.persistedshare/creation.log`. At
  `2026-07-21T17:42:54Z`, Codespaces built the repository Dockerfile using
  `.devcontainer/Dockerfile` and repository-root context. The pinned Python
  image was available and its build stage started.
- The first Dockerfile `apt-get update` read the inherited Yarn repository. Its
  signature could not be verified because public key `62D54FD4003F6525` was
  unavailable. APT rejected the unsigned repository, the Dockerfile command
  exited 100 and Dev Containers exited 1. Codespaces then created the Alpine
  recovery container.
- Both Dev Container Features resolved successfully before Docker build. The
  initial target-container command used `--skip-post-create`, and the target
  image never finished building. Therefore the Node Feature, Docker-in-Docker
  Feature, Bench installation, Docker wait and target `postCreateCommand` were
  not the cause of this incident. The recovery container's generic
  `postCreateOutput.json` is not evidence that the target bootstrap ran.
- VS Code Codespaces logs independently report `Container build failed` and
  `Running recovery container`. No production system or credential was used.

## Root-cause repair

- The Dockerfile retains the validated immutable Python image digest, but
  removes `/etc/apt/sources.list.d/yarn.list` before the first `apt-get update`.
  This repository explicitly disables Node Feature Yarn-APT installation, so
  the removed third-party source is not required.
- `.devcontainer/devcontainer-lock.json` locks Node Feature 2.1.0 to
  `sha256:586c9a6f...b686857` and Docker-in-Docker Feature 3.0.1 to
  `sha256:ca250849...933df9`. Registry metadata confirms both official Feature
  artifacts and all configured option names. No unnecessary Feature major
  upgrade was mixed into the root-cause repair.
- Node 18.20.8 and its bundled npm 10.8.2 are now both exact cross-file pins.
  Docker 28.3.3 uses the official Moby packages and Compose v2 through the
  locked Feature. Bench 5.31.0 and Vite 5.4.14 remain exact pins; the image
  explicitly grants read/traverse/execute access to the root-owned Bench venv
  before exposing its command on the `vscode` user's PATH.
- `bootstrap-dev.sh` now validates its prerequisites, installs Vite only when
  needed, accepts a positive configurable Docker wait and defaults to 120
  seconds. A timeout prints Docker client/context, dockerd process and available
  daemon-log diagnostics, then still returns failure.
- `scripts/verify_devcontainer.py` validates JSON semantics, Dockerfile/context
  paths, the immutable base manifest, the image's `vscode` metadata, official
  Feature artifacts/options/lock digests, post-create wiring, Git executable
  modes and cross-source toolchain availability. It uses only Python standard
  library code and the official registries needed by the real build.

## Static and registry evidence — 2026-07-21 repair round 2

- `make verify-dev-config`: **PASS**. The base image manifest/digest and
  `vscode` user were verified in MCR; both Feature artifacts and digests were
  verified in GHCR; Node/npm, Moby, Bench, Vite and the pinned Frappe commit
  resolved from their official upstream metadata.
- Dev Containers CLI `upgrade --dry-run`: **PASS**. Generated Feature lock data
  exactly matched `.devcontainer/devcontainer-lock.json`.
- Dev Containers CLI `read-configuration`: **NOT EXECUTABLE in recovery**. The
  available CLI requires Docker even for that command and returned
  `spawn docker ENOENT`; the creation log already proves the actual Dockerfile,
  context, remote user and Feature resolution used by Codespaces.
- `make verify`: **PASS**. Environment configuration/registry validation and all
  18 repository tests passed, including five devcontainer-verifier tests added
  in this repair.
- `git diff --check`: must pass on the final checkpoint diff before commit.
- `make verify-dev-environment`: **EXPECTED FAIL IN RECOVERY** with
  `Required development command is missing: node` (make exit 2). The recovery
  container lacks the target Node, npm, Docker, Bench and Vite runtime. Static
  evidence cannot replace a target-container run.

Frontend, E2E, visual, localization, application permission, API/integration
and migration checks are not applicable to this environment-only root-cause
repair. Phase 3 remains paused.

## Release-gate review

Root-cause repair checkpoint: `PASS`. The diff is limited to the authorized
environment scope; no application API, schema, permission, migration,
integration, UI or localization path changed; no dependency bypass, secret,
production ID, fake success or accepted-path placeholder was introduced; and
the static/registry/repository checks pass with documented rollback.

Phase 1.1 milestone gate: `BLOCKED` pending the required fresh-container dynamic
evidence. This checkpoint PASS does not promote the Phase or authorize Phase 3.

## Pending dynamic gate

Create a fresh Codespace from the latest
`codex/npi-v1.2-implementation` branch. The new target container must then pass
`make verify-dev-environment`, `make verify` and `git diff --check` before Phase
1.1 can be marked `PASS`.

## Rollback

Revert the Phase 1.1 root-cause checkpoint and create a fresh Codespace from the
reverted branch. No database, production endpoint or ERPNext data is touched.
