import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import type { RequestFailure } from "../../src/api/http";
import {
  DockedInspector,
  GateTrack,
  LifecycleTrack,
  MetricStrip,
  ObjectHeader,
  SectionAnchors,
} from "../../src/components/object-components";
import {
  DefinitionList,
  ImpactReview,
  Panel,
  SemanticStatus,
  SourceBadge,
  SourceSystemIdentity,
  SyncBadge,
} from "../../src/components/primitives";
import {
  activities,
  gateSteps,
  lifecycleSteps,
} from "../../src/fixtures/prototype";
import { renderWithLocale } from "../support/render";

const source = {
  sourceSystem: "NPI_ONE" as const,
  editableIn: "NPI_ONE" as const,
  syncState: "processing" as const,
};

const paneLayoutFailure: RequestFailure = {
  kind: "network",
  referenceId: "request-pane-layout-failure",
  referenceKind: "request",
};

function dispatchPointer(
  element: Element,
  type: "pointerdown" | "pointermove",
  properties: {
    button?: number;
    clientX: number;
    pointerId: number;
  },
): void {
  const event = new Event(type, { bubbles: true, cancelable: true });
  for (const [name, value] of Object.entries(properties)) {
    Object.defineProperty(event, name, { value });
  }
  fireEvent(element, event);
}

function ControlledInspectorFixture({
  canUpdate = true,
  collapsed: initialCollapsed = false,
  failure = null,
  onChange = vi.fn(),
  onReload = vi.fn(),
  recoveryReason = null,
  status = "ready",
  widthPx: initialWidthPx = 340,
}: {
  canUpdate?: boolean;
  collapsed?: boolean;
  failure?: RequestFailure | null;
  onChange?: (next: { collapsed: boolean; widthPx: number }) => void;
  onReload?: () => void;
  recoveryReason?: "stored_preference_invalid" | null;
  status?: "failed" | "loading" | "ready" | "saving" | "unavailable";
  widthPx?: number;
}): React.JSX.Element {
  const [layout, setLayout] = useState({
    collapsed: initialCollapsed,
    widthPx: initialWidthPx,
  });
  return (
    <div className="worklist-layout">
      <div>fixture worklist</div>
      <DockedInspector
        layout={{
          canUpdate,
          collapsed: layout.collapsed,
          failure,
          onChange: (next) => {
            onChange(next);
            setLayout(next);
          },
          onReload,
          recoveryReason,
          status,
          widthPx: layout.widthPx,
        }}
        title="Fixture inspector"
      >
        <button type="button">Inspector field</button>
      </DockedInspector>
    </div>
  );
}

function ExpandFailureInspectorFixture(): React.JSX.Element {
  const [layout, setLayout] = useState<{
    canUpdate: boolean;
    collapsed: boolean;
    failure: RequestFailure | null;
    status: "failed" | "ready" | "saving";
    widthPx: number;
  }>({
    canUpdate: true,
    collapsed: true,
    failure: null,
    status: "ready",
    widthPx: 340,
  });
  return (
    <div className="worklist-layout">
      <div>fixture worklist</div>
      <DockedInspector
        layout={{
          ...layout,
          onChange: (next) => {
            setLayout((current) => ({
              ...current,
              ...next,
              status: "saving",
            }));
            queueMicrotask(() => {
              setLayout({
                canUpdate: false,
                collapsed: true,
                failure: paneLayoutFailure,
                status: "failed",
                widthPx: 340,
              });
            });
          },
          onReload: vi.fn(),
          recoveryReason: null,
        }}
        title="Fixture inspector"
      >
        <button type="button">Inspector field</button>
      </DockedInspector>
    </div>
  );
}

