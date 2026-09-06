import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  ProjectSetupDataSource,
  SetupOptions,
  SetupPolicy,
} from "../../src/api/project-setup-data-source";
import { NpiTransportError } from "../../src/api/http";
import type { ProjectWorkContextViewModel } from "../../src/domain/view-models";
import { ProjectSetupWorkspace } from "../../src/pages/project-setup-workspace";
import { projectWorkContextFixture } from "../support/project-work-fixture";
import { renderWithLocale } from "../support/render";

function adminContext() {
  const value = projectWorkContextFixture();
  return {
    ...value,
    permissions: { ...value.permissions, canAdminister: true },
  };
}
function setup(context = adminContext()) {
  const reference = context.workPolicyRef ?? {
    globalId: "a1000000-0000-4000-8000-000000000001",
    version: 1,
    snapshotHash: "a".repeat(64),
  };
  const policy: SetupPolicy = {
    reference,
    title: "Injection collaboration",
    roleKeys: ["engineering", "quality"],
    wbsLifecycle: {
      initialStateKey: "not_started",
      states: [
        { key: "not_started", labelSource: "Not started", terminal: false },
        { key: "completed", labelSource: "Completed", terminal: true },
      ],
    },
  };
  const catalog: SetupOptions = {
    projectId: context.projectId,
    projectVersion: context.projectVersion,
    policies: [policy],
    nextCursor: null,
  };
  const source = {
    loadOptions: vi.fn<ProjectSetupDataSource["loadOptions"]>(() =>
      Promise.resolve(catalog),
    ),
    execute: vi.fn<ProjectSetupDataSource["execute"]>(() =>
      Promise.resolve({
        projectVersion: context.projectVersion + 1,
        replayed: false,
      }),
    ),
    createDrafts: vi.fn<ProjectSetupDataSource["createDrafts"]>(() =>
      Promise.resolve({
        projectId: context.projectId,
        projectVersion: context.projectVersion,
        templateGlobalId: reference.globalId,
        policyGlobalId: reference.globalId,
        templateVersion: 1,
        policyVersion: 1,
        publicationState: "draft",
      }),
    ),
  } satisfies ProjectSetupDataSource;
  return { source, catalog, policy };
}
function session(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            allowedLanguages: ["en", "zh", "zh-TW"],
            catalog: { language: "en", messages: {}, version: "4".repeat(64) },
            csrfToken: "setup-command-session-fixture-0000000001",
            language: "en",
            preferences: { navigationCollapsed: false },
            userId: "administrator@example.invalid",
          }),
          { status: 200 },
        ),
      ),
    ),
  );
}
function renderSetup(
  context: ProjectWorkContextViewModel,
  source: ProjectSetupDataSource,
  section: "team" | "plan" = "team",
) {
  const onChanged = vi.fn();
  const reload = vi.fn();
  const dirty = vi.fn();
  renderWithLocale(
    <ProjectSetupWorkspace
      context={context}
      dataSource={source}
      section={section}
      onChanged={onChanged}
      reload={reload}
      reportWorkspaceDirty={dirty}
    />,
    "en",
  );
  return { onChanged, reload, dirty };
}
async function fillTeam(): Promise<void> {
  const user = userEvent.setup();
  await user.click(
    screen.getByRole("button", { name: "Add team assignments" }),
  );
  await screen.findByLabelText("Member email 1");
  await user.type(
    screen.getByLabelText("Member email 1"),
    "engineer@example.invalid",
  );
  await user.selectOptions(screen.getByLabelText("Role 1"), "engineering");
  fireEvent.change(screen.getByLabelText("Effective from 1"), {
    target: { value: "2026-09-06" },
  });
  await user.type(
    screen.getByLabelText("Responsibility key 1"),
    "design.review",
  );
}
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Project setup workspace", () => {
  it("initializes role definitions without requesting member accounts or dates", async () => {
    session();
    const context = {
      ...adminContext(),
      initialized: false,
      workPolicyRef: null,
      members: [],
      roleAssignments: [],
      raciAssignments: [],
      substitutions: [],
      wbsItems: [],
      dependencies: [],
      baselines: [],
      baselineComparison: null,
    };
    const { source, policy } = setup(context);
    policy.roleKeys = [
      "engineering",
      "quality",
      "purchasing",
      "sales",
      "warehouse",
      "materials_control",
    ];
    renderSetup(context, source);
    await userEvent.click(
      screen.getByRole("button", { name: "Initialize project roles" }),
    );
    await userEvent.selectOptions(
      await screen.findByLabelText("Published work policy"),
      `${policy.reference.globalId}:${String(policy.reference.version)}`,
    );
    expect(screen.queryByLabelText("Member email 1")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Effective from 1")).not.toBeInTheDocument();
    expect(screen.getByText("Materials control")).toBeVisible();
    await userEvent.click(
      screen.getByRole("button", { name: "Review project setup" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Confirm project setup" }),
    );
    await waitFor(() => {
      expect(source.execute).toHaveBeenCalledWith(
        context.projectId,
        {
          kind: "roles",
          body: {
            expectedProjectVersion: context.projectVersion,
            workPolicyRef: policy.reference,
          },
        },
        expect.anything(),
      );
    });
  });
  it("has no setup commands or configuration fetch for read-only users", () => {
    const context = adminContext();
    context.permissions.canAdminister = false;
    const { source } = setup(context);
    renderSetup(context, source);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(source.loadOptions).not.toHaveBeenCalled();
    expect(source.execute).not.toHaveBeenCalled();
  });
  it("shows the actual configuration destination when no policy is published", async () => {
    const context = adminContext();
    const { source, catalog } = setup(context);
    catalog.policies = [];
    renderSetup(context, source);
    await userEvent.click(
      screen.getByRole("button", { name: "Add team assignments" }),
    );
    expect(
      await screen.findByText("No published Project work policy"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Configure project work policies" }),
    ).toHaveAttribute("href", "/app/npi-project-work-policy-version");
    expect(
      screen.queryByRole("button", { name: "Review project setup" }),
    ).not.toBeInTheDocument();
  });
  it("exposes a failed policy lookup and retries without submitting a setup command", async () => {
    const context = adminContext();
    const { source } = setup(context);
    source.loadOptions.mockRejectedValueOnce(
      new NpiTransportError("network", "catalog-failure-12345678", "client"),
    );
    renderSetup(context, source);
    await userEvent.click(
      screen.getByRole("button", { name: "Add team assignments" }),
    );
    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
    await screen.findByLabelText("Member email 1");
    expect(source.loadOptions).toHaveBeenCalledTimes(2);
    expect(
      screen.queryByRole("button", { name: "Retry" }),
    ).not.toBeInTheDocument();
    expect(source.execute).not.toHaveBeenCalled();
  });
  it("requires session verification before sending any team command", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("session unavailable"))),
    );
    const context = adminContext();
    const { source } = setup(context);
    renderSetup(context, source);
    await fillTeam();
    expect(
      screen.getByRole("button", { name: "Review project setup" }),
    ).toBeDisabled();
    expect(source.execute).not.toHaveBeenCalled();
  });
  it("reviews team assignments, records dirty state and retries the identical command after a lost response", async () => {
    session();
    const context = adminContext();
    const { source } = setup(context);
    const execute = vi
      .fn<ProjectSetupDataSource["execute"]>()
      .mockRejectedValueOnce(
        new NpiTransportError("network", "request-network-test", "request"),
      )
      .mockResolvedValueOnce({
        projectVersion: context.projectVersion + 1,
        replayed: true,
      });
    source.execute = execute;
    const { onChanged, dirty, reload } = renderSetup(context, source);
    await fillTeam();
    await userEvent.click(
      screen.getByRole("button", { name: "Review project setup" }),
    );
    expect(
      await screen.findByRole("dialog", { name: "Review project setup" }),
    ).toBeInTheDocument();
    expect(execute).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm project setup" }),
    );
    await screen.findByRole("button", { name: "Retry exact setup command" });
    expect(screen.getByLabelText("Member email 1")).toBeDisabled();
    await userEvent.click(
      screen.getByRole("button", { name: "Retry exact setup command" }),
    );
    await waitFor(() => {
      expect(execute).toHaveBeenCalledTimes(2);
    });
    expect(execute.mock.calls[1]?.[1]).toEqual(execute.mock.calls[0]?.[1]);
    expect(execute.mock.calls[1]?.[2].idempotencyKey).toBe(
      execute.mock.calls[0]?.[2].idempotencyKey,
    );
    expect(execute.mock.calls[0]?.[1].kind).toBe("team");
    expect(dirty).toHaveBeenCalledWith(
      expect.objectContaining({ objectIdentity: `${context.projectId}:setup` }),
    );
    await waitFor(() => {
      expect(onChanged).toHaveBeenCalledWith(context.projectVersion + 1);
    });
    expect(reload).toHaveBeenCalled();
  });
  it("keeps persisted plan identities and dependencies when editing dates", async () => {
    session();
    const context = adminContext();
    const { source } = setup(context);
    renderSetup(context, source, "plan");
    await userEvent.click(
      screen.getByRole("button", { name: "Edit project plan" }),
    );
    await screen.findByLabelText("Planned finish 1");
    expect(
      screen.getByRole("button", { name: "Remove plan item 1" }),
    ).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Planned finish 1"), {
      target: { value: "2026-09-30" },
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Review project setup" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Confirm project setup" }),
    );
    await waitFor(() => {
      expect(source.execute).toHaveBeenCalledOnce();
    });
    const command = vi.mocked(source.execute).mock.calls[0]?.[1];
    expect(command?.kind).toBe("plan");
    if (command?.kind !== "plan") throw new Error("Expected plan command");
    expect(command.body.items[0]?.globalId).toBe(context.wbsItems[0]?.globalId);
    expect(command.body.items[0]?.plannedFinish).toBe("2026-09-30");
    expect(command.body.items[0]).not.toHaveProperty("projectId");
    expect(command.body.items[0]).not.toHaveProperty("version");
    expect(command.body.items[0]).not.toHaveProperty("statusLabelSource");
    expect(command.body.dependencies).toHaveLength(context.dependencies.length);
  });
  it("creates a dated child plan item with an exact retained owner and dependency", async () => {
    session();
    const context = adminContext();
    const { source } = setup(context);
    renderSetup(context, source, "plan");
    await userEvent.click(
      screen.getByRole("button", { name: "Edit project plan" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Add plan item" }),
    );
    await userEvent.type(screen.getByLabelText("Plan code 3"), "G6.3");
    await userEvent.type(
      screen.getByLabelText("Plan title 3"),
      "Pilot release review",
    );
    const owner = context.roleAssignments[0];
    const parent = context.wbsItems[0];
    if (!owner || !parent)
      throw new Error("Missing retained Project references");
    await userEvent.selectOptions(
      screen.getByLabelText("Plan owner 3"),
      owner.globalId,
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Parent item 3"),
      parent.globalId,
    );
    fireEvent.change(screen.getByLabelText("Planned start 3"), {
      target: { value: "2026-09-28" },
    });
    fireEvent.change(screen.getByLabelText("Planned finish 3"), {
      target: { value: "2026-09-28" },
    });
    await userEvent.selectOptions(
      screen.getByLabelText("Plan state 3"),
      "completed",
    );
    fireEvent.change(screen.getByLabelText("Progress 3"), {
      target: { value: "100" },
    });
    await userEvent.click(screen.getByLabelText("Milestone 3"));
    await userEvent.click(
      screen.getByRole("button", { name: "Add dependency" }),
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Predecessor 2"),
      parent.globalId,
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Successor 2"),
      screen
        .getAllByRole("option", { name: "G6.3 Pilot release review" })[0]
        ?.getAttribute("value") ?? "",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Review project setup" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Confirm project setup" }),
    );
    await waitFor(() => {
      expect(source.execute).toHaveBeenCalledOnce();
    });
    const command = source.execute.mock.calls[0]?.[1];
    if (command?.kind !== "plan") throw new Error("Expected a plan command");
    expect(command.body.items[2]).toMatchObject({
      code: "G6.3",
      title: "Pilot release review",
      ownerRoleAssignmentId: owner.globalId,
      parentId: parent.globalId,
      plannedStart: "2026-09-28",
      plannedFinish: "2026-09-28",
      statusKey: "completed",
      progressPercent: 100,
      milestone: true,
    });
    expect(command.body.dependencies[1]?.successorItemId).toBe(
      command.body.items[2]?.globalId,
    );
  });
  it("offers a role-neutral injection plan draft without inventing dates or users", async () => {
    session();
    const context = {
      ...adminContext(),
      wbsItems: [],
      dependencies: [],
      baselines: [],
      baselineComparison: null,
    };
    const { source } = setup(context);
    renderSetup(context, source, "plan");
    await userEvent.click(
      screen.getByRole("button", { name: "Set up project plan" }),
    );
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Use injection-moulding task draft",
      }),
    );
    expect(screen.getAllByLabelText(/^Plan code [0-9]+$/u)).toHaveLength(16);
    expect(screen.getByLabelText("Planned start 1")).toHaveValue("");
    expect(screen.getByLabelText("Plan owner 1")).toHaveValue("");
    expect(source.execute).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Remove plan item 16" }),
    );
    expect(screen.getAllByLabelText(/^Plan code [0-9]+$/u)).toHaveLength(15);
  });
  it("captures an explicitly named baseline only after confirmation", async () => {
    session();
    const context = adminContext();
    const { source } = setup(context);
    renderSetup(context, source, "plan");
    await userEvent.click(
      screen.getByRole("button", { name: "Capture plan baseline" }),
    );
    await userEvent.type(
      await screen.findByLabelText("Baseline label"),
      "Reviewed kickoff plan",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Review project setup" }),
    );
    expect(source.execute).not.toHaveBeenCalled();
    await userEvent.click(
      await screen.findByRole("button", { name: "Confirm project setup" }),
    );
    await waitFor(() => {
      expect(source.execute).toHaveBeenCalledWith(
        context.projectId,
        {
          kind: "baseline",
          body: {
            expectedProjectVersion: context.projectVersion,
            workPolicyRef: context.workPolicyRef,
            label: "Reviewed kickoff plan",
          },
        },
        expect.anything(),
      );
    });
  });
  it("creates unpublished template drafts and provides exact review links", async () => {
    session();
    const context = adminContext();
    const { source } = setup(context);
    renderSetup(context, source);
    await userEvent.click(
      screen.getByRole("button", {
        name: "Injection-moulding collaboration template",
      }),
    );
    await userEvent.type(
      screen.getByLabelText("Template code"),
      "INJECTION-REVIEW",
    );
    await userEvent.type(
      screen.getByLabelText("Template title"),
      "Injection review",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Create template drafts" }),
    );
    await screen.findByText("Template drafts created");
    expect(source.createDrafts).toHaveBeenCalledWith(
      context.projectId,
      {
        expectedProjectVersion: context.projectVersion,
        templateCode: "INJECTION-REVIEW",
        title: "Injection review",
      },
      expect.anything(),
    );
    expect(
      screen
        .getByRole("link", { name: "Review project template draft" })
        .getAttribute("href"),
    ).toMatch(/^\/app\/npi-project-template-version\/[0-9a-f-]+%3A1$/u);
    expect(source.execute).not.toHaveBeenCalled();
  });
});
