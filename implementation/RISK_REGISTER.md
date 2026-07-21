# Risk Register

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R-001 | Active Codespace is still the pre-remediation runtime and lacks Node, npm, Docker CLI and Bench; Python is 3.12.13 rather than 3.11. | Phase 1.1 and Phase 3 blocked until rebuild | Rebuild from the committed devcontainer, then rerun `make verify-dev-environment` and `make verify` | Active — rebuild required |
| R-002 | Large V1.2 scope can hide trace gaps. | P0/P1 omission | Machine-readable requirement trace and per-phase gates | Open |
| R-003 | Siemens component defaults may violate square/neutral baseline. | UI gate failure | Local adapter, tokens and visual assertions | Open |
| R-004 | Translation fallback can mask missing Chinese. | Language gate failure | Strict missing markers and coverage/mixed-language scanners | Open |
| R-005 | ERP retry/replay can duplicate execution. | External data corruption | Idempotency, inbox/outbox, expected version, reconciliation and fault tests | Open |
| R-006 | No production ERP access for final activation. | External go-live dependency | Mock plus sandbox-ready adapter and activation runbook | Accepted external |
| R-007 | A Codespaces clone may retain generated Git LFS hooks even though the repository has no LFS attributes or pointer objects. | Push fails when the unused `git-lfs` binary is absent. | Verify attributes and reachable history before removing only clone-local generated hooks; require approved attributes and reproducible installation before any future LFS adoption. | Mitigated — current clone residue removed |
