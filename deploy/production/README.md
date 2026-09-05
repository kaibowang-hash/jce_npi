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
- `npi_item_publish_sandbox_secrets` (a closed JSON object keyed by the
  approved opaque Item connector secret reference; use `{}` while Item
  Sandbox dispatch remains disabled)
- `npi_mbom_publish_sandbox_secrets` (a closed JSON object keyed by the
  approved opaque MBOM connector secret reference; use `{}` while MBOM
  Sandbox dispatch remains disabled)
- `npi_tool_asset_sandbox_secrets` (a closed JSON object keyed by the
  approved opaque Tool Asset connector secret reference; use `{}` while Tool
  Asset Sandbox dispatch remains disabled)
- `npi_trial_summary_erp_sandbox_secrets` (a closed JSON object keyed by the
  approved opaque released-Trial-Summary connector secret reference; use `{}`
  while that Sandbox dispatch remains disabled)
- `npi_engineering_change_sandbox_secrets` (a closed JSON object keyed by the
  approved opaque Engineering Change summary connector secret reference; use
  `{}` while that Sandbox dispatch remains disabled)
- `npi_erp_project_ingress_secrets` (a closed JSON object keyed by the
  approved opaque ERP Project webhook secret reference; use `{}` while the
  inbound Project profile remains disabled)
- `npi_engineering_change_ingress_secrets` (a closed JSON object keyed by the
  approved Engineering Change webhook signing-key ID; use `{}` while the
  inbound Engineering Change profile remains disabled)

Only the short worker receives the Item, MBOM, Tool Asset, released-Trial-
Summary and Engineering Change outbound connector secrets. Only the backend
receives the Project and Engineering Change ingress signing secrets. The long
worker does not consume the short queue, so a
secret-dependent operation cannot be claimed by a worker without its scoped
credential. Root startup wrappers read the root-only files and immediately
drop to the `frappe` UID/GID before executing the worker or web process. The
Site configuration stores only non-secret profiles, never API credentials.

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
