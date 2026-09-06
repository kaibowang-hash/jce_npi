# ADR-008: Files, audit and asynchronous work

Status: Accepted. Frappe-managed private files carry content hash and immutable release metadata; object storage remains deployable. Domain commands record actor/trace/version and audit events. Long work uses Redis queues with visible durable operation status; logs never replace user-visible failure state.
