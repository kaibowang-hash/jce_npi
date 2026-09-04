# P4-04 Gate Review Domain Checkpoint

Status: **IN PROGRESS — domain foundation only; P4-04 is not PASS**

Recorded: `2026-07-24T06:16:24Z`

## Delivered boundary

This checkpoint adds the independently testable, persistence-neutral domain
foundation for the P4-04 review policy and review-cycle aggregate. It provides:

- immutable, canonical, versioned policy snapshots bound to an exact Gate
  Template version and hash;
- allowlisted `always` and `requirement_priority_present` step selection;
- explicit separation of review, final-decision, and reopen authority slots;
- frozen authority bindings and parallel/sequential review enforcement;
- stale version and exact-input hash preconditions;
- fail-closed normal pass checks for selected approvals, required evidence,
  private-file safety, and blocking items;
- a server-built immutable decision snapshot and hash;
- controlled new-cycle reopen without copied approvals or overwritten decision;
  and
- a downstream guard that accepts only a current, non-stale pass decision.

No production policy is installed. The test policy is explicitly synthetic.
No DocType, migration, controller, BFF/OpenAPI, permission, exception/waiver,
automatic invalidation, impact action, frontend, localization catalog, browser,
or visual change is claimed by this checkpoint.

## Changed-files to affected-tests mapping

| Changed files | Affected checks |
|---|---|
| `apps/npi_core/npi_core/gate_review/__init__.py`, `domain.py` | `tests/test_phase4_gate_review_domain.py`; existing Gate Template and evidence domain tests; Ruff format/lint |
| `tests/test_phase4_gate_review_domain.py` | focused pytest collection; Ruff format/lint |
| controller/evidence records | `git diff --check`; manual trace/status review |

## Level 1 evidence

| Command | Result |
|---|---|
| `python -m pytest tests/test_phase4_gate_review_domain.py -q` | PASS — 8 tests |
| `python -m pytest -q` | PASS — 285 tests plus 257 subtests |
| `python -m pytest tests/test_phase4_gate_template_domain.py tests/test_phase4_gate_evidence_domain.py tests/test_phase4_gate_review_domain.py -q` | PASS — 21 tests plus 3 subtests |
| `python -m ruff check apps/npi_core/npi_core/gate_review tests/test_phase4_gate_review_domain.py` | PASS |
| `python -m ruff format --check apps/npi_core/npi_core/gate_review tests/test_phase4_gate_review_domain.py` | PASS |
| `git diff --check` | PASS |

## Recovery action

Continue P4-04 with the additive persistence model and repository/controller
boundary. Preserve this domain contract, add exception and invalidation event
aggregates, then expose only strict authorized BFF commands. P4-04 remains
unfinished until its complete vertical slice and triggered Level 3 Gate pass.
