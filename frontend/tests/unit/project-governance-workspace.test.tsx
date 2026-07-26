import {
  screen,
  waitFor,
  within,
  type RenderResult,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ProjectControlsDataSource } from "../../src/api/project-controls-data-source";
import { NpiApiError, NpiTransportError } from "../../src/api/http";
import type {
  ProjectActivityItemViewModel,
  ProjectActivityPageViewModel,
  ProjectControlsViewModel,
  ProjectLearningViewModel,
} from "../../src/domain/view-models";
import type { Locale } from "../../src/i18n/runtime";
import { ProjectGovernanceWorkspace } from "../../src/pages/project-governance-workspace";
import {
  projectActivityFixture,
  projectControlIds,
  projectControlsFixture,
  projectLearningFixture,
} from "../support/project-controls-fixture";
import { renderWithLocale } from "../support/render";

const csrfToken = "project-controls-csrf-token-fixture-0001";

function enableCommandSession(): void {
  const fetchMock = vi.fn<typeof fetch>(() =>
    Promise.resolve(
      new Response(
        JSON.stringify({
          allowedLanguages: ["en", "zh", "zh-TW"],
          catalog: {
            language: "en",
            messages: {},
            version: "c".repeat(64),
          },
          csrfToken,
          language: "en",
          preferences: { navigationCollapsed: false },
          userId: "manager@example.invalid",
        }),
        { status: 200 },
      ),
    ),
  );
  vi.stubGlobal("fetch", fetchMock);
}

function activityItemFixture(): ProjectActivityItemViewModel {
  const item = projectActivityFixture().items[0];
  if (!item) throw new Error("The Project activity fixture requires one item.");
  return item;
}

function learningItemFixture(): ProjectLearningViewModel {
  const item = projectLearningFixture().items[0];
  if (!item) throw new Error("The Project learning fixture requires one item.");
  return item;
}

function createDataSource(
  overrides: Partial<ProjectControlsDataSource> = {},
): ProjectControlsDataSource {
  return {
    addComment: () => Promise.resolve(activityItemFixture()),
    assessHealth: () => Promise.resolve(projectControlsFixture()),
    bindPolicy: () => Promise.resolve(projectControlsFixture()),
    changeFollowing: (_projectId, following) =>
      Promise.resolve({
        changedAt: "2026-07-25T13:00:00Z",
        following,
        projectId: projectControlIds.project,
        version: 3,
      }),
    createLearning: () => Promise.resolve(learningItemFixture()),
    loadActivity: () => Promise.resolve(projectActivityFixture()),
    loadControls: () => Promise.resolve(projectControlsFixture()),
    loadLearning: () => Promise.resolve(projectLearningFixture()),
    transition: () => Promise.resolve(projectControlsFixture()),
    ...overrides,
  };
}

function renderWorkspace(
  source: ProjectControlsDataSource,
  section: "controls" | "activity" | "learning",
  options: {
    cockpitState?:
      | "draft"
      | "proposed"
      | "active"
      | "on_hold"
      | "completed"
      | "cancelled";
    locale?: Locale;
    navigate?: (target: string) => void;
    onProjectChanged?: (project: ProjectControlsViewModel["project"]) => void;
    path?: string;
  } = {},
): RenderResult {
  return renderWithLocale(
    <ProjectGovernanceWorkspace
      cockpitState={options.cockpitState ?? "active"}
      dataSource={source}
      navigate={options.navigate ?? vi.fn()}
      onProjectChanged={options.onProjectChanged ?? vi.fn()}
      projectId={projectControlIds.project}
      section={section}
    />,
    options.locale,
    options.path ?? `/projects/${projectControlIds.project}?tab=${section}`,
  );
}

