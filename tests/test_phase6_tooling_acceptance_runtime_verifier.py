from __future__ import annotations

import copy
import importlib.util
import inspect
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_tooling_acceptance_runtime.py"
RUNTIME_SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    saved = {
        name: sys.modules.pop(name, None)
        for name in (
            "verify_document_runtime",
            "verify_tooling_runtime",
            "verify_tooling_revision_runtime",
            "verify_tooling_manufacturing_runtime",
            "verify_tooling_engineering_controls_runtime",
            "verify_tooling_acceptance_runtime_contract",
        )
    }
    spec = importlib.util.spec_from_file_location(
        "verify_tooling_acceptance_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Tooling acceptance runtime verifier cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        with patch.dict(
            os.environ,
            {"NPI_DOCUMENT_RUNTIME_RUN_ID": FIXTURE_RUN_ID},
            clear=False,
        ):
            spec.loader.exec_module(module)
    finally:
        for name in tuple(saved):
            sys.modules.pop(name, None)
        for name, value in saved.items():
            if value is not None:
                sys.modules[name] = value
    return module


class Phase6ToolingAcceptanceRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def context(self) -> dict[str, object]:
        return {
            "projectId": "10000000-0000-4000-8000-000000000001",
            "masterId": "20000000-0000-4000-8000-000000000002",
            "masterSnapshotHash": "a" * 64,
            "member": {
                "globalId": "30000000-0000-4000-8000-000000000003",
                "userId": self.module.ACTOR_USER,
                "optimisticVersion": 1,
            },
            "fileEvidence": {
                "fileRevisionGlobalId": "40000000-0000-4000-8000-000000000004",
                "fileOptimisticVersion": 2,
                "frappeContentHash": "b" * 32,
                "sha256": "c" * 64,
            },
            "revisionId": "50000000-0000-4000-8000-000000000005",
            "revisionNumber": 3,
            "revisionLabel": "C",
            "revisionSnapshotHash": "d" * 64,
            "toolingSetId": "60000000-0000-4000-8000-000000000006",
            "toolingSetSnapshotHash": "e" * 64,
            "bindingId": "70000000-0000-4000-8000-000000000007",
            "bindingSnapshotHash": "f" * 64,
            "requirementKind": "customer_owned_intake",
            "physicalSerial": "P6-02-PHYSICAL-001",
        }

    def acceptance(self, version: int) -> dict[str, object]:
        return {
            "globalId": f"80000000-0000-4000-8000-00000000000{version}",
            "acceptanceGlobalId": "90000000-0000-4000-8000-000000000009",
            "acceptanceVersion": version,
            "snapshotHash": str(version) * 64,
        }

    def available_asset_projection(self) -> dict[str, object]:
        return {
            "sourceSystem": "ERPNEXT",
            "editableIn": "ERPNEXT",
            "state": "available",
            "mappingCardinality": "zero_or_one_per_physical_set",
            "toolingSetGlobalId": self.context()["toolingSetId"],
            "mappingVersion": 1,
            "formalAssetId": "ASSET-CONFIRMED-001",
            "targetVersion": "sandbox-asset-v1",
            "assetState": "active",
            "currentLocation": "Confirmed location",
            "shotCount": 12,
            "expectedLifeShots": 100000,
            "maintenanceDue": "2026-12-01",
            "movements": [
                {
                    "globalId": "a0000000-0000-4000-8000-000000000001",
                    "actionKind": "move",
                    "fromLocation": "A",
                    "toLocation": "B",
                    "occurredAt": "2026-08-01T01:02:03Z",
                    "sourceObjectId": "MOVE-CONFIRMED-1",
                }
            ],
            "repairs": [
                {
                    "globalId": "b0000000-0000-4000-8000-000000000002",
                    "summary": "Confirmed repair",
                    "downtimeHours": "4",
                    "completedAt": "2026-08-02T01:02:03Z",
                    "sourceObjectId": "REPAIR-CONFIRMED-1",
                }
            ],
            "spares": [
                {
                    "formalItemId": "ITEM-CONFIRMED-1",
                    "description": "Confirmed spare",
                    "stockOnHand": "2",
                    "minimumStock": "1",
                    "unit": "EA",
                    "supplierId": None,
                }
            ],
            "observationGlobalId": "c0000000-0000-4000-8000-000000000003",
            "observationHash": "1" * 64,
            "observedAt": "2026-08-03T01:02:03Z",
        }

    def acceptance_context_value(self, projection: object) -> dict[str, object]:
        context = self.context()
        return {
            "projectGlobalId": context["projectId"],
            "toolingMasterGlobalId": context["masterId"],
            "permissions": {
                "view": True,
                "recordEvidence": True,
                "prepareMockAssetRequest": True,
                "approveAcceptance": False,
                "dispatchAssetRequest": False,
                "editErpProjection": False,
            },
            "businessApproval": {
                "state": "unavailable",
                "reasonCode": "tooling_acceptance_policy_unavailable",
            },
            "assetProjection": projection,
            "acceptanceRevisions": [{}, {}],
            "assetRequests": [{}],
        }

    def test_acceptance_context_uses_independent_closed_asset_projection_modes(self) -> None:
        module = self.module
        self.assertIs(
            inspect.signature(module.assert_acceptance_context)
            .parameters["expected_asset_projection_mode"]
            .default,
            module.ExpectedAssetProjectionMode.UNAVAILABLE,
        )
        self.assertIs(
            inspect.signature(module.replay_context)
            .parameters["expected_asset_projection_mode"]
            .default,
            module.ExpectedAssetProjectionMode.UNAVAILABLE,
        )
        unavailable = self.acceptance_context_value(
            copy.deepcopy(module._ASSET_PROJECTION_UNAVAILABLE)
        )
        available = self.acceptance_context_value(self.available_asset_projection())
        for value, mode in (
            (unavailable, module.ExpectedAssetProjectionMode.UNAVAILABLE),
            (available, module.ExpectedAssetProjectionMode.AVAILABLE),
        ):
            with self.subTest(mode=mode):
                result = module.assert_acceptance_context(
                    SimpleNamespace(status=200, body=value),
                    context=self.context(),
                    acceptance_count=2,
                    request_count=1,
                    expected_asset_projection_mode=mode,
                )
                self.assertIs(result, value)

        with self.assertRaisesRegex(
            RuntimeError, "^P6-06 expected ERP Asset projection mode is invalid$"
        ):
            module.assert_acceptance_context(
                SimpleNamespace(status=200, body=unavailable),
                context=self.context(),
                acceptance_count=2,
                request_count=1,
                expected_asset_projection_mode="available",
            )

    def test_replay_context_explicitly_forwards_asset_projection_mode(self) -> None:
        module = self.module
        context = self.context()
        retained = {
            "acceptanceRevisions": [self.acceptance(1), self.acceptance(2)],
            "assetRequests": [{}],
        }
        with (
            patch.object(module, "project_context", return_value=context),
            patch.object(module, "tooling_request", return_value=object()),
            patch.object(
                module,
                "assert_acceptance_context",
                return_value=retained,
            ) as acceptance_context,
            patch.object(module, "assert_acceptance_revision"),
            patch.object(module, "assert_asset_request"),
        ):
            result = module.replay_context(
                object(),
                "http://127.0.0.1:8003",
                expected_asset_projection_mode=(
                    module.ExpectedAssetProjectionMode.AVAILABLE
                ),
            )
        self.assertEqual(result, (context, *retained["acceptanceRevisions"], {}))
        self.assertIs(
            acceptance_context.call_args.kwargs["expected_asset_projection_mode"],
            module.ExpectedAssetProjectionMode.AVAILABLE,
        )

    def test_available_asset_projection_is_strict_and_constant_safe(self) -> None:
        module = self.module
        cases = {}
        for name, mutate in (
            ("extra", lambda value: value.update({"privateValue": "must-not-leak"})),
            (
                "wrong-set",
                lambda value: value.update(
                    {"toolingSetGlobalId": str(UUID(int=99))}
                ),
            ),
            ("mapping-bool", lambda value: value.update({"mappingVersion": True})),
            ("shot-bool", lambda value: value.update({"shotCount": True})),
            (
                "movement-shape",
                lambda value: value["movements"][0].update(
                    {"privateValue": "must-not-leak"}
                ),
            ),
            (
                "repair-type",
                lambda value: value["repairs"][0].update({"downtimeHours": 4}),
            ),
            (
                "spare-type",
                lambda value: value["spares"][0].update({"stockOnHand": 2}),
            ),
            ("observed-at", lambda value: value.update({"observedAt": "not-a-date"})),
        ):
            projection = self.available_asset_projection()
            mutate(projection)
            cases[name] = projection
        for name, projection in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^P6-06 confirmed ERP Asset projection truth drifted$",
                ) as raised:
                    module.assert_acceptance_context(
                        SimpleNamespace(
                            status=200,
                            body=self.acceptance_context_value(projection),
                        ),
                        context=self.context(),
                        acceptance_count=2,
                        request_count=1,
                        expected_asset_projection_mode=(
                            module.ExpectedAssetProjectionMode.AVAILABLE
                        ),
                    )
                self.assertNotIn("must-not-leak", str(raised.exception))
                self.assertNotIn("not-a-date", str(raised.exception))

    def test_available_mode_does_not_relax_permissions_approval_or_cardinality(self) -> None:
        module = self.module
        for key, replacement in (
            ("permissions", {"view": True}),
            ("businessApproval", {"state": "approved"}),
        ):
            value = self.acceptance_context_value(self.available_asset_projection())
            value[key] = replacement
            with self.subTest(key=key), self.assertRaisesRegex(
                RuntimeError,
                "^P6-06 identity, permissions, or approval truth drifted$",
            ):
                module.assert_acceptance_context(
                    SimpleNamespace(status=200, body=value),
                    context=self.context(),
                    acceptance_count=2,
                    request_count=1,
                    expected_asset_projection_mode=(
                        module.ExpectedAssetProjectionMode.AVAILABLE
                    ),
                )
        value = self.acceptance_context_value(self.available_asset_projection())
        value["acceptanceRevisions"] = [{}]
        with self.assertRaisesRegex(
            RuntimeError, "^P6-06 retained acceptance/Asset cardinality drifted$"
        ):
            module.assert_acceptance_context(
                SimpleNamespace(status=200, body=value),
                context=self.context(),
                acceptance_count=2,
                request_count=1,
                expected_asset_projection_mode=(
                    module.ExpectedAssetProjectionMode.AVAILABLE
                ),
            )

    def test_fixture_namespace_and_scope_are_synthetic_and_bounded(self) -> None:
        module = self.module
        self.assertEqual(module.FIXTURE_RUN_ID, FIXTURE_RUN_ID)
        self.assertEqual(module.TENANT_ID, "runtime-tenant")
        self.assertTrue(module.ACTOR_USER.endswith("@example.invalid"))
        self.assertTrue(module.UNRELATED_USER.endswith("@example.invalid"))
        self.assertIn(
            'validate_local_fixture_inputs(\n        arguments.base_url,\n        "Administrator",',
            self.source,
        )
        self.assertNotIn("core." + "whjichen.cn", self.source)
        self.assertNotIn("requests.post", self.source)
        self.assertNotIn("erpnext_url", self.source.casefold())

    def test_acceptance_payload_has_nine_categories_and_customer_authorization(self) -> None:
        module = self.module
        context = self.context()
        first = module.acceptance_payload(context, version=1)
        self.assertEqual(
            {item["category"] for item in first["checklist"]},
            set(module.ACCEPTANCE_CATEGORIES),
        )
        self.assertEqual(len(first["checklist"]), 9)
        self.assertNotIn("acceptanceGlobalId", first)
        self.assertNotIn("expectedVersion", first)
        self.assertEqual(
            first["repairs"][0]["customerAuthorizationEvidence"][0]["role"],
            "customer_authorization",
        )
        self.assertEqual(first["assetActions"][0]["evidence"][0]["role"], "action")
        predecessor_value = self.acceptance(1)
        second = module.acceptance_payload(
            context,
            version=2,
            predecessor_value=predecessor_value,
        )
        self.assertEqual(
            second["acceptanceGlobalId"], predecessor_value["acceptanceGlobalId"]
        )
        self.assertEqual(second["expectedVersion"], 1)

    def test_asset_request_payload_is_operation_specific_and_mock_only(self) -> None:
        module = self.module
        payload = module.asset_request_payload(self.context(), self.acceptance(2))
        self.assertEqual(payload["targetMode"], "mock")
        self.assertEqual(payload["acknowledgement"], module.ACKNOWLEDGEMENT)
        self.assertEqual(payload["acceptanceVersion"], 2)
        for forbidden in (
            "operation",
            "targetPayload",
            "assetId",
            "approvalState",
            "dispatch",
            "targetResult",
        ):
            self.assertNotIn(forbidden, payload)

    def test_request_delegates_to_closed_predecessor_transport(self) -> None:
        raw = SimpleNamespace(status=200, headers={}, body={})
        with patch.object(
            self.module.predecessor,
            "tooling_request",
            return_value=raw,
        ) as request:
            result = self.module.tooling_request(
                object(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/project/tooling/master/acceptance-assets",
                query_key="acceptance",
            )
        self.assertIs(result, raw)
        self.assertEqual(request.call_args.kwargs["query_key"], "p606-acceptance")

    def test_asset_create_diagnostic_uses_exact_shared_trace_and_safe_reader(self) -> None:
        module = self.module
        path = module.asset_request_command_path(
            "10000000-0000-4000-8000-000000000001",
            "20000000-0000-4000-8000-000000000002",
            "30000000-0000-4000-8000-000000000003",
        )
        trace_id = "trace-" + "a" * 32
        result = SimpleNamespace(
            status=500,
            headers={
                "X-Request-ID": module.document_runtime.fixture_request_id(
                    module.ASSET_REQUEST_KEY
                ),
                "Cache-Control": "private, no-store",
            },
            body={"private": "must not leak"},
            trace_id=trace_id,
        )
        tuple_value = (
            "ValidationError",
            "P805_P606_ASSET_REQUEST_INSERT",
            trace_id,
        )
        with (
            patch.object(module, "P606_ASSET_CREATE_DIAGNOSTICS_ENABLED", True),
            patch.object(module.item_runtime, "_replay_diagnostic_log_cursors", return_value={"cursor": 0}),
            patch.object(module.document_runtime, "request", return_value=result) as request,
            patch.object(
                module.item_runtime,
                "_sanitized_server_log_diagnostic",
                return_value=tuple_value,
            ) as reader,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                r"diagnostic_code=P805_P606_ASSET_REQUEST_INSERT; "
                r"exception_type=ValidationError; trace_id=trace-[a-f0-9]{32}",
            ) as raised:
                module.command(
                    object(),
                    "http://127.0.0.1:8003",
                    "csrf",
                    path,
                    {"private": "must not leak"},
                    module.ASSET_REQUEST_KEY,
                    asset_create_diagnostic=True,
                )
        headers = request.call_args.kwargs["request_headers"]
        self.assertEqual(
            headers[module._P606_ASSET_CREATE_DIAGNOSTIC_HEADER],
            module._P606_ASSET_CREATE_DIAGNOSTIC_SCOPE,
        )
        self.assertEqual(reader.call_args.args[:2], (trace_id, {"cursor": 0}))
        self.assertEqual(
            reader.call_args.kwargs,
            {
                "code_prefix": "P805_P606_ASSET_",
                "allowed_codes": module._P606_ASSET_CREATE_DIAGNOSTIC_CODES,
            },
        )
        self.assertNotIn("must not leak", str(raised.exception))
        self.assertNotIn("500", str(raised.exception))

    def test_asset_create_reader_accepts_one_logical_record_and_rejects_ambiguity(self) -> None:
        module = self.module
        trace_id = "trace-" + "c" * 32
        code = "P805_P606_ASSET_REQUEST_INSERT"
        valid = {
            "code": code,
            "exceptionType": "ValidationError",
            "traceId": trace_id,
        }
        with tempfile.TemporaryDirectory() as directory:
            bench = Path(directory).resolve()
            with patch.object(module.item_runtime, "BENCH_PATH", bench):
                paths = module.item_runtime._replay_diagnostic_log_paths()

                def prepare() -> dict[str, int]:
                    for path in paths:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text("prior\n", encoding="utf-8")
                    cursors = module.item_runtime._replay_diagnostic_log_cursors()
                    self.assertIsNotNone(cursors)
                    return cursors or {}

                def read(cursors):
                    return module.item_runtime._sanitized_server_log_diagnostic(
                        trace_id,
                        cursors,
                        code_prefix="P805_P606_ASSET_",
                        allowed_codes=module._P606_ASSET_CREATE_DIAGNOSTIC_CODES,
                    )

                cursors = prepare()
                with paths[0].open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(valid) + "\n")
                self.assertEqual(read(cursors), ("ValidationError", code, trace_id))

                cursors = prepare()
                for path in paths:
                    with path.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(valid) + "\n")
                self.assertEqual(read(cursors), ("ValidationError", code, trace_id))

                cursors = prepare()
                with paths[0].open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(valid) + "\n" + json.dumps(valid) + "\n")
                self.assertIsNone(read(cursors))

                cursors = prepare()
                different = {**valid, "code": "P805_P606_ASSET_RECEIPT_SEAL"}
                for path, record in zip(paths, (valid, different), strict=True):
                    with path.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(record) + "\n")
                self.assertIsNone(read(cursors))

                for invalid in (
                    {**valid, "traceId": "trace-" + "d" * 32},
                    {**valid, "exceptionType": "invalid type"},
                    {**valid, "private": "must-not-leak"},
                ):
                    cursors = prepare()
                    with paths[0].open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(invalid) + "\n")
                    self.assertIsNone(read(cursors))

    def test_asset_create_diagnostic_is_bounded_off_and_constant_on_reader_failure(self) -> None:
        module = self.module
        valid_path = module.asset_request_command_path(
            "10000000-0000-4000-8000-000000000001",
            "20000000-0000-4000-8000-000000000002",
            "30000000-0000-4000-8000-000000000003",
        )
        failure = SimpleNamespace(
            status=500,
            headers={"X-Request-ID": "untrusted", "Cache-Control": "private, no-store"},
            body={"secret": "body-value"},
            trace_id=None,
        )
        for enabled, key, path in (
            (False, module.ASSET_REQUEST_KEY, valid_path),
            (True, "different-key", valid_path),
            (True, module.ASSET_REQUEST_KEY, "/wrong/path"),
        ):
            with self.subTest(enabled=enabled, key=key, path=path):
                with (
                    patch.object(module, "P606_ASSET_CREATE_DIAGNOSTICS_ENABLED", enabled),
                    patch.object(module.predecessor, "tooling_request", return_value=failure) as predecessor,
                    patch.object(module.document_runtime, "request") as direct,
                ):
                    with self.assertRaises(RuntimeError):
                        module.command(
                            object(), "http://127.0.0.1:8003", "csrf", path, {}, key,
                            asset_create_diagnostic=True,
                        )
                predecessor.assert_called_once()
                direct.assert_not_called()

        headers = module.document_runtime.command_headers(
            "csrf", module.ASSET_REQUEST_KEY
        )
        failure.headers["X-Request-ID"] = headers["X-Request-ID"]
        with (
            patch.object(module, "P606_ASSET_CREATE_DIAGNOSTICS_ENABLED", True),
            patch.object(module.item_runtime, "_replay_diagnostic_log_cursors", return_value=None),
            patch.object(module.document_runtime, "request", return_value=failure),
            patch.object(module.item_runtime, "_sanitized_server_log_diagnostic", return_value=None),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "^P6-06 Tool Asset predecessor command failed$"
            ) as raised:
                module.command(
                    object(), "http://127.0.0.1:8003", "csrf", valid_path, {},
                    module.ASSET_REQUEST_KEY, asset_create_diagnostic=True,
                )
        self.assertNotIn("body-value", str(raised.exception))

    def test_asset_create_diagnostic_is_dormant_by_default(self) -> None:
        module = self.module
        self.assertFalse(module.P606_ASSET_CREATE_DIAGNOSTICS_ENABLED)
        path = module.asset_request_command_path(
            "10000000-0000-4000-8000-000000000001",
            "20000000-0000-4000-8000-000000000002",
            "30000000-0000-4000-8000-000000000003",
        )
        failure = SimpleNamespace(
            status=500,
            headers={},
            body={"private": "must not leak"},
            trace_id="trace-" + "e" * 32,
        )
        with (
            patch.object(module.predecessor, "tooling_request", return_value=failure) as predecessor,
            patch.object(module.item_runtime, "_replay_diagnostic_log_cursors") as cursors,
            patch.object(module.document_runtime, "request") as direct,
            patch.object(module.item_runtime, "_sanitized_server_log_diagnostic") as reader,
        ):
            with self.assertRaises(RuntimeError):
                module.command(
                    object(),
                    "http://127.0.0.1:8003",
                    "csrf",
                    path,
                    {},
                    module.ASSET_REQUEST_KEY,
                    asset_create_diagnostic=True,
                )
        predecessor.assert_called_once()
        cursors.assert_not_called()
        direct.assert_not_called()
        reader.assert_not_called()

    def test_asset_create_diagnostic_allowlist_has_one_product_context_per_code(self) -> None:
        module = self.module
        api_source = (
            ROOT
            / "apps/npi_integration/npi_integration/tool_asset_request_api.py"
        ).read_text(encoding="utf-8")
        repository_source = (
            ROOT
            / "apps/npi_integration/npi_integration/tool_asset_request/frappe_repository.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(len(module._P606_ASSET_CREATE_DIAGNOSTIC_CODES), 20)
        for code in module._P606_ASSET_CREATE_DIAGNOSTIC_CODES:
            with self.subTest(code=code):
                self.assertEqual((api_source + repository_source).count(f'"{code}"'), 1)
        self.assertNotIn("result.body", self.source[
            self.source.index("if result.status != 201 and diagnostic_active"):
            self.source.index("require(\n        result.status == 201")
        ])

    def test_project_context_binds_customer_owned_set_revision_and_master(self) -> None:
        module = self.module
        context = self.context()
        predecessor_context = {
            key: context[key]
            for key in (
                "projectId",
                "masterId",
                "member",
                "fileEvidence",
                "revisionId",
                "revisionSnapshotHash",
                "toolingSetId",
                "toolingSetSnapshotHash",
            )
        }
        predecessor_context["revisionId"] = (
            "51000000-0000-4000-8000-000000000005"
        )
        predecessor_context["revisionSnapshotHash"] = "9" * 64

        def fixture_rows(_administrator, _base_url, doctype, filters, fields=None):
            if doctype == "NPI Tooling Master":
                return [
                    {
                        "global_id": context["masterId"],
                        "snapshot_hash": context["masterSnapshotHash"],
                    }
                ]
            if doctype == "NPI Tooling Set":
                self.assertIn(["project_global_id", "=", context["projectId"]], filters)
                return [
                    {
                        "global_id": context["toolingSetId"],
                        "requirement_kind": context["requirementKind"],
                        "physical_serial": context["physicalSerial"],
                        "snapshot_hash": context["toolingSetSnapshotHash"],
                    }
                ]
            if doctype == "NPI Tooling Set Revision Binding":
                self.assertEqual(
                    filters,
                    [
                        ["project_global_id", "=", context["projectId"]],
                        ["tooling_set_global_id", "=", context["toolingSetId"]],
                    ],
                )
                return [
                    {
                        "global_id": context["bindingId"],
                        "tooling_revision_global_id": context["revisionId"],
                        "tooling_revision_snapshot_hash": context[
                            "revisionSnapshotHash"
                        ],
                        "snapshot_hash": context["bindingSnapshotHash"],
                    }
                ]
            if doctype == "NPI Tooling Revision":
                return [
                    {
                        "global_id": context["revisionId"],
                        "revision_number": context["revisionNumber"],
                        "revision_label": context["revisionLabel"],
                        "snapshot_hash": context["revisionSnapshotHash"],
                    }
                ]
            raise AssertionError(f"Unexpected fixture doctype: {doctype}")

        with (
            patch.object(
                module.predecessor,
                "project_context",
                return_value=predecessor_context,
            ),
            patch.object(module, "rows", side_effect=fixture_rows),
        ):
            resolved = module.project_context(object(), "http://127.0.0.1:8003")
        self.assertEqual(resolved["requirementKind"], "customer_owned_intake")
        self.assertEqual(resolved["bindingId"], context["bindingId"])
        self.assertEqual(resolved["revisionId"], context["revisionId"])
        self.assertEqual(
            resolved["engineeringRevisionId"],
            predecessor_context["revisionId"],
        )
        self.assertEqual(
            module.predecessor_context(resolved)["revisionId"],
            predecessor_context["revisionId"],
        )

    def test_verifier_covers_required_runtime_truth_and_failure_boundaries(self) -> None:
        required = (
            "TOOLING_IDEMPOTENCY_CONFLICT",
            "TOOLING_VERSION_CONFLICT",
            "TOOLING_REFERENCE_UNAVAILABLE",
            "VALIDATION_FAILED",
            "TOOLING_ACCEPTANCE_ASSETS_ROUTES_DISABLED",
            "customer-owned repair authorization truth drifted",
            "local Mock preparation created integration traffic",
            "accepted generic mutation",
            "cross-process replay changed immutable or integration cardinality",
            "unauthorized and absent request details are distinguishable",
            "phase_6_dispatch_prohibited",
            "zero_or_one_per_physical_set",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.source)

    def test_idor_fixture_has_transport_access_without_system_manager_bypass(self) -> None:
        idor_source = self.source.split("def verify_idor(", 1)[1].split(
            "def verify_conflict_rollback(",
            1,
        )[0]
        self.assertIn("document_runtime.create_internal_fixture_user(", idor_source)
        self.assertNotIn("create_resource(", idor_source)
        self.assertNotIn('"System Manager"', idor_source)
        self.assertEqual(
            idor_source.count(
                'validate_problem(denied_command, 403, "PERMISSION_DENIED")'
            ),
            1,
        )

    def test_shell_orchestrates_independent_fail_closed_switch_and_cleanup(self) -> None:
        required = (
            "tooling_acceptance_assets_route_switch_state",
            "npi_p6_06_routes_disabled",
            "set_tooling_acceptance_assets_route_switch true true",
            "set_tooling_acceptance_assets_route_switch false false",
            "run_tooling_acceptance_runtime_verifier fresh",
            "run_tooling_acceptance_route_probe disabled",
            "run_tooling_acceptance_route_probe recovered",
            "run_tooling_acceptance_runtime_verifier replay-only",
            "restore_tooling_acceptance_assets_route_switch",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.shell)
        self.assertLess(
            self.shell.index("run_tooling_engineering_controls_runtime_verifier replay-only"),
            self.shell.index("run_tooling_acceptance_runtime_verifier fresh"),
        )
        self.assertLess(
            self.shell.index("run_tooling_acceptance_route_probe disabled"),
            self.shell.index("run_tooling_acceptance_route_probe recovered"),
        )
        self.assertLess(
            self.shell.index("run_tooling_acceptance_route_probe recovered"),
            self.shell.index("run_tooling_acceptance_runtime_verifier replay-only"),
        )

    def test_manual_controlled_workflow_records_exact_cumulative_scope(self) -> None:
        self.assertIn(
            "name: P5 controlled document runtime and P6 Tooling through export",
            self.workflow,
        )
        self.assertIn("Verify cumulative P5 and P6-08 controlled runtime", self.workflow)
        self.assertIn("scope=p5-01-through-p6-08", self.workflow)
        self.assertIn(
            "bash scripts/verify-frappe-runtime.sh --tooling-only",
            self.workflow,
        )
        self.assertIn("if: github.event_name == 'workflow_dispatch'", self.workflow)


if __name__ == "__main__":
    unittest.main()
