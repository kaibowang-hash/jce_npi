# Phase 1.1 Gate — BLOCKED

The configuration-remediation checkpoint is complete, but the runtime gate cannot pass before GitHub Codespaces rebuilds the devcontainer.

## Scope

Only development environment configuration, bootstrap/verification scripts, CI static checks, Make targets, status and development documentation changed. No React, UI, Frappe business module, DocType, API, schema, migration or production dependency was added.

## Static evidence

- `make verify-dev-config`: validates devcontainer JSON, shell syntax, mandatory version pins, official feature references, Frappe commit shape and Compose service/loopback bindings.
- `make verify`: includes the static environment configuration gate and the existing repository tests.
- `git diff --check`: validates patch whitespace.
- Current-runtime probe: Node, npm, Docker CLI, Bench and Vite are missing; Python is 3.12.13. This proves the active container is the pre-remediation environment and prevents a false PASS.

## Latest verification attempt — 2026-07-21

- `make verify-dev-environment`: **FAILED** with `Required development command is missing: node` (exit 2). Direct probes also found npm, Docker CLI and Bench unavailable; Python reports 3.12.13 instead of the pinned 3.11 runtime.
- `make verify`: **PASSED**. Development configuration validation and all 13 repository tests passed.
- Repair round: 1 of 5. No in-place tool installation was attempted because it would not validate the committed devcontainer build and would undermine the approved reproducible environment.
- Required next action: run **Codespaces: Rebuild Container** against the committed `.devcontainer/devcontainer.json`, then rerun both verification commands.

## Pending dynamic evidence

After **Codespaces: Rebuild Container**, `make verify-dev-environment` must verify actual Node 18.20.8, npm 10.x, Python 3.11, Docker 28.3.3 with Compose v2 and a responding daemon, Bench 5.31.0, Vite 5.4.14, valid Compose configuration and the pinned Frappe v15 commit. The gate remains **BLOCKED** until that command passes in the rebuilt container.

Frontend, E2E, visual, i18n, application permission, API/integration and migration checks are not applicable to this environment-only checkpoint. No production endpoint or ERPNext credential is used.

## Rollback

Revert the Phase 1.1 checkpoint and rebuild the Codespace. Named local database/cache volumes are preserved unless the separately guarded reset target is explicitly invoked.
