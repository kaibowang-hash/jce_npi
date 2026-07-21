# Blockers

## Active hard blocker: fresh target-container validation required

The current environment is a newly created Alpine recovery container. The
preserved Codespaces creation log proves the repository's original devcontainer
build failed before target-container creation: the pinned Python image's
inherited Yarn APT source had an unavailable signing key, so `apt-get update`
exited 100 and Codespaces reported error 1302.

Repair round 3 removes matching repository lines from `/etc/apt/sources.list`
and deletes all `/etc/apt/sources.list.d/*yarn*` source fragments before package
refresh. It retains the verified base digest, locks the official Feature OCI
digests, rejects APT trust/signature bypasses and ignored APT failures,
cross-validates fixed tool versions, makes post-create setup idempotent and
extends Docker readiness diagnostics. All current static, registry and
repository tests pass, but Phase 1.1 cannot pass until a new Codespace created
from the repaired branch dynamically verifies the target runtime. Phase 3
remains paused.

Production ERPNext credentials and production activation remain explicitly out
of scope and are not a development blocker.
