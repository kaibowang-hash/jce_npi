# P8-06 Checkpoint 1 — Formal Quality Link Domain and Metadata

Status: **CHECKPOINT 1 PASS — exact-SHA ordinary verified**

Requirements: `INT-007`, `FR-TR-006`, `FR-NP-006`

Authorization transition:
`675c28a15133b9937ccac6af492db7c537a17946`, ordinary CI `32949383911`

Product checkpoint:
`64b59f219f4a5687865e6b27670e3bd11d186b88`, ordinary CI `32953275865`

## Delivered boundary

- Pure closed values for five NPI quality source contexts, three formal ERP
  record kinds, exact current observation references, immutable revisions,
  fixed command identity, five fault classes and canonical SHA-256 payloads.
- Default configuration installs zero profiles and rejects enablement,
  authority or freshness values until later explicit approval.
- Three additive read-only DocTypes install no fixture/default rows: Formal
  Quality Link Revision is append-only; Link Head requires exact `+1`
  revision/optimistic CAS; Command Idempotency permits only a one-way sealed
  response.
- A request-local internal capability guards insert/save and restores all
  flags in `finally`. There is no checkpoint-1 writer or capability caller.
- Link Revision revalidates exact P8-01 observation and head identity,
  containment, payload/head hashes, availability, freshness, disposition and
  optimistic version. It stores raw status/result only and has no pass field.
- Ownership keeps ERP formal quality identity/status/result ERPNext-owned and
  immutable NPI link history NPI-owned. OpenAPI adds closed components only;
  paths and integration events are unchanged.
- Every new English literal has direct `zh` and `zh-TW` translation and the
  generated frontend catalog is synchronized.

## Explicit non-scope and holds

No route/API/BFF, repository, row creation, integration event, Outbox,
enqueue, scheduler, worker, adapter, runtime fixture, UI, browser target call,
ERP mutation, credential, production contact or generic reconciliation is
introduced. P8-01 remains the sole formal-quality observation/head/order/
freshness owner. Current ERPNext Quality Inspection/NCR/CAPA mappings,
service scopes, workflow, raw-code interpretation, source authority,
cardinality, freshness/reconciliation owner and Sandbox profile remain
Class-B holds; production access and irreversible migration remain Class C.

## Level-1 evidence

- focused quality-link tests: `19/19` PASS;
- P8-01 projection plus P7 quality/review/readiness regressions: `97/97` PASS;
- Item, MBOM and Tool Asset config/domain/contract/metadata/security peers:
  `106/106` PASS;
- affected Python total: `222/222` PASS;
- generated catalog current; i18n audit: `8,403` literal English sources,
  direct `100%` `zh`/`zh-TW` coverage;
- current-task and reconciliation units: `35/35` PASS; both reconciliation
  scripts and the current-task verifier PASS;
- targeted Python compilation, shell syntax, JSON/YAML/CSV parsing, security
  scans and `git diff --check` PASS;
- the exact `32`-path checkpoint diff is accepted, its simulated post-commit
  base-to-tip manifest is the frozen exact `43` paths, and a synthetic
  unauthorized `33`rd checkpoint path is rejected fail-closed.

Exact-SHA ordinary CI passes frontend `98129304814`, repository
`98129305104`, secret `98129305097` and governed visual `98129305261`;
controlled lanes correctly skip because this checkpoint has no route or
runtime behavior.

Checkpoint-2 controller authorization exact SHA `bc6095c` passes ordinary CI
`32955709358`. The separate FR-CO-003/004 scope-decision exact SHA `51c552a`
passes ordinary CI `32957762888` and changes no checkpoint-1 product fact.
Checkpoint-2 product work remains closed until its governance-only restoration
passes exact-SHA ordinary CI; the external-portal decision remains durable.

Checkpoint 2 subsequently passes exact accepted tip `9983a8d` and ordinary CI
`32964612981` across frontend `98164272727`, repository `98164272787`, visual
`98164272829` and secret `98164272855`. Product commit `2e4ace3` remains the
exact-fourteen implementation. The final exact-two test change only prevents
the direct-SQL scanner from matching its own negative-test literal; the same
runtime forbidden-symbol contract remains, so product root count is zero.

The separate checkpoint-3 controller transition authorizes no product until
its own exact-SHA ordinary CI. Its future exact-nine boundary is read-only
current/drift/unavailable reconciliation on the existing list/detail response.
It adds no route, write, P7 policy effect, Outbox, worker, adapter, network,
runtime, UI or raw-code pass interpretation. All existing Class-B/Class-C and
FR-CO-003/004 holds remain unchanged.

