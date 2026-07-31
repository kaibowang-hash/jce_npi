# Active Execution Goal

Updated: `2026-07-31T20:15:18Z`

- Goal: `NPI One V1.2 — Reconciled Autopilot Continuous Delivery`
- Codex Goal ID: `019fb65e-318b-7fb1-8775-0d600b154ef0`
- Mode: `IN_PROGRESS — P5-03 AUTHORIZED ACTIVE`
- Final target: `IMPLEMENTATION_COMPLETE` or a true Hard Blocker defined by
  `implementation/AUTOPILOT_CONTROLLER.md`
- Branch: `codex/npi-v1.2-implementation`
- Latest passed product checkpoint:
  `f088d70b00b54488587b2a83a311b636ef48cf78`
- Local and remote product SHA:
  `f088d70b00b54488587b2a83a311b636ef48cf78` (`0 ahead / 0 behind` before
  the P5-02 evidence/controller commit)
- Complete normal CI:
  `30661086073` (`PASS`)
- Final unchanged controlled-Site Gate:
  `30661586342` (`PASS`)
- Current controller task:
  `P5-03 — Baseline and impact invalidation`
  (`READY — REQUIREMENT/DOMAIN AUDIT`)
- Current Requirement IDs:
  `FR-DS-006`
- Completed P5-02 evidence:
  `implementation/evidence/phase-5/p5-02-validation.md`
- Current product Phase:
  `5 — Part Design, Documents, Baselines, and EBOM` (`IN_PROGRESS`)
- Latest complete product Phase:
  `4 — Project Work Items and Stage Gates` (`PASS`)

## Historical passing and reusable evidence

The remainder of this file preserves chronological recovery detail. Where a
historical paragraph says P5-01 was incomplete or P5-02 inactive, the
authoritative current state is the header above together with
`implementation/PHASE_STATUS.yaml` and `implementation/NEXT_ACTION.md`.

R1-01 through R1-06 are complete for their executable scope. Conditional R1-07
was not activated because `DR-REC-001` remains pending.

The cumulative exit result is:

`PASS — LEVEL 3 R1 SHARED SHELL/DESIGN/I18N EXIT GATE`

Terminal synchronized evidence:

- CI `#72`, run `30546528862`;
- repository job `90884045344`: `763/763` Python, `634/634` frontend unit,
  `279/279` non-visual browser, `2,782` complete direct trilingual sources,
  both zero-vulnerability audits and both secret scans;
- visual job `90884045367`: exact fixed-Linux `24/24`;
- current visual inventory: `231` cases completely covered by the accepted
  210-case matrix plus every source-affected replacement and `21` additive
  cases; and
- current trace: `282` unique IDs =
  `173 PACK_CANONICAL / 95 DOCX_RECONCILED / 14 ADDENDUM_DIRECT`.

The pushed recovery checkpoint `c980571b27be66e16f2ac57409f0ef72a986e741`
then passed CI `#73`, run `30548142786`: `764/764` Python, `634/634`
frontend unit, `279/279` non-visual browser, `24/24` fixed-Linux visuals,
complete direct trilingual coverage, both zero-vulnerability audits and both
secret scans. This seals the controller/evidence checkpoint without changing
the original R1 Gate decision.

The subsequent bounded P5-01 resume-audit checkpoint
`ee8730133e8cdd30fc7bff158ab80a252ed14249` passed CI `#74`, run
`30549749537`, including both repository and fixed-Linux visual jobs. The
controller synchronization commit
`9198dc9c54d314c9927ff5aa68ce17253f6f4afe` then passed CI `#75`, run
`30550637406`.

The P5 frontend/runtime-ready product checkpoint, its three bounded CI repair
loops and the exact reviewed historical synthetic fingerprint then converged
at `86f3fde02303a5088c5ec4d4be906efcdb83c96d`. CI `#79`, run
`30560612349`, passed the complete repository, `285/285` non-visual browser,
fixed-Linux visual, current-tree secret and complete PR-history secret lanes.
It is the latest complete CI recovery point.

