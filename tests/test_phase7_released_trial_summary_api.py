from __future__ import annotations

import importlib
import sys
import types
import unittest
from dataclasses import dataclass
from typing import Any
from uuid import UUID


sys.path.insert(0, "apps/npi_core")


PROJECT_ID = "2e96f421-5872-4c96-a0dd-718d5c970a21"
ROUND_ID = "89953948-4178-46dc-b7ca-8b94f2ac4e36"
SUMMARY_ID = "29e933a3-3954-4a96-9400-2be1987ae370"
CONCLUSION_ID = "39e933a3-3954-4a96-9400-2be1987ae370"
REQUEST_ID = "5dc0ef7b-8563-46ad-9f40-76dd474566ea"
SHA = "a" * 64


class AttrDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


@dataclass
class PrincipalStub:
    user_id: str = "admin@example.invalid"
    tenant_id: str = "TENANT-A"
    roles: tuple[str, ...] = ("NPI API User", "System Manager")
    is_external: bool = False


class RepositoryStub:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[str, tuple[object, ...], dict[str, Any]]] = []
        self.replayed = False

    def summary_workspace(self, *args, **kwargs):
        self.calls.append(("query", args, kwargs))
        return self.response

    def retain_summary(self, *args, **kwargs):
        self.calls.append(("retain", args, kwargs))
        return types.SimpleNamespace(response=self.response, replayed=self.replayed)

    def revise_summary(self, *args, **kwargs):
        self.calls.append(("revise", args, kwargs))
        return types.SimpleNamespace(response=self.response, replayed=self.replayed)


