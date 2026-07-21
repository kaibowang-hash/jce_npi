# Blockers

## Active hard blocker: Codespaces rebuild required

Phase 1.1 repair round 1 proved that the active container is stale: `make verify-dev-environment` cannot find Node, and direct probes also show npm, Docker CLI and Bench missing while Python is 3.12.13. The committed devcontainer defines the approved pinned toolchain, so the required action is **Codespaces: Rebuild Container**. Phase 3 remains paused until the rebuilt runtime passes both `make verify-dev-environment` and `make verify`.

Production ERPNext credentials and production activation remain explicitly out of scope and are not a development blocker.
