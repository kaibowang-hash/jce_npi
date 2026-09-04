import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  FormalQualityLinkDataSource,
  FormalQualityLinkItem,
  FormalQualitySourceReference,
} from "../../src/api/formal-quality-link-data-source";
import { NpiApiError, NpiTransportError } from "../../src/api/http";
import { FormalQualityLinkInspector } from "../../src/pages/formal-quality-link-inspector";
import { renderWithLocale } from "../support/render";

const id = (tail: string): string =>
  `10000000-0000-4000-8000-${tail.padStart(12, "0")}`;
const hash = (value: string): string => value.repeat(64);
const projectId = id("1");
const source: FormalQualitySourceReference = {
  scopeGlobalId: id("2"),
  scopeKind: "trial_round",
  sourceCapability: true,
  sourceGlobalId: id("3"),
  sourceKind: "trial_defect",
  sourceSnapshotHash: hash("a"),
  sourceVersion: 2,
};
const candidate = {
  observationGlobalId: id("4"),
  headGlobalId: id("5"),
  headOptimisticVersion: 3,
  headHash: hash("b"),
  scopeGlobalId: id("2"),
  values: {
    recordKind: "quality_inspection" as const,
    statusCode: "Completed",
    resultCode: "Accepted",
    observedAt: "2026-08-26T08:00:00Z",
  },
};

function item(
  state: "current" | "drifted" | "unavailable" = "current",
): FormalQualityLinkItem {
  return {
    linkHead: {
      globalId: id("6"),
      sourceKind: source.sourceKind,
      sourceGlobalId: source.sourceGlobalId,
      optimisticVersion: 1,
      currentObservationGlobalId: candidate.observationGlobalId,
      currentProjectionHeadGlobalId: candidate.headGlobalId,
      currentProjectionHeadVersion: 3,
      headHash: hash("c"),
    },
    linkRevision: {
      globalId: id("7"),
      revisionNumber: 1,
      source: {
        sourceKind: source.sourceKind,
        sourceGlobalId: source.sourceGlobalId,
        sourceVersion: 2,
        sourceState: "open",
        sourceSnapshotHash: hash("a"),
      },
      formalObservation: {
        observationGlobalId: candidate.observationGlobalId,
        headGlobalId: candidate.headGlobalId,
        headOptimisticVersion: 3,
        recordKind: "quality_inspection",
        statusCode: "Completed",
        resultCode: "Accepted",
        payloadHash: hash("d"),
        observationHash: hash("e"),
        headHash: hash("b"),
      },
    },
    reconciliation: {
      state,
      reasonCode:
        state === "current"
          ? "linked_truth_current"
          : state === "drifted"
            ? "linked_source_advanced"
            : "current_truth_unavailable",
    },
    formalQualityInterpretation: {
      state: "unavailable",
      reasonCode: "raw_formal_quality_codes_not_interpreted",
    },
  };
}

