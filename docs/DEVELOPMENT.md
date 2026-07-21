# Development Environment

## Supported path

GitHub Codespaces / VS Code Dev Containers is the authoritative development path. The rebuilt container provides:

- Python 3.11 from the digest-pinned Debian Bookworm devcontainer image;
- Node.js 18.20.8 and npm 10 through the pinned official Node feature;
- Docker Engine/CLI 28.3.3 and Compose v2 through the pinned official Docker-in-Docker feature;
- Frappe Bench CLI 5.31.0 installed in the image;
- Vite 5.4.14 installed by the idempotent post-create bootstrap;
- digest-pinned MariaDB 10.6 and Redis 7.2 through repository Compose services;
- Frappe `version-15` pinned to commit `a3d8090ba80cb91d3ed72ea90bec67df201db5c1` for local Bench initialization.

The selected Frappe commit declares Python `>=3.10,<3.15` and Node `>=18`; the pinned toolchain is within those supported ranges. This remediation does not change the accepted independent-site, React SPA or ERPNext boundary decisions.

## Rebuild and verify

After checking out the Phase 1.1 checkpoint in Codespaces:

1. Open the Command Palette.
2. Run **Codespaces: Rebuild Container**. If that command is not shown, run **Dev Containers: Rebuild Container**.
3. Wait for `scripts/bootstrap-dev.sh` to finish. A failure is a failed environment build; do not continue to Phase 3.
4. In the rebuilt terminal run:

```text
make verify-dev-environment
make verify
```

The first command prints real versions for Node, npm, Python, Docker, Compose, Bench and Vite, checks the Docker daemon and validates Compose. It also prints the selected Frappe branch and exact commit. It does not infer availability from configuration.

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

Revert the Phase 1.1 checkpoint and rebuild the Codespace. Local Compose data remains in named volumes unless the guarded reset command is explicitly invoked. Remove `tmp/frappe-bench` only when its disposable local contents are no longer needed; no production system is touched.
