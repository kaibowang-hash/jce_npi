# Phase 7 Requirement Anchor — Trial, Quality Collaboration, and NPI Readiness

Status: **ANCHORED — P7-00 LEVEL 2 PASS**

Anchor date: 2026-08-10

Controller phase: 7 — Trial, Quality Issues, and NPI Readiness

Compatibility milestone: M6 — Trial and NPI

Starting controller checkpoint:
`e662684ffefd9d44c11a0e5e70e8801bd0a5f1e3`

Retained product/runtime checkpoint:
`68f230fee73b1b6ca95206346d128e1518613d82`

## 1. Authority and bounded outcome

This anchor applies the V1.2 continuous-delivery authority to
`FR-TR-001..010`, `FR-NP-001..015` and `UX-020`. It also carries the accepted
`FR-TX-019` fact-layer foundation, the technically verified `FR-PRN-002`
controlled-output foundation and the NPI-side snapshot portion of
`FR-INT-015`. The exact external event and ERP/JCE projection remain held by
`DR-REC-009`.

The bounded demonstrable Phase 7 path is:

> plan one Trial -> create a distinct immutable Round identity -> lock exact
> product, Tooling, material, parameter, inspection and evidence inputs ->
> record versioned actual parameters and sample/cavity truth -> carry defects,
> actions and independent verification across Rounds -> compare Rounds and
> freeze a conclusion -> evaluate versioned NPI checklist evidence and explicit
> blockers -> retain handover and observation snapshots -> release one
> immutable NPI-owned Trial Summary and controlled output -> expose only the
> same authorized field actions on supported mobile layouts

Phase 7 owns Trial planning and collaboration, exact Round inputs and actuals,
sample/cavity trace, NPI-owned defects/actions, Trial conclusions, readiness
snapshots, handover evidence, observation evidence and the immutable NPI-side
Released Trial Summary. ERPNext continues to own formal Quality Inspection/NCR
results, Item/material master truth, production transactions, actual production
and quality metrics, official manufacturing execution and external projection
confirmation.

## 2. Requirement allocation and atomic order

| Atomic task | Compatibility task | Primary requirements | Truthful delivery boundary |
|---|---|---|---|
| P7-01 — Trial plan and Round identity/lifecycle foundation | M6-01 | FR-TR-001 | Separate Plan and Round identities, Project/Tooling containment, planned resources and versioned command policy; no guessed production numbering, reservation or approval authority |
| P7-02 — Locked inputs, parameters, actuals and samples | M6-02 | FR-TR-002, FR-TR-003, FR-TR-010; FR-NP-004, FR-NP-005; FR-TX-019 foundation | Exact immutable input-lock snapshots, versioned TP Trial Actual, parameters, material/sample batches and clean File Revision evidence; no machine/ERP connection or fake measured value |
| P7-03 — Cavity defects, actions and verification | M6-03 | FR-TR-004, FR-TR-009; FR-TL-009/010 foundation | Round/cavity-specific defect lineage, responsibility, target Round and independent verification; no automatic NCR, Gate or Tooling lifecycle mutation |
| P7-04 — Round comparison, conclusion, quality and approval references | M6-04 | FR-TR-005..008 | Exact input/parameter/dimension/defect comparison, immutable conclusion, controlled quality/approval references and one-page summary input; formal ERP quality remains read-only/unavailable and business authority is policy-bound |
| P7-05 — NPI checklist, readiness and blockers | M6-05 | FR-NP-001..013 | Versioned template and frozen Project instance, evidence/checklist/pilot/training/supplier/capacity truth, derived category/total scores and separately dominant blockers; no percentage may hide a blocking item or fabricate ERP results |
| P7-06 — Production handover and observation period | M6-06 | FR-NP-014, FR-NP-015 | Immutable handover package/acknowledgement and observation snapshots with explicit unresolved actions and unavailable external actuals; no automatic G7 close or production transaction |
| P7-07 — Immutable Released Trial Summary and controlled output | M6-07 | FR-PRN-002; FR-INT-015 NPI-side foundation; FR-TR-008 output | NPI-owned immutable summary with exact inputs/actuals/cavities/issues/conclusion/references and reuse of controlled-print snapshot/output mechanics; no external event, projection, production form mapping or copy policy under DR-REC-009/003/004 |
| P7-08 — Mobile field actions | M6-08 | UX-020 | Responsive Trial/Gate review, permitted status/action preparation, photo evidence, issue capture and scan entry through the same BFF capabilities; complex engineering tables remain desktop and mobile grants no new authority |

