import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { EngineeringBomPublishRequestDataSource } from "../../src/api/publish-request-data-source";
import type {
  ItemPublishDataSource,
  ItemPublishRequestListViewModel,
} from "../../src/api/item-publish-data-source";
import { NpiApiError } from "../../src/api/http";
import { EngineeringBomPublishRequestWorkspace } from "../../src/pages/project-ebom-publish-workspace";
import {
  ebomProjectId,
  engineeringBomDetailFixture,
  releasedEngineeringBomRevisionFixture,
} from "../support/ebom-fixture";
import {
  publishPolicyId,
  publishRequestFixture,
  publishRequestId,
  publishRequestListFixture,
} from "../support/publish-request-fixture";
import {
  itemPublishDetailFixture,
  itemPublishListFixture,
} from "../support/item-publish-fixture";
import { renderWithLocale } from "../support/render";

const csrfToken = "publish-workspace-csrf-token-fixture";

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
              version: "c".repeat(64),
            },
            csrfToken,
            language: "en",
            preferences: { navigationCollapsed: false },
            userId: "publisher@example.invalid",
          }),
          { status: 200 },
        ),
      ),
    ),
  );
}

function dataSource(
  overrides: Partial<EngineeringBomPublishRequestDataSource> = {},
): EngineeringBomPublishRequestDataSource {
  return {
    createRequest: () => Promise.resolve(publishRequestFixture()),
    loadRequest: () => Promise.resolve(publishRequestFixture()),
    loadRequests: () => Promise.resolve(publishRequestListFixture()),
    ...overrides,
  };
}

function itemDataSource(
  detail = itemPublishDetailFixture(),
  overrides: Partial<ItemPublishDataSource> = {},
): ItemPublishDataSource {
  return {
    createRequest: () => Promise.resolve(detail),
    loadRequest: () => Promise.resolve(detail),
    loadRequests: () => Promise.resolve(itemPublishListFixture(detail)),
    ...overrides,
  };
}

function renderWorkspace(
  source: EngineeringBomPublishRequestDataSource | undefined = dataSource(),
  revision = releasedEngineeringBomRevisionFixture(),
  onDirtyChange?: (dirty: boolean) => void,
  itemSource?: ItemPublishDataSource,
): void {
  const detail = engineeringBomDetailFixture();
  renderWithLocale(
    <EngineeringBomPublishRequestWorkspace
      dataSource={source}
      ebom={detail.ebom}
      itemPublishDataSource={itemSource}
      onDirtyChange={onDirtyChange}
      projectId={ebomProjectId}
      revision={revision}
    />,
    "en",
    `/projects/${ebomProjectId}?tab=ebom`,
  );
}

