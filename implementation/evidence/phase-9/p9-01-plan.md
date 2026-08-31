# P9-01 Change Impact and Revalidation Plan

Status: `AUDIT COMPLETE — EXACT CHANGE-METADATA DELTA GOVERNANCE PENDING CI`

## Accepted predecessor

P9-00 exact SHA `065803ae484d885001259de8238ef01d0ad311e4`
passes ordinary CI `33345162833`. P9-01 audit activation exact SHA
`e6a99666f2f1101bb21ffd4d499728d015c5e98c` passes ordinary CI
`33345969806`: secret `99350038718`, visual `99350038806`, frontend
`99350038836` and repository `99350038884` all pass.

## Audit result

The repository already provides immutable baseline-impact lineage, Gate review
and revalidation control, Project work items, versioned document/EBOM/Tooling/
Trial evidence, actor/trace/request IDs, audit and P8 integration mechanics.
These are reusable building blocks; none is a formal ERP change master.
ERPNext remains owner of formal ECR/ECO/ECN identity, lifecycle and
transaction-effective truth. LaunchFlow remains owner of NPI impact categories,
affected old/new versions, responsibilities, task packages, revalidation
evidence and Gate consequences.

The accepted P8-07F inventory proves `Engineering Change Request` is one of 27
present relevant production DocTypes; only `Injection Molding Condition` is
absent. The retained aggregate hashes do not expose the exact change fields,
permissions, Workflow/Script or naming metadata required to decide the
`INT-008` map. No incompatibility is inferred from that missing detail.

## Frozen fact-delta boundary

Before any P9-01 product plan is authorized, one exact-SHA ordinary CI must
approve the existing collector and its focused test as task paths. After that
Gate, one bounded read may inspect only the exact names `Engineering Change
Request`, `Engineering Change Order` and `Engineering Change Notice`, plus
their direct DocField, DocPerm, Custom Field, Property Setter, Workflow,
Client/Server Script and naming metadata. Raw Script, condition and configured
values are hashed; no business row, endpoint, credential, Site value, secret,
target method or unrelated metadata may be retained.

The read reuses the fixed `JCE-Core` transport, `frappe-bench` root and private
Site parameter, with BatchMode, strict host-key verification, no TTY or
forwarding, bounded output, deterministic ordering/pagination, local redaction,
checksum provenance and fail-closed shape checks. It performs no write or
business action. Any drift, unexpected shape, permission failure or sensitive
output stops the affected read without expanding scope.

## Product authorization

`product_code_authorized=false`. The final vertical-slice/checkpoint plan will
be appended only after the sanitized production delta is accepted. It must use
`DIRECT_MATCH`/`NO_CHANGE` wherever possible, configuration/mapping next, and
only a proven smallest local reversible adjustment otherwise. No redesign,
generalized change engine, ERP core modification, generic DocType writer,
browser-direct ERP access, cross-database write, dual-master field or fake
success is permitted.
