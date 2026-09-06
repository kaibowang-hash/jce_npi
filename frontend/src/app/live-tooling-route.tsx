import { LiveDocumentDataSource } from "../api/document-data-source";
import { LiveToolingDataSource } from "../api/tooling-data-source";
import { LiveToolingListDataSource } from "../api/tooling-list-data-source";
import type { ReportWorkspaceDirty } from "./workspace-navigation";
import LiveToolingPage from "../pages/live-tooling-page";

const dataSource = new LiveToolingDataSource();
const documentDataSource = new LiveDocumentDataSource();
const toolingListDataSource = new LiveToolingListDataSource();

export default function LiveToolingRoute({
  masterId,
  navigate,
  projectId,
  reportWorkspaceDirty,
}: {
  masterId: string | null;
  navigate: (target: string) => void;
  projectId: string;
  reportWorkspaceDirty: ReportWorkspaceDirty;
}): React.JSX.Element {
  return (
    <LiveToolingPage
      dataSource={dataSource}
      documentDataSource={documentDataSource}
      masterId={masterId}
      navigate={navigate}
      projectId={projectId}
      reportWorkspaceDirty={reportWorkspaceDirty}
      toolingListDataSource={toolingListDataSource}
    />
  );
}
