# R1-06 Stage 1 Prototype Review Package

Date: 2026-07-30
Task: `R1-06 — Controlled undo prototype gate and 1440 visual governance`
Requirements: `UX-026`, `UX-030`
Prototype ID: `my-work-grid-reset-undo`
Prototype revision: `r1-06-stage-1-v1`
Approval status: `PENDING_PRODUCT_OWNER`

## Review route

`/demo/work?prototype=my-work-grid-reset-undo&undoState=review`

The route is available only through the existing explicit demo boundary. It
does not add a live/production route, API, DocType, permission or business
command. The surface continuously states that it is a prototype, sends no
production mutation and changes no saved settings.

The optional closed `undoState` query accepts only:

- `review`;
- `confirmation`;
- `available`;
- `processing`;
- `restored`;
- `expired`;
- `conflict`;
- `denied`;
- `retryable`; or
- `final`.

Unknown values fail closed to `review`.

## Eligible action proposed for approval

Reset one closed My Work view's personal grid layout for the current
authenticated actor to code-owned defaults.

The approved implementation, if authorized later, would offer one bounded
undo only after the reset is server-confirmed. Undo would be a new authorized
and idempotent server command that rechecks actor, permission, current
preference version/hash, expiry and consumption, then restores the previous
layout as a new preference version with append-only audit evidence.

The prototype displays `10` seconds only as the interaction-review duration.
The production duration remains unset and requires Product Owner approval.

## Consequence and recovery copy

- Reset affects only the current actor's selected personal grid view.
- No business data or shared view would change.
- The processing state never reports the prior layout as restored.
- An unknown response reconciles the prepared request before any retry.
- Expiry leaves the confirmed reset active.
- Conflict requires current-settings reload.
- Permission denial sends no command.
- Final failure retains a visible reference ID.
- Gate decisions/reopen, approval, release/publish/baseline, registered
  revision mutation, business lifecycle transition, external execution,
  delete/cancel/void and unapproved bulk actions never use this generic Undo.
- Those ineligible actions retain their owning workflow's approved
  forward-correction, new-revision, reconciliation or support path.

## Interaction and accessibility review

- Each state has text plus an icon/shape status; color is not the sole signal.
- Each state exposes a visible keyboard-reachable action; no recovery depends
  on hover.
- Focus moves to the state region after a state transition.
- One visually primary action exists in each prototype state.
- The layout uses square panels, 1px borders, no decorative shadow/gradient,
  the existing industrial teal and dense side-by-side state/fact panes.
- The prototype coexists with the Worklist and its inspector at 1440×900.
- Axe WCAG A/AA checks, document-width overflow checks, industrial computed
  style checks and mixed-language scans passed in all three locales.

## Three-language review captures

The captures were attached by the passing Playwright run at a 1440×900
viewport on the local Chromium/Darwin review runner. They are approval-review
captures, not the canonical fixed-Linux visual-regression baselines owned by
R1-06 Stage 3.

| Locale | Capture | SHA-256 | Review |
|---|---|---|---|
| English | `implementation/evidence/phase-5/r1-06-stage-1/playwright-report/data/26f74d3f0d0d2d9dd3b84ce93de80ca548c4e141.png` | `33bd048a433454a2e0e96683c081b377f3ef27448cdd6e707eb0973713f78b8e` | PASS |
| Simplified Chinese | `implementation/evidence/phase-5/r1-06-stage-1/playwright-report/data/4796f3b3bdf18317b0339d0ca6de1f37337490a6.png` | `8eee50e9b26b21626828e988fed5d6c077e467d9f088ebe5989a6c41899c8787` | PASS |
| Traditional Chinese | `implementation/evidence/phase-5/r1-06-stage-1/playwright-report/data/1bf96e993eac7810cb7969b1940c146cd4ff3226.png` | `c2bdfb976067d1df0eb4dab872c389672c5c759ed8e3cffc6000b53ea9482b7d` | PASS |

Original-resolution inspection found no ordinary mixed language, clipped
prototype control, horizontal document overflow, excess radius, decorative
shadow, missing visible state or competing page-level primary action.

## Approval manifest and entry gate

Manifest:
`implementation/prototype-approvals/r1-06-my-work-grid-reset.json`.

Reviewed source digest:
`cd5eea1ce8f88d27e0b8194c0d3e974f972b040680f259212f5d15fc99a13408`.

Normal repository verification accepts the manifest only as a truthful pending
record. The exact Stage 2 entry command is:

```text
python scripts/verify_prototype_approvals.py \
  --require-backend-approval my-work-grid-reset-undo
```

It currently fails with:

```text
backend implementation is blocked pending Product Owner approval
```

The verifier also rejects unknown fields/states/actions, source digest drift,
duplicate prototype IDs, fabricated pending authorization, an approval tied to
another revision/action/state set, missing approval evidence or malformed
Product Owner/timestamp/duration facts.

## Product Owner decision

- Decision: `PENDING_PRODUCT_OWNER`
- Product Owner identifier: unsigned
- Approved at: unsigned
- Approved prototype revision: unsigned
- Approved eligible action: unsigned
- Approved production duration: unsigned
- Approval evidence: unsigned
- Backend implementation authorized: `false`

Technical tests, screenshots, Codex review and this package do not sign or
replace the Product Owner decision. Until that decision is supplied, R1-06
Stage 2 remains scoped-held and the independent Stage 3 1440 visual-governance
work continues.
