from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_document_runtime.py"
RUNTIME_SHELL = ROOT / "scripts" / "verify-frappe-runtime.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
TOOLCHAIN = ROOT / ".devcontainer" / "toolchain.env"
FIXTURE_RUN_ID = "0123456789abcdef0123456789abcdef"


def load_verifier():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "verify_document_runtime_contract",
        VERIFIER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Document runtime verifier cannot be imported")
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
        sys.modules.pop(spec.name, None)
    return module


class Phase5DocumentRuntimeVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_verifier()
        cls.source = VERIFIER.read_text(encoding="utf-8")
        cls.shell = RUNTIME_SHELL.read_text(encoding="utf-8")
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    def test_fixture_namespace_and_headers_are_bounded(self) -> None:
        module = self.module
        self.assertEqual(
            module.validated_fixture_run_id(FIXTURE_RUN_ID),
            FIXTURE_RUN_ID,
        )
        for invalid in (None, "", "A" * 32, "a" * 31, "../runtime"):
            with self.subTest(invalid=invalid), self.assertRaises(RuntimeError):
                module.validated_fixture_run_id(invalid)
        self.assertRegex(
            module.PROJECT_TEMPLATE_ID,
            r"^[a-f0-9-]{36}$",
        )
        self.assertNotEqual(
            module.PROJECT_TEMPLATE_ID,
            module.DOCUMENT_POLICY_ID,
        )
        self.assertRegex(
            module.OWNER_USER,
            r"^npi-document-[a-f0-9]{20}-owner@example[.]invalid$",
        )
        self.assertRegex(
            module.UNRELATED_USER,
            r"^npi-document-[a-f0-9]{20}-unrelated@example[.]invalid$",
        )
        self.assertRegex(
            module.BASELINE_USER,
            r"^npi-document-[a-f0-9]{20}-baseline@example[.]invalid$",
        )
        self.assertEqual(
            len({module.OWNER_USER, module.BASELINE_USER, module.UNRELATED_USER}),
            3,
        )
        headers = module.command_headers(
            "csrf-" + ("a" * 48),
            module.DOCUMENT_CREATE_KEY,
        )
        self.assertEqual(headers["Idempotency-Key"], module.DOCUMENT_CREATE_KEY)
        self.assertRegex(
            headers["X-Request-ID"],
            r"^[a-f0-9-]{36}$",
        )
        self.assertTrue(headers["X-Trace-ID"].startswith("trace-"))

    def test_runtime_pdf_fixture_is_structurally_complete_and_safe(self) -> None:
        content = self.module.PDF_CONTENT
        self.assertEqual(content, self.module.build_synthetic_pdf())
        self.assertTrue(content.startswith(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"))
        self.assertNotIn(b"/JS", content)
        self.assertNotIn(b"/JavaScript", content)

        startxref_match = re.search(
            rb"startxref\n([0-9]+)\n%%EOF\n\Z",
            content,
        )
        self.assertIsNotNone(startxref_match)
        xref_offset = int(startxref_match.group(1))
        self.assertEqual(content[xref_offset : xref_offset + 5], b"xref\n")

        xref_match = re.search(
            rb"xref\n0 5\n0000000000 65535 f \n"
            rb"((?:[0-9]{10} 00000 n \n){4})",
            content,
        )
        self.assertIsNotNone(xref_match)
        object_offsets = re.findall(rb"([0-9]{10}) 00000 n", xref_match.group(1))
        self.assertEqual(len(object_offsets), 4)
        for number, encoded_offset in enumerate(object_offsets, start=1):
            offset = int(encoded_offset)
            self.assertTrue(
                content[offset:].startswith(f"{number} 0 obj\n".encode())
            )

    def test_baseline_payload_is_exact_and_caller_cannot_select_file_truth(
        self,
    ) -> None:
        payload = self.module.baseline_command_payload(
            policy_snapshot_hash="a" * 64,
            revision_id="20873131-6923-5ad4-bf35-74efdc358224",
            revision_snapshot_hash="b" * 64,
            release_snapshot_hash="c" * 64,
        )
        self.assertEqual(
            set(payload),
            {
                "policyGlobalId",
                "policyVersion",
                "policySnapshotHash",
                "label",
                "members",
            },
        )
        self.assertEqual(
            set(payload["members"][0]),
            {
                "revisionId",
                "expectedRevisionSnapshotHash",
                "expectedLifecycleVersion",
                "expectedReleaseSnapshotHash",
            },
        )
        serialized = json.dumps(payload, sort_keys=True).casefold()
        for forbidden in ("scanstate", "fileurl", '"url"', "cookie"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, serialized)

    def test_relationship_runtime_diagnostic_is_closed_and_sanitized(self) -> None:
        module = self.module
        expected_codes = {
            "P5_RUNTIME_RELATIONSHIP_FILTER_HTTP",
            "P5_RUNTIME_RELATIONSHIP_FILTER_CARDINALITY",
            "P5_RUNTIME_RELATIONSHIP_FILTER_IDENTITY",
        }
        self.assertEqual(
            set(module._RUNTIME_RELATIONSHIP_DIAGNOSTIC_CODES),
            expected_codes,
        )
        trace_id = "trace-" + ("a" * 32)
        for code in expected_codes:
            with self.subTest(code=code):
                with self.assertRaises(module.RuntimeSubstageFailure) as failure:
                    module.require_runtime_substage(
                        False,
                        code=code,
                        trace_id=trace_id,
                    )
                diagnostic = module.runtime_substage_diagnostic(
                    failure.exception
                )
                self.assertEqual(
                    diagnostic,
                    (
                        f"[diagnostic_code={code}; "
                        "exc_type=RuntimeSubstageFailure; "
                        f"trace_id={trace_id}]"
                    ),
                )
                self.assertNotIn("request", diagnostic.casefold())
                self.assertNotIn("cookie", diagnostic.casefold())
                self.assertNotIn("credential", diagnostic.casefold())

        self.assertIsNone(
            module.require_runtime_substage(
                True,
                code="P5_RUNTIME_RELATIONSHIP_FILTER_HTTP",
                trace_id=trace_id,
            )
        )
        for code, candidate_trace in (
            ("NOT_ALLOWLISTED", trace_id),
            ("P5_RUNTIME_RELATIONSHIP_FILTER_HTTP", "invalid-trace"),
        ):
            with (
                self.subTest(code=code, trace_id=candidate_trace),
                self.assertRaises(ValueError),
            ):
                module.require_runtime_substage(
                    False,
                    code=code,
                    trace_id=candidate_trace,
                )

    def test_baseline_workspace_diagnostic_is_predicate_level_and_closed(
        self,
    ) -> None:
        module = self.module
        expected_codes = {
            "P503_RUNTIME_BASELINE_WORKSPACE_HTTP",
            "P503_RUNTIME_BASELINE_WORKSPACE_BODY_SHAPE",
            "P503_RUNTIME_BASELINE_WORKSPACE_PERMISSIONS_SHAPE",
            "P503_RUNTIME_BASELINE_WORKSPACE_VIEW_PERMISSION",
            "P503_RUNTIME_BASELINE_WORKSPACE_CREATE_PERMISSION",
            "P503_RUNTIME_BASELINE_WORKSPACE_ITEMS_EMPTY",
            "P503_RUNTIME_BASELINE_WORKSPACE_IMPACTS_EMPTY",
            "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_CARDINALITY",
            "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_SHAPE",
            "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_IDENTITY",
            "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_VERSION",
            "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_HASH",
            "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_KEY",
            "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_TITLE",
        }
        self.assertEqual(
            set(module._BASELINE_WORKSPACE_DIAGNOSTIC_CODES),
            expected_codes,
        )
        trace_id = "trace-" + ("b" * 32)
        policy_hash = "a" * 64
        body = {
            "permissions": {"view": True, "create": True},
            "items": [],
            "impacts": [],
            "policies": [
                {
                    "globalId": module.DOCUMENT_BASELINE_POLICY_ID,
                    "version": module.DOCUMENT_BASELINE_POLICY_VERSION,
                    "snapshotHash": policy_hash,
                    "key": module.BASELINE_POLICY_KEY,
                    "title": (
                        "Synthetic P5-03 document baseline policy version"
                    ),
                }
            ],
        }

        self.assertIsNone(
            module.validate_initial_document_baseline_workspace(
                module.HttpResult(
                    status=200,
                    headers=Mock(),
                    body=body,
                    trace_id=trace_id,
                ),
                expected_policy_hash=policy_hash,
            )
        )

        cases = (
            ("P503_RUNTIME_BASELINE_WORKSPACE_HTTP", 500, body),
            ("P503_RUNTIME_BASELINE_WORKSPACE_BODY_SHAPE", 200, []),
            (
                "P503_RUNTIME_BASELINE_WORKSPACE_PERMISSIONS_SHAPE",
                200,
                {**body, "permissions": {"view": True}},
            ),
            (
                "P503_RUNTIME_BASELINE_WORKSPACE_VIEW_PERMISSION",
                200,
                {**body, "permissions": {"view": False, "create": True}},
            ),
            (
                "P503_RUNTIME_BASELINE_WORKSPACE_CREATE_PERMISSION",
                200,
                {**body, "permissions": {"view": True, "create": False}},
            ),
            (
                "P503_RUNTIME_BASELINE_WORKSPACE_ITEMS_EMPTY",
                200,
                {**body, "items": [{}]},
            ),
            (
                "P503_RUNTIME_BASELINE_WORKSPACE_IMPACTS_EMPTY",
                200,
                {**body, "impacts": [{}]},
            ),
            (
                "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_CARDINALITY",
                200,
                {**body, "policies": []},
            ),
            (
                "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_SHAPE",
                200,
                {**body, "policies": [{**body["policies"][0], "extra": 1}]},
            ),
            (
                "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_IDENTITY",
                200,
                {
                    **body,
                    "policies": [
                        {
                            **body["policies"][0],
                            "globalId": module.PROJECT_TEMPLATE_ID,
                        }
                    ],
                },
            ),
            (
                "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_VERSION",
                200,
                {**body, "policies": [{**body["policies"][0], "version": 2}]},
            ),
            (
                "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_HASH",
                200,
                {
                    **body,
                    "policies": [
                        {**body["policies"][0], "snapshotHash": "c" * 64}
                    ],
                },
            ),
            (
                "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_KEY",
                200,
                {**body, "policies": [{**body["policies"][0], "key": "other"}]},
            ),
            (
                "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_TITLE",
                200,
                {
                    **body,
                    "policies": [{**body["policies"][0], "title": "Other"}],
                },
            ),
        )
        for expected_code, status, candidate_body in cases:
            with self.subTest(code=expected_code):
                with self.assertRaises(module.RuntimeSubstageFailure) as failure:
                    module.validate_initial_document_baseline_workspace(
                        module.HttpResult(
                            status=status,
                            headers=Mock(),
                            body=candidate_body,
                            trace_id=trace_id,
                        ),
                        expected_policy_hash=policy_hash,
                    )
                self.assertEqual(failure.exception.code, expected_code)
                self.assertEqual(failure.exception.trace_id, trace_id)
                diagnostic = module.runtime_substage_diagnostic(
                    failure.exception
                )
                self.assertEqual(
                    diagnostic,
                    (
                        f"[diagnostic_code={expected_code}; "
                        "exc_type=RuntimeSubstageFailure; "
                        f"trace_id={trace_id}]"
                    ),
                )
                for forbidden in (
                    "response",
                    "exception",
                    "traceback",
                    "request",
                    "cookie",
                    "credential",
                ):
                    with self.subTest(code=expected_code, forbidden=forbidden):
                        self.assertNotIn(forbidden, diagnostic.casefold())

        with self.assertRaises(module.RuntimeSubstageFailure) as failure:
            module.validate_initial_document_baseline_workspace(
                module.HttpResult(
                    status=200,
                    headers=Mock(),
                    body={
                        **body,
                        "permissions": {"view": True, "create": False},
                        "policies": [],
                    },
                    trace_id=trace_id,
                ),
                expected_policy_hash=policy_hash,
            )
        self.assertEqual(
            failure.exception.code,
            "P503_RUNTIME_BASELINE_WORKSPACE_POLICY_CARDINALITY",
        )

    def test_post_workspace_verifier_stage_diagnostic_is_closed_and_exact(
        self,
    ) -> None:
        module = self.module
        expected_codes = {
            "P503_VERIFIER_POST_WORKSPACE_PAYLOAD_BUILD",
            "P503_VERIFIER_POST_WORKSPACE_CSRF_GUARD",
            "P503_BASELINE_CREATE_CLIENT_HTTP",
            "P503_BASELINE_CREATE_RESPONSE_SHAPE",
            "P503_BASELINE_CREATE_RESPONSE_CONTRACT",
            "P503_VERIFIER_POST_WORKSPACE_BASELINE_REPLAY",
            "P503_VERIFIER_POST_WORKSPACE_IDEMPOTENCY_CONFLICT",
            "P503_VERIFIER_POST_WORKSPACE_GATE_LOOKUP",
            "P503_VERIFIER_POST_WORKSPACE_GATE_FREEZE",
            "P503_VERIFIER_POST_WORKSPACE_EVIDENCE_ATTACH",
            "P503_VERIFIER_POST_WORKSPACE_DEPENDENCY_QUERY",
            "P503_VERIFIER_POST_WORKSPACE_REVIEW_POLICY",
            "P503_VERIFIER_POST_WORKSPACE_REVIEW_START",
            "P503_VERIFIER_POST_WORKSPACE_SUCCESSOR_CHECKOUT",
            "P503_VERIFIER_POST_WORKSPACE_SUCCESSOR_CREATE",
            "P503_VERIFIER_POST_WORKSPACE_IMPACT_QUERY",
            "P503_VERIFIER_POST_WORKSPACE_REVIEW_REFRESH",
            "P503_VERIFIER_POST_WORKSPACE_UNREGISTERED_SUCCESSOR_CREATE",
            "P503_VERIFIER_POST_WORKSPACE_UNREGISTERED_WORKSPACE_QUERY",
            "P503_VERIFIER_POST_WORKSPACE_UNREGISTERED_REVIEW_QUERY",
            "P503_VERIFIER_POST_WORKSPACE_UNREGISTERED_INVARIANTS",
            "P503_VERIFIER_POST_WORKSPACE_RESULT_BUILD",
        }
        self.assertEqual(
            set(module._POST_WORKSPACE_VERIFIER_STAGE_CODES),
            expected_codes,
        )
        trace_id = "trace-" + ("f" * 32)
        code = "P503_BASELINE_CREATE_CLIENT_HTTP"
        secret_text = "cookie=post-workspace-secret"

        @module.post_workspace_verifier_diagnostics
        def fail_after_checkpoint() -> None:
            module.post_workspace_verifier_stage(code, trace_id)
            raise AssertionError(secret_text)

        with self.assertRaises(module.RuntimeSubstageFailure) as failure:
            fail_after_checkpoint()
        self.assertEqual(failure.exception.code, code)
        self.assertEqual(failure.exception.exception_type, "AssertionError")
        self.assertEqual(failure.exception.trace_id, trace_id)
        diagnostic = module.runtime_substage_diagnostic(failure.exception)
        self.assertEqual(
            diagnostic,
            (
                f"[diagnostic_code={code}; "
                "exc_type=AssertionError; "
                f"trace_id={trace_id}]"
            ),
        )
        for forbidden in ("cookie", "secret", secret_text):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden.casefold(), diagnostic.casefold())

        @module.post_workspace_verifier_diagnostics
        def fail_without_checkpoint() -> None:
            raise KeyError(secret_text)

        with self.assertRaises(KeyError) as original:
            fail_without_checkpoint()
        self.assertEqual(original.exception.args, (secret_text,))
        with self.assertRaises(ValueError):
            module.post_workspace_verifier_stage("NOT_ALLOWLISTED", trace_id)
        with self.assertRaises(ValueError):
            module.post_workspace_verifier_stage(code, "trace-invalid")

    def test_post_workspace_verifier_stage_checkpoints_cover_exact_flow(self) -> None:
        source = Path(self.module.__file__).read_text(encoding="utf-8")
        function_start = source.index("def verify_document_baseline_runtime(")
        function_end = source.index("\ndef run_fresh(", function_start)
        function = source[function_start:function_end]
        checkpoints = tuple(
            code
            for code in sorted(self.module._POST_WORKSPACE_VERIFIER_STAGE_CODES)
            if code != "P503_VERIFIER_POST_WORKSPACE_RESULT_BUILD"
        )
        for code in checkpoints:
            with self.subTest(code=code):
                self.assertIn(f'"{code}"', function)
        self.assertIn(
            'stage_code = "P503_VERIFIER_POST_WORKSPACE_RESULT_BUILD"',
            function,
        )
        self.assertEqual(function.count("post_workspace_verifier_stage("), 34)

    def test_repaired_flow_does_not_activate_evidence_attach_diagnostic(self) -> None:
        source = Path(self.module.__file__).read_text(encoding="utf-8")
        function_start = source.index("def verify_document_baseline_runtime(")
        function_end = source.index("\ndef run_fresh(", function_start)
        function = source[function_start:function_end]
        self.assertNotIn(
            "gate_evidence_attach_diagnostic=True",
            function,
        )
        self.assertNotIn("baseline_create_diagnostic=True", function)

    def test_successor_checkout_uses_new_lock_aggregate_version(self) -> None:
        source = Path(self.module.__file__).read_text(encoding="utf-8")
        function_start = source.index("def verify_document_baseline_runtime(")
        function_end = source.index("\ndef run_fresh(", function_start)
        function = source[function_start:function_end]

        self.assertIn('lock.get("version") == 1', function)
        self.assertEqual(function.count("lock_version=1"), 2)
        self.assertNotIn("lock_version=2", function)

    def test_runtime_schema_inventory_is_exact_and_additive(self) -> None:
        self.assertEqual(
            set(self.module.DOCUMENT_DOCTYPES),
            {
                "NPI Document Policy",
                "NPI Document Policy Version",
                "NPI Controlled Document",
                "NPI Document Revision",
                "NPI Document Revision File",
                "NPI Document Relationship",
                "NPI Document Lock Event",
                "NPI Document Command Idempotency",
                "NPI Document Share Grant",
                "NPI Document Release Policy",
                "NPI Document Release Policy Version",
                "NPI Document Revision Lifecycle",
                "NPI Document Review Cycle",
                "NPI Document Confirmation",
                "NPI Document Lifecycle Event",
                "NPI Document Baseline Policy",
                "NPI Document Baseline Policy Version",
                "NPI Document Baseline",
                "NPI Document Baseline Member",
                "NPI Baseline Command Idempotency",
                "NPI Baseline Gate Dependency",
                "NPI Baseline Impact Event",
            },
        )
        self.assertIn("frappe.db.table_exists(doctype)", self.source)
        self.assertIn("frappe.get_meta(doctype, cached=False)", self.source)
        schema_inventory = self.source.split(
            "required_fields = {",
            maxsplit=1,
        )[1].split("for doctype in DOCUMENT_DOCTYPES:", maxsplit=1)[0]
        document_receipt = schema_inventory.split(
            '"NPI Document Command Idempotency": {',
            maxsplit=1,
        )[1].split("},", maxsplit=1)[0]
        baseline_receipt = schema_inventory.split(
            '"NPI Baseline Command Idempotency": {',
            maxsplit=1,
        )[1].split("},", maxsplit=1)[0]
        self.assertIn('"response_snapshot"', document_receipt)
        self.assertIn('"response_sealed"', document_receipt)
        self.assertNotIn('"response_payload"', document_receipt)
        self.assertIn('"response_payload"', baseline_receipt)
        self.assertIn('"sealed"', baseline_receipt)
        self.assertNotIn("drop table", self.source.casefold())
        self.assertNotIn("truncate table", self.source.casefold())

    def test_http_failure_diagnostics_are_bounded_and_sanitized(self) -> None:
        module = self.module
        result = module.HttpResult(
            status=500,
            headers=Mock(),
            body={
                "exc_type": "DataError",
                "_server_messages": json.dumps(
                    [
                        json.dumps(
                            {
                                "message": (
                                    "<strong>Incorrect datetime value</strong> "
                                    "for column published_at"
                                )
                            }
                        )
                    ]
                ),
                "exc": "traceback contains controlled-fixture-password",
                "exception": "database exception contains a request payload",
                "cookies": "sid=synthetic-secret",
                "request": {"password": "controlled-fixture-password"},
            },
        )
        detail = module.sanitized_http_failure(result)
        self.assertEqual(
            detail,
            (
                " [exc_type=DataError; message=Incorrect datetime value "
                "for column published_at]"
            ),
        )
        for forbidden in (
            "traceback",
            "payload",
            "cookie",
            "controlled-fixture-password",
            "sid=",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, detail)
        with self.assertRaisesRegex(
            RuntimeError,
            (
                r"Document policy publication returned HTTP 500 "
                r"\[exc_type=DataError; message=Incorrect datetime value "
                r"for column published_at\]"
            ),
        ):
            module.require_http_status(
                result,
                {200},
                "Document policy publication",
            )

        sensitive = module.HttpResult(
            status=500,
            headers=Mock(),
            body={
                "exc_type": "Invalid Type With Spaces",
                "message": "Authorization token=synthetic-secret",
            },
        )
        self.assertEqual(module.sanitized_http_failure(sensitive), "")

    def test_http_failure_diagnostic_message_is_length_bounded(self) -> None:
        result = self.module.HttpResult(
            status=500,
            headers=Mock(),
            body={"message": "x" * 500},
        )
        detail = self.module.sanitized_http_failure(result)
        self.assertEqual(detail, f" [message={'x' * 240}]")

    def test_document_workspace_uses_exact_sanitized_bff_log_diagnostic(
        self,
    ) -> None:
        module = self.module
        trace_id = module.fixture_trace_id(module.DOCUMENT_CHECK_OUT_KEY)
        with tempfile.TemporaryDirectory() as temporary_directory:
            bench_path = Path(temporary_directory)
            log_directory = bench_path / "logs"
            log_directory.mkdir()
            (log_directory / "npi_core.log").write_text(
                "\n".join(
                    (
                        json.dumps(
                            {
                                "code": "UNEXPECTED_BFF_EXCEPTION",
                                "exceptionType": "WrongTraceError",
                                "traceId": "trace-" + ("0" * 32),
                            }
                        ),
                        json.dumps(
                            {
                                "code": "UNEXPECTED_BFF_EXCEPTION",
                                "exceptionType": "Unsafe Type",
                                "traceId": trace_id,
                            }
                        ),
                        (
                            "2026-07-31 ERROR npi_core "
                            + json.dumps(
                                {
                                    "code": "UNEXPECTED_BFF_EXCEPTION",
                                    "exceptionType": "ValidationError",
                                    "traceId": trace_id,
                                },
                                separators=(",", ":"),
                                sort_keys=True,
                            )
                        ),
                        (
                            "request payload password="
                            "controlled-fixture-password"
                        ),
                    )
                ),
                encoding="utf-8",
            )
            result = module.HttpResult(
                status=500,
                headers=Mock(),
                body={
                    "detail": "The server could not complete the request.",
                    "request": {
                        "password": "controlled-fixture-password",
                    },
                },
                request_id=module.fixture_request_id(
                    module.DOCUMENT_CHECK_OUT_KEY
                ),
                trace_id=trace_id,
            )
            with (
                patch.object(module, "BENCH_PATH", bench_path),
                self.assertRaises(RuntimeError) as raised,
            ):
                module.validate_document_workspace(
                    result,
                    project_id=module.fixture_id("project"),
                    expected_document_id=module.fixture_id("document"),
                )
        self.assertEqual(
            str(raised.exception),
            (
                "Document workspace returned HTTP 500 "
                "[diagnostic_code=UNEXPECTED_BFF_EXCEPTION; "
                "exc_type=ValidationError; "
                f"trace_id={trace_id}]"
            ),
        )
        for forbidden in (
            "payload",
            "password",
            "controlled-fixture-password",
            "WrongTraceError",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, str(raised.exception))

    def test_document_workspace_emits_no_body_diagnostic_without_safe_record(
        self,
    ) -> None:
        module = self.module
        trace_id = module.fixture_trace_id(module.DOCUMENT_CHECK_OUT_KEY)
        result = module.HttpResult(
            status=500,
            headers=Mock(),
            body={
                "exc_type": "ValidationError",
                "message": "raw validation text",
                "request": {
                    "password": "controlled-fixture-password",
                },
            },
            request_id=module.fixture_request_id(module.DOCUMENT_CHECK_OUT_KEY),
            trace_id=trace_id,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            bench_path = Path(temporary_directory)
            with (
                patch.object(module, "BENCH_PATH", bench_path),
                self.assertRaises(RuntimeError) as raised,
            ):
                module.validate_document_workspace(
                    result,
                    project_id=module.fixture_id("project"),
                    expected_document_id=module.fixture_id("document"),
                )
        self.assertEqual(
            str(raised.exception),
            "Document workspace returned HTTP 500",
        )
        for forbidden in (
            "ValidationError",
            "raw validation text",
            "password",
            "controlled-fixture-password",
            trace_id,
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, str(raised.exception))

    def test_checkout_stage_diagnostic_is_allowlisted_and_preferred(
        self,
    ) -> None:
        module = self.module
        expected_codes = {
            "DOCUMENT_CHECKOUT_RECEIPT_INSERT",
            "DOCUMENT_CHECKOUT_LOCK_EVENT_INSERT",
            "DOCUMENT_CHECKOUT_PROJECTION_SAVE",
            "DOCUMENT_CHECKOUT_AUDIT_APPEND",
            "DOCUMENT_CHECKOUT_RESPONSE_BUILD",
            "DOCUMENT_CHECKOUT_RECEIPT_SEAL",
        }
        self.assertEqual(module._CHECKOUT_STAGE_DIAGNOSTIC_CODES, expected_codes)
        trace_id = module.fixture_trace_id(module.DOCUMENT_CHECK_OUT_KEY)
        stage_code = "DOCUMENT_CHECKOUT_LOCK_EVENT_INSERT"
        with tempfile.TemporaryDirectory() as temporary_directory:
            bench_path = Path(temporary_directory)
            log_directory = bench_path / "logs"
            log_directory.mkdir()
            (log_directory / "npi_core.log").write_text(
                "\n".join(
                    (
                        json.dumps(
                            {
                                "code": stage_code,
                                "exceptionType": "ValidationError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "code": "UNREVIEWED_CHECKOUT_STAGE",
                                "exceptionType": "UnsafeError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "code": ["DOCUMENT_CHECKOUT_RECEIPT_SEAL"],
                                "exceptionType": "UnhashableCodeError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "code": "UNEXPECTED_BFF_EXCEPTION",
                                "exceptionType": "GenericError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    )
                ),
                encoding="utf-8",
            )
            result = module.HttpResult(
                status=500,
                headers=Mock(),
                body={
                    "exc_type": "BodyError",
                    "message": "server detail must not be emitted",
                    "request": {
                        "password": "controlled-fixture-password",
                    },
                },
                request_id=module.fixture_request_id(
                    module.DOCUMENT_CHECK_OUT_KEY
                ),
                trace_id=trace_id,
            )
            with patch.object(module, "BENCH_PATH", bench_path):
                detail = module.sanitized_http_failure(result)
        self.assertEqual(
            detail,
            (
                f" [diagnostic_code={stage_code}; "
                "exc_type=ValidationError; "
                f"trace_id={trace_id}]"
            ),
        )
        for forbidden in (
            "BodyError",
            "GenericError",
            "UnsafeError",
            "UnhashableCodeError",
            "server detail",
            "password",
            "controlled-fixture-password",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, detail)

    def test_revision_stage_diagnostic_is_allowlisted_and_preferred(
        self,
    ) -> None:
        module = self.module
        expected_codes = {
            "DOCUMENT_REVISION_RECEIPT_INSERT",
            "DOCUMENT_REVISION_PRIVATE_FILE_SAVE",
            "DOCUMENT_REVISION_FILE_REVISION_INSERT",
            "DOCUMENT_REVISION_DOMAIN_APPEND",
            "DOCUMENT_REVISION_RECORD_INSERT",
            "DOCUMENT_REVISION_FILE_ASSOCIATION_INSERT",
            "DOCUMENT_REVISION_PROJECTION_SAVE",
            "DOCUMENT_REVISION_AUDIT_APPEND",
            "DOCUMENT_REVISION_RESPONSE_BUILD",
            "DOCUMENT_REVISION_RECEIPT_SEAL",
        }
        self.assertEqual(module._REVISION_STAGE_DIAGNOSTIC_CODES, expected_codes)
        trace_id = module.fixture_trace_id(module.DOCUMENT_REVISION_KEY)
        stage_code = "DOCUMENT_REVISION_PRIVATE_FILE_SAVE"
        with tempfile.TemporaryDirectory() as temporary_directory:
            bench_path = Path(temporary_directory)
            log_directory = bench_path / "logs"
            log_directory.mkdir()
            (log_directory / "npi_core.log").write_text(
                "\n".join(
                    (
                        json.dumps(
                            {
                                "code": stage_code,
                                "exceptionType": "PdfStreamError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "code": "UNREVIEWED_REVISION_STAGE",
                                "exceptionType": "UnsafeError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "code": "UNEXPECTED_BFF_EXCEPTION",
                                "exceptionType": "GenericError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    )
                ),
                encoding="utf-8",
            )
            result = module.HttpResult(
                status=500,
                headers=Mock(),
                body={
                    "exc_type": "BodyError",
                    "message": "raw PDF parser detail must not be emitted",
                    "request": {
                        "cookie": "controlled-fixture-cookie",
                    },
                },
                request_id=module.fixture_request_id(module.DOCUMENT_REVISION_KEY),
                trace_id=trace_id,
            )
            with patch.object(module, "BENCH_PATH", bench_path):
                detail = module.sanitized_http_failure(result)
        self.assertEqual(
            detail,
            (
                f" [diagnostic_code={stage_code}; "
                "exc_type=PdfStreamError; "
                f"trace_id={trace_id}]"
            ),
        )
        for forbidden in (
            "BodyError",
            "GenericError",
            "UnsafeError",
            "raw PDF parser detail",
            "cookie",
            "controlled-fixture-cookie",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, detail)

    def test_projection_validation_substage_is_closed_and_preferred(
        self,
    ) -> None:
        module = self.module
        expected_codes = {
            "DOCUMENT_CHECKOUT_PROJECTION_NORMALIZE_INPUT",
            "DOCUMENT_CHECKOUT_PROJECTION_IMMUTABLE_IDENTITY",
            "DOCUMENT_CHECKOUT_PROJECTION_POLICY_IDENTITY",
            "DOCUMENT_CHECKOUT_PROJECTION_DOMAIN_RECONSTRUCTION",
            "DOCUMENT_CHECKOUT_PROJECTION_NORMALIZE_IDENTITY",
            "DOCUMENT_CHECKOUT_PROJECTION_VERSION",
            "DOCUMENT_CHECKOUT_PROJECTION_REVISION",
            "DOCUMENT_CHECKOUT_PROJECTION_LOCK",
            "DOCUMENT_CHECKOUT_PROJECTION_NORMALIZE_PROJECTION",
            "DOCUMENT_CHECKOUT_PROJECTION_COMMAND_GUARD",
            "DOCUMENT_CHECKOUT_PROJECTION_FRAPPE_STANDARD_VALIDATION",
            "DOCUMENT_CHECKOUT_PROJECTION_POST_SAVE_HOOK",
            "DOCUMENT_CHECKOUT_PROJECTION_SAVE_LIFECYCLE",
        }
        self.assertEqual(
            module._PROJECTION_VALIDATION_DIAGNOSTIC_CODES,
            expected_codes,
        )
        trace_id = module.fixture_trace_id(module.DOCUMENT_CHECK_OUT_KEY)
        substage_code = "DOCUMENT_CHECKOUT_PROJECTION_LOCK"
        with tempfile.TemporaryDirectory() as temporary_directory:
            bench_path = Path(temporary_directory)
            log_directory = bench_path / "logs"
            log_directory.mkdir()
            (log_directory / "npi_core.log").write_text(
                "\n".join(
                    (
                        json.dumps(
                            {
                                "code": substage_code,
                                "exceptionType": "ValidationError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "code": "DOCUMENT_CHECKOUT_PROJECTION_SAVE",
                                "exceptionType": "ValidationError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "code": "UNEXPECTED_BFF_EXCEPTION",
                                "exceptionType": "ValidationError",
                                "traceId": trace_id,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    )
                ),
                encoding="utf-8",
            )
            result = module.HttpResult(
                status=500,
                headers=Mock(),
                body={
                    "message": "raw validation detail must not be emitted",
                    "request": {
                        "password": "controlled-fixture-password",
                    },
                },
                request_id=module.fixture_request_id(
                    module.DOCUMENT_CHECK_OUT_KEY
                ),
                trace_id=trace_id,
            )
            with patch.object(module, "BENCH_PATH", bench_path):
                detail = module.sanitized_http_failure(result)
        self.assertEqual(
            detail,
            (
                f" [diagnostic_code={substage_code}; "
                "exc_type=ValidationError; "
                f"trace_id={trace_id}]"
            ),
        )
        for forbidden in (
            "raw validation detail",
            "password",
            "controlled-fixture-password",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, detail)

    def test_npi_request_preserves_deterministic_diagnostic_identity(
        self,
    ) -> None:
        module = self.module
        request_id = module.fixture_request_id(module.DOCUMENT_CHECK_OUT_KEY)
        trace_id = module.fixture_trace_id(module.DOCUMENT_CHECK_OUT_KEY)
        response = module.HttpResult(
            status=500,
            headers={
                "X-Request-ID": request_id,
                "Cache-Control": "private, no-store",
            },
            body={},
        )
        with patch.object(module, "request", return_value=response) as request_call:
            result = module.npi_request(
                Mock(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/example/documents/example:check-out",
                method="POST",
                payload={"expectedDocumentVersion": 1},
                csrf_token="csrf-" + ("a" * 48),
                idempotency_key=module.DOCUMENT_CHECK_OUT_KEY,
            )
        self.assertEqual(result.request_id, request_id)
        self.assertEqual(result.trace_id, trace_id)
        self.assertNotIn(
            module._BASELINE_CREATE_DIAGNOSTIC_HEADER,
            request_call.call_args.kwargs["request_headers"],
        )

        baseline_key = module.DOCUMENT_BASELINE_KEY
        baseline_request_id = module.fixture_request_id(baseline_key)
        diagnostic_response = module.HttpResult(
            status=500,
            headers={
                "X-Request-ID": baseline_request_id,
                "Cache-Control": "private, no-store",
            },
            body={},
        )
        with patch.object(
            module,
            "request",
            return_value=diagnostic_response,
        ) as diagnostic_call:
            module.npi_request(
                Mock(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/example/document-baselines",
                method="POST",
                payload={},
                csrf_token="csrf-" + ("a" * 48),
                idempotency_key=baseline_key,
                baseline_create_diagnostic=True,
            )
        self.assertEqual(
            diagnostic_call.call_args.kwargs["request_headers"].get(
                module._BASELINE_CREATE_DIAGNOSTIC_HEADER
            ),
            module._BASELINE_CREATE_DIAGNOSTIC_SCOPE,
        )

        attach_key = module.GATE_BASELINE_ATTACH_KEY
        attach_response = module.HttpResult(
            status=500,
            headers={
                "X-Request-ID": module.fixture_request_id(attach_key),
                "Cache-Control": "private, no-store",
            },
            body={},
        )
        with patch.object(
            module,
            "request",
            return_value=attach_response,
        ) as attach_call:
            module.npi_request(
                Mock(),
                "http://127.0.0.1:8003",
                "/api/npi/v1/projects/example/gates/example/requirements/x/evidence",
                method="POST",
                payload={},
                csrf_token="csrf-" + ("a" * 48),
                idempotency_key=attach_key,
                gate_evidence_attach_diagnostic=True,
            )
        self.assertEqual(
            attach_call.call_args.kwargs["request_headers"].get(
                module._GATE_EVIDENCE_ATTACH_DIAGNOSTIC_HEADER
            ),
            module._GATE_EVIDENCE_ATTACH_DIAGNOSTIC_SCOPE,
        )

    def test_baseline_create_server_diagnostic_precedes_client_http_code(
        self,
    ) -> None:
        module = self.module
        expected_codes = {
            "P503_BASELINE_CREATE_COMMAND_CONTEXT",
            "P503_BASELINE_CREATE_INPUT_PARSE",
            "P503_BASELINE_CREATE_PROJECT_LOCK",
            "P503_BASELINE_CREATE_MEMBERSHIP_AUTHORITY",
            "P503_BASELINE_CREATE_POLICY_LOAD",
            "P503_BASELINE_CREATE_IDEMPOTENCY_REPLAY",
            "P503_BASELINE_CREATE_MEMBER_RESOLVE",
            "P503_BASELINE_CREATE_MEMBER_PRECONDITION_SET",
            "P503_BASELINE_CREATE_MEMBER_RECORD_LOAD",
            "P503_BASELINE_CREATE_MEMBER_RELEASE_STATE",
            "P503_BASELINE_CREATE_MEMBER_REVIEW_LOAD",
            "P503_BASELINE_CREATE_MEMBER_RELEASE_LINEAGE",
            "P503_BASELINE_CREATE_MEMBER_PROJECT_SCOPE",
            "P503_BASELINE_CREATE_MEMBER_DOMAIN_BUILD",
            "P503_BASELINE_CREATE_MEMBER_FILE_QUERY",
            "P503_BASELINE_CREATE_MEMBER_FILE_ASSOCIATION_LOAD",
            "P503_BASELINE_CREATE_MEMBER_FILE_CARDINALITY",
            "P503_BASELINE_CREATE_MEMBER_FILE_LOAD",
            "P503_BASELINE_CREATE_MEMBER_FILE_INTEGRITY",
            "P503_BASELINE_CREATE_DOMAIN_BUILD",
            "P503_BASELINE_CREATE_RECEIPT_INSERT",
            "P503_BASELINE_CREATE_BASELINE_INSERT",
            "P503_BASELINE_CREATE_MEMBER_INSERT",
            "P503_BASELINE_CREATE_AUDIT_APPEND",
            "P503_BASELINE_CREATE_RESPONSE_BUILD",
            "P503_BASELINE_CREATE_RECEIPT_SEAL",
        }
        self.assertEqual(
            module._BASELINE_CREATE_SERVER_DIAGNOSTIC_CODES,
            expected_codes,
        )
        self.assertEqual(
            module._BASELINE_CREATE_VERIFIER_DIAGNOSTIC_CODES,
            {
                "P503_BASELINE_CREATE_CLIENT_HTTP",
                "P503_BASELINE_CREATE_RESPONSE_SHAPE",
                "P503_BASELINE_CREATE_RESPONSE_CONTRACT",
                "P503_BASELINE_CREATE_RESPONSE_PROJECT_IDENTITY",
                "P503_BASELINE_CREATE_RESPONSE_IDEMPOTENCY_REPLAY_HEADER",
                "P503_BASELINE_CREATE_RESPONSE_BASELINE_SHAPE",
                "P503_BASELINE_CREATE_RESPONSE_VERSION",
                "P503_BASELINE_CREATE_RESPONSE_CREATOR",
                "P503_BASELINE_CREATE_RESPONSE_GLOBAL_IDENTITY",
                "P503_BASELINE_CREATE_RESPONSE_SNAPSHOT_HASH",
                "P503_BASELINE_CREATE_RESPONSE_POLICY_IDENTITY",
                "P503_BASELINE_CREATE_RESPONSE_POLICY_VERSION",
                "P503_BASELINE_CREATE_RESPONSE_POLICY_HASH",
                "P503_BASELINE_CREATE_RESPONSE_MEMBER_CARDINALITY",
                "P503_BASELINE_CREATE_RESPONSE_REVISION_IDENTITY",
                "P503_BASELINE_CREATE_RESPONSE_REVISION_HASH",
                "P503_BASELINE_CREATE_RESPONSE_LIFECYCLE_VERSION",
                "P503_BASELINE_CREATE_RESPONSE_RELEASE_SNAPSHOT_HASH",
                "P503_BASELINE_CREATE_RESPONSE_FILE_CARDINALITY",
                "P503_BASELINE_CREATE_RESPONSE_SCAN_STATE",
                "P503_BASELINE_CREATE_RESPONSE_PRIVATE_PATH_EXCLUSION",
                "P503_BASELINE_CREATE_RESPONSE_URL_EXCLUSION",
            },
        )
        trace_id = module.fixture_trace_id(module.DOCUMENT_BASELINE_KEY)
        server_code = "P503_BASELINE_CREATE_BASELINE_INSERT"
        safe_record = json.dumps(
            {
                "code": server_code,
                "exceptionType": "ValidationError",
                "traceId": trace_id,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        result = module.HttpResult(
            status=500,
            headers=Mock(),
            body={"response": "must-not-be-emitted"},
            trace_id=trace_id,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            bench_path = Path(temporary_directory)
            log_directory = bench_path / "logs"
            log_directory.mkdir()
            (log_directory / "npi_core.log").write_text(
                safe_record,
                encoding="utf-8",
            )
            with (
                patch.object(module, "BENCH_PATH", bench_path),
                self.assertRaises(module.RuntimeSubstageFailure) as failure,
            ):
                module.require_baseline_create_http(result)
        self.assertEqual(failure.exception.code, server_code)
        self.assertEqual(failure.exception.exception_type, "ValidationError")
        self.assertEqual(failure.exception.trace_id, trace_id)
        diagnostic = module.runtime_substage_diagnostic(failure.exception)
        self.assertEqual(
            diagnostic,
            (
                f"[diagnostic_code={server_code}; "
                "exc_type=ValidationError; "
                f"trace_id={trace_id}]"
            ),
        )
        for forbidden in (
            "response",
            "must-not-be-emitted",
            "request",
            "cookie",
            "credential",
            "traceback",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, diagnostic.casefold())

        with self.assertRaises(module.RuntimeSubstageFailure) as client_failure:
            module.require_baseline_create_http(
                module.HttpResult(
                    status=500,
                    headers=Mock(),
                    body={},
                    trace_id=trace_id,
                )
            )
        self.assertEqual(
            client_failure.exception.code,
            "P503_BASELINE_CREATE_CLIENT_HTTP",
        )

    def test_gate_evidence_attach_diagnostic_is_exact_and_closed(self) -> None:
        module = self.module
        server_codes = {
            "P503_GATE_EVIDENCE_ATTACH_COMMAND_CONTEXT",
            "P503_GATE_EVIDENCE_ATTACH_INPUT_PARSE",
            "P503_GATE_EVIDENCE_ATTACH_PROJECT_LOCK",
            "P503_GATE_EVIDENCE_ATTACH_GATE_LOCK",
            "P503_GATE_EVIDENCE_ATTACH_IDEMPOTENCY_REPLAY",
            "P503_GATE_EVIDENCE_ATTACH_PRECONDITION",
            "P503_GATE_EVIDENCE_ATTACH_SOURCE_RESOLVE",
            "P503_GATE_EVIDENCE_ATTACH_RECEIPT_INSERT",
            "P503_GATE_EVIDENCE_ATTACH_REFERENCE_INSERT",
            "P503_GATE_EVIDENCE_ATTACH_DEPENDENCY_INSERT",
            "P503_GATE_EVIDENCE_ATTACH_GATE_SAVE",
            "P503_GATE_EVIDENCE_ATTACH_REVIEW_REFRESH",
            "P503_GATE_EVIDENCE_ATTACH_AUDIT_APPEND",
            "P503_GATE_EVIDENCE_ATTACH_RESPONSE_BUILD",
            "P503_GATE_EVIDENCE_ATTACH_RECEIPT_SEAL",
        }
        verifier_codes = {
            "P503_GATE_EVIDENCE_ATTACH_CLIENT_HTTP",
            "P503_GATE_EVIDENCE_ATTACH_RESPONSE_SHAPE",
            "P503_GATE_EVIDENCE_ATTACH_RESPONSE_GATE_VERSION",
            "P503_GATE_EVIDENCE_ATTACH_RESPONSE_EVIDENCE_CARDINALITY",
            "P503_GATE_EVIDENCE_ATTACH_RESPONSE_IDENTITY",
            "P503_GATE_EVIDENCE_ATTACH_RESPONSE_BASELINE",
            "P503_GATE_EVIDENCE_ATTACH_RESPONSE_URL_EXCLUSION",
        }
        self.assertEqual(
            module._GATE_EVIDENCE_ATTACH_SERVER_DIAGNOSTIC_CODES,
            server_codes,
        )
        self.assertEqual(
            module._GATE_EVIDENCE_ATTACH_VERIFIER_DIAGNOSTIC_CODES,
            verifier_codes,
        )
        trace_id = module.fixture_trace_id(module.GATE_BASELINE_ATTACH_KEY)
        safe_record = json.dumps(
            {
                "code": "P503_GATE_EVIDENCE_ATTACH_DEPENDENCY_INSERT",
                "exceptionType": "ValidationError",
                "traceId": trace_id,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        result = module.HttpResult(
            status=500,
            headers=Mock(),
            body={"response": "must-not-be-emitted"},
            trace_id=trace_id,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            bench_path = Path(temporary_directory)
            log_directory = bench_path / "logs"
            log_directory.mkdir()
            (log_directory / "npi_core.log").write_text(
                safe_record,
                encoding="utf-8",
            )
            with (
                patch.object(module, "BENCH_PATH", bench_path),
                self.assertRaises(module.RuntimeSubstageFailure) as failure,
            ):
                module.require_gate_evidence_attach_http(result)
        self.assertEqual(
            failure.exception.code,
            "P503_GATE_EVIDENCE_ATTACH_DEPENDENCY_INSERT",
        )
        self.assertEqual(failure.exception.exception_type, "ValidationError")
        self.assertEqual(failure.exception.trace_id, trace_id)

    def test_gate_evidence_attach_response_predicates_are_exact(self) -> None:
        module = self.module
        trace_id = module.fixture_trace_id(module.GATE_BASELINE_ATTACH_KEY)
        baseline_id = "6cfd51d9-6e47-4c47-92ae-8a5ca1eff081"
        baseline_hash = "a" * 64
        baseline = {"globalId": baseline_id, "snapshotHash": baseline_hash}
        valid_body = {
            "gate": {"version": 3},
            "requirements": [
                {
                    "evidence": [
                        {
                            "globalId": "2e96f421-5872-4c96-a0dd-718d5c970a21",
                            "kind": "release_baseline",
                            "sourceGlobalId": baseline_id,
                            "revision": 1,
                            "objectHash": baseline_hash,
                            "baseline": baseline,
                        }
                    ]
                }
            ],
        }

        def changed(mutator):
            body = json.loads(json.dumps(valid_body))
            headers = {"Idempotency-Replayed": "false"}
            mutator(body, headers)
            return module.HttpResult(
                status=201,
                headers=headers,
                body=body,
                trace_id=trace_id,
            )

        cases = (
            (
                "P503_GATE_EVIDENCE_ATTACH_RESPONSE_GATE_VERSION",
                lambda body, _headers: body["gate"].update({"version": 2}),
            ),
            (
                "P503_GATE_EVIDENCE_ATTACH_RESPONSE_EVIDENCE_CARDINALITY",
                lambda body, _headers: body.update({"requirements": []}),
            ),
            (
                "P503_GATE_EVIDENCE_ATTACH_RESPONSE_IDENTITY",
                lambda body, _headers: body["requirements"][0]["evidence"][
                    0
                ].update({"revision": 2}),
            ),
            (
                "P503_GATE_EVIDENCE_ATTACH_RESPONSE_BASELINE",
                lambda body, _headers: body["requirements"][0]["evidence"][
                    0
                ].update({"baseline": {}}),
            ),
            (
                "P503_GATE_EVIDENCE_ATTACH_RESPONSE_URL_EXCLUSION",
                lambda body, _headers: body["requirements"][0]["evidence"][
                    0
                ].update({"url": "/private"}),
            ),
        )
        for expected_code, mutator in cases:
            with self.subTest(code=expected_code):
                with self.assertRaises(
                    module.RuntimeSubstageFailure
                ) as failure:
                    module.validate_gate_baseline_attachment(
                        changed(mutator),
                        baseline_id=baseline_id,
                        baseline_hash=baseline_hash,
                        baseline=baseline,
                    )
                self.assertEqual(failure.exception.code, expected_code)

        attached = module.validate_gate_baseline_attachment(
            changed(lambda _body, _headers: None),
            baseline_id=baseline_id,
            baseline_hash=baseline_hash,
            baseline=baseline,
        )
        self.assertEqual(attached, valid_body["requirements"][0]["evidence"][0])

    def test_baseline_create_response_diagnostics_are_shape_then_predicate(
        self,
    ) -> None:
        module = self.module
        trace_id = module.fixture_trace_id(module.DOCUMENT_BASELINE_KEY)
        project_id = "2e96f421-5872-4c96-a0dd-718d5c970a21"
        revision_id = "590b332e-1ec4-44d8-8778-8b84eaf079bc"
        shared = {
            "project_id": project_id,
            "revision_id": revision_id,
            "revision_snapshot_hash": "a" * 64,
            "release_snapshot_hash": "b" * 64,
            "policy_snapshot_hash": "c" * 64,
            "replayed": False,
            "diagnostic": True,
        }
        with self.assertRaises(module.RuntimeSubstageFailure) as shape_failure:
            module.validate_document_baseline_command(
                module.HttpResult(
                    status=201,
                    headers=Mock(),
                    body=[],
                    trace_id=trace_id,
                ),
                **shared,
            )
        self.assertEqual(
            shape_failure.exception.code,
            "P503_BASELINE_CREATE_RESPONSE_SHAPE",
        )

        with self.assertRaises(module.RuntimeSubstageFailure) as contract_failure:
            module.validate_document_baseline_command(
                module.HttpResult(
                    status=201,
                    headers={"Idempotency-Replayed": "false"},
                    body={"projectId": project_id, "baseline": {}},
                    trace_id=trace_id,
                ),
                **shared,
            )
        self.assertEqual(
            contract_failure.exception.code,
            "P503_BASELINE_CREATE_RESPONSE_VERSION",
        )

    def test_baseline_create_response_predicate_ladder_is_exact_and_closed(
        self,
    ) -> None:
        module = self.module
        trace_id = module.fixture_trace_id(module.DOCUMENT_BASELINE_KEY)
        project_id = "2e96f421-5872-4c96-a0dd-718d5c970a21"
        revision_id = "590b332e-1ec4-44d8-8778-8b84eaf079bc"
        revision_hash = "a" * 64
        release_hash = "b" * 64
        policy_hash = "c" * 64
        valid_body = {
            "projectId": project_id,
            "baseline": {
                "version": 1,
                "createdByUserId": module.BASELINE_USER,
                "globalId": "6cfd51d9-6e47-4c47-92ae-8a5ca1eff081",
                "snapshotHash": "d" * 64,
                "policy": {
                    "globalId": module.DOCUMENT_BASELINE_POLICY_ID,
                    "version": module.DOCUMENT_BASELINE_POLICY_VERSION,
                    "snapshotHash": policy_hash,
                },
                "members": [
                    {
                        "revisionGlobalId": revision_id,
                        "revisionSnapshotHash": revision_hash,
                        "lifecycleVersion": 5,
                        "releaseSnapshotHash": release_hash,
                        "files": [{"scanState": "clean"}],
                    }
                ],
            },
        }
        shared = {
            "project_id": project_id,
            "revision_id": revision_id,
            "revision_snapshot_hash": revision_hash,
            "release_snapshot_hash": release_hash,
            "policy_snapshot_hash": policy_hash,
            "replayed": False,
            "diagnostic": True,
        }

        def changed(mutator):
            body = json.loads(json.dumps(valid_body))
            headers = {"Idempotency-Replayed": "false"}
            mutator(body, headers)
            return module.HttpResult(
                status=201,
                headers=headers,
                body=body,
                trace_id=trace_id,
            )

        cases = (
            (
                "P503_BASELINE_CREATE_RESPONSE_PROJECT_IDENTITY",
                lambda body, _headers: body.update({"projectId": "wrong"}),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_IDEMPOTENCY_REPLAY_HEADER",
                lambda _body, headers: headers.update(
                    {"Idempotency-Replayed": "true"}
                ),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_BASELINE_SHAPE",
                lambda body, _headers: body.update({"baseline": []}),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_VERSION",
                lambda body, _headers: body["baseline"].update({"version": 2}),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_CREATOR",
                lambda body, _headers: body["baseline"].update(
                    {"createdByUserId": "wrong"}
                ),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_GLOBAL_IDENTITY",
                lambda body, _headers: body["baseline"].update(
                    {"globalId": "wrong"}
                ),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_SNAPSHOT_HASH",
                lambda body, _headers: body["baseline"].update(
                    {"snapshotHash": "wrong"}
                ),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_POLICY_IDENTITY",
                lambda body, _headers: body["baseline"]["policy"].update(
                    {"globalId": "wrong"}
                ),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_POLICY_VERSION",
                lambda body, _headers: body["baseline"]["policy"].update(
                    {"version": 2}
                ),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_POLICY_HASH",
                lambda body, _headers: body["baseline"]["policy"].update(
                    {"snapshotHash": "wrong"}
                ),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_MEMBER_CARDINALITY",
                lambda body, _headers: body["baseline"].update(
                    {"members": []}
                ),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_REVISION_IDENTITY",
                lambda body, _headers: body["baseline"]["members"][0].update(
                    {"revisionGlobalId": "wrong"}
                ),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_REVISION_HASH",
                lambda body, _headers: body["baseline"]["members"][0].update(
                    {"revisionSnapshotHash": "wrong"}
                ),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_LIFECYCLE_VERSION",
                lambda body, _headers: body["baseline"]["members"][0].update(
                    {"lifecycleVersion": 6}
                ),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_RELEASE_SNAPSHOT_HASH",
                lambda body, _headers: body["baseline"]["members"][0].update(
                    {"releaseSnapshotHash": "wrong"}
                ),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_FILE_CARDINALITY",
                lambda body, _headers: body["baseline"]["members"][0].update(
                    {"files": []}
                ),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_SCAN_STATE",
                lambda body, _headers: body["baseline"]["members"][0][
                    "files"
                ][0].update({"scanState": "pending"}),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_PRIVATE_PATH_EXCLUSION",
                lambda body, _headers: body["baseline"].update(
                    {"privatePath": "/private/files/redacted.pdf"}
                ),
            ),
            (
                "P503_BASELINE_CREATE_RESPONSE_URL_EXCLUSION",
                lambda body, _headers: body["baseline"].update(
                    {"url": "/redacted"}
                ),
            ),
        )
        for expected_code, mutator in cases:
            with self.subTest(code=expected_code):
                with self.assertRaises(
                    module.RuntimeSubstageFailure
                ) as failure:
                    module.validate_document_baseline_command(
                        changed(mutator),
                        **shared,
                    )
                self.assertEqual(failure.exception.code, expected_code)
                diagnostic = module.runtime_substage_diagnostic(
                    failure.exception
                )
                self.assertEqual(
                    diagnostic,
                    (
                        f"[diagnostic_code={expected_code}; "
                        "exc_type=RuntimeSubstageFailure; "
                        f"trace_id={trace_id}]"
                    ),
                )
                for forbidden in (
                    "redacted.pdf",
                    "/redacted",
                    project_id,
                    revision_id,
                    policy_hash,
                    module.BASELINE_USER,
                ):
                    self.assertNotIn(forbidden, diagnostic)

        baseline = module.validate_document_baseline_command(
            changed(lambda _body, _headers: None),
            **shared,
        )
        self.assertEqual(baseline, valid_body["baseline"])

    def test_bff_log_diagnostic_rejects_symlink_and_stale_oversize_tail(
        self,
    ) -> None:
        module = self.module
        trace_id = module.fixture_trace_id(module.DOCUMENT_CHECK_OUT_KEY)
        safe_record = json.dumps(
            {
                "code": "UNEXPECTED_BFF_EXCEPTION",
                "exceptionType": "ValidationError",
                "traceId": trace_id,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bench_path = root / "bench"
            log_directory = bench_path / "logs"
            log_directory.mkdir(parents=True)
            external_log = root / "external.log"
            external_log.write_text(safe_record, encoding="utf-8")
            diagnostic_log = log_directory / "npi_core.log"
            diagnostic_log.symlink_to(external_log)
            with patch.object(module, "BENCH_PATH", bench_path):
                self.assertIsNone(
                    module._sanitized_bff_log_diagnostic(trace_id)
                )
            diagnostic_log.unlink()
            diagnostic_log.write_text(
                safe_record
                + "\n"
                + ("x" * (module._DIAGNOSTIC_LOG_TAIL_LIMIT + 1)),
                encoding="utf-8",
            )
            with patch.object(module, "BENCH_PATH", bench_path):
                self.assertIsNone(
                    module._sanitized_bff_log_diagnostic(trace_id)
                )

    def test_runtime_covers_real_file_and_authorization_boundaries(self) -> None:
        required_fragments = (
            "multipart_revision_request(",
            "observe_document_file_scan",
            "FILE_SCAN_RESULT_FLAG",
            '"scanState"] == "pending"',
            '"scanState") == "clean"',
            "binary_content_request(",
            '"X-Content-Type-Options") == "nosniff"',
            '"Referrer-Policy") == "no-referrer"',
            '"Idempotency-Replayed") == "true"',
            "DOCUMENT_VERSION_CONFLICT",
            "DOCUMENT_UNAVAILABLE",
            "AUTHENTICATION_REQUIRED",
            "DOCUMENT_REVIEW_ASSIGNMENT_UNAVAILABLE",
            "DOCUMENT_REVIEW_STATE_CONFLICT",
            "DOCUMENT_RELEASE_INTEGRITY_BLOCKED",
            "DOCUMENT_RELEASE_ROUTES_DISABLED",
            "create_internal_fixture_user(",
            '"user_type": "System User"',
            '{"role": "NPI API User"}',
            "ensure_document_release_policy(",
            "verify_review_release_runtime(",
            '"set_document_file_content"',
            '"verify_released_file_delete_guard"',
            "DOCUMENT_REVIEW_REJECT_KEY",
            "DOCUMENT_REVIEW_RESUBMIT_KEY",
            "DOCUMENT_REVIEW_APPROVE_KEY",
            "DOCUMENT_RELEASE_KEY",
            "ensure_document_baseline_policy(",
            "verify_document_baseline_runtime(",
            "DOCUMENT_BASELINE_KEY",
            '"evidenceKind": "release_baseline"',
            '"BASELINE_SUCCESSOR_IMPACT"',
            "DOCUMENT_SUCCESSOR_KEY",
            "DOCUMENT_UNREGISTERED_SUCCESSOR_KEY",
            "externalRetrieval",
            "rawPrivateUrlExposed",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.source)
        permission_bypass_token = "ignore_" + "permissions=True"
        self.assertNotIn(permission_bypass_token, self.source)
        self.assertNotIn("allow_guest=True", self.source)
        self.assertNotIn("http://core.whjichen.cn", self.source)

    def test_integrity_fixture_resolves_exact_file_association(self) -> None:
        fixture = self.source.split(
            "def set_document_file_content(",
            maxsplit=1,
        )[1].split("def run_bench_fixture(", maxsplit=1)[0]
        self.assertIn('"NPI Document Revision File"', fixture)
        self.assertIn('"file_document_global_id"', fixture)
        self.assertIn('"file_revision_global_id": file_revision_id', fixture)
        self.assertIn(
            'str(revision.document_global_id)\n'
            '        == str(association.get("file_document_global_id"))',
            fixture,
        )
        self.assertIn(
            'str(revision.sha256) == str(association.get("sha256"))',
            fixture,
        )
        self.assertNotIn(
            "str(revision.document_global_id) == document_id",
            fixture,
        )

    def test_delete_guard_resolves_exact_file_association(self) -> None:
        fixture = self.source.split(
            "def verify_released_file_delete_guard(",
            maxsplit=1,
        )[1].split("def set_document_file_content(", maxsplit=1)[0]
        self.assertIn('"NPI Document Revision File"', fixture)
        self.assertIn('"file_document_global_id"', fixture)
        self.assertIn('"file_revision_global_id": file_revision_id', fixture)
        self.assertIn(
            'str(revision.document_global_id)\n'
            '        == str(association.get("file_document_global_id"))',
            fixture,
        )
        self.assertIn(
            'str(revision.sha256) == str(association.get("sha256"))',
            fixture,
        )
        self.assertIn("int(revision.released or 0) == 1", fixture)
        self.assertNotIn(
            "str(revision.document_global_id) == document_id",
            fixture,
        )

    def test_project_uses_the_disposable_email_owner(self) -> None:
        response = Mock(
            status=201,
            body={
                "project": {
                    "globalId": "20873131-6923-5ad4-bf35-74efdc358224",
                    "version": 1,
                }
            },
        )
        with patch.object(
            self.module,
            "post_project",
            return_value=response,
        ) as post_project:
            self.module.create_project(
                Mock(),
                "http://127.0.0.1:8003",
                "csrf-" + ("a" * 48),
            )
        payload = post_project.call_args.args[2]
        self.assertEqual(payload["ownerUserId"], self.module.OWNER_USER)
        self.assertNotEqual(payload["ownerUserId"], "Administrator")

    def test_internal_owner_is_cleaned_on_success_and_failure(self) -> None:
        module = self.module
        expected = {"fixtureRunId": FIXTURE_RUN_ID}
        for downstream, expected_error in (
            (Mock(return_value=expected), None),
            (Mock(side_effect=RuntimeError("fixture failed")), "fixture failed"),
        ):
            with self.subTest(expected_error=expected_error):
                with (
                    patch.object(module, "verify_fresh_namespace"),
                    patch.object(
                        module,
                        "create_internal_fixture_user",
                    ) as create_user,
                    patch.object(
                        module,
                        "_run_fresh_with_owner",
                        downstream,
                    ),
                    patch.object(
                        module,
                        "delete_disposable_user",
                    ) as delete_user,
                ):
                    if expected_error is None:
                        result = module.run_fresh(
                            Mock(),
                            "http://127.0.0.1:8003",
                            "csrf-" + ("a" * 48),
                            "controlled-fixture-password",
                        )
                        self.assertEqual(
                            result,
                            {
                                **expected,
                                "baselineAuthorityFixtureRetained": True,
                                "ownerFixtureCleaned": True,
                            },
                        )
                    else:
                        with self.assertRaisesRegex(RuntimeError, expected_error):
                            module.run_fresh(
                                Mock(),
                                "http://127.0.0.1:8003",
                                "csrf-" + ("a" * 48),
                                "controlled-fixture-password",
                            )
                self.assertEqual(create_user.call_count, 2)
                self.assertEqual(
                    [call.args[2] for call in create_user.call_args_list],
                    [module.OWNER_USER, module.BASELINE_USER],
                )
                delete_user.assert_called_once()
                self.assertEqual(
                    delete_user.call_args.args[2],
                    module.OWNER_USER,
                )

    def test_replay_requires_the_disposable_owner_to_be_absent(self) -> None:
        owner_still_exists = Mock(status=200)
        with (
            patch.object(
                self.module,
                "request",
                return_value=owner_still_exists,
            ),
            self.assertRaisesRegex(
                RuntimeError,
                "Project owner was not cleaned",
            ),
        ):
            self.module.run_replay(
                Mock(),
                "http://127.0.0.1:8003",
                "csrf-" + ("a" * 48),
                "controlled-fixture-password",
            )

    def test_replay_selects_exact_baseline_revision_from_successor_history(
        self,
    ) -> None:
        revision_id = "66997315-516a-4a5d-800b-0933f70a1e7d"
        histories = [
            {
                "revisionId": "10000000-0000-4000-8000-000000000001",
                "lifecycle": {"state": "draft", "version": 0},
            },
            {
                "revisionId": revision_id,
                "lifecycle": {"state": "released", "version": 5},
            },
            {
                "revisionId": "10000000-0000-4000-8000-000000000002",
                "lifecycle": {"state": "draft", "version": 0},
            },
        ]
        detail = self.module.HttpResult(
            status=200,
            headers={},
            body={"releaseWorkspace": {"revisions": histories}},
        )

        self.assertIs(
            self.module.exact_released_revision_history(detail, revision_id),
            histories[1],
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "exact Document release history is unavailable",
        ):
            self.module.exact_released_revision_history(
                detail,
                "10000000-0000-4000-8000-000000000003",
            )

    def test_runtime_shell_migrates_twice_and_restores_route_switch(self) -> None:
        required_fragments = (
            '"--document-only"',
            "for _migration_attempt in 1 2",
            'npi_p5_01_routes_disabled "${value}"',
            'npi_p5_02_routes_disabled "${value}"',
            'npi_p5_03_routes_disabled "${value}"',
            "run_document_runtime_verifier fresh",
            "run_document_route_probe disabled",
            "run_document_route_probe recovered",
            "run_document_release_route_probe disabled",
            "run_document_release_route_probe recovered",
            "run_document_baseline_route_probe disabled",
            "run_document_baseline_route_probe recovered",
            "run_document_runtime_verifier replay-only",
            "restore_document_route_switch",
            "restore_document_release_route_switch",
            "restore_document_baseline_route_switch",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.shell)
        self.assertIn(
            'document_route_disable_original_state}" != "absent"',
            self.shell,
        )
        self.assertIn(
            'document_release_route_disable_original_state}" != "absent"',
            self.shell,
        )
        self.assertIn(
            'document_baseline_route_disable_original_state}" != "absent"',
            self.shell,
        )

    def test_site_init_preserves_apps_registry_line_boundaries(self) -> None:
        site_init = (ROOT / "scripts" / "init-npi-site.sh").read_text(
            encoding="utf-8"
        )
        required_fragments = (
            'local apps_file="${bench_path}/sites/apps.txt"',
            '[[ -L "${apps_file}" || ! -f "${apps_file}" ]]',
            "Bench application registry must be a physical file: ${apps_file}",
            'tail -c 1 "${apps_file}" | od -An -tx1 | tr -d \'[:space:]\'',
            '!= "0a"',
            'printf \'\\n\' >>"${apps_file}"',
            'grep -Fqx "${application}" "${apps_file}"',
            'printf \'%s\\n\' "${application}" >>"${apps_file}"',
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, site_init)
        self.assertLess(
            site_init.index('printf \'\\n\' >>"${apps_file}"'),
            site_init.index('printf \'%s\\n\' "${application}" >>"${apps_file}"'),
        )

    def test_runtime_uses_only_the_fixed_disposable_site(self) -> None:
        required_fragments = (
            'SITE_NAME = "npi.localhost"',
            'DATABASE_NAME = "npi_one_runtime"',
            'RUNTIME_MARKER = "npi-one-local-runtime-disposable-v1"',
            "frappe.local.site == SITE_NAME",
            "frappe.conf.get(\"npi_runtime_disposable_marker\") == RUNTIME_MARKER",
            "BENCH_PATH.resolve() == BENCH_PATH",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.source)

    def test_manual_ci_lane_uses_the_pinned_disposable_runtime(self) -> None:
        toolchain = dict(
            line.split("=", 1)
            for line in TOOLCHAIN.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        )
        runtime_job = self.workflow.split("\n  document_runtime:\n", 1)[1]
        required_fragments = (
            "if: github.event_name == 'workflow_dispatch'",
            "timeout-minutes: 45",
            f'"frappe-bench=={toolchain["BENCH_EXPECTED_VERSION"]}"',
            f'"uv=={toolchain["UV_EXPECTED_VERSION"]}"',
            'from importlib.metadata import version',
            'version("frappe-bench")',
            'version("uv")',
            f'("{toolchain["BENCH_EXPECTED_VERSION"]}", "{toolchain["UV_EXPECTED_VERSION"]}")',
            f'test "$(yarn --version)" = "{toolchain["YARN_EXPECTED_VERSION"]}"',
            "bash scripts/init-frappe-bench.sh",
            "bash scripts/init-npi-site.sh",
            "bash scripts/verify-frappe-runtime.sh --tooling-only",
            "site=npi.localhost",
            "database=npi_one_runtime",
            "runtime_marker=npi-one-local-runtime-disposable-v1",
            "scope=p5-01-through-p6-04",
            "predecessor_scope=p5-01-through-p5-06",
            "predecessor_command=bash scripts/verify-frappe-runtime.sh --document-only",
            f'frappe_commit={toolchain["FRAPPE_COMMIT"]}',
            "p6-tooling-runtime-${{ github.run_id }}",
            "docker compose down --volumes",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, runtime_job)
        self.assertNotIn("secrets.", runtime_job)
        self.assertNotIn("continue-on-error", runtime_job)
        self.assertNotIn("core.whjichen.cn", runtime_job)
        self.assertNotIn("npm install --global", runtime_job)
        self.assertNotIn("--dangerously-allow-all-scripts", runtime_job)


if __name__ == "__main__":
    unittest.main()
