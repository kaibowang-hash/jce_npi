# Development Environment

Prerequisites: Docker Engine with Compose v2, Git and Make. Open the repository in a Dev Container or run `make start`. Stop services with `make stop`. Destructive local reset requires `CONFIRM_RESET=YES make reset` and affects only the named Compose development volumes. Run `make verify` before commits. No production endpoint or credential belongs in this environment.