class Phase7ReleasedTrialSummaryApiTest(unittest.TestCase):
    MODULES = (
        "frappe",
        "npi_core.released_summary_api",
        "npi_core.bff",
    )

    def setUp(self) -> None:
        self.saved = {name: sys.modules.get(name) for name in self.MODULES}
        for name in self.MODULES:
            sys.modules.pop(name, None)
        self.headers = {
            "Idempotency-Key": "p7-07-summary-command-0001",
            "X-Request-ID": REQUEST_ID,
        }
        frappe = types.ModuleType("frappe")
        frappe._ = lambda source: source
        frappe.conf = AttrDict(npi_p7_07_routes_disabled=False)
        frappe.flags = types.SimpleNamespace(
            npi_route_params={
                "project_id": PROJECT_ID,
                "trial_round_id": ROUND_ID,
                "summary_id": SUMMARY_ID,
            }
        )
        frappe.local = types.SimpleNamespace(
            request=types.SimpleNamespace(path="/", method="GET"),
            form_dict=AttrDict(),
        )
        frappe.get_request_header = lambda name: self.headers.get(name)

        def whitelist(*, allow_guest=False, methods=None):
            return lambda function: function

        frappe.whitelist = whitelist
        self.frappe = frappe
        sys.modules["frappe"] = frappe
        self.api = importlib.import_module("npi_core.released_summary_api")
        self.router = importlib.import_module("npi_core.bff")
        self.response = {
            "projectGlobalId": PROJECT_ID,
            "trialRound": {"globalId": ROUND_ID},
            "summaryRevisions": [],
            "currentSummaryRevisionGlobalId": None,
            "currentDecidedConclusion": None,
            "permissions": {
                "view": True,
                "retain": True,
                "revise": False,
                "requiresExactRound": True,
                "requiresExactConclusion": True,
                "requiresExactPredecessor": True,
            },
            "controlledOutput": {
                "sourceObjectType": "released_trial_summary",
                "sourceGlobalId": None,
                "sourceVersion": None,
                "mapping": "unavailable",
            },
            "holds": {
                "formalRelease": "unavailable",
                "customerApproval": "unavailable",
                "signature": "unavailable",
                "productionAcceptance": "unavailable",
                "gateDecision": "unavailable",
                "externalProjection": "unavailable",
            },
        }
        self.repository = RepositoryStub(self.response)
        self.api.frappe_domain_call = lambda function, **_kwargs: function()
        self.api.authenticated_user = lambda: "admin@example.invalid"
        self.api.authenticated_principal = lambda _actor: PrincipalStub()
        self.api.require_csrf_token = lambda: None
        self.api.response_request_id = lambda: REQUEST_ID
        self.api.actor_idempotency_key_hash = lambda *_args: "b" * 64
        self.api.current_trace_id = types.SimpleNamespace(get=lambda: "trace-p707-api")
        self.api._repository_factory = lambda **_kwargs: self.repository

    def tearDown(self) -> None:
        for name in self.MODULES:
            sys.modules.pop(name, None)
            if self.saved[name] is not None:
                sys.modules[name] = self.saved[name]

    @staticmethod
    def retain_payload() -> dict[str, object]:
        return {
            "expectedRoundOptimisticVersion": 7,
            "expectedRoundSnapshotHash": SHA,
            "conclusionRevisionGlobalId": CONCLUSION_ID,
            "expectedConclusionVersion": 4,
            "expectedConclusionSnapshotHash": SHA,
            "reason": "Retain the exact decided Trial conclusion.",
        }

    def test_exact_routes_and_independent_default_closed_switch(self) -> None:
        cases = (
            (
                "GET",
                f"/api/npi/v1/projects/{PROJECT_ID}/trial-rounds/{ROUND_ID}/released-trial-summaries",
                "npi_core.released_summary_api.get_released_trial_summaries",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/trial-rounds/{ROUND_ID}/released-trial-summaries",
                "npi_core.released_summary_api.retain_released_trial_summary",
            ),
            (
                "POST",
                f"/api/npi/v1/projects/{PROJECT_ID}/trial-rounds/{ROUND_ID}/released-trial-summaries/{SUMMARY_ID}:revise",
                "npi_core.released_summary_api.revise_released_trial_summary",
            ),
        )
        for method, path, expected in cases:
            with self.subTest(method=method):
                self.frappe.local.request = types.SimpleNamespace(path=path, method=method)
                self.frappe.local.form_dict = AttrDict()
                self.router.route_request()
                self.assertEqual(self.frappe.local.form_dict.cmd, expected)
        self.frappe.conf.pop("npi_p7_07_routes_disabled")
        self.frappe.local.form_dict = AttrDict()
        self.router.route_request()
        self.assertEqual(
            self.frappe.local.form_dict.cmd,
            "npi_core.released_summary_api.released_trial_summary_routes_disabled",
        )

    def test_query_and_commands_bind_only_route_and_exact_body_truth(self) -> None:
        self.assertEqual(self.api.get_released_trial_summaries(), self.response)
        self.assertEqual(
            self.repository.calls[-1][1],
            (UUID(PROJECT_ID), UUID(ROUND_ID)),
        )
        payload = self.retain_payload()
        self.assertEqual(self.api.retain_released_trial_summary(**payload), self.response)
        name, args, values = self.repository.calls[-1]
        self.assertEqual(name, "retain")
        self.assertEqual(args, (UUID(PROJECT_ID), UUID(ROUND_ID)))
        self.assertEqual(values["conclusion_revision_id"], UUID(CONCLUSION_ID))
        self.assertEqual(values["idempotency_key_hash"], "b" * 64)

        revise = payload | {
            "predecessorRevisionGlobalId": SUMMARY_ID,
            "expectedPredecessorVersion": 1,
            "expectedPredecessorSnapshotHash": SHA,
        }
        self.assertEqual(self.api.revise_released_trial_summary(**revise), self.response)
        name, args, values = self.repository.calls[-1]
        self.assertEqual(name, "revise")
        self.assertEqual(
            args,
            (UUID(PROJECT_ID), UUID(ROUND_ID), UUID(SUMMARY_ID)),
        )
        self.assertNotIn("tenant_id", values)
        self.assertNotIn("source_manifest", values)

    def test_switch_and_authentication_precede_body_validation(self) -> None:
        order: list[str] = []
        self.api._require_routes_enabled = lambda: order.append("switch")
        self.api.authenticated_user = lambda: order.append("authentication") or "admin"
        self.api.require_csrf_token = lambda: order.append("csrf")
        self.api.authenticated_principal = lambda _actor: (
            order.append("principal") or PrincipalStub()
        )
        self.api.reject_unexpected_request_fields = lambda *_args: order.append("closed-body")
        self.api.require_request_fields = lambda *_args: order.append("required-body")
        self.api._new_repository = lambda _principal: (
            order.append("repository") or (REQUEST_ID, self.repository)
        )
        self.api.retain_released_trial_summary(**self.retain_payload())
        self.assertEqual(
            order[:7],
            [
                "switch",
                "authentication",
                "csrf",
                "principal",
                "closed-body",
                "required-body",
                "repository",
            ],
        )

    def test_response_validation_rejects_scope_escape_and_open_fields(self) -> None:
        with self.assertRaises(RuntimeError):
            self.api._validated_response(
                self.response | {"projectGlobalId": str(UUID(int=999))},
                UUID(PROJECT_ID),
                UUID(ROUND_ID),
            )
        with self.assertRaises(RuntimeError):
            self.api._validated_response(
                self.response | {"externalAuthority": "approved"},
                UUID(PROJECT_ID),
                UUID(ROUND_ID),
            )

        from tests.test_phase7_released_trial_summary_domain import summary

        first = summary()
        invalid_first = summary(
            global_id=21,
            summary_version=2,
            predecessor=first,
            conclusion_id=17,
            conclusion_version=5,
            conclusion_marker="e",
        )
        with self.assertRaises(RuntimeError):
            self.api._validated_response(
                self.response
                | {
                    "projectGlobalId": str(invalid_first.project_global_id),
                    "trialRound": {
                        "globalId": str(invalid_first.trial_round_global_id)
                    },
                    "summaryRevisions": [
                        invalid_first.snapshot_payload()
                        | {"snapshotHash": invalid_first.snapshot_hash}
                    ],
                    "currentSummaryRevisionGlobalId": str(invalid_first.global_id),
                    "controlledOutput": {
                        "sourceObjectType": "released_trial_summary",
                        "sourceGlobalId": str(invalid_first.global_id),
                        "sourceVersion": invalid_first.summary_version,
                        "mapping": "unavailable",
                    },
                },
                invalid_first.project_global_id,
                invalid_first.trial_round_global_id,
            )


if __name__ == "__main__":
    unittest.main()
