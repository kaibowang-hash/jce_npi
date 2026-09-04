# ADR-001: Independent NPI platform boundary

Status: Accepted. NPI One uses an independent Frappe site/database and React SPA. ERPNext remains the formal execution system. No core patches, cross-database access or browser-to-ERP calls. Rollback: remove the standalone deployment; no ERP data is touched.
