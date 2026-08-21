# P8-03 Final Level 3 Recovery

- Captured at: `2026-08-21T05:14:45Z`
- Branch: `codex/npi-v1.2-implementation`
- Failed exact revision: `a9ac0b5e96024642eeb9918b44aac35bb861cde6`
- Failed controlled Level 3 run: `32448049882`
- Failed cumulative Site job: `96673329957`
- Recovery classification: one bounded response-neutral diagnostic checkpoint; no
  product root has yet been claimed or repaired.

## Observable stop

The exact-revision controlled Level 3 run passed secret scanning, repository,
frontend, visual, preflight, both migration passes, and every cumulative runtime
predecessor through P8-01. The P8-03 default-disabled probe also passed. The first
P8-03 Item create then stopped at
`scripts/verify_item_publish_runtime.py:322` with
`RuntimeError: P8-03 Item command did not create one queued request`.

The response and retained logs did not distinguish input parsing, project/source
resolution, mapping/profile resolution, transaction writes, commit, or enqueue.
Therefore the failure did not uniquely prove a product root and no product
behavior was changed.

## Bounded diagnostic checkpoint

The checkpoint enables a fixed `p803-item-create-v1` diagnostic header only on
the first disposable synthetic Item create. The server records at most one
allowlisted `P803_CREATE_*` stage, validated exception type, and exact trace ID.
It records no request body, business value, actor, secret, transport target, or
stack trace; the diagnostic never enters the HTTP response and cannot alter the
original exception, transaction, authorization, or enqueue behavior. A governed
problem response is reduced to its closed uppercase problem code and trace ID.

Local validation before commit:

- P8-03 Item module tests: `118/118` PASS.
- Repository verification: `2145/2145` tests PASS, prototype approval check PASS,
  P0 visual governance PASS, V1.2 reconciliation PASS.
- `git diff --check`: PASS.

## Serial recovery budget

- Exact unchanged final Level 3 dispatches consumed: `1`.
- Diagnostic checkpoints consumed: `0/1` before this checkpoint is pushed.
- Uniquely proven product repair batches consumed: `0/1`.
- Next action: push this checkpoint, require ordinary CI on its exact SHA, then
  run the sole controlled diagnostic Site pass. Do not dispatch another final
  unchanged Level 3 run until the diagnostic root is uniquely classified and
  any authorized minimal repair has passed its affected checks and ordinary CI.

No production ERPNext or JCE endpoint, credential, or data is used by this
recovery path.
