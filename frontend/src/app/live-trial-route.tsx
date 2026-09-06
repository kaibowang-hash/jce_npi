import { LiveControlledPrintDataSource } from "../api/controlled-print-data-source";
import { LiveTrialDataSource } from "../api/trial-data-source";
import type { ReportWorkspaceDirty } from "./workspace-navigation";
import LiveTrialPage from "../pages/live-trial-page";

const controlledPrintDataSource = new LiveControlledPrintDataSource();
const dataSource = new LiveTrialDataSource();

export default function LiveTrialRoute({
  navigate,
  projectId,
  reportWorkspaceDirty,
}: {
  navigate: (target: string) => void;
  projectId: string;
  reportWorkspaceDirty: ReportWorkspaceDirty;
}): React.JSX.Element {
  return (
    <LiveTrialPage
      controlledPrintDataSource={controlledPrintDataSource}
      dataSource={dataSource}
      navigate={navigate}
      projectId={projectId}
      reportWorkspaceDirty={reportWorkspaceDirty}
    />
  );
}
