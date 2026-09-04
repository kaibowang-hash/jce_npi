from __future__ import annotations

import ast
import copy
import csv
import hashlib
import importlib
import json
import re
import sys
import types
import unittest
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/npi_core"))
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"
RECEIPT_ROOT = DOCTYPE_ROOT / "npi_readiness_command_idempotency"
GLOBAL_ID = "1d09c19c-5f0e-435c-abbd-854348b7d6b4"
PROJECT_ID = "9943ba03-bc1e-4e4f-b407-16184fc85b4e"
TARGET_ID = "44a0554a-6e94-40a5-a48c-f1a5d376f5fd"
RECEIPT_OPERATIONS = {
    "readiness_template.create": "readiness_template",
    "readiness_template.edit": "readiness_template_version",
    "readiness_template.publish": "readiness_template_version",
    "readiness_instance.initialize": "readiness_instance_revision",
    "readiness_instance.revise": "readiness_instance_revision",
}


class StubDocument:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        for fieldname, value in (values or {}).items():
            setattr(self, fieldname, value)
        self._previous: StubDocument | None = None

    def get(self, fieldname: str) -> Any:
        return getattr(self, fieldname, None)

    def get_doc_before_save(self) -> StubDocument | None:
        return self._previous


class Phase7ReadinessMetadataTest(unittest.TestCase):
    FOLDERS = (
        "npi_readiness_template",
        "npi_readiness_template_version",
        "npi_readiness_instance_revision",
        "npi_readiness_command_idempotency",
    )

    def load(self, folder: str) -> dict[str, object]:
        return json.loads((DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8"))

    @staticmethod
    def fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
        return {item["fieldname"]: item for item in metadata["fields"]}

    def test_four_additive_doctypes_are_guarded_and_have_no_fixture_rows(self) -> None:
        for folder in self.FOLDERS:
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(metadata["autoname"], "field:global_id")
                self.assertNotIn("fixtures", metadata)
                self.assertEqual(metadata["permissions"][0]["role"], "System Manager")
                self.assertEqual(metadata["permissions"][1]["role"], "NPI API User")
                self.assertEqual(metadata["permissions"][0].get("delete"), 0)
                source = (DOCTYPE_ROOT / folder / f"{folder}.py").read_text(encoding="utf-8")
                self.assertIn("require_readiness_command_write()", source)
                self.assertIn("deny_readiness_history_delete(self)", source)
                ast.parse(source)

    def test_template_version_is_exact_and_published_history_is_immutable(self) -> None:
        fields = self.fields(self.load("npi_readiness_template_version"))
        for name in (
            "template_global_id",
            "template_version",
            "version_key_hash",
            "optimistic_version",
            "publication_state",
            "applicability_snapshot",
            "category_snapshot",
            "item_snapshot",
            "template_snapshot",
            "snapshot_hash",
        ):
            self.assertIn(name, fields)
        self.assertEqual(fields["global_id"].get("unique"), 1)
        self.assertEqual(fields["version_key_hash"].get("unique"), 1)
        source = (
            DOCTYPE_ROOT
            / "npi_readiness_template_version"
            / "npi_readiness_template_version.py"
        ).read_text(encoding="utf-8")
        self.assertIn('str(previous.publication_state) == "published"', source)
        self.assertIn("deny_readiness_history_update()", source)

    def test_instance_is_append_only_and_persists_derived_evaluation_not_score_fields(self) -> None:
        metadata = self.load("npi_readiness_instance_revision")
        fields = self.fields(metadata)
        for name in (
            "instance_global_id",
            "version_key_hash",
            "project_optimistic_version",
            "project_snapshot_hash",
            "template_revision_global_id",
            "template_version",
            "template_snapshot_hash",
            "instance_version",
            "predecessor_global_id",
            "predecessor_snapshot_hash",
            "category_snapshot",
            "item_snapshot",
            "evaluation_snapshot",
            "instance_snapshot",
            "snapshot_hash",
        ):
            self.assertIn(name, fields)
        for forbidden in (
            "caller_score",
            "readiness_percentage",
            "gate_state",
            "gate_decision",
            "erp_quality_result",
            "run_at_rate_result",
        ):
            self.assertNotIn(forbidden, fields)
        self.assertEqual(metadata["permissions"][0].get("write"), 0)
        self.assertEqual(metadata["permissions"][1].get("write"), 0)

    def test_receipt_vocabulary_is_closed_for_checkpoint_two_routes(self) -> None:
        metadata = self.load("npi_readiness_command_idempotency")
        fields = self.fields(metadata)
        operations = str(fields["operation"]["options"]).splitlines()
        targets = str(fields["target_object_type"]["options"]).splitlines()
        self.assertEqual(operations, list(RECEIPT_OPERATIONS))
        self.assertEqual(
            targets,
            ["", *dict.fromkeys(RECEIPT_OPERATIONS.values())],
        )
        self.assertNotEqual(fields["project_global_id"].get("reqd"), 1)
        self.assertTrue(all(field.get("read_only") == 1 for field in fields.values()))
        self.assertTrue(
            all(permission.get("delete") == 0 for permission in metadata["permissions"])
        )
        self.assertTrue((ROOT / "apps/npi_core/npi_core/readiness_api.py").is_file())

    def test_checkpoint_two_messages_have_symmetric_direct_translations(self) -> None:
        source_paths = (
            ROOT / "apps/npi_core/npi_core/readiness_api.py",
            RECEIPT_ROOT / "npi_readiness_command_idempotency.py",
            *(ROOT / "apps/npi_core/npi_core/readiness").glob("*.py"),
        )
        visible_sources: set[str] = set()
        for source_path in source_paths:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            visible_sources.update(
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
                sorted(
                    source_text
                    for source_text in visible_sources
                    if not catalogs[language].get(source_text)
                ),
                f"missing {language} checkpoint two readiness translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))

    def test_metadata_validation_replays_exact_domain_snapshots(self) -> None:
        source = (ROOT / "apps/npi_core/npi_core/readiness/metadata_validation.py").read_text(encoding="utf-8")
        self.assertIn("template_from_snapshot", source)
        self.assertIn("instance_from_snapshot", source)
        self.assertIn("value.evaluation.snapshot_payload()", source)
        self.assertNotIn("insert_default", source)
        ast.parse(source)

    def test_new_metadata_sources_have_direct_symmetric_chinese_translations(self) -> None:
        sources: set[str] = set()
        for folder in self.FOLDERS:
            metadata = self.load(folder)
            sources.add(str(metadata["name"]))
            sources.update(str(field["label"]) for field in metadata["fields"])
            for field in metadata["fields"]:
                if field.get("fieldtype") == "Select":
                    sources.update(value for value in str(field.get("options", "")).splitlines() if value)
        catalogs: dict[str, dict[str, str]] = {}
        for language in ("zh", "zh-TW"):
            with (TRANSLATIONS / f"{language}.csv").open(encoding="utf-8", newline="") as handle:
                catalogs[language] = {
                    row[0]: row[1]
                    for row in csv.reader(handle)
                    if len(row) >= 2 and row[0]
                }
            self.assertFalse(
                sorted(source for source in sources if not catalogs[language].get(source)),
                f"missing {language} readiness metadata translations",
            )
        self.assertEqual(set(catalogs["zh"]), set(catalogs["zh-TW"]))

    def test_every_new_link_target_is_a_real_repository_doctype(self) -> None:
        doctype_names = {
            str(json.loads(path.read_text(encoding="utf-8"))["name"])
            for path in DOCTYPE_ROOT.glob("*/*.json")
        }
        for folder in self.FOLDERS:
            for field in self.load(folder)["fields"]:
                if field.get("fieldtype") == "Link":
                    self.assertIn(field.get("options"), doctype_names)


class Phase7ReadinessReceiptControllerTest(unittest.TestCase):
    MODULES_TO_RELOAD = (
        "frappe",
        "frappe.model",
        "frappe.model.document",
        "npi_core.documents.frappe_validation",
        "npi_core.readiness.frappe_validation",
        "npi_core.readiness.metadata_validation",
        (
            "npi_core.npi_core.doctype.npi_readiness_command_idempotency"
            ".npi_readiness_command_idempotency"
        ),
    )

    def setUp(self) -> None:
        self.saved_modules = {
            name: sys.modules.get(name) for name in self.MODULES_TO_RELOAD
        }
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)

        self.ValidationError = type("ValidationError", (Exception,), {})
        self.PermissionError = type("PermissionError", (Exception,), {})
        self.parent_checks: list[tuple[object, ...]] = []

        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.ValidationError = self.ValidationError
        frappe.PermissionError = self.PermissionError
        frappe.flags = types.SimpleNamespace()

        def throw(message: str, exception: type[Exception]) -> None:
            raise exception(message)

        frappe.throw = throw
        model = types.ModuleType("frappe.model")
        document = types.ModuleType("frappe.model.document")
        document.Document = StubDocument
        model.document = document
        frappe.model = model
        sys.modules["frappe"] = frappe
        sys.modules["frappe.model"] = model
        sys.modules["frappe.model.document"] = document

        validation = types.ModuleType("npi_core.documents.frappe_validation")

        def canonical_uuid(value: object, _label: str) -> str:
            try:
                return str(UUID(str(value)))
            except (TypeError, ValueError):
                throw("invalid global ID", self.ValidationError)
            raise AssertionError

        def optional_uuid(value: object, label: str) -> str | None:
            return None if value in (None, "") else canonical_uuid(value, label)

        def required_text(value: object) -> str:
            if not isinstance(value, str) or not value.strip():
                throw("invalid text", self.ValidationError)
            return value.strip()

        def lowercase_sha256(value: object, _label: str) -> str:
            normalized = required_text(value)
            if re.fullmatch(r"[a-f0-9]{64}", normalized) is None:
                throw("invalid hash", self.ValidationError)
            return normalized

        def canonical_json(value: object) -> str:
            return json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )

        def json_object(value: object, _label: str) -> dict[str, object]:
            prepared = json.loads(value) if isinstance(value, str) else value
            if not isinstance(prepared, dict):
                throw("invalid JSON object", self.ValidationError)
            return prepared

        def utc_datetime_text(value: object, _label: str) -> str:
            if isinstance(value, datetime):
                parsed = value
            elif isinstance(value, str):
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    throw("invalid timestamp", self.ValidationError)
            else:
                throw("invalid timestamp", self.ValidationError)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")

        def frappe_utc_datetime_text(value: object, label: str) -> str:
            parsed = datetime.fromisoformat(
                utc_datetime_text(value, label).replace("Z", "+00:00")
            )
            return parsed.strftime("%Y-%m-%d %H:%M:%S.%f")

        def assert_immutable_fields(
            current: object,
            previous: object,
            fields: tuple[str, ...],
        ) -> None:
            for fieldname in fields:
                if getattr(current, fieldname, None) != getattr(
                    previous, fieldname, None
                ):
                    throw("immutable field changed", self.PermissionError)

        def require_exact_parent(
            doctype: str,
            name: object,
            expected: dict[str, object],
            message: str,
        ) -> dict[str, object]:
            self.parent_checks.append((doctype, name, expected, message))
            if name != PROJECT_ID or expected != {
                "global_id": PROJECT_ID,
                "tenant_id": "tenant-a",
            }:
                throw(message, self.ValidationError)
            return expected

        validation.actor_text = lambda value, _label: required_text(value)
        validation.assert_immutable_fields = assert_immutable_fields
        validation.canonical_json = canonical_json
        validation.frappe_utc_datetime_text = frappe_utc_datetime_text
        validation.json_object = json_object
        validation.lowercase_sha256 = lowercase_sha256
        validation.optional_uuid = optional_uuid
        validation.require_exact_parent = require_exact_parent
        validation.tenant_text = required_text
        validation.utc_datetime_text = utc_datetime_text
        sys.modules["npi_core.documents.frappe_validation"] = validation

        readiness_validation = types.ModuleType("npi_core.readiness.frappe_validation")

        def require_readiness_command_write() -> None:
            if not getattr(frappe.flags, "npi_readiness_command_write", False):
                throw("command guard required", self.PermissionError)

        def deny_readiness_history_delete(_document: object) -> None:
            throw("delete denied", self.PermissionError)

        readiness_validation.require_readiness_command_write = (
            require_readiness_command_write
        )
        readiness_validation.deny_readiness_history_delete = (
            deny_readiness_history_delete
        )
        sys.modules["npi_core.readiness.frappe_validation"] = readiness_validation

        metadata_validation = types.ModuleType("npi_core.readiness.metadata_validation")

        def canonical_readiness_identity(value: object) -> None:
            value.global_id = canonical_uuid(value.global_id, "Global ID")
            value.name = value.global_id

        metadata_validation.canonical_readiness_identity = canonical_readiness_identity
        sys.modules["npi_core.readiness.metadata_validation"] = metadata_validation

        self.frappe = frappe
        module = importlib.import_module(self.MODULES_TO_RELOAD[-1])
        self.Controller = module.NPIReadinessCommandIdempotency
        self.identity_fields = module._IDENTITY_FIELDS

        from npi_core.project.domain import ProjectType
        from npi_core.readiness.domain import (
            ReadinessApplicabilitySelector,
            ReadinessBlockingLevel,
            ReadinessCategoryDefinition,
            ReadinessCompletionRule,
            ReadinessGateReference,
            ReadinessItemDefinition,
            ReadinessItemState,
            ReadinessMemberReference,
            ReadinessProjectSnapshot,
            ReadinessTemplateVersion,
            initialize_readiness_instance,
            revise_readiness_item,
        )
        from npi_core.readiness.source_resolver import (
            EXTERNAL_SOURCE_KINDS,
            EXTERNAL_UNAVAILABLE_REASON_CODES,
        )

        applicability = ReadinessApplicabilitySelector(
            project_types=(ProjectType.NEW_TOOL,),
            industry_keys=("automotive",),
        )
        template = ReadinessTemplateVersion.create_draft(
            template_global_id=UUID(TARGET_ID),
            template_code="NPI-AUTO",
            template_version=1,
            title="Automotive NPI readiness",
            applicability=applicability,
            categories=(ReadinessCategoryDefinition("launch", "Launch readiness"),),
            items=(
                ReadinessItemDefinition(
                    key="handover",
                    title="Handover",
                    category_key="launch",
                    weight=10,
                    required=True,
                    blocking_level=ReadinessBlockingLevel.P0,
                    gate_key="G6",
                    completion_rule=ReadinessCompletionRule.CONFIRMATION,
                    applicability=applicability,
                ),
            ),
            changed_by_user_id="owner@example.com",
            changed_at=datetime(2026, 8, 11, 1, 1, tzinfo=UTC),
            request_id=UUID(int=91),
            trace_id="trace-p705-receipt-template",
        )
        published = template.publish(
            expected_version=1,
            changed_by_user_id="owner@example.com",
            changed_at=datetime(2026, 8, 11, 1, 2, tzinfo=UTC),
            request_id=UUID(int=92),
            trace_id="trace-p705-receipt-publish",
        )
        self.template_response = {
            **template.snapshot_payload(),
            "snapshotHash": template.snapshot_hash,
        }
        self.published_template_response = {
            **published.snapshot_payload(),
            "snapshotHash": published.snapshot_hash,
        }

        member = ReadinessMemberReference(UUID(int=93), "owner@example.com", 1)
        project = ReadinessProjectSnapshot(
            UUID(PROJECT_ID),
            1,
            "1" * 64,
            ProjectType.NEW_TOOL,
            (),
            "automotive",
        )
        gate = ReadinessGateReference(UUID(int=94), "G6", 1, "2" * 64)
        initialized = initialize_readiness_instance(
            global_id=UUID(int=95),
            instance_global_id=UUID(int=96),
            tenant_id="tenant-a",
            project=project,
            template=published,
            gates={"G6": gate},
            assignments={"handover": (member, date(2026, 9, 1))},
            created_by_user_id="owner@example.com",
            created_at=datetime(2026, 8, 11, 1, 3, tzinfo=UTC),
            request_id=UUID(int=97),
            trace_id="trace-p705-receipt-initialize",
        )
        revised = revise_readiness_item(
            initialized,
            global_id=UUID(int=98),
            expected_instance_version=1,
            item_key="handover",
            owner=member,
            due_date=date(2026, 9, 2),
            state=ReadinessItemState.IN_PROGRESS,
            confirmation_value=None,
            sources=(),
            created_by_user_id="owner@example.com",
            created_at=datetime(2026, 8, 11, 1, 4, tzinfo=UTC),
            request_id=UUID(int=99),
            trace_id="trace-p705-receipt-revise",
        )
        unavailable = [
            {
                "kind": kind.value,
                "state": "unavailable",
                "reasonCode": EXTERNAL_UNAVAILABLE_REASON_CODES[kind],
            }
            for kind in sorted(EXTERNAL_SOURCE_KINDS, key=lambda item: item.value)
        ]

        def workspace(*revisions) -> dict[str, object]:
            responses = [
                {**value.snapshot_payload(), "snapshotHash": value.snapshot_hash}
                for value in revisions
            ]
            return {
                "projectGlobalId": PROJECT_ID,
                "currentRevision": responses[-1],
                "revisions": responses,
                "sourceOptions": [],
                "unavailableProjections": unavailable,
                "permissions": {
                    "canManageTemplates": True,
                    "canInitialize": True,
                    "canRevise": True,
                },
            }

        self.initialize_response = workspace(initialized)
        self.revise_response = workspace(initialized, revised)
        self.operation_responses = {
            "readiness_template.create": self.template_response,
            "readiness_template.edit": self.template_response,
            "readiness_template.publish": self.published_template_response,
            "readiness_instance.initialize": self.initialize_response,
            "readiness_instance.revise": self.revise_response,
        }
        self.operation_targets = {
            "readiness_template.create": self.template_response["templateGlobalId"],
            "readiness_template.edit": self.template_response["globalId"],
            "readiness_template.publish": self.published_template_response["globalId"],
            "readiness_instance.initialize": self.initialize_response[
                "currentRevision"
            ]["globalId"],
            "readiness_instance.revise": self.revise_response["currentRevision"][
                "globalId"
            ],
        }

    def tearDown(self) -> None:
        for name in self.MODULES_TO_RELOAD:
            sys.modules.pop(name, None)
        for name, module in self.saved_modules.items():
            if module is not None:
                sys.modules[name] = module

    def receipt(
        self,
        operation: str,
        *,
        project_global_id: str | None = None,
    ) -> StubDocument:
        document = self.Controller(
            {
                "global_id": GLOBAL_ID.upper(),
                "receipt_key": None,
                "tenant_id": " tenant-a ",
                "project_global_id": project_global_id,
                "actor_user_id": "Owner@Example.COM",
                "operation": operation,
                "idempotency_key_hash": "a" * 64,
                "payload_hash": "b" * 64,
                "target_object_type": None,
                "target_global_id": None,
                "response_payload": "{}",
                "response_hash": None,
                "sealed": 0,
                "created_at": "2026-08-11T01:02:03Z",
                "updated_at": "2026-08-11T01:02:03Z",
            }
        )
        document.before_validate()
        return document

    @staticmethod
    def snapshot(document: StubDocument) -> StubDocument:
        return StubDocument(
            {
                fieldname: value
                for fieldname, value in vars(document).items()
                if fieldname != "_previous"
            }
        )

    def test_receipt_identity_key_and_nullable_project_scope_are_canonical(self) -> None:
        template = self.receipt("readiness_template.create")
        template.validate()
        expected_key = hashlib.sha256(
            json.dumps(
                {
                    "actorUserId": "owner@example.com",
                    "idempotencyKeyHash": "a" * 64,
                    "operation": "readiness_template.create",
                    "projectGlobalId": None,
                    "tenantId": "tenant-a",
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(template.name, GLOBAL_ID)
        self.assertEqual(template.receipt_key, expected_key)
        self.assertEqual(template.response_payload, "{}")
        self.assertEqual(self.parent_checks, [])

        instance = self.receipt(
            "readiness_instance.initialize",
            project_global_id=PROJECT_ID.upper(),
        )
        instance.validate()
        self.assertEqual(instance.project_global_id, PROJECT_ID)
        self.assertEqual(len(self.parent_checks), 1)
        self.assertEqual(
            self.parent_checks[0][0:2],
            ("NPI Engineering Project", PROJECT_ID),
        )

    def test_each_receipt_operation_seals_only_its_mapped_target(self) -> None:
        for operation, target_type in RECEIPT_OPERATIONS.items():
            with self.subTest(operation=operation):
                document = self.receipt(
                    operation,
                    project_global_id=(
                        PROJECT_ID if operation.startswith("readiness_instance.") else None
                    ),
                )
                document.validate()
                document._previous = self.snapshot(document)
                document.target_object_type = target_type
                document.target_global_id = self.operation_targets[operation].upper()
                document.response_payload = copy.deepcopy(
                    self.operation_responses[operation]
                )
                document.response_hash = None
                document.sealed = 1
                document.updated_at = "2026-08-11T01:02:04Z"
                document.before_validate()
                document.validate()
                expected_response = json.dumps(
                    self.operation_responses[operation],
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                self.assertEqual(document.response_payload, expected_response)
                self.assertEqual(
                    document.response_hash,
                    hashlib.sha256(expected_response.encode("utf-8")).hexdigest(),
                )

    def test_receipt_rejects_extra_fields_target_drift_and_wrong_operation_state(
        self,
    ) -> None:
        secret = "database-password-must-not-escape"

        extra = self.receipt("readiness_template.create")
        extra.validate()
        extra._previous = self.snapshot(extra)
        extra.target_object_type = "readiness_template"
        extra.target_global_id = self.operation_targets["readiness_template.create"]
        extra.response_payload = {**self.template_response, "databasePassword": secret}
        extra.sealed = 1
        extra.before_validate()
        with self.assertRaises(RuntimeError) as context:
            extra.validate()
        self.assertNotIn(secret, str(context.exception))

        drifted = self.receipt("readiness_template.edit")
        drifted.validate()
        drifted._previous = self.snapshot(drifted)
        drifted.target_object_type = "readiness_template_version"
        drifted.target_global_id = str(UUID(int=1234))
        drifted.response_payload = copy.deepcopy(self.template_response)
        drifted.sealed = 1
        drifted.before_validate()
        with self.assertRaises(RuntimeError):
            drifted.validate()

        wrong_state = self.receipt("readiness_template.publish")
        wrong_state.validate()
        wrong_state._previous = self.snapshot(wrong_state)
        wrong_state.target_object_type = "readiness_template_version"
        wrong_state.target_global_id = self.operation_targets[
            "readiness_template.publish"
        ]
        wrong_state.response_payload = copy.deepcopy(self.template_response)
        wrong_state.sealed = 1
        wrong_state.before_validate()
        with self.assertRaises(RuntimeError):
            wrong_state.validate()

    def test_receipt_rejects_oversized_project_snapshot_collection(self) -> None:
        from npi_core.readiness.domain import instance_from_snapshot

        response = copy.deepcopy(self.initialize_response)
        revision = copy.deepcopy(response["currentRevision"])
        revision["project"]["customerReferenceKeys"] = [
            f"CUSTOMER:{index:03d}" for index in range(101)
        ]
        snapshot = {
            key: value
            for key, value in revision.items()
            if key != "snapshotHash"
        }
        parsed = instance_from_snapshot(snapshot)
        canonical_revision = {
            **parsed.snapshot_payload(),
            "snapshotHash": parsed.snapshot_hash,
        }
        response["currentRevision"] = canonical_revision
        response["revisions"] = [copy.deepcopy(canonical_revision)]

        document = self.receipt(
            "readiness_instance.initialize",
            project_global_id=PROJECT_ID,
        )
        document.validate()
        document._previous = self.snapshot(document)
        document.target_object_type = "readiness_instance_revision"
        document.target_global_id = canonical_revision["globalId"]
        document.response_payload = response
        document.sealed = 1
        document.before_validate()
        with self.assertRaises(RuntimeError):
            document.validate()

    def test_unsealed_or_mismatched_receipt_response_is_rejected(self) -> None:
        premature = self.receipt("readiness_template.create")
        premature.response_payload = {"globalId": TARGET_ID}
        with self.assertRaises(self.ValidationError):
            premature.validate()

        wrong_target = self.receipt("readiness_template.publish")
        wrong_target.validate()
        wrong_target._previous = self.snapshot(wrong_target)
        wrong_target.target_object_type = "readiness_template"
        wrong_target.target_global_id = TARGET_ID
        wrong_target.response_payload = {"globalId": TARGET_ID}
        wrong_target.sealed = 1
        with self.assertRaises(self.PermissionError):
            wrong_target.validate()

        wrong_hash = self.receipt(
            "readiness_instance.revise",
            project_global_id=PROJECT_ID,
        )
        wrong_hash.validate()
        wrong_hash._previous = self.snapshot(wrong_hash)
        wrong_hash.target_object_type = "readiness_instance_revision"
        wrong_hash.target_global_id = self.operation_targets[
            "readiness_instance.revise"
        ]
        wrong_hash.response_payload = copy.deepcopy(self.revise_response)
        wrong_hash.response_hash = "c" * 64
        wrong_hash.sealed = 1
        with self.assertRaises(self.ValidationError):
            wrong_hash.validate()

    def test_receipt_project_scope_matches_the_operation_family(self) -> None:
        with self.assertRaises(self.ValidationError):
            self.receipt(
                "readiness_template.create",
                project_global_id=PROJECT_ID,
            ).validate()
        with self.assertRaises(self.ValidationError):
            self.receipt("readiness_instance.initialize").validate()

    def test_receipt_identity_and_sealed_response_are_immutable(self) -> None:
        self.assertTrue(
            {"actor_user_id", "operation", "payload_hash"}.issubset(
                self.identity_fields
            )
        )
        for fieldname, replacement in (
            ("actor_user_id", "other@example.com"),
            ("operation", "readiness_template.edit"),
            ("payload_hash", "c" * 64),
        ):
            with self.subTest(fieldname=fieldname):
                document = self.receipt("readiness_template.create")
                document.validate()
                document._previous = self.snapshot(document)
                setattr(document, fieldname, replacement)
                document.target_object_type = RECEIPT_OPERATIONS[
                    "readiness_template.create"
                ]
                document.target_global_id = TARGET_ID
                document.response_payload = {"globalId": TARGET_ID}
                document.sealed = 1
                with self.assertRaises((self.ValidationError, self.PermissionError)):
                    document.validate()

        sealed = self.receipt("readiness_template.create")
        sealed.validate()
        sealed._previous = self.snapshot(sealed)
        sealed.target_object_type = "readiness_template"
        sealed.target_global_id = self.operation_targets["readiness_template.create"]
        sealed.response_payload = copy.deepcopy(self.template_response)
        sealed.sealed = 1
        sealed.validate()
        sealed._previous = self.snapshot(sealed)
        sealed.response_payload = {**self.template_response, "changed": True}
        with self.assertRaises(self.PermissionError):
            sealed.validate()

    def test_generic_receipt_create_update_and_delete_are_guarded(self) -> None:
        document = self.receipt("readiness_template.create")
        with self.assertRaises(self.PermissionError):
            document.before_insert()
        with self.assertRaises(self.PermissionError):
            document.before_save()
        with self.assertRaises(self.PermissionError):
            document.on_trash()

        self.frappe.flags.npi_readiness_command_write = True
        document.before_insert()
        document.before_save()


if __name__ == "__main__":
    unittest.main()