`ANCHORED_P7_XX` means allocated, not implemented or accepted. Existing
verified foundations keep their truthful earlier status and gain only an
anchor reference until the relevant Phase 7 task produces new evidence.

## 3. Frozen identities and version boundaries

### 3.1 Trial Plan and Trial Round

- `TrialPlan` and `TrialRound` are distinct aggregates. A Plan may schedule
  resources and propose Rounds; a Round is one exact execution context and is
  never replaced by updating the Plan.
- Every Round has an immutable UUID. `T0`, `T1` and later display numbers are
  controlled labels within an exact Tooling/Project context, not global
  identity and not a caller-selected primary key.
- A Round references exactly one Project execution context, Tooling Master,
  Tooling Revision, physical Set, applicable cavity/insert configuration,
  Part/Product Revision and any ordered multi-shot/overmold chain.
- Cloning a prior Round creates a new Round and copies only explicitly
  selected values with source provenance. It never aliases mutable prior rows
  or silently carries a resolved defect as open.
- The accepted conclusion vocabulary is
  `pass / conditional_pass / tooling_change / design_change /
  process_tuning / material_change / cancelled`. Conclusion and lifecycle
  state are different facts. Transition commands require an exact versioned
  policy/capability and may not infer Gate, Tooling or quality authority.

### 3.2 Exact input locks and Trial Actual

- A prepared Round freezes exact IDs, versions and hashes for product/design
  baseline, Part Revision, Tooling Revision, physical Set, cavity/insert map,
  process chain, material/color/additive/batch, parameter-template Revision,
  inspection plan/drawing, controlled documents and any change/deviation.
- A later source revision never moves an existing lock to `latest`. Drift is
  displayed as a difference and requires a new lock version, controlled reopen
  or new Round according to the exact task policy.
- Customer Standard/Provided Specification, TP Trial Actual and Approved
  Process Baseline remain separate immutable fact layers. Copying a Standard
  cannot create an Actual; an unmeasured value remains `not_measured`.
- Every Actual retains metric, value, unit, source, acquisition mode,
  timestamp, actor/confirmation, exact Round/context and effective version.
  Automatic machine import under `FR-TR-010` remains unavailable until a
  source adapter exists; manual or synthetic input cannot claim automation.

### 3.3 Samples, cavities, defects and evidence

- `SampleBatch` has its own immutable identity, label and exact Round/material/
  packaging/destination context. A sample count is not a substitute batch.
- `CavityResult` references a defined cavity UUID and exact Sample Batch. A
  family/multi-cavity result cannot be stored only as free text.
- Trial files reference exact clean private `FileRevision` records. Local
  selection, upload, scan, registration and domain attachment are separate
  states; a raw private URL never grants access.
- A defect may continue across Rounds, but each Round observation and
  verification is immutable and independent. Root cause, containment,
  permanent action, responsibility, target Round and clean evidence retain
  exact lineage.
- NPI defect/action truth does not become an ERPNext NCR or a Gate/Tooling
  transition without the separate authorized command and confirmed result.

### 3.4 Conclusion, quality and approval

- A submitted conclusion is an immutable snapshot over exact inputs, actuals,
  samples, cavities, defects, actions, quality references and evidence hashes.
  Correction uses controlled reopen plus audit or a successor Round; overwrite
  is prohibited.
- Missing critical fields or evidence prevent conclusion submission. The
  browser cannot supply a derived readiness result or suppress server blockers.
- ERPNext Quality Inspection/NCR/result/status remains ERPNext-owned and
  read-only. Until Phase 8 supplies an authenticated projection, Phase 7 shows
  explicit `unavailable`, not a synthetic success.
