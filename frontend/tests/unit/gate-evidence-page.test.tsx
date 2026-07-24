import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { GateEvidenceDataSource } from "../../src/api/gate-evidence-data-source";
import {
  NpiApiError,
  NpiTransportError,
  type ProblemDetails,
} from "../../src/api/http";
import type { GateEvidenceViewModel } from "../../src/domain/view-models";
import GateEvidencePage from "../../src/pages/gate-evidence-page";
import { gateEvidenceFixture } from "../support/gate-evidence-fixture";
import { renderWithLocale } from "../support/render";

function problem(status: number, code: string, retryable = false): NpiApiError {
  const value: ProblemDetails = {
    type: `urn:npi:problem:${code.toLowerCase()}`,
    title: `Controlled ${code} response`,
    status,
    code,
    traceId: `trace-${code.toLowerCase()}`,
    retryable,
  };
  return new NpiApiError(value);
}

function resolvedDataSource(
  view: GateEvidenceViewModel,
): GateEvidenceDataSource {
  return {
    load: vi.fn(() => Promise.resolve(view)),
  };
}

function rejectedDataSource(error: Error): GateEvidenceDataSource {
  return {
    load: vi.fn(() => Promise.reject(error)),
  };
}

function renderPage(
  dataSource: GateEvidenceDataSource,
  navigate = vi.fn<(target: string) => void>(),
): {
  fixture: GateEvidenceViewModel;
  navigate: ReturnType<typeof vi.fn<(target: string) => void>>;
} {
  const fixture = gateEvidenceFixture();
  renderWithLocale(
    <GateEvidencePage
      dataSource={dataSource}
      gateGlobalId={fixture.gate.globalId}
      navigate={navigate}
      projectGlobalId={fixture.project.globalId}
    />,
  );
  return { fixture, navigate };
}

