from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import ClassVar

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (ROOT / "contracts/npi-api.openapi.yaml").read_text(encoding="utf-8")
LINES = CONTRACT.splitlines()
OWNERSHIP = (ROOT / "contracts/data-ownership.yaml").read_text(encoding="utf-8")


def _indented_block(marker: str) -> str:
    matches = [index for index, line in enumerate(LINES) if line == marker]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {marker!r} block, found {len(matches)}")
    start = matches[0]
    indent = len(marker) - len(marker.lstrip())
    end = len(LINES)
    for index in range(start + 1, len(LINES)):
        line = LINES[index]
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            end = index
            break
    return "\n".join(LINES[start:end])


def _schema(name: str) -> str:
    return _indented_block(f"    {name}:")


def _response(name: str) -> str:
    return _indented_block(f"    {name}:")


def _required(schema_name: str) -> tuple[str, ...]:
    block = _schema(schema_name)
    match = re.search(r"^      required:\s*\[([^]]*)\]", block, re.MULTILINE)
    if match is None:
        raise AssertionError(f"{schema_name} has no flow required list")
    return tuple(item.strip() for item in match.group(1).split(",") if item.strip())


def _property_names(schema_name: str) -> set[str]:
    return set(
        re.findall(
            r"^        ([A-Za-z][A-Za-z0-9]*):",
            _schema(schema_name),
            re.MULTILINE,
        )
    )


