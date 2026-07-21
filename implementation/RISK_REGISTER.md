# Risk Register

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R-001 | A fresh Codespace entered Alpine recovery because the target Dockerfile inherited a Yarn APT source with an unavailable signing key. | Phase 1.1 and Phase 3 remain blocked until the repaired target image is created and dynamically verified. | Sanitize both `/etc/apt/sources.list` and `/etc/apt/sources.list.d/*yarn*` before APT refresh, lock/verify all remote artifacts, then create a fresh Codespace from the repaired branch and run the dynamic gate. | Active — root cause repaired; fresh-container proof pending |
| R-002 | Large V1.2 scope can hide trace gaps. | P0/P1 omission | Machine-readable requirement trace and per-phase gates | Open |
| R-003 | Siemens component defaults may violate square/neutral baseline. | UI gate failure | Local adapter, tokens and visual assertions | Open |
| R-004 | Translation fallback can mask missing Chinese. | Language gate failure | Strict missing markers and coverage/mixed-language scanners | Open |
| R-005 | ERP retry/replay can duplicate execution. | External data corruption | Idempotency, inbox/outbox, expected version, reconciliation and fault tests | Open |
| R-006 | No production ERP access for final activation. | External go-live dependency | Mock plus sandbox-ready adapter and activation runbook | Accepted external |
| R-007 | A Codespaces clone may retain generated Git LFS hooks even though the repository has no LFS attributes or pointer objects. | Push fails when the unused `git-lfs` binary is absent. | Verify attributes and reachable history before removing only clone-local generated hooks; require approved attributes and reproducible installation before any future LFS adoption. | Mitigated — current clone residue removed |
| R-008 | A valid immutable base image can still reference time-sensitive external package repositories whose signing configuration later expires. | Reproducible container creation can fail before Feature or post-create execution. | Remove the unused Yarn APT source from both supported locations, forbid signature/trust bypasses and validate base/Feature/tool artifacts against official registries before delivery. | Mitigated in repair round 3; dynamic proof pending |
