import { describe, expect, it, vi } from "vitest";

import type { CollaborationDataSource } from "../../src/api/collaboration-data-source";
import type { ProjectControlsDataSource } from "../../src/api/project-controls-data-source";
import LiveExecutionRoute from "../../src/app/live-execution-route";
import LiveGateRoute from "../../src/app/live-gate-route";
import LiveProjectRoute from "../../src/app/live-project-route";
import LiveToolingRoute from "../../src/app/live-tooling-route";
import LiveTrialRoute from "../../src/app/live-trial-route";
import LiveWorkRoute from "../../src/app/live-work-route";
import ToolingImportRoute from "../../src/app/tooling-import-route";
import ExecutionPage from "../../src/pages/execution-page";
import GateEvidencePage from "../../src/pages/gate-evidence-page";
import LiveToolingPage from "../../src/pages/live-tooling-page";
import LiveTrialPage from "../../src/pages/live-trial-page";
import LiveWorkPage from "../../src/pages/live-work-page";
import ProjectPage from "../../src/pages/project-page";
import ToolingImportWorkspace from "../../src/pages/tooling-import-workspace";

describe("route-owned live data sources", () => {
  const navigate = vi.fn();
  const reportWorkspaceDirty = vi.fn();

  it("keeps each lightweight route bound to its original page contract", () => {
    const work = LiveWorkRoute({ navigate });
    expect(work.type).toBe(LiveWorkPage);
    expect(work.props).toMatchObject({ navigate });

    const execution = LiveExecutionRoute({ projectId: "project-id" });
    expect(execution.type).toBe(ExecutionPage);
    expect(execution.props).toMatchObject({ projectId: "project-id" });

    const gate = LiveGateRoute({
      gateGlobalId: "gate-id",
      navigate,
      projectGlobalId: "project-id",
    });
    expect(gate.type).toBe(GateEvidencePage);
    expect(gate.props).toMatchObject({
      gateGlobalId: "gate-id",
      navigate,
      projectGlobalId: "project-id",
    });

    const tooling = LiveToolingRoute({
      masterId: "tool-id",
      navigate,
      projectId: "project-id",
      reportWorkspaceDirty,
    });
    expect(tooling.type).toBe(LiveToolingPage);
    expect(tooling.props).toMatchObject({
      masterId: "tool-id",
      navigate,
      projectId: "project-id",
      reportWorkspaceDirty,
    });

    const toolingImport = ToolingImportRoute({
      navigate,
      projectId: "project-id",
      reportWorkspaceDirty,
    });
    expect(toolingImport.type).toBe(ToolingImportWorkspace);
    expect(toolingImport.props).toMatchObject({
      navigate,
      projectId: "project-id",
      reportWorkspaceDirty,
    });

    const trial = LiveTrialRoute({
      navigate,
      projectId: "project-id",
      reportWorkspaceDirty,
    });
    expect(trial.type).toBe(LiveTrialPage);
    expect(trial.props).toMatchObject({
      navigate,
      projectId: "project-id",
      reportWorkspaceDirty,
    });
  });

  it("keeps the Project route's shared and route-owned dependencies distinct", () => {
    const collaborationDataSource = {} as CollaborationDataSource;
    const controlsDataSource = {} as ProjectControlsDataSource;
    const requestWorkspaceTransition = vi.fn();
    const project = LiveProjectRoute({
      collaborationDataSource,
      controlsDataSource,
      globalId: "project-id",
      navigate,
      reportWorkspaceDirty,
      requestWorkspaceTransition,
    });

    expect(project.type).toBe(ProjectPage);
    expect(project.props).toMatchObject({
      collaborationDataSource,
      controlsDataSource,
      globalId: "project-id",
      navigate,
      reportWorkspaceDirty,
      requestWorkspaceTransition,
    });
    const projectProps = project.props as Readonly<Record<string, unknown>>;
    for (const routeOwnedName of [
      "changeControlDataSource",
      "contextDataSource",
      "controlledPrintDataSource",
      "dataSource",
      "documentDataSource",
      "domainWorkItemsDataSource",
      "engineeringBomDataSource",
      "itemPublishDataSource",
      "mbomPublishDataSource",
      "productionTransitionDataSource",
      "publishRequestDataSource",
      "readinessDataSource",
    ]) {
      expect(projectProps[routeOwnedName]).toBeDefined();
    }
  });
});