The manual controlled-runtime lane checkpoint
`3839503982223470fafb7e268f3331089418b350` then passed normal CI `#80`,
run `30561689283`: complete repository, `285/285` non-visual browser,
fixed-Linux visual, current-tree secret and complete PR-history secret lanes.
The first manual dispatch, run `30562284484`, proved the event, ref, SHA and
read-only permissions, then failed before Bench/Site/Compose/database work
because npm rejected Yarn's preinstall script without an explicit allowlist.
The bounded repair retains the runner's already exact Yarn and verifies all
three tool versions fail closed; no runtime result is claimed yet.

That repair checkpoint `7e47dbbae4832a7495ab7cf6c3085ba6afbd7f21`
passed normal CI `#81`, run `30562550109`, including complete repository,
`285/285` browser, fixed-Linux visual and both secret lanes. Its manual run
`30563106063` installed both exact Python packages and again reported exact
Yarn, but a silent CLI presentation-string comparison returned nonzero before
initialization. The bounded repair now uses exact installed distribution
metadata for Bench/uv and retains the exact Yarn CLI version check.

That repair checkpoint `b500dfac18bac9260fed5a39140a0fdc2a112b9f`
passed normal CI `#82`, run `30563401058`, including the complete repository,
`285/285` browser, fixed-Linux visual and both secret lanes. Manual run
`30564025523` then passed tool and pinned Bench setup, created only the guarded
fresh Site after the live database identity proof, and failed before NPI app
installation because Bench's unterminated `apps.txt` joined `frappe` and
`npi_core`. The runner removed both containers, both new volumes and its
network. The bounded repair restores only the missing line boundary before an
app-name append and rejects a missing registry.

The app-registry repair checkpoint
`5dfb99df923ed112ea4eae2ea1b8019ec723d953` passed normal run
`30564533440`: complete repository, `285/285` browser, fixed-Linux visual and
both secret lanes. Manual run `30565065165` passed exact tool/Bench/database
guards, installed both NPI apps on the fresh Site and completed both
migrations. The unchanged verifier then failed closed at its first schema
fixture because it required obsolete `response_payload` metadata instead of
the existing sealed `response_snapshot` and `response_sealed` contract.
Cleanup removed the two containers, two volumes and runner-local network.
The current bounded repair changes only this verifier inventory and its
regression assertion; no product or runtime PASS is claimed.

That schema-inventory repair checkpoint
`56e1b75d6b34fd000df34d0ab70016d9163143f4` passed normal run
`30565607707`, including the complete repository, `285/285` browser,
fixed-Linux visual and both secret lanes. Manual run `30566120000` then
passed exact tool/Bench/database guards, installed both apps, completed both
migrations and passed the corrected nine-DocType schema fixture. Its
synthetic Project command returned HTTP `422` because the fixture used
`Administrator` as `ownerUserId`, while the retained Project command requires
a canonical email owner. Cleanup removed both containers, both volumes and
the runner-local network.

This was the fifth complete genuine controlled-runtime repair round and
correctly triggered the controller Hard Blocker. The user explicitly
authorized exactly one additional bounded owner repair. Candidate `a2d98e2`
passed `91/91` affected and `774/774` complete tracked Python tests plus normal
CI run `30569830739`.

Manual run `30570343315` proved that repair through successful Project,
Document Policy root and policy-draft creation. Publishing the draft returned
HTTP `500` at the first P5 Frappe `Datetime` persistence boundary. The
code-backed shared root is canonical ISO `T`/`Z` API text being assigned
directly to Frappe database datetime fields. The user-authorized round is now
exhausted and the necessary Gate remains failed. Exact evidence:
`implementation/evidence/phase-5/p5-01-controlled-runtime-datetime-blocker.md`.

The user then explicitly authorized one bounded shared-Datetime repair.
Candidate `7aa14edbdd2e484784cee6a8ec52adef4f6bf328` applied one reviewed
Frappe storage adapter to all thirteen affected P5 Document Datetime fields,
preserved canonical snapshot/API truth, added semantic comparisons and passed
normal CI `#98`, run `30573186630`.

The single authorized controlled dispatch `#99`, run `30573778175`, passed
the previously failing policy publication, controlled document creation and
its immediate idempotency replay. The first document `:check-out` returned
HTTP `500`. The generic document-workspace assertion did not emit the new
sanitized exception type/message, so the retained evidence cannot uniquely
distinguish lock-event insertion, document projection save, audit append or
response reconstruction. The one authorized dispatch is exhausted. Exact
evidence:
`implementation/evidence/phase-5/p5-01-controlled-runtime-checkout-blocker.md`.

