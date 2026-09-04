# Phase 1.1 Gate — PASS

Phase 1.1 repaired and dynamically verified the authoritative GitHub
Codespaces / VS Code Dev Container path. The final evidence comes from a fresh
Debian 12 target container created from
`codex/npi-v1.2-implementation`; configuration inspection alone was not used to
claim success.

## Scope and acceptance

The change is limited to the development-container build/lifecycle scripts,
their version model and tests, development documentation and controller
evidence. It does not change React/UI, localization behavior, domain rules,
Frappe business modules, DocTypes, APIs, schemas, migrations, ERPNext
integration or any production system.

Acceptance required all of the following in the rebuilt target container:

- the target Debian image rather than the Alpine recovery image;
- exact Node, npm, Yarn, Python, Bench, uv and Vite evidence; Docker client/server evidence
  matching the selected semantic version; actual Compose v2 evidence; and the
  selected Frappe branch and commit;
- a healthy Docker daemon and valid repository Compose configuration;
- passing repository/static/registry tests and `git diff --check`;
- no APT trust bypass, ignored failure, temporary host install or fake success.

## Repair evidence

Repair rounds 1–3 fixed the original Codespaces build failure. The pinned base
image inherited an unused Yarn APT source whose signing key was unavailable.
The Dockerfile now removes that source from both supported locations before its
first APT refresh, keeps signature verification enabled, retains the verified
base-image digest, locks both official Feature artifacts and rejects regression
patterns in the repository verifier.

The rebuilt target then exposed two facts unavailable in the recovery
container:

1. `postCreateCommand` invoked `bootstrap-dev.sh`, but `sudo npm` sanitized the
   Node Feature PATH. npm's `/usr/bin/env node` launcher exited 127 before Vite
   installation. Repair round 4 resolves and checks the writable npm global
   prefix owned by the remote `vscode:nvm` user and installs the exact Vite
   version without privilege elevation. A regression test rejects the unsafe
   `sudo npm` form.
2. The Docker Feature selector `28.3.3`, installed Moby package
   `28.3.3-debian12u1`, and client/server runtime `28.3.3-1` are related but not
   identical strings. The verifier now requires client/server to match the
   selected semantic version with only a numeric package-revision suffix. The
   configured Compose selector remains v2; the fresh runtime reported `2.40.3`.
   Neither observed package revision is misrepresented as an exact installation
   pin.

The repaired lifecycle script was rerun as the remote user in the same fresh
target container and completed successfully. No production dependency, secret,
ERPNext endpoint or database was used.

## Reproducible gate evidence — 2026-07-21

| Command | Result | Evidence |
|---|---|---|
| `bash scripts/bootstrap-dev.sh` | **PASS** | Idempotent post-create path completed; Docker daemon ready; dynamic verifier passed |
| `make verify-dev-environment` | **PASS** | Node `v18.20.8`; npm `10.8.2`; Python `3.11.13`; Docker client/server `28.3.3-1`; Compose `2.40.3`; Bench `5.31.0`; Vite `5.4.14`; Frappe `version-15` at `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` |
| `make verify` | **PASS** | Pinned base/Feature/tool registry checks and 26/26 repository tests passed |
| `git diff --check` | **PASS** | Exit 0, no output |

## Revalidation addendum — 2026-07-22

The initialized local Bench exposed two development-only prerequisites used by
Frappe's public initialization path: Yarn for Frappe's declared frontend
dependencies and uv for the pinned Bench environment. The repeatable lifecycle
now verifies Yarn `1.22.22`, pins and exposes uv `0.11.30`, and initializes the
Frappe checkout without creating a second Redis/process-control boundary,
modifying the user's backup crontab or building the Desk assets that are not the
NPI One end-user UI. The initialized Frappe checkout is on `version-15` at the
approved commit `a3d8090ba80cb91d3ed72ea90bec67df201db5c1`.

The same target container was revalidated after this follow-up:

| Command | Result | Evidence |
|---|---|---|
| `make verify-dev-environment` | **PASS** | Yarn `1.22.22` and uv `0.11.30` were printed in addition to the previously accepted toolchain |
| `make verify` | **PASS** | Registry/configuration checks and 27/27 repository tests passed |
| `git diff --check` | **PASS** | Exit 0, no output |

This addendum changes only reproducible development initialization. It does not
create a Site, connect to ERPNext, install a production dependency or alter the
Phase 1.1 `PASS` decision.

Frontend application, E2E, visual, localization, application permission,
business API/integration and migration checks are not applicable to this
environment-only remediation. Those checks remain mandatory in the phases that
change the corresponding surfaces.

## Release-gate review

**PASS.** The diff is confined to the authorized environment scope. It adds no
application dependency, core patch, direct database access, permission bypass,
secret, production identifier, destructive operation, accepted-path TODO,
silent failure or fake success. Exact failures remain visible and non-zero.
Rollback is configuration-only and documented.

Phase 1.1 is complete. Automatic transition activates Phase 3.

## Rollback

Revert only this repair-round-4 checkpoint while retaining the earlier Yarn APT
source repair, then create a fresh Codespace. Named local Compose volumes are
unchanged unless a user separately runs the guarded reset command. No production
or ERPNext data is touched. If rollback would reintroduce a known build failure,
use a forward fix instead.

## Node 24 security revalidation addendum — 2026-07-25

ADR-011 supersedes the historical Node 18/npm 10 runtime lines above with the
supported security baseline Node `v24.18.0` and bundled npm `11.16.0`. The
base-image digest, locked Node and Docker Feature artifacts, Python, Docker,
Bench, uv, Vite and Frappe selections remain governed by the same Phase 1.1
controls. The historical evidence is retained as evidence of the original
repair; it is not the current toolchain.

An actual fresh privileged devcontainer target was created from the pinned
definition at `2026-07-25T07:39:09Z`. Its retained disposable container identity
is `ec87589840647a343123667c386f0f9ff5a9e34fb14e7f0af158c5d766061cb4`
with label `npi.fresh-target=p4-04-node24`. In that target:

- the global Vite/esbuild installation was removed and the repaired bootstrap
  proved the missing-state path with npm's strict script policy, exact
  `esbuild@0.21.5`, and only the exact optional `fsevents@2.3.3` hook;
- a second bootstrap proved idempotence without reinstalling the tools;
- the formal dynamic environment gate passed; and
- the target was stopped, not deleted, after verification.

The target was restarted and revalidated again against the final working tree:

| Command | Result | Evidence |
|---|---|---|
| `bash scripts/bootstrap-dev.sh` | **PASS** | Idempotent lifecycle; Docker readiness and the complete dynamic verifier passed |
| `make verify-dev-environment` | **PASS** | Node `v24.18.0`; npm `11.16.0`; Yarn `1.22.22`; Python `3.11.13`; Docker client/server `28.3.3-1`; Compose `2.40.3`; Bench `5.31.0`; uv `0.11.30`; Vite `5.4.14`; esbuild `0.21.5`; Frappe `version-15` at `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` |

The official Linux x64 Node archive used for the independent application Gate
was also checked against Node's published `SHASUMS256.txt`; both reported
`55aa7153f9d88f28d765fcdad5ae6945b5c0f98a36881703817e4c450fa76742`.
Application clean-install, audit and browser evidence belongs to the P4-04
release record rather than this environment-only addendum.

Rollback must not restore Node 18 or another end-of-life or known-vulnerable
runtime. Any replacement must select a supported LTS line and repeat the same
registry, missing-state bootstrap, idempotence and fresh-target dynamic gates.
