from __future__ import annotations

import importlib
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_APP = ROOT / "apps/npi_integration"
if str(INTEGRATION_APP) not in sys.path:
    sys.path.insert(0, str(INTEGRATION_APP))

from npi_integration.project_publish.domain import (  # noqa: E402
    ProjectPublishError,
    ProjectSource,
    TargetObservation,
    canonical_json,
)


REQUEST_ID = "00000000-0000-4000-8000-000000009001"
ATTEMPT_ID = "00000000-0000-4000-8000-000000009002"


def source() -> ProjectSource:
    return ProjectSource(
        tenant_id="jce",
        project_global_id="00000000-0000-4000-8000-000000009003",
        business_code="MM-35029",
        title="MM-35029 program",
        project_type="new_tool",
        target_sop="2027-01-31",
        actor_user_id="kaibo_wang@whjichen.cn",
        source_version=1,
    )


def observation(
    status: int = 200,
    *,
    authenticated: bool = True,
    contract_valid: bool = True,
    formal_project_id: str | None = "PROJ-0042",
    target_version: str | None = "2026-09-06 10:00:00.000001",
    found: bool | None = None,
) -> TargetObservation:
    return TargetObservation(
        http_status=status,
        response_hash="a" * 64,
        authenticated=authenticated,
        contract_valid=contract_valid,
        formal_project_id=formal_project_id,
        target_version=target_version,
        exact_replay=False,
        error_code=None,
        found=found,
    )


