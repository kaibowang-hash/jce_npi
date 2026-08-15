from __future__ import annotations

import ast
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = (
    ROOT
    / "apps/npi_integration/npi_integration/npi_integration/doctype"
)
CORE_DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"
PROJECTION_ROOT = ROOT / "apps/npi_integration/npi_integration/projections"


class Phase8ProjectionMetadataTest(unittest.TestCase):
    FOLDERS = (
        "npi_erp_projection_observation",
        "npi_erp_projection_head",
    )
    EXPECTED_FIELDS = {
        "npi_erp_projection_observation": {
            "global_id", "schema_version", "event_id", "event_key_hash",
            "event_type", "event_version", "source_system", "target_system",
            "adapter_mode", "adapter_contract_version", "source_environment",
            "source_object_type", "source_object_id", "source_version",
            "source_modified_at", "payload", "payload_hash", "received_at",
            "trace_id", "correlation_id", "sensitivity", "tenant_id",
            "project_global_id", "scope_kind", "scope_global_id",
            "projection_kind", "availability", "freshness", "disposition",
            "unavailable_reason_code", "observation_snapshot",
            "observation_hash", "created_at",
        },
        "npi_erp_projection_head": {
            "global_id", "stream_key_hash", "tenant_id", "project_global_id",
            "scope_kind", "scope_global_id", "projection_kind",
            "source_object_type", "source_object_id", "current_observation",
            "last_refresh_observation", "current_source_version",
            "current_source_modified_at", "current_payload_hash",
            "availability", "freshness", "freshness_policy_ref",
            "optimistic_version", "head_snapshot", "head_hash", "updated_at",
        },
    }

    def load(self, folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    def test_two_additive_support_doctypes_are_exact_read_only_and_have_no_business_crud(self) -> None:
        for folder in self.FOLDERS:
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                fields = {field["fieldname"]: field for field in metadata["fields"]}
                self.assertEqual(set(fields), self.EXPECTED_FIELDS[folder])
                self.assertEqual(metadata["autoname"], "field:global_id")
                self.assertEqual(metadata["allow_rename"], 0)
                self.assertEqual(metadata["read_only"], 1)
                self.assertNotIn("fixtures", metadata)
                self.assertNotIn("records", metadata)
                self.assertTrue(all(field.get("read_only") == 1 for field in fields.values()))
                for permission in metadata["permissions"]:
                    self.assertEqual(permission.get("write"), 0)
                    self.assertEqual(permission.get("create"), 0)
                    self.assertEqual(permission.get("delete"), 0)
                    self.assertEqual(permission.get("export"), 0)
                    self.assertEqual(permission.get("print"), 0)
                    self.assertEqual(permission.get("email"), 0)

    def test_controllers_require_narrow_internal_flags_and_deny_history_delete(self) -> None:
        observation = (
            DOCTYPE_ROOT
            / "npi_erp_projection_observation/npi_erp_projection_observation.py"
        ).read_text(encoding="utf-8")
        head = (
            DOCTYPE_ROOT / "npi_erp_projection_head/npi_erp_projection_head.py"
        ).read_text(encoding="utf-8")
        guards = (PROJECTION_ROOT / "frappe_validation.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(observation.count("require_projection_observation_write()"), 2)
        self.assertIn("deny_projection_observation_update()", observation)
        self.assertIn("deny_projection_history_delete()", observation)
        self.assertGreaterEqual(head.count("require_projection_head_write()"), 2)
        self.assertIn("deny_projection_history_delete()", head)
        for marker in (
            'PROJECTION_OBSERVATION_WRITE_FLAG = "npi_erp_projection_observation_write"',
            'PROJECTION_HEAD_WRITE_FLAG = "npi_erp_projection_head_write"',
            "projection_observation_write()",
            "projection_head_write()",
        ):
            self.assertIn(marker, guards)
        for source in (observation, head, guards):
            ast.parse(source)

    def test_scalar_identity_and_hash_fields_replay_canonical_snapshots(self) -> None:
        observation = (
            DOCTYPE_ROOT
            / "npi_erp_projection_observation/npi_erp_projection_observation.py"
        ).read_text(encoding="utf-8")
        head = (
            DOCTYPE_ROOT / "npi_erp_projection_head/npi_erp_projection_head.py"
        ).read_text(encoding="utf-8")
        for marker in (
            "ProjectionReaderResult(",
            "result.event_payload(",
            "expected_event_key_hash",
            "expected_snapshot",
            "canonical_payload_hash(expected_snapshot)",
        ):
            self.assertIn(marker, observation)
        for marker in (
            "ProjectionContext(",
            "stream_identity",
            "expected_stream_hash",
            "expected_snapshot",
            "canonical_payload_hash(expected_snapshot)",
        ):
            self.assertIn(marker, head)

    def test_metadata_links_target_real_repository_doctypes(self) -> None:
        doctype_names = {
            str(json.loads(path.read_text(encoding="utf-8"))["name"])
            for root in (DOCTYPE_ROOT, CORE_DOCTYPE_ROOT)
            for path in root.glob("*/*.json")
        }
        for folder in self.FOLDERS:
            for field in self.load(folder)["fields"]:
                if field.get("fieldtype") == "Link":
                    self.assertIn(field.get("options"), doctype_names)

    def test_visible_sources_have_symmetric_direct_chinese_translations(self) -> None:
        sources: set[str] = set()
        source_paths: list[Path] = [
            PROJECTION_ROOT / "frappe_validation.py",
            ROOT / "apps/npi_integration/npi_integration/projection_api.py",
        ]
        for folder in self.FOLDERS:
            metadata = self.load(folder)
            sources.add(str(metadata["name"]))
            sources.update(str(field["label"]) for field in metadata["fields"])
            for field in metadata["fields"]:
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
                f"missing {language} P8 projection translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))

    def test_checkpoint_one_foundation_remains_scheduler_network_and_fixture_free(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                PROJECTION_ROOT / "domain.py",
                PROJECTION_ROOT / "config.py",
                PROJECTION_ROOT / "frappe_validation.py",
            )
        ).casefold()
        for forbidden in (
            "requests" + ".",
            "httpx" + ".",
            "urllib." + "request",
            "socket" + ".",
            "frappe.db" + ".sql",
            "frappe.get" + "_doc",
            "enqueue(",
            "scheduler_events",
            "write_doc",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
