from frappe.model.document import Document


class NPIOutboxMessage(Document):
    """Support projection for a durable outbound integration message."""
