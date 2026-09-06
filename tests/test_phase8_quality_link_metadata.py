from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
import sys
import types
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_integration/npi_integration/npi_integration/doctype"
CORE_DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
MODULE = ROOT / "apps/npi_integration/npi_integration/quality_link"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"


class Phase8QualityLinkMetadataTest(unittest.TestCase):
    FOLDERS = ("npi_formal_quality_link_head", "npi_formal_quality_link_revision", "npi_formal_quality_link_command_idempotency")

    def load(self, folder: str) -> dict[str, object]:
        return json.loads((DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8"))

    def test_three_additive_doctypes_are_zero_row_read_only_and_no_business_crud(self) -> None:
        for folder in self.FOLDERS:
            metadata = self.load(folder)
            self.assertEqual(metadata, self.load(folder), "metadata discovery must be idempotent across repeated migrate reads")
            self.assertEqual(metadata["autoname"], "field:global_id")
            self.assertEqual((metadata["allow_rename"], metadata["track_changes"], metadata["read_only"]), (0, 0, 1))
            self.assertNotIn("fixtures", metadata)
            self.assertNotIn("records", metadata)
            self.assertTrue(all(field.get("read_only") == 1 for field in metadata["fields"]))
            for permission in metadata["permissions"]:
                for action in ("write", "create", "delete", "export", "print", "email"):
                    self.assertFalse(permission.get(action, 0))

    def test_links_resolve_and_controllers_are_guarded(self) -> None:
        names = {json.loads(path.read_text(encoding="utf-8"))["name"] for root in (DOCTYPE_ROOT, CORE_DOCTYPE_ROOT) for path in root.glob("*/*.json")}
        for folder in self.FOLDERS:
            metadata = self.load(folder)
            for field in metadata["fields"]:
                if field.get("fieldtype") == "Link":
                    self.assertIn(field["options"], names)
            source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(encoding="utf-8")
            self.assertIn("QualityLinkSupportDocument", source)
            ast.parse(source)
        base = (MODULE / "doctype_base.py").read_text(encoding="utf-8")
        guards = (MODULE / "frappe_validation.py").read_text(encoding="utf-8")
        for marker in ("require_quality_link_write(self.doctype, action)", "deny_quality_link_history_delete()", "assert_immutable_fields"):
            self.assertIn(marker, base)
        for marker in ("QualityLinkWriteCapability", "_CURRENT.reset(token)", "QUALITY_LINK_REVISION_WRITE_FLAG", "QUALITY_LINK_HEAD_WRITE_FLAG", "QUALITY_LINK_RECEIPT_WRITE_FLAG"):
            self.assertIn(marker, guards)

    def test_revision_append_head_plus_one_and_receipt_one_way_seal_are_explicit(self) -> None:
        revision = (DOCTYPE_ROOT / self.FOLDERS[1] / f"{self.FOLDERS[1]}.py").read_text(encoding="utf-8")
        head = (DOCTYPE_ROOT / self.FOLDERS[0] / f"{self.FOLDERS[0]}.py").read_text(encoding="utf-8")
        receipt = (DOCTYPE_ROOT / self.FOLDERS[2] / f"{self.FOLDERS[2]}.py").read_text(encoding="utf-8")
        self.assertIn("append_only = True", (MODULE / "doctype_base.py").read_text(encoding="utf-8"))
        self.assertIn("previous.optimistic_version + 1", head)
        self.assertIn("previous.revision_number + 1", head)
        self.assertIn("require_exact_parent", head)
        self.assertIn("require_exact_parent", revision)
        self.assertIn("previous.sealed or 0", receipt)
        self.assertIn("canonical_payload_hash(expected)", revision)
        self.assertIn("canonical_payload_hash(response)", receipt)

    def test_revision_and_head_controllers_keep_iso_snapshots_and_database_datetimes_distinct(self) -> None:
        validation_error = type("PinnedValidationError", (Exception,), {})
        frappe = types.ModuleType("frappe")
        frappe._ = lambda value: value
        frappe.ValidationError = validation_error
        frappe.throw = lambda message, error: (_ for _ in ()).throw(error(message))

        def parse_datetime(value: object) -> datetime:
            if isinstance(value, datetime):
                parsed = value
            else:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)

        def utc_datetime_text(value: object, _label: str) -> str:
            return parse_datetime(value).isoformat().replace("+00:00", "Z")

        def frappe_utc_datetime_text(value: object, _label: str) -> str:
            return parse_datetime(value).strftime("%Y-%m-%d %H:%M:%S.%f")

        def canonical_payload_hash(value: object) -> str:
            return hashlib.sha256(
                json.dumps(
                    value,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                    allow_nan=False,
                ).encode()
            ).hexdigest()

        parent_rows: dict[tuple[str, str], dict[str, object]] = {}

        def require_exact_parent(
            doctype: str,
            name: object,
            expected: dict[str, object],
            _message: str,
            **_kwargs: object,
        ) -> dict[str, object]:
            row = parent_rows.get((doctype, str(name)))
            if row is None or any(str(row.get(key)) != str(value) for key, value in expected.items()):
                raise validation_error("exact parent mismatch")
            return row

        core_validation = types.ModuleType("npi_core.documents.frappe_validation")
        core_validation.canonical_json = lambda value: json.dumps(
            value, sort_keys=True, separators=(",", ":")
        )
        core_validation.frappe_utc_datetime_text = frappe_utc_datetime_text
        core_validation.json_object = lambda value, _label: (
            json.loads(value) if isinstance(value, str) else dict(value)
        )
        core_validation.lowercase_sha256 = lambda value, _label: value
        core_validation.require_exact_parent = require_exact_parent
        core_validation.required_text = lambda value, _label, _maximum: value
        core_validation.utc_datetime_text = utc_datetime_text

        doctype_base = types.ModuleType("npi_integration.quality_link.doctype_base")

        class QualityLinkSupportDocument:
            def validate(self) -> None:
                return None

            def get_doc_before_save(self):
                return getattr(self, "_previous", None)

        doctype_base.QualityLinkSupportDocument = QualityLinkSupportDocument
        domain = types.ModuleType("npi_integration.quality_link.domain")
        domain.QUALITY_LINK_SCHEMA_VERSION = 1
        domain.canonical_payload_hash = canonical_payload_hash
        modules = {
            "frappe": frappe,
            "npi_core.documents.frappe_validation": core_validation,
            "npi_integration.quality_link.doctype_base": doctype_base,
            "npi_integration.quality_link.domain": domain,
        }

        def load_controller(folder: str):
            path = DOCTYPE_ROOT / folder / f"{folder}.py"
            spec = importlib.util.spec_from_file_location(
                f"p806_{folder}_timestamp_contract",
                path,
            )
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader)
            controller = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, modules):
                spec.loader.exec_module(controller)
            return controller

        revision_controller = load_controller("npi_formal_quality_link_revision")
        head_controller = load_controller("npi_formal_quality_link_head")
        created_at_iso = "2026-08-28T01:02:03Z"
        created_at_database = "2026-08-28 01:02:03.000000"
        source = {
            "tenantId": "tenant-quality-link",
            "projectGlobalId": "00000000-0000-4000-8000-00000000d601",
            "sourceKind": "readiness_assessment",
            "sourceGlobalId": "00000000-0000-4000-8000-00000000d602",
            "sourceVersion": 1,
            "sourceState": "ready",
            "sourceSnapshotHash": "a" * 64,
        }
        observation = {
            "tenantId": source["tenantId"],
            "projectGlobalId": source["projectGlobalId"],
            "scopeKind": "readiness",
            "scopeGlobalId": source["sourceGlobalId"],
            "projectionKind": "formal_quality_status",
            "sourceSystem": "ERPNEXT",
            "availability": "available",
            "freshness": "fresh",
            "disposition": "applied_current",
            "observationGlobalId": "00000000-0000-4000-8000-00000000d603",
            "headGlobalId": "00000000-0000-4000-8000-00000000d604",
            "headOptimisticVersion": 1,
            "sourceObjectType": "Quality Inspection",
            "sourceObjectId": "QI-SYNTHETIC",
            "sourceVersion": "1",
            "recordKind": "quality_inspection",
            "statusCode": "COMPLETED",
            "resultCode": None,
            "payloadHash": "b" * 64,
            "observationHash": "c" * 64,
            "headHash": "d" * 64,
            "freshnessPolicyRef": "formal_quality_v1",
        }
        link_payload = {
            "schemaVersion": 1,
            "globalId": "00000000-0000-4000-8000-00000000d605",
            "streamKeyHash": "e" * 64,
            "revisionNumber": 1,
            "predecessorGlobalId": None,
            "source": source,
            "formalObservation": observation,
            "linkState": "linked",
            "actorUserId": "quality@example.invalid",
            "traceId": "trace-quality-link-timestamp",
            "createdAt": created_at_iso,
        }
        parent_rows.update(
            {
                ("NPI ERP Projection Observation", observation["observationGlobalId"]): {
                    "global_id": observation["observationGlobalId"],
                    "tenant_id": source["tenantId"],
                    "project_global_id": source["projectGlobalId"],
                    "scope_kind": observation["scopeKind"],
                    "scope_global_id": observation["scopeGlobalId"],
                    "projection_kind": observation["projectionKind"],
                    "source_object_type": observation["sourceObjectType"],
                    "source_object_id": observation["sourceObjectId"],
                    "source_version": observation["sourceVersion"],
                    "payload_hash": observation["payloadHash"],
                    "observation_hash": observation["observationHash"],
                    "availability": observation["availability"],
                    "freshness": observation["freshness"],
                    "disposition": observation["disposition"],
                },
                ("NPI ERP Projection Head", observation["headGlobalId"]): {
                    "global_id": observation["headGlobalId"],
                    "tenant_id": source["tenantId"],
                    "project_global_id": source["projectGlobalId"],
                    "scope_kind": observation["scopeKind"],
                    "scope_global_id": observation["scopeGlobalId"],
                    "projection_kind": observation["projectionKind"],
                    "source_object_type": observation["sourceObjectType"],
                    "source_object_id": observation["sourceObjectId"],
                    "current_observation": observation["observationGlobalId"],
                    "current_source_version": observation["sourceVersion"],
                    "current_payload_hash": observation["payloadHash"],
                    "availability": observation["availability"],
                    "freshness": observation["freshness"],
                    "freshness_policy_ref": observation["freshnessPolicyRef"],
                    "optimistic_version": observation["headOptimisticVersion"],
                    "head_hash": observation["headHash"],
                },
            }
        )

        def revision_value(
            *,
            snapshot: dict[str, object] | None = None,
            link_hash: str | None = None,
            created_at: str = created_at_database,
        ):
            value = revision_controller.NPIFormalQualityLinkRevision()
            values = {
                "global_id": link_payload["globalId"],
                "schema_version": 1,
                "tenant_id": source["tenantId"],
                "project_global_id": source["projectGlobalId"],
                "source_kind": source["sourceKind"],
                "source_global_id": source["sourceGlobalId"],
                "source_version": source["sourceVersion"],
                "source_state": source["sourceState"],
                "source_snapshot_hash": source["sourceSnapshotHash"],
                "stream_key_hash": link_payload["streamKeyHash"],
                "revision_number": 1,
                "predecessor_global_id": None,
                "observation_global_id": observation["observationGlobalId"],
                "head_global_id": observation["headGlobalId"],
                "head_optimistic_version": observation["headOptimisticVersion"],
                "scope_kind": observation["scopeKind"],
                "scope_global_id": observation["scopeGlobalId"],
                "source_object_type": observation["sourceObjectType"],
                "source_object_id": observation["sourceObjectId"],
                "source_object_version": observation["sourceVersion"],
                "record_kind": observation["recordKind"],
                "raw_status_code": observation["statusCode"],
                "raw_result_code": observation["resultCode"],
                "projection_payload_hash": observation["payloadHash"],
                "observation_hash": observation["observationHash"],
                "projection_head_hash": observation["headHash"],
                "freshness_policy_ref": observation["freshnessPolicyRef"],
                "link_state": link_payload["linkState"],
                "source_snapshot": dict(source),
                "formal_observation_snapshot": dict(observation),
                "link_snapshot": dict(snapshot or link_payload),
                "link_hash": link_hash or canonical_payload_hash(link_payload),
                "actor_user_id": link_payload["actorUserId"],
                "trace_id": link_payload["traceId"],
                "created_at": created_at,
            }
            for fieldname, field_value in values.items():
                setattr(value, fieldname, field_value)
            return value

        revision = revision_value()
        revision.validate()
        self.assertEqual(json.loads(revision.link_snapshot), link_payload)
        self.assertEqual(revision.created_at, created_at_database)

        db_snapshot = dict(link_payload)
        db_snapshot["createdAt"] = created_at_database
        for candidate in (
            revision_value(
                snapshot=db_snapshot,
                link_hash=canonical_payload_hash(db_snapshot),
            ),
            revision_value(created_at="2026-08-28 01:02:04.000000"),
            revision_value(link_hash="f" * 64),
        ):
            with self.subTest(candidate=candidate.link_hash), self.assertRaises(
                validation_error
            ):
                candidate.validate()
        observation_parent = parent_rows[
            ("NPI ERP Projection Observation", observation["observationGlobalId"])
        ]
        observation_parent["freshness"] = "stale"
        with self.assertRaises(validation_error):
            revision_value().validate()
        observation_parent["freshness"] = "fresh"

        head_payload = {
            "schemaVersion": 1,
            "globalId": "00000000-0000-4000-8000-00000000d606",
            "tenantId": source["tenantId"],
            "projectGlobalId": source["projectGlobalId"],
            "sourceKind": source["sourceKind"],
            "sourceGlobalId": source["sourceGlobalId"],
            "streamKeyHash": link_payload["streamKeyHash"],
            "currentRevisionGlobalId": link_payload["globalId"],
            "revisionNumber": 1,
            "currentObservationGlobalId": observation["observationGlobalId"],
            "currentProjectionHeadGlobalId": observation["headGlobalId"],
            "currentProjectionHeadVersion": observation["headOptimisticVersion"],
            "optimisticVersion": 1,
            "updatedAt": created_at_iso,
        }
        parent_rows[("NPI Formal Quality Link Revision", link_payload["globalId"])] = {
            "global_id": link_payload["globalId"],
            "tenant_id": source["tenantId"],
            "project_global_id": source["projectGlobalId"],
            "source_kind": source["sourceKind"],
            "source_global_id": source["sourceGlobalId"],
            "stream_key_hash": link_payload["streamKeyHash"],
            "revision_number": 1,
            "observation_global_id": observation["observationGlobalId"],
            "head_global_id": observation["headGlobalId"],
            "head_optimistic_version": observation["headOptimisticVersion"],
        }

        def head_value(*, snapshot: dict[str, object] | None = None, head_hash: str | None = None):
            value = head_controller.NPIFormalQualityLinkHead()
            values = {
                "global_id": head_payload["globalId"],
                "tenant_id": head_payload["tenantId"],
                "project_global_id": head_payload["projectGlobalId"],
                "source_kind": head_payload["sourceKind"],
                "source_global_id": head_payload["sourceGlobalId"],
                "stream_key_hash": head_payload["streamKeyHash"],
                "current_revision": head_payload["currentRevisionGlobalId"],
                "revision_number": head_payload["revisionNumber"],
                "current_observation_global_id": head_payload["currentObservationGlobalId"],
                "current_projection_head_global_id": head_payload["currentProjectionHeadGlobalId"],
                "current_projection_head_version": head_payload["currentProjectionHeadVersion"],
                "optimistic_version": head_payload["optimisticVersion"],
                "head_snapshot": dict(snapshot or head_payload),
                "head_hash": head_hash or canonical_payload_hash(head_payload),
                "updated_at": created_at_database,
                "_previous": None,
            }
            for fieldname, field_value in values.items():
                setattr(value, fieldname, field_value)
            return value

        head = head_value()
        head.validate()
        self.assertEqual(json.loads(head.head_snapshot), head_payload)
        self.assertEqual(head.updated_at, created_at_database)
        db_head_snapshot = dict(head_payload)
        db_head_snapshot["updatedAt"] = created_at_database
        for candidate in (
            head_value(
                snapshot=db_head_snapshot,
                head_hash=canonical_payload_hash(db_head_snapshot),
            ),
            head_value(head_hash="f" * 64),
        ):
            with self.subTest(candidate=candidate.head_hash), self.assertRaises(
                validation_error
            ):
                candidate.validate()
        parent_rows[("NPI Formal Quality Link Revision", link_payload["globalId"])][
            "revision_number"
        ] = 2
        with self.assertRaises(validation_error):
            head_value().validate()

    def test_visible_sources_have_direct_symmetric_chinese_translations(self) -> None:
        sources: set[str] = set()
        paths = [
            MODULE / "frappe_validation.py",
            MODULE / "problems.py",
            ROOT / "apps/npi_integration/npi_integration/quality_link_api.py",
        ]
        for folder in self.FOLDERS:
            metadata = self.load(folder)
            sources.add(metadata["name"])
            sources.update(field["label"] for field in metadata["fields"])
            for field in metadata["fields"]:
                if field.get("fieldtype") == "Select":
                    sources.update(item for item in field.get("options", "").splitlines() if item)
            paths.append(DOCTYPE_ROOT / folder / f"{folder}.py")
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            sources.update(node.args[0].value for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str))
        catalogs = {}
        for language in ("zh", "zh-TW"):
            with (TRANSLATIONS / f"{language}.csv").open(encoding="utf-8", newline="") as handle:
                catalogs[language] = {row[0]: row[1] for row in csv.reader(handle) if len(row) >= 2 and row[0]}
            self.assertFalse(sorted(source for source in sources if not catalogs[language].get(source)))
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))

    def test_checkpoint_two_repository_uses_only_guarded_additive_records(self) -> None:
        repository = (MODULE / "frappe_repository.py").read_text(encoding="utf-8")
        guards = (MODULE / "frappe_validation.py").read_text(encoding="utf-8")
        for doctype, action in (
            ("NPI Formal Quality Link Revision", "insert"),
            ("NPI Formal Quality Link Head", "insert"),
            ("NPI Formal Quality Link Head", "save"),
            ("NPI Formal Quality Link Command Idempotency", "insert"),
            ("NPI Formal Quality Link Command Idempotency", "save"),
        ):
            self.assertIn(f'("{doctype}", "{action}")', guards)
        self.assertIn("with quality_link_command_write(", repository)
        self.assertIn("self._insert_receipt", repository)
        self.assertIn("self._insert_revision", repository)
        self.assertIn("self._insert_head", repository)
        self.assertIn("self._append_audit", repository)
        self.assertIn("self._seal_receipt", repository)
        self.assertNotIn("ignore_permissions", repository)


if __name__ == "__main__":
    unittest.main()
