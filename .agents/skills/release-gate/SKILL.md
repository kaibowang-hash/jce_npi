---
name: release-gate
description: Perform the final evidence-based merge or release review for an NPI One task. Use before every PR merge, milestone exit or production deployment.
---

# Release Gate

## Evidence required
- task acceptance mapping;
- diff and changed-file scope;
- real test logs;
- API/schema diff;
- migration/rollback;
- permission/security review;
- UI state evidence;
- integration fault evidence when applicable;
- docs updated.

## Block when
- scope creep or unapproved dependency;
- core patch/cross-DB/dual master;
- fake success or silent failure;
- missing permission/audit/version control;
- tests not run or failing;
- contracts differ from code;
- destructive migration without approval;
- critical path requires Desk;
- severe usability issue;
- unhandled high-risk UI action;
- secrets, test backdoors, hardcoded production IDs;
- unresolved TODO/placeholder in accepted path.

## Output
State `PASS` or `BLOCKED`. For BLOCKED, cite exact evidence and minimum fix. Never lower the gate to match the implementation.


## Visual and localization release blockers
- Any core page violates the single-primary, neutral, square, flat Siemens-style visual baseline.
- Ordinary component radius exceeds 2px without an approved semantic exception.
- Colorful KPI/card wall, gradient, glass effect, strong shadow or decorative illustration appears in business flow.
- User-visible text bypasses Frappe-compatible translation wrappers.
- Chinese UI contains non-allowlisted ordinary English, 英文界面 contains Chinese UI copy, or touched core flows have missing translations.
