from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_phase9_controlled_uat import (
    MANIFEST,
    ControlledUatError,
    load_manifest,
    validate_manifest,
)


class Phase9ControlledUatTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def write_manifest(self, value: object) -> Path:
        temporary = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            delete=False,
        )
        with temporary:
            json.dump(value, temporary)
        path = Path(temporary.name)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def test_repository_manifest_passes_with_honest_ninety_percent_ratio(self) -> None:
        result = validate_manifest()
        self.assertEqual(result["evidenceClass"], "CONTROLLED_NON_PRODUCTION_TECHNICAL_UAT")
        self.assertEqual(result["qualifying"], 18)
        self.assertEqual(result["total"], 20)
        self.assertEqual(result["ratio"], 0.9)
        self.assertEqual(
            [(item["id"], item["ratio"]) for item in result["scenarios"]],
            [("AT-01", 0.9), ("AT-02", 0.9)],
        )
        self.assertFalse(result["productionContact"])
        self.assertRegex(result["manifestSha256"], r"^[0-9a-f]{64}$")

    def test_duplicate_or_unknown_manifest_keys_fail_closed(self) -> None:
        source = MANIFEST.read_text(encoding="utf-8")
        duplicate = source.replace(
            '"schemaVersion": "p9-08-controlled-uat.v1",',
            '"schemaVersion": "p9-08-controlled-uat.v1", "schemaVersion": "p9-08-controlled-uat.v1",',
            1,
        )
        path = self.write_manifest({})
        path.write_text(duplicate, encoding="utf-8")
        with self.assertRaisesRegex(ControlledUatError, "duplicate manifest key"):
            load_manifest(path)
        changed = {**self.manifest, "untrusted": True}
        with self.assertRaisesRegex(ControlledUatError, "manifest keys drifted"):
            validate_manifest(self.write_manifest(changed))

    def test_real_pilot_project_or_adoption_claim_fails_closed(self) -> None:
        for claim in ("realPilot", "realProject", "realUserAdoption"):
            with self.subTest(claim=claim):
                changed = copy.deepcopy(self.manifest)
                changed["claims"][claim] = True
                with self.assertRaisesRegex(ControlledUatError, "claims overstate"):
                    validate_manifest(self.write_manifest(changed))

    def test_unapproved_route_or_below_threshold_ratio_fails_closed(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["scenarios"][0]["activities"][1]["routeTemplate"] = "/tooling/legacy"
        with self.assertRaisesRegex(ControlledUatError, "not in one approved Project context"):
            validate_manifest(self.write_manifest(changed))

        changed = copy.deepcopy(self.manifest)
        for index in (1, 2):
            activity = changed["scenarios"][0]["activities"][index]
            activity["surface"] = "outside_context"
            activity["routeTemplate"] = "/reports"
        with self.assertRaisesRegex(ControlledUatError, "workflow ratio is below"):
            validate_manifest(self.write_manifest(changed))

    def test_missing_evidence_file_or_selector_fails_closed(self) -> None:
        changed = copy.deepcopy(self.manifest)
        evidence = changed["scenarios"][0]["activities"][0]["evidence"][0]
        evidence["path"] = "frontend/tests/e2e/not-present.spec.ts"
        with self.assertRaisesRegex(ControlledUatError, "evidence file is missing"):
            validate_manifest(self.write_manifest(changed))

        changed = copy.deepcopy(self.manifest)
        evidence = changed["scenarios"][0]["activities"][0]["evidence"][0]
        evidence["selector"] = "selector that is deliberately absent"
        with self.assertRaisesRegex(ControlledUatError, "selector is absent"):
            validate_manifest(self.write_manifest(changed))

    def test_duplicate_activity_or_missing_required_family_fails_closed(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["scenarios"][1]["activities"][0]["id"] = "AT01-01"
        with self.assertRaisesRegex(ControlledUatError, "activity ID is invalid|duplicate activity ID"):
            validate_manifest(self.write_manifest(changed))

        changed = copy.deepcopy(self.manifest)
        changed["scenarios"][1]["activities"][2]["families"] = ["documents_baselines"]
        with self.assertRaisesRegex(ControlledUatError, "required evidence families are missing"):
            validate_manifest(self.write_manifest(changed))

    def test_each_scenario_requires_golden_and_fault_flows(self) -> None:
        changed = copy.deepcopy(self.manifest)
        for activity in changed["scenarios"][0]["activities"]:
            activity["flow"] = "golden"
        with self.assertRaisesRegex(ControlledUatError, "needs golden and fault flows"):
            validate_manifest(self.write_manifest(changed))


if __name__ == "__main__":
    unittest.main()