## Checkpoint-3 affected-test manifest correction

The frozen Level-1 command originally named a standalone
`tests.test_phase7_readiness_source_resolver` module that does not exist in the
repository. This is a governance-path defect, not a product or coverage root.
The corrected command retains the full
`tests.test_phase7_readiness_repository` suite and adds the existing
`tests.test_phase7_readiness_repository_seams` suite, where the readiness
source-resolver seam contract is actually pinned. Both suites pass before the
checkpoint-3 exact-nine product diff is staged. No test, scanner, threshold,
product path or acceptance condition is removed or weakened.

## Rollback

Before any future link row exists, revert this pure module, components,
translations/tests and the three additive metadata definitions; remove
metadata only on a disposable Site after proving zero rows. Once later
history exists, disable future routes/UI and retain immutable revisions,
heads, receipts and audits for forward repair. Never rewrite ERP observation
truth or convert unavailable/raw evidence into pass.

## Checkpoint-3 acceptance and checkpoint-4 boundary

Checkpoint 3 passes exact product SHA
`f09f7baed565b232f37530ede3df0a13fb466a1e` and ordinary CI
`32971175544`: frontend `98185026209`, repository `98185025979`, visual
`98185026270` and secret `98185026147` pass. Its exact-nine boundary adds only
read-only current/drifted/unavailable facts.

The separate checkpoint-4 transition changes no product. Its future exact44
boundary is one compact Trial-quality/readiness inspector, one existing NPI
link Impact Review gated by both server query permission and exact source
capability, direct EN/zh/zh-TW/a11y/visual evidence and one disposable
network-free cumulative runtime. It reuses existing routes and adds no ERP
write, Outbox, worker, adapter, browser target network or pass/Gate mapping.
All Class-B/Class-C and FR-CO-003/004 holds remain unchanged.

## Checkpoint-4 same-cycle CI harness evidence

Checkpoint-4 product SHA `0bc2687f9541fb14fa348614c16968c182aafcbb`
reached ordinary run `32983850058`. Repository job `98227122886`, frontend
job `98227123050` and governed visual job `98227123047` expose only stale
current-scope, asynchronous-load and unmocked-inspector fixture contracts;
secret scanning passes. The product root count is zero.

The authorized repair is exact fourteen changed paths: three runtime tests,
one readiness unit test, two P7 E2E fixtures, one current-task verifier test,
three Linux Bookworm/x64
baselines and four governance paths. All six visual cases remain mandatory;
P7-04 English/Simplified Chinese and P7-07 Traditional Chinese are tested but
bit-identical to their existing canonical files after the terminal gate.
Historical assertions remain exact;
readiness proves one loaded empty response; P7 fixtures prove both exact GETs
and terminal inspector state. Product source, API, permission, runtime,
translations, thresholds, Darwin baselines and all B/C holds are unchanged.
The old run is immutable and will not be rerun. Acceptance requires focused
tests, two focused-six no-update visual runs, full 132 no-update, exact-path
manifest acceptance with an unauthorized fifteenth path rejected, a new
exact-SHA ordinary PASS and then one Level-3 Gate.

## Formal-quality runtime-stage diagnostic checkpoint

Exact harness SHA `f382e708564e7b82cb54ac54280fbf722249e0b0`
passes ordinary `32989038683`: repository `98241964702`, frontend
`98241964596`, visual `98241964309` and secret `98241964649` pass, with the
native visual lane proving `132/132`. The sole Level-3 run `32990691540`
passes repository `98247307210`, frontend `98247306942`, visual `98247307155`,
secret `98247307189` and controlled preflight `98251578444`. Runtime
`98251654660` then fails only at the outer formal-quality-link verifier
boundary; disposable cleanup passes. No child output, business value, private
path or stack is accepted as evidence.

Static cross-proof excludes workflow, Bench/Site initialization and the prior
P8-01 projection fresh/disable/recover/replay/redaction chain, but cannot
select among verifier bootstrap/readiness, disposable projection setup,
create/replay/stale/list or cleanup predicates. Checkpoint-4 final `1/1` is
therefore immutable and no product repair is allowed.

The independent `p8-06-quality-link-runtime-stage` cycle is diagnostic `0/1`,
repair `0/1`, final `0/1`. Its exact-six change is verifier/evidence only. The
single active verifier flag selects seventeen fixed ordered parent codes and
one exact run-scoped trace. Failure writes at most one exclusive exact-three-
key safe record; innermost stage wins, the original exception is re-raised and
`finally` remains unchanged. The parent shell never reads failed-child output.
Its strict reader accepts one allowlisted code, validated exception class and
equal trace only; all other cases retain the static outer failure with no
leak. Product, permissions, transactions, ownership, contracts, migrations,
UI, translations, visuals, target network, FR-CO-003/004 deferral and all B/C
holds are unchanged.

