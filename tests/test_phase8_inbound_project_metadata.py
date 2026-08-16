from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_integration/npi_integration/npi_integration/doctype"
CORE_DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
INBOUND_ROOT = ROOT / "apps/npi_integration/npi_integration/inbound_project"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"


class Phase8InboundProjectMetadataTest(unittest.TestCase):
    FOLDERS = ("npi_inbox_message", "npi_project_source_binding")

    def load(self, folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    def test_inbox_is_additive_read_only_and_legacy_fields_remain_compatible(self) -> None:
        metadata = self.load("npi_inbox_message")
        fields = {field["fieldname"]: field for field in metadata["fields"]}
        for fieldname in (
            "event_id",
            "source_system",
            "payload_hash",
            "payload",
            "state",
        ):
            self.assertEqual(fields[fieldname].get("reqd"), 1)
        for fieldname in (
            "receipt_id",
            "schema_version",
            "authenticated",
            "tenant_id",
            "profile_id",
            "policy_snapshot",
            "event_snapshot",
            "canonical_event_hash",
            "raw_body",
            "raw_body_hash",
            "source_key_hash",
            "signing_key_id",
            "claim_token",
            "project_global_id",
            "receipt_snapshot",
            "receipt_hash",
        ):
            self.assertIn(fieldname, fields)
            self.assertNotEqual(fields[fieldname].get("reqd"), 1)
        self.assertEqual(fields["event_id"].get("unique"), 1)
        self.assertEqual(fields["receipt_id"].get("unique"), 1)
        self.assertTrue(all(field.get("read_only") == 1 for field in fields.values()))
        self._assert_support_only_permissions(metadata)
        self.assertNotIn("fixtures", metadata)
        self.assertNotIn("records", metadata)

    def test_source_binding_has_one_hash_identity_and_no_business_crud(self) -> None:
        metadata = self.load("npi_project_source_binding")
        fields = {field["fieldname"]: field for field in metadata["fields"]}
        self.assertEqual(metadata["autoname"], "field:source_key_hash")
        self.assertEqual(fields["source_key_hash"].get("unique"), 1)
        self.assertEqual(fields["highest_inbox_message"].get("options"), "NPI Inbox Message")
        self.assertEqual(fields["bound_project_global_id"].get("options"), "NPI Engineering Project")
        self.assertEqual(
            fields["stream_state"].get("options"), "unbound\nbound\nconflicted"
        )
        self.assertTrue(all(field.get("read_only") == 1 for field in fields.values()))
        self._assert_support_only_permissions(metadata)
        self.assertNotIn("fixtures", metadata)
        self.assertNotIn("records", metadata)

    def test_controllers_require_narrow_flags_freeze_legacy_and_deny_delete(self) -> None:
        inbox = (
            DOCTYPE_ROOT / "npi_inbox_message/npi_inbox_message.py"
        ).read_text(encoding="utf-8")
        binding = (
            DOCTYPE_ROOT / "npi_project_source_binding/npi_project_source_binding.py"
        ).read_text(encoding="utf-8")
        guards = (INBOUND_ROOT / "frappe_validation.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(inbox.count("require_inbox_write()"), 2)
        self.assertIn("deny_legacy_inbox_update()", inbox)
        self.assertIn("_IMMUTABLE_V1_FIELDS", inbox)
        self.assertIn("parse_project_source_event", inbox)
        self.assertIn("SourceStreamIdentity(", inbox)
        self.assertIn("deny_inbound_project_delete()", inbox)
        self.assertGreaterEqual(binding.count("require_source_binding_write()"), 2)
        self.assertIn("_IMMUTABLE_SOURCE_FIELDS", binding)
        self.assertIn("_BOUND_FIELDS", binding)
        self.assertIn("SourceStreamIdentity(", binding)
        self.assertIn("deny_inbound_project_delete()", binding)
        for marker in (
            'INBOX_WRITE_FLAG = "npi_inbound_project_inbox_write"',
            'SOURCE_BINDING_WRITE_FLAG = "npi_project_source_binding_write"',
            "inbound_project_repository_write()",
        ):
            self.assertIn(marker, guards)
        for source in (inbox, binding, guards):
            ast.parse(source)

    def test_links_resolve_and_all_visible_sources_have_symmetric_translations(self) -> None:
        doctype_names = {
            str(json.loads(path.read_text(encoding="utf-8"))["name"])
            for root in (DOCTYPE_ROOT, CORE_DOCTYPE_ROOT)
            for path in root.glob("*/*.json")
        }
        sources: set[str] = set()
        source_paths = [
            INBOUND_ROOT / "frappe_validation.py",
            ROOT
            / "apps/npi_integration/npi_integration/inbound_project_api.py",
        ]
        for folder in self.FOLDERS:
            metadata = self.load(folder)
            sources.add(str(metadata["name"]))
            for field in metadata["fields"]:
                sources.add(str(field["label"]))
                if field.get("fieldtype") == "Link":
                    self.assertIn(field.get("options"), doctype_names)
                if field.get("fieldtype") == "Select":
                    sources.update(
                        value
                        for value in str(field.get("options", "")).splitlines()
                        if value
                    )
            source_paths.append(DOCTYPE_ROOT / folder / f"{folder}.py")
        for source_path in source_paths:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
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
            ) as handle:
                catalogs[language] = {
                    row[0]: row[1]
                    for row in csv.reader(handle)
                    if len(row) >= 2 and row[0]
                }
            self.assertFalse(
                sorted(source for source in sources if not catalogs[language].get(source)),
                f"missing {language} P8-02 translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))

    def test_checkpoint_two_activates_only_fixed_ingress_without_worker_or_business_effects(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in INBOUND_ROOT.glob("*.py")
        ).casefold()
        for forbidden in (
            "requests" + ".",
            "httpx" + ".",
            "urllib." + "request",
            "socket" + ".",
            "frappe.db" + ".sql",
            "scheduler_events",
            "projectinstantiationservice",
        ):
            self.assertNotIn(forbidden, combined)
        bff = (ROOT / "apps/npi_core/npi_core/bff.py").read_text(encoding="utf-8")
        api = (
            ROOT / "apps/npi_integration/npi_integration/inbound_project_api.py"
        ).read_text(encoding="utf-8")
        repository = (INBOUND_ROOT / "frappe_repository.py").read_text(
            encoding="utf-8"
        )
        self.assertEqual(bff.count("project-source-events"), 1)
        self.assertIn("accept_project_source_event", api)
        self.assertIn("frappe.db.commit()", api)
        self.assertIn("_enqueue_after_commit", api)
        self.assertIn("FrappeInboundProjectRepository", repository)
        self.assertFalse((INBOUND_ROOT / "worker.py").exists())
        for forbidden in (
            "NPI Engineering Project",
            "NPI Gate Shell",
            "NPI Domain Work Item",
            "ProjectInstantiationService",
        ):
            self.assertNotIn(forbidden, repository)
        self.assertNotIn(
            "inbound_project",
            (ROOT / "apps/npi_integration/npi_integration/hooks.py").read_text(encoding="utf-8"),
        )

    def _assert_support_only_permissions(self, metadata: dict[str, object]) -> None:
        self.assertEqual(metadata.get("allow_rename"), 0)
        self.assertEqual(metadata.get("read_only"), 1)
        for permission in metadata["permissions"]:
            for action in ("write", "create", "delete", "export", "print", "email"):
                self.assertEqual(permission.get(action, 0), 0)


if __name__ == "__main__":
    unittest.main()
