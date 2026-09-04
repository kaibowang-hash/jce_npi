# PA-04 Server-Owned Deployment Environment

Status: **LOCAL TASK GATE PASS — NOT DEPLOYED OR PRODUCTION-ACTIVATED**

Date: 2026-09-03 (Asia/Bangkok)

## Authorization and scope

The user requested a ready-to-use production deployment and reported that
selecting Production outside the application did not change the LaunchFlow
interface. Repository inspection proved that both App Shell environment labels
were hard-coded to **Test environment**.

This atomic task replaces that false live label with one server-owned,
non-secret Frappe Site setting:

- key: `npi_deployment_environment`;
- exact values: `production` or `sandbox`;
- owner: the LaunchFlow Frappe Site operator through the approved deployment
  procedure;
- transport: authenticated `SessionBootstrap.deploymentEnvironment` through
  the existing LaunchFlow BFF;
- presentation: Production/Sandbox in the side navigation and status bar,
  translated in English, Simplified Chinese and Traditional Chinese.

Missing, mixed-case or unknown Site values fail the new backend bootstrap as
`DEPLOYMENT_ENVIRONMENT_UNAVAILABLE`. During a rolling frontend-before-backend
deployment, an absent legacy response field displays **Deployment environment
not confirmed**; it never guesses Test or Production. Prototype mode remains
explicitly labelled Test.

## Non-scope and safety

- No production host, Site or ERPNext system was contacted or changed.
- No credential, endpoint, host identity or business value is stored.
- No account, role, permission, Entra configuration or ERP adapter is changed.
- No Frappe or ERPNext core code is changed.
- Setting the production Site value remains an approved deployment operation;
  the repository task only implements and documents the contract.

## Changed files to affected checks

| Area | Files | Evidence |
|---|---|---|
| Server truth and safe problem | `localization_api.py`, `foundation/errors.py` | exact value, missing/invalid and redaction unit cases |
| API contract | `contracts/npi-api.openapi.yaml` | required closed enum in `SessionBootstrap` |
| App Shell | `session.ts`, `runtime.tsx`, `app-shell.tsx` | Production/Sandbox, rolling omission and malformed-value tests |
| Local disposable Site | `init-npi-site.sh`, `verify_local_frappe_site.py`, `verify_frappe_runtime.py` | fixed Sandbox classification and drift guard |
| Operator procedure | `docs/GO_LIVE_AND_RECOVERY_RUNBOOK.md` | exact non-secret Site configuration and smoke requirement |
| Internationalization | Frappe translation CSVs and generated catalogs | three-language coverage and mixed-language audit |
| Visual evidence | 12 governed `r1-03-shell-*-linux.png` baselines | English/Simplified/Traditional, expanded/collapsed/command/responsive states |

## Verification evidence

- Focused Python localization and local-Site safety tests: **55/55 PASS**.
- Focused frontend session, i18n and App Shell tests: **109/109 PASS**.
- R1-03 non-visual browser matrix: **10/10 PASS**.
- Linux Playwright visual matrix after reviewed baseline update: **6/6 PASS**
  without snapshot updates on the confirmation run.
- Internationalization audit: **9333** literal English sources with **100%**
  Simplified Chinese and Traditional Chinese coverage.
- Full isolated exact-toolchain Gate with Node **24.18.0** and npm
  **11.16.0**: **PASS** — **2994/2994** Python tests, **1155/1155**
  frontend tests, typecheck, lint, production build, build budgets, brand audit,
  install-script review, and both dependency audits with **0 vulnerabilities**.

## Deployment smoke and rollback

Before the new backend receives production traffic, the approved operator sets
the exact production Site key and confirms that authenticated session bootstrap
returns `deploymentEnvironment: production`. Rollback disables traffic to the
new release and restores the prior application SHA; if the previous release
does not understand this additive key, the non-secret Site key may remain for a
forward-fix. No database schema or business data rollback is required.
