# R1-06 Stage 3 Validation — Durable 1440 P0 visual governance

Date: 2026-07-30
Branch: `codex/npi-v1.2-implementation`
Stage 3 starting synchronized checkpoint:
`a681c8cf948158b33a78b40a057145f91daf3cc8`
Bootstrap implementation checkpoint:
`96723b9aca57a6cfd907610d97c6de8c0a9442a6`
Final fixed-Linux baseline checkpoint:
`0b3a7b28bb447edbc165daa95a3e9963f255d832`
Task: `R1-06 — Controlled undo prototype gate and 1440 visual governance`
Requirements: `UX-035`, `UX-036`
Result:
`PASS — LEVEL 2 R1-06 STAGE 3 1440 P0 VISUAL GOVERNANCE`

## Delivered boundary

Stage 3 makes the current P0 screen set explicit in
`frontend/tests/e2e/p0-visual-registry.json` and verifies exactly:

- `work`, `project`, `gate`, `tooling`, `trial` and `execution`;
- `en`, `zh` and `zh-TW`;
- normal state at 1440×900 and 100% scale; and
- one exact screenshot per screen/language pair, for `18` governed images.

Every governed case requires visible object context, one visual primary action,
a sufficiently dense work surface/list and an applicable properties/inspector
surface, with no document-level overflow. The registry, case names, selectors,
viewport, screenshot files, fixed-container CI command, image digest, retained
R1-05 scope, artifact paths and retention are fail-closed repository inputs.

The Stage 3 slice adds tests, Linux screenshots and CI governance only. It does
not alter product UI source, literal-English copy, translations, API, schema,
permission, authentication, data ownership, production dependency or business
behavior. Every accepted 1366×768, 1920×1080, state, zoom and tablet baseline
remains unchanged.

## Requirement → code → test → evidence

| Requirement | Code/governance | Test evidence | Result |
|---|---|---|---|
| `UX-035` | closed six-screen P0 registry; visible context/action/work/properties density contract | exact 18-case browser assertions; PNG dimensions and file-set verifier; all-image original-resolution review | `TECHNICAL_VERIFIED_CURRENT_P0_SCOPE` |
| `UX-036` | digest-pinned Linux CI comparison; exact case/file set; bounded always-uploaded evidence | workflow/verifier adversarial unit tests; controlled missing-baseline bootstrap; clean `24/24` Linux comparison | `TECHNICAL_VERIFIED_CURRENT_P0_SCOPE` |

The status is deliberately bounded to the current six-screen P0 registry. It
does not claim that an unregistered future P0 page already has a baseline.

## Changed files → affected tests

| Changed boundary | Required checks | Final evidence |
|---|---|---|
| P0 registry and shared E2E support | exact schema, screen/locale/viewport cross-product and selector integrity | strict governance verifier and `7/7` adversarial tests |
| R1-06 visual spec | exact 18 test names; language purity; document overflow and density assertions; no snapshot-update path | Playwright list `18/18`; local comparison `18/18`; CI comparison `18/18` |
| Fixed Linux snapshots | exact file set, PNG signature, 1440×900 dimensions, no symlinks or extras | strict verifier `18/18`; SHA-256 manifest below; original-resolution review |
| CI workflow and devcontainer verifier | exact digest, command, retained R1-05 six-case scope, always-uploaded bounded artifacts, `30`-day retention | devcontainer verifier `21/21`; clean CI visual job and artifact |
| Repository aggregate entry | invoke the P0 visual verifier from `scripts/verify.sh` | CI repository verifier, `762` Python tests and complete frontend gate |

## Validation results

### Level 1 and affected checks

- TypeScript typecheck, ESLint, Prettier and Python compile: PASS.
- Devcontainer/workflow verifier tests: `21/21` PASS.
- P0 visual-governance verifier tests: `7/7` PASS.
- Combined affected Python verifier lane: `28/28` PASS.
- Direct strict baseline verification: `18` exact 1440×900 Linux baselines
  PASS.