describe("live Gate evidence workspace", () => {
  it("renders only validated frozen requirements and exact safe evidence metadata", async () => {
    const fixture = gateEvidenceFixture();
    const dataSource = resolvedDataSource(fixture);
    renderPage(dataSource);

    expect(
      screen.getByRole("status", { name: "Loading Gate evidence workspace" }),
    ).toHaveAttribute("aria-busy", "true");
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: /G1 \/ SYN-PROJECT-001 Synthetic initiation evidence/u,
      }),
    ).toBeVisible();
    expect(dataSource.load).toHaveBeenCalledWith(
      fixture.project.globalId,
      fixture.gate.globalId,
      expect.any(AbortSignal),
    );
    expect(screen.getByText("Required requirements")).toBeVisible();
    expect(screen.getByText("Unsafe scan results")).toBeVisible();
    expect(
      screen.getAllByText("Synthetic design baseline").length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("Exact evidence attached")).toBeVisible();
    expect(screen.getByText("3".repeat(64))).toBeVisible();
    expect(document.body).not.toHaveTextContent("/private/files/");
    expect(
      screen.queryByRole("button", { name: "Review impact and decide" }),
    ).toBeNull();
    expect(document.body).not.toHaveTextContent("Decision options");
    expect(document.body).not.toHaveTextContent("Prototype command");
    expect(
      document.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(0);
  });

  it("selects requirements and preserves the real file scan metadata", async () => {
    const user = userEvent.setup();
    renderPage(resolvedDataSource(gateEvidenceFixture()));
    await screen.findByRole("heading", {
      level: 1,
      name: /Synthetic initiation evidence/u,
    });

    await user.click(
      screen.getByRole("button", {
        name: /DIMENSIONAL_REPORT Synthetic dimensional report/u,
      }),
    );
    const evidenceTable = screen.getByRole("table", {
      name: "Controlled evidence",
    });
    expect(
      within(evidenceTable).getByText("Private file revision"),
    ).toBeVisible();
    expect(within(evidenceTable).getByText("Scan pending")).toBeVisible();
    expect(screen.getByText("SYN-DIMENSIONAL-REPORT.pdf")).toBeVisible();
    expect(screen.getByText("application/pdf")).toBeVisible();
    expect(
      screen.getAllByText("quality.lead@example.invalid").length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("4".repeat(64))).toBeVisible();

    await user.click(
      screen.getByRole("button", {
        name: /CUSTOMER_CONFIRMATION Synthetic customer confirmation/u,
      }),
    );
    expect(
      screen.getByText("No controlled evidence is attached."),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Select a requirement with evidence to inspect its exact controlled reference.",
      ),
    ).toBeVisible();
  });

  it("renders a truthful read-only and empty-evidence workspace", async () => {
    const fixture = gateEvidenceFixture();
    const requirements = fixture.requirements.map((requirement) => ({
      ...requirement,
      evidenceState: "missing" as const,
      evidence: [],
    }));
    const empty: GateEvidenceViewModel = {
      ...fixture,
      requirements,
      summary: {
        requiredCount: 2,
        missingRequiredCount: 2,
        unsafeScanCount: 0,
        evidenceCount: 0,
      },
    };
    renderPage(resolvedDataSource(empty));

    expect(
      await screen.findByText(
        "You have view-only access. Evidence attachment is not available in this workspace.",
      ),
    ).toBeVisible();
    expect(
      screen.getByText(
        "This Gate has frozen requirements but no controlled evidence references.",
      ),
    ).toBeVisible();
    expect(screen.getByText("Required evidence is missing")).toBeVisible();
    expect(
      screen.getAllByText("No controlled evidence is attached.").length,
    ).toBeGreaterThan(0);
  });

  it("renders business data as text without executable markup", async () => {
    const fixture = gateEvidenceFixture();
    const unsafe = '<img src=x onerror="globalThis.compromised=true">';
    const view: GateEvidenceViewModel = {
      ...fixture,
      gate: { ...fixture.gate, title: unsafe },
      requirements: fixture.requirements.map((requirement, index) =>
        index === 0 ? { ...requirement, title: unsafe } : requirement,
      ),
    };
    renderPage(resolvedDataSource(view));

    expect(await screen.findAllByText(unsafe)).not.toHaveLength(0);
    expect(document.querySelector(".object-header img")).toBeNull();
    expect(
      (globalThis as typeof globalThis & { compromised?: boolean }).compromised,
    ).toBeUndefined();
  });

  it.each([
    [404, "GATE_EVIDENCE_UNAVAILABLE", "Gate evidence is unavailable"],
    [
      403,
      "GATE_EVIDENCE_ACCESS_DENIED",
      "Gate evidence access is not available",
    ],
    [422, "REQUEST_VALIDATION_FAILED", "The Gate evidence address is invalid"],
  ] as const)(
    "maps HTTP %s to a protected terminal state",
    async (status, code, heading) => {
      const { fixture } = renderPage(rejectedDataSource(problem(status, code)));

      expect(
        await screen.findByRole("heading", { level: 1, name: heading }),
      ).toBeVisible();
      expect(
        screen.getByRole("alert", { name: "Error details" }),
      ).toHaveTextContent(`trace-${code.toLowerCase()}`);
      expect(document.body).not.toHaveTextContent(fixture.gate.title);
      expect(document.body).not.toHaveTextContent("SYN-DIMENSIONAL-REPORT.pdf");
      expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    },
  );

  it("treats an invalid client route as validation without a blind retry", async () => {
    const fixture = gateEvidenceFixture();
    const navigate = vi.fn<(target: string) => void>();
    const user = userEvent.setup();
    renderWithLocale(
      <GateEvidencePage
        dataSource={rejectedDataSource(
          new NpiTransportError(
            "request_not_ready",
            "client-gate-evidence-address",
            "client",
          ),
        )}
        gateGlobalId="not-a-uuid"
        navigate={navigate}
        projectGlobalId={fixture.project.globalId}
      />,
    );

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "The Gate evidence address is invalid",
      }),
    ).toBeVisible();
    expect(screen.getByText("client-gate-evidence-address")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Return to My Work" }));
    expect(navigate).toHaveBeenCalledWith("/work");
  });

  it("retries a trace-aware conflict and replaces it with current evidence", async () => {
    const fixture = gateEvidenceFixture();
    const load = vi
      .fn<GateEvidenceDataSource["load"]>()
      .mockRejectedValueOnce(problem(409, "VERSION_CONFLICT"))
      .mockResolvedValueOnce(fixture);
    const user = userEvent.setup();
    renderPage({ load });

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "The Gate evidence view is out of date",
      }),
    ).toBeVisible();
    expect(screen.getByText("trace-version_conflict")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Reload Gate evidence" }),
    );
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: /Synthetic initiation evidence/u,
      }),
    ).toBeVisible();
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("retries a retryable failure without hiding its trace", async () => {
    const fixture = gateEvidenceFixture();
    const load = vi
      .fn<GateEvidenceDataSource["load"]>()
      .mockRejectedValueOnce(problem(503, "GATE_QUERY_UNAVAILABLE", true))
      .mockResolvedValueOnce(fixture);
    const user = userEvent.setup();
    renderPage({ load });

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Gate evidence could not be loaded",
      }),
    ).toBeVisible();
    expect(screen.getByText("trace-gate_query_unavailable")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: /Synthetic initiation evidence/u,
      }),
    ).toBeVisible();
  });

  it("returns from a terminal state to the authorized Project route", async () => {
    const navigate = vi.fn<(target: string) => void>();
    const { fixture } = renderPage(
      rejectedDataSource(problem(404, "GATE_EVIDENCE_UNAVAILABLE")),
      navigate,
    );
    const user = userEvent.setup();

    await screen.findByRole("heading", {
      level: 1,
      name: "Gate evidence is unavailable",
    });
    await user.click(screen.getByRole("button", { name: "Return to project" }));
    expect(navigate).toHaveBeenLastCalledWith(
      `/projects/${fixture.project.globalId}`,
    );
  });
});