async function activateItemInspector(
  user: ReturnType<typeof userEvent.setup>,
  locale: "en" | "zh" | "zh-TW" = "en",
): Promise<void> {
  await user.click(await screen.findByRole("button", { name: "ENG-SYN-001" }));
  const inspectorName =
    locale === "zh"
      ? "物料执行检查器"
      : locale === "zh-TW"
        ? "物料執行檢查器"
        : "Item execution inspector";
  await screen.findByRole("region", {
    name: inspectorName,
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("EBOM publish-request workspace", () => {
  it("renders exact Mock request, node, mapping and no-fake-success truth", async () => {
    renderWorkspace();

    expect(
      await screen.findByRole("heading", { name: "Formal publish requests" }),
    ).toBeVisible();
    expect(screen.getByText("Mock validation only")).toBeVisible();
    expect(
      (await screen.findAllByText("Validated in Mock")).length,
    ).toBeGreaterThan(0);
    expect(
      await screen.findByText(
        "Create Item intent; Create or update MBOM intent",
      ),
    ).toBeVisible();
    expect(screen.getByText("Unmapped")).toBeVisible();
    expect(screen.getAllByText("Not assigned").length).toBeGreaterThan(0);
    expect(
      document.querySelector(".publish-request__detail-header"),
    ).toHaveTextContent("Dispatch: Disabled");
    expect(
      screen.getByText(
        "Validated means the frozen NPI request passed local checks. It was not queued, sent or completed in ERPNext.",
      ),
    ).toBeVisible();
    expect(screen.queryByText("ITEM-001")).not.toBeInTheDocument();
  });

  it("prepares one exact confirmed request and reports dirty navigation state", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const createRequest = vi.fn<
      EngineeringBomPublishRequestDataSource["createRequest"]
    >(() => Promise.resolve(publishRequestFixture()));
    const onDirtyChange = vi.fn<(dirty: boolean) => void>();
    renderWorkspace(dataSource({ createRequest }), undefined, onDirtyChange);

    const prepare = await screen.findByRole("button", {
      name: "Prepare publish request",
    });
    await waitFor(() => {
      expect(prepare).toBeEnabled();
    });
    await user.click(prepare);
    const form = screen
      .getByRole("combobox", { name: "Exact publish policy" })
      .closest("form");
    if (!form) throw new Error("The publish form is unavailable.");
    await waitFor(() => {
      expect(
        within(form).getByRole("combobox", { name: "Exact publish policy" }),
      ).toHaveFocus();
    });
    expect(
      document.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(1);
    await user.type(
      within(form).getByRole("textbox", { name: "Reason" }),
      "Formal handoff validation",
    );
    await user.click(
      within(form).getByRole("checkbox", {
        name: "I confirm validation of this exact released EBOM in Mock mode. No Item or MBOM will be created in ERPNext.",
      }),
    );
    expect(onDirtyChange).toHaveBeenCalledWith(true);
    await user.click(
      within(form).getByRole("button", {
        name: "Validate exact released EBOM",
      }),
    );

    await waitFor(() => {
      expect(createRequest).toHaveBeenCalledOnce();
    });
    const call = createRequest.mock.calls[0];
    expect(call?.[1]).toBe(engineeringBomDetailFixture().ebom.globalId);
    expect(call?.[2]).toBe(releasedEngineeringBomRevisionFixture().globalId);
    expect(call?.[3]).toMatchObject({
      expectedEbomVersion: 2,
      expectedLifecycleVersion: 4,
      expectedRevisionSnapshotHash: "b".repeat(64),
      publishPolicyGlobalId: publishPolicyId,
      targetMode: "mock",
      confirmed: true,
      confirmationIntent: "validate_exact_released_ebom_for_item_mbom_publish",
      reason: "Formal handoff validation",
    });
    expect(call?.[4].csrfToken).toBe(csrfToken);
    expect(call?.[4].idempotencyKey).toMatch(/^ebom-publish-/u);
    expect(
      await screen.findByText(
        "The immutable request was recorded locally. ERPNext was not contacted.",
      ),
    ).toBeVisible();
    expect(onDirtyChange).toHaveBeenLastCalledWith(false);
  });

  it("reuses the actor-bound idempotency key for an exact retry", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const failure = new NpiApiError({
      type: "https://example.invalid/problems/target-unavailable",
      title: "Target unavailable",
      status: 503,
      code: "EBOM_PUBLISH_REQUEST_UNAVAILABLE",
      traceId: "trace-publish-workspace-retry",
      retryable: true,
    });
    const createRequest = vi
      .fn<EngineeringBomPublishRequestDataSource["createRequest"]>()
      .mockRejectedValueOnce(failure)
      .mockResolvedValueOnce(publishRequestFixture());
    renderWorkspace(dataSource({ createRequest }));

    const prepare = await screen.findByRole("button", {
      name: "Prepare publish request",
    });
    await waitFor(() => {
      expect(prepare).toBeEnabled();
    });
    await user.click(prepare);
    await user.type(
      screen.getByRole("textbox", { name: "Reason" }),
      "Retry exact request",
    );
    await user.click(
      screen.getByRole("checkbox", {
        name: "I confirm validation of this exact released EBOM in Mock mode. No Item or MBOM will be created in ERPNext.",
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Validate exact released EBOM" }),
    );
    expect(
      await screen.findByText("trace-publish-workspace-retry"),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(createRequest).toHaveBeenCalledTimes(2);
    });
    expect(createRequest.mock.calls[0]?.[4].idempotencyKey).toBe(
      createRequest.mock.calls[1]?.[4].idempotencyKey,
    );
  });

  it("renders manual-intervention and target-unavailable node truth without enabling retry", async () => {
    const request = publishRequestFixture({
      requestState: "manual_intervention",
      nodeState: "target_unavailable",
    });
    renderWorkspace(
      dataSource({
        loadRequest: () => Promise.resolve(request),
        loadRequests: () => Promise.resolve(publishRequestListFixture(request)),
      }),
    );

    expect(await screen.findByText("Manual intervention")).toBeVisible();
    expect(screen.getAllByText("Target unavailable").length).toBeGreaterThan(0);
    expect(screen.getByText("Reconcile before retry")).toBeVisible();
    expect(screen.getByText("Reconciliation required")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Retry failed nodes only" }),
    ).not.toBeInTheDocument();
  });

  it("renders synthetic Item history without inventing formal success or mapping", async () => {
    const user = userEvent.setup();
    renderWorkspace(dataSource(), undefined, undefined, itemDataSource());

    await activateItemInspector(user);
    expect(
      await screen.findByRole("heading", { name: "Item execution inspector" }),
    ).toBeVisible();
    expect(
      await screen.findByText("Synthetic verification; not authoritative"),
    ).toBeVisible();
    expect(
      document.querySelector(".item-publish__status-strip"),
    ).toHaveTextContent("Disposable synthetic runtime");
    expect(screen.getByText("No authoritative mapping")).toBeVisible();
    expect(screen.getAllByText("Not assigned").length).toBeGreaterThan(0);
    expect(screen.queryByText("ITEM-SANDBOX-0001")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /reconcile/iu }),
    ).not.toBeInTheDocument();
  });

  it("keeps the inactive Item inspector out of the DOM and does not query its source", async () => {
    const loadRequests = vi.fn<ItemPublishDataSource["loadRequests"]>();
    const loadRequest = vi.fn<ItemPublishDataSource["loadRequest"]>();
    renderWorkspace(
      dataSource(),
      undefined,
      undefined,
      itemDataSource(undefined, { loadRequests, loadRequest }),
    );

    await screen.findByRole("button", { name: "ENG-SYN-001" });
    expect(
      screen.queryByRole("region", { name: "Item execution inspector" }),
    ).not.toBeInTheDocument();
    expect(loadRequests).not.toHaveBeenCalled();
    expect(loadRequest).not.toHaveBeenCalled();
  });

  it.each(["Enter", "Space"] as const)(
    "activates the Item inspector exactly once with %s",
    async (key) => {
      const user = userEvent.setup();
      const loadRequests = vi.fn<ItemPublishDataSource["loadRequests"]>(() =>
        Promise.resolve(itemPublishListFixture(itemPublishDetailFixture())),
      );
      renderWorkspace(
        dataSource(),
        undefined,
        undefined,
        itemDataSource(undefined, { loadRequests }),
      );
      const trigger = await screen.findByRole("button", {
        name: "ENG-SYN-001",
      });
      trigger.focus();
      await user.keyboard(key === "Enter" ? "{Enter}" : "{Space}");
      if (key === "Space") trigger.click();

      await screen.findByRole("region", {
        name: "Item execution inspector",
      });
      expect(loadRequests).toHaveBeenCalledOnce();
      expect(trigger).toHaveAttribute(
        "aria-controls",
        "item-publish-execution-inspector",
      );
      expect(trigger).toHaveAttribute("aria-expanded", "true");
      expect(trigger).toHaveFocus();
    },
  );

  it("shows an unavailable inspector after the first click when its source is absent", async () => {
    const user = userEvent.setup();
    renderWorkspace(dataSource(), undefined, undefined, undefined);

    await user.click(
      await screen.findByRole("button", { name: "ENG-SYN-001" }),
    );

    expect(
      await screen.findByText(
        "The Item execution data source is not configured. No target system was contacted.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("region", { name: "Item execution inspector" }),
    ).toBeVisible();
  });

  it("aborts stale Item reads and clears A truth before selecting sibling B", async () => {
    const user = userEvent.setup();
    const phase5 = publishRequestFixture();
    const firstNode = phase5.nodes[0];
    if (!firstNode) throw new Error("The publish fixture requires one node.");
    const secondNode = {
      ...firstNode,
      globalId: "75000000-0000-4000-8000-000000000026",
      line: {
        ...firstNode.line,
        engineeringItemId: "ENG-SYN-002",
        globalId: "75000000-0000-4000-8000-000000000027",
      },
    };
    const twoNodeRequest = { ...phase5, nodes: [firstNode, secondNode] };
    const firstAbort = vi.fn();
    let firstSignal: AbortSignal | undefined;
    let resolveFirst:
      | ((value: ItemPublishRequestListViewModel) => void)
      | null = null;
    const firstPending = new Promise<ItemPublishRequestListViewModel>(
      (resolve) => {
        resolveFirst = resolve;
      },
    );
    const detail = itemPublishDetailFixture();
    const loadRequests = vi.fn<ItemPublishDataSource["loadRequests"]>(
      (_projectId, _requestId, nodeId, signal) => {
        if (nodeId === firstNode.globalId) {
          firstSignal = signal;
          signal.addEventListener("abort", firstAbort, { once: true });
          return firstPending;
        }
        return Promise.resolve(itemPublishListFixture(detail));
      },
    );
    renderWorkspace(
      dataSource({
        loadRequest: () => Promise.resolve(twoNodeRequest),
        loadRequests: () =>
          Promise.resolve(publishRequestListFixture(twoNodeRequest)),
      }),
      undefined,
      undefined,
      itemDataSource(detail, { loadRequests }),
    );

    await user.click(
      await screen.findByRole("button", { name: "ENG-SYN-001" }),
    );
    const inspector = await screen.findByRole("region", {
      name: "Item execution inspector",
    });
    await waitFor(() => {
      expect(loadRequests).toHaveBeenCalledWith(
        ebomProjectId,
        publishRequestId,
        firstNode.globalId,
        expect.any(AbortSignal),
      );
    });
    await user.click(
      within(inspector).getByRole("button", { name: "ENG-SYN-002" }),
    );

    await waitFor(() => {
      expect(firstSignal?.aborted).toBe(true);
      expect(firstAbort).toHaveBeenCalledOnce();
      expect(loadRequests).toHaveBeenCalledWith(
        ebomProjectId,
        publishRequestId,
        secondNode.globalId,
        expect.any(AbortSignal),
      );
    });
    expect(resolveFirst).not.toBeNull();
    const activeTriggers = screen.getAllByRole("button", {
      name: "ENG-SYN-002",
    });
    expect(
      activeTriggers.some(
        (trigger) => trigger.getAttribute("aria-expanded") === "true",
      ),
    ).toBe(true);
  });

  it("fails closed for Item list and detail transport failures", async () => {
    const user = userEvent.setup();
    const listFailure = new NpiApiError({
      type: "https://example.invalid/problems/item-list",
      title: "Item list unavailable",
      status: 503,
      code: "ITEM_PUBLISH_REQUEST_UNAVAILABLE",
      traceId: "trace-item-list-failure",
      retryable: false,
    });
    renderWorkspace(
      dataSource(),
      undefined,
      undefined,
      itemDataSource(undefined, {
        loadRequests: () => Promise.reject(listFailure),
      }),
    );
    await activateItemInspector(user);
    expect(await screen.findByText("trace-item-list-failure")).toBeVisible();
    cleanup();

    const detailFailure = new NpiApiError({
      type: "https://example.invalid/problems/item-detail",
      title: "Item detail unavailable",
      status: 500,
      code: "ITEM_PUBLISH_REQUEST_UNAVAILABLE",
      traceId: "trace-item-detail-failure",
      retryable: false,
    });
    renderWorkspace(
      dataSource(),
      undefined,
      undefined,
      itemDataSource(itemPublishDetailFixture(), {
        loadRequest: () => Promise.reject(detailFailure),
      }),
    );
    await activateItemInspector(user);
    expect(await screen.findByText("trace-item-detail-failure")).toBeVisible();
  });

  it("uses the historical request profile instead of the prospective list profile", async () => {
    const user = userEvent.setup();
    const detail = itemPublishDetailFixture({
      state: "succeeded",
      targetMode: "sandbox",
      authoritativeMapping: true,
    });
    const loadRequests = vi.fn<ItemPublishDataSource["loadRequests"]>(() =>
      Promise.resolve(
        itemPublishListFixture(detail, { profileMode: "synthetic" }),
      ),
    );
    const loadRequest = vi.fn<ItemPublishDataSource["loadRequest"]>(() =>
      Promise.resolve(detail),
    );
    renderWorkspace(
      dataSource(),
      undefined,
      undefined,
      itemDataSource(detail, {
        loadRequests,
        loadRequest,
      }),
    );
    await activateItemInspector(user);
    await waitFor(() => {
      expect(loadRequests).toHaveBeenCalledOnce();
      expect(loadRequest).toHaveBeenCalledOnce();
    });
    expect(
      await screen.findByText(/Execution profile: Sandbox execution/u),
    ).toBeVisible();
    expect(screen.getByText("item-sandbox-v1")).toBeVisible();
    expect(
      screen.queryByText(/Execution profile: Disposable synthetic runtime/u),
    ).not.toBeInTheDocument();
  });

  it("keeps mapping-conflict identity on the old current head", async () => {
    const user = userEvent.setup();
    const conflict = itemPublishDetailFixture({ state: "mapping_conflict" });
    if (!conflict.result)
      throw new Error("The conflict fixture requires a result.");
    const detail = {
      ...conflict,
      result: {
        ...conflict.result,
        formalItemCode: "ITEM-CONFLICT-NEW",
        targetVersion: "2",
      },
    };
    renderWorkspace(dataSource(), undefined, undefined, itemDataSource(detail));
    await activateItemInspector(user);
    expect(await screen.findByText("ITEM-SANDBOX-0001")).toBeVisible();
    expect(screen.queryByText("ITEM-CONFLICT-NEW")).not.toBeInTheDocument();
  });

  it.each([
    ["zh", "已启动", "开始时间"],
    ["zh-TW", "已啟動", "開始時間"],
  ] as const)(
    "keeps Started state distinct from Started at in %s",
    async (locale, started, startedAt) => {
      const detail = itemPublishDetailFixture({
        state: "processing",
        targetMode: "sandbox",
      });
      renderWithLocale(
        <EngineeringBomPublishRequestWorkspace
          dataSource={dataSource()}
          ebom={engineeringBomDetailFixture().ebom}
          itemPublishDataSource={itemDataSource(detail)}
          projectId={ebomProjectId}
          revision={releasedEngineeringBomRevisionFixture()}
        />,
        locale,
        `/projects/${ebomProjectId}?tab=ebom`,
      );
      const user = userEvent.setup();
      await activateItemInspector(user, locale);
      expect(
        screen.getByRole("columnheader", { name: startedAt }),
      ).toBeVisible();
      expect(screen.getByText(started)).toBeVisible();
    },
  );

  it("renders closed attempt state and fault labels instead of wire literals", async () => {
    const user = userEvent.setup();
    const detail = itemPublishDetailFixture({ state: "failed_final" });
    const attempt = detail.attempts[0];
    if (!attempt) throw new Error("The Item fixture requires an attempt.");
    const localizedDetail = {
      ...detail,
      attempts: [
        {
          ...attempt,
          state: "observed_failure" as const,
          faultKind: "response_contract_invalid",
        },
      ],
    };
    renderWorkspace(
      dataSource(),
      undefined,
      undefined,
      itemDataSource(localizedDetail),
    );
    await activateItemInspector(user);

    expect(await screen.findByText("Observed failure")).toBeVisible();
    expect(screen.getByText("Response contract invalid")).toBeVisible();
    expect(screen.queryByText("observed_failure")).not.toBeInTheDocument();
    expect(
      screen.queryByText("response_contract_invalid"),
    ).not.toBeInTheDocument();
  });

  it("shows formal Item identity only from the authoritative current mapping", async () => {
    const user = userEvent.setup();
    const detail = itemPublishDetailFixture({
      authoritativeMapping: true,
      state: "succeeded",
      targetMode: "sandbox",
    });
    renderWorkspace(dataSource(), undefined, undefined, itemDataSource(detail));
    await activateItemInspector(user);

    expect(
      await screen.findByText("Authoritative Sandbox result observed"),
    ).toBeVisible();
    expect(screen.getByText("Authoritative Sandbox observation")).toBeVisible();
    expect(screen.getByText("ITEM-SANDBOX-0001")).toBeVisible();
  });

  it("guards one Item request, commits locally and reports no target success", async () => {
    enableCommandSession();
    const user = userEvent.setup();
    const queued = itemPublishDetailFixture({ state: "queued" });
    const createRequest = vi.fn<ItemPublishDataSource["createRequest"]>(() =>
      Promise.resolve(queued),
    );
    const source = itemDataSource(queued, {
      createRequest,
      loadRequests: () =>
        Promise.resolve(
          itemPublishListFixture(null, {
            mappingExpectation: {
              mappingVersion: 3,
              formalItemCode: "ITEM-SANDBOX-0001",
              targetVersion: "7",
              observationHash: "c".repeat(64),
            },
          }),
        ),
    });
    renderWorkspace(dataSource(), undefined, undefined, source);
    await activateItemInspector(user);

    const requestButton = await screen.findByRole("button", {
      name: "Request Item execution",
    });
    await waitFor(() => {
      expect(requestButton).toBeDisabled();
    });
    await user.click(
      screen.getByRole("checkbox", {
        name: "I confirm this request uses the exact released Item source and current execution profile.",
      }),
    );
    expect(requestButton).toBeEnabled();
    expect(
      document.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(1);
    await user.click(requestButton);

    await waitFor(() => {
      expect(createRequest).toHaveBeenCalledOnce();
    });
    expect(createRequest.mock.calls[0]?.[1]).toEqual({
      acknowledgement:
        "I confirm this request uses the exact released Item source and current execution profile.",
      expectedMappingVersion: 3,
      publishRequestGlobalId: publishRequestFixture().globalId,
      selectedPublishNodeGlobalId: publishRequestFixture().nodes[0]?.globalId,
    });
    expect(createRequest.mock.calls[0]?.[2].idempotencyKey).toMatch(
      /^item-publish-/u,
    );
    expect(
      await screen.findByText(
        "The immutable request was committed locally. This is not target success.",
      ),
    ).toBeVisible();
    expect(
      screen.getAllByText("Queued; target result pending").length,
    ).toBeGreaterThan(0);
  });

  it("blocks Mock, unavailable-profile, read-only and uncertain Item states", async () => {
    const user = userEvent.setup();
    const mock = itemPublishDetailFixture({ targetMode: "mock" });
    const { unmount } = renderWithLocale(
      <EngineeringBomPublishRequestWorkspace
        dataSource={dataSource()}
        ebom={engineeringBomDetailFixture().ebom}
        itemPublishDataSource={itemDataSource(mock, {
          loadRequests: () =>
            Promise.resolve(
              itemPublishListFixture(mock, { profileMode: "mock" }),
            ),
        })}
        projectId={ebomProjectId}
        revision={releasedEngineeringBomRevisionFixture()}
      />,
      "en",
    );
    await activateItemInspector(user);
    expect(
      await screen.findByText(
        "Mock validates the request locally and cannot execute an Item.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Request Item execution" }),
    ).toBeDisabled();
    unmount();

    const missingProfileRender = renderWithLocale(
      <EngineeringBomPublishRequestWorkspace
        dataSource={dataSource()}
        ebom={engineeringBomDetailFixture().ebom}
        itemPublishDataSource={itemDataSource(undefined, {
          loadRequests: () =>
            Promise.resolve(
              itemPublishListFixture(null, { profileUnavailable: true }),
            ),
        })}
        projectId={ebomProjectId}
        revision={releasedEngineeringBomRevisionFixture()}
      />,
      "en",
    );
    await activateItemInspector(user);
    expect(
      await screen.findByText(
        "The exact Item execution profile is unavailable.",
      ),
    ).toBeVisible();
    missingProfileRender.unmount();

    const uncertain = itemPublishDetailFixture({
      state: "uncertain_after_timeout",
      targetMode: "sandbox",
    });
    renderWorkspace(
      dataSource(),
      undefined,
      undefined,
      itemDataSource(uncertain, {
        loadRequests: () =>
          Promise.resolve(
            itemPublishListFixture(uncertain, { canExecute: false }),
          ),
      }),
    );
    await activateItemInspector(user);
    expect(
      await screen.findByText(
        "Uncertain after timeout; reconciliation required",
      ),
    ).toBeVisible();
    expect(
      screen.getByText("You can inspect Item execution but cannot request it."),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /retry|reconcile/iu }),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["queued", "Queued; target result pending"],
    ["processing", "Processing; target result pending"],
    ["failed_retryable", "Retryable failure; no success recorded"],
    ["failed_final", "Final failure; no success recorded"],
    ["mapping_conflict", "Mapping conflict; no mapping changed"],
  ] as const)("renders guarded %s Item truth", async (state, label) => {
    const user = userEvent.setup();
    const detail = itemPublishDetailFixture({ state });
    renderWorkspace(dataSource(), undefined, undefined, itemDataSource(detail));
    await activateItemInspector(user);
    expect(await screen.findByText(label)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Request Item execution" }),
    ).toBeDisabled();
  });

  it("fails closed when Item history view permission is denied", async () => {
    const user = userEvent.setup();
    const detail = itemPublishDetailFixture();
    const loadRequest = vi.fn<ItemPublishDataSource["loadRequest"]>();
    renderWorkspace(
      dataSource(),
      undefined,
      undefined,
      itemDataSource(detail, {
        loadRequest,
        loadRequests: () =>
          Promise.resolve({
            ...itemPublishListFixture(detail),
            permissions: { canExecute: false, canView: false },
          }),
      }),
    );
    await activateItemInspector(user);
    expect(
      (
        await screen.findAllByText(
          "You cannot view Item execution history for this Project.",
        )
      ).length,
    ).toBeGreaterThanOrEqual(1);
    expect(loadRequest).not.toHaveBeenCalled();
  });

  it("does not query unreleased revisions", async () => {
    const loadRequests =
      vi.fn<EngineeringBomPublishRequestDataSource["loadRequests"]>();
    const draft = engineeringBomDetailFixture().revisions[0];
    if (!draft) throw new Error("The EBOM fixture requires a draft revision.");
    renderWorkspace(dataSource({ loadRequests }), draft);
    expect(await screen.findByText("Released revision required")).toBeVisible();
    expect(loadRequests).not.toHaveBeenCalled();
  });

  it("fails closed when the publish-request adapter is absent", () => {
    const detail = engineeringBomDetailFixture();
    renderWithLocale(
      <EngineeringBomPublishRequestWorkspace
        ebom={detail.ebom}
        projectId={ebomProjectId}
        revision={releasedEngineeringBomRevisionFixture()}
      />,
      "en",
    );

    expect(screen.getByText("Unavailable")).toBeVisible();
    expect(
      screen.getByText(
        "The publish-request data source is not configured. No target system was contacted.",
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Prepare publish request" }),
    ).not.toBeInTheDocument();
  });

  it("renders read-only, missing-policy, empty and protected failure states", async () => {
    const list = publishRequestListFixture();
    const { unmount } = renderWithLocale(
      <EngineeringBomPublishRequestWorkspace
        dataSource={dataSource({
          loadRequests: () =>
            Promise.resolve({
              ...list,
              permissions: { view: true, create: false },
              policies: [],
              items: [],
            }),
        })}
        ebom={engineeringBomDetailFixture().ebom}
        projectId={ebomProjectId}
        revision={releasedEngineeringBomRevisionFixture()}
      />,
      "en",
    );
    expect(await screen.findByText("No publish request")).toBeVisible();
    expect(screen.getByText("Publish authority unavailable")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Prepare publish request" }),
    ).toBeDisabled();
    unmount();

    const failure = new NpiApiError({
      type: "https://example.invalid/problems/not-found",
      title: "Not found",
      status: 404,
      code: "EBOM_PUBLISH_REQUEST_UNAVAILABLE",
      traceId: "trace-publish-protected",
      retryable: false,
    });
    renderWorkspace(
      dataSource({ loadRequests: () => Promise.reject(failure) }),
    );
    expect(await screen.findByText("trace-publish-protected")).toBeVisible();
  });
});