## Prepare-projection substage diagnostic checkpoint

The exact runtime-stage diagnostic checkpoint
`71b3ee9276c6078175682ffdc7528e84ccdc7249` passes ordinary CI
`32994361662`. Controlled diagnostic `32995898417` passes preflight and fails
only in runtime job `98265034895`, exposing the safe tuple
`P806_QUALITY_PREPARE_PROJECTION / RuntimeError /
trace-d41bef28f3675f2287359d7258a83015`. Failed-child output, business values,
IDs, messages and stacks were not read. The previous cycle freezes at
diagnostic `1/1`, repair `0/1`, final `0/1`.

The parent wrapper converts every nonzero prepare child into the same
`RuntimeError`; real-Site P8-01 projection and Project-first readiness
boundaries pass, but the tuple remains nonunique across the Readiness-scoped
apply, persistence, audit, collection and commit sequence. No product repair
is selected.

The independent `p8-06-quality-link-prepare-projection` cycle starts at
diagnostic `0/1`, repair `0/1`, final `0/1`. Its exact-eight checkpoint turns
the old flag off and enables one exact new scope. Four parent and thirty-nine
child/repository lexical stages share the validated trace. Child failures use
the existing response-neutral safe logger. The strict cursor reader accepts
one logical exact-three-key mirrored record; a trusted server tuple wins,
otherwise a fixed parent stage is used. Innermost wins, the original exception
and `finally` behavior are retained, failed-child stdout/stderr remain unread,
and dormant/no-scope execution produces no record.

Focused tests pin mutual exclusion, exact allowlists and lexical uniqueness,
trace propagation, server-win and parent-fallback behavior, malformed,
duplicate and wrong-trace rejection, no leak, default-off behavior, unchanged
projection ordering and zero direct SQL/network/commit additions. Product
values, permissions, transaction boundaries, write order, responses,
rollback, API, contracts, metadata, migrations, UI, i18n, ERP target traffic,
FR-CO-003/004 deferral and every B/C hold remain unchanged.

## Prepare-projection bootstrap diagnostic checkpoint

Exact prepare-projection checkpoint
`cf4f431e4ca3d74f50716bfbaa8e7c2d66e3d83e` passes ordinary
`32998865737`. Its sole controlled diagnostic `33000193191` passes preflight
job `98279700208`; runtime job `98279799344` reports only
`P806_QUALITY_PREPARE_PARENT_CHILD_STATUS / RuntimeError /
trace-9996bb78f674578fae7afed049451082`. No failed-child output, business
value, ID, message or stack was read.

The no-server-tuple condition is uniquely a harness bootstrap defect. The
fresh child entered `quality_link_prepare_projection_diagnostics` before
`frappe.init`; pinned Frappe binds `frappe.flags` only in init, so the
context's first flags lookup raised on an unbound local proxy and its
best-effort guard yielded without diagnostic state. The prior unit fake
pre-bound a `SimpleNamespace` and therefore missed this real lifecycle. This
does not identify a product predicate, so the old cycle freezes at diagnostic
`1/1`, repair `0/1`, final `0/1` without repair.

Independent `p8-06-quality-link-prepare-bootstrap` starts at diagnostic
`0/1`, repair `0/1`, final `0/1`. Its exact-five verifier/evidence paths add
one active harness flag and five direct bootstrap stages for imports,
arguments, init and active-context proof. Each may write only the existing
exclusive exact-three-key safe record. Repository diagnostics begin only
after init; later product failures retain the existing thirty-nine lexical
server stages, strict mirrored reader and server-inner preference. The
original exception/finally behavior and failed-child-unread contract remain
unchanged.

Product code, APIs, permissions, transactions, source ownership, values,
write order, rollback, metadata, migrations, UI, i18n, ERP target traffic and
all B/C holds remain unchanged. FR-CO-003/004 remain
`USER_APPROVED_POST_V1_2_DEFERRED`. Production SSH/read-only facts and final
DoD documentation remain a separate queued governance task and are not
authorized here.

Level 1 passes focused bootstrap/projection `25/25`, affected P8-06/P8-01/P7
and Item/MBOM/Tool Asset peers `297/297`, full repository Python `2528/2528`
and current/reconciliation `36/36`. Current and reconciliation scripts,
compile, shell syntax, activation/security/no-leak scans and diff hygiene pass.
The exact-five manifest and base union are accepted; an unauthorized sixth
path is rejected.