- Playwright discovery: exactly `18` governed R1-06 cases.
- Local host comparison of the new cases: `18/18` PASS.
- Adjacent non-visual affected browser lane: `64/64` PASS.
- `git diff --check`: PASS.

The Darwin screenshots produced by host diagnostics are not canonical,
tracked or cited as Linux evidence.

### Controlled bootstrap and clean canonical comparison

GitHub Actions CI `#69`, run `30544199843`, intentionally established the
missing-baseline boundary:

- repository job `90876100858`: PASS;
- retained R1-05 Linux visual cases: `6/6` PASS;
- new R1-06 cases: all `18` failed only because the Linux snapshots were
  absent, and Playwright emitted the actual/baseline files;
- no density, language-purity, overflow or unrelated comparison failure was
  present; and
- `r1-06-linux-visual-evidence` artifact `8760026503`, digest
  `sha256:d43cfb8af689a97b299ce8db47c1b126ec9f354114eeaaee1a67952d4bd45ded`,
  was downloaded and its ZIP hash independently matched before the exact
  eighteen PNG files were extracted.

That controlled failure is bootstrap evidence, not a PASS claim.

GitHub Actions CI `#70`, run `30544737387`, then completed successfully for
the exact pushed baseline checkpoint:

- repository job `90877923233`: PASS;
- fixed-container visual job `90877923386`: `24/24` PASS in `29.6s`
  (`18` R1-06 plus the retained `6` R1-05 cases);
- complete Python lane: `762/762` PASS;
- complete frontend unit lane: `634/634` across `30/30` files;
- frontend coverage: statements `85.46%`, branches `83.63%`, functions
  `89.01%`, lines `87.53%`;
- i18n audit: `2,782` literal English sources with `100%` direct `zh` and
  `zh-TW` coverage;
- complete non-visual browser matrix: `279/279` PASS in `4.7m`;
- clean install and both npm audits: `0` vulnerabilities;
- action secret scan: `22` commits / `6.32 MB`, no leaks; and
- complete branch secret scan: `56` commits / `11.85 MB`, no leaks.

The canonical visual container is:

`mcr.microsoft.com/devcontainers/python:1-3.11-bookworm@sha256:b726eb94f42fcddb10056835f2c474c9f9e12e717ba2b2d2f9a8b1d78feeb68b`

Retained CI artifacts:

- `r1-06-linux-visual-evidence`, artifact `8760245782`, digest
  `sha256:c1921b3e29af91fb244fbb9d0bc377f346befcd482a93fdaf4b5f9010ecc7cd3`,
  expires 2026-08-29; and
- `gitleaks-results.sarif`, artifact `8760407958`, digest
  `sha256:67910a0ad390dde5787beafc8bf3931c47af7ba4595e10ad420614fe663dabfc`,
  expires 2026-10-28.

### Canonical baseline hashes

