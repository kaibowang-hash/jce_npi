import { expect, test } from "@playwright/test";

import {
  parseRoute,
  validateInternalNavigationTarget,
} from "../../src/app/router";
import manifest from "../../../implementation/uat/p9-08-controlled-uat.json" with { type: "json" };

const projectGlobalId = "11111111-1111-4111-8111-111111111111";
const gateGlobalId = "22222222-2222-4222-8222-222222222222";
const toolingMasterGlobalId = "33333333-3333-4333-8333-333333333333";
const origin = "http://127.0.0.1:4173";

function concreteRoute(template: string): string {
  return template
    .replace("{projectGlobalId}", projectGlobalId)
    .replace("{gateGlobalId}", gateGlobalId)
    .replace("{toolingMasterGlobalId}", toolingMasterGlobalId);
}

function routeLocation(path: string): Location {
  const url = new URL(path, origin);
  return {
    hash: url.hash,
    pathname: url.pathname,
    search: url.search,
  } as Location;
}

test.describe("P9-08 controlled full-product UAT context", () => {
  test("classifies the fixed AT-01 and AT-02 activity routes without an adoption claim", () => {
    expect(manifest.evidenceClass).toBe(
      "CONTROLLED_NON_PRODUCTION_TECHNICAL_UAT",
    );
    expect(manifest.claims).toEqual({
      environment: "representative_non_production",
      realPilot: false,
      realProject: false,
      realUserAdoption: false,
    });

    let qualifyingTotal = 0;
    let activityTotal = 0;
    for (const scenario of manifest.scenarios) {
      let qualifying = 0;
      const flows = new Set<string>();
      expect(scenario.activities).toHaveLength(10);
      for (const activity of scenario.activities) {
        const path = concreteRoute(activity.routeTemplate);
        expect(validateInternalNavigationTarget(path, origin)).toBe(path);
        const parsed = parseRoute(routeLocation(path));
        flows.add(activity.flow);
        if (activity.surface === "my_work") {
          expect(parsed.screen).toBe("work");
          expect(parsed.projectGlobalId).toBeNull();
          qualifying += 1;
        } else if (activity.surface === "project_context") {
          expect(parsed.projectGlobalId).toBe(projectGlobalId);
          expect([
            "project",
            "gate",
            "tooling",
            "trial",
            "execution",
          ]).toContain(parsed.screen);
          qualifying += 1;
        } else {
          expect(activity.surface).toBe("outside_context");
          expect(path).toBe("/reports");
          expect(parsed.screen).toBe("portfolio");
          expect(parsed.projectGlobalId).toBeNull();
        }
      }
      expect(flows).toEqual(new Set(["golden", "fault"]));
      expect(qualifying / scenario.activities.length).toBeGreaterThanOrEqual(
        manifest.threshold,
      );
      qualifyingTotal += qualifying;
      activityTotal += scenario.activities.length;
    }

    expect(manifest.scenarios.map((scenario) => scenario.id)).toEqual([
      "AT-01",
      "AT-02",
    ]);
    expect(qualifyingTotal).toBe(18);
    expect(activityTotal).toBe(20);
    expect(qualifyingTotal / activityTotal).toBe(0.9);
  });

  test("keeps reporting outside the Project-context numerator", () => {
    for (const scenario of manifest.scenarios) {
      const outside = scenario.activities.filter(
        (activity) => activity.surface === "outside_context",
      );
      expect(outside).toHaveLength(1);
      expect(outside[0]?.routeTemplate).toBe("/reports");
      expect(outside[0]?.families).toContain("reporting_collaboration");
    }
  });
});