describe("industrial reusable components", () => {
  it("uses textual, shaped, and iconic status semantics together", () => {
    const { container } = renderWithLocale(
      <SemanticStatus label="Blocked" tone="danger" />,
    );
    expect(screen.getByText("Blocked")).toBeVisible();
    expect(
      container.querySelector(
        '[data-status-tone="danger"] .semantic-status__shape',
      ),
    ).toBeInTheDocument();
    expect(container.querySelector('[data-icon="error"]')).toBeInTheDocument();
  });

  it("renders flat panels, provenance, sync status, and definition rows", () => {
    renderWithLocale(
      <Panel
        actions={<button type="button">fixture action</button>}
        title="Fixture panel"
      >
        <SourceBadge source={source} />
        <SourceSystemIdentity sourceSystem="ERPNEXT" />
        <SourceSystemIdentity sourceSystem="COMPUTED" />
        <SyncBadge state="processing" />
        <DefinitionList
          rows={[{ label: "Code", value: "PJ-26018", exempt: "identifier" }]}
        />
      </Panel>,
    );
    expect(
      screen.getByRole("heading", { name: "Fixture panel" }),
    ).toBeVisible();
    expect(
      screen.getByRole("img", { name: "LaunchFlow platform" }),
    ).toHaveAttribute("data-brand-context", "platform-source");
    expect(screen.getByText("ERPNext")).toBeVisible();
    expect(screen.getByText("Computed")).toBeVisible();
    expect(screen.getByText("Processing")).toBeVisible();
    expect(screen.getByText("PJ-26018")).toHaveAttribute(
      "data-language-exempt",
      "identifier",
    );
  });

  it("keeps definition rows stable when localized labels are identical", () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    try {
      renderWithLocale(
        <DefinitionList
          rows={[
            { label: "项目", rowKey: "item", value: "Tooling review" },
            { label: "项目", rowKey: "project", value: "NPI-26018" },
          ]}
        />,
      );
      expect(screen.getByText("Tooling review")).toBeVisible();
      expect(screen.getByText("NPI-26018")).toBeVisible();
      expect(consoleError.mock.calls.flat().join(" ")).not.toContain(
        "same key",
      );
    } finally {
      consoleError.mockRestore();
    }
  });

  it("renders object identity, one primary action, gate and tooling tracks", async () => {
    const user = userEvent.setup();
    const onPrimary = vi.fn();
    const { container } = renderWithLocale(
      <>
        <ObjectHeader
          code="PJ-26018"
          metadata={<span>fixture metadata</span>}
          name="Fixture project"
          primaryAction={{ label: "Fixture primary", onClick: onPrimary }}
          source={source}
          status={<SemanticStatus label="Active" tone="info" />}
        />
        <GateTrack steps={gateSteps} />
        <LifecycleTrack steps={lifecycleSteps} />
        <MetricStrip
          metrics={[
            { label: "Progress", value: "68%" },
            { label: "Risk", value: 1, tone: "danger" },
          ]}
        />
      </>,
    );
    expect(
      container.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(1);
    expect(
      screen
        .getByLabelText("Gate track")
        .querySelector('[aria-current="step"]'),
    ).toBeInTheDocument();
    expect(
      screen
        .getByLabelText("Tooling lifecycle")
        .querySelector('[aria-current="step"]'),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Fixture primary" }));
    expect(onPrimary).toHaveBeenCalledOnce();
  });

  it("shows a contextual activity timeline with locale-aware time", () => {
    renderWithLocale(
      <DockedInspector activities={activities} title="Fixture inspector">
        <p>fixture properties</p>
      </DockedInspector>,
      "zh",
    );
    expect(screen.getByLabelText("Fixture inspector")).toBeVisible();
    expect(screen.getAllByRole("listitem")).toHaveLength(activities.length);
    expect(screen.getAllByRole("time")[0]).toHaveAttribute(
      "datetime",
      activities[0]?.occurredAt,
    );
    expect(document.body).not.toHaveTextContent("⟦Missing:");
    expect(screen.getByText("CMT-0007")).toBeVisible();
    expect(screen.getByText("G4-D03")).toBeVisible();
  });

  it("keeps the legacy inspector preference path isolated at its existing default", async () => {
    const user = userEvent.setup();
    const first = renderWithLocale(
      <div className="worklist-layout">
        <div>worklist</div>
        <DockedInspector title="Fixture inspector">
          <p>fixture properties</p>
        </DockedInspector>
      </div>,
    );
    const width = screen.getByRole("slider", { name: "Inspector width" });
    expect(width).toHaveValue("320");
    fireEvent.change(width, { target: { value: "400" } });
    expect(localStorage.getItem("npi-one-inspector-width")).toBe("400");
    expect(document.querySelector(".worklist-layout")).toHaveStyle(
      "--npi-inspector-width: 400px",
    );
    await user.click(
      screen.getByRole("button", { name: "Collapse inspector" }),
    );
    expect(screen.queryByText("fixture properties")).not.toBeInTheDocument();
    expect(localStorage.getItem("npi-one-inspector-collapsed")).toBe("true");

    first.unmount();
    renderWithLocale(
      <div className="worklist-layout">
        <div>worklist</div>
        <DockedInspector title="Fixture inspector">
          <p>fixture properties</p>
        </DockedInspector>
      </div>,
    );
    await user.click(screen.getByRole("button", { name: "Expand inspector" }));
    expect(screen.getByRole("slider", { name: "Inspector width" })).toHaveValue(
      "400",
    );
  });

  it("uses the controlled boundary without reading or writing legacy storage and clamps unsafe width input", () => {
    globalThis.localStorage.setItem("npi-one-inspector-width", "400");
    globalThis.localStorage.setItem("npi-one-inspector-collapsed", "true");
    const getItem = vi.spyOn(Storage.prototype, "getItem");
    const setItem = vi.spyOn(Storage.prototype, "setItem");

    renderWithLocale(<ControlledInspectorFixture widthPx={999} />);

    expect(
      screen.getByRole("separator", { name: "Resize inspector" }),
    ).toHaveAttribute("aria-valuenow", "480");
    expect(document.querySelector(".worklist-layout")).toHaveStyle(
      "--npi-inspector-width: 480px",
    );
    expect(
      screen.queryByRole("slider", { name: "Inspector width" }),
    ).not.toBeInTheDocument();
    expect(getItem).not.toHaveBeenCalledWith("npi-one-inspector-width");
    expect(getItem).not.toHaveBeenCalledWith("npi-one-inspector-collapsed");
    expect(setItem).not.toHaveBeenCalledWith(
      "npi-one-inspector-width",
      expect.anything(),
    );
    expect(setItem).not.toHaveBeenCalledWith(
      "npi-one-inspector-collapsed",
      expect.anything(),
    );
  });

  it("commits controlled keyboard resize and double-click reset through the real separator", () => {
    const onChange = vi.fn();
    renderWithLocale(
      <ControlledInspectorFixture onChange={onChange} widthPx={400} />,
    );
    const separator = screen.getByRole("separator", {
      name: "Resize inspector",
    });

    fireEvent.keyDown(separator, { key: "ArrowLeft" });
    expect(onChange).toHaveBeenLastCalledWith({
      collapsed: false,
      widthPx: 420,
    });
    fireEvent.keyDown(separator, { key: "ArrowRight" });
    expect(onChange).toHaveBeenLastCalledWith({
      collapsed: false,
      widthPx: 400,
    });

    fireEvent.doubleClick(separator);
    expect(onChange).toHaveBeenLastCalledWith({
      collapsed: false,
      widthPx: 340,
    });
  });

  it("reverts controlled pointer preview geometry without saving when resize is cancelled", () => {
    const onChange = vi.fn();
    renderWithLocale(<ControlledInspectorFixture onChange={onChange} />);
    const separator = screen.getByRole("separator", {
      name: "Resize inspector",
    });
    Object.defineProperties(separator, {
      releasePointerCapture: { value: vi.fn() },
      setPointerCapture: { value: vi.fn() },
    });

    dispatchPointer(separator, "pointerdown", {
      button: 0,
      clientX: 400,
      pointerId: 12,
    });
    dispatchPointer(separator, "pointermove", {
      clientX: 360,
      pointerId: 12,
    });
    expect(document.querySelector(".worklist-layout")).toHaveStyle(
      "--npi-inspector-width: 380px",
    );

    fireEvent.keyDown(separator, { key: "Escape" });
    expect(document.querySelector(".worklist-layout")).toHaveStyle(
      "--npi-inspector-width: 340px",
    );
    expect(onChange).not.toHaveBeenCalled();
  });

  it("keeps controlled content mounted and moves focus to the expand control when collapsed", async () => {
    const user = userEvent.setup();
    renderWithLocale(<ControlledInspectorFixture />);
    const field = screen.getByRole("button", { name: "Inspector field" });
    field.focus();
    expect(field).toHaveFocus();

    await user.click(
      screen.getByRole("button", { name: "Collapse inspector" }),
    );

    const expand = screen.getByRole("button", { name: "Expand inspector" });
    expect(expand).toHaveFocus();
    expect(field).toBeInTheDocument();
    expect(field).not.toBeVisible();

    await user.click(expand);
    expect(screen.getByRole("button", { name: "Inspector field" })).toBe(field);
    expect(field).toBeVisible();
  });

  it("keeps failed controlled layout truth and reload reachable when collapsed", async () => {
    const onReload = vi.fn();
    const user = userEvent.setup();
    renderWithLocale(
      <ControlledInspectorFixture
        canUpdate={false}
        collapsed={true}
        failure={paneLayoutFailure}
        onReload={onReload}
        status="failed"
      />,
    );

    expect(screen.getByText("Not saved")).toBeVisible();
    expect(screen.getByText("The service could not be reached.")).toBeVisible();
    expect(screen.getByText("request-pane-layout-failure")).toBeVisible();
    expect(document.querySelector(".worklist-layout")).toHaveStyle(
      "--npi-inspector-width: 340px",
    );
    const reload = screen.getByRole("button", { name: "Reload pane layout" });
    expect(reload).toBeEnabled();
    await user.click(reload);
    expect(onReload).toHaveBeenCalledOnce();
  });

  it("moves failed expansion recovery focus to traceable reload instead of a disabled expand control", async () => {
    const user = userEvent.setup();
    renderWithLocale(<ExpandFailureInspectorFixture />);

    await user.click(screen.getByRole("button", { name: "Expand inspector" }));

    await waitFor(() => {
      expect(screen.getByText("Not saved")).toBeVisible();
    });
    expect(screen.getByText("The service could not be reached.")).toBeVisible();
    expect(screen.getByText("request-pane-layout-failure")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Expand inspector" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Reload pane layout" }),
    ).toHaveFocus();
  });

  it("keeps in-progress controlled layout truth visible on the collapsed strip", () => {
    renderWithLocale(
      <ControlledInspectorFixture collapsed={true} status="saving" />,
    );

    expect(screen.getByText("Saving")).toBeVisible();
    expect(screen.getByText("Saving pane layout")).toBeInTheDocument();
  });

  it("shows the server-owned invalid-storage recovery truth instead of confirmed", () => {
    renderWithLocale(
      <ControlledInspectorFixture recoveryReason="stored_preference_invalid" />,
    );

    expect(screen.getByText("Defaults active")).toBeVisible();
    expect(
      screen.getByText(
        "Stored pane layout was invalid. The default layout is active.",
      ),
    ).toBeVisible();
    expect(screen.queryByText("Confirmed")).not.toBeInTheDocument();
  });

  it("renders expanded controlled failure details and the reload path", async () => {
    const onReload = vi.fn();
    const user = userEvent.setup();
    renderWithLocale(
      <ControlledInspectorFixture
        canUpdate={false}
        failure={paneLayoutFailure}
        onReload={onReload}
        status="failed"
      />,
    );

    expect(
      screen.getByText(
        "Pane layout was not saved. The last confirmed layout remains active.",
      ),
    ).toBeVisible();
    expect(screen.getByText("The service could not be reached.")).toBeVisible();
    expect(screen.getByText("request-pane-layout-failure")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Reload pane layout" }),
    );
    expect(onReload).toHaveBeenCalledOnce();
  });

  it("moves keyboard focus to the selected object-page section", async () => {
    const user = userEvent.setup();
    const scrollIntoView = vi.fn();
    const originalScrollIntoView = Object.getOwnPropertyDescriptor(
      globalThis.HTMLElement.prototype,
      "scrollIntoView",
    );
    Object.defineProperty(globalThis.HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    renderWithLocale(
      <>
        <SectionAnchors
          sections={[
            { id: "fixture-structure", label: "Fixture structure" },
            { id: "fixture-inspector", label: "Fixture inspector" },
          ]}
        />
        <Panel id="fixture-structure" title="Fixture structure">
          <p>structure</p>
        </Panel>
        <DockedInspector id="fixture-inspector" title="Fixture inspector">
          <p>properties</p>
        </DockedInspector>
      </>,
    );

    await user.click(screen.getByRole("button", { name: "Fixture inspector" }));
    expect(
      screen.getByRole("complementary", { name: "Fixture inspector" }),
    ).toHaveFocus();
    expect(scrollIntoView).toHaveBeenCalledWith({ block: "nearest" });
    if (originalScrollIntoView) {
      Object.defineProperty(
        globalThis.HTMLElement.prototype,
        "scrollIntoView",
        originalScrollIntoView,
      );
    } else {
      Reflect.deleteProperty(
        globalThis.HTMLElement.prototype,
        "scrollIntoView",
      );
    }
  });
});

