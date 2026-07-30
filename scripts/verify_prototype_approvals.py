#!/usr/bin/env python3
"""Validate versioned prototype approval manifests without inventing approval."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIRECTORY = ROOT / "implementation" / "prototype-approvals"

REVIEW_STATES = [
    "review",
    "confirmation",
    "available",
    "processing",
    "restored",
    "expired",
    "conflict",
    "denied",
    "retryable",
    "final",
]
INELIGIBLE_ACTIONS = [
    "gate_decision_or_reopen",
    "release_publish_or_baseline",
    "registered_revision_mutation",
    "business_lifecycle_transition",
    "external_execution",
    "delete_cancel_or_void",
    "unapproved_bulk_action",
]
MANIFEST_FIELDS = {
    "schemaVersion",
    "taskId",
    "prototypeId",
    "prototypeRevision",
    "requirements",
    "route",
    "eligibleAction",
    "ineligibleActions",
    "reviewStates",
    "prototypeDurationSeconds",
    "productionDurationSeconds",
    "status",
    "backendImplementationAuthorized",
    "approval",
    "sourceFiles",
    "sourceDigest",
}
APPROVAL_FIELDS = {
    "productOwnerIdentifier",
    "approvedAt",
    "approvalEvidence",
    "approvedPrototypeRevision",
    "approvedEligibleAction",
    "approvedReviewStates",
}


class PrototypeApprovalError(ValueError):
    """Raised when a prototype manifest is unsafe or internally inconsistent."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PrototypeApprovalError(message)


def _closed_object(
    value: Any,
    expected_fields: set[str],
    label: str,
) -> dict[str, Any]:
    _require(isinstance(value, dict), f"{label} must be an object")
    fields = set(value)
    _require(
        fields == expected_fields,
        f"{label} fields differ: expected {sorted(expected_fields)}, got {sorted(fields)}",
    )
    return value


def _repository_path(root: Path, relative_path: str, label: str) -> Path:
    _require(
        isinstance(relative_path, str)
        and relative_path
        and not Path(relative_path).is_absolute(),
        f"{label} must be a non-empty repository-relative path",
    )
    candidate = (root / relative_path).resolve()
    _require(
        candidate.is_relative_to(root.resolve()),
        f"{label} escapes the repository",
    )
    return candidate


