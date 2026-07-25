import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

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
        <SyncBadge state="processing" />
        <DefinitionList
          rows={[{ label: "Code", value: "PJ-26018", exempt: "identifier" }]}
        />
      </Panel>,
    );
    expect(
      screen.getByRole("heading", { name: "Fixture panel" }),
    ).toBeVisible();
    expect(screen.getByText("NPI One")).toBeVisible();
    expect(screen.getByText("Processing")).toBeVisible();
    expect(screen.getByText("PJ-26018")).toHaveAttribute(
      "data-language-exempt",
      "identifier",
    );
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

  it("resizes, collapses, and restores the docked inspector preference", async () => {
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
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
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
