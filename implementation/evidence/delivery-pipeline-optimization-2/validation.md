# CI-OPT-02 Validation and Release-Gate Evidence

Recorded: `2026-09-03`

Result: `PASS — EXACT-SHA LEVEL 3`

Accepted checkpoint:
`ea6112fa04e08cee6920407df426efc685cea98b`

## Scope result

CI-OPT-02 changed delivery mechanics only. It introduced a fail-closed
diagnostic-only attestation path and native two-way Playwright sharding while
retaining the complete ordinary and Level 3 paths. It did not change product
behavior, domain rules, API or event contracts, Schema, migrations,
permissions, translations, visual baselines, coverage thresholds, retries or
production configuration. Production ERPNext was not contacted.

The committed task delta from predecessor product checkpoint
`a439043f96976c562edb8d4af69d51c709390043` is five commits:

- `f60e02120d30c44eaef213e8e84867862690cea1` — fail-closed diagnostic fast path
- `cdb9d9d89eaebc97da793d854deeabeb88749f1c` — native two-way nonvisual E2E sharding
- `e6672a4afcd22f6fb35f0857fff15e5853812ae3` — bounded value-free legacy classifier
- `5b77dcf7b9fb37c17570dbd9f1091bba2cd0cd59` — transitive development security lock repair
- `ea6112fa04e08cee6920407df426efc685cea98b` — nonreproducing classifier closure

## Baseline and stability

The frozen five-run pre-change baseline was:

| Run | SHA | Repository | Frontend | Nonvisual E2E | Visual | Secret |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `33624647220` | `70684e30` | 69s | 637s | 447s | 318s | 22s |
| `33628445755` | `7669d554` | 70s | 824s | 610s | 287s | 24s |
| `33631552203` | `7e9e0f24` | 73s | 781s | 568s | 310s | 22s |
| `33634947509` | `749c0096` | 70s | 877s | 630s | 278s | 18s |
| `33638920721` | `a439043f` | 72s | 852s | 624s | 302s | 20s |

Baseline nonvisual E2E was P50 `610s`, P95 `630s`. Three unchanged four-worker
attempts completed `460/460` tests with zero retries at `397/560/574s`, giving
P50 `560s` and P95 `574s`. This was stable but only 8.2% below baseline, so the
frozen rule authorized native two-way sharding.

Run `33650279037` at exact SHA
`cdb9d9d89eaebc97da793d854deeabeb88749f1c` was rerun twice without code
changes. Its three sharded attempts each completed `230 + 230 = 460` tests with
zero retries. Critical E2E durations were `290/284/257s`, P50 `284s`, P95
`290s`, a 53.4% improvement from the `610s` baseline. The aggregate `frontend`
required check passed each attempt.

## Fail-closed and fault evidence

- Diagnostic reuse is limited to the latest successful ordinary pull-request
  run on the same repository and branch, with an ancestor SHA and an exact
  allowlisted intervening path set. Denied, unknown, stale, foreign,
  non-ancestor, incomplete or unavailable evidence selects full CI.
- Diagnostic runs always execute repository verification, current-tree secret
  scanning, controlled preflight and a fresh disposable Site. Reused
  frontend/visual evidence is explicitly ineligible for merge, release or
  Level 3 evidence.
- The attestation contains fixed classification, counts and run/SHA
  provenance only. It does not emit changed paths, runtime payloads,
  identities, business values or secrets.
- The first full Level 3, `33653098092`, passed every base lane and preflight
  before a retained P8-03 migrated-legacy assertion failed in the cumulative
  Site. No repair was inferred from its outer label.
- Classifier ordinary run `33655458898` passed repository, secret, visual and
  both `230/230` shards. The aggregate failed closed because a newly published
  high-severity advisory rejected transitive development-only `fast-uri`
  `3.1.5`.
- The bounded lock repair moved only that transitive entry to compatible fixed
  `3.1.7`. Exact npm audit then reported zero vulnerabilities; local exact Node
  `24.18.0` / npm `11.16.0` verification passed typecheck, lint, `1097/1097`
  unit/coverage tests and build.
- Exact-SHA ordinary `33657532266` passed all lanes. Its sole diagnostic-only
  continuation `33658159139` passed plan `100341822118`, repository
  `100341930295`, secret `100341930540`, preflight `100342340611` and full
  cumulative runtime `100342416427`. It emitted no classifier tuple, so no
  fixture or product repair was authorized. The classifier was disabled.

## Final exact-SHA evidence

Ordinary pull-request run `33659491378` at accepted SHA `ea6112fa` passed:

| Lane | Job | Result |
| --- | ---: | --- |
| secret scan | `100346237590` | PASS |
| repository | `100346237571` | PASS |
| frontend verify | `100346237471` | PASS |
| E2E shard 1 | `100346237574` | PASS — `230/230`, zero retries |
| E2E shard 2 | `100346237443` | PASS — `230/230`, zero retries |
| visual | `100346237299` | PASS |
| frontend aggregate | `100348208185` | PASS |

The one final diagnostics-off Level 3 run `33660141866` at the same SHA passed:

| Lane | Job | Result |
| --- | ---: | --- |
| secret scan | `100348403326` | PASS |
| repository | `100348403450` | PASS |
| frontend verify | `100348402873` | PASS |
| E2E shard 1 | `100348403186` | PASS — `230/230`, zero retries |
| E2E shard 2 | `100348403361` | PASS — `230/230`, zero retries |
| visual | `100348403072` | PASS |
| frontend aggregate | `100350269092` | PASS |
| controlled preflight | `100350306172` | PASS |
| cumulative disposable Site | `100350396533` | PASS — 9m22s |

Local closure evidence also passed focused classifier tests `48/48`, full
repository verification `2841/2841`, current-task/reconciliation checks,
syntax and diff hygiene.

## Changed-files to evidence

| Surface | Evidence |
| --- | --- |
| prior-Gate verifier and tests | latest-run, ancestry, allow/deny/unknown, unavailable/network and bounded-output tests; repository PASS |
| CI workflow | static workflow contracts, exact-SHA ordinary PASS and full Level 3 PASS |
| Playwright scripts | three unchanged `460/460` sharded attempts, zero retries, aggregate required check |
| transitive lock | exact install, zero-vulnerability audit and complete frontend verification |
| temporary classifier closure | focused `48/48`, repository `2841/2841`, diagnostic no-tuple evidence and diagnostics-off final Level 3 |
| governance state | current-task verifier, V1.2 reconciliation and exact-path diff |

## Release-gate review

`release-gate` result: `PASS`.

- Acceptance mapping, exact diff, real CI logs, rollback and evidence are
  present.
- API/schema, migrations, permissions, product UI, i18n and integration
  ownership are unchanged.
- No retry, ignored failure, reduced threshold, fake success, core patch,
  cross-database access, secret, backdoor or production ERP connection was
  introduced.
- Rollback before later product work is a normal revert of the five delivery
  commits. After later work, disable `diagnostic_only` and restore two
  nonvisual workers through a reviewed forward fix while retaining the full
  ordinary and Level 3 paths.
- User-owned dirty documents, screenshots, evidence, local prerequisites and
  editor files were not staged, overwritten or removed.

CI-OPT-02 is complete. P9-02 may resume automatically.