The user explicitly authorized one additional bounded P5-01
controlled-runtime diagnostic/repair round on 2026-07-31. That authority is
limited to document-workspace sanitized diagnostics, one diagnostic-only
controlled-Site dispatch, repair of only the proven checkout transaction root,
affected checks and normal CI, and one final unchanged controlled-Site Gate.
The diagnostic checkpoint now carries the deterministic request/trace identity
to the workspace boundary and reads only an exact three-field safe BFF record
from a fixed physical Bench log with a 64 KiB tail bound. Focused `15/15` and
complete tracked Python `781/781` tests passed locally. No product contract,
DocType, permission, transaction, lock, audit or idempotency behavior changed.

Exact checkpoint `e4b284f6360a852ffd81d6a9e7b0f41f65f363a9`
passed normal CI `#101`, run `30598406263`. The sole authorized
diagnostic-only dispatch `#102`, run `30598733723`, passed setup, both
migrations, the fixed disposable Site and all previously reusable steps, then
reported only
`exc_type=ValidationError; diagnostic_code=UNEXPECTED_BFF_EXCEPTION`
at checkout. Cleanup passed.

That class is still shared by the checkout idempotency receipt, immutable lock
event, exact lock projection and response-receipt seal validations. The safe
record does not carry a stage code, so the run cannot prove which transaction
boundary failed. The single diagnostic dispatch is exhausted; changing any
one candidate would guess at the root and violate the explicit authorization.
Exact Hard Blocker evidence:
`implementation/evidence/phase-5/p5-01-controlled-runtime-checkout-stage-blocker.md`.

The user explicitly authorized one additional bounded stage-diagnostic
checkpoint and one controlled-Site diagnostic dispatch on 2026-07-31. The
authorization permits only allowlisted checkout stage code, validated
exception type and exact trace ID, followed by repair of only the proven
stage; the already authorized final unchanged Gate remains reserved.

The local checkpoint now distinguishes receipt insert, lock-event insert,
projection save, audit append, response build and receipt seal without
changing their order or behavior. Diagnostics exclude `NpiProblem`, raw
exception text, traceback, request, cookie and credential data. Focused
checkout/repository/verifier tests pass `28/28`, the complete P5 Document
module group passes `83/83`, and complete tracked Python passes `784/784`.
Evidence:
`implementation/evidence/phase-5/p5-01-controlled-runtime-checkout-stage-diagnostic.md`.

Exact stage-diagnostic checkpoint
`954bd0d08b9f82614e34cc0e92e67f5de0340db9` passed complete normal CI
`#104`, run `30600587269`. The sole authorized stage-diagnostic dispatch
`30600943765` matched that SHA, passed fixed setup, both migrations and
cleanup, and safely proved
`ValidationError / DOCUMENT_CHECKOUT_PROJECTION_SAVE`. The exact request
trace was equality-validated against the existing three-field safe record
before the result was accepted and was not echoed to the job output.

The bounded repair candidate changed only the projection-save boundary by
binding the save to the exact immutable acquisition-event name returned by
the successful prior insert. Focused `41/41`, complete P5 Document `85/85`
and complete tracked Python `786/786` tests passed locally, but the candidate
remained a hypothesis until the controlled Gate. Its later failure and
forward reversion are recorded below.

The exact repair checkpoint is
`b2d7ca9256a0dd62a693baa6feea1c53fd33402f`. Complete normal CI run
`30601670711` passed its repository, complete E2E, fixed-Linux visual and both
secret-scan lanes.

The retained final unchanged controlled-Site Gate `30601980685` matched that
SHA. Fixed tools, disposable Site/database, both app installations, both
migrations and cleanup passed, but checkout again returned the exact safe
result `ValidationError / DOCUMENT_CHECKOUT_PROJECTION_SAVE`. Therefore the
acquisition-event selector hypothesis is disproven. The failed candidate is
forward-reverted in the blocker checkpoint.

