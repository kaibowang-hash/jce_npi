from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE = (
    ROOT
    / "apps/npi_integration/npi_integration/npi_integration/doctype"
    / "npi_authorization_projection"
)
PROJECTION = ROOT / "apps/npi_integration/npi_integration/authorization_projection"
API = ROOT / "apps/npi_integration/npi_integration/authorization_projection_api.py"
HOOKS = ROOT / "apps/npi_integration/npi_integration/hooks.py"
BFF = ROOT / "apps/npi_core/npi_core/bff.py"
CORE_SECURITY = ROOT / "apps/npi_core/npi_core/request_security.py"
OPENAPI = ROOT / "contracts/npi-api.openapi.yaml"
OWNERSHIP = ROOT / "contracts/data-ownership.yaml"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"


class AuthorizationProjectionMetadataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.metadata = json.loads(
            (DOCTYPE / "npi_authorization_projection.json").read_text(
                encoding="utf-8"
            )
        )

    def test_projection_doctype_is_additive_read_only_and_has_no_business_crud(self) -> None:
        fields = {field["fieldname"]: field for field in self.metadata["fields"]}
        self.assertEqual(
            set(fields),
            {
                "global_id",
                "projection_key_hash",
                "tenant_id",
                "source_subject_hash",
                "target_user_id",
                "source_version",
                "state",
                "roles",
                "project_access",
                "organization_scopes",
                "source_event_id",
                "source_event_hash",
                "projection_hash",
                "issued_at",
                "expires_at",
                "applied_at",
                "source_trace_id",
                "request_id",
            },
        )
        self.assertEqual(self.metadata["autoname"], "field:global_id")
        self.assertEqual(self.metadata["allow_rename"], 0)
        self.assertEqual(self.metadata["read_only"], 1)
        self.assertEqual(fields["target_user_id"]["fieldtype"], "Data")
        self.assertNotIn("options", fields["target_user_id"])
        self.assertNotIn("fixtures", self.metadata)
        self.assertNotIn("records", self.metadata)
        self.assertTrue(all(field.get("read_only") == 1 for field in fields.values()))
        for permission in self.metadata["permissions"]:
            for action in ("write", "create", "delete", "export", "print", "email"):
                self.assertFalse(permission.get(action, 0))

    def test_controlled_write_guard_and_resolver_fail_closed(self) -> None:
        controller = (DOCTYPE / "npi_authorization_projection.py").read_text(
            encoding="utf-8"
        )
        guard = (PROJECTION / "frappe_validation.py").read_text(encoding="utf-8")
        repository = (PROJECTION / "frappe_repository.py").read_text(encoding="utf-8")
        security = CORE_SECURITY.read_text(encoding="utf-8")
        for marker in (
            "require_authorization_projection_write()",
            "deny_authorization_projection_delete()",
        ):
            self.assertIn(marker, controller)
        for marker in (
            'PROJECTION_WRITE_FLAG = "npi_authorization_projection_write"',
            'LOCAL_USER_WRITE_FLAG = "npi_authorization_local_user_write"',
            "authorization_projection_write(",
            "insert_provisioned_user(",
            "save_provisioned_user(",
            'actor.casefold() in {"guest", "administrator"}',
            '"NPI API User" not in set(frappe.get_roles(actor)',
        ):
            self.assertIn(marker, guard)
        self.assertIn("for_update=True", repository)
        self.assertNotIn("frappe.db" + ".sql", repository)
        self.assertIn('"send_welcome_email": 0', repository)
        self.assertIn('user.flags.no_welcome_mail = True', repository)
        self.assertNotIn('"new_password"', repository)
        self.assertIn('npi_p9_04_authorization_projection_enforced', security)
        self.assertIn("raise AuthenticationRequired()", security)
        for source in (controller, guard, repository, security):
            ast.parse(source)

    def test_bff_openapi_hook_and_ownership_are_operation_specific(self) -> None:
        bff = BFF.read_text(encoding="utf-8")
        api = API.read_text(encoding="utf-8")
        hooks = HOOKS.read_text(encoding="utf-8")
        openapi = OPENAPI.read_text(encoding="utf-8")
        ownership = OWNERSHIP.read_text(encoding="utf-8")
        for source in (bff, openapi):
            self.assertIn("/integration/erpnext/user-authorization", source)
        self.assertIn(
            'method == "PUT"\n        and path == "/api/npi/v1/integration/erpnext/user-authorization"',
            bff,
        )
        self.assertIn("replace_user_authorization", api)
        self.assertIn("npi_authorization_projection_resolver", hooks)
        self.assertIn("UserAuthorizationProjection:", ownership)
        self.assertIn("owner_system: ERPNEXT", ownership)
        self.assertIn("passwords_mfa_factors_provider_secrets_session_cookies", ownership)
        self.assertIn(
            "targetUserId: { type: string, format: email, minLength: 3, maxLength: 254 }",
            openapi,
        )
        self.assertIn("localUserDisposition", openapi)
        for forbidden in (
            "generic_doc" + "type_writer",
            "frappe.client." + "save",
            "frappe.client." + "insert",
            "frappe.client." + "set_value",
        ):
            self.assertNotIn(forbidden, "\n".join((api, bff, ownership)).casefold())

    def test_visible_sources_have_symmetric_direct_chinese_translations(self) -> None:
        sources = {str(self.metadata["name"])}
        sources.update(str(field["label"]) for field in self.metadata["fields"])
        sources.update(
            value
            for field in self.metadata["fields"]
            if field.get("fieldtype") == "Select"
            for value in str(field.get("options", "")).splitlines()
            if value
        )
        for path in (
            DOCTYPE / "npi_authorization_projection.py",
            PROJECTION / "frappe_validation.py",
            PROJECTION / "frappe_repository.py",
            API,
        ):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            sources.update(
                str(node.args[0].value)
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            )
        catalogs: dict[str, dict[str, str]] = {}
        for language in ("zh", "zh-TW"):
            with (TRANSLATIONS / f"{language}.csv").open(
                encoding="utf-8", newline=""
            ) as stream:
                catalogs[language] = {
                    row[0]: row[1]
                    for row in csv.reader(stream)
                    if len(row) >= 2 and row[0]
                }
            self.assertFalse(
                sorted(source for source in sources if not catalogs[language].get(source)),
                f"missing {language} P9-04 authorization translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))


if __name__ == "__main__":
    unittest.main()
