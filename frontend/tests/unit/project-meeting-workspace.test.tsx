import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectMeetingWorkspace } from "../../src/pages/project-meeting-workspace";
import { SyntheticCollaborationDataSource } from "../support/collaboration-fixture";
import { reportingProjectId } from "../support/reporting-fixture";
import { renderWithLocale } from "../support/render";

function enableCommandSession(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            allowedLanguages: ["en", "zh", "zh-TW"],
            catalog: {
              language: "en",
              messages: {},
              version: "9".repeat(64),
            },
            csrfToken: "p902-csrf-token-fixture-00000001",
            language: "en",
            preferences: { navigationCollapsed: false },
            userId: "project.admin@example.invalid",
          }),
          { status: 200 },
        ),
      ),
    ),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  globalThis.localStorage.clear();
});

describe("Project meeting-minute workspace", () => {
  it("creates one immutable minute only after an explicit impact review", async () => {
    enableCommandSession();
    const source = new SyntheticCollaborationDataSource();
    const create = vi.spyOn(source, "createMeeting");
    const user = userEvent.setup();
    renderWithLocale(
      <ProjectMeetingWorkspace
        dataSource={source}
        navigate={vi.fn()}
        projectId={reportingProjectId}
      />,
      "en",
      `/projects/${reportingProjectId}?tab=meetings`,
    );

    expect(
      await screen.findByText(
        "No meeting minutes have been recorded for this Project.",
      ),
    ).toBeVisible();
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Review and create" }),
      ).toBeDisabled();
      expect(
        screen.queryByText(
          "The authenticated session is not ready. Reconcile the session before creating a record.",
        ),
      ).not.toBeInTheDocument();
    });
    await user.type(screen.getByLabelText("Meeting title"), "Synthetic review");
    await user.type(
      screen.getByLabelText("Attendee emails"),
      "project.admin@example.invalid",
    );
    await user.type(
      screen.getByLabelText("Agenda"),
      "Review release readiness",
    );
    await user.type(screen.getByLabelText("Discussion"), "Evidence reviewed");
    await user.type(
      screen.getByLabelText("Decisions"),
      "Proceed with controls",
    );
    await user.click(screen.getByRole("button", { name: "Review and create" }));

    expect(
      screen.getByRole("heading", { name: "Review meeting-minute command" }),
    ).toBeVisible();
    expect(create).not.toHaveBeenCalled();
    await user.click(
      screen.getByRole("button", { name: "Create meeting minute" }),
    );
    expect(
      await screen.findByText(
        "The immutable meeting minute and 0 linked work items were created.",
      ),
    ).toBeVisible();
    expect(create).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Immutable")).toBeVisible();
  });

  it("fails closed when the collaboration source is unavailable", () => {
    renderWithLocale(
      <ProjectMeetingWorkspace
        navigate={vi.fn()}
        projectId={reportingProjectId}
      />,
      "en",
      `/projects/${reportingProjectId}?tab=meetings`,
    );

    expect(
      screen.getByText(
        "The live meeting-minute data source is not configured.",
      ),
    ).toBeVisible();
  });
});
