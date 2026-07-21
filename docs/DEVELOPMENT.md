# Development Environment

## Supported path

GitHub Codespaces / VS Code Dev Containers is the authoritative development path. A successfully created container provides:

- Python 3.11 from the digest-pinned Debian Bookworm devcontainer image. The
  pinned image contains an obsolete Yarn APT source, which the Dockerfile
  removes from `/etc/apt/sources.list` and
  `/etc/apt/sources.list.d/*yarn*` before the first package-index refresh;
- Node.js 18.20.8 and npm 10.8.2 through the pinned official Node feature;
- Docker/Moby semantic version 28.3.3 and Compose v2 through the digest-locked official Docker-in-Docker feature (the verified fresh target resolved package `28.3.3-debian12u1`, Engine/CLI `28.3.3-1` and Compose `2.40.3`);
- Frappe Bench CLI 5.31.0 installed in the image;
- Vite 5.4.14 installed by the idempotent post-create bootstrap;
- digest-pinned MariaDB 10.6 and Redis 7.2 through repository Compose services;
- Frappe `version-15` pinned to commit `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` for local Bench initialization.

The Dev Container Features are additionally locked to their OCI digests in
`.devcontainer/devcontainer-lock.json`. The selected Frappe commit declares
Python `>=3.10,<3.15` and Node `>=18`; the pinned toolchain is within those
supported ranges. This remediation does not change the accepted independent-site,
React SPA or ERPNext boundary decisions.

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

The repository contains no `package.json`, Yarn lockfile, `.yarnrc` or other
application-level Yarn requirement. Node and npm come from the locked Node Dev
Container Feature. If an approved future toolchain requires Yarn, it must use a
fixed Corepack or controlled npm installation after that Feature; the invalid
Yarn APT repository must not be restored.

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
server, Compose, Bench and Vite. It checks that Docker client/server match the
selected semantic version (allowing only the numeric packaging revision suffix),
requires the configured Compose v2 major, checks the Docker daemon and validates
Compose. It also prints the selected Frappe branch and exact commit. It does not
infer availability from configuration. The locked Docker Feature resolves the
current Moby package revision and Compose v2 patch during image creation, so
those printed values are runtime evidence, not claims of exact package/Compose
installation pins.

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

## Rollback

Revert only the repair-round-4 checkpoint while retaining the earlier Yarn APT
source repair, then create a fresh Codespace. If that rollback would reintroduce
a known build failure, use a forward fix instead. Local Compose data remains in
named volumes unless the guarded reset command is explicitly invoked. Remove
`tmp/frappe-bench` only when its disposable local contents are no longer needed;
no production system is touched.
