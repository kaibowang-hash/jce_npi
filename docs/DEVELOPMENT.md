# Development Environment

## Supported path

GitHub Codespaces / VS Code Dev Containers is the authoritative development path. A successfully created container provides:

- Python 3.11 from the digest-pinned Debian Bookworm devcontainer image. The
  pinned image contains an obsolete Yarn APT source, which the Dockerfile
  removes from `/etc/apt/sources.list` and
  `/etc/apt/sources.list.d/*yarn*` before the first package-index refresh;
- Node.js 24.18.0 LTS and its bundled npm 11.16.0 through the pinned official Node feature, plus Yarn 1.22.22 already present in the digest-pinned base image for Frappe dependency installation;
- Docker/Moby semantic version 28.3.3 and Compose v2 through the digest-locked official Docker-in-Docker feature (the verified fresh target resolved package `28.3.3-debian12u1`, Engine/CLI `28.3.3-1` and Compose `2.40.3`);
- Frappe Bench CLI 5.31.0 and pinned uv 0.11.30 installed in its environment and exposed by post-create;
- Vite 5.4.14 and its exact esbuild 0.21.5 runtime installed by the
  idempotent post-create bootstrap with npm's strict install-script policy;
- digest-pinned MariaDB 10.6 and Redis 7.2 through repository Compose services;
- Frappe `version-15` pinned to commit `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` for local Bench initialization.

The Dev Container Features are additionally locked to their OCI digests in
`.devcontainer/devcontainer-lock.json`. The selected Frappe commit declares
Python `>=3.10,<3.15` and Node `>=18`; the pinned toolchain is within those
supported ranges. ADR-011 records the 2026-07-25 security move from the
end-of-life Node 18 baseline after a newly published High-severity
`brace-expansion` advisory. The application lock now resolves only the patched
`brace-expansion` 5.0.8, explicitly allows only the exact existing esbuild
install script and requires both complete and production-only npm audits. This
remediation does not change the accepted independent-site, React SPA or ERPNext
boundary decisions.

## Creation failure evidence

The Codespaces creation log for the 2026-07-21 fresh environment proves the
original target container failed during its Dockerfile build. The pinned base
image was found, but its Yarn repository rejected `apt-get update` with
`NO_PUBKEY 62D54FD4003F6525`; Docker build exited 100 and Codespaces then created
the Alpine recovery container with error 1302. Both Features resolved before
the build, and the target `postCreateCommand` was skipped, so neither Feature
installation nor `bootstrap-dev.sh` caused that incident.

After the repaired image built, the first target `postCreateCommand` proved a
separate lifecycle defect: invoking the Node Feature's npm through `sudo`
removed Node from the elevated PATH, so npm's `/usr/bin/env node` launcher
exited 127. The bootstrap now verifies that the Feature's remote-user global npm
prefix is writable and installs pinned Vite without privilege elevation. This
is enforced by a regression test; the exact lifecycle script and dynamic gate
passed in the fresh target container.

The repository root has no application-level Yarn requirement. Phase 3 adds an
npm-lockfile-backed SPA under `frontend/`; its exact dependencies are isolated
from the Yarn 1.x invocation used internally by the pinned Frappe Bench setup.
Node and npm come from the locked Node Dev Container Feature. The invalid Yarn
APT repository must not be restored.

The global Vite smoke installation explicitly permits only the reviewed exact
esbuild 0.21.5 postinstall and Vite's exact optional fsevents 2.3.3 install
hook; strict mode fails any newly introduced script. fsevents remains absent
on Linux. The application workspace has a separate exact `allowScripts` entry
for its locked esbuild 0.25.12 and a name-wide reviewed denial for fsevents,
including the lock's optional 2.3.2 and 2.3.3 hooks. Its checked-in `.npmrc`,
Make target and CI command enforce npm 11 strict install-script handling, and
the frontend audit also fails unless the read-only pending-script report is
empty.

## Create and verify

Create a new Codespace from the latest
`codex/npi-v1.2-implementation` branch. Wait for `scripts/bootstrap-dev.sh` to
finish. It installs Vite only when the exact version is missing, waits up to 120
seconds for Docker and prints Docker process/log diagnostics before returning a
real failure. Vite is installed through the writable remote-user npm prefix so
its Node launcher keeps the Feature PATH. It does not hide installation,
permission or daemon failures.

In the new target container run:

```text
make verify-dev-environment
make verify
```

The first command prints real versions for Node, npm, Python, Docker client and
server, Compose, Bench, uv, Yarn and Vite. It checks that Docker client/server match the
selected semantic version (allowing only the numeric packaging revision suffix),
requires the configured Compose v2 major, checks the Docker daemon and validates
Compose. It also prints the selected Frappe branch and exact commit. It does not
infer availability from configuration. The locked Docker Feature resolves the
current Moby package revision and Compose v2 patch during image creation, so
those printed values are runtime evidence, not claims of exact package/Compose
installation pins.