def source_digest(root: Path, source_files: list[str]) -> str:
    digest = hashlib.sha256()
    for relative_path in source_files:
        source = _repository_path(root, relative_path, "source file")
        _require(source.is_file(), f"prototype source file is missing: {relative_path}")
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith(("Z", "+00:00")):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_manifest(
    manifest: Any,
    *,
    root: Path = ROOT,
    require_backend_approval: bool = False,
) -> dict[str, Any]:
    document = _closed_object(manifest, MANIFEST_FIELDS, "prototype manifest")
    _require(document["schemaVersion"] == 1, "unsupported prototype schema")
    _require(document["taskId"] == "R1-06", "unexpected prototype task")
    _require(
        document["prototypeId"] == "my-work-grid-reset-undo",
        "unexpected prototype identity",
    )
    _require(
        isinstance(document["prototypeRevision"], str)
        and re.fullmatch(r"r1-06-stage-1-v[1-9][0-9]*", document["prototypeRevision"])
        is not None,
        "prototype revision must be a closed R1-06 Stage 1 revision",
    )
    _require(
        document["requirements"] == ["UX-026", "UX-030"],
        "prototype requirement allocation drifted",
    )
    _require(
        document["route"]
        == "/demo/work?prototype=my-work-grid-reset-undo&undoState=review",
        "prototype route drifted",
    )
    _require(
        document["eligibleAction"]
        == "current_actor_closed_my_work_view_grid_reset",
        "eligible action drifted",
    )
    _require(
        document["ineligibleActions"] == INELIGIBLE_ACTIONS,
        "ineligible action set drifted",
    )
    _require(document["reviewStates"] == REVIEW_STATES, "review state set drifted")
    _require(
        isinstance(document["prototypeDurationSeconds"], int)
        and not isinstance(document["prototypeDurationSeconds"], bool)
        and document["prototypeDurationSeconds"] > 0,
        "prototype duration must be a positive integer",
    )
    source_files = document["sourceFiles"]
    _require(
        isinstance(source_files, list)
        and source_files
        and source_files == sorted(set(source_files))
        and all(isinstance(item, str) for item in source_files),
        "source files must be a non-empty sorted unique string list",
    )
    observed_digest = source_digest(root, source_files)
    _require(
        document["sourceDigest"] == observed_digest,
        "prototype source digest does not match the reviewed source files",
    )
    approval = _closed_object(document["approval"], APPROVAL_FIELDS, "approval")

    status = document["status"]
    _require(
        status in {"PENDING_PRODUCT_OWNER", "APPROVED"},
        "prototype approval status is not recognized",
    )
    if status == "PENDING_PRODUCT_OWNER":
        _require(
            document["backendImplementationAuthorized"] is False,
            "pending approval cannot authorize backend implementation",
        )
        _require(
            document["productionDurationSeconds"] is None,
            "pending approval cannot select a production duration",
        )
        _require(
            all(value is None for value in approval.values()),
            "pending approval cannot contain approval facts",
        )
    else:
        _require(
            document["backendImplementationAuthorized"] is True,
            "approved prototype must explicitly authorize backend implementation",
        )
        duration = document["productionDurationSeconds"]
        _require(
            isinstance(duration, int)
            and not isinstance(duration, bool)
            and 0 < duration <= 2_147_483_647,
            "approved production duration must be a positive bounded integer",
        )
        _require(
            isinstance(approval["productOwnerIdentifier"], str)
            and approval["productOwnerIdentifier"].strip()
            and len(approval["productOwnerIdentifier"]) <= 200,
            "approved prototype requires a bounded Product Owner identifier",
        )
        _require(
            _valid_timestamp(approval["approvedAt"]),
            "approved prototype requires a UTC approval timestamp",
        )
        _require(
            approval["approvedPrototypeRevision"] == document["prototypeRevision"],
            "approval is not tied to the current prototype revision",
        )
        _require(
            approval["approvedEligibleAction"] == document["eligibleAction"],
            "approval eligible action drifted",
        )
        _require(
            approval["approvedReviewStates"] == document["reviewStates"],
            "approval review state set drifted",
        )
        evidence = _repository_path(
            root,
            approval["approvalEvidence"],
            "approval evidence",
        )
        _require(evidence.is_file(), "approved prototype evidence is missing")

    if require_backend_approval:
        _require(
            status == "APPROVED"
            and document["backendImplementationAuthorized"] is True,
            "backend implementation is blocked pending Product Owner approval",
        )
    return document


def load_manifests(
    *,
    root: Path = ROOT,
    manifest_directory: Path | None = None,
    require_backend_approval: str | None = None,
) -> list[dict[str, Any]]:
    directory = manifest_directory or root / "implementation" / "prototype-approvals"
    _require(directory.is_dir(), "prototype approval directory is missing")
    paths = sorted(directory.glob("*.json"))
    _require(paths, "no prototype approval manifests were found")
    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in paths:
        document = validate_manifest(
            json.loads(path.read_text(encoding="utf-8")),
            root=root,
            require_backend_approval=False,
        )
        prototype_id = document["prototypeId"]
        _require(prototype_id not in seen, f"duplicate prototype ID: {prototype_id}")
        seen.add(prototype_id)
        validated.append(document)
    if require_backend_approval is not None:
        matching = [
            document
            for document in validated
            if document["prototypeId"] == require_backend_approval
        ]
        _require(matching, "requested prototype approval manifest was not found")
        validate_manifest(
            matching[0],
            root=root,
            require_backend_approval=True,
        )
    return validated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-backend-approval")
    arguments = parser.parse_args()
    try:
        manifests = load_manifests(
            require_backend_approval=arguments.require_backend_approval
        )
    except (json.JSONDecodeError, OSError, PrototypeApprovalError) as error:
        print(f"prototype approval verification failed: {error}", file=sys.stderr)
        return 1
    pending = sum(
        manifest["status"] == "PENDING_PRODUCT_OWNER" for manifest in manifests
    )
    print(
        "prototype approval verification passed: "
        f"{len(manifests)} manifest(s), {pending} pending Product Owner approval"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