describe("Project governance workspace", () => {
  it("binds only an exact server-offered policy and eligible authority members", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const controls = projectControlsFixture();
    const updated = {
      ...controls,
      binding: controls.binding
        ? { ...controls.binding, version: controls.binding.version + 1 }
        : null,
      project: { ...controls.project, version: controls.project.version + 1 },
    };
    const bindPolicy = vi.fn<ProjectControlsDataSource["bindPolicy"]>(() =>
      Promise.resolve(updated),
    );
    const source = createDataSource({ bindPolicy });
    const onProjectChanged =
      vi.fn<(project: ProjectControlsViewModel["project"]) => void>();
    const rendered = renderWorkspace(source, "controls", { onProjectChanged });

    await screen.findByRole("heading", {
      name: "Control policy and authority",
    });
    expect(
      screen.getByRole("radio", { name: "Complete project" }),
    ).toBeDisabled();
    expect(
      screen.getByText("A required readiness source is unavailable."),
    ).toBeVisible();
    expect(
      rendered.container.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(1);

    await user.selectOptions(
      screen.getByRole("combobox", { name: /project_manager/u }),
      projectControlIds.managerMember,
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: /quality_lead/u }),
      projectControlIds.qualityMember,
    );
    const bind = screen.getByRole("button", {
      name: "Replace policy binding",
    });
    await waitFor(() => {
      expect(bind).toBeEnabled();
    });
    await user.click(bind);

    await waitFor(() => {
      expect(bindPolicy).toHaveBeenCalledTimes(1);
    });
    const policy = controls.bindingOptions?.policies[0];
    if (!policy) throw new Error("The binding fixture requires one policy.");
    const call = bindPolicy.mock.calls[0];
    if (!call) throw new Error("The binding command was not captured.");
    expect(call[0]).toBe(projectControlIds.project);
    expect(call[1]).toEqual({
      bindings: [
        {
          memberGlobalId: projectControlIds.managerMember,
          slot: "project_manager",
        },
        {
          memberGlobalId: projectControlIds.qualityMember,
          slot: "quality_lead",
        },
      ],
      expectedProjectVersion: 7,
      policyRef: policy.policyRef,
    });
    expect(call[2].csrfToken).toBe(csrfToken);
    expect(call[2].idempotencyKey).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u,
    );
    expect(call[2].signal).toBeInstanceOf(AbortSignal);
    expect(onProjectChanged).toHaveBeenCalledWith(updated.project);
  });

  it("requires an explicit reason and recovery plan for a manual red assessment", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const assessHealth = vi.fn<ProjectControlsDataSource["assessHealth"]>(() =>
      Promise.resolve(projectControlsFixture()),
    );
    const source = createDataSource({ assessHealth });
    renderWorkspace(source, "controls");

    const manualStatus = await screen.findByRole("combobox", {
      name: "New manual health status Quality",
    });
    expect(
      screen.getByRole("combobox", {
        name: "New manual health status Risk",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("textbox", {
        name: "New numeric health value Progress",
      }),
    ).toBeVisible();
    await user.selectOptions(manualStatus, "red");
    const assess = screen.getByRole("button", {
      name: "Assess project health",
    });
    await waitFor(() => {
      expect(assess).toBeEnabled();
    });
    await user.click(assess);

    expect(
      screen.getByText(
        "A red health assessment requires a reason and recovery plan.",
      ),
    ).toBeVisible();
    expect(assessHealth).not.toHaveBeenCalled();
  });

  it("shows exact lifecycle state, policy, authority, and prerequisites before execution", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    renderWorkspace(createDataSource(), "controls");

    await screen.findByRole("heading", { name: "Lifecycle actions" });
    await user.click(screen.getByRole("radio", { name: "Pause project" }));
    await user.click(
      screen.getByRole("button", { name: "Review lifecycle action" }),
    );

    const dialog = screen.getByRole("dialog", {
      name: "Review project lifecycle transition",
    });
    const details = within(dialog);
    expect(details.getByText("Battery housing")).toBeVisible();
    expect(details.getByText("Active")).toBeVisible();
    expect(details.getByText("On hold")).toBeVisible();
    expect(details.getByText(`PCP-STD / 3 / ${"a".repeat(64)}`)).toBeVisible();
    expect(details.getByText("project_manager")).toBeVisible();
    expect(details.getByText("Project Manager")).toBeVisible();
    expect(details.getByText("manager@example.invalid")).toBeVisible();
    expect(details.getByText(projectControlIds.managerMember)).toBeVisible();
    expect(details.getByText("None")).toBeVisible();
    expect(details.getByText("2")).toBeVisible();
  });

  it("adds a comment with only resolved mentions, clean revisions, and typed object links", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const navigate = vi.fn<(target: string) => void>();
    const added: ProjectActivityItemViewModel = {
      ...activityItemFixture(),
      globalId: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
      occurredAt: "2026-07-25T13:00:00Z",
    };
    const addComment = vi.fn<ProjectControlsDataSource["addComment"]>(() =>
      Promise.resolve(added),
    );
    const source = createDataSource({ addComment });
    renderWorkspace(source, "activity", { navigate });

    expect(
      await screen.findByText("Review the controlled Gate evidence."),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: /Gate.*Tooling release/u }),
    );
    expect(navigate).toHaveBeenCalledWith(
      `/projects/${projectControlIds.project}/gates/${projectControlIds.gate}`,
    );

    const commentForm = screen
      .getByRole("button", { name: "Add comment" })
      .closest("form");
    if (!commentForm) throw new Error("The comment form was not rendered.");
    const form = within(commentForm);
    expect(form.getAllByRole("textbox")).toHaveLength(1);
    await user.type(
      form.getByRole("textbox", { name: "Comment" }),
      "Evidence is ready.",
    );
    await user.click(form.getByRole("checkbox", { name: /Quality Lead/ }));
    await user.click(form.getByRole("checkbox", { name: /trial-report\.pdf/ }));
    await user.click(
      form.getByRole("checkbox", { name: /G3 · Tooling release/ }),
    );
    const add = form.getByRole("button", { name: "Add comment" });
    await waitFor(() => {
      expect(add).toBeEnabled();
    });
    await user.click(add);

    await waitFor(() => {
      expect(addComment).toHaveBeenCalledTimes(1);
    });
    const call = addComment.mock.calls[0];
    if (!call) throw new Error("The comment command was not captured.");
    expect(call[0]).toBe(projectControlIds.project);
    expect(call[1]).toEqual({
      attachments: [{ globalId: projectControlIds.fileRevision, version: 4 }],
      body: "Evidence is ready.",
      mentions: [{ memberGlobalId: projectControlIds.qualityMember }],
      objectLinks: [
        { globalId: projectControlIds.gate, type: "gate", version: 3 },
      ],
    });
    expect(call[2].csrfToken).toBe(csrfToken);
    expect(call[2].idempotencyKey).toEqual(expect.any(String));
    expect(call[2].signal).toBeInstanceOf(AbortSignal);
  });

  it("keeps activity and available comment choices usable when choices are truncated", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const page = {
      ...projectActivityFixture(),
      commentOptions: {
        ...projectActivityFixture().commentOptions,
        truncated: true,
      },
    };
    const loadActivity = vi.fn<ProjectControlsDataSource["loadActivity"]>(() =>
      Promise.resolve(page),
    );
    const source = createDataSource({ loadActivity });
    renderWorkspace(source, "activity");

    expect(await screen.findByText("Comment choices limited")).toBeVisible();
    expect(
      screen.getByText(
        "Only the first 500 eligible comment choices are shown. You can still read activity and add a comment with the available choices.",
      ),
    ).toBeVisible();
    expect(
      screen.getByText("Review the controlled Gate evidence."),
    ).toBeVisible();

    const comment = screen.getByRole("textbox", { name: "Comment" });
    expect(
      screen.getByRole("checkbox", { name: /Quality Lead/ }),
    ).toBeEnabled();
    await user.type(comment, "Use an available choice.");
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Add comment" })).toBeEnabled();
    });
  });

  it("loads, deduplicates, and preserves descending activity continuations", async () => {
    const user = userEvent.setup();
    const first = {
      ...projectActivityFixture(),
      nextCursor: "opaque.activity.cursor-a",
    };
    const duplicate = structuredClone(first.items[0]);
    if (!duplicate) throw new Error("Missing activity fixture.");
    const older: ProjectActivityItemViewModel = {
      ...structuredClone(duplicate),
      actorUserId: "older@example.invalid",
      globalId: "77777777-7777-4777-8777-777777777777",
      occurredAt: "2026-07-25T10:00:00.123456Z",
    };
    const continuation = {
      ...projectActivityFixture(),
      following: false,
      followerVersion: 1,
      items: [duplicate, older],
      nextCursor: null,
    };
    const loadActivity = vi
      .fn<ProjectControlsDataSource["loadActivity"]>()
      .mockResolvedValueOnce(first)
      .mockResolvedValueOnce(continuation);
    const { container } = renderWorkspace(
      createDataSource({ loadActivity }),
      "activity",
    );

    const loadMore = await screen.findByRole("button", {
      name: "Load more activity",
    });
    await user.click(loadMore);
    await waitFor(() => {
      expect(loadActivity).toHaveBeenCalledTimes(2);
    });
    expect(loadActivity.mock.calls[1]?.[0]).toBe(projectControlIds.project);
    expect(loadActivity.mock.calls[1]?.[1]).toBeInstanceOf(AbortSignal);
    expect(loadActivity.mock.calls[1]?.[2]).toBe(50);
    expect(loadActivity.mock.calls[1]?.[3]).toBe("opaque.activity.cursor-a");
    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: "Load more activity" }),
      ).not.toBeInTheDocument();
    });
    const rows = container.querySelectorAll(
      ".governance-activity-table tbody tr",
    );
    expect(rows).toHaveLength(2);
    expect(
      within(rows[0] as HTMLElement).getByText("manager@example.invalid"),
    ).toBeVisible();
    expect(
      within(rows[1] as HTMLElement).getByText("older@example.invalid"),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Unfollow project" }),
    ).toBeVisible();
  });

  it("retains loaded activity and offers retry when a cursor cycle is rejected", async () => {
    const user = userEvent.setup();
    const first = {
      ...projectActivityFixture(),
      nextCursor: "opaque.activity.cursor-a",
    };
    const cycle = {
      ...projectActivityFixture(),
      nextCursor: "opaque.activity.cursor-a",
    };
    const older = {
      ...activityItemFixture(),
      actorUserId: "older@example.invalid",
      globalId: "77777777-7777-4777-8777-777777777777",
      occurredAt: "2026-07-25T10:00:00Z",
    };
    const recovered = {
      ...projectActivityFixture(),
      items: [older],
      nextCursor: null,
    };
    const loadActivity = vi
      .fn<ProjectControlsDataSource["loadActivity"]>()
      .mockResolvedValueOnce(first)
      .mockResolvedValueOnce(cycle)
      .mockResolvedValueOnce(recovered);
    const { container } = renderWorkspace(
      createDataSource({ loadActivity }),
      "activity",
    );

    await user.click(
      await screen.findByRole("button", { name: "Load more activity" }),
    );
    expect(
      await screen.findByText("More project activity could not be loaded."),
    ).toBeVisible();
    expect(
      container.querySelectorAll(".governance-activity-table tbody tr"),
    ).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(loadActivity).toHaveBeenCalledTimes(3);
    });
    await waitFor(() => {
      expect(
        screen.queryByText("More project activity could not be loaded."),
      ).not.toBeInTheDocument();
    });
    expect(
      container.querySelectorAll(".governance-activity-table tbody tr"),
    ).toHaveLength(2);
  });

  it("retries an uncertain network append with the same idempotency key", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const page = {
      ...projectActivityFixture(),
      commentOptions: {
        attachments: [],
        mentions: [],
        objectLinks: [],
        truncated: false,
      },
    };
    const loadActivity = vi.fn<ProjectControlsDataSource["loadActivity"]>(() =>
      Promise.resolve(page),
    );
    const addComment = vi
      .fn<ProjectControlsDataSource["addComment"]>()
      .mockRejectedValueOnce(
        new NpiTransportError("network", "trace-network-001", "trace"),
      )
      .mockResolvedValueOnce(activityItemFixture());
    const source = createDataSource({ addComment, loadActivity });
    renderWorkspace(source, "activity");

    const comment = await screen.findByRole("textbox", { name: "Comment" });
    await user.type(comment, "Keep the exact command.");
    const add = screen.getByRole("button", { name: "Add comment" });
    await waitFor(() => {
      expect(add).toBeEnabled();
    });
    await user.click(add);

    const retry = await screen.findByRole("button", {
      name: "Retry same command",
    });
    const firstContext = addComment.mock.calls[0]?.[2];
    expect(firstContext).toBeDefined();
    await user.click(retry);
    await waitFor(() => {
      expect(addComment).toHaveBeenCalledTimes(2);
    });
    const secondContext = addComment.mock.calls[1]?.[2];
    expect(secondContext?.idempotencyKey).toBe(firstContext?.idempotencyKey);
    expect(secondContext?.csrfToken).toBe(firstContext?.csrfToken);
    expect(secondContext?.signal).not.toBe(firstContext?.signal);
  });

  it("requires a latest-data reload instead of replaying a stale conflict", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const page = {
      ...projectActivityFixture(),
      commentOptions: {
        attachments: [],
        mentions: [],
        objectLinks: [],
        truncated: false,
      },
    };
    const loadActivity = vi.fn<ProjectControlsDataSource["loadActivity"]>(() =>
      Promise.resolve(page),
    );
    const addComment = vi
      .fn<ProjectControlsDataSource["addComment"]>()
      .mockRejectedValue(
        new NpiApiError({
          code: "PROJECT_VERSION_CONFLICT",
          detail: "The submitted project version is stale.",
          retryable: true,
          status: 409,
          title: "Project version conflict",
          traceId: "trace-conflict-001",
          type: "https://npi.invalid/problems/project-version-conflict",
        }),
      );
    const source = createDataSource({ addComment, loadActivity });
    renderWorkspace(source, "activity");

    const comment = await screen.findByRole("textbox", { name: "Comment" });
    await user.type(comment, "Reload before another attempt.");
    const add = screen.getByRole("button", { name: "Add comment" });
    await waitFor(() => {
      expect(add).toBeEnabled();
    });
    await user.click(add);

    expect(
      await screen.findByRole("button", { name: "Reload latest data" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Retry same command" }),
    ).not.toBeInTheDocument();
  });

  it("keeps learning append-only on a terminal project and captures improvement fields", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const created: ProjectLearningViewModel = {
      ...learningItemFixture(),
      content: "Require signed supplier lead-time evidence.",
      globalId: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      kind: "template_improvement",
      recommendation: "Add the evidence field to the project template.",
      tags: ["supplier", "evidence"],
      title: "Strengthen sourcing evidence",
    };
    const createLearning = vi.fn<ProjectControlsDataSource["createLearning"]>(
      () => Promise.resolve(created),
    );
    const source = createDataSource({ createLearning });
    renderWorkspace(source, "learning", { cockpitState: "completed" });

    expect(await screen.findByText("Append-only learning")).toBeVisible();
    const createButton = screen.getByRole("button", {
      name: "Create learning record",
    });
    const createForm = createButton.closest("form");
    if (!createForm) throw new Error("The learning form was not rendered.");
    const form = within(createForm);
    await user.selectOptions(
      form.getByRole("combobox", { name: "Learning kind" }),
      "template_improvement",
    );
    expect(
      screen.getByText(
        "This feedback is proposed only. It does not change or publish a Project Template.",
      ),
    ).toBeVisible();
    await user.type(
      form.getByRole("textbox", { name: "Title" }),
      "Strengthen sourcing evidence",
    );
    await user.type(
      form.getByRole("textbox", { name: "Learning content" }),
      "Require signed supplier lead-time evidence.",
    );
    await user.type(
      form.getByRole("textbox", { name: "Recommendation" }),
      "Add the evidence field to the project template.",
    );
    await user.type(
      form.getByRole("textbox", { name: "Tags" }),
      "supplier, evidence",
    );
    await waitFor(() => {
      expect(createButton).toBeEnabled();
    });
    await user.click(createButton);

    await waitFor(() => {
      expect(createLearning).toHaveBeenCalledTimes(1);
    });
    const call = createLearning.mock.calls[0];
    if (!call) throw new Error("The learning command was not captured.");
    expect(call[0]).toBe(projectControlIds.project);
    expect(call[1]).toEqual({
      content: "Require signed supplier lead-time evidence.",
      kind: "template_improvement",
      recommendation: "Add the evidence field to the project template.",
      tags: ["supplier", "evidence"],
      title: "Strengthen sourcing evidence",
    });
    expect(call[2].csrfToken).toBe(csrfToken);
    expect(call[2].idempotencyKey).toEqual(expect.any(String));
    expect(call[2].signal).toBeInstanceOf(AbortSignal);
    expect(
      screen.getAllByText(
        "This feedback is proposed only. It does not change or publish a Project Template.",
      ),
    ).toHaveLength(2);
  });

  it.each<[Locale, string]>([
    [
      "en",
      "This feedback is proposed only. It does not change or publish a Project Template.",
    ],
    ["zh", "此反馈仅为拟议内容，不会更改或发布项目模板。"],
    ["zh-TW", "此回饋僅為提議內容，不會變更或發佈專案模板。"],
  ])(
    "shows proposed template feedback honestly in %s",
    async (locale, copy) => {
      const learning = projectLearningFixture();
      const item = learning.items[0];
      if (!item)
        throw new Error("The Project learning fixture requires one item.");
      renderWorkspace(
        createDataSource({
          loadLearning: () =>
            Promise.resolve({
              ...learning,
              items: [{ ...item, kind: "template_improvement" }],
            }),
        }),
        "learning",
        { locale },
      );

      expect(await screen.findByText(copy)).toBeVisible();
    },
  );

  it.each<[Locale, string]>([
    ["en", "supplier and lead-time"],
    ["zh", "supplier和lead-time"],
    ["zh-TW", "supplier和lead-time"],
  ])(
    "formats learning tags with the %s list rules",
    async (locale, expected) => {
      renderWorkspace(createDataSource(), "learning", { locale });

      expect(await screen.findByText(expected)).toBeVisible();
    },
  );

  it("loads an exact learning deep link without falling back to unrelated records", async () => {
    const loadLearning = vi
      .fn<ProjectControlsDataSource["loadLearning"]>()
      .mockRejectedValue(
        new NpiApiError({
          code: "PROJECT_UNAVAILABLE",
          detail: "The requested Project resource is unavailable.",
          retryable: false,
          status: 404,
          title: "Project unavailable",
          traceId: "trace-learning-missing-001",
          type: "https://npi.invalid/problems/project-unavailable",
        }),
      );
    renderWorkspace(createDataSource({ loadLearning }), "learning", {
      path:
        `/projects/${projectControlIds.project}?tab=learning&learning=` +
        projectControlIds.learning,
    });

    expect(
      await screen.findByRole("heading", {
        name: "Project collaboration data is unavailable",
      }),
    ).toBeVisible();
    expect(loadLearning).toHaveBeenCalledTimes(1);
    expect(loadLearning.mock.calls[0]?.[1]).toEqual({
      learningId: projectControlIds.learning,
      limit: 1,
    });
    expect(
      screen.queryByText("Hot runner sourcing retrospective"),
    ).not.toBeInTheDocument();
  });

  it("transfers quick-create focus only after the authorized learning form loads", async () => {
    enableCommandSession();
    renderWorkspace(createDataSource(), "learning", {
      path: `/projects/${projectControlIds.project}?tab=learning&quickCreate=learning`,
    });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await waitFor(() => {
      expect(title).toHaveFocus();
    });
    expect(
      document.getElementById("project-learning-quick-create"),
    ).toContainElement(title);
  });

  it("shows empty read-only activity without exposing contribution controls", async () => {
    const loadActivity = vi.fn<ProjectControlsDataSource["loadActivity"]>(() =>
      Promise.resolve({
        ...projectActivityFixture(),
        permissions: {
          canComment: false,
          canFollow: false,
        },
        commentOptions: {
          attachments: [],
          mentions: [],
          objectLinks: [],
          truncated: false,
        },
        following: false,
        items: [],
      }),
    );
    const source = createDataSource({ loadActivity });
    renderWorkspace(source, "activity");

    expect(await screen.findByText("Read only")).toBeVisible();
    expect(
      screen.getByText("No project activity has been recorded."),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Add project comment" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Follow project" }),
    ).toBeDisabled();
  });

  it("fails closed without displaying protected controls when access is denied", async () => {
    const loadControls = vi
      .fn<ProjectControlsDataSource["loadControls"]>()
      .mockRejectedValue(
        new NpiApiError({
          code: "PROJECT_ACCESS_DENIED",
          detail: "The current user cannot view this Project.",
          retryable: false,
          status: 403,
          title: "Project access denied",
          traceId: "trace-denied-001",
          type: "https://npi.invalid/problems/project-access-denied",
        }),
      );
    const source = createDataSource({ loadControls });
    renderWorkspace(source, "controls");

    expect(await screen.findByText("No permission")).toBeVisible();
    expect(
      screen.getByText("No protected collaboration data was displayed."),
    ).toBeVisible();
    expect(
      screen.queryByText("Standard project control policy"),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["zh", "管控策略与权限"],
    ["zh-TW", "管控策略與權責"],
  ] as const)(
    "renders the governed controls surface entirely from the %s catalog",
    async (locale, heading) => {
      renderWorkspace(createDataSource(), "controls", { locale });

      expect(
        await screen.findByRole("heading", { name: heading }),
      ).toBeVisible();
      expect(
        screen.queryByText("Control policy and authority"),
      ).not.toBeInTheDocument();
    },
  );

  it.each([
    [
      "zh",
      "加载更多项目活动",
      "正在加载更多项目活动",
      "无法加载更多项目活动。",
    ],
    [
      "zh-TW",
      "載入更多專案活動",
      "正在載入更多專案活動",
      "無法載入更多專案活動。",
    ],
  ] as const)(
    "renders activity continuation states entirely from the %s catalog",
    async (locale, loadLabel, loadingLabel, failureLabel) => {
      const user = userEvent.setup();
      const first = {
        ...projectActivityFixture(),
        nextCursor: "opaque.activity.cursor-a",
      };
      let resolveContinuation:
        | ((value: ProjectActivityPageViewModel) => void)
        | undefined;
      const pending = new Promise<ProjectActivityPageViewModel>((resolve) => {
        resolveContinuation = resolve;
      });
      const loadActivity = vi
        .fn<ProjectControlsDataSource["loadActivity"]>()
        .mockResolvedValueOnce(first)
        .mockReturnValueOnce(pending);
      renderWorkspace(createDataSource({ loadActivity }), "activity", {
        locale,
      });

      await user.click(await screen.findByRole("button", { name: loadLabel }));
      expect(
        await screen.findByRole("button", { name: loadingLabel }),
      ).toBeDisabled();
      resolveContinuation?.({
        ...projectActivityFixture(),
        nextCursor: "opaque.activity.cursor-a",
      });
      expect(await screen.findByText(failureLabel)).toBeVisible();
      expect(screen.queryByText("Load more activity")).not.toBeInTheDocument();
      expect(
        screen.queryByText("More project activity could not be loaded."),
      ).not.toBeInTheDocument();
    },
  );
});
