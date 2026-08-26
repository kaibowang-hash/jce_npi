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

## Rollback

Before any future link row exists, revert this pure module, components,
translations/tests and the three additive metadata definitions; remove
metadata only on a disposable Site after proving zero rows. Once later
history exists, disable future routes/UI and retain immutable revisions,
heads, receipts and audits for forward repair. Never rewrite ERP observation
truth or convert unavailable/raw evidence into pass.
