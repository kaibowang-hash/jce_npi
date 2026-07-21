# Next Action

Status: `HARD_BLOCKED_CODESPACE_REBUILD`

In the GitHub Codespaces command palette, run **Codespaces: Rebuild Container**.

After the rebuilt workspace opens, the delivery agent must resume from Phase
1.1 by running `make verify-dev-environment`, `make verify` and
`git diff --check`. On `PASS`, update the Phase 1.1 gate and controller evidence,
commit and push the checkpoint, then continue automatically to Phase 3. No
production ERPNext connection is authorized.