```text
d30483ade8e7155938710fdf71e513cea7a6eddf54ec9480047fafb157382c1b  r1-06-p0-normal-execution-en-1440x900-100-linux.png
161e25af9b696230467fd88ecbd2575b449fe28c3f3bf3aaa01402f02ea154cf  r1-06-p0-normal-execution-zh-1440x900-100-linux.png
b3aa4ed837caf5a8f1c84774220dff920e4ae09b4f234d8c93baf14da3031c2e  r1-06-p0-normal-execution-zh-TW-1440x900-100-linux.png
03a1bce3406780db49684bb1ba0ba880a7cff4a9922719157f2aef1e9a5c6cc8  r1-06-p0-normal-gate-en-1440x900-100-linux.png
7ac339177c83941c94c4316be40138dc6242b6fb493197063a8199097bbd91d4  r1-06-p0-normal-gate-zh-1440x900-100-linux.png
d4955d7ba40fb93be8842dd5bc7cb02405e6b6efb3227a9f98fbde9544f51342  r1-06-p0-normal-gate-zh-TW-1440x900-100-linux.png
a39ef65de587eb36a8cd90b05f36ca80f9eb607351ee1b8effbfe0a261dbcdfd  r1-06-p0-normal-project-en-1440x900-100-linux.png
0560314d53bfff9e756711743a7b245298cd11840b0dd12903a74070fc6ec2fb  r1-06-p0-normal-project-zh-1440x900-100-linux.png
38508682931ecacf438702da5a90e68d525fc11d5a7069bcb4e2d3640afa0b8f  r1-06-p0-normal-project-zh-TW-1440x900-100-linux.png
ca2684f10b450fcf21a9ff49c02fd50a9bd59a89e2e792765908ab54ec78909c  r1-06-p0-normal-tooling-en-1440x900-100-linux.png
5babad5474a831835bb9b8b87b36ea5c4ffa27dff977feb86bad93795512ccf8  r1-06-p0-normal-tooling-zh-1440x900-100-linux.png
2396bf24ecda53a9ad73f9f010a957bbbd991da3be75a34b0fd893d43719461d  r1-06-p0-normal-tooling-zh-TW-1440x900-100-linux.png
ebe21b96f6baeb0f6b3905b3efaf5d34ec0f385db12d23de78922d9158a2e182  r1-06-p0-normal-trial-en-1440x900-100-linux.png
fcf56acf3490dd54f6ea085b473a6ce4096f2e2994dfb306d907265ae010e8c8  r1-06-p0-normal-trial-zh-1440x900-100-linux.png
0cc1241809b776c1f277d942617726488f4fd5569b998d53b6e99a4e6cc59e0b  r1-06-p0-normal-trial-zh-TW-1440x900-100-linux.png
9963672caf8d687fd63d377530a3fb2a2d06ac6dc5dbf1cd7c9148c2dc4b65c8  r1-06-p0-normal-work-en-1440x900-100-linux.png
ffcd49f404aeeda1282d54391e51ef3d6b44bf6efc3c88e47239025d6bace629  r1-06-p0-normal-work-zh-1440x900-100-linux.png
8578205606965dc54d066229e1e6b54fa3b533d6abbdec7ef37157ab6c7c8a7f  r1-06-p0-normal-work-zh-TW-1440x900-100-linux.png
```

## UX, accessibility and localization review

All eighteen fixed-Linux images were inspected at original 1440×900
resolution, covering all six screens in each language. The review confirmed:

- classic light industrial app shell and stable engineering layout;
- square 1px borders, restrained radius, flat hierarchy and no decorative
  shadow treatment;
- dark teal as the single primary color, with restrained semantic accents;
- visible object context, work surface and properties/inspector surfaces;
- one visible primary action per governed context;
- dense readable layout with no document overflow or clipped governed
  surface; and
- language-pure English, Simplified Chinese and Traditional Chinese UI.

Observed retained Latin strings in Chinese screenshots are only controlled
product/system abbreviations, identifiers, business data or units such as
`NPI`, `ERPNext`, `LaunchFlow`, project codes and dimensional units. No direct
catalog or source copy changed in Stage 3.

## Security, contract, migration and rollback review

- Public API/OpenAPI, Frappe controller and BFF changes: **none**.
- Database schema, DocType, migration, patch and retained data changes:
  **none**.
- Authentication, authorization, CSRF and permission-model changes: **none**.
- Product source, design token, theme, translation source/catalog and
  dependency changes: **none**.
- CI uses the repository-scoped read-only GitHub token only for exact
  fail-closed metadata and scanner operations.
- Reports, results, diffs and screenshots are bounded to the declared Stage 3
  evidence path and retained for `30` days; absence is an upload failure.
- Rollback removes only the exact registry/spec/verifier additions and eighteen
  R1-06 Linux screenshots, then restores the previous affected visual command.
  It requires no migration or data recovery and does not touch historical
  accepted baselines.

## Gate decision

`UX-035` and `UX-036` are technically verified for the exact current P0
registry. Stage 3 passes. This result does not approve R1-06 Stage 2, does not
close future P0-page coverage and does not release P5-01 by itself. Proceed to
the R1-06 Level 2 Task Gate with the Product Owner approval hold intact.
