from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (ROOT / "contracts" / "npi-api.openapi.yaml").read_text(encoding="utf-8")
LINES = CONTRACT.splitlines()
OWNERSHIP = (ROOT / "contracts" / "data-ownership.yaml").read_text(encoding="utf-8")
OWNERSHIP_LINES = OWNERSHIP.splitlines()


def _block(marker: str) -> str:
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
    return _block(f"    {name}:")


def _ownership_block(marker: str) -> str:
    matches = [index for index, line in enumerate(OWNERSHIP_LINES) if line == marker]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {marker!r} ownership block")
    start = matches[0]
    indent = len(marker) - len(marker.lstrip())
    end = len(OWNERSHIP_LINES)
    for index in range(start + 1, len(OWNERSHIP_LINES)):
        line = OWNERSHIP_LINES[index]
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            end = index
            break
    return "\n".join(OWNERSHIP_LINES[start:end])


def _operation(path_marker: str, method: str) -> str:
    path_block = _block(path_marker)
    lines = path_block.splitlines()
    marker = f"    {method}:"
    matches = [index for index, line in enumerate(lines) if line == marker]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {method!r} operation in {path_marker!r}")
    start = matches[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.strip() and len(line) - len(line.lstrip()) <= 4:
            end = index
            break
    return "\n".join(lines[start:end])


def _response_statuses(operation: str) -> set[str]:
    return set(
        match.group(1) or "default"
        for match in re.finditer(
            r'^        (?:"([0-9]{3})"|default):',
            operation,
            re.MULTILINE,
        )
    )


def _required(name: str) -> tuple[str, ...]:
    block = _schema(name)
    flow = re.search(r"^      required:\s*\[([^]]*)\]", block, re.MULTILINE)
    if flow:
        return tuple(
            value.strip() for value in flow.group(1).split(",") if value.strip()
        )
    lines = block.splitlines()
    start = lines.index("      required:") + 1
    values = []
    for line in lines[start:]:
        if line.startswith("        ["):
            values.extend(
                value.strip() for value in line.strip(" []").split(",") if value.strip()
            )
            continue
        if line.startswith("          "):
            normalized = line.strip().strip(",")
            if normalized not in {"[", "]"}:
                values.append(normalized)
            continue
        if line.strip():
            break
    return tuple(values)


def _properties(name: str) -> set[str]:
    return set(
        re.findall(
            r"^        ([A-Za-z][A-Za-z0-9]*):",
            _schema(name),
            re.MULTILINE,
        )
    )


class Phase5DocumentContractTest(unittest.TestCase):
    ROUTES = (
        "  /projects/{projectId}/documents:",
        "  /projects/{projectId}/documents/{documentId}:",
        "  /projects/{projectId}/documents/{documentId}:check-out:",
        "  /projects/{projectId}/documents/{documentId}:check-in:",
        "  /projects/{projectId}/documents/{documentId}:recover-lock:",
        "  /projects/{projectId}/documents/{documentId}/revisions:",
        (
            "  /projects/{projectId}/documents/{documentId}/revisions/"
            "{revisionId}/files/{fileRevisionId}/capabilities:"
        ),
        (
            "  /projects/{projectId}/documents/{documentId}/revisions/"
            "{revisionId}/files/{fileRevisionId}:content:"
        ),
    )
    OPERATIONS = (
        (ROUTES[0], "get", "listControlledDocuments", "200", False),
        (ROUTES[0], "post", "createControlledDocument", "201", True),
        (ROUTES[1], "get", "getControlledDocument", "200", False),
        (ROUTES[2], "post", "checkOutControlledDocument", "200", True),
        (ROUTES[3], "post", "checkInControlledDocument", "200", True),
        (
            ROUTES[4],
            "post",
            "recoverControlledDocumentLock",
            "200",
            True,
        ),
        (ROUTES[5], "post", "createDocumentRevision", "201", True),
        (
            ROUTES[6],
            "get",
            "getDocumentFileCapabilities",
            "200",
            False,
        ),
        (ROUTES[7], "post", "getDocumentFileContent", "200", True),
    )
    RELEASE_ROUTES = (
        (
            "  /projects/{projectId}/documents/{documentId}/revisions/"
            "{revisionId}:submit-review:"
        ),
        (
            "  /projects/{projectId}/documents/{documentId}/revisions/"
            "{revisionId}:review:"
        ),
        (
            "  /projects/{projectId}/documents/{documentId}/revisions/"
            "{revisionId}:resubmit-review:"
        ),
        (
            "  /projects/{projectId}/documents/{documentId}/revisions/"
            "{revisionId}:release:"
        ),
        (
            "  /projects/{projectId}/documents/{documentId}/revisions/"
            "{revisionId}:supersede:"
        ),
        (
            "  /projects/{projectId}/documents/{documentId}/revisions/"
            "{revisionId}:obsolete:"
        ),
    )
    RELEASE_OPERATIONS = (
        (
            RELEASE_ROUTES[0],
            "submitDocumentRevisionReview",
            "exact-policy-submitter",
            "SubmitDocumentReview",
        ),
        (
            RELEASE_ROUTES[1],
            "confirmDocumentRevisionReview",
            "exact-active-reviewer-slot",
            "ConfirmDocumentReview",
        ),
        (
            RELEASE_ROUTES[2],
            "resubmitDocumentRevisionReview",
            "exact-policy-submitter",
            "ResubmitDocumentReview",
        ),
        (
            RELEASE_ROUTES[3],
            "releaseDocumentRevision",
            "exact-policy-release-authority",
            "ReleaseDocumentRevision",
        ),
        (
            RELEASE_ROUTES[4],
            "supersedeDocumentRevision",
            "exact-policy-supersede-authority",
            "SupersedeDocumentRevision",
        ),
        (
            RELEASE_ROUTES[5],
            "obsoleteDocumentRevision",
            "exact-policy-obsolete-authority",
            "ObsoleteDocumentRevision",
        ),
    )

    def test_document_routes_are_explicit_bff_operations(self) -> None:
        for marker in self.ROUTES:
            with self.subTest(route=marker):
                block = _block(marker)
                self.assertIn("tags: [Documents]", block)
                self.assertIn(
                    '$ref: "#/components/parameters/RequestId"',
                    block,
                )
                self.assertNotIn("ignore_" "permissions", block)
        collection = _block(self.ROUTES[0])
        self.assertIn("operationId: listControlledDocuments", collection)
        self.assertIn("operationId: createControlledDocument", collection)
        self.assertIn("signed-keyset", collection)
        self.assertIn("same 404 representation", collection)
        self.assertIn("raw DocType names", collection)
        self.assertIn("are never accepted", collection)
        detail = _block(self.ROUTES[1])
        self.assertIn("operationId: getControlledDocument", detail)
        self.assertIn("never returns a raw", detail)

    def test_each_document_method_has_exact_operation_and_status_matrix(
        self,
    ) -> None:
        query_errors = {"400", "401", "404", "422", "500", "503", "default"}
        command_errors = {
            "400",
            "401",
            "403",
            "404",
            "409",
            "422",
            "500",
            "503",
            "default",
        }
        observed = set()
        for path, method, operation_id, success, command in self.OPERATIONS:
            with self.subTest(path=path, method=method):
                operation = _operation(path, method)
                observed.add((path, method))
                self.assertIn(f"operationId: {operation_id}", operation)
                self.assertIn("tags: [Documents]", operation)
                self.assertIn(
                    '$ref: "#/components/parameters/RequestId"',
                    operation,
                )
                self.assertEqual(
                    _response_statuses(operation),
                    {success} | (command_errors if command else query_errors),
                )
        self.assertEqual(len(observed), 9)

    def test_every_command_binds_csrf_idempotency_audit_and_exact_roles(self) -> None:
        for marker, method, _operation_id, _success, command in self.OPERATIONS:
            if not command:
                continue
            with self.subTest(route=marker, method=method):
                block = _operation(marker, method)
                self.assertIn("x-required-roles: [System Manager]", block)
                self.assertIn("x-transaction-boundary:", block)
                self.assertIn("x-audit-operation:", block)
                self.assertIn(
                    '$ref: "#/components/parameters/IdempotencyKey"',
                    block,
                )
                self.assertIn(
                    '$ref: "#/components/parameters/CsrfToken"',
                    block,
                )

    def test_release_commands_are_exact_policy_authorized_bff_operations(
        self,
    ) -> None:
        command_errors = {
            "400",
            "401",
            "403",
            "404",
            "409",
            "422",
            "500",
            "503",
            "default",
        }
        for route, operation_id, authority, schema in self.RELEASE_OPERATIONS:
            with self.subTest(route=route):
                operation = _operation(route, "post")
                self.assertIn("tags: [Documents]", operation)
                self.assertIn(f"operationId: {operation_id}", operation)
                self.assertIn("x-required-roles: [NPI API User]", operation)
                self.assertNotIn("System Manager", operation)
                self.assertIn(f"x-business-authority: {authority}", operation)
                self.assertIn("x-transaction-boundary:", operation)
                self.assertIn("x-audit-operation: document.", operation)
                self.assertIn(
                    '$ref: "#/components/parameters/IdempotencyKey"',
                    operation,
                )
                self.assertIn(
                    '$ref: "#/components/parameters/CsrfToken"',
                    operation,
                )
                self.assertIn(
                    f'$ref: "#/components/schemas/{schema}"',
                    operation,
                )
                self.assertEqual(
                    _response_statuses(operation),
                    {"201"} | command_errors,
                )

    def test_release_request_and_transition_schemas_are_closed_and_exact(
        self,
    ) -> None:
        expected = {
            "SubmitDocumentReview": {
                "expectedDocumentVersion",
                "expectedLifecycleVersion",
                "policyGlobalId",
                "policyVersion",
                "policySnapshotHash",
                "confirmationIntent",
                "confirmed",
            },
            "ResubmitDocumentReview": {
                "expectedDocumentVersion",
                "expectedLifecycleVersion",
                "policyGlobalId",
                "policyVersion",
                "policySnapshotHash",
                "priorRejectedCycleId",
                "confirmationIntent",
                "confirmed",
            },
            "ConfirmDocumentReview": {
                "expectedDocumentVersion",
                "expectedLifecycleVersion",
                "decision",
                "reason",
                "confirmationIntent",
                "confirmed",
            },
            "ReleaseDocumentRevision": {
                "expectedDocumentVersion",
                "expectedLifecycleVersion",
                "confirmationIntent",
                "confirmed",
            },
            "SupersedeDocumentRevision": {
                "expectedDocumentVersion",
                "expectedLifecycleVersion",
                "replacementRevisionId",
                "expectedReplacementLifecycleVersion",
                "reason",
                "confirmationIntent",
                "confirmed",
            },
            "ObsoleteDocumentRevision": {
                "expectedDocumentVersion",
                "expectedLifecycleVersion",
                "reason",
                "confirmationIntent",
                "confirmed",
            },
        }
        optional = {"ConfirmDocumentReview": {"reason"}}
        for schema, fields in expected.items():
            with self.subTest(schema=schema):
                block = _schema(schema)
                self.assertIn("additionalProperties: false", block)
                self.assertEqual(_properties(schema), fields)
                self.assertEqual(
                    set(_required(schema)),
                    fields - optional.get(schema, set()),
                )
                self.assertIn("confirmed: { type: boolean, const: true }", block)
                self.assertNotIn("actor", block.casefold())
                self.assertNotIn("scanstate", block.casefold())
                self.assertNotIn("fileidentity", block.casefold())
        for schema in (
            "DocumentReleasePolicyReference",
            "DocumentReleaseEventSummary",
            "DocumentConfirmationSummary",
            "DocumentReleaseTransition",
        ):
            with self.subTest(response_schema=schema):
                self.assertIn("additionalProperties: false", _schema(schema))
        transition = _schema("DocumentReleaseTransition")
        self.assertEqual(
            set(_required("DocumentReleaseTransition")),
            _properties("DocumentReleaseTransition"),
        )
        self.assertIn(
            "enum: [draft, in_review, approved, released, superseded, obsolete]",
            transition,
        )
        self.assertNotIn("fileUrl", transition)

    def test_command_schemas_are_closed_and_browser_cannot_assert_file_truth(
        self,
    ) -> None:
        expected = {
            "CreateControlledDocument": {
                "policyGlobalId",
                "policyVersion",
                "policySnapshotHash",
                "documentTypeKey",
                "title",
                "confidentialityKey",
                "objectLinks",
            },
            "DocumentVersionCommand": {"expectedDocumentVersion"},
            "DocumentLockCommand": {
                "expectedDocumentVersion",
                "expectedLockVersion",
            },
            "RecoverDocumentLock": {
                "expectedDocumentVersion",
                "expectedLockVersion",
                "reason",
            },
            "CreateDocumentRevisionMetadata": {
                "expectedDocumentVersion",
                "expectedLockVersion",
                "major",
                "minor",
                "reason",
                "effectiveDate",
                "predecessorRevisionId",
            },
            "DocumentContentRequest": {
                "expectedDocumentVersion",
                "expectedFileVersion",
                "disposition",
            },
        }
        for name, fields in expected.items():
            with self.subTest(schema=name):
                self.assertIn("additionalProperties: false", _schema(name))
                self.assertEqual(_properties(name), fields)
                self.assertEqual(set(_required(name)), fields)
        metadata = _schema("CreateDocumentRevisionMetadata").casefold()
        for forbidden in (
            "sha256",
            "mimetype",
            "sizebytes",
            "scanstate",
            "released",
            "private",
            "tenant",
            "actor",
            "fileidentity",
            "connector",
        ):
            self.assertNotIn(forbidden, metadata)
        revision_route = _block(self.ROUTES[5])
        self.assertIn("multipart/form-data", revision_route)
        self.assertIn("format: binary", revision_route)
        self.assertIn("additionalProperties: false", revision_route)

    def test_response_schemas_are_closed_url_free_and_capabilities_independent(
        self,
    ) -> None:
        schemas = (
            "ControlledDocumentPage",
            "ControlledDocumentWorkspace",
            "ControlledDocumentSummary",
            "DocumentPermissions",
            "DocumentRevision",
            "DocumentRevisionFile",
            "DocumentFileMetadata",
            "DocumentFileCapabilities",
            "DocumentObjectRelationship",
            "DocumentProjectReferenceRelationship",
            "DocumentLockEvent",
            "DocumentFileCapabilityResult",
            "DocumentReleaseWorkspace",
            "DocumentReleaseRevisionHistory",
            "DocumentRevisionLifecycle",
            "DocumentReleaseCapabilities",
            "DocumentReleasePolicyOption",
            "DocumentReviewCycle",
            "DocumentReviewFileEvidence",
            "DocumentReviewerProgress",
            "DocumentReleaseConfirmation",
            "DocumentReleaseLifecycleEvent",
        )
        combined = ""
        for name in schemas:
            with self.subTest(schema=name):
                value = _schema(name)
                self.assertIn("additionalProperties: false", value)
                combined += value.casefold()
        for forbidden in (
            "fileurl",
            "rawurl",
            "privateurl",
            "downloadurl",
            "previewurl",
            "token:",
            "frappecontenthash",
            "fileidentity",
        ):
            self.assertNotIn(forbidden, combined)
        capabilities = _schema("DocumentFileCapabilities")
        self.assertEqual(
            set(_required("DocumentFileCapabilities")),
            {
                "integrity",
                "preview",
                "download",
                "externalRetrieval",
                "connector",
            },
        )
        self.assertIn(
            '$ref: "#/components/schemas/DocumentPreviewCapability"',
            capabilities,
        )
        self.assertIn(
            ('$ref: "#/components/schemas/' 'DocumentExternalRetrievalCapability"'),
            capabilities,
        )
        self.assertIn(
            '$ref: "#/components/schemas/DocumentConnectorCapability"',
            capabilities,
        )
        self.assertIn(
            "state: { type: string, const: unavailable }",
            _schema("DocumentExternalRetrievalCapability"),
        )
        self.assertNotIn(
            "enum: [available",
            _schema("DocumentConnectorCapability"),
        )
        summary = _schema("ControlledDocumentSummary")
        self.assertIn("source", _required("ControlledDocumentSummary"))
        self.assertIn(
            '$ref: "#/components/schemas/ProjectSourceStatus"',
            summary,
        )
        permissions = _schema("DocumentPermissions")
        self.assertIn("preview: { type: boolean }", permissions)
        self.assertIn("download: { type: boolean }", permissions)
        self.assertIn("share: { type: boolean, const: false }", permissions)
        self.assertEqual(
            {
                "submitReview",
                "resubmitReview",
                "review",
                "approve",
                "release",
                "supersede",
                "obsolete",
            },
            {
                name
                for name in _properties("DocumentPermissions")
                if name
                in {
                    "submitReview",
                    "resubmitReview",
                    "review",
                    "approve",
                    "release",
                    "supersede",
                    "obsolete",
                }
            },
        )
        workspace = _schema("ControlledDocumentWorkspace")
        self.assertIn("releaseWorkspace", _required("ControlledDocumentWorkspace"))
        self.assertIn(
            '$ref: "#/components/schemas/DocumentReleaseWorkspace"',
            workspace,
        )
        release_workspace = _schema("DocumentReleaseWorkspace")
        self.assertEqual(
            set(_required("DocumentReleaseWorkspace")),
            _properties("DocumentReleaseWorkspace"),
        )
        self.assertIn(
            "enum: [available, permission_unavailable, routes_disabled]",
            release_workspace,
        )
        self.assertEqual(
            set(_required("DocumentReleaseCapabilities")),
            _properties("DocumentReleaseCapabilities"),
        )
        for name in ("DocumentRelationshipInput", "DocumentRelationship"):
            with self.subTest(discriminator=name):
                value = _schema(name)
                self.assertIn("oneOf:", value)
                self.assertIn("propertyName: kind", value)
        ordinary = _schema("DocumentObjectRelationship")
        self.assertIn('projectReferenceType: { type: "null" }', ordinary)
        self.assertIn('targetSourceSystem: { type: "null" }', ordinary)
        project_reference = _schema("DocumentProjectReferenceRelationship")
        self.assertIn(
            "kind: { type: string, const: project_reference }",
            project_reference,
        )
        self.assertIn(
            '$ref: "#/components/schemas/ProjectReferenceType"',
            project_reference,
        )

    def test_content_contract_requires_committed_audit_and_secure_headers(self) -> None:
        content = _block(self.ROUTES[7])
        self.assertIn("appends and", content)
        self.assertIn("commits an audit event", content)
        self.assertIn("returns the verified bytes directly", content)
        self.assertIn("share-grant rows never", content)
        for header in (
            "Cache-Control",
            "X-Content-Type-Options",
            "Content-Disposition",
            "Content-Length",
            "Content-Security-Policy",
            "Referrer-Policy",
            "X-Request-ID",
            "X-Trace-ID",
            "Idempotency-Replayed",
        ):
            self.assertIn(f"{header}:", content)
        self.assertIn('const: "private, no-store"', content)
        self.assertIn("const: nosniff", content)
        self.assertIn("const: no-referrer", content)
        self.assertIn("sandbox; default-src 'none'", content)
        self.assertIn('"*/*":', content)
        for response in (
            "DocumentListResult",
            "DocumentQueryResult",
            "DocumentCommandResult",
            "DocumentReleaseCommandResult",
            "DocumentCapabilityResult",
        ):
            with self.subTest(response=response):
                block = _block(f"    {response}:")
                self.assertIn("Cache-Control:", block)
                self.assertIn('"^[A-Za-z0-9._:-]+$"', block)

    def test_ownership_separates_root_revision_file_lock_and_future_authority(
        self,
    ) -> None:
        for object_name in (
            "ControlledDocument",
            "DocumentPolicy",
            "DocumentPolicyVersion",
            "DocumentRevision",
            "DocumentRevisionFile",
            "DocumentRelationship",
            "DocumentLockEvent",
            "DocumentCommandIdempotency",
            "DocumentShareGrant",
            "FileRevision",
        ):
            with self.subTest(object_name=object_name):
                self.assertIn(f"  {object_name}:", OWNERSHIP)
        self.assertIn(
            "scan_state: {owner: NPI_ONE_SCAN_SERVICE",
            OWNERSHIP,
        )
        self.assertIn(
            "external_identity_and_retrieval_authority: "
            "{owner: FUTURE_EXTERNAL_ACCESS_POLICY",
            OWNERSHIP,
        )
        self.assertIn(
            "conflict: NEVER_PERSIST_OR_EXPOSE",
            OWNERSHIP,
        )
        self.assertIn(
            "connector_state: {owner: FUTURE_CAD_PDM_ADAPTER",
            OWNERSHIP,
        )
        self.assertIn(
            "raw_idempotency_key: {owner: REQUEST_TRANSPORT",
            OWNERSHIP,
        )
        self.assertIn("conflict: NEVER_PERSIST", OWNERSHIP)
        self.assertIn(
            "response_seal_transition: {owner: NPI_ONE_DOCUMENT_COMMAND",
            OWNERSHIP,
        )
        self.assertIn("conflict: ONE_WAY_SEAL", OWNERSHIP)
        for object_name in (
            "DocumentPolicy",
            "DocumentPolicyVersion",
            "ControlledDocument",
            "DocumentRevision",
            "DocumentRevisionFile",
            "DocumentRelationship",
            "DocumentLockEvent",
            "DocumentShareGrant",
            "DocumentCommandIdempotency",
        ):
            with self.subTest(single_owner=object_name):
                block = _ownership_block(f"  {object_name}:")
                self.assertNotIn("owner: [", block)
                self.assertNotIn(
                    "editable_in: [NPI_ONE, ERPNEXT]",
                    block,
                )

    def test_all_local_component_references_resolve(self) -> None:
        references = set(
            re.findall(
                r'\$ref: "#/components/(schemas|parameters|responses)/([^"]+)"',
                CONTRACT,
            )
        )
        for section, name in references:
            with self.subTest(section=section, name=name):
                self.assertEqual(
                    CONTRACT.count(f"    {name}:"),
                    1,
                    f"Missing or duplicate components.{section}.{name}",
                )


if __name__ == "__main__":
    unittest.main()
