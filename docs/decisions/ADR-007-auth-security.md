# ADR-007: Authentication and authorization

Status: Accepted. Frappe sessions are the initial identity boundary; deployment can federate OIDC through supported configuration. Domain APIs enforce role, project and tenant scope server-side. Service identities are separate, least-privileged and auditable. Secrets enter via environment/secret stores only.
