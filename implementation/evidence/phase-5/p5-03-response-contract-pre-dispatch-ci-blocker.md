# P5-03 Response-Contract Pre-Dispatch Ordinary-CI Blocker

Recorded: `2026-08-05T06:28:34Z`

Status:
`BLOCKED_EXTERNAL — NO P5-03 PASS`

Requirement:
`FR-DS-006`

Diagnostic checkpoint:
`9d25e50085aa97a4c959136ec04e4606c17522fc`

## Completed bounded work

The response-contract predicate ladder is behavior-neutral and limited to the
user-authorized project, replay, baseline, policy, member, revision, File,
scan, private-path and URL predicates. It emits only an allowlisted predicate
code, a validated exception type and the exact trace ID. It does not send the
server diagnostic header and does not expose exception text, traceback,
request, response, Cookie, credentials, business data or storage paths.

Only these two P5-03 files were committed in the diagnostic checkpoint:

- `scripts/verify_document_runtime.py`;
- `tests/test_phase5_document_runtime_verifier.py`.

Existing tracked and untracked user workspace changes were not staged.
Affected P5 Document tests passed `168/168`; the complete set of Git-tracked
Python tests passed `883/883`. The clean committed frontend snapshot passed
generation checks, type checking, lint, `671/671` unit tests with coverage,
production build and the display-brand guard. The fixed-Linux visual job also
passed on the exact checkpoint.

## Complete ordinary CI

Pull-request CI run `30980622113` matched exact SHA `9d25e50`. Its controlled
Site job was skipped as required. The repository job failed in
`bash scripts/verify.sh`; a retry of that same ordinary job failed at the same
step. No diagnostic-only controlled-Site dispatch was executed, so the new
response-contract allowance remains `0/1` used.

The available structured GitHub metadata identifies only the enclosing
`verify.sh` step. Reading the complete failed log was rejected because it can
emit data outside the current non-disclosure boundary. A direct online
`npm audit` request was also rejected because it would send dependency
metadata to an external registry without separate authority. Dependabot
alerts are disabled for this repository. A local offline cached audit reports
zero vulnerabilities, but cannot prove the current runner result and is not a
substitute for the required complete ordinary CI.

The safe local narrowing therefore cannot uniquely distinguish a current
online dependency advisory/registry result from another hidden `verify.sh`
subcommand failure. No dependency, CI criterion, product code or contract may
be changed on that evidence.

## Controller conclusion

P5-03 is `BLOCKED_EXTERNAL`, not `PASS`. The response-contract diagnostic
dispatch, any product/fixture/verifier repair, the final unchanged
controlled-Site Gate and the P5-03 Level 2 Task Gate have not run. The global
five-product-root rule and the separate unused response-contract exception are
unchanged.

The single resume action is explicit bounded authority to read only the failed
ordinary-CI subcommand identity and, if it is an npm advisory, only package
name, GHSA identifier, severity and first patched version. Raw exception text,
traceback, request/response, Cookie, credentials, business data and storage
paths remain forbidden. After the ordinary CI root is safely proven and
closed, the existing authorization resumes at the still-unused single
diagnostic-only controlled-Site dispatch.

`implementation/LAST_RUN.md` was already user-dirty and remains untouched and
excluded from this checkpoint.
