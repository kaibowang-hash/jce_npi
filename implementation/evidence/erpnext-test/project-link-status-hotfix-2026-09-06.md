# ERPNext Project Link Status Hotfix Evidence

Date: 2026-09-06 (Asia/Bangkok)

LaunchFlow Site: `launchflow.whjichen.cn`

ERPNext target: `test`

Product release: `96c3a791b949b803d3519299d99cefcaa4de9387`

Previous release: `1522d700f4f8675f91bd06d550522fa1e0106afa`

The production ERPNext alias `JCE-Core` was not contacted or modified.

## Root cause and correction

The Project portfolio rendered an absent ERP projection observation as a red
ERPNext-system availability failure. That state did not describe the actual
connection or the independent ERP Project source binding. Consequently,
Projects with valid ERPNext bindings could show `JCE Core unavailable`, and a
Project cockpit with no governed references could show a misleading global
empty-project banner.

The release keeps three facts separate:

- the global NPI-to-ERPNext connection status;
- the per-Project ERP Project source binding (`bound`, `unbound`, `conflicted`
  or `unavailable`); and
- the availability of later ERP reporting observations for that Project.

The Project portfolio and cockpit now render the exact Project binding and ERP
Project ID when bound. A missing later reporting observation is neutral `No ERP
fact observations yet`, while a real projection-store failure remains an
explicit unavailable state. The governed-reference empty state is confined to
its own table and no longer declares the whole Project empty.

## Verification before release

- Repository Level 3: `3154/3154` checks passed in the pinned Python 3.11
  development container.
- Frontend Level 3 under exact Node `24.18.0` and npm `11.16.0`: `79` files and
  `1168/1168` tests passed.
- Frontend coverage passed: `80.00%` statements, `79.39%` branches, `82.09%`
  functions and `82.61%` lines.
- Lint, typecheck, build, asset budgets, brand controls and both dependency
  audits passed; dependency audits reported zero vulnerabilities.
- The English-source i18n audit covered `9477` sources with complete Simplified
  and Traditional Chinese catalogs.
- Affected non-visual browser coverage passed `43/43` checks. The Linux Project
  visual suite passed `12/12`; the affected macOS Project and portfolio suite
  passed `15/15`.
- Production image build repeated the complete frontend verification and
  embedded the exact product SHA in both OCI image labels.

## Deployment and recovery evidence

- The source archive SHA-256 was
  `37184fbe73de04f3db9ee04f4d76bc2048347fe0c7bd6c8b62cec92dfc59d620`.
- The compressed image archive SHA-256 was
  `02e7adce7232d69fb3e278a5a5c73c896d25a3cf7d637541ee0b2fe5d6fc1f90`.
- Local and remote archive checksums matched before extraction or image load.
- A full encrypted backup was created and verified before maintenance mode:
  `launchflow-launchflow.whjichen.cn-20260906T062044Z.tar.gpg`, SHA-256
  `6d2b9cd8ee0d9b7ebeca5b2e84ce59bebfac6389774fb88f4d3eb2d930e2b94c`.
- The previous environment file remains as root-owned mode-`0600`
  `/etc/launchflow/production.env.before-96c3a791`; the previous release and
  exact images remain available for code rollback without schema downgrade.
- Migration, cache clear and maintenance-mode exit succeeded.
- The production health gate passed. All ten required services are running,
  and the backend and SPA OCI revision labels both equal the exact product
  release SHA.

## Live post-deployment result

A fixed, read-only LaunchFlow runtime verification executed as
`kaibo_wang@whjichen.cn` returned `connectionState: connected`, target
environment `test`, and all five capabilities as `true`:
authorization synchronization, Item commands, Project synchronization, master
data synchronization and reporting synchronization.

The permission-filtered Project result was:

| NPI Project | ERP Project binding | ERP Project ID | Governed references |
| --- | --- | --- | ---: |
| `PROJ-0027` | `bound` | `PROJ-0027` | 0 |
| `PROJ-0028` | `bound` | `PROJ-0028` | 0 |
| `MM-35029` | `unbound` | none | 0 |

The portfolio response and each Project cockpit returned the same binding
state. Therefore `PROJ-0027` and `PROJ-0028` now display as linked even though
they do not yet have later ERP reporting observations. `MM-35029` truthfully
displays as not linked, not as an unavailable ERPNext system.

This hotfix does not create an ERPNext Project for `MM-35029`. Automatic
NPI-to-ERPNext Project creation is not an approved operation in the current
ownership contract; existing Project synchronization is ERPNext-owned inbound
binding. Adding an outbound Project command would require an explicit contract,
permission, idempotency and rollback decision rather than fabricating a link in
the display layer.
