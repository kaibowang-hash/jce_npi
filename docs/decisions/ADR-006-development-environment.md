# ADR-006: Reproducible development environment

Status: Accepted. A devcontainer plus Docker Compose supplies pinned Frappe, MariaDB, Redis and workers; host Node tooling runs the React workflow where useful. Scripts provide start, stop, reset and verification. Reset targets only named development volumes and must require explicit confirmation.
