from __future__ import annotations

from uuid import uuid4

from frappe import _
from frappe.model.document import Document

from npi_core.foundation.errors import RequestValidationFailed
from npi_core.project.domain import validate_template_code
from npi_core.project.frappe_validation import (
    assert_immutable_fields,
    ensure_uuid,
    throw_domain_validation,
)


class NPIProjectTemplate(Document):
    """Administrative root for generic, explicitly versioned project templates."""

    def autoname(self) -> None:
        self._set_identity()
        self.name = self.global_id

    def before_validate(self) -> None:
        self._set_identity()

    def _set_identity(self) -> None:
        if not self.global_id:
            self.global_id = str(uuid4())

    def validate(self) -> None:
        self.global_id = ensure_uuid(self.global_id, _("Global ID"))
        try:
            self.template_code = validate_template_code(self.template_code)
        except RequestValidationFailed as error:
            throw_domain_validation(error)
        previous = self.get_doc_before_save()
        if previous is not None:
            assert_immutable_fields(
                self,
                previous,
                ("global_id", "template_code"),
            )