describe("high-risk impact review", () => {
  const details = {
    objectIdentity: "PJ-26018 / G5",
    version: "v3",
    impact: "Five exact evidence versions will be locked.",
    permission: "Gate approver permission is required.",
    irreversible: "The decision snapshot cannot be overwritten.",
    failureHandling: "A failed command changes nothing.",
    audit: "The actor, reason, result, and trace ID will be recorded.",
  };

  it("focuses the dialog, exposes an impact summary, and handles both decisions", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    renderWithLocale(
      <ImpactReview
        confirmLabel="Prepare command"
        details={details}
        onCancel={onCancel}
        onConfirm={onConfirm}
        title="Gate decision impact review"
      />,
    );
    const dialog = screen.getByRole("dialog", {
      name: "Gate decision impact review",
    });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(
      screen.getByRole("heading", { name: "Gate decision impact review" }),
    ).toHaveFocus();
    expect(screen.getByLabelText("Reason")).toBeVisible();
    expect(dialog).toHaveTextContent(
      "Five exact evidence versions will be locked.",
    );

    const confirm = screen.getByRole("button", { name: "Prepare command" });
    expect(confirm).toBeDisabled();
    await user.type(screen.getByLabelText("Reason"), "Evidence reviewed");
    await user.click(confirm);
    expect(onConfirm).toHaveBeenCalledWith("Evidence reviewed");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("accepts 4000 reason characters and constrains a 4001-character change", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    renderWithLocale(
      <ImpactReview
        confirmLabel="Prepare command"
        details={details}
        onCancel={vi.fn()}
        onConfirm={onConfirm}
        title="Gate decision impact review"
      />,
    );
    const reason = screen.getByLabelText("Reason");
    const maximum = `${"x".repeat(3999)}a`;
    fireEvent.change(reason, { target: { value: maximum } });
    expect(reason).toHaveAttribute("maxlength", "4000");
    expect(reason).toHaveValue(maximum);

    const tooLong = "y".repeat(4001);
    fireEvent.change(reason, { target: { value: tooLong } });
    expect(reason).toHaveValue("y".repeat(4000));
    await user.click(screen.getByRole("button", { name: "Prepare command" }));
    expect(onConfirm).toHaveBeenCalledWith("y".repeat(4000));
  });
});