## Frontend install and verification

The application SPA pins its own Vite, React, Siemens iX, test and lint versions
in `frontend/package-lock.json`; the globally verified Vite 5.4.14 remains only
the Phase 1.1 environment smoke tool. Install and verify the application with:

```text
make frontend-install
make frontend-browser-install
make frontend-verify
make frontend-e2e
make frontend-visual
```

`frontend-install` uses strict `npm ci`, refuses lock drift and rejects any
install script outside the exact reviewed application allowlist. Browser installation is
a separate reproducible provisioning step because Playwright's Chromium and OS
libraries are larger than ordinary npm dependencies. `make verify` includes the
frontend type, lint, unit/coverage, production build and audit gates once the
lockfile has been installed. E2E and visual suites remain explicit commands and
also run in CI.

Before creating a container, `make verify-dev-config` checks JSON and shell
syntax; path/context resolution; tracked executable script modes; the remote
user; post-create wiring; cross-file toolchain pins; the base-image manifest and
`vscode` metadata in MCR; locked Feature artifacts and supported options in
GHCR; and the pinned Node/npm, Moby, Bench, Vite and Frappe releases in their
official registries. A missing image, Feature, script, user, version or execute
bit fails the command. The same verifier rejects any literal
`dl.yarnpkg.com` build source and the listed trust, authentication and ignored
failure bypass patterns; it also rejects removal that does not cover both
supported source locations before `apt-get update`.

## GitHub authentication and Git LFS

Codespaces' native VS Code Git credential bridge is the supported authentication path for this repository. Credentials must remain in the Codespaces/VS Code credential channel and must never be copied into repository files, scripts, command logs or chat. The expected remote is `https://github.com/kaibowang-hash/jce_npi`; environment setup must not rewrite it.

This repository does not currently use Git LFS: it has no `.gitattributes`, LFS filter attributes or LFS pointer blobs. Do not install or initialize Git LFS merely because a clone contains stale generated hooks. A verified stale clone-local LFS hook may be removed; adopting LFS later requires an approved repository attribute change and a reproducible devcontainer installation. Restore removed generated hooks only by intentionally installing and initializing Git LFS after that approval.

## Services and Frappe Bench

Start MariaDB and Redis with `make start`, inspect them with `docker compose ps`, and stop them with `make stop`. `CONFIRM_RESET=YES make reset` removes only the named development volumes and is intentionally destructive to local development data.

Initialize the pinned Frappe v15 development Bench only when backend runtime work needs it:

```text
make frappe-init
```

This creates `tmp/frappe-bench`, fetches the exact Frappe commit, runs the public `bench init` workflow and verifies the resulting Git HEAD. It refuses to overwrite an existing Bench. Site creation, production credentials and ERPNext production connectivity are not part of Phase 1.1.
The initialization deliberately skips local Redis configuration, Procfile,
automatic backup crontab and Frappe asset building: Redis/process control and
backup scheduling belong to the repository Compose/operations boundary, while
the end-user UI is the independent React SPA. Bench still installs Frappe's
declared Node dependencies with the verified Yarn 1.22.22 already present in
the digest-pinned base image; it never restores the obsolete Yarn APT source.

After the Bench exists, create or reconcile the local NPI One Site with:

```text
make frappe-site-init
make frappe-runtime-verify
```

This idempotent command starts only the repository's local MariaDB and Redis,
links both repository apps into the pinned Bench, installs `npi_core` before
`npi_integration`, migrates the Site and clears its runtime caches. It defaults
to the disposable `npi.localhost` Site and the explicit `dev-only-*` credentials
from the local Compose boundary; override them with `NPI_FRAPPE_SITE_NAME`,
`NPI_DATABASE_ROOT_PASSWORD` and `NPI_ADMINISTRATOR_PASSWORD` when needed. It
does not install ERPNext or connect to any production service.

`frappe-runtime-verify` starts a temporary local development Web process, proves
the exact `/api/npi/v1` authentication/problem contract, verifies both direct
Chinese catalogs and language persistence across later sessions, rejects an
unsupported locale without mutation, keeps the Administrator language
unchanged, deletes the disposable Website User and then stops the process. It
requires the local Site and Compose services but no ERPNext installation or
connection.

Frappe v15 reads the custom App CSV catalogs directly after cache invalidation.
Do not use `build-message-files` as a deployment/init step: in the pinned v15
implementation that command calls `rebuild_all_translation_files()` and rewrites
every installed App's source CSV from Frappe's extractor and merged translation
dictionary. It is a source-catalog regeneration command, not a non-destructive
runtime compiler.

## Rollback

Revert only the repair-round-4 checkpoint while retaining the earlier Yarn APT
source repair, then create a fresh Codespace. If that rollback would reintroduce
a known build failure, use a forward fix instead. Local Compose data remains in
named volumes unless the guarded reset command is explicitly invoked. Remove
`tmp/frappe-bench` only when its disposable local contents are no longer needed;
no production system is touched.
