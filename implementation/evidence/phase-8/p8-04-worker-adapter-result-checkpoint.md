# P8-04 Checkpoint 3 — Leased Worker, Closed Adapter and Per-node Truth

Recorded: `2026-08-21`

Status: `IMPLEMENTED — AWAITING EXACT-SHA ORDINARY CI`

## Candidate scope

- Adds bounded pending/expired claim recovery, immutable batch attempts and a
  commit-before-dispatch adapter boundary. A live lease is not stolen; an
  expired pre-boundary claim may create the next bounded attempt; an expired
  post-boundary claim is classified uncertain and never blindly redispatched.
- Adds a closed, default-disabled MBOM adapter registry. No production or
  default Sandbox profile, endpoint or credential is installed. The only
  runtime proof is explicit, disposable, network-free synthetic execution.
- Persists one aggregate Result before its linked per-assembly Node Results,
  preserving partial, retryable, final, submitted-blocked, mapping-conflict and
  uncertain truth. Mock/synthetic never produce a formal BOM ID, target
  version or authoritative mapping.
- Applies authenticated authoritative Sandbox observations only through exact
  per-node compare-and-set. Submitted or stale truth stays fail-closed; a
  duplicate first-head race retains the winner and appends an observed
  conflict without overwriting it.
- Runs only under the frozen internal service actor, restores the requester
  session, records safe diagnostics without target/body/exception leakage and
  offers one bounded local seal recovery plus the existing scheduler scan.

## Candidate verification

- Focused adapter, worker, worker repository, runtime fixture/verifier and
  service-scope tests cover claim/lease order, default-disable, closed registry,
  one dispatch, boundary uncertainty, submitted/stale CAS, per-node aggregation,
  zero formal synthetic mapping and session restoration.
- Complete MBOM `86/86`, the explicit checkpoint MBOM + Item set `144/144`,
  affected Item publish `146/146`, Phase 5 EBOM `69/69`, Phase 5 publish
  `47/47`, Phase 2 `15/15` and controller/reconciliation `32/32`: PASS.
- Python compile, shell syntax, current-task/reconciliation commands, product
  no-network/no-direct-SQL scan, Frappe-backed catalog generation, i18n audit
  (`8,108` literal English sources, `100%` direct `zh`/`zh-TW`) and
  `git diff --check`: PASS.
- Exact-SHA ordinary CI must pass before checkpoint 4 activates. This file
  records no CI or runtime PASS in advance.

The first exact candidate
`e3e36a0c7adc600a2df012fae8d2d8cb33cc74c4` reached ordinary CI
`32505131927`. Repository job `96843477712` passed `2,259/2,259` tracked
Python tests before the direct-SQL zero-match scanner matched only this
checkpoint's negative-test combination literal. Frontend `96843477566`,
secret `96843477773` and visual `96843477762` passed. This is a test-harness
self-trigger, not product or Gate evidence; the response-neutral AST
remediation must pass a new exact-SHA ordinary CI before checkpoint 4.

## Changed-files to affected-checks map

| Changed boundary | Affected evidence |
|---|---|
| `hooks.py`, `worker.py`, `worker_repository.py` | scheduler registration, service-actor-before-claim, live/expired lease order, commit-before-dispatch boundary, one dispatch, terminal retained truth, safe recovery, immutable attempt/result/node ordering and exact per-node CAS tests |
| `adapters.py`, `domain.py`, `frappe_validation.py` | closed default-disabled registry, exact request/node manifests, authenticated response classification, partial/submitted/uncertain truth, actor/session restoration and capability-bound writes |
| `runtime_fixture.py`, `verify_mbom_publish_runtime.py`, `verify-frappe-runtime.sh` | default-disabled probe, exact marker-gated network-free synthetic profile, Project-first create, requester/service session proof, zero formal IDs/mapping heads, terminal replay and environment cleanup |
| focused P8-04 tests | complete MBOM `86/86`, explicit MBOM + Item `144/144`, exact request-to-mapping-head identity including forged self-consistent stable-line rejection, commit-failure rollback with zero dispatch, no direct SQL/network/production identity, no fake formal truth and no exception/body/credential leakage |
| controller and checkpoint evidence | exact checkpoint 2 SHA/CI/jobs/artifacts, checkpoint 3-only authority, external holds and no checkpoint 4/UI overclaim |

## Rollback

Disable new MBOM claims and the synthetic fixture. Retain every request, node,
Outbox event, claim, attempt, boundary flag, response hash, aggregate/node
result, uncertainty, observation, mapping head and audit. After any boundary
crossing, use reviewed forward repair only: never delete, blindly redispatch,
rewrite partial/failure/uncertain truth, change a formal BOM identity, mutate
released source, submit or overwrite a BOM, or compensate a target
automatically.
