import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type {
  ProjectCreationContext,
  ProjectCreationDataSource,
} from "../../src/api/project-data-source";
import { NpiTransportError } from "../../src/api/http";
import { ProjectCreateDialog } from "../../src/components/project-create-dialog";
import { renderWithLocale } from "../support/render";
import { projectCockpitFixture } from "../support/project-fixture";
import { messagesForTest } from "../translate";
import { LiveERPMasterDataSource } from "../../src/api/erp-master-data-source";
import { masterPage } from "../support/erp-master-fixture";

const context: ProjectCreationContext = {
  ownerUserId: "manager@example.invalid",
  templates: [
    {
      applicableProjectTypes: ["new_tool", "tool_change"],
      code: "NEW-TOOL",
      expectedVersion: 2,
      globalId: "11111111-1111-4111-8111-111111111111",
      referenceRules: [],
      title: "New Tool Project",
      version: 1,
    },
  ],
  tenantId: "TENANT-A",
};

function sessionResponse(): Response {
  return new Response(
    JSON.stringify({
      allowedLanguages: ["en", "zh", "zh-TW"],
      canCreateProject: true,
      catalog: {
        language: "en",
        messages: messagesForTest("en"),
        version: "a".repeat(64),
      },
      csrfToken: "c".repeat(32),
      deploymentEnvironment: "production",
      isSystemManager: false,
      language: "en",
      preferences: { navigationCollapsed: false },
      userId: "manager@example.invalid",
    }),
  );
}

function dataSource(
  loadCreationContext: ProjectCreationDataSource["loadCreationContext"] = vi
    .fn()
    .mockResolvedValue(context),
): ProjectCreationDataSource {
  return {
    create: vi.fn().mockResolvedValue(projectCockpitFixture()),
    loadCreationContext,
  };
}

describe("Project create dialog", () => {
  it("selects the ERP customer required by a published template", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sessionResponse()));
    const template = context.templates[0];
    if (!template) throw new Error("Template fixture missing");
    const source = dataSource(() =>
      Promise.resolve({
        ...context,
        templates: [
          {
            ...template,
            referenceRules: [
              { type: "customer", required: true, allowMultiple: false },
            ],
          },
        ],
      }),
    );
    const create = vi.spyOn(source, "create");
    const lookup = vi
      .spyOn(LiveERPMasterDataSource.prototype, "load")
      .mockImplementation((kind) => Promise.resolve(masterPage(kind)));
    const user = userEvent.setup();
    renderWithLocale(
      <ProjectCreateDialog
        dataSource={source}
        navigate={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await user.type(
      await screen.findByRole("textbox", { name: "Business code" }),
      "P-26002",
    );
    await user.type(
      screen.getByRole("textbox", { name: "Project title" }),
      "Program Beta",
    );
    expect(
      screen.getByRole("button", { name: "Create project" }),
    ).toBeDisabled();
    await user.click(screen.getByRole("combobox", { name: "Customer" }));
    await user.click(
      await screen.findByRole("option", {
        name: "SYNTHETIC-CUSTOMER — Synthetic customer",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Create project" }));
    await waitFor(() => {
      expect(create).toHaveBeenCalledWith(
        expect.objectContaining({ customerSourceKey: "SYNTHETIC-CUSTOMER" }),
        expect.anything(),
        expect.anything(),
      );
    });
    lookup.mockRestore();
  });
  it("creates a controlled draft for the current projected ERPNext user", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sessionResponse()));
    const create = vi
      .fn<ProjectCreationDataSource["create"]>()
      .mockResolvedValue(projectCockpitFixture());
    const source: ProjectCreationDataSource = {
      create,
      loadCreationContext: vi.fn().mockResolvedValue(context),
    };
    const navigate = vi.fn<(target: string) => void>();
    const user = userEvent.setup();

    renderWithLocale(
      <ProjectCreateDialog
        dataSource={source}
        navigate={navigate}
        onClose={vi.fn()}
      />,
    );

    const dialog = await screen.findByRole("dialog", {
      name: "Create project",
    });
    await user.type(
      await within(dialog).findByRole("textbox", { name: "Business code" }),
      "P-26001",
    );
    await user.type(
      within(dialog).getByRole("textbox", { name: "Project title" }),
      "Program Alpha",
    );
    await user.selectOptions(
      within(dialog).getByRole("combobox", { name: "Project type" }),
      "tool_change",
    );
    await waitFor(() => {
      expect(
        within(dialog).getByRole("button", { name: "Create project" }),
      ).toBeEnabled();
    });
    await user.click(
      within(dialog).getByRole("button", { name: "Create project" }),
    );

    await waitFor(() => {
      expect(create).toHaveBeenCalledTimes(1);
    });
    const call = create.mock.calls.at(0);
    if (!call) throw new Error("Expected one Project creation call.");
    expect(call[0]).toEqual({
      businessCode: "P-26001",
      expectedVersion: 2,
      projectType: "tool_change",
      targetSop: call[0].targetSop,
      templateGlobalId: "11111111-1111-4111-8111-111111111111",
      templateVersion: 1,
      title: "Program Alpha",
    });
    expect(call[0].targetSop).toMatch(/^\d{4}-\d{2}-\d{2}$/u);
    expect(call[1]).toEqual(context);
    expect(call[2].csrfToken).toBe("c".repeat(32));
    expect(call[2].idempotencyKey).toMatch(/^[0-9a-f-]{36}$/u);
    expect(call[2].signal).toBeInstanceOf(AbortSignal);
    expect(navigate).toHaveBeenCalledWith(
      `/projects/${projectCockpitFixture().project.globalId}`,
    );
  });

  it("retries a failed context load and closes with Escape", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sessionResponse()));
    const load = vi
      .fn<ProjectCreationDataSource["loadCreationContext"]>()
      .mockRejectedValueOnce(
        new NpiTransportError("network", "load-failed", "request"),
      )
      .mockResolvedValueOnce(context);
    const onClose = vi.fn();
    const user = userEvent.setup();

    renderWithLocale(
      <ProjectCreateDialog
        dataSource={dataSource(load)}
        navigate={vi.fn()}
        onClose={onClose}
      />,
    );

    await user.click(await screen.findByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("textbox", { name: "Business code" }),
    ).toBeVisible();
    expect(load).toHaveBeenCalledTimes(2);
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("blocks templates with required references and handles an empty catalog", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sessionResponse()));
    const source = dataSource(
      vi.fn().mockResolvedValue({
        ...context,
        templates: [
          {
            ...context.templates[0],
            referenceRules: [
              { allowMultiple: false, required: true, type: "product" },
            ],
          },
        ],
      }),
    );
    const { unmount } = renderWithLocale(
      <ProjectCreateDialog
        dataSource={source}
        navigate={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(
      await screen.findByText(
        "This template requires project references and is not available in quick create.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Create project" }),
    ).toBeDisabled();

    unmount();
    renderWithLocale(
      <ProjectCreateDialog
        dataSource={dataSource(
          vi.fn().mockResolvedValue({ ...context, templates: [] }),
        )}
        navigate={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(
      await screen.findByText("No published project template is available."),
    ).toBeVisible();
  });
});
