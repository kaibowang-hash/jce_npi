# ADR-006: Reproducible development environment

Status: Accepted. A devcontainer plus Docker Compose supplies pinned Frappe, MariaDB, Redis and workers; host Node tooling runs the React workflow where useful. Scripts provide start, stop, reset and verification. Reset targets only named development volumes and must require explicit confirmation.

Phase 1.1 implementation note: the original generic workspace did not include Node, Docker CLI/daemon or Bench and therefore did not satisfy this decision. The remediation uses a digest-pinned Python 3.11 devcontainer, exact official Node and Docker-in-Docker feature releases, a pinned Bench CLI, digest-pinned MariaDB/Redis Compose services and an exact Frappe v15 commit. Static configuration checks run before rebuild; the ADR is not considered implemented until the rebuilt Codespace passes `make verify-dev-environment` with actual command output.
