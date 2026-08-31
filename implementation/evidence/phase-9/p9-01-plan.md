# P9-01 Change Impact and Revalidation Plan

Status: `AUDIT COMPLETE — CHANGE-METADATA COLLECTOR IMPLEMENTED; ACTIVATION CI PENDING`

## Accepted predecessor

P9-00 exact SHA `065803ae484d885001259de8238ef01d0ad311e4`
passes ordinary CI `33345162833`. P9-01 audit activation exact SHA
`e6a99666f2f1101bb21ffd4d499728d015c5e98c` passes ordinary CI
`33345969806`: secret `99350038718`, visual `99350038806`, frontend
`99350038836` and repository `99350038884` all pass.

The independent fact-delta governance exact SHA
`0e56c83327b12fc5501a4d5d71c5abf5e30981f6` passes ordinary CI
`33347047323`: repository `99353044581`, secret `99353044662`, frontend
`99353044670` and visual `99353044785` all pass. It authorizes only the
collector and focused test paths; it made no production connection.

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

## Collector activation checkpoint

The no-state `change-metadata` command is implemented for exactly three fixed
DocType names and twelve fixed declarative metadata families. Every remote
operation is an application-layer `frappe.client.get_list` or a fixed Workflow
parent read; commands are deterministically ordered and paged. Scope escape,
duplicate names, unknown shape, page overflow, missing private Site parameter,
dirty governed paths or a non-exact activation fail closed before facts are
accepted. Script, condition, configured value and naming-prefix content is
represented only by byte count and SHA-256. Workflow child rows are projected
to pre-existing fixed safe shapes.

Focused tests prove exact filters, no SQL/console/wildcard, sensitive-value
hashing, no Site/identity leakage, workflow projection, scope-escape rejection,
activation/path enforcement and no SSH in self-check. The command remains
inactive until this collector checkpoint itself passes exact-SHA ordinary CI;
there has still been no production contact in this checkpoint.

Level 1/2 evidence is green: collector-focused `27/27`, governance/collector/
reconciliation `67/67`, full repository Python `2716/2716`, current-task and
V1.2 reconciliation scripts, compileall, shell syntax and `git diff --check`.
The full repository verifier passes with the local `python3` interpreter
exposed through a temporary non-repository `python` PATH shim; no repository
file, test or threshold was changed for that host-only interpreter-name fact.