The remaining failure is within the Frappe Controlled Document `save()`
lifecycle after receipt and lock-event insertion. Current authorized evidence
cannot distinguish identity/policy hydration, domain reconstruction,
optimistic-version validation, exact lock-projection validation or a later
Frappe save hook. Both authorized controlled executions are exhausted. A new
projection-substage diagnostic checkpoint/dispatch plus a new final unchanged
Gate require explicit bounded authorization.

Complete bridge evidence:
`implementation/evidence/reconciliation/r1-shared-bridge-level-3-validation.md`.

These accepted results are not rerun unless P5-01 changes their source
boundary. Historical Phase 3/4, P5-00, P5-01 checkpoint and R1 evidence remains
append-only.

## Historical P5-01 delivered scope

Retained at `930b5a2`:

- controlled document/revision/File Revision identities and domain invariants;
- nine additive controlled DocTypes and guarded controllers;
- Project/tenant/actor-bound repository and command idempotency;
- fixed document BFF/API/OpenAPI/data-ownership contracts;
- confidential audited binary retrieval and URL-free capability truth;
- external/CAD/PDM unavailable seams;
- direct backend/DocType `zh` and `zh-TW` sources; and
- focused backend/contract tests.

Delivered in the current frontend/runtime-ready candidate:

- strict closed browser parsers, data sources and FormData/Blob handling;
- a live dense Project Documents workspace with exact policy, revision, file,
  relationship, lock and provider truth;
- registered App/Project/history/`beforeunload` dirty-state protection;
- complete direct `zh`/`zh-TW`, affected unit, browser, accessibility and
  exact trilingual visual evidence;
- a fail-closed controlled-Site migration/runtime verifier; and
- Requirement → Code → Test → Evidence plus changed-files → affected-tests
  mapping.

Still unfinished:

- actual execution of the additive/idempotent migrations and complete
  controlled Frappe runtime on the fixed disposable Site;
- final Task Diff/domain/permission/security/UX/i18n review after that runtime;
- P5-01 Level 2 Task Gate; and
- every later P5 task.

No P5-01 requirement is yet reported complete.

## Historical P5-01 first incomplete action — superseded

The frontend/runtime-ready checkpoint is recorded at
`implementation/evidence/phase-5/p5-01-frontend-runtime-checkpoint.md`.
Frontend, unit, browser, visual, translation and static runtime checks pass.

The authorized projection-validation diagnostic proved
`DOCUMENT_CHECKOUT_PROJECTION_REVISION / ValidationError`. The only proven
repair is complete at `7dc4dc0`; focused `44/44`, complete P5 Document
`88/88`, complete tracked Python `789/789` and complete normal CI
`30605323680` pass.

The single final unchanged Gate `30605683679` matched `7dc4dc0`. Its
repository/E2E/security, fixed-Linux visual, exact setup, both migrations and
cleanup passed, but the controlled job emitted only the safe
`UNEXPECTED_BFF_EXCEPTION / PdfStreamError` result and failed. The prior
revision substage did not recur, but the new generic code does not prove a
unique post-checkout revision/upload stage.

The first incomplete action requires the explicit bounded authorization
recorded in `implementation/NEXT_ACTION.md`. Do not add revision/upload stage
diagnostics, make another repair or dispatch another controlled Site before
that authority exists.

P5-01 remains incomplete and P5-02 remains inactive.

Do not start P5-02, add review/release/baseline/EBOM behavior, enable external
retrieval, claim an Office/CAD viewer or connect ERPNext/JCE/CAD/PDM.

## Scoped holds that remain truthful

- Production document classes, numbering, revision, release authority,
  confidentiality, retention, scanner/viewer and sharing rules remain
  unresolved Class-B inputs.
- R1-06 Stage 2 remains held by its unsigned Product Owner approval.
- R1-07 remains unactivated while `DR-REC-001` is pending.
- Phase 3 named business UAT and sanitized-data provenance remain externally
  unsigned.
- Production ERPNext/JCE/CAD/PDM access remains prohibited.

These hold only their named behavior and are not currently global Hard
Blockers.

## Historical P5-01 recovery boundary — closed

