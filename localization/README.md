# Localization seed

These CSV files demonstrate the required Frappe-style `source_string,translated_string,context` structure. Their filenames are deliberately marked `provisional`: M0 must inspect the actual Frappe/ERPNext deployment and replace them with the exact supported language codes and approved extraction/compilation workflow before implementation.

Rules:
- English source strings are literal and canonical.
- Simplified and Traditional Chinese must be updated together.
- Do not import these seed files blindly into production.
- The React catalog must be generated from, or served by, the same canonical translation source as the Frappe app.