class StubDatabase:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class ProjectPublishWorkerTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_integration.project_publish.frappe_validation",
        "npi_integration.project_publish.service",
        "npi_integration.project_publish.worker",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)

        self.database = StubDatabase()
        self.enqueued: list[dict[str, object]] = []
        self.saved_documents: list[object] = []
        frappe = types.ModuleType("frappe")
        frappe.conf = {}
        frappe.db = self.database
        frappe.get_doc = lambda *_args, **_kwargs: types.SimpleNamespace(
            state="pending"
        )
        frappe.enqueue = lambda path, **kwargs: self.enqueued.append(
            {"path": path, **kwargs}
        )
        sys.modules["frappe"] = frappe

        validation = types.ModuleType(
            "npi_integration.project_publish.frappe_validation"
        )

        @contextmanager
        def project_publish_write(_request_id: str):
            yield object()

        validation.project_publish_write = project_publish_write
        validation.insert_support_document = (
            lambda document, **_kwargs: self.saved_documents.append(document)
        )
        validation.save_support_document = (
            lambda document, **_kwargs: self.saved_documents.append(document)
        )
        sys.modules[validation.__name__] = validation
        self.frappe = frappe
        self.module = importlib.import_module(
            "npi_integration.project_publish.worker"
        )

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    def claim(self, *, number: int = 1, kind: str = "publish"):
        return self.module.Claim(
            REQUEST_ID,
            ATTEMPT_ID,
            number,
            "00000000-0000-4000-8000-000000009004",
            kind,
            source(),
        )

    def test_process_publishes_the_persisted_actor_bound_source(self) -> None:
        claim = self.claim()
        calls: list[object] = []

        def publish(command, profile, credential):
            calls.extend((command, profile, credential))
            return observation()

        with (
            patch.object(self.module, "_claim", return_value=claim),
            patch.object(self.module, "_profile", return_value="profile"),
            patch.object(self.module, "load_credential", return_value="credential"),
            patch.object(self.module, "_mark_adapter_boundary") as boundary,
            patch.object(self.module, "publish", side_effect=publish),
            patch.object(self.module, "_complete_publish") as complete,
            patch.object(
                self.module,
                "_status",
                return_value={"requestGlobalId": REQUEST_ID, "state": "succeeded"},
            ),
        ):
            result = self.module.process_request(REQUEST_ID)

        self.assertEqual(result["state"], "succeeded")
        boundary.assert_called_once_with(claim, "profile")
        complete.assert_called_once()
        command = calls[0]
        self.assertEqual(command.source.actor_user_id, "kaibo_wang@whjichen.cn")
        self.assertEqual(command.source.project_global_id, source().project_global_id)
        self.assertEqual(calls[1:], ["profile", "credential"])

    def test_publish_response_truth_selects_retry_final_and_uncertain_states(self) -> None:
        cases = (
            (self.claim(number=2), observation(503), ("failed_retryable", "failed_retryable")),
            (self.claim(number=3), observation(503), ("failed_final", "failed_final")),
            (
                self.claim(number=1),
                observation(authenticated=False, contract_valid=False),
                ("uncertain", "uncertain"),
            ),
            (self.claim(number=1), observation(422), ("failed_final", "failed_final")),
        )
        for claim, value, expected in cases:
            with self.subTest(status=value.http_status, attempt=claim.attempt_number):
                captured: list[tuple[object, ...]] = []
                with patch.object(
                    self.module,
                    "_complete",
                    side_effect=lambda *args, **_kwargs: captured.append(args),
                ):
                    self.module._complete_publish(claim, value)
                self.assertEqual(captured[0][1:3], expected)

    def test_uncertain_request_reconciles_before_any_republish(self) -> None:
        self.frappe.get_doc = lambda *_args, **_kwargs: types.SimpleNamespace(
            state="uncertain"
        )
        claim = self.claim(kind="reconcile")
        with (
            patch.object(self.module, "_claim", return_value=claim) as claim_call,
            patch.object(self.module, "_profile", return_value="profile"),
            patch.object(self.module, "load_credential", return_value="credential"),
            patch.object(self.module, "_mark_adapter_boundary"),
            patch.object(
                self.module,
                "reconcile",
                return_value=observation(found=True),
            ) as reconcile_call,
            patch.object(self.module, "publish") as publish_call,
            patch.object(self.module, "_complete_reconcile"),
            patch.object(self.module, "_status", return_value={"state": "succeeded"}),
        ):
            self.module.process_request(REQUEST_ID)

        claim_call.assert_called_once_with(REQUEST_ID, kind="reconcile")
        reconcile_call.assert_called_once()
        publish_call.assert_not_called()

    def test_reconciled_absence_returns_to_pending_and_enqueues_one_publish(self) -> None:
        claim = self.claim(kind="reconcile")
        captured: list[tuple[object, ...]] = []
        with patch.object(
            self.module,
            "_complete",
            side_effect=lambda *args, **_kwargs: captured.append(args),
        ):
            self.module._complete_reconcile(
                claim,
                observation(
                    formal_project_id=None,
                    target_version=None,
                    found=False,
                ),
            )
        self.assertEqual(captured[0][1:3], ("reconciled_absent", "pending"))
        self.assertEqual(len(self.enqueued), 1)
        self.assertEqual(self.enqueued[0]["request_global_id"], REQUEST_ID)

    def test_corrupt_persisted_source_fails_before_claim_state_is_mutated(self) -> None:
        request = types.SimpleNamespace(
            state="pending",
            source_snapshot=canonical_json({"schemaVersion": 1}),
            source_hash="b" * 64,
        )
        self.frappe.get_doc = lambda *_args, **_kwargs: request
        with self.assertRaises(ProjectPublishError):
            self.module._claim(REQUEST_ID, kind="publish")
        self.assertEqual(request.state, "pending")
        self.assertEqual(self.database.commits, 0)
        self.assertEqual(self.saved_documents, [])

    def test_automatic_retry_limit_is_persisted_as_final_failure(self) -> None:
        value = source()
        request = types.SimpleNamespace(
            state="failed_retryable",
            source_snapshot=canonical_json(value.snapshot),
            source_hash=value.source_hash,
            next_retry_at=None,
            attempt_count=3,
        )
        self.frappe.get_doc = lambda *_args, **_kwargs: request
        self.assertIsNone(self.module._claim(REQUEST_ID, kind="publish"))
        self.assertEqual(request.state, "failed_final")
        self.assertEqual(
            request.last_error_code,
            "PROJECT_PUBLISH_AUTOMATIC_RETRY_LIMIT_REACHED",
        )
        self.assertEqual(self.database.commits, 1)


if __name__ == "__main__":
    unittest.main()