The R1 bridge Gate remains complete at
`2ced098362ab99a4750a13e7004a441a7f19b698` and CI `#72`; its pushed recovery
checkpoint is `c980571b27be66e16f2ac57409f0ef72a986e741` with CI `#73`. The
P5-01 retained backend checkpoint remains `930b5a2`; its resume-audit
checkpoint is `ee8730133e8cdd30fc7bff158ab80a252ed14249` with CI `#74`; controller
checkpoint `9198dc9c54d314c9927ff5aa68ce17253f6f4afe` passed CI `#75`. The
frontend/runtime-ready candidate and its bounded CI repairs are complete at
`86f3fde02303a5088c5ec4d4be906efcdb83c96d` with CI `#79`; the manual lane
checkpoint is complete at `3839503982223470fafb7e268f3331089418b350` with
CI `#80`; the first setup repair is complete at
`7e47dbbae4832a7495ab7cf6c3085ba6afbd7f21` with CI `#81`. P5-01 remains
incomplete and is now at the proven projection-save repair checkpoint; the
distribution-metadata repair is complete at
`b500dfac18bac9260fed5a39140a0fdc2a112b9f` with CI `#82`. The app-registry
repair is complete at `5dfb99df923ed112ea4eae2ea1b8019ec723d953`
with normal run `30564533440`; the schema repair is complete at
`56e1b75d6b34fd000df34d0ab70016d9163143f4` with normal run
`30565607707`. The owner repair is complete at
`a2d98e23f7dd4d37cb66ae220beade32123bd567` with normal run
`30569830739`; its authorized controlled run `30570343315` failed at policy
Datetime persistence after Project and draft-policy success. The bounded
shared-Datetime repair is complete at
`7aa14edbdd2e484784cee6a8ec52adef4f6bf328` with normal CI `#98`, run
`30573186630`; its single authorized controlled run `#99`, `30573778175`,
passed policy publication/document creation/replay and failed the first
checkout with HTTP `500`. Diagnostic checkpoint
`e4b284f6360a852ffd81d6a9e7b0f41f65f363a9` passed normal CI `#101`;
diagnostic run `#102`, `30598733723`, safely narrowed the exception class to
Frappe `ValidationError` but not a unique transaction stage. Stage checkpoint
`954bd0d08b9f82614e34cc0e92e67f5de0340db9` passed normal CI `#104`;
dispatch `30600943765` then proved
`ValidationError / DOCUMENT_CHECKOUT_PROJECTION_SAVE`. Its disproven bounded
repair is forward-reverted at checkpoint `cefe763`. Projection-validation
diagnostic checkpoint `57b4314` passed normal CI `30604536515`; dispatch
`30604964265` proved
`DOCUMENT_CHECKOUT_PROJECTION_REVISION / ValidationError`. Its only proven
repair is `7dc4dc0`, with normal CI `30605323680` passing. Final unchanged
Gate `30605683679` then failed later with only
`UNEXPECTED_BFF_EXCEPTION / PdfStreamError`; its repository/E2E/security,
visual, setup, migrations and cleanup passed. The fixed controlled Site has
not passed. The fifth-round Hard
Blocker remains historically recorded at
`implementation/evidence/phase-5/p5-01-controlled-runtime-blocker.md`; its one
authorized recovery is complete at
`implementation/evidence/phase-5/p5-01-controlled-runtime-extra-repair.md`.
The historical checkout blocker evidence is
`implementation/evidence/phase-5/p5-01-controlled-runtime-checkout-blocker.md`;
the completed bounded diagnostic evidence is
`implementation/evidence/phase-5/p5-01-controlled-runtime-checkout-diagnostic.md`;
the historical stage blocker evidence is
`implementation/evidence/phase-5/p5-01-controlled-runtime-checkout-stage-blocker.md`;
the completed checkout-stage evidence is
`implementation/evidence/phase-5/p5-01-controlled-runtime-checkout-stage-diagnostic.md`;
and the active Hard Blocker evidence is
`implementation/evidence/phase-5/p5-01-controlled-runtime-projection-validation-blocker.md`.

On compaction, model switch, tool interruption or handoff, reread this file,
`implementation/PHASE_STATUS.yaml`, `implementation/NEXT_ACTION.md`,
`implementation/LAST_RUN.md`, `implementation/phase-5-requirement-anchor.md`,
`implementation/evidence/phase-5/p5-01-plan.md` and
`implementation/evidence/phase-5/p5-01-frontend-runtime-checkpoint.md`. Chat
memory is non-authoritative.
