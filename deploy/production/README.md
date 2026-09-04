# LaunchFlow production deployment

This deployment runs one independent Frappe v15 Site and database for NPI One.
Only `npi_core` and `npi_integration` are installed on the Site. ERPNext is not
installed, contacted, or modified. Runtime-fixture environment variables and
the disposable marker are absent, and the production ERP authorization ingress
remains disabled.

## Immutable release

Build only from a clean exact checkout:

```text
sudo deploy/production/scripts/build-release.sh
```

The image embeds both the repository SHA and the pinned Frappe commit in OCI
labels. `production.env` selects the exact backend and SPA image tags.

## Server-only configuration

`/etc/launchflow/production.env` is root-owned mode `0600`. Secret values are
separate mode-`0600` files under `/etc/launchflow/secrets`; they are mounted as
Compose secrets and never appear in Compose environment variables, image
layers, source control, or normal command output.

Required secret files:

- `mariadb_root_password`
- `administrator_password`
- `backup_passphrase`

The production Site is initialized only through `init-site.sh`. It refuses an
existing Site without the production ownership marker, verifies the database
identity, installs `npi_core` before `npi_integration`, disables developer mode,
rejects the disposable marker, records the Site as `production`, disables public
self-signup, migrates, and enables the scheduler. Do not run the repository's
local `make frappe-site-init` target in production.

## Network path

Host Nginx terminates TLS and proxies Frappe/API/Socket.IO paths to the internal
Frappe frontend. All remaining routes go to the React SPA, whose Nginx config
provides history fallback. Docker publishes only `127.0.0.1:8080` and
`127.0.0.1:8081`; MariaDB and Redis have no host port.

## Operations

Systemd owns stack startup. Docker also uses `unless-stopped`, bounded JSON log
rotation, and live restore. The health timer verifies all required services,
trusted HTTPS, the SPA health endpoint, the unauthenticated NPI problem
contract, and scheduler status every five minutes.

The daily backup includes the MariaDB dump, public files, private files, and
Site configuration. It writes plaintext only to a mode-`0700` staging
directory, records SHA-256 checksums, streams the bundle through AES-256 GPG
encryption, verifies decryption, and removes staging data. Encrypted local
copies are retained for fourteen days. The current host owner explicitly
waived a remote copy; adding one later must use a least-privileged service
identity and must not expose credentials.

Use `restore-rehearsal.sh` to restore the latest encrypted backup into an
isolated, internal-only Docker network and temporary MariaDB/Site volumes. Use
`restore.sh` only for an approved production recovery; it requires the exact
Site name in `CONFIRM_RESTORE`, takes a fresh safety backup first, and leaves
maintenance mode enabled on failure.

Code rollback never performs a schema downgrade:

```text
sudo /opt/launchflow/current/deploy/production/scripts/rollback.sh EXACT_SHA
```

The command requires locally retained images with matching OCI release labels,
takes a full encrypted backup, switches both images together, clears caches,
and runs the production health gate. When schema compatibility is uncertain,
keep routes disabled and deploy a reviewed forward fix instead.