class Phase4GateReviewContractTest(unittest.TestCase):
    ROUTES = (
        (
            "  /projects/{projectId}/gates/{gateId}/review:",
            "operationId: getGateReview",
            None,
        ),
        (
            "  /projects/{projectId}/gates/{gateId}:start-review:",
            "operationId: startGateReview",
            "StartGateReview",
        ),
        (
            "  /projects/{projectId}/gates/{gateId}/review-cycles/{cycleId}/reviews:",
            "operationId: submitGateReview",
            "SubmitGateReview",
        ),
        (
            (
                "  /projects/{projectId}/gates/{gateId}/review-cycles/"
                "{cycleId}/exceptions:"
            ),
            "operationId: requestGateReviewException",
            "RequestGateReviewException",
        ),
        (
            (
                "  /projects/{projectId}/gates/{gateId}/review-cycles/"
                "{cycleId}/exceptions/{exceptionId}:decide:"
            ),
            "operationId: decideGateReviewException",
            "DecideGateReviewException",
        ),
        (
            "  /projects/{projectId}/gates/{gateId}:decide:",
            "operationId: decideGate",
            "DecideGate",
        ),
        (
            "  /projects/{projectId}/gates/{gateId}:reopen:",
            "operationId: reopenGate",
            "ReopenGate",
        ),
    )

    REQUEST_FIELDS: ClassVar[dict[str, tuple[str, ...]]] = {
        "StartGateReview": (
            "expectedGateVersion",
            "policyGlobalId",
            "policyVersion",
            "policySnapshotHash",
            "bindings",
        ),
        "SubmitGateReview": (
            "expectedCycleVersion",
            "expectedInputHash",
            "stepKey",
            "outcome",
            "opinion",
        ),
        "RequestGateReviewException": (
            "expectedCycleVersion",
            "expectedInputHash",
            "requirementGlobalId",
            "requirementKey",
            "kind",
            "reason",
            "risk",
            "expiresAt",
            "closureActionGlobalId",
        ),
        "DecideGateReviewException": (
            "expectedCycleVersion",
            "expectedExceptionVersion",
            "expectedInputHash",
            "outcome",
            "opinion",
        ),
        "DecideGate": (
            "expectedGateVersion",
            "expectedCycleVersion",
            "expectedInputHash",
            "outcome",
        ),
        "ReopenGate": (
            "expectedGateVersion",
            "expectedCycleVersion",
            "expectedInputHash",
            "reason",
            "policyGlobalId",
            "policyVersion",
            "policySnapshotHash",
            "bindings",
        ),
    }

    def test_exact_review_routes_replace_the_open_prototype(self) -> None:
        for marker, operation, request_schema in self.ROUTES:
            with self.subTest(marker=marker):
                block = _indented_block(marker)
                self.assertIn(operation, block)
                self.assertIn(
                    '$ref: "#/components/parameters/RequestId"',
                    block,
                )
                if request_schema is None:
                    self.assertIn(
                        '$ref: "#/components/responses/GateReviewQueryResult"',
                        block,
                    )
                    self.assertIn("same Gate-unavailable 404", block)
                else:
                    self.assertIn(
                        '$ref: "#/components/parameters/IdempotencyKey"',
                        block,
                    )
                    self.assertIn(
                        '$ref: "#/components/parameters/CsrfToken"',
                        block,
                    )
                    self.assertIn(
                        f'$ref: "#/components/schemas/{request_schema}"',
                        block,
                    )
                    self.assertIn(
                        '$ref: "#/components/responses/GateReviewCommandResult"',
                        block,
                    )
                    self.assertIn("x-transaction-boundary: gate-root", block)
                    for status in ("400", "401", "404", "409", "422", "500", "503"):
                        self.assertIn(f'"{status}":', block)

        review = _indented_block(self.ROUTES[0][0])
        self.assertNotIn("deliverables", review)
        self.assertNotIn("decisionOptions", review)
        decide = _indented_block("  /projects/{projectId}/gates/{gateId}:decide:")
        for removed in (
            "expectedVersion",
            "evidenceSnapshotHash",
            "waiverIds",
            "enum: [pass, conditional_pass, reject, reopen]",
        ):
            self.assertNotIn(removed, decide)

    def test_management_and_transport_permissions_are_not_business_authority(
        self,
    ) -> None:
        start = _indented_block("  /projects/{projectId}/gates/{gateId}:start-review:")
        self.assertIn("x-required-management-role: System Manager", start)
        self.assertIn("x-business-authority: management-command-only", start)
        self.assertIn("grant review, exception, decision", start)

        expected_authorities = {
            "submitGateReview": "exact-frozen-review-step-member-binding",
            "requestGateReviewException": (
                "exact-current-cycle-member-and-policy-rule"
            ),
            "decideGateReviewException": (
                "exact-frozen-exception-authority-member-binding"
            ),
            "decideGate": "exact-frozen-final-decision-member-binding",
            "reopenGate": "exact-frozen-reopen-member-binding",
        }
        for marker, operation, _schema_name in self.ROUTES[2:]:
            with self.subTest(operation=operation):
                block = _indented_block(marker)
                operation_id = operation.removeprefix("operationId: ")
                self.assertIn("x-required-transport-role: NPI API User", block)
                self.assertIn(
                    "x-business-authority: " + expected_authorities[operation_id],
                    block,
                )
        self.assertIn("transport role", _indented_block(self.ROUTES[2][0]))
        self.assertIn(
            "never supplies business authority",
            _indented_block(self.ROUTES[2][0]),
        )

    def test_command_schemas_are_closed_required_and_exact(self) -> None:
        prohibited = {
            "snapshot",
            "decisionSnapshot",
            "inputSnapshot",
            "url",
            "permissions",
            "canReview",
            "canDecide",
            "blockerCount",
            "reviewCount",
            "readinessScore",
            "actor",
            "memberUserId",
        }
        for name, expected in self.REQUEST_FIELDS.items():
            with self.subTest(schema=name):
                self.assertEqual(_required(name), expected)
                self.assertEqual(_property_names(name), set(expected))
                self.assertIn("additionalProperties: false", _schema(name))
                self.assertTrue(prohibited.isdisjoint(_property_names(name)))

        self.assertEqual(
            _required("GateReviewBindingInput"),
            ("slot", "memberGlobalId"),
        )
        self.assertEqual(
            _property_names("GateReviewBindingInput"),
            {"slot", "memberGlobalId"},
        )
        self.assertIn(
            "enum: [approved, rejected]",
            _schema("SubmitGateReview"),
        )
        self.assertIn(
            "enum: [approved, rejected]",
            _schema("DecideGateReviewException"),
        )
        decide = _schema("DecideGate")
        self.assertIn("enum: [pass, conditional_pass, reject]", decide)
        self.assertNotIn("reopen", decide.casefold())

    def test_request_validation_contract_is_canonical_and_bounded(self) -> None:
        canonical_uuid = _schema("CanonicalUuid")
        self.assertIn("pattern:", canonical_uuid)
        self.assertIn("[0-9a-f]", canonical_uuid)
        for name in ("StartGateReview", "ReopenGate"):
            with self.subTest(schema=name):
                block = _schema(name)
                self.assertIn(
                    '$ref: "#/components/schemas/CanonicalUuid"',
                    block,
                )
                self.assertIn('pattern: "^[a-f0-9]{64}$"', block)
                self.assertIn("maxItems: 64", block)
        exception = _schema("RequestGateReviewException")
        self.assertIn("format: date-time", exception)
        self.assertIn("?Z$'", exception)
        self.assertIn("maxLength: 4000", exception)
        for name in self.REQUEST_FIELDS:
            self.assertNotIn("[a-fA-F0-9]", _schema(name))

    def test_review_result_and_replay_headers_are_closed(self) -> None:
        query = _response("GateReviewQueryResult")
        command = _response("GateReviewCommandResult")
        self.assertIn(
            '$ref: "#/components/schemas/GateReview"',
            query,
        )
        self.assertIn("X-Request-ID:", query)
        self.assertIn("X-Trace-ID:", query)
        self.assertIn(
            '$ref: "#/components/schemas/GateReview"',
            command,
        )
        self.assertIn("X-Request-ID:", command)
        self.assertIn("X-Trace-ID:", command)
        self.assertIn("Idempotency-Replayed:", command)
        self.assertIn("required: true", command)

        closed_outputs = (
            "GateReview",
            "GateReviewGate",
            "GateReviewDecisionBlockedReason",
            "GateReviewDecisionReadiness",
            "GateReviewExceptionRequestOption",
            "GateReviewPolicyReference",
            "GateReviewAuthoritySlot",
            "GateReviewExceptionRuleOption",
            "GateReviewAvailablePolicy",
            "GateReviewMember",
            "GateReviewAuthorityBinding",
            "GateReviewClosureAction",
            "GateReviewBlocker",
            "GateReviewDependencyChange",
            "GateReviewRecord",
            "GateReviewSelectedStep",
            "GateReviewExactObjectReference",
            "GateReviewInputRequirement",
            "GateReviewInputEvidence",
            "GateReviewInputBlocker",
            "GateReviewInputDependency",
            "GateReviewInputSnapshot",
            "GateDecisionDetail",
            "GateReviewExceptionDecision",
            "GateReviewException",
            "GateReviewCycle",
            "GateDecisionSummary",
            "GateReviewPermissions",
            "GateReviewCommandReceipt",
        )
        for name in closed_outputs:
            with self.subTest(schema=name):
                self.assertIn("additionalProperties: false", _schema(name))
        self.assertEqual(
            _required("GateReview"),
            (
                "project",
                "gate",
                "evidence",
                "activeCycle",
                "decisions",
                "decisionReadiness",
                "exceptionRequestOptions",
                "availablePolicies",
                "eligibleMembers",
                "eligibleClosureActions",
                "blockers",
                "dependencyChanges",
                "permissions",
            ),
        )
        self.assertNotIn("items: { type: object }", _schema("GateReview"))

    def test_workspace_exposes_exact_bounded_command_construction_options(
        self,
    ) -> None:
        frozen_requirement = _schema("GateFrozenRequirement")
        self.assertIn("globalId", _required("GateFrozenRequirement"))
        self.assertIn(
            '$ref: "#/components/schemas/CanonicalUuid"',
            frozen_requirement,
        )

        cycle = _schema("GateReviewCycle")
        self.assertIn("bindings", _required("GateReviewCycle"))
        self.assertIn("policyDefinition", _required("GateReviewCycle"))
        self.assertEqual(
            _property_names("GateReviewAuthorityBinding"),
            {"slot", "memberGlobalId", "userId", "displayName"},
        )
        self.assertIn(
            '$ref: "#/components/schemas/GateReviewAuthorityBinding"',
            cycle,
        )
        self.assertIn("maxItems: 64", cycle)
        self.assertIn(
            "enum: [active, decided, invalidated, superseded]",
            cycle,
        )
        self.assertIn(
            '$ref: "#/components/schemas/GateReviewAvailablePolicy"',
            cycle,
        )

        workspace = _schema("GateReview")
        self.assertIn("remains present with state", workspace)
        self.assertIn("decided after a decision", workspace)
        self.assertIn(
            '$ref: "#/components/schemas/GateReviewAvailablePolicy"',
            workspace,
        )
        self.assertIn(
            '$ref: "#/components/schemas/GateReviewMember"',
            workspace,
        )
        self.assertIn(
            '$ref: "#/components/schemas/GateReviewClosureAction"',
            workspace,
        )
        self.assertIn(
            '$ref: "#/components/schemas/GateReviewBlocker"',
            workspace,
        )
        self.assertIn(
            '$ref: "#/components/schemas/GateReviewDependencyChange"',
            workspace,
        )
        self.assertIn(
            '$ref: "#/components/schemas/GateReviewDecisionReadiness"',
            workspace,
        )
        self.assertIn(
            '$ref: "#/components/schemas/GateReviewExceptionRequestOption"',
            workspace,
        )
        for bound in (
            "maxItems: 100",
            "maxItems: 500",
            "maxItems: 256",
            "maxItems: 1000",
            "maxItems: 8192",
        ):
            self.assertIn(bound, workspace)

    def test_decision_readiness_and_exception_options_are_closed_domain_facts(
        self,
    ) -> None:
        self.assertEqual(
            _required("GateReviewDecisionReadiness"),
            ("allowedOutcomes", "blockedReasons"),
        )
        readiness = _schema("GateReviewDecisionReadiness")
        self.assertEqual(
            _property_names("GateReviewDecisionReadiness"),
            {"allowedOutcomes", "blockedReasons"},
        )
        self.assertIn(
            "enum: [pass, conditional_pass, reject]",
            readiness,
        )
        self.assertIn("maxItems: 3", readiness)
        self.assertIn(
            '$ref: "#/components/schemas/GateReviewDecisionBlockedReason"',
            readiness,
        )

        blocked = _schema("GateReviewDecisionBlockedReason")
        self.assertEqual(
            _required("GateReviewDecisionBlockedReason"), ("outcome", "code")
        )
        self.assertEqual(
            _property_names("GateReviewDecisionBlockedReason"),
            {"outcome", "code"},
        )
        match = re.search(
            (
                r"^        code:\n"
                r"          type: string\n"
                r"          enum:\n"
                r"            \[\n"
                r"(?P<codes>.*?)"
                r"            \]"
            ),
            blocked,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(
            {
                value
                for value in re.findall(
                    r"^\s+([A-Z][A-Z0-9_]+),?$",
                    match.group("codes"),
                    re.MULTILINE,
                )
            },
            {
                "REVIEW_CYCLE_CLOSED",
                "GATE_INPUT_CHANGED",
                "DECISION_AUTHORITY_REQUIRED",
                "REVIEWS_INCOMPLETE",
                "FILE_EVIDENCE_UNSAFE",
                "GATE_BLOCKED",
                "REQUIRED_P0_EVIDENCE_MISSING",
                "REQUIRED_EVIDENCE_MISSING",
                "EXCEPTION_NOT_REQUIRED",
                "APPROVED_EXCEPTION_REQUIRED",
            },
        )

        self.assertEqual(
            _required("GateReviewExceptionRequestOption"),
            (
                "requirementGlobalId",
                "requirementKey",
                "kind",
                "maximumValidityDays",
                "closureActionGlobalIds",
            ),
        )
        option = _schema("GateReviewExceptionRequestOption")
        self.assertEqual(
            _property_names("GateReviewExceptionRequestOption"),
            set(_required("GateReviewExceptionRequestOption")),
        )
        self.assertIn("maxItems: 500", option)
        self.assertIn("maximum: 3650", option)

        exception = _schema("GateReviewException")
        self.assertIn("allowedOutcomes", _required("GateReviewException"))
        self.assertIn("enum: [approved, rejected]", exception)
        self.assertIn("maxItems: 2", exception)
        self.assertIn("closureActionRef", _required("GateReviewException"))
        self.assertNotIn(
            "closureActionGlobalId",
            _property_names("GateReviewException"),
        )
        self.assertEqual(
            _required("GateReviewExactObjectReference"),
            ("globalId", "version", "snapshotHash"),
        )

        decision = _schema("GateDecisionSummary")
        self.assertIn("detail", _required("GateDecisionSummary"))
        self.assertIn(
            '$ref: "#/components/schemas/GateDecisionDetail"',
            decision,
        )
        self.assertEqual(
            _required("GateDecisionDetail"),
            (
                "lineageHash",
                "cycleNumber",
                "policyRef",
                "inputSnapshot",
                "reviewHashes",
                "exceptionHashes",
                "cycleVersion",
            ),
        )

    def test_policy_member_action_and_blocker_options_are_closed_exact_outputs(
        self,
    ) -> None:
        self.assertEqual(
            _required("GateReviewAvailablePolicy"),
            ("policyRef", "authoritySlots", "exceptionRules"),
        )
        self.assertEqual(
            _property_names("GateReviewAuthoritySlot"),
            {"slot", "purpose"},
        )
        self.assertIn(
            "enum: [review, decision, reopen, exception]",
            _schema("GateReviewAuthoritySlot"),
        )
        self.assertEqual(
            _required("GateReviewExceptionRuleOption"),
            (
                "kind",
                "eligibleRequirementKeys",
                "approvalAuthoritySlot",
                "maximumValidityDays",
                "requiredClosureActionKind",
            ),
        )
        exception_rule = _schema("GateReviewExceptionRuleOption")
        self.assertIn("maximum: 3650", exception_rule)
        self.assertIn("const: action", exception_rule)
        self.assertEqual(
            _required("GateReviewClosureAction"),
            ("globalId", "title", "state", "stateLabelSource", "version"),
        )
        self.assertEqual(
            _required("GateReviewBlocker"),
            (
                "globalId",
                "kind",
                "title",
                "state",
                "stateLabelSource",
                "dueAt",
                "owner",
            ),
        )
        blocker = _schema("GateReviewBlocker")
        self.assertIn("enum: [risk, issue, action, decision_request]", blocker)
        self.assertNotIn("readiness", blocker.casefold())
        self.assertNotIn("url", blocker.casefold())
        self.assertIn("stateLabelSource", blocker)
        self.assertIn("stateLabelSource", _schema("GateReviewClosureAction"))

        dependency_change = _schema("GateReviewDependencyChange")
        self.assertEqual(
            _required("GateReviewDependencyChange"),
            (
                "eventGlobalId",
                "eventType",
                "priorCycleGlobalId",
                "successorCycleGlobalId",
                "oldInputHash",
                "newInputHash",
                "priorDecisionGlobalId",
                "priorDecisionLineageHash",
                "actorUserId",
                "initiatedByUserId",
                "occurredAt",
                "reason",
            ),
        )
        self.assertEqual(
            _property_names("GateReviewDependencyChange"),
            {
                *_required("GateReviewDependencyChange"),
                "impactActionGlobalId",
            },
        )
        self.assertIn('type: "null"', dependency_change)
        self.assertIn("Optional legacy lineage only", dependency_change)
        self.assertIn("enum: [invalidated, refreshed]", dependency_change)
        self.assertIn("domain lineage hash", dependency_change)
        self.assertIn("public persisted", dependency_change)
        self.assertIn("?Z$'", dependency_change)

        command_schemas = "\n".join(_schema(name) for name in self.REQUEST_FIELDS)
        for output_only in (
            "availablePolicies",
            "eligibleMembers",
            "eligibleClosureActions",
            "blockers",
            "dependencyChanges",
            "decisionReadiness",
            "exceptionRequestOptions",
            "allowedOutcomes",
            "authoritySlots",
            "exceptionRules",
        ):
            self.assertNotIn(f"        {output_only}:", command_schemas)

    def test_command_receipt_reconciliation_is_closed_actor_bound_and_no_store(
        self,
    ) -> None:
        route = _indented_block(
            "  /projects/{projectId}/gates/{gateId}/"
            "review-command-receipts/{operation}:"
        )
        self.assertIn("operationId: getGateReviewCommandReceipt", route)
        self.assertIn(
            "x-business-authority: exact-current-actor-command-receipt",
            route,
        )
        self.assertIn("x-lock-order: [project, gate]", route)
        self.assertIn('$ref: "#/components/parameters/IdempotencyKey"', route)
        self.assertIn('$ref: "#/components/parameters/RequestId"', route)
        self.assertNotIn('$ref: "#/components/parameters/CsrfToken"', route)
        self.assertIn('const: "private, no-store"', route)
        self.assertIn(
            '$ref: "#/components/schemas/GateReviewCommandReceipt"',
            route,
        )
        for operation in (
            "gate.review.start",
            "gate.review.submit",
            "gate.review.exception.request",
            "gate.review.exception.decide",
            "gate.review.decide",
            "gate.review.reopen",
        ):
            self.assertIn(operation, route)
        self.assertEqual(
            _required("GateReviewCommandReceipt"),
            ("operation", "status", "workspaceReloadRequired"),
        )
        receipt = _schema("GateReviewCommandReceipt")
        self.assertEqual(
            _property_names("GateReviewCommandReceipt"),
            {"operation", "status", "workspaceReloadRequired"},
        )
        self.assertIn("enum: [completed, absent]", receipt)
        self.assertIn("const: true", receipt)

    def test_review_history_ownership_is_append_only_and_fail_closed(self) -> None:
        expected_objects = (
            "GateReviewPolicy",
            "GateReviewCycle",
            "GateReviewRecord",
            "GateReviewException",
            "GateReviewEvent",
            "GateDecisionSnapshot",
        )
        for object_name in expected_objects:
            with self.subTest(object_name=object_name):
                self.assertIn(
                    f"  {object_name}:\n    owner_system: NPI_ONE",
                    OWNERSHIP,
                )
        for object_name in (
            "GateReviewCycle",
            "GateReviewRecord",
            "GateReviewException",
            "GateReviewEvent",
            "GateDecisionSnapshot",
        ):
            marker = f"  {object_name}:"
            lines = OWNERSHIP.splitlines()
            start = lines.index(marker)
            end = next(
                (
                    index
                    for index in range(start + 1, len(lines))
                    if lines[index].startswith("  ")
                    and not lines[index].startswith("    ")
                ),
                len(lines),
            )
            block = "\n".join(lines[start:end])
            self.assertIn("APPEND_ONLY", block)
        self.assertIn(
            "authority_slots_and_rules: {owner: VERSIONED_GATE_POLICY",
            OWNERSHIP,
        )
        self.assertIn("conflict: FAIL_CLOSED", OWNERSHIP)


if __name__ == "__main__":
    unittest.main()
