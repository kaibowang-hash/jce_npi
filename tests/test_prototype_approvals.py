from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "verify_prototype_approvals.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location(
        "verify_prototype_approvals", MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load prototype approval verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PrototypeApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = _load_verifier()

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "frontend" / "src").mkdir(parents=True)
        (self.root / "frontend" / "src" / "prototype.tsx").write_text(
            "export const prototype = true;\n",
            encoding="utf-8",
        )
        self.source_files = ["frontend/src/prototype.tsx"]

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def manifest(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "taskId": "R1-06",
            "prototypeId": "my-work-grid-reset-undo",
            "prototypeRevision": "r1-06-stage-1-v1",
            "requirements": ["UX-026", "UX-030"],
            "route": (
                "/demo/work?prototype=my-work-grid-reset-undo&undoState=review"
            ),
            "eligibleAction": "current_actor_closed_my_work_view_grid_reset",
            "ineligibleActions": list(self.verifier.INELIGIBLE_ACTIONS),
            "reviewStates": list(self.verifier.REVIEW_STATES),
            "prototypeDurationSeconds": 10,
            "productionDurationSeconds": None,
            "status": "PENDING_PRODUCT_OWNER",
            "backendImplementationAuthorized": False,
            "approval": {
                "productOwnerIdentifier": None,
                "approvedAt": None,
                "approvalEvidence": None,
                "approvedPrototypeRevision": None,
                "approvedEligibleAction": None,
                "approvedReviewStates": None,
            },
            "sourceFiles": self.source_files,
            "sourceDigest": self.verifier.source_digest(
                self.root, self.source_files
            ),
        }

    def test_pending_manifest_is_truthful_but_cannot_open_backend_stage(self) -> None:
        manifest = self.manifest()
        validated = self.verifier.validate_manifest(manifest, root=self.root)
        self.assertEqual(validated["status"], "PENDING_PRODUCT_OWNER")
        with self.assertRaisesRegex(
            self.verifier.PrototypeApprovalError,
            "blocked pending Product Owner approval",
        ):
            self.verifier.validate_manifest(
                manifest,
                root=self.root,
                require_backend_approval=True,
            )

    def test_pending_manifest_rejects_fabricated_authorization(self) -> None:
        manifest = self.manifest()
        manifest["backendImplementationAuthorized"] = True
        with self.assertRaisesRegex(
            self.verifier.PrototypeApprovalError,
            "pending approval cannot authorize",
        ):
            self.verifier.validate_manifest(manifest, root=self.root)

    def test_source_drift_invalidates_the_review_revision(self) -> None:
        manifest = self.manifest()
        (self.root / self.source_files[0]).write_text(
            "export const prototype = false;\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            self.verifier.PrototypeApprovalError,
            "source digest does not match",
        ):
            self.verifier.validate_manifest(manifest, root=self.root)

    def test_complete_approved_manifest_opens_only_its_exact_revision(self) -> None:
        evidence_path = (
            self.root
            / "implementation"
            / "evidence"
            / "reconciliation"
            / "approval.md"
        )
        evidence_path.parent.mkdir(parents=True)
        evidence_path.write_text("# Actual approval\n", encoding="utf-8")
        manifest = self.manifest()
        manifest.update(
            {
                "productionDurationSeconds": 30,
                "status": "APPROVED",
                "backendImplementationAuthorized": True,
                "approval": {
                    "productOwnerIdentifier": "product-owner",
                    "approvedAt": "2026-07-30T12:00:00Z",
                    "approvalEvidence": (
                        "implementation/evidence/reconciliation/approval.md"
                    ),
                    "approvedPrototypeRevision": "r1-06-stage-1-v1",
                    "approvedEligibleAction": (
                        "current_actor_closed_my_work_view_grid_reset"
                    ),
                    "approvedReviewStates": list(self.verifier.REVIEW_STATES),
                },
            }
        )
        validated = self.verifier.validate_manifest(
            manifest,
            root=self.root,
            require_backend_approval=True,
        )
        self.assertEqual(validated["status"], "APPROVED")

    def test_manifest_directory_rejects_duplicate_prototype_ids(self) -> None:
        manifest_directory = (
            self.root / "implementation" / "prototype-approvals"
        )
        manifest_directory.mkdir(parents=True)
        manifest = self.manifest()
        for name in ("first.json", "second.json"):
            (manifest_directory / name).write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
        with self.assertRaisesRegex(
            self.verifier.PrototypeApprovalError,
            "duplicate prototype ID",
        ):
            self.verifier.load_manifests(
                root=self.root,
                manifest_directory=manifest_directory,
            )