- NPI-owned controlled-report references, internal review evidence, customer
  evidence and deviation/waiver evidence stay distinct. Evidence presence is
  not approval. Exact approver/customer/signature/effectivity authority must
  be versioned and fail closed when unavailable.

## 4. NPI readiness, handover and observation

- A reusable `NpiReadinessTemplate` has immutable published versions and
  applicability. A Project instance freezes the exact template version; later
  edits never rewrite an active Project checklist.
- Every checklist item retains category, owner, due date, status, evidence,
  blocking level and exact applicable Gate/policy reference. Industry-specific
  content such as PFMEA/MSA/CPK/PPAP is configuration, never a hard-coded
  requirement for every Project.
- Material/specification, process, sample, controlled-document, training,
  supplier, equipment/capacity and pilot-run evidence retains its source and
  exact version. Formal ERP mappings/results remain target-confirmed or
  unavailable.
- Readiness scores are deterministic derived projections from an exact
  template/instance snapshot. Total and category scores are displayed together
  with blocker counts. Any applicable blocking item prevents `ready` regardless
  of percentage.
- A G6/G7 effect is evaluated through the existing versioned Gate policy and a
  separate authorized command. P7 tasks do not hard-code a Gate pass/close or
  bypass review, evidence, exception and reopen rules.
- `HandoverSnapshot` records exact objects, receiving group, acknowledgements,
  unresolved actions, owners and due dates. `ObservationPeriodSnapshot` is a
  separate post-SOP record for yield, complaints, cycle and Tooling stability;
  source metrics remain ERP/customer evidence or explicitly unavailable.

## 5. Released Trial Summary and controlled output

- `ReleasedTrialSummary` is an NPI-owned immutable snapshot distinct from a
  mutable Round workspace, rendered PDF and integration event.
- It contains exact Plan/Round/input/parameter/sample/cavity/defect/action/
  quality-reference/approval-reference/conclusion identities and hashes plus
  a redaction manifest and controlled references. It never embeds raw private
  URLs or silently resolves current source values on reprint.
- P7-07 reuses the P5-06 controlled-print registry/snapshot/output, private
  File, QR/hash, actor/time/language/watermark/copy-state and audited-reprint
  mechanics. No production Trial mapping is enabled until its exact form owner,
  signer, retention and copy policy are approved under `DR-REC-003/004`.
- `DR-REC-009` remains `PENDING_INTEGRATION_CONTRACT`. Phase 7 may create the
  immutable NPI snapshot, but must not publish a guessed event type/payload,
  map an ERP/JCE consumer or claim an external projection. A dotted candidate
  such as `trial_summary.released` is not a contract until approved.

## 6. Existing-capability audit

- NPI Core has no Trial Plan/Round, input-lock, parameter actual, Sample Batch,
  Cavity Result, Trial conclusion, NPI readiness, handover, observation or
  Released Trial Summary DocType/domain/repository/BFF route.
- `frontend/src/pages/trial-page.tsx` is an explicit deterministic prototype.
  Its values are static, its photo remains local, and its primary action only
  stores an in-memory reason while stating that no snapshot or audit was
  persisted. It is UX evidence, not product completion.
- `contracts/data-ownership.yaml` contains only a coarse legacy `TrialRound`
  split plus Phase 6 future-owner placeholders. It does not provide the exact
  Phase 7 aggregates or command authority required for live behavior.
- Phase 6 provides exact Part/Tooling/Revision/Set/cavity/process identities,
  immutable defects/actions, clean File Revisions, Customer Standard,
  `not_measured` Trial Actual, unavailable Approved Baseline, capacity and
  acceptance evidence. Those are predecessors, not Trial/NPI completion.
- Existing Project authorization, Gate policy/review, Domain Work Item,
  idempotency/audit, controlled-print, private File, translation, DenseGrid,
  docked workspace and mobile field primitives are reusable mechanisms. Reuse
  grants no Trial, quality, approval, Gate or ERP authority.

