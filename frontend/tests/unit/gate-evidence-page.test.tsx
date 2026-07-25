import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { JSX } from "react";

import {
  isGateReviewResponse,
  type GateReviewDataSource,
} from "../../src/api/gate-review-data-source";
import {
  NpiApiError,
  NpiTransportError,
  type ProblemDetails,
} from "../../src/api/http";
import type {
  GateReviewDecisionBlockedReasonCode,
  GateReviewViewModel,
} from "../../src/domain/view-models";
import { I18nProvider, type Locale, useI18n } from "../../src/i18n/runtime";
import GateEvidencePage, {
  GATE_REVIEW_RECEIPT_STORAGE_KEY,
} from "../../src/pages/gate-evidence-page";
import {
  gateReviewDecidedFixture,
  gateReviewDecisionReadyFixture,
  gateReviewExceptionEligibleFixture,
  gateReviewExceptionHistoryFixture,
  gateReviewFixture,
  gateReviewFixtureIds,
  gateReviewNoCycleFixture,
  gateReviewRequiresReviewFixture,
  pendingExceptionFixture,
} from "../support/gate-review-fixture";
import { renderWithLocale } from "../support/render";

const csrfToken = "c".repeat(32);
const decisionBlockedReasonCases = [
  ["REVIEWS_INCOMPLETE", "Every selected review must approve this outcome."],
  ["FILE_EVIDENCE_UNSAFE", "File evidence is not safe and current."],
  ["GATE_BLOCKED", "Resolve every blocking item before this outcome."],
  ["REQUIRED_P0_EVIDENCE_MISSING", "Required P0 evidence is missing."],
  ["REQUIRED_EVIDENCE_MISSING", "Required evidence is missing."],
  ["GATE_INPUT_CHANGED", "The Gate input changed."],
  ["APPROVED_EXCEPTION_REQUIRED", "A current approved exception is required."],
] as const satisfies readonly (readonly [
  GateReviewDecisionBlockedReasonCode,
  string,
])[];

function sessionBootstrap(
  userId = "reviewer@example.invalid",
  language: Locale = "en",
  token = csrfToken,
): unknown {
  return {
    allowedLanguages: ["en", "zh", "zh-TW"],
    catalog: {
      language,
      messages: {},
      version: "a".repeat(64),
    },
    csrfToken: token,
    language,
    userId,
  };
}

function problem(status: number, code: string, retryable = false): NpiApiError {
  const value: ProblemDetails = {
    code,
    retryable,
    status,
    title: `Controlled ${code} response`,
    traceId: `trace-${code.toLowerCase()}`,
    type: `urn:npi:problem:${code.toLowerCase()}`,
  };
  return new NpiApiError(value);
}

function unexpectedCommand(): Promise<GateReviewViewModel> {
  return Promise.reject(new Error("Unexpected Gate review command."));
}

function resolvedDataSource(
  view: GateReviewViewModel,
  overrides: Partial<GateReviewDataSource> = {},
): GateReviewDataSource {
  return {
    decideException: vi.fn(unexpectedCommand),
    decideGate: vi.fn(unexpectedCommand),
    load: vi.fn(() => Promise.resolve(view)),
    reconcileCommandReceipt: vi.fn(() =>
      Promise.reject(new Error("Unexpected Gate review receipt query.")),
    ),
    reopenGate: vi.fn(unexpectedCommand),
    requestException: vi.fn(unexpectedCommand),
    startReview: vi.fn(unexpectedCommand),
    submitReview: vi.fn(unexpectedCommand),
    ...overrides,
  };
}

function rejectedDataSource(error: Error): GateReviewDataSource {
  return resolvedDataSource(gateReviewFixture(), {
    load: vi.fn(() => Promise.reject(error)),
  });
}

