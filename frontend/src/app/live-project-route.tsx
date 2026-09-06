import { LiveChangeControlDataSource } from "../api/change-control-data-source";
import type { CollaborationDataSource } from "../api/collaboration-data-source";
import { LiveControlledPrintDataSource } from "../api/controlled-print-data-source";
import { LiveDocumentDataSource } from "../api/document-data-source";
import { LiveEngineeringBomDataSource } from "../api/ebom-data-source";
import { LiveItemPublishDataSource } from "../api/item-publish-data-source";
import { LiveMbomPublishDataSource } from "../api/mbom-publish-data-source";
import type { ProjectControlsDataSource } from "../api/project-controls-data-source";
import { LiveProjectCockpitDataSource } from "../api/project-data-source";
import {
  LiveProjectDomainWorkItemsDataSource,
  LiveProjectWorkContextDataSource,
} from "../api/project-work-data-source";
import { LiveProductionTransitionDataSource } from "../api/production-transition-data-source";
import { LiveEngineeringBomPublishRequestDataSource } from "../api/publish-request-data-source";
import { LiveReadinessDataSource } from "../api/readiness-data-source";
import type {
  ReportWorkspaceDirty,
  RequestWorkspaceTransition,
} from "./workspace-navigation";
import ProjectPage from "../pages/project-page";

const dataSource = new LiveProjectCockpitDataSource();
const contextDataSource = new LiveProjectWorkContextDataSource();
const domainWorkItemsDataSource = new LiveProjectDomainWorkItemsDataSource();
const controlledPrintDataSource = new LiveControlledPrintDataSource();
const documentDataSource = new LiveDocumentDataSource();
const engineeringBomDataSource = new LiveEngineeringBomDataSource();
const itemPublishDataSource = new LiveItemPublishDataSource();
const mbomPublishDataSource = new LiveMbomPublishDataSource();
const publishRequestDataSource =
  new LiveEngineeringBomPublishRequestDataSource();
const productionTransitionDataSource = new LiveProductionTransitionDataSource();
const readinessDataSource = new LiveReadinessDataSource();
const changeControlDataSource = new LiveChangeControlDataSource();

export default function LiveProjectRoute({
  collaborationDataSource,
  controlsDataSource,
  globalId,
  navigate,
  reportWorkspaceDirty,
  requestWorkspaceTransition,
}: {
  collaborationDataSource: CollaborationDataSource;
  controlsDataSource: ProjectControlsDataSource;
  globalId: string;
  navigate: (target: string) => void;
  reportWorkspaceDirty: ReportWorkspaceDirty;
  requestWorkspaceTransition: RequestWorkspaceTransition;
}): React.JSX.Element {
  return (
    <ProjectPage
      changeControlDataSource={changeControlDataSource}
      collaborationDataSource={collaborationDataSource}
      contextDataSource={contextDataSource}
      controlledPrintDataSource={controlledPrintDataSource}
      controlsDataSource={controlsDataSource}
      dataSource={dataSource}
      documentDataSource={documentDataSource}
      domainWorkItemsDataSource={domainWorkItemsDataSource}
      engineeringBomDataSource={engineeringBomDataSource}
      globalId={globalId}
      itemPublishDataSource={itemPublishDataSource}
      mbomPublishDataSource={mbomPublishDataSource}
      navigate={navigate}
      productionTransitionDataSource={productionTransitionDataSource}
      publishRequestDataSource={publishRequestDataSource}
      readinessDataSource={readinessDataSource}
      reportWorkspaceDirty={reportWorkspaceDirty}
      requestWorkspaceTransition={requestWorkspaceTransition}
    />
  );
}