function session(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            allowedLanguages: ["en", "zh", "zh-TW"],
            catalog: { language: "en", messages: {}, version: hash("f") },
            csrfToken: "formal-quality-link-csrf-token-fixture-0001",
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

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("formal quality link inspector", () => {
  it("renders loading then honest unavailable read-only truth", async () => {
    let resolveLoad:
      | ((
          value: Awaited<ReturnType<FormalQualityLinkDataSource["load"]>>,
        ) => void)
      | undefined;
    const dataSource: FormalQualityLinkDataSource = {
      load: vi.fn(
        () =>
          new Promise<Awaited<ReturnType<FormalQualityLinkDataSource["load"]>>>(
            (resolve) => {
              resolveLoad = resolve;
            },
          ),
      ),
      link: vi.fn(),
    };
    renderWithLocale(
      <FormalQualityLinkInspector
        dataSource={dataSource}
        projectId={projectId}
        source={{ ...source, sourceCapability: false }}
      />,
    );
    expect(
      screen.getByText("Loading formal quality truth"),
    ).toBeInTheDocument();
    resolveLoad?.({
      collection: {
        projectGlobalId: projectId,
        permissions: { view: true, link: false },
        items: [],
      },
      candidate: null,
    });
    expect(
      await screen.findByText("No formal quality reference available"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "This formal quality reference is read only in the current Project context.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Link formal quality reference" }),
    ).not.toBeInTheDocument();
  });

  it("shows raw codes and reconciliation without interpreting a pass", async () => {
    const dataSource: FormalQualityLinkDataSource = {
      load: vi.fn().mockResolvedValue({
        collection: {
          projectGlobalId: projectId,
          permissions: { view: true, link: false },
          items: [item("drifted")],
        },
        candidate,
      }),
      link: vi.fn(),
    };
    renderWithLocale(
      <FormalQualityLinkInspector
        dataSource={dataSource}
        projectId={projectId}
        source={source}
      />,
    );
    expect(
      (await screen.findAllByText("Drifted formal quality link")).length,
    ).toBe(2);
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("Accepted")).toBeInTheDocument();
    expect(screen.getByText(/never interpreted as a pass/)).toBeInTheDocument();
  });

  it.each([
    ["current", "Current formal quality link"],
    ["unavailable", "Formal quality truth unavailable"],
  ] as const)(
    "renders the exact %s reconciliation state",
    async (state, label) => {
      const dataSource: FormalQualityLinkDataSource = {
        load: vi.fn().mockResolvedValue({
          collection: {
            projectGlobalId: projectId,
            permissions: { view: true, link: false },
            items: [item(state)],
          },
          candidate: null,
        }),
        link: vi.fn(),
      };
      renderWithLocale(
        <FormalQualityLinkInspector
          dataSource={dataSource}
          projectId={projectId}
          source={source}
        />,
      );
      expect((await screen.findAllByText(label)).length).toBe(2);
    },
  );

  it.each([
    [true, false],
    [false, true],
  ])(
    "requires both source capability %s and server capability %s",
    async (sourceCapability, serverCapability) => {
      const dataSource: FormalQualityLinkDataSource = {
        load: vi.fn().mockResolvedValue({
          collection: {
            projectGlobalId: projectId,
            permissions: { view: true, link: serverCapability },
            items: [],
          },
          candidate,
        }),
        link: vi.fn(),
      };
      renderWithLocale(
        <FormalQualityLinkInspector
          dataSource={dataSource}
          projectId={projectId}
          source={{ ...source, sourceCapability }}
        />,
      );
      expect(
        await screen.findByText(
          "This formal quality reference is read only in the current Project context.",
        ),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", {
          name: "Link formal quality reference",
        }),
      ).not.toBeInTheDocument();
    },
  );

  it.each([
    [
      new NpiTransportError("network", "request-quality-link-load", "request"),
      "The service could not be reached.",
    ],
    [
      new NpiApiError({
        code: "FORMAL_QUALITY_LINK_CONFLICT",
        retryable: false,
        status: 409,
        title: "The formal quality link changed.",
        traceId: "trace-quality-link-conflict",
        type: "urn:npi:error:formal-quality-link-conflict",
      }),
      "The formal quality link changed.",
    ],
  ])("renders a fail-closed load boundary", async (failure, title) => {
    const dataSource: FormalQualityLinkDataSource = {
      load: vi.fn().mockRejectedValue(failure),
      link: vi.fn(),
    };
    renderWithLocale(
      <FormalQualityLinkInspector
        dataSource={dataSource}
        projectId={projectId}
        source={source}
      />,
    );
    expect(await screen.findByText(title)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Link formal quality reference" }),
    ).not.toBeInTheDocument();
  });

  it("opens one impact review and links only after confirmation", async () => {
    session();
    const linked = item();
    const link = vi
      .fn<FormalQualityLinkDataSource["link"]>()
      .mockResolvedValue(linked);
    const dataSource: FormalQualityLinkDataSource = {
      load: vi.fn().mockResolvedValue({
        collection: {
          projectGlobalId: projectId,
          permissions: { view: true, link: true },
          items: [],
        },
        candidate,
      }),
      link,
    };
    const user = userEvent.setup();
    renderWithLocale(
      <FormalQualityLinkInspector
        dataSource={dataSource}
        projectId={projectId}
        source={source}
      />,
    );
    await user.click(
      await screen.findByRole("button", {
        name: "Link formal quality reference",
      }),
    );
    const dialog = screen.getByRole("dialog", {
      name: "Review formal quality link",
    });
    expect(dialog).toBeInTheDocument();
    expect(link).not.toHaveBeenCalled();
    await user.click(
      within(dialog).getByRole("button", {
        name: "Link formal quality reference",
      }),
    );
    await waitFor(() => {
      expect(link).toHaveBeenCalledTimes(1);
    });
    expect(link.mock.calls[0]?.[1]).toMatchObject({
      source,
      candidate,
      expectedLinkHeadVersion: 0,
    });
    expect(
      await screen.findByText(
        "The exact formal quality reference is linked and audited.",
      ),
    ).toBeInTheDocument();
  });
});