function renderPage(
  dataSource: GateReviewDataSource,
  navigate = vi.fn<(target: string) => void>(),
): {
  fixture: GateReviewViewModel;
  navigate: ReturnType<typeof vi.fn<(target: string) => void>>;
} {
  const fixture = gateReviewFixture();
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

function activeCycle(view: GateReviewViewModel) {
  if (!view.activeCycle) throw new Error("The test fixture requires a cycle.");
  return view.activeCycle;
}

function commandUpdatedView(
  view: GateReviewViewModel,
  cycleVersion = activeCycle(view).version + 1,
): GateReviewViewModel {
  return {
    ...view,
    activeCycle: {
      ...activeCycle(view),
      version: cycleVersion,
    },
  };
}

function deferred<T>(): {
  promise: Promise<T>;
  reject: (error: unknown) => void;
  resolve: (value: T) => void;
} {
  let resolvePromise!: (value: T) => void;
  let rejectPromise!: (error: unknown) => void;
  const promise = new Promise<T>((resolve, reject) => {
    resolvePromise = resolve;
    rejectPromise = reject;
  });
  return { promise, reject: rejectPromise, resolve: resolvePromise };
}

function persistedReceiptMarker(
  fixture: GateReviewViewModel,
  actor = "reviewer@example.invalid",
): Record<string, string> {
  return {
    actor,
    gate: fixture.gate.globalId,
    issuedAt: "2026-07-24T09:30:00.000Z",
    key: "gate-review:11111111-1111-4111-8111-111111111111",
    operation: "gate.review.submit",
    project: fixture.project.globalId,
  };
}

function LocaleSwitchControl({ locale }: { locale: Locale }): JSX.Element {
  const { setLocale } = useI18n();
  return (
    <button
      onClick={() => {
        setLocale(locale);
      }}
      type="button"
    >
      Switch test locale
    </button>
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify(sessionBootstrap()), { status: 200 }),
      ),
    ),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("live Gate Review Room", () => {
  it("renders the accepted route as one dense three-pane review workspace", async () => {
    const fixture = gateReviewFixture();
    expect(isGateReviewResponse(fixture)).toBe(true);
    expect(isGateReviewResponse(gateReviewNoCycleFixture())).toBe(true);
    expect(isGateReviewResponse(gateReviewDecisionReadyFixture())).toBe(true);
    expect(isGateReviewResponse(gateReviewDecidedFixture())).toBe(true);
    expect(isGateReviewResponse(gateReviewRequiresReviewFixture())).toBe(true);
    const dataSource = resolvedDataSource(fixture);
    renderPage(dataSource);

    expect(
      screen.getByRole("status", { name: "Loading Gate Review Room" }),
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
    expect(
      screen.getByRole("table", { name: "Frozen Gate requirements" }),
    ).toBeVisible();
    expect(
      screen.getByRole("table", { name: "Selected review steps" }),
    ).toBeVisible();
    expect(screen.getAllByText("ENGINEERING_REVIEW").length).toBeGreaterThan(0);
    expect(screen.getAllByText("TOOLING_REVIEW").length).toBeGreaterThan(0);
    expect(screen.getByText("Waiting for prior sequence")).toBeVisible();
    expect(
      screen.getByText("Synthetic unresolved dimensional issue"),
    ).toBeVisible();
    expect(
      screen.getByRole("complementary", { name: "Review inspector" }),
    ).toBeVisible();
    expect(document.body).not.toHaveTextContent("/private/files/");
    await screen.findByRole("button", {
      name: "Submit review",
    });
    expect(
      document.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(1);
  });

  it("renders immutable review actor, opinion, input, policy, and record hashes", async () => {
    const fixture = gateReviewFixture();
    renderPage(resolvedDataSource(fixture));

    const records = await screen.findByRole("table", {
      name: "Immutable review records",
    });
    expect(
      within(records).getByText("tooling.reviewer@example.invalid"),
    ).toBeVisible();
    expect(
      within(records).getByText(
        "The tooling input is acceptable for this synthetic review.",
      ),
    ).toBeVisible();
    expect(
      within(records).getByText(activeCycle(fixture).inputHash),
    ).toBeVisible();
    expect(within(records).getByText("7".repeat(64))).toBeVisible();
    expect(
      within(records).getByText(activeCycle(fixture).policyRef.snapshotHash),
    ).toBeVisible();
  });

  it("renders the complete controlled exception request and decision audit", async () => {
    const fixture = gateReviewExceptionHistoryFixture();
    renderPage(resolvedDataSource(fixture));

    const history = await screen.findByRole("list", {
      name: "Gate review exceptions",
    });
    expect(
      within(history).getByText("A bounded synthetic exception is required."),
    ).toBeVisible();
    expect(
      within(history).getByText(
        "The synthetic deviation remains visible until closure.",
      ),
    ).toBeVisible();
    expect(
      within(history).getByText(/Synthetic Engineering Reviewer/u),
    ).toBeVisible();
    expect(
      within(history).getByText(/Synthetic Exception Authority/u),
    ).toBeVisible();
    expect(
      within(history).getByText("The bounded synthetic exception is approved."),
    ).toBeVisible();
    expect(
      within(history).getByText(gateReviewFixtureIds.closureAction),
    ).toBeVisible();
    expect(
      within(history).getByText("Approved through recorded expiry"),
    ).toBeVisible();
  });

  it("expands exact frozen requirement, evidence, blocker, and dependency rows for a decision", async () => {
    const fixture = gateReviewDecidedFixture();
    renderPage(resolvedDataSource(fixture));
    const user = userEvent.setup();

    await user.click(await screen.findByText("Frozen decision input rows"));
    expect(
      screen.getByRole("table", { name: "Frozen requirements" }),
    ).toBeVisible();
    expect(
      screen.getByRole("table", { name: "Frozen evidence" }),
    ).toBeVisible();
    expect(
      screen.getByRole("table", { name: "Frozen blockers" }),
    ).toBeVisible();
    expect(
      screen.getByRole("table", { name: "Frozen dependencies" }),
    ).toBeVisible();
    expect(screen.getAllByText("DESIGN_BASELINE").length).toBeGreaterThan(0);
    expect(screen.getAllByText("d".repeat(64)).length).toBeGreaterThan(0);
  });

  it("preserves embedded P4-03 evidence selection and truthful empty evidence", async () => {
    const user = userEvent.setup();
    renderPage(resolvedDataSource(gateReviewFixture()));
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

  it.each(decisionBlockedReasonCases)(
    "renders the controlled decision-readiness reason %s",
    async (code, expected) => {
      const fixture = gateReviewFixture();
      const view: GateReviewViewModel = {
        ...fixture,
        decisionReadiness: {
          allowedOutcomes: [],
          blockedReasons: (["pass", "conditional_pass", "reject"] as const).map(
            (outcome) => ({ code, outcome }),
          ),
        },
      };
      renderPage(resolvedDataSource(view));

      const heading = await screen.findByRole("heading", {
        name: "Gate decision readiness",
      });
      const readiness = heading.closest("section");
      if (!readiness) {
        throw new Error("The Gate decision readiness section is missing.");
      }
      expect(within(readiness).getAllByText(expected)).toHaveLength(3);
    },
  );

  it("shows sequential wait and read-only states without inferring authority", async () => {
    const fixture = gateReviewFixture();
    const readOnly: GateReviewViewModel = {
      ...fixture,
      permissions: {
        canApproveException: false,
        canDecide: false,
        canRequestException: false,
        canReopen: false,
        canReview: false,
        canStartReview: false,
        canView: true,
      },
    };
    renderPage(resolvedDataSource(readOnly));

    expect(await screen.findByText("Waiting for prior sequence")).toBeVisible();
    expect(
      screen.getAllByText("No permitted review action").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByText(
        "The server returned view access without an applicable review command for this actor and state.",
      ),
    ).toBeVisible();
    expect(
      document.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(0);
  });

  it("shows exact dependency history and exposes only start acknowledgement for requires-review", async () => {
    const fixture = gateReviewRequiresReviewFixture();
    renderPage(resolvedDataSource(fixture));

    expect(
      await screen.findAllByText("Gate input snapshot changed"),
    ).not.toHaveLength(0);
    expect(screen.getByText("Decision invalidated")).toBeVisible();
    expect(screen.getAllByText("c".repeat(64)).length).toBeGreaterThan(0);
    expect(screen.getAllByText("5".repeat(64)).length).toBeGreaterThan(0);
    expect(
      screen.getByText("A controlled Gate source object changed."),
    ).toBeVisible();
    expect(
      await screen.findByRole("button", {
        name: "Acknowledge change and start review",
      }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", {
        name: "Submit review",
      }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: "Decide Gate" })).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Request controlled exception" }),
    ).toBeNull();
    expect(
      document.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(1);
    expect(
      screen.queryByRole("combobox", { name: "Published review policy" }),
    ).toBeNull();
    expect(
      screen.queryByRole("combobox", { name: "Authority assignment" }),
    ).toBeNull();
    expect(
      screen.getByRole("list", { name: "Authority assignment" }),
    ).toBeVisible();
  });

  it("does not present a stale input-change banner for historical dependency lineage", async () => {
    const invalidated = gateReviewRequiresReviewFixture();
    if (!invalidated.activeCycle) {
      throw new Error("The fixture requires a dependency cycle.");
    }
    const acknowledged: GateReviewViewModel = {
      ...invalidated,
      activeCycle: {
        ...invalidated.activeCycle,
        selectedSteps: invalidated.activeCycle.selectedSteps.map(
          (step, index) => ({
            ...step,
            state: index === 0 ? "available" : "waiting",
          }),
        ),
      },
      gate: {
        ...invalidated.gate,
        reviewState: "in_review",
      },
      permissions: {
        ...invalidated.permissions,
        canStartReview: false,
      },
    };
    renderPage(resolvedDataSource(acknowledged));

    await screen.findByRole("heading", {
      level: 1,
      name: /Synthetic initiation evidence/u,
    });
    expect(document.querySelector(".scenario-banner--partial")).toBeNull();
    expect(screen.getByText("Gate input snapshot changed")).toBeVisible();
    expect(screen.getByText("Decision invalidated")).toBeVisible();
    expect(
      screen.getByText("A controlled Gate source object changed."),
    ).toBeVisible();
  });

  it("keeps multiple review-step choices distinguishable by exact step identity", async () => {
    const fixture = gateReviewFixture();
    if (!fixture.activeCycle) throw new Error("The fixture requires a cycle.");
    const engineering = fixture.activeCycle.selectedSteps[0];
    const tooling = fixture.activeCycle.selectedSteps[1];
    if (!engineering || !tooling) {
      throw new Error("The fixture requires parallel review steps.");
    }
    const multiStep: GateReviewViewModel = {
      ...fixture,
      activeCycle: {
        ...fixture.activeCycle,
        selectedSteps: [
          engineering,
          {
            ...tooling,
            assignedMember: engineering.assignedMember,
            review: null,
            state: "available",
          },
          ...fixture.activeCycle.selectedSteps.slice(2),
        ],
      },
    };
    renderPage(resolvedDataSource(multiStep));

    const actions = await screen.findByRole("combobox", {
      name: "Review action",
    });
    expect(
      within(actions).getByRole("option", {
        name: "Submit review: ENGINEERING_REVIEW",
      }),
    ).toHaveValue("review:ENGINEERING_REVIEW");
    expect(
      within(actions).getByRole("option", {
        name: "Submit review: TOOLING_REVIEW",
      }),
    ).toHaveValue("review:TOOLING_REVIEW");
  });

  it("starts a cycle from the exact policy and explicit bindings", async () => {
    const fixture = gateReviewNoCycleFixture();
    const updated = gateReviewFixture();
    const startReview = vi.fn<GateReviewDataSource["startReview"]>(() =>
      Promise.resolve(updated),
    );
    renderPage(resolvedDataSource(fixture, { startReview }));
    const user = userEvent.setup();

    expect(await screen.findByText("No active review cycle")).toBeVisible();
    const start = await screen.findByRole("button", { name: "Start review" });
    await user.click(start);

    await waitFor(() => {
      expect(startReview).toHaveBeenCalledTimes(1);
    });
    const call = startReview.mock.calls[0];
    expect(call?.[0]).toBe(fixture.project.globalId);
    expect(call?.[1]).toBe(fixture.gate.globalId);
    expect(call?.[2].expectedGateVersion).toBe(fixture.gate.version);
    expect(call?.[2].policyGlobalId).toBe(gateReviewFixtureIds.policy);
    expect(call?.[2].policyVersion).toBe(1);
    expect(call?.[2].bindings.map((binding) => binding.slot)).toEqual([
      "engineering_review",
      "tooling_review",
      "quality_review",
      "decision_authority",
      "reopen_authority",
      "exception_authority",
    ]);
    expect(call?.[3].csrfToken).toBe(csrfToken);
    expect(call?.[3].idempotencyKey).toMatch(/^gate-review:/u);
    expect(call?.[3].signal).toBeInstanceOf(AbortSignal);
  });

  it("fails closed when no published policy or eligible authority member is available", async () => {
    const fixture: GateReviewViewModel = {
      ...gateReviewNoCycleFixture(),
      availablePolicies: [],
      eligibleMembers: [],
    };
    renderPage(resolvedDataSource(fixture));

    expect(
      await screen.findByText(
        "No applicable published review policy is available.",
      ),
    ).toBeVisible();
    expect(
      screen.getByText(
        "No enabled internal Project member is available for authority binding.",
      ),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Start review" })).toBeDisabled();
  });

  it("submits one assigned review without optimistic completion or double execution", async () => {
    const fixture = gateReviewFixture();
    const pending = deferred<GateReviewViewModel>();
    const submitReview = vi.fn(() => pending.promise);
    renderPage(resolvedDataSource(fixture, { submitReview }));
    const user = userEvent.setup();

    const opinion = await screen.findByRole("textbox", {
      name: "Complete review opinion",
    });
    await user.type(opinion, "The synthetic input is approved.");
    const submit = screen.getByRole("button", {
      name: "Submit review",
    });
    await user.click(submit);
    await user.click(submit);

    expect(submitReview).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Processing Gate review command")).toBeVisible();
    expect(screen.queryByText("Server confirmed")).toBeNull();
    expect(submitReview).toHaveBeenCalledWith(
      fixture.project.globalId,
      fixture.gate.globalId,
      activeCycle(fixture).globalId,
      {
        expectedCycleVersion: activeCycle(fixture).version,
        expectedInputHash: activeCycle(fixture).inputHash,
        opinion: "The synthetic input is approved.",
        outcome: "approved",
        stepKey: "ENGINEERING_REVIEW",
      },
      expect.objectContaining({ csrfToken }),
    );

    pending.resolve(commandUpdatedView(fixture));
    expect(await screen.findByText("Server confirmed")).toBeVisible();
  });

  it("requests a bounded exception through focused impact review", async () => {
    const fixture = gateReviewExceptionEligibleFixture();
    const requestException = vi.fn(() =>
      Promise.resolve(commandUpdatedView(fixture)),
    );
    renderPage(resolvedDataSource(fixture, { requestException }));
    const user = userEvent.setup();

    await user.click(
      await screen.findByRole("button", {
        name: /CUSTOMER_CONFIRMATION Synthetic customer confirmation/u,
      }),
    );
    const action = await screen.findByRole("combobox", {
      name: "Review action",
    });
    await user.selectOptions(
      action,
      `request_exception:${fixture.evidence.requirements[2]?.globalId ?? ""}:controlled_deviation`,
    );
    await user.type(
      screen.getByRole("textbox", { name: "Risk if accepted" }),
      "The deviation needs bounded monitoring.",
    );
    await user.type(
      screen.getByLabelText("Exception expiry date"),
      "2026-08-12",
    );
    await user.click(
      screen.getByRole("button", {
        name: "Request controlled exception",
      }),
    );

    const dialog = screen.getByRole("dialog", {
      name: "Review controlled exception request",
    });
    await user.type(
      within(dialog).getByRole("textbox", { name: "Reason" }),
      "A temporary controlled deviation is required.",
    );
    expect(
      document.querySelectorAll('[data-visual-primary="true"]'),
    ).toHaveLength(1);
    await user.click(
      within(dialog).getByRole("button", {
        name: "Request controlled exception",
      }),
    );

    await waitFor(() => {
      expect(requestException).toHaveBeenCalledTimes(1);
    });
    expect(requestException).toHaveBeenCalledWith(
      fixture.project.globalId,
      fixture.gate.globalId,
      activeCycle(fixture).globalId,
      expect.objectContaining({
        closureActionGlobalId: gateReviewFixtureIds.closureAction,
        expiresAt: "2026-08-12T23:59:59Z",
        kind: "controlled_deviation",
        reason: "A temporary controlled deviation is required.",
        requirementGlobalId: fixture.evidence.requirements[2]?.globalId,
        requirementKey: "CUSTOMER_CONFIRMATION",
        risk: "The deviation needs bounded monitoring.",
      }),
      expect.objectContaining({ csrfToken }),
    );
  });

  it("decides a pending exception with one immutable opinion", async () => {
    const fixture = gateReviewFixture();
    const exception = pendingExceptionFixture();
    const view: GateReviewViewModel = {
      ...fixture,
      activeCycle: {
        ...activeCycle(fixture),
        exceptions: [
          { ...exception, allowedOutcomes: ["approved", "rejected"] },
        ],
      },
      permissions: {
        canApproveException: true,
        canDecide: false,
        canRequestException: false,
        canReopen: false,
        canReview: false,
        canStartReview: false,
        canView: true,
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              sessionBootstrap("exception.authority@example.invalid"),
            ),
            { status: 200 },
          ),
        ),
      ),
    );
    const decideException = vi.fn(() =>
      Promise.resolve(commandUpdatedView(view)),
    );
    renderPage(resolvedDataSource(view, { decideException }));
    const user = userEvent.setup();

    await user.selectOptions(
      await screen.findByRole("combobox", { name: "Exception decision" }),
      "rejected",
    );
    await user.click(
      screen.getByRole("button", {
        name: "Decide exception",
      }),
    );
    const dialog = screen.getByRole("dialog", {
      name: "Review exception decision",
    });
    await user.type(
      within(dialog).getByRole("textbox", { name: "Reason" }),
      "The remaining risk is not acceptable.",
    );
    await user.click(
      within(dialog).getByRole("button", {
        name: "Decide exception",
      }),
    );

    await waitFor(() => {
      expect(decideException).toHaveBeenCalledTimes(1);
    });
    expect(decideException).toHaveBeenCalledWith(
      view.project.globalId,
      view.gate.globalId,
      activeCycle(view).globalId,
      exception.globalId,
      expect.objectContaining({
        expectedExceptionVersion: exception.version,
        opinion: "The remaining risk is not acceptable.",
        outcome: "rejected",
      }),
      expect.objectContaining({ csrfToken }),
    );
  });

  it("decides the Gate with the contract-defined no-reason impact review", async () => {
    const fixture = gateReviewDecisionReadyFixture();
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              sessionBootstrap("decision.authority@example.invalid"),
            ),
            { status: 200 },
          ),
        ),
      ),
    );
    const decided = gateReviewDecidedFixture();
    const decideGate = vi.fn(() => Promise.resolve(decided));
    renderPage(resolvedDataSource(fixture, { decideGate }));
    const user = userEvent.setup();

    const outcome = await screen.findByRole("combobox", {
      name: "Decision outcome",
    });
    expect(
      within(outcome).queryByRole("option", { name: "Conditional pass" }),
    ).toBeNull();
    await user.selectOptions(outcome, "pass");
    await user.click(screen.getByRole("button", { name: "Decide Gate" }));
    const dialog = screen.getByRole("dialog", {
      name: "Review immutable Gate decision",
    });
    expect(
      within(dialog).queryByRole("textbox", { name: "Reason" }),
    ).toBeNull();
    await user.click(
      within(dialog).getByRole("button", { name: "Decide Gate" }),
    );

    await waitFor(() => {
      expect(decideGate).toHaveBeenCalledTimes(1);
    });
    expect(decideGate).toHaveBeenCalledWith(
      fixture.project.globalId,
      fixture.gate.globalId,
      {
        expectedCycleVersion: activeCycle(fixture).version,
        expectedGateVersion: fixture.gate.version,
        expectedInputHash: activeCycle(fixture).inputHash,
        outcome: "pass",
      },
      expect.objectContaining({ csrfToken }),
    );
  });

  it("reopens a decided Gate while preserving exact policy bindings", async () => {
    const fixture = gateReviewDecidedFixture();
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              sessionBootstrap("reopen.authority@example.invalid"),
            ),
            { status: 200 },
          ),
        ),
      ),
    );
    const reopened = gateReviewFixture({
      decisions: fixture.decisions.map((decision) => ({
        ...decision,
        current: false,
      })),
      gate: {
        ...fixture.gate,
        downstreamDecisionCurrent: false,
        reviewState: "in_review",
      },
    });
    const reopenGate = vi.fn(() => Promise.resolve(reopened));
    renderPage(resolvedDataSource(fixture, { reopenGate }));
    const user = userEvent.setup();

    await user.click(
      await screen.findByRole("button", { name: "Reopen Gate" }),
    );
    const dialog = screen.getByRole("dialog", { name: "Review Gate reopen" });
    await user.type(
      within(dialog).getByRole("textbox", { name: "Reason" }),
      "The controlled input changed after the prior decision.",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Reopen Gate" }),
    );

    await waitFor(() => {
      expect(reopenGate).toHaveBeenCalledTimes(1);
    });
    expect(reopenGate).toHaveBeenCalledWith(
      fixture.project.globalId,
      fixture.gate.globalId,
      expect.objectContaining({
        bindings: activeCycle(fixture).bindings.map((binding) => ({
          memberGlobalId: binding.memberGlobalId,
          slot: binding.slot,
        })),
        policyGlobalId: gateReviewFixtureIds.policy,
        reason: "The controlled input changed after the prior decision.",
      }),
      expect.objectContaining({ csrfToken }),
    );
  });

  it.each([
    [404, "GATE_REVIEW_UNAVAILABLE", "Gate Review Room is unavailable"],
    [403, "GATE_REVIEW_ACCESS_DENIED", "Gate review access is not available"],
    [422, "REQUEST_VALIDATION_FAILED", "The Gate review address is invalid"],
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
      expect(document.body).not.toHaveTextContent(
        "Synthetic unresolved dimensional issue",
      );
    },
  );

  it("retries a command with the same idempotency key and never claims early success", async () => {
    const fixture = gateReviewFixture();
    const submitReview = vi
      .fn<GateReviewDataSource["submitReview"]>()
      .mockRejectedValueOnce(problem(503, "GATE_REVIEW_UNAVAILABLE", true))
      .mockResolvedValueOnce(commandUpdatedView(fixture));
    renderPage(resolvedDataSource(fixture, { submitReview }));
    const user = userEvent.setup();

    await user.type(
      await screen.findByRole("textbox", {
        name: "Complete review opinion",
      }),
      "The exact input is acceptable.",
    );
    await user.click(
      screen.getByRole("button", {
        name: "Submit review",
      }),
    );
    const failureAlert = await screen.findByRole("alert", {
      name: "Gate review command failure",
    });
    expect(within(failureAlert).getByText("Retryable failure")).toBeVisible();
    expect(within(failureAlert).getByText("Failed step")).toBeVisible();
    expect(within(failureAlert).getByText("Submit review")).toBeVisible();
    expect(within(failureAlert).getByText("Write confirmation")).toBeVisible();
    expect(
      within(failureAlert).getByText(
        "No successful write was confirmed for this command.",
      ),
    ).toBeVisible();
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.queryByText("Server confirmed")).toBeNull();
    const firstContext = submitReview.mock.calls[0]?.[4];

    await user.click(screen.getByRole("button", { name: "Retry command" }));
    await waitFor(() => {
      expect(submitReview).toHaveBeenCalledTimes(2);
    });
    expect(submitReview.mock.calls[1]?.[4].idempotencyKey).toBe(
      firstContext?.idempotencyKey,
    );
    expect(await screen.findByText("Server confirmed")).toBeVisible();
  });

  it.each([
    [
      "invalid response",
      new NpiTransportError(
        "invalid_response",
        "request-invalid-command-response",
        "request",
      ),
      "Retryable failure",
    ],
    [
      "unexpected final failure",
      new Error("Synthetic unexpected command failure."),
      "Final failure",
    ],
  ] as const)(
    "keeps the receipt and reports an unknown write status for %s",
    async (_caseName, error, failureLabel) => {
      const fixture = gateReviewFixture();
      const submitReview = vi
        .fn<GateReviewDataSource["submitReview"]>()
        .mockRejectedValue(error);
      renderPage(resolvedDataSource(fixture, { submitReview }));
      const user = userEvent.setup();

      await user.type(
        await screen.findByRole("textbox", {
          name: "Complete review opinion",
        }),
        "The exact input is acceptable.",
      );
      await user.click(
        screen.getByRole("button", {
          name: "Submit review",
        }),
      );

      const failureAlert = await screen.findByRole("alert", {
        name: "Gate review command failure",
      });
      expect(within(failureAlert).getByText(failureLabel)).toBeVisible();
      expect(within(failureAlert).getByText("Failed step")).toBeVisible();
      expect(within(failureAlert).getByText("Submit review")).toBeVisible();
      expect(
        within(failureAlert).getByText(
          "The write status is unknown because the command result could not be confirmed. Verify the current Gate review state before preparing another command.",
        ),
      ).toBeVisible();
      expect(
        globalThis.sessionStorage.getItem(GATE_REVIEW_RECEIPT_STORAGE_KEY),
      ).not.toBeNull();
      expect(screen.getAllByRole("alert")).toHaveLength(1);

      globalThis.sessionStorage.removeItem(GATE_REVIEW_RECEIPT_STORAGE_KEY);
    },
  );

  it("keeps one in-flight command through a language refresh and protects ordinary unload", async () => {
    const fixture = gateReviewFixture();
    const languageResponse = deferred<Response>();
    const pending = deferred<GateReviewViewModel>();
    const submitReview = vi.fn<GateReviewDataSource["submitReview"]>(
      () => pending.promise,
    );
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify(sessionBootstrap()), { status: 200 }),
        )
        .mockReturnValueOnce(languageResponse.promise),
    );
    render(
      <I18nProvider>
        <LocaleSwitchControl locale="zh" />
        <GateEvidencePage
          dataSource={resolvedDataSource(fixture, { submitReview })}
          gateGlobalId={fixture.gate.globalId}
          navigate={vi.fn()}
          projectGlobalId={fixture.project.globalId}
        />
      </I18nProvider>,
    );
    const user = userEvent.setup();

    await user.type(
      await screen.findByRole("textbox", {
        name: "Complete review opinion",
      }),
      "The exact input remains acceptable during localization.",
    );
    await user.click(
      screen.getByRole("button", {
        name: "Submit review",
      }),
    );
    const firstContext = submitReview.mock.calls[0]?.[4];
    expect(submitReview).toHaveBeenCalledTimes(1);
    expect(firstContext?.signal.aborted).toBe(false);
    const persistedMarker = JSON.parse(
      globalThis.sessionStorage.getItem(GATE_REVIEW_RECEIPT_STORAGE_KEY) ??
        "{}",
    ) as Record<string, unknown>;
    expect(Object.keys(persistedMarker).sort()).toEqual([
      "actor",
      "gate",
      "issuedAt",
      "key",
      "operation",
      "project",
    ]);
    expect(JSON.stringify(persistedMarker)).not.toContain(
      "The exact input remains acceptable during localization.",
    );
    expect(JSON.stringify(persistedMarker)).not.toContain(csrfToken);

    const blockedUnload = new Event("beforeunload", { cancelable: true });
    expect(globalThis.dispatchEvent(blockedUnload)).toBe(false);
    expect(blockedUnload.defaultPrevented).toBe(true);

    await user.click(
      screen.getByRole("button", { name: "Switch test locale" }),
    );
    expect(
      await screen.findByText("Review commands unavailable"),
    ).toBeVisible();
    await act(async () => {
      languageResponse.resolve(
        new Response(
          JSON.stringify(
            sessionBootstrap("reviewer@example.invalid", "zh", "d".repeat(32)),
          ),
          { status: 200 },
        ),
      );
      await languageResponse.promise;
    });
    await waitFor(() => {
      expect(document.documentElement.lang).toBe("zh");
    });
    expect(firstContext?.signal.aborted).toBe(false);
    expect(submitReview).toHaveBeenCalledTimes(1);

    pending.resolve(commandUpdatedView(fixture));
    expect(await screen.findByText("服务器已确认")).toBeVisible();
    expect(submitReview).toHaveBeenCalledTimes(1);
    expect(firstContext?.signal.aborted).toBe(false);

    const releasedUnload = new Event("beforeunload", { cancelable: true });
    expect(globalThis.dispatchEvent(releasedUnload)).toBe(true);
    expect(releasedUnload.defaultPrevented).toBe(false);
  });

  it("retranslates a failed command from its stable action code after a language refresh", async () => {
    const fixture = gateReviewFixture();
    const languageResponse = deferred<Response>();
    const pending = deferred<GateReviewViewModel>();
    const submitReview = vi.fn<GateReviewDataSource["submitReview"]>(
      () => pending.promise,
    );
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify(sessionBootstrap()), { status: 200 }),
        )
        .mockReturnValueOnce(languageResponse.promise),
    );
    render(
      <I18nProvider>
        <LocaleSwitchControl locale="zh" />
        <GateEvidencePage
          dataSource={resolvedDataSource(fixture, { submitReview })}
          gateGlobalId={fixture.gate.globalId}
          navigate={vi.fn()}
          projectGlobalId={fixture.project.globalId}
        />
      </I18nProvider>,
    );
    const user = userEvent.setup();

    await user.type(
      await screen.findByRole("textbox", {
        name: "Complete review opinion",
      }),
      "The exact input remains acceptable during localization.",
    );
    await user.click(
      screen.getByRole("button", {
        name: "Submit review",
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Switch test locale" }),
    );
    await act(async () => {
      languageResponse.resolve(
        new Response(
          JSON.stringify(
            sessionBootstrap("reviewer@example.invalid", "zh", "d".repeat(32)),
          ),
          { status: 200 },
        ),
      );
      await languageResponse.promise;
    });
    await waitFor(() => {
      expect(document.documentElement.lang).toBe("zh");
    });

    await act(async () => {
      pending.reject(
        new NpiTransportError(
          "network",
          "request-command-language-refresh",
          "request",
        ),
      );
      await pending.promise.catch(() => undefined);
    });
    const failureAlert = await screen.findByRole("alert", {
      name: "阶段门评审命令失败",
    });
    expect(within(failureAlert).getByText("失败步骤")).toBeVisible();
    expect(within(failureAlert).getByText("提交评审")).toBeVisible();
    expect(within(failureAlert).getByText("写入确认")).toBeVisible();
    expect(
      within(failureAlert).getByText(
        "由于无法确认命令结果，写入状态未知。准备其他命令前，请核对当前阶段门评审状态。",
      ),
    ).toBeVisible();
    expect(within(failureAlert).queryByText("Submit review")).toBeNull();
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("reconciles a completed persisted receipt before loading authoritative workspace", async () => {
    const fixture = gateReviewFixture();
    const marker = persistedReceiptMarker(fixture);
    globalThis.sessionStorage.setItem(
      GATE_REVIEW_RECEIPT_STORAGE_KEY,
      JSON.stringify(marker),
    );
    const load = vi.fn<GateReviewDataSource["load"]>(() =>
      Promise.resolve(fixture),
    );
    const reconcileCommandReceipt = vi.fn<
      GateReviewDataSource["reconcileCommandReceipt"]
    >(() =>
      Promise.resolve({
        operation: "gate.review.submit",
        status: "completed",
        workspaceReloadRequired: true,
      }),
    );

    renderPage(resolvedDataSource(fixture, { load, reconcileCommandReceipt }));

    expect(
      await screen.findByText(
        "The server confirmed the review workspace update.",
      ),
    ).toBeVisible();
    expect(reconcileCommandReceipt).toHaveBeenCalledWith(
      fixture.project.globalId,
      fixture.gate.globalId,
      "gate.review.submit",
      expect.objectContaining({ idempotencyKey: marker.key }),
    );
    expect(load).toHaveBeenCalledTimes(1);
    expect(
      globalThis.sessionStorage.getItem(GATE_REVIEW_RECEIPT_STORAGE_KEY),
    ).toBeNull();
  });

  it("reconciles a prior Gate marker without reporting that update on the current Gate", async () => {
    const priorGate = gateReviewFixture();
    const currentGateId = "abababab-abab-4bab-8bab-abababababab";
    const currentGate: GateReviewViewModel = {
      ...priorGate,
      evidence: {
        ...priorGate.evidence,
        gate: {
          ...priorGate.evidence.gate,
          globalId: currentGateId,
        },
      },
      gate: {
        ...priorGate.gate,
        globalId: currentGateId,
      },
    };
    const marker = persistedReceiptMarker(priorGate);
    globalThis.sessionStorage.setItem(
      GATE_REVIEW_RECEIPT_STORAGE_KEY,
      JSON.stringify(marker),
    );
    const load = vi.fn<GateReviewDataSource["load"]>(() =>
      Promise.resolve(currentGate),
    );
    const reconcileCommandReceipt = vi.fn<
      GateReviewDataSource["reconcileCommandReceipt"]
    >(() =>
      Promise.resolve({
        operation: "gate.review.submit",
        status: "completed",
        workspaceReloadRequired: true,
      }),
    );

    renderWithLocale(
      <GateEvidencePage
        dataSource={resolvedDataSource(currentGate, {
          load,
          reconcileCommandReceipt,
        })}
        gateGlobalId={currentGateId}
        navigate={vi.fn()}
        projectGlobalId={currentGate.project.globalId}
      />,
    );

    expect(
      await screen.findByRole("table", { name: "Frozen Gate requirements" }),
    ).toBeVisible();
    expect(reconcileCommandReceipt).toHaveBeenCalledWith(
      priorGate.project.globalId,
      priorGate.gate.globalId,
      "gate.review.submit",
      expect.objectContaining({ idempotencyKey: marker.key }),
    );
    expect(load).toHaveBeenCalledWith(
      currentGate.project.globalId,
      currentGateId,
      expect.any(AbortSignal),
    );
    expect(
      screen.queryByText("The server confirmed the review workspace update."),
    ).toBeNull();
    expect(screen.queryByText("Server confirmed")).toBeNull();
  });

  it("bounds absent receipt retries, reloads, and asks for current-state verification without claiming non-submission", async () => {
    const fixture = gateReviewFixture();
    const marker = persistedReceiptMarker(fixture);
    globalThis.sessionStorage.setItem(
      GATE_REVIEW_RECEIPT_STORAGE_KEY,
      JSON.stringify(marker),
    );
    const reconcileCommandReceipt = vi.fn<
      GateReviewDataSource["reconcileCommandReceipt"]
    >(() =>
      Promise.resolve({
        operation: "gate.review.submit",
        status: "absent",
        workspaceReloadRequired: true,
      }),
    );
    const load = vi.fn<GateReviewDataSource["load"]>(() =>
      Promise.resolve(fixture),
    );

    renderPage(resolvedDataSource(fixture, { load, reconcileCommandReceipt }));

    expect(
      await screen.findByText(
        "No completed command record was found yet. The workspace was reloaded; verify its current state and re-enter the command inputs before submitting again.",
        {},
        { timeout: 3000 },
      ),
    ).toBeVisible();
    expect(reconcileCommandReceipt).toHaveBeenCalledTimes(4);
    expect(load).toHaveBeenCalledTimes(1);
    expect(document.body).not.toHaveTextContent(
      "The server did not record this command",
    );
    expect(
      globalThis.sessionStorage.getItem(GATE_REVIEW_RECEIPT_STORAGE_KEY),
    ).toBeNull();
  });

  it("retains another actor's unresolved marker without querying or exposing its result", async () => {
    const fixture = gateReviewFixture();
    globalThis.sessionStorage.setItem(
      GATE_REVIEW_RECEIPT_STORAGE_KEY,
      JSON.stringify(
        persistedReceiptMarker(fixture, "previous.actor@example.invalid"),
      ),
    );
    const reconcileCommandReceipt =
      vi.fn<GateReviewDataSource["reconcileCommandReceipt"]>();
    const load = vi.fn<GateReviewDataSource["load"]>(() =>
      Promise.resolve(fixture),
    );

    renderPage(resolvedDataSource(fixture, { load, reconcileCommandReceipt }));

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: /G1 \/ SYN-PROJECT-001 Synthetic initiation evidence/u,
      }),
    ).toBeVisible();
    expect(reconcileCommandReceipt).not.toHaveBeenCalled();
    expect(load).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Server confirmed")).toBeNull();
    expect(
      globalThis.sessionStorage.getItem(GATE_REVIEW_RECEIPT_STORAGE_KEY),
    ).toBe(
      JSON.stringify(
        persistedReceiptMarker(fixture, "previous.actor@example.invalid"),
      ),
    );
  });

  it("clears a terminal receipt lookup marker and reloads without claiming a command result", async () => {
    const fixture = gateReviewFixture();
    globalThis.sessionStorage.setItem(
      GATE_REVIEW_RECEIPT_STORAGE_KEY,
      JSON.stringify(persistedReceiptMarker(fixture)),
    );
    const reconcileCommandReceipt = vi.fn<
      GateReviewDataSource["reconcileCommandReceipt"]
    >(() => Promise.reject(problem(403, "GATE_REVIEW_ACCESS_DENIED")));
    const load = vi.fn<GateReviewDataSource["load"]>(() =>
      Promise.resolve(fixture),
    );

    renderPage(resolvedDataSource(fixture, { load, reconcileCommandReceipt }));

    expect(
      await screen.findByText(
        "The command receipt could not be reconciled. The workspace was reloaded without claiming a command result; verify its current state before submitting another command.",
      ),
    ).toBeVisible();
    expect(load).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Server confirmed")).toBeNull();
    expect(
      globalThis.sessionStorage.getItem(GATE_REVIEW_RECEIPT_STORAGE_KEY),
    ).toBeNull();
  });

  it("reattaches a rejected command after an SPA route change and retries its prepared key", async () => {
    const fixture = gateReviewFixture();
    const pending = deferred<GateReviewViewModel>();
    const submitReview = vi
      .fn<GateReviewDataSource["submitReview"]>()
      .mockImplementationOnce(() => pending.promise)
      .mockResolvedValueOnce(commandUpdatedView(fixture));
    const dataSource = resolvedDataSource(fixture, { submitReview });
    const gatePage = (
      <GateEvidencePage
        dataSource={dataSource}
        gateGlobalId={fixture.gate.globalId}
        navigate={vi.fn()}
        projectGlobalId={fixture.project.globalId}
      />
    );
    const rendered = render(<I18nProvider>{gatePage}</I18nProvider>);
    const user = userEvent.setup();

    await user.type(
      await screen.findByRole("textbox", {
        name: "Complete review opinion",
      }),
      "The exact input remains acceptable after route navigation.",
    );
    await user.click(
      screen.getByRole("button", {
        name: "Submit review",
      }),
    );
    const firstContext = submitReview.mock.calls[0]?.[4];
    rendered.rerender(
      <I18nProvider>
        <div>Temporary Project route</div>
      </I18nProvider>,
    );
    expect(screen.getByText("Temporary Project route")).toBeVisible();
    await act(async () => {
      pending.reject(problem(503, "GATE_REVIEW_UNAVAILABLE", true));
      await pending.promise.catch(() => undefined);
    });

    rendered.rerender(<I18nProvider>{gatePage}</I18nProvider>);
    expect(await screen.findByText("Retryable failure")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry command" }));
    await waitFor(() => {
      expect(submitReview).toHaveBeenCalledTimes(2);
    });
    expect(submitReview.mock.calls[1]?.[4].idempotencyKey).toBe(
      firstContext?.idempotencyKey,
    );
    expect(await screen.findByText("Server confirmed")).toBeVisible();
  });

  it("discards an old actor command result after session rotation and reloads current authority", async () => {
    const fixture = gateReviewFixture();
    const languageResponse = deferred<Response>();
    const pending = deferred<GateReviewViewModel>();
    const load = vi.fn<GateReviewDataSource["load"]>(() =>
      Promise.resolve(fixture),
    );
    const submitReview = vi.fn<GateReviewDataSource["submitReview"]>(
      () => pending.promise,
    );
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify(sessionBootstrap()), { status: 200 }),
        )
        .mockReturnValueOnce(languageResponse.promise),
    );
    render(
      <I18nProvider>
        <LocaleSwitchControl locale="zh" />
        <GateEvidencePage
          dataSource={resolvedDataSource(fixture, { load, submitReview })}
          gateGlobalId={fixture.gate.globalId}
          navigate={vi.fn()}
          projectGlobalId={fixture.project.globalId}
        />
      </I18nProvider>,
    );
    const user = userEvent.setup();

    await user.type(
      await screen.findByRole("textbox", {
        name: "Complete review opinion",
      }),
      "The original actor prepared this exact review.",
    );
    await user.click(
      screen.getByRole("button", {
        name: "Submit review",
      }),
    );
    const originalContext = submitReview.mock.calls[0]?.[4];
    await user.click(
      screen.getByRole("button", { name: "Switch test locale" }),
    );
    await act(async () => {
      languageResponse.resolve(
        new Response(
          JSON.stringify(
            sessionBootstrap(
              "rotated.actor@example.invalid",
              "zh",
              "e".repeat(32),
            ),
          ),
          { status: 200 },
        ),
      );
      await languageResponse.promise;
    });
    await waitFor(() => {
      expect(document.documentElement.lang).toBe("zh");
    });
    expect(load).toHaveBeenCalledTimes(1);
    expect(
      globalThis.sessionStorage.getItem(GATE_REVIEW_RECEIPT_STORAGE_KEY),
    ).not.toBeNull();
    expect(originalContext?.signal.aborted).toBe(false);

    pending.resolve({
      ...commandUpdatedView(fixture),
      gate: {
        ...fixture.gate,
        title: "Old actor result must not render",
      },
    });
    await waitFor(() => {
      expect(load).toHaveBeenCalledTimes(2);
    });
    expect(originalContext?.signal.aborted).toBe(false);
    expect(screen.queryByText("Old actor result must not render")).toBeNull();
    expect(screen.queryByText("服务器已确认")).toBeNull();
    expect(screen.queryByText("Server confirmed")).toBeNull();
    expect(
      globalThis.sessionStorage.getItem(GATE_REVIEW_RECEIPT_STORAGE_KEY),
    ).toBeNull();
  });

  it("requires a reload after command conflict and does not blind-retry validation", async () => {
    const fixture = gateReviewFixture();
    const load = vi
      .fn<GateReviewDataSource["load"]>()
      .mockResolvedValueOnce(fixture)
      .mockResolvedValueOnce(fixture);
    const submitReview = vi
      .fn<GateReviewDataSource["submitReview"]>()
      .mockRejectedValue(problem(409, "VERSION_CONFLICT"));
    renderPage(resolvedDataSource(fixture, { load, submitReview }));
    const user = userEvent.setup();

    await user.type(
      await screen.findByRole("textbox", {
        name: "Complete review opinion",
      }),
      "A stale review opinion.",
    );
    await user.click(
      screen.getByRole("button", {
        name: "Submit review",
      }),
    );
    const failureAlert = await screen.findByRole("alert", {
      name: "Gate review command failure",
    });
    expect(within(failureAlert).getByText("Version conflict")).toBeVisible();
    expect(within(failureAlert).getByText("Failed step")).toBeVisible();
    expect(within(failureAlert).getByText("Submit review")).toBeVisible();
    expect(
      within(failureAlert).getByText(
        "No successful write was confirmed for this command.",
      ),
    ).toBeVisible();
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Retry command" })).toBeNull();
    await user.click(
      screen.getByRole("button", { name: "Reload Gate review" }),
    );
    await waitFor(() => {
      expect(load).toHaveBeenCalledTimes(2);
    });
    expect(submitReview).toHaveBeenCalledTimes(1);
  });

  it("treats an invalid client route as validation without a blind retry", async () => {
    const fixture = gateReviewFixture();
    const navigate = vi.fn<(target: string) => void>();
    const user = userEvent.setup();
    renderWithLocale(
      <GateEvidencePage
        dataSource={rejectedDataSource(
          new NpiTransportError(
            "request_not_ready",
            "client-gate-review-address",
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
        name: "The Gate review address is invalid",
      }),
    ).toBeVisible();
    expect(screen.getByText("client-gate-review-address")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Return to My Work" }));
    expect(navigate).toHaveBeenCalledWith("/work");
  });
});
