import { LiveToolingImportDataSource } from "../api/tooling-import-data-source";
import type { ReportWorkspaceDirty } from "./workspace-navigation";
import ToolingImportWorkspace from "../pages/tooling-import-workspace";

const dataSource = new LiveToolingImportDataSource();

export default function ToolingImportRoute({
  navigate,
  projectId,
  reportWorkspaceDirty,
}: {
  navigate: (target: string) => void;
  projectId: string;
  reportWorkspaceDirty: ReportWorkspaceDirty;
}): React.JSX.Element {
  return (
    <ToolingImportWorkspace
      dataSource={dataSource}
      navigate={navigate}
      projectId={projectId}
      reportWorkspaceDirty={reportWorkspaceDirty}
    />
  );
}
