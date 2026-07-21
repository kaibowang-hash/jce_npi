# Risk Register

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R-001 | Greenfield environment lacks Frappe runtime and container services. | Bootstrap delay | Reproducible devcontainer/compose, pinned dependencies, CI evidence | Open |
| R-002 | Large V1.2 scope can hide trace gaps. | P0/P1 omission | Machine-readable requirement trace and per-phase gates | Open |
| R-003 | Siemens component defaults may violate square/neutral baseline. | UI gate failure | Local adapter, tokens and visual assertions | Open |
| R-004 | Translation fallback can mask missing Chinese. | Language gate failure | Strict missing markers and coverage/mixed-language scanners | Open |
| R-005 | ERP retry/replay can duplicate execution. | External data corruption | Idempotency, inbox/outbox, expected version, reconciliation and fault tests | Open |
| R-006 | No production ERP access for final activation. | External go-live dependency | Mock plus sandbox-ready adapter and activation runbook | Accepted external |

