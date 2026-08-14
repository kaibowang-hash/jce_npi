from __future__ import annotations

import ast
import copy
import csv
import importlib.util
import json
import sys
import types
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import uuid5


ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_ROOT = ROOT / "apps/npi_core/npi_core/npi_core/doctype"
TRANSITION_ROOT = ROOT / "apps/npi_core/npi_core/production_transition"
TRANSLATIONS = ROOT / "apps/npi_core/npi_core/translations"
RECEIPT_ROOT = DOCTYPE_ROOT / "npi_production_transition_command_idempotency"
RECEIPT_OPERATIONS = {
    "production_transition_policy.create": "production_transition_policy",
    "production_transition_policy.edit": "production_transition_policy_version",
    "production_transition_policy.publish": "production_transition_policy_version",
    "production_transition_policy.next_version": "production_transition_policy_version",
    "production_handover.create": "handover_package_revision",
    "production_handover.revise": "handover_package_revision",
    "production_handover.acknowledge": "handover_acknowledgement",
    "observation_period.create": "observation_period_revision",
    "observation_period.revise": "observation_period_revision",
}


class Phase7ProductionTransitionMetadataTest(unittest.TestCase):
    FOLDERS = (
        "npi_production_transition_policy",
        "npi_production_transition_policy_version",
        "npi_handover_package_revision",
        "npi_handover_acknowledgement",
        "npi_observation_period_revision",
        "npi_production_transition_command_idempotency",
    )

    def load(self, folder: str) -> dict[str, object]:
        return json.loads(
            (DOCTYPE_ROOT / folder / f"{folder}.json").read_text(encoding="utf-8")
        )

    @staticmethod
    def fields(metadata: dict[str, object]) -> dict[str, dict[str, object]]:
        return {item["fieldname"]: item for item in metadata["fields"]}

    def test_six_additive_doctypes_are_guarded_and_install_no_rows(self) -> None:
        for folder in self.FOLDERS:
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertEqual(metadata["autoname"], "field:global_id")
                self.assertNotIn("fixtures", metadata)
                self.assertEqual(metadata["permissions"][0]["role"], "System Manager")
                self.assertEqual(metadata["permissions"][1]["role"], "NPI API User")
                self.assertTrue(
                    all(
                        permission.get("delete") == 0
                        for permission in metadata["permissions"]
                    )
                )
                source = (
                    DOCTYPE_ROOT / folder / f"{folder}.py"
                ).read_text(encoding="utf-8")
                self.assertIn("require_production_transition_command_write()", source)
                self.assertIn("deny_production_transition_history_delete(self)", source)
                ast.parse(source)
        policy = self.load("npi_production_transition_policy")
        policy_fields = self.fields(policy)
        version_fields = self.fields(
            self.load("npi_production_transition_policy_version")
        )
        self.assertTrue(all("default" not in field for field in policy["fields"]))
        self.assertNotEqual(policy_fields["policy_code"].get("unique"), 1)
        self.assertEqual(policy_fields["policy_code_key_hash"].get("unique"), 1)
        for fields in (policy_fields, version_fields):
            self.assertEqual(fields["tenant_id"].get("reqd"), 1)
            self.assertEqual(fields["tenant_id"].get("read_only"), 1)
        validation_source = (TRANSITION_ROOT / "metadata_validation.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("document.tenant_id = tenant_text(value.tenant_id)", validation_source)
        self.assertIn('"tenant_id": value.tenant_id', validation_source)
        self.assertIn("document.policy_code_key_hash = hashlib.sha256", validation_source)

    def test_only_draft_policy_versions_have_a_guarded_update_path(self) -> None:
        version_metadata = self.load("npi_production_transition_policy_version")
        version_fields = self.fields(version_metadata)
        version_source = (
            DOCTYPE_ROOT
            / "npi_production_transition_policy_version"
            / "npi_production_transition_policy_version.py"
        ).read_text(encoding="utf-8")
        self.assertIn("require_production_transition_policy_version_write()", version_source)
        self.assertIn('str(previous.publication_state) == "published"', version_source)
        self.assertIn("deny_production_transition_history_update()", version_source)
        self.assertEqual(version_metadata["permissions"][0].get("write"), 1)
        self.assertEqual(version_metadata["permissions"][1].get("write"), 1)
        for name in (
            "version_key_hash",
            "optimistic_version",
            "publication_state",
            "changed_by_user_id",
            "changed_at",
            "request_id",
            "trace_id",
            "policy_snapshot",
            "snapshot_hash",
        ):
            self.assertIn(name, version_fields)
        self.assertEqual(version_fields["version_key_hash"].get("unique"), 1)

        for folder in (
            "npi_handover_package_revision",
            "npi_handover_acknowledgement",
            "npi_observation_period_revision",
        ):
            with self.subTest(folder=folder):
                metadata = self.load(folder)
                self.assertTrue(
                    all(
                        permission.get("write") == 0
                        for permission in metadata["permissions"]
                    )
                )
                source = (
                    DOCTYPE_ROOT / folder / f"{folder}.py"
                ).read_text(encoding="utf-8")
                self.assertIn("deny_production_transition_history_update()", source)

    def test_policy_and_actor_fields_preserve_contract_lengths(self) -> None:
        expected_lengths = {
            "npi_production_transition_policy": {"title": 200},
            "npi_production_transition_policy_version": {
                "title": 200,
                "changed_by_user_id": 254,
            },
            "npi_handover_package_revision": {"created_by_user_id": 254},
            "npi_handover_acknowledgement": {"actor_user_id": 254},
            "npi_observation_period_revision": {"created_by_user_id": 254},
            "npi_production_transition_command_idempotency": {
                "actor_user_id": 254
            },
        }
        for folder, lengths in expected_lengths.items():
            fields = self.fields(self.load(folder))
            for fieldname, length in lengths.items():
                with self.subTest(folder=folder, fieldname=fieldname):
                    self.assertEqual(fields[fieldname].get("length"), length)

    def test_package_and_acknowledgement_store_exact_facts_not_derived_completion(self) -> None:
        package_fields = self.fields(self.load("npi_handover_package_revision"))
        acknowledgement_fields = self.fields(
            self.load("npi_handover_acknowledgement")
        )
        for name in (
            "handover_global_id",
            "handover_version",
            "predecessor_global_id",
            "predecessor_snapshot_hash",
            "project_optimistic_version",
            "project_snapshot_hash",
            "policy_version_global_id",
            "policy_snapshot_hash",
            "slot_snapshot",
            "manifest_snapshot",
            "unresolved_selector_snapshot",
            "unresolved_action_snapshot",
            "package_snapshot",
            "snapshot_hash",
        ):
            self.assertIn(name, package_fields)
        for name in (
            "package_revision_global_id",
            "package_version",
            "package_snapshot_hash",
            "slot_key",
            "acknowledgement_intent",
            "actor_user_id",
            "member_global_id",
            "member_optimistic_version",
            "member_snapshot_hash",
            "role_global_id",
            "role_optimistic_version",
            "role_snapshot_hash",
            "acknowledgement_snapshot",
            "snapshot_hash",
        ):
            self.assertIn(name, acknowledgement_fields)
        self.assertNotIn("fully_acknowledged", package_fields)
        self.assertNotIn("approval_state", package_fields)
        self.assertNotIn("signature", acknowledgement_fields)
        self.assertNotIn("delegated_actor_user_id", acknowledgement_fields)

    def test_observation_storage_preserves_identity_free_unavailable_sources(self) -> None:
        fields = self.fields(self.load("npi_observation_period_revision"))
        for name in (
            "observation_global_id",
            "observation_version",
            "predecessor_global_id",
            "predecessor_snapshot_hash",
            "provider_source_snapshot",
            "context_reference_snapshot",
            "retrospective_evidence_snapshot",
            "observation_state",
            "technical_disposition",
            "observation_snapshot",
            "snapshot_hash",
        ):
            self.assertIn(name, fields)
        for forbidden in (
            "actual_sop_date",
            "first_batch_yield_value",
            "customer_complaint_count",
            "production_cycle_time_value",
            "tooling_stability_value",
            "provider_identity",
            "formal_stability_conclusion",
            "gate_decision",
        ):
            self.assertNotIn(forbidden, fields)
        self.assertEqual(fields["technical_disposition"]["options"], "not_evaluable")

    def test_receipt_operation_and_target_vocabulary_is_closed(self) -> None:
        metadata = self.load("npi_production_transition_command_idempotency")
        fields = self.fields(metadata)
        self.assertEqual(
            str(fields["operation"]["options"]).splitlines(),
            list(RECEIPT_OPERATIONS),
        )
        self.assertEqual(
            str(fields["target_object_type"]["options"]).splitlines(),
            ["", *dict.fromkeys(RECEIPT_OPERATIONS.values())],
        )
        self.assertNotEqual(fields["project_global_id"].get("reqd"), 1)
        self.assertTrue(all(field.get("read_only") == 1 for field in fields.values()))
        controller = (
            RECEIPT_ROOT / "npi_production_transition_command_idempotency.py"
        ).read_text(encoding="utf-8")
        self.assertIn("actorUserId", controller)
        self.assertIn("assert_immutable_fields", controller)
        self.assertIn("expected_target_type", controller)
        self.assertIn("validate_receipt_response", controller)
        self.assertIn("tenant_id=self.tenant_id", controller)
        self.assertLess(
            controller.index("validate_receipt_response("),
            controller.index("expected_response_hash = _sha256_json(response)"),
        )
        self.assertNotIn("ignore_" + "permissions", controller)

    def test_sealed_receipt_rejects_unclosed_or_mismatched_replay_truth(self) -> None:
        from tests.test_phase7_production_transition_domain import (
            draft_policy,
            package,
        )

        from npi_core.production_transition.response_validation import (
            ProductionTransitionResponseInvalid,
            validate_receipt_response,
        )

        policy = draft_policy()
        policy_response = {
            **policy.snapshot_payload(),
            "snapshotHash": policy.snapshot_hash,
        }
        self.assertEqual(
            validate_receipt_response(
                "production_transition_policy.create",
                policy_response,
                target_global_id=str(policy.policy_global_id),
                project_global_id=None,
                tenant_id=policy.tenant_id,
            ),
            policy_response,
        )
        for operation, response, target, project_id in (
            (
                "unsupported.operation",
                policy_response,
                str(policy.policy_global_id),
                None,
            ),
            (
                "production_transition_policy.create",
                policy_response,
                "00000000-0000-0000-0000-000000000999",
                None,
            ),
            (
                "production_transition_policy.create",
                policy_response,
                str(policy.policy_global_id),
                "00000000-0000-0000-0000-000000000999",
            ),
        ):
            with self.subTest(operation=operation, target=target, project=project_id):
                with self.assertRaises(ProductionTransitionResponseInvalid):
                    validate_receipt_response(
                        operation,
                        response,
                        target_global_id=target,
                        project_global_id=project_id,
                        tenant_id=policy.tenant_id,
                    )

        extra = copy.deepcopy(policy_response)
        extra["secret"] = "must-not-be-retained"
        with self.assertRaises(ProductionTransitionResponseInvalid):
            validate_receipt_response(
                "production_transition_policy.create",
                extra,
                target_global_id=str(policy.policy_global_id),
                project_global_id=None,
                tenant_id=policy.tenant_id,
            )
        tampered = copy.deepcopy(policy_response)
        tampered["snapshotHash"] = "0" * 64
        with self.assertRaises(ProductionTransitionResponseInvalid):
            validate_receipt_response(
                "production_transition_policy.create",
                tampered,
                target_global_id=str(policy.policy_global_id),
                project_global_id=None,
                tenant_id=policy.tenant_id,
            )

        handover = package()
        handover_response = {
            "projectGlobalId": str(handover.project.global_id),
            "handoverPackage": {
                **handover.snapshot_payload(),
                "snapshotHash": handover.snapshot_hash,
            },
        }
        self.assertEqual(
            validate_receipt_response(
                "production_handover.create",
                handover_response,
                target_global_id=str(handover.global_id),
                project_global_id=str(handover.project.global_id),
                tenant_id=handover.tenant_id,
            ),
            handover_response,
        )
        wrong_project = copy.deepcopy(handover_response)
        wrong_project["projectGlobalId"] = (
            "00000000-0000-0000-0000-000000000999"
        )
        with self.assertRaises(ProductionTransitionResponseInvalid):
            validate_receipt_response(
                "production_handover.create",
                wrong_project,
                target_global_id=str(handover.global_id),
                project_global_id=str(handover.project.global_id),
                tenant_id=handover.tenant_id,
            )

    def test_snapshot_metadata_replays_the_four_domain_objects(self) -> None:
        source = (TRANSITION_ROOT / "metadata_validation.py").read_text(
            encoding="utf-8"
        )
        for parser in (
            "policy_from_snapshot",
            "handover_package_from_snapshot",
            "acknowledgement_from_snapshot",
            "observation_from_snapshot",
        ):
            self.assertIn(parser, source)
        self.assertIn("value.snapshot_payload()", source)
        self.assertIn("value.version_key_hash", source)
        self.assertIn(
            "validate_policy_persistence_transition(previous_value, value)",
            source,
        )
        self.assertIn('extra_fields=("tenant_id", "project_global_id", "package_snapshot")', source)
        self.assertIn("_validate_acknowledgement_package_slot(value, package_value)", source)
        self.assertNotIn("insert_default", source)
        self.assertNotIn("ignore_" + "permissions", source)
        ast.parse(source)

    def test_metadata_and_controller_sources_have_symmetric_direct_translations(self) -> None:
        sources: set[str] = set()
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
            for path in (DOCTYPE_ROOT / folder).glob("*.py"):
                sources.update(self.literal_translation_sources(path))
        for path in TRANSITION_ROOT.glob("*.py"):
            sources.update(self.literal_translation_sources(path))

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
                f"missing {language} production-transition translations",
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

    @staticmethod
    def literal_translation_sources(path: Path) -> set[str]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return {
            str(node.args[0].value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        }


class Phase7ProductionTransitionFrappeGuardTest(unittest.TestCase):
    def test_policy_version_insert_and_publish_use_the_dedicated_guard(self) -> None:
        controller_path = (
            DOCTYPE_ROOT
            / "npi_production_transition_policy_version"
            / "npi_production_transition_policy_version.py"
        )
        tree = ast.parse(controller_path.read_text(encoding="utf-8"))
        before_insert = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "before_insert"
        )
        insert_calls = {
            node.func.id
            for node in ast.walk(before_insert)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertIn(
            "require_production_transition_policy_version_write", insert_calls
        )
        self.assertNotIn("require_production_transition_command_write", insert_calls)

        module_name = "tests._p706_policy_version_controller"
        dependency_names = (
            "frappe",
            "frappe.model",
            "frappe.model.document",
            "npi_core.production_transition.frappe_validation",
            "npi_core.production_transition.metadata_validation",
            module_name,
        )
        saved = {name: sys.modules.get(name) for name in dependency_names}
        events: list[str] = []

        validation_error = type("ValidationError", (Exception,), {})
        permission_error = type("PermissionError", (Exception,), {})
        frappe = types.ModuleType("frappe")
        frappe.__path__ = []
        frappe.ValidationError = validation_error
        frappe.PermissionError = permission_error
        frappe._ = lambda source: source

        def throw(message: str, error: type[Exception]) -> None:
            raise error(message)

        frappe.throw = throw
        frappe_model = types.ModuleType("frappe.model")
        frappe_model.__path__ = []
        frappe_document = types.ModuleType("frappe.model.document")

        class Document:
            def get_doc_before_save(self):
                return getattr(self, "_previous", None)

        frappe_document.Document = Document
        guard_module = types.ModuleType(
            "npi_core.production_transition.frappe_validation"
        )

        def command_guard() -> None:
            events.append("command")

        def policy_guard() -> None:
            events.append("policy")

        def deny_update() -> None:
            events.append("deny-update")
            raise permission_error("immutable")

        guard_module.require_production_transition_command_write = command_guard
        guard_module.require_production_transition_policy_version_write = policy_guard
        guard_module.deny_production_transition_history_update = deny_update
        guard_module.deny_production_transition_history_delete = lambda document: None
        metadata_module = types.ModuleType(
            "npi_core.production_transition.metadata_validation"
        )
        metadata_module.normalize_policy_version_identity = lambda document: None
        validated_previous: list[object | None] = []
        metadata_module.validate_policy_version_document = (
            lambda document, previous=None: validated_previous.append(previous)
        )

        sys.modules.update(
            {
                "frappe": frappe,
                "frappe.model": frappe_model,
                "frappe.model.document": frappe_document,
                "npi_core.production_transition.frappe_validation": guard_module,
                "npi_core.production_transition.metadata_validation": metadata_module,
            }
        )
        try:
            spec = importlib.util.spec_from_file_location(module_name, controller_path)
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader)
            controller_module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = controller_module
            spec.loader.exec_module(controller_module)
            controller_type = controller_module.NPIProductionTransitionPolicyVersion

            draft = controller_type()
            draft.publication_state = "draft"
            draft.before_insert()
            self.assertEqual(events, ["policy"])

            events.clear()
            published_insert = controller_type()
            published_insert.publication_state = "published"
            with self.assertRaises(validation_error):
                published_insert.before_insert()
            self.assertEqual(events, ["policy"])

            events.clear()
            publish = controller_type()
            publish.publication_state = "published"
            publish._previous = types.SimpleNamespace(publication_state="draft")
            publish.before_save()
            self.assertEqual(events, ["command", "policy"])

            events.clear()
            publish.validate()
            self.assertEqual(events, ["policy"])
            self.assertEqual(validated_previous, [publish._previous])

            events.clear()
            immutable = controller_type()
            immutable.publication_state = "published"
            immutable._previous = types.SimpleNamespace(publication_state="published")
            with self.assertRaises(permission_error):
                immutable.before_save()
            self.assertEqual(events, ["command", "deny-update"])
        finally:
            for name, module in saved.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

    def test_acknowledgement_is_bound_to_the_exact_frozen_package_slot(self) -> None:
        from tests.test_phase7_production_transition_domain import (
            NOW,
            SENDER_MEMBER,
            SENDER_ROLE,
            package,
            uid,
        )
        from npi_core.production_transition.domain import (
            create_handover_acknowledgement,
        )

        handover = package()
        acknowledgement = create_handover_acknowledgement(
            handover,
            slot_key="sender",
            acknowledgement_intent=True,
            actor_user_id=SENDER_MEMBER.user_id,
            actor_user_enabled=True,
            current_member=SENDER_MEMBER,
            current_role=SENDER_ROLE,
            acknowledged_at=NOW,
            request_id=uid(88),
            trace_id="trace-p706-metadata-ack",
        )
        module_name = "tests._p706_metadata_validation"
        validation_module_name = "npi_core.documents.frappe_validation"
        dependency_names = ("frappe", validation_module_name, module_name)
        saved = {name: sys.modules.get(name) for name in dependency_names}

        validation_error = type("ValidationError", (Exception,), {})
        frappe = types.ModuleType("frappe")
        frappe.ValidationError = validation_error
        frappe._ = lambda source: source

        def throw(message: str, error: type[Exception]) -> None:
            raise error(message)

        frappe.throw = throw
        validation_module = types.ModuleType(validation_module_name)
        for name in (
            "actor_text",
            "canonical_json",
            "canonical_uuid",
            "frappe_utc_datetime_text",
            "json_array",
            "json_object",
            "lowercase_sha256",
            "optional_uuid",
            "require_exact_parent",
            "required_text",
            "tenant_text",
        ):
            setattr(validation_module, name, lambda *args, **kwargs: args[0])
        sys.modules["frappe"] = frappe
        sys.modules[validation_module_name] = validation_module
        try:
            metadata_path = TRANSITION_ROOT / "metadata_validation.py"
            spec = importlib.util.spec_from_file_location(module_name, metadata_path)
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader)
            metadata_module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = metadata_module
            spec.loader.exec_module(metadata_module)

            metadata_module._validate_acknowledgement_package_slot(
                acknowledgement, handover
            )
            tampered_bindings = (
                {"actor_user_id": "attacker@example.invalid"},
                {"member_global_id": uid(777)},
                {
                    "member_optimistic_version": (
                        acknowledgement.member_optimistic_version + 1
                    )
                },
                {"member_snapshot_hash": "a" * 64},
                {"role_global_id": uid(778)},
                {
                    "role_optimistic_version": (
                        acknowledgement.role_optimistic_version + 1
                    )
                },
                {"role_snapshot_hash": "b" * 64},
            )
            for changes in tampered_bindings:
                with self.subTest(changes=changes):
                    attacker = replace(acknowledgement, **changes)
                    with self.assertRaises(validation_error):
                        metadata_module._validate_acknowledgement_package_slot(
                            attacker, handover
                        )
            unknown_slot = replace(
                acknowledgement,
                global_id=uuid5(
                    handover.global_id,
                    "npi-handover-acknowledgement:unknown",
                ),
                slot_key="unknown",
            )
            with self.assertRaises(validation_error):
                metadata_module._validate_acknowledgement_package_slot(
                    unknown_slot, handover
                )
        finally:
            for name, module in saved.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

    def test_write_flags_are_scoped_and_restored(self) -> None:
        module_name = "npi_core.production_transition.frappe_validation"
        saved_frappe = sys.modules.get("frappe")
        saved_module = sys.modules.get(module_name)
        frappe = types.ModuleType("frappe")
        frappe.flags = types.SimpleNamespace(existing="retained")
        frappe.PermissionError = type("PermissionError", (Exception,), {})
        frappe._ = lambda source: source

        def throw(message: str, error: type[Exception]) -> None:
            raise error(message)

        frappe.throw = throw
        sys.modules["frappe"] = frappe
        sys.modules.pop(module_name, None)
        sys.path.insert(0, str(ROOT / "apps/npi_core"))
        try:
            module = __import__(module_name, fromlist=["*"])
            with self.assertRaises(frappe.PermissionError):
                module.require_production_transition_command_write()
            with module.production_transition_policy_version_write():
                module.require_production_transition_command_write()
                module.require_production_transition_policy_version_write()
            self.assertFalse(
                hasattr(frappe.flags, module.PRODUCTION_TRANSITION_COMMAND_WRITE_FLAG)
            )
            self.assertFalse(
                hasattr(
                    frappe.flags,
                    module.PRODUCTION_TRANSITION_POLICY_VERSION_WRITE_FLAG,
                )
            )
            self.assertEqual(frappe.flags.existing, "retained")
        finally:
            sys.path.remove(str(ROOT / "apps/npi_core"))
            if saved_frappe is None:
                sys.modules.pop("frappe", None)
            else:
                sys.modules["frappe"] = saved_frappe
            if saved_module is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = saved_module


if __name__ == "__main__":
    unittest.main()