## 7. Scoped holds and non-scope

- `DR-REC-009` blocks the exact Released Trial Summary event and external
  projection, not the NPI-owned immutable snapshot.
- `DR-REC-003/004` block enabled production Trial forms, signatures, browser
  copy claims and copy numbering, not immutable snapshot/output mechanics.
- `DR-REC-002` blocks production exception-color semantics only; textual
  versioned comparison states continue without color-only meaning.
- `DR-REC-010` continues to block formal Tooling Requirement/Revision/Set
  lifecycle commands. A Trial conclusion cannot bypass that hold.
- Production ERPNext access, machine/IoT acquisition, official quality
  mutation, customer/supplier portal authority, production reservations,
  production mappings and automatic Gate close are not Phase 7 assumptions.
  Missing external facts pause only the dependent behavior.

## 8. Task verification and Gate order

Every P7 product task begins with a bounded Requirement/domain/existing-
capability audit. Unless that audit proves a smaller safe slice, delivery uses:

1. pure immutable domain, closed contracts, ownership and guarded additive
   metadata without live routes;
2. Project-first repository/BFF, exact containment, capability/permission,
   actor-bound idempotency, one transaction and append-only audit;
3. dense trilingual SPA with complete operational/accessibility states and
   affected fixed-Linux visual evidence; and
4. cumulative disposable-Site runtime, Level 2 Task Gate and trace transition.

Complete ordinary CI passes before every controlled-Site boundary. Temporary
diagnostics follow the controller's serial response-neutral protocol. Phase 7
ends with a cumulative Level 3 `release-gate` review.

## 9. Changed-files to affected-tests map

| Change boundary | Minimum affected evidence |
|---|---|
| Plan/Round identity and policy | UUID/non-collapse, Project/Tooling containment, display-number collision, version conflict, clone provenance and policy/capability tests |
| input lock/actual/parameter/sample | exact-version/hash drift, no-latest substitution, Standard/Actual/Baseline separation, units/source/timestamps, batch/cavity and File Revision tests |
| defect/action/verification | cross-Round lineage, cavity identity, target/verification independence, blocker separation, IDOR and no-NCR/no-Gate-mutation tests |
| comparison/conclusion/quality/approval | deterministic deltas, required evidence, immutable conclusion/reopen, unavailable ERP projection and policy-bound approval tests |
| readiness/checklist/pilot/training | template freeze, applicability, evidence, score formula, dominant blockers, Gate dependency and no-fake-ERP-result tests |
| handover/observation | immutable acknowledgements, unresolved actions, source/version, external-unavailable metrics and no-auto-G7 tests |
| summary/print/projection | exact snapshot/redaction/hash, retained reprint, mapping fail-closed, no raw URL and no external event/ERP traffic tests |
| mobile field actions | same capability/CSRF/permission, camera/file/scan states, keyboard/touch/zoom, phone/tablet and desktop-complex-table tests |
| every live SPA surface | unit/state/accessibility, direct English/zh/zh-TW, mixed-language and affected governed visual matrix |

## 10. Migration and rollback

- P7 metadata is additive and installs no production lifecycle/approval/Gate/
  print/integration policy, external adapter, endpoint, credential or business
  fixture.
- Before retained task history, a disposable environment may restore the task
  checkpoint and migrate fresh.
- After retained Plan/Round/input/actual/sample/defect/conclusion/readiness/
  handover/summary/audit history, rollback disables only affected independent
  routes/workers/workspaces and deploys a reviewed forward fix. It never
  deletes or rewrites immutable evidence to simulate reversal.
- External observations and released outputs are append-only. Revocation or
  supersession creates explicit successor truth and never mutates the exact
  source snapshot.

## 11. Automatic transition

P7-00 passes its documentation/trace Task Gate. Standing authority activates
only `P7-01 — Trial plan and Round identity/lifecycle foundation`, beginning
with its bounded Requirement/domain/existing-capability audit. No Phase 7
product mutation occurs until that audit freezes the exact plan, policy hold,
checkpoint and affected-test boundary.
