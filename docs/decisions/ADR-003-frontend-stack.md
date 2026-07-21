# ADR-003: Frontend stack

Status: Accepted. React 18, TypeScript and Vite form the SPA; server state and routing are isolated behind typed modules. `npi-ui` wraps Siemens iX dependencies so business screens do not bind directly to vendor APIs. Rollback: swap adapters without changing domain ViewModels.
