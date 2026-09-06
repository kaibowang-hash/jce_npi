# R1-06 Stage 1 Validation — Controlled undo review prototype

Date: 2026-07-30
Branch: `codex/npi-v1.2-implementation`
Starting synchronized checkpoint:
`2790ca280bbc47670d840bdb75fadaf2885367d3`
Final pushed implementation checkpoint:
`e7f2e3bc7956d5f2192eb1b2b9e5fb3d5dc0c4a2`
Task: `R1-06 — Controlled undo prototype gate and 1440 visual governance`
Requirements: `UX-026`, `UX-030`
Result:
`PASS — TECHNICAL PROTOTYPE/GOVERNANCE; PRODUCT OWNER APPROVAL PENDING; STAGE 2 HELD; STAGE 3 READY`

## Delivered boundary

The Stage 1 slice adds one deterministic review-only prototype for the current
actor's closed My Work personal-grid reset candidate. The exact demo route is:

`/demo/work?prototype=my-work-grid-reset-undo&undoState=review`

The prototype covers review, confirmation, reset-confirmed undo availability,
processing, reconciled restoration, expiry, conflict, permission denial,
retryable unknown result and final failure. It always states that it sends no
production request and changes no saved settings. Automated transport checks
observed only the existing session bootstrap `GET`; no mutating request was
issued.

The slice adds no production API, BFF command, DocType, database schema,
permission, audit row or business mutation. It does not implement a generic
undo service or claim the unapproved business-bulk part of `UX-026`.

## Product approval truth

The versioned manifest
`implementation/prototype-approvals/r1-06-my-work-grid-reset.json` remains:

- `status = PENDING_PRODUCT_OWNER`;
- `backendImplementationAuthorized = false`;
- no Product Owner identifier, timestamp or approval evidence; and
- no production duration.

Normal repository validation accepts that truthful pending record. The exact
backend-entry check fails closed, as required:

```text
python scripts/verify_prototype_approvals.py \
  --require-backend-approval my-work-grid-reset-undo

prototype approval verification failed: backend implementation is blocked pending Product Owner approval
```

Therefore `UX-026` is
`PROTOTYPE_VERIFIED_BACKEND_APPROVAL_HELD` and `UX-030` is
`TECHNICAL_VERIFIED_GOVERNANCE_PRODUCT_APPROVAL_HELD`. Technical tests,
screenshots and Codex review are not Product Owner approval. R1-06 Stage 2
remains scoped-held; independent Stage 3 is ready.

## Requirement → code → test → evidence

| Requirement | Code/governance | Test evidence | Result |
|---|---|---|---|
| `UX-026` | closed prototype state model and My Work demo consumer; visible consequence/recovery and ineligible-action truth | component state/no-transport tests; complete non-visual browser lane; trilingual screenshot review | Prototype verified; backend and business-bulk acceptance held |
| `UX-030` | versioned closed approval manifest, reviewed-source digest and fail-closed Stage 2 verifier | five approval-verifier tests; normal pending verification; required-backend expected failure; reconciliation trace test | Technical governance verified; Product Owner decision pending |

The complete approval review package, screenshot hashes and original-resolution
inspection are recorded in
`implementation/evidence/reconciliation/r1-06-stage-1-prototype-review.md`.

## Changed files → affected tests

| Boundary | Affected checks |
|---|---|
| Prototype model/component, Work route and styles | `controlled-undo-prototype.test.tsx`; `r1-06-controlled-undo-prototype.spec.ts`; frontend type/lint/style/boundary/UI audits |
| Literal-English copy and direct `zh`/`zh-TW` catalogs | generated catalog freshness; i18n lint; trilingual mixed-language and accessibility browser cases |
| Approval manifest and verifier | `tests.test_prototype_approvals`; normal pending validation; exact backend-entry expected failure |
| Trace generator/verifier and controller evidence | reconciliation unit tests; standalone verifier; generated trace freshness; YAML/controller scans |

## Validation results

### Level 1 and affected checks

- Approval verifier unit tests: `5/5` PASS.
- Real pending manifest: `1` manifest accepted with `1` pending Product Owner
  approval.
- Exact backend-entry verifier: expected FAIL with the closed pending-approval
  message above.
- Prototype unit/component tests: `14/14` PASS.
- Prototype E2E and review captures: `14/14` PASS.
- TypeScript typecheck, i18n lint, generated-catalog freshness, Prettier and
  style lint: PASS.

### Task-level frontend gate

- Complete frontend unit suite: `634/634` across `30/30` files.
- Coverage: statements `85.46%`, branches `83.63%`, functions `89.01%`,
  lines `87.53%`.
- Production build and exact display-brand asset guard: PASS.
- Complete non-visual browser matrix: `279/279` PASS in `2.1m`.
- The local npm install-script/audit tail could not run under workstation npm
  `11.3.0` because that client reports `approve-scripts` as an unknown
  command. This is an environment/tool-version limitation, not a substituted
  PASS; the clean hosted CI repository lane must supply the canonical
  install-script and zero-vulnerability audit evidence for this checkpoint.

### Hosted canonical checkpoint

GitHub Actions CI `#67`, run `30542155671`, completed `success` for the exact
pushed checkpoint:

- repository job `90869267448`: PASS;
- Node `24.18.0` / npm `11.16.0` clean install: `380` packages audited,
  `0` vulnerabilities;
- complete repository verifier, including the install-script guard and both
  npm audits: PASS;
- complete non-visual browser matrix: `279/279` PASS in `4.2m`;
- action secret scan: `22` commits / `6.32 MB`, no leaks;
- complete PR-branch secret scan: `53` commits / `11.81 MB`, no leaks; and
- fixed-container visual job `90869267397`: PASS.

Retained CI artifacts:

- `r1-05-linux-visual-evidence`, artifact `8759172677`, digest
  `sha256:34637088bf8ba8e86d95a8e6bcf515914914211f9b4a17556cf011cd18a5cfcb`;
- `gitleaks-results.sarif`, artifact `8759316210`, digest
  `sha256:46277e63a3c9b8ac55d4967961597527311a7ed98f46c7214a45a30f927318fa`.

### UX, accessibility and localization review

- Literal English remains the only source language; direct `zh` and `zh-TW`
  translations are generated from the Frappe-compatible catalogs.
- The three 1440×900 review captures passed original-resolution inspection for
  mixed language, clipping, document overflow, state visibility, square
  geometry, shadow/radius restraint and one primary action.
- Axe WCAG A/AA, keyboard actions, focus transfer, accessible status, visible
  recovery, industrial computed-style and document-overflow assertions pass in
  `en`, `zh` and `zh-TW`.
- The captures are Stage 1 approval evidence only. They are not the
  digest-pinned Linux 1440 product baselines owned by Stage 3.

## Security, permission, migration and rollback review

- No production request or mutation route is introduced.
- No protected data is added to the prototype or manifest.
- Unknown route state, manifest field, action, state, source drift, fabricated
  authorization, approval mismatch, duplicate ID and missing approval evidence
  fail closed.
- There is no migration or retained business data. Rollback removes only the
  prototype component/model, exact demo consumer, pending manifest, verifier
  and review evidence.

## Gate decision

Stage 1 is a technical prototype/governance PASS, not backend acceptance,
business UAT or Product Owner approval. The only dependent hold is Stage 2.
Proceed automatically to R1-06 Stage 3 while retaining the unsigned manifest
and the exact Stage 2 entry guard.
