from __future__ import annotations

from frappe.model.document import Document

from npi_integration.master_data.frappe_validation import (
    deny_master_data_delete,
    require_master_data_write,
)


class NPIERPMasterCatalogHead(Document):
    def before_insert(self) -> None:
        require_master_data_write()

    def validate(self) -> None:
        require_master_data_write()

    def on_trash(self) -> None:
        deny_master_data_delete()
